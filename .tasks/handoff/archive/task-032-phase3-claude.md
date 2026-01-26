# Task-032 Phase 3: Memory Layer (Claude Code)

**Status**: 🔲 Blocked on Phase 1
**Assignee**: Claude Code
**Effort**: 1-2 hours
**Priority**: MEDIUM
**Prerequisite**: Phase 1 (Codex skeleton) complete

---

## Git Branch

```bash
# After Phase 1 completes:
git checkout task-032-phase1
git checkout -b task-032-phase3
```

**Stacked PR Structure**:
```
main
 └── task-032-sdk-base (Phase 0)
      └── task-032-phase1 (Codex)
           └── task-032-phase3 (this branch) ← YOUR WORK HERE
```

---

## Objective

Integrate the v4.0 Symbolic Context Engine into the SDK by re-exporting the existing components from `broker/components/symbolic_context.py`.

---

## Source → Destination Mapping

| Source | Destination | Action |
|--------|-------------|--------|
| `broker/components/symbolic_context.py` | `memory/symbolic.py` | Re-export |

---

## Deliverables

### 1. `memory/symbolic.py`

```python
"""
Symbolic Context Memory Layer for SDK.

Re-exports v4.0 Symbolic Context components from broker.
Reference: broker/components/symbolic_context.py
"""

from broker.components.symbolic_context import (
    Sensor,
    SignatureEngine,
    SymbolicContextMonitor,
)

__all__ = [
    "Sensor",
    "SignatureEngine",
    "SymbolicContextMonitor",
]


# Optional: SDK-specific wrapper for cleaner interface
class SymbolicMemory:
    """
    SDK-friendly wrapper for SymbolicContextMonitor.

    Provides O(1) state signature lookup and novelty-first surprise detection.
    """

    def __init__(self, sensors: list, arousal_threshold: float = 0.5):
        """
        Initialize symbolic memory.

        Args:
            sensors: List of Sensor configs (dicts with path, name, bins)
            arousal_threshold: Threshold for System 1/2 switching
        """
        sensor_objs = [
            Sensor(**s) if isinstance(s, dict) else s
            for s in sensors
        ]
        self._monitor = SymbolicContextMonitor(sensor_objs, arousal_threshold)

    def observe(self, world_state: dict) -> tuple:
        """
        Observe world state and compute surprise.

        Returns:
            (signature, surprise): State hash and surprise score (0-1)
        """
        return self._monitor.observe(world_state)

    def get_trace(self) -> dict:
        """Get the last observation trace for XAI."""
        return self._monitor.get_last_trace()

    def explain(self) -> str:
        """Human-readable explanation of last observation."""
        return self._monitor.explain_last()

    @property
    def frequency_map(self) -> dict:
        """Access the internal frequency map."""
        return self._monitor.frequency_map

    @property
    def total_events(self) -> int:
        """Total observations made."""
        return self._monitor.total_events
```

### 2. Update `memory/__init__.py`

```python
"""
Memory layer components.
"""

from .symbolic import (
    Sensor,
    SignatureEngine,
    SymbolicContextMonitor,
    SymbolicMemory,
)

__all__ = [
    "Sensor",
    "SignatureEngine",
    "SymbolicContextMonitor",
    "SymbolicMemory",
]
```

---

## Test Cases (Create `tests/test_symbolic_memory.py`)

```python
"""
Test suite for SDK Symbolic Memory.

Run: pytest governed_ai_sdk/tests/test_symbolic_memory.py -v
"""

import pytest
from governed_ai_sdk.v1_prototype.memory.symbolic import (
    Sensor,
    SymbolicContextMonitor,
    SymbolicMemory,
)


class TestSymbolicMemoryWrapper:
    """Tests for SymbolicMemory SDK wrapper."""

    def test_creation_from_dicts(self):
        """Test creating SymbolicMemory from sensor dicts."""
        sensors = [
            {"path": "flood", "name": "FLOOD", "bins": [
                {"label": "LOW", "max": 1.0},
                {"label": "HIGH", "max": 99.0}
            ]}
        ]
        memory = SymbolicMemory(sensors, arousal_threshold=0.5)
        assert memory.total_events == 0

    def test_observe_returns_signature_and_surprise(self):
        """Test observe() returns correct tuple."""
        sensors = [
            {"path": "x", "name": "X", "bins": [
                {"label": "LO", "max": 5},
                {"label": "HI", "max": 99}
            ]}
        ]
        memory = SymbolicMemory(sensors)

        sig, surprise = memory.observe({"x": 10})

        assert isinstance(sig, str)
        assert len(sig) == 16  # SHA256 truncated
        assert surprise == 1.0  # First observation = novel

    def test_novelty_first_logic(self):
        """Test that first observation has max surprise."""
        sensors = [{"path": "v", "name": "V", "bins": [{"label": "A", "max": 99}]}]
        memory = SymbolicMemory(sensors)

        _, s1 = memory.observe({"v": 1})
        assert s1 == 1.0  # First = novel

        _, s2 = memory.observe({"v": 1})
        assert s2 < 1.0  # Second = seen before

    def test_get_trace(self):
        """Test trace retrieval."""
        sensors = [{"path": "a", "name": "A", "bins": [{"label": "X", "max": 99}]}]
        memory = SymbolicMemory(sensors)

        memory.observe({"a": 5})
        trace = memory.get_trace()

        assert "signature" in trace
        assert "is_novel" in trace
        assert trace["is_novel"] is True

    def test_explain(self):
        """Test human-readable explanation."""
        sensors = [{"path": "b", "name": "B", "bins": [{"label": "Y", "max": 99}]}]
        memory = SymbolicMemory(sensors)

        memory.observe({"b": 10})
        explanation = memory.explain()

        assert "NOVEL" in explanation or "Sensors" in explanation
```

---

## Verification Commands

```bash
# 1. Verify imports work
python -c "from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory; print('OK')"

# 2. Run memory tests
pytest governed_ai_sdk/tests/test_symbolic_memory.py -v

# 3. Integration test
python -c "
from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory

sensors = [{'path': 'flood', 'name': 'FLOOD', 'bins': [{'label': 'LO', 'max': 1}, {'label': 'HI', 'max': 99}]}]
mem = SymbolicMemory(sensors)

sig, surprise = mem.observe({'flood': 5.0})
print(f'Signature: {sig[:8]}..., Surprise: {surprise:.0%}')
print(f'Trace: {mem.get_trace()}')
"
```

---

## Success Criteria

1. `SymbolicMemory` wrapper works with dict-based sensor configs
2. Re-exports from broker work without modification
3. At least 5 tests pass
4. O(1) lookup performance maintained

---

## Handoff Checklist

- [ ] `memory/symbolic.py` created with re-exports and SymbolicMemory wrapper
- [ ] `memory/__init__.py` updated
- [ ] `tests/test_symbolic_memory.py` created
- [ ] All verification commands pass
- [ ] Update `.tasks/handoff/current-session.md`
