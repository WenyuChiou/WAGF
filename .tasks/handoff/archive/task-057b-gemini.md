# Task-057B: Source-Stratified Memory Retrieval (Gemini Assignment)

**Assigned To**: Gemini
**Status**: COMPLETED
**Priority**: High
**Estimated Scope**: ~85 lines new, 1 file + 1 test file
**Depends On**: None (Phase 1 — can run in parallel with 057-A)

---

## Objective

Add a `retrieve_stratified()` method to `HumanCentricMemoryEngine` that allocates retrieval slots by memory source category, ensuring diversity in reflected memories.

Currently `retrieve()` returns top-k by `(recency × 0.3) + (importance × 0.5) + (context × 0.2)` scoring. High-importance reflection memories (stored with importance=0.9) crowd out lower-scored episodic, neighbor, and community memories. This means the reflection prompt sees homogeneous input.

---

## Context

### Current Retrieval Code (`broker/components/engines/humancentric_engine.py`, line 292-333)

```python
# MODE 2: WEIGHTED
scored_memories = []
for mem in all_memories:
    age = current_time - mem["timestamp"]
    recency_score = 1.0 - (age / max(current_time, 1))
    importance_score = mem.get("importance", ...)
    contextual_boost = ...
    final_score = (recency_score * self.W_recency) + \
                  (importance_score * self.W_importance) + \
                  (contextual_boost * self.W_context)
    scored_memories.append((mem["content"], final_score))

top_k_memories = heapq.nlargest(top_k, scored_memories, key=lambda x: x[1])
return [content for content, score in top_k_memories]
```

### Memory Item Structure (line 203-211)

```python
memory_item = {
    "content": str,
    "importance": float,       # 0.0 - 1.0
    "emotion": str,            # "critical" | "major" | "positive" | "shift" | "observation" | "routine"
    "source": str,             # "personal" | "neighbor" | "community" | "abstract" | "social"
    "timestamp": int,
    "consolidated": bool,
    "type": str,               # optional: "reflection" | "reasoning" | "event" | ...
}
```

### Problem

With pure top-k scoring, high-importance reflection memories (0.9) always win over neighbor observations (0.4-0.5) and community events (0.5-0.7), creating an echo chamber.

---

## Changes Required

### File: `broker/components/engines/humancentric_engine.py`

**Change:** Add `retrieve_stratified()` method after `retrieve()` (after line 333):

```python
def retrieve_stratified(
    self,
    agent_id: str,
    allocation: Optional[Dict[str, int]] = None,
    total_k: int = 10,
    contextual_boosters: Optional[Dict[str, float]] = None,
) -> List[str]:
    """Retrieve memories with source-stratified diversity guarantee.

    Instead of pure top-k by score, allocates retrieval slots by source category.
    This ensures reflection prompts see a mix of personal experiences,
    neighbor observations, community events, and past reflections.

    Args:
        agent_id: Agent to retrieve for
        allocation: Dict mapping source -> max slots.
                    Default: {"personal": 4, "neighbor": 2, "community": 2, "reflection": 1, "abstract": 1}
        total_k: Total memories to return (cap)
        contextual_boosters: Same as retrieve() -- optional score boosters

    Returns:
        List of memory content strings, stratified by source
    """
    if allocation is None:
        allocation = {
            "personal": 4,
            "neighbor": 2,
            "community": 2,
            "reflection": 1,
            "abstract": 1,
        }

    working = self.working.get(agent_id, [])
    longterm = self.longterm.get(agent_id, [])

    if not working and not longterm:
        return []

    # Combine all memories (same dedup logic as retrieve weighted mode)
    max_timestamp = -1
    if working:
        max_timestamp = max(max_timestamp, max(m["timestamp"] for m in working))
    if longterm:
        max_timestamp = max(max_timestamp, max(m["timestamp"] for m in longterm))
    current_time = max_timestamp + 1

    all_memories_map = {}
    for mem in self._apply_decay(longterm, current_time):
        all_memories_map[mem["content"]] = mem
    for mem in working:
        all_memories_map[mem["content"]] = mem
    all_memories = list(all_memories_map.values())

    # Score all memories (same scoring as weighted mode)
    scored = []
    for mem in all_memories:
        age = current_time - mem["timestamp"]
        recency_score = 1.0 - (age / max(current_time, 1))
        importance_score = mem.get("importance", mem.get("decayed_importance", 0.1))

        contextual_boost = 0.0
        if contextual_boosters:
            for tag_key_val, boost_val in contextual_boosters.items():
                if ":" in tag_key_val:
                    tag_cat, tag_val = tag_key_val.split(":", 1)
                    if mem.get(tag_cat) == tag_val:
                        contextual_boost = boost_val
                        break

        final_score = (recency_score * self.W_recency) + \
                      (importance_score * self.W_importance) + \
                      (contextual_boost * self.W_context)

        scored.append((mem, final_score))

    # Group by source
    import heapq
    source_groups: Dict[str, List] = {}
    for mem, score in scored:
        src = mem.get("source", "abstract")
        # Map reflection-sourced memories
        if mem.get("type") == "reflection" or "Consolidated Reflection" in mem.get("content", ""):
            src = "reflection"
        if src not in source_groups:
            source_groups[src] = []
        source_groups[src].append((mem["content"], score))

    # Sort each group by score descending
    for src in source_groups:
        source_groups[src].sort(key=lambda x: -x[1])

    # Allocate slots per source
    result = []
    remaining_slots = total_k

    for src, max_slots in allocation.items():
        available = source_groups.get(src, [])
        take = min(max_slots, len(available), remaining_slots)
        for content, score in available[:take]:
            result.append(content)
            remaining_slots -= 1
        if remaining_slots <= 0:
            break

    # Fill remaining slots with highest-scoring memories from any source
    if remaining_slots > 0:
        all_sorted = sorted(scored, key=lambda x: -x[1])
        for mem, score in all_sorted:
            if mem["content"] not in result and remaining_slots > 0:
                result.append(mem["content"])
                remaining_slots -= 1

    return result
```

---

## Verification

### 1. Add test file

**File**: `tests/test_stratified_retrieval.py`

```python
"""Tests for source-stratified memory retrieval (Task-057B)."""
import pytest
from broker.components.engines.humancentric_engine import HumanCentricMemoryEngine


@pytest.fixture
def engine():
    e = HumanCentricMemoryEngine(ranking_mode="weighted")
    return e


@pytest.fixture
def populated_engine(engine):
    """Engine with diverse source memories."""
    agent_id = "H_001"

    # Personal memories (5)
    for i in range(5):
        engine.add_memory(agent_id, f"Year {i+1}: I experienced flooding.",
                          metadata={"source": "personal", "importance": 0.6, "emotion": "critical"})

    # Neighbor memories (3)
    for i in range(3):
        engine.add_memory(agent_id, f"Neighbor {i+1} elevated their house.",
                          metadata={"source": "neighbor", "importance": 0.5, "emotion": "observation"})

    # Community memories (3)
    for i in range(3):
        engine.add_memory(agent_id, f"Community meeting about flood policy #{i+1}.",
                          metadata={"source": "community", "importance": 0.7, "emotion": "major"})

    # Abstract/reflection (2)
    engine.add_memory(agent_id, "Consolidated Reflection: Safety matters most.",
                      metadata={"source": "personal", "importance": 0.9, "emotion": "major", "type": "reflection"})
    engine.add_memory(agent_id, "Government announced new grant program.",
                      metadata={"source": "abstract", "importance": 0.4, "emotion": "observation"})

    return engine


class TestStratifiedRetrieval:
    def test_default_allocation_returns_diverse_sources(self, populated_engine):
        memories = populated_engine.retrieve_stratified("H_001")
        assert len(memories) == 10

        # Check diversity: should contain memories from multiple sources
        has_personal = any("experienced" in m for m in memories)
        has_neighbor = any("Neighbor" in m for m in memories)
        has_community = any("Community" in m for m in memories)
        assert has_personal
        assert has_neighbor
        assert has_community

    def test_custom_allocation(self, populated_engine):
        memories = populated_engine.retrieve_stratified(
            "H_001",
            allocation={"personal": 2, "neighbor": 5, "community": 3},
            total_k=10
        )
        assert len(memories) <= 10
        neighbor_count = sum(1 for m in memories if "Neighbor" in m)
        assert neighbor_count >= 2

    def test_empty_agent_returns_empty(self, engine):
        memories = engine.retrieve_stratified("NONEXISTENT")
        assert memories == []

    def test_total_k_cap(self, populated_engine):
        memories = populated_engine.retrieve_stratified("H_001", total_k=5)
        assert len(memories) <= 5

    def test_reflection_memories_categorized(self, populated_engine):
        memories = populated_engine.retrieve_stratified(
            "H_001",
            allocation={"reflection": 5, "personal": 0, "neighbor": 0, "community": 0, "abstract": 0},
            total_k=5
        )
        assert any("Reflection" in m or "reflection" in m.lower() for m in memories)

    def test_overflow_fills_from_best(self, populated_engine):
        """If allocation can't fill total_k, remaining slots filled by top score."""
        memories = populated_engine.retrieve_stratified(
            "H_001",
            allocation={"personal": 1, "neighbor": 1},
            total_k=8
        )
        assert len(memories) == 8
```

### 2. Run tests

```bash
pytest tests/test_stratified_retrieval.py -v
pytest tests/test_memory_engine_split.py -v
pytest tests/test_memory_integration.py -v
```

All tests must pass. No regressions in existing memory tests.

---

## DO NOT

- Do NOT modify `retrieve()` or any existing method in `HumanCentricMemoryEngine`
- Do NOT change `_add_memory_internal()` or memory item structure
- Do NOT change `_apply_decay()` or scoring weights (`W_recency`, `W_importance`, `W_context`)
- Do NOT modify any file other than `broker/components/engines/humancentric_engine.py` and `tests/test_stratified_retrieval.py`
