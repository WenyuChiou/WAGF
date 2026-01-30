# Task-057C: Dynamic Importance Scoring (Codex Assignment)

**Assigned To**: Codex
**Status**: READY (after 057-A)
**Priority**: High
**Estimated Scope**: ~60 lines new/edit, 2 files + 1 test file
**Depends On**: 057-A (uses `AgentReflectionContext`, `extract_agent_context()`)

---

## Objective

Replace the hardcoded `importance=0.9` for all reflection insights with variable importance based on agent state. Currently all reflections are stored with `importance=0.9` and `source="personal"`, creating an echo chamber where reflection memories crowd out diverse episodic memories.

Also update the SA reflection loop in `run_flood.py` to use personalized prompts, stratified retrieval, and dynamic importance.

---

## Context

### Current Hardcoded Importance

In `broker/components/reflection_engine.py`, line 54:
```python
self.importance_boost = insight_importance_boost  # default 0.9
```

In `_create_insight()` (line 306-314):
```python
return ReflectionInsight(
    summary=text.strip()[:500],
    importance=self.importance_boost,  # Always 0.9
    ...
)
```

In `examples/single_agent/run_flood.py`, line 498-502:
```python
self.runner.memory_engine.add_memory(
    agent_id,
    f"Consolidated Reflection: {insight.summary}",
    {"significance": 0.9, "emotion": "major", "source": "personal"}  # Always 0.9
)
```

### Problem

All reflections stored at 0.9 importance → they dominate retrieval → future reflections see only past reflections → echo chamber.

---

## Changes Required

### File 1: `broker/components/reflection_engine.py`

**Change 1:** Add importance profiles dict (module-level, after `REFLECTION_QUESTIONS` added by 057-A):

```python
IMPORTANCE_PROFILES: Dict[str, float] = {
    "first_flood": 0.95,      # First flood experience -> very memorable
    "repeated_flood": 0.75,   # Repeated floods -> diminishing impact
    "post_action": 0.80,      # Just took a major action (elevate/relocate)
    "stable_year": 0.60,      # Nothing major happened
    "denied_action": 0.85,    # Governance denial -> memorable frustration
    "mg_agent": 0.90,         # MG agents retain reflections more (limited info)
}
```

**Change 2:** Add `compute_dynamic_importance()` method to `ReflectionEngine`:

```python
def compute_dynamic_importance(
    self,
    context: AgentReflectionContext,
    base_importance: float = 0.9,
) -> float:
    """Compute variable importance based on agent state.

    Returns importance in [0.6, 0.95] range instead of fixed 0.9.
    """
    importance = base_importance

    # First flood is maximally memorable
    if context.flood_count == 1:
        importance = IMPORTANCE_PROFILES["first_flood"]
    elif context.flood_count > 2:
        importance = IMPORTANCE_PROFILES["repeated_flood"]

    # MG agents: higher retention (compensates for limited social info)
    if context.mg_status:
        importance = max(importance, IMPORTANCE_PROFILES["mg_agent"])

    # Recent major action
    if context.recent_decision in ("elevate_house", "relocate", "buy_insurance"):
        importance = max(importance, IMPORTANCE_PROFILES["post_action"])

    # Stable/boring year = lower importance
    if context.flood_count == 0 and context.recent_decision in ("do_nothing", ""):
        importance = min(importance, IMPORTANCE_PROFILES["stable_year"])

    return round(min(1.0, max(0.0, importance)), 2)
```

### File 2: `examples/single_agent/run_flood.py`

**Change:** Replace the reflection block in `FinalParityHook.post_year()` (lines 463-506).

Find this block:
```python
        # --- PILLAR 2: BATCH YEAR-END REFLECTION ---
        if self.reflection_engine and self.reflection_engine.should_reflect("any", year):
            # Optimized: Pull batch_size from YAML (Pillar 2)
            refl_cfg = self.runner.broker.config.get_reflection_config()
            batch_size = refl_cfg.get("batch_size", 10)

            # 1. Collect all agents that need reflection this year
            candidates = []
            for agent_id, agent in self.sim.agents.items():
                if getattr(agent, "relocated", False):
                    continue  # Skip relocated agents
                memories = self.runner.memory_engine.retrieve(agent, top_k=10)
                if memories:
                    candidates.append({"agent_id": agent_id, "memories": memories})

            if candidates:
                print(f" [Reflection:Batch] Processing {len(candidates)} agents in batches of {batch_size}...")
                llm_call = self.runner.get_llm_invoke("household")

                # 2. Process in batches
                for i in range(0, len(candidates), batch_size):
                    batch = candidates[i:i+batch_size]
                    batch_ids = [c["agent_id"] for c in batch]
                    prompt = self.reflection_engine.generate_batch_reflection_prompt(batch, year)

                    try:
                        raw_res = llm_call(prompt)
                        response_text = raw_res[0] if isinstance(raw_res, tuple) else raw_res

                        # 3. Parse and store insights
                        insights = self.reflection_engine.parse_batch_reflection_response(response_text, batch_ids, year)
                        for agent_id, insight in insights.items():
                            if insight:
                                self.reflection_engine.store_insight(agent_id, insight)
                                # Feed insight back to Memory Engine
                                self.runner.memory_engine.add_memory(
                                    agent_id,
                                    f"Consolidated Reflection: {insight.summary}",
                                    {"significance": 0.9, "emotion": "major", "source": "personal"}
                                )
                    except Exception as e:
                        print(f" [Reflection:Batch:Error] Batch {i//batch_size+1} failed: {e}")

                print(f" [Reflection:Batch] Completed reflection for Year {year}.")
```

Replace with:
```python
        # --- PILLAR 2: BATCH YEAR-END REFLECTION (Personalized) ---
        if self.reflection_engine and self.reflection_engine.should_reflect("any", year):
            from broker.components.reflection_engine import AgentReflectionContext
            refl_cfg = self.runner.broker.config.get_reflection_config()
            batch_size = refl_cfg.get("batch_size", 10)

            # 1. Collect candidates with identity context
            candidates = []
            for agent_id, agent in self.sim.agents.items():
                if getattr(agent, "relocated", False):
                    continue
                # Use stratified retrieval if available, else fallback to top-k
                mem_engine = self.runner.memory_engine
                if hasattr(mem_engine, 'retrieve_stratified'):
                    memories = mem_engine.retrieve_stratified(agent_id, total_k=10)
                else:
                    memories = mem_engine.retrieve(agent, top_k=10)
                if memories:
                    ctx = self.reflection_engine.extract_agent_context(agent, year)
                    candidates.append({"agent_id": agent_id, "memories": memories, "context": ctx})

            if candidates:
                print(f" [Reflection:Batch] Processing {len(candidates)} agents in batches of {batch_size}...")
                llm_call = self.runner.get_llm_invoke("household")

                for i in range(0, len(candidates), batch_size):
                    batch = candidates[i:i+batch_size]
                    batch_ids = [c["agent_id"] for c in batch]

                    # Use personalized batch prompt if available
                    if hasattr(self.reflection_engine, 'generate_personalized_batch_prompt'):
                        prompt = self.reflection_engine.generate_personalized_batch_prompt(batch, year)
                    else:
                        prompt = self.reflection_engine.generate_batch_reflection_prompt(batch, year)

                    try:
                        raw_res = llm_call(prompt)
                        response_text = raw_res[0] if isinstance(raw_res, tuple) else raw_res

                        insights = self.reflection_engine.parse_batch_reflection_response(response_text, batch_ids, year)
                        for agent_id, insight in insights.items():
                            if insight:
                                # Dynamic importance based on agent context
                                ctx_item = next((c for c in batch if c["agent_id"] == agent_id), None)
                                if ctx_item and ctx_item.get("context") and hasattr(self.reflection_engine, 'compute_dynamic_importance'):
                                    dynamic_imp = self.reflection_engine.compute_dynamic_importance(ctx_item["context"])
                                    insight.importance = dynamic_imp

                                self.reflection_engine.store_insight(agent_id, insight)
                                self.runner.memory_engine.add_memory(
                                    agent_id,
                                    f"Consolidated Reflection: {insight.summary}",
                                    {"significance": insight.importance, "emotion": "major", "source": "personal", "type": "reflection"}
                                )
                    except Exception as e:
                        print(f" [Reflection:Batch:Error] Batch {i//batch_size+1} failed: {e}")

                print(f" [Reflection:Batch] Completed reflection for Year {year}.")
```

---

## Verification

### 1. Add test file

**File**: `tests/test_dynamic_importance.py`

```python
"""Tests for dynamic reflection importance scoring (Task-057C)."""
import pytest
from broker.components.reflection_engine import (
    ReflectionEngine, AgentReflectionContext, IMPORTANCE_PROFILES
)


@pytest.fixture
def engine():
    return ReflectionEngine()


class TestDynamicImportance:
    def test_first_flood_highest(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", flood_count=1)
        imp = engine.compute_dynamic_importance(ctx)
        assert imp == 0.95

    def test_repeated_floods_diminish(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", flood_count=5)
        imp = engine.compute_dynamic_importance(ctx)
        assert imp == 0.75

    def test_stable_year_lowest(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", flood_count=0, recent_decision="do_nothing")
        imp = engine.compute_dynamic_importance(ctx)
        assert imp == 0.6

    def test_mg_agent_boost(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", mg_status=True)
        imp = engine.compute_dynamic_importance(ctx)
        assert imp >= 0.9

    def test_post_action_boost(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", recent_decision="elevate_house")
        imp = engine.compute_dynamic_importance(ctx)
        assert imp >= 0.8

    def test_importance_bounded(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", flood_count=1, mg_status=True)
        imp = engine.compute_dynamic_importance(ctx)
        assert 0.0 <= imp <= 1.0

    def test_profiles_dict_exists(self):
        assert "first_flood" in IMPORTANCE_PROFILES
        assert "stable_year" in IMPORTANCE_PROFILES
        assert all(0.0 <= v <= 1.0 for v in IMPORTANCE_PROFILES.values())
```

### 2. Run tests

```bash
pytest tests/test_dynamic_importance.py -v
pytest tests/test_reflection_personalization.py -v
pytest tests/test_reflection_engine_v2.py -v
```

All tests must pass.

---

## DO NOT

- Do NOT modify `_create_insight()` or `parse_batch_reflection_response()` in reflection_engine.py
- Do NOT change the signature of `store_insight()`
- Do NOT remove the original `generate_batch_reflection_prompt()` method
- Do NOT modify `run_flood.py` `pre_year()` or `post_step()` hooks — only `post_year()` reflection block
- Do NOT modify any memory engine files
