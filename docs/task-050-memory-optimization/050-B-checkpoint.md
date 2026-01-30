# Task 050-B: Memory Checkpoint/Resume

> **Status**: Complete
> **Priority**: HIGH
> **Complexity**: Low

---

## Overview

Implement a checkpoint system for persisting and restoring agent memory states across sessions, enabling lifelong learning and experiment reproducibility.

## Problem Statement

Current memory system limitations:
1. Memory only exists within a single session
2. No way to resume agent state across experiments
3. Experiment reproducibility requires re-running from scratch
4. Cross-session learning is not possible

## Literature Reference

| Paper | Key Insight |
|-------|-------------|
| **MemGPT** (Packer et al., 2023) | Archival memory persistence for unlimited context |
| **LangMem** (LangChain, 2024) | Long-term memory SDK with serialization support |
| **Generative Agents** (Park et al., 2023) | Memory stream persistence for agent state |

### From Zotero (Task-050 Collection)
- L2: MemGPT's archival memory provides inspiration for checkpoint format
- L3: Generative Agents requires memory persistence for extended simulations

## Technical Design

### 1. New Module: `persistence.py`

```
cognitive_governance/memory/
├── persistence.py        # NEW: Checkpoint/restore functionality
├── store.py              # Modified: add checkpoint hooks
└── unified_engine.py     # Modified: checkpoint integration
```

### 2. Checkpoint Format (JSON)

```json
{
  "version": "1.0",
  "created_at": "2026-01-29T12:00:00Z",
  "agent_id": "Agent_42",
  "metadata": {
    "experiment": "flood_sim_2026",
    "year": 5,
    "seed": 401
  },
  "memory_state": {
    "working": [/* UnifiedMemoryItem serialized */],
    "longterm": [/* UnifiedMemoryItem serialized */]
  },
  "belief_state": {
    "trust_insurance": 0.65,
    "trust_government": 0.72,
    "risk_perception": 0.45
  },
  "surprise_state": {
    "ema_value": 0.32,
    "novelty_counts": {"flood": 3, "policy": 2}
  }
}
```

### 3. Class Design

```python
class MemoryCheckpoint:
    """Save and restore agent memory states."""

    def save(
        self,
        agent_id: str,
        store: UnifiedMemoryStore,
        path: Path,
        metadata: Optional[Dict] = None
    ) -> None:
        """Serialize memories to JSON."""

    def load(
        self,
        path: Path
    ) -> Tuple[str, List[UnifiedMemoryItem], Dict]:
        """Restore memories from checkpoint."""

    def merge(
        self,
        old: List[UnifiedMemoryItem],
        new: List[UnifiedMemoryItem],
        strategy: str = "importance"
    ) -> List[UnifiedMemoryItem]:
        """Merge memories from different sessions."""
```

### 4. CLI Integration

```bash
# Save checkpoint
python run_flood.py --save-checkpoint results/agent_42_year5.json

# Load checkpoint
python run_flood.py --load-checkpoint results/agent_42_year5.json

# Resume from checkpoint
python run_flood.py --resume-from results/agent_42_year5.json
```

## Implementation Steps

1. [x] Create documentation
2. [x] Implement `MemoryCheckpoint` class
3. [x] Implement `MemorySerializer` class
4. [x] Add unit tests (15 tests passing)
5. [ ] Integrate with CLI (optional, future)
6. [x] Add merge strategies (importance, recency, dedupe)

---

## Files Created/Modified

| File | Status | Description |
|------|--------|-------------|
| `cognitive_governance/memory/persistence.py` | Created | Checkpoint/restore functionality |
| `cognitive_governance/memory/__init__.py` | Modified | Export new classes |
| `tests/test_memory_persistence.py` | Created | 15 unit tests |

## Usage Example

```python
from cognitive_governance.memory import (
    MemoryCheckpoint,
    save_checkpoint,
    load_checkpoint
)

# Quick save/load
save_checkpoint("Agent_42", memories, "checkpoint.json")
agent_id, memories, state = load_checkpoint("checkpoint.json")

# Full checkpoint with state
checkpoint = MemoryCheckpoint()
checkpoint.save_agent(
    agent_id="Agent_42",
    memories=memory_list,
    path="agent_checkpoint.json",
    metadata={"year": 5, "experiment": "flood_sim"},
    belief_state={"trust_insurance": 0.65}
)

# Merge sessions
merged = checkpoint.merge(old_memories, new_memories, strategy="importance")

# Experiment-level checkpoint (all agents)
checkpoint.save_experiment(agents_dict, "experiment.json")
agents, metadata = checkpoint.load_experiment("experiment.json")
```

## Dependencies

None (uses standard library json, dataclasses, hashlib)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-29 | Initial design document created |
| 2026-01-29 | Implementation complete, 15 tests passing |
