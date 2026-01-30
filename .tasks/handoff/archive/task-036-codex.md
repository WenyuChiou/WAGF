# Task-036: Multi-Agent Memory V4 Upgrade (Codex Assignment)

**Assigned To**: Codex
**Status**: READY FOR EXECUTION
**Priority**: High
**Depends On**: Task-035 ✅ Complete

---

## Objective

Upgrade multi-agent examples from V2b memory system (`CognitiveMemory`/`humancentric`) to V4 (`SymbolicMemory` from SDK).

---

## Background

Current multi-agent example uses:
- `CognitiveMemory` from `broker/components/memory.py` (V2)
- `humancentric` engine from `ma_agent_types.yaml` (V2b)

Target:
- SDK `SymbolicMemory` from `governed_ai_sdk/v1_prototype/memory/symbolic.py` (V4)
- Domain-aware `FloodMemoryScorer` from SDK

---

## Subtasks for Codex

### 036-A: Update Memory Configuration

**File**: `examples/multi_agent/ma_agent_types.yaml`

**Changes Required**:

1. Update `memory_config` section to use SDK v4:
```yaml
memory_config:
  household_owner:
    engine: "symbolic"  # Changed from "humancentric"
    sensors:
      - path: "flood_depth_m"
        name: "FLOOD"
        bins:
          - { label: "SAFE", max: 0.3 }
          - { label: "MINOR", max: 1.0 }
          - { label: "MODERATE", max: 2.0 }
          - { label: "SEVERE", max: 99.0 }
    arousal_threshold: 0.5
    scorer: "flood"  # Use FloodMemoryScorer
```

### 036-B: Update Agent Initialization

**File**: `examples/multi_agent/ma_agents/household.py`

**Changes Required**:

1. Import SDK SymbolicMemory:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from governed_ai_sdk.v1_prototype.memory import SymbolicMemory
```

2. Update agent initialization to use SymbolicMemory when configured:
```python
def _init_memory_v4(self, config: dict):
    """Initialize V4 symbolic memory if configured."""
    if config.get("engine") == "symbolic":
        from governed_ai_sdk.v1_prototype.memory import SymbolicMemory
        sensors = config.get("sensors", [])
        arousal = config.get("arousal_threshold", 0.5)
        return SymbolicMemory(sensors, arousal_threshold=arousal)
    return None
```

### 036-C: Integrate FloodMemoryScorer

**File**: `examples/multi_agent/run_ma_flood.py` (or main entry point)

**Changes Required**:

1. Initialize memory with scorer:
```python
from governed_ai_sdk.v1_prototype.memory import get_memory_scorer
from broker.components.memory_engine import create_memory_engine

# Create domain-aware scorer
scorer = get_memory_scorer("flood")

# Create memory engine with scorer
memory_engine = create_memory_engine(
    engine_type="universal",
    scorer=scorer,
    arousal_threshold=config.get("arousal_threshold", 1.0)
)
```

---

## Verification

After making changes, run:

```bash
# SDK tests (should still pass)
pytest governed_ai_sdk/tests/ -v

# Multi-agent specific tests
pytest examples/multi_agent/tests/ -v --tb=short

# Broker tests
pytest tests/ -v --tb=short
```

---

## Files to Read First

1. `governed_ai_sdk/v1_prototype/memory/symbolic.py` - SDK SymbolicMemory
2. `governed_ai_sdk/v1_prototype/memory/scoring.py` - FloodMemoryScorer
3. `examples/multi_agent/ma_agent_types.yaml` - Current config
4. `broker/components/memory_engine.py` - create_memory_engine factory

---

## Report Format

When done, add to `current-session.md`:

```
---
REPORT
agent: Codex
task_id: task-036
scope: examples/multi_agent
status: done
changes:
- examples/multi_agent/ma_agent_types.yaml (V4 memory config)
- examples/multi_agent/ma_agents/household.py (SymbolicMemory init)
- examples/multi_agent/run_ma_flood.py (FloodMemoryScorer integration)
tests: pytest governed_ai_sdk/tests/ -v (XXX passed)
artifacts: none
issues: none
next: Task-037 (additional domain examples)
---
```

---

## Notes

- Maintain backwards compatibility (V2b should still work if configured)
- Use TYPE_CHECKING to avoid circular imports
- Test that surprise detection works with SymbolicMemory's novelty-first logic
