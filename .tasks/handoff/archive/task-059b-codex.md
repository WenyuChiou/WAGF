# Task-059B: Universal Engine Stratified Retrieval (Codex Assignment)

**Assigned To**: Codex
**Status**: COMPLETED
**Priority**: High
**Estimated Scope**: ~40 lines new in universal_memory.py, ~5 lines in memory_engine.py, 1 test file
**Depends On**: None (Phase 1 — can run in parallel with 059-C, 059-D)
**Branch**: `feat/memory-embedding-retrieval`

---

## Objective

Add `retrieve_stratified()` to UniversalCognitiveEngine (v3) as a passthrough delegate to the internal HumanCentricMemoryEngine. Currently only HumanCentricMemoryEngine (v2, deprecated) has `retrieve_stratified()`. The Universal engine wraps HumanCentric internally but doesn't expose this method, blocking MA reflection hooks from using the latest memory engine.

Also add `retrieve_stratified()` to the base `MemoryEngine` ABC with a default `NotImplementedError`.

**SA Compatibility**: This is purely additive — no existing methods are modified. SA experiments using `retrieve()` are unaffected.

---

## Context

### Current Code: `broker/components/universal_memory.py`

Line 93-121: `UniversalCognitiveEngine` wraps `HumanCentricMemoryEngine` internally:
```python
class UniversalCognitiveEngine:
    def __init__(self, ...):
        self._base_engine = HumanCentricMemoryEngine(...)
```

Line 266-324: `retrieve()` already delegates to `self._base_engine.retrieve()` with System 1/2 switching.

**Missing**: No `retrieve_stratified()` method on this class.

### Current Code: `broker/components/engines/humancentric_engine.py`

Line 335-447: `retrieve_stratified()` exists with source-stratified diversity guarantee:
```python
def retrieve_stratified(
    self,
    agent_id: str,
    allocation: Optional[Dict[str, int]] = None,
    total_k: int = 10,
    contextual_boosters: Optional[Dict[str, float]] = None,
) -> List[str]:
```

Default allocation: `{"personal": 4, "neighbor": 2, "community": 2, "reflection": 1, "abstract": 1}`

### Current Code: `broker/components/memory_engine.py`

Line 9-56: `MemoryEngine` ABC has `add_memory()`, `retrieve()`, `clear()` — but no `retrieve_stratified()`.

### Problem

`examples/multi_agent/orchestration/lifecycle_hooks.py` calls `retrieve_stratified()` directly on the memory engine. When switching from `humancentric` to `universal` engine in YAML, this call would fail with `AttributeError`.

---

## Changes Implemented

### File: `broker/components/memory_engine.py`

**Change 1:** Add `retrieve_stratified()` to MemoryEngine ABC (after `clear()`, ~line 56):

```python
    def retrieve_stratified(
        self,
        agent_id: str,
        allocation: Optional[Dict[str, int]] = None,
        total_k: int = 10,
        contextual_boosters: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """Retrieve memories with source-stratified diversity guarantee.

        Subclasses that support stratified retrieval should override this.
        Default raises NotImplementedError.

        Args:
            agent_id: Agent to retrieve for
            allocation: Dict mapping source -> max slots
            total_k: Total memories to return
            contextual_boosters: Optional score boosters

        Returns:
            List of memory content strings, stratified by source
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support retrieve_stratified(). "
            "Use HumanCentricMemoryEngine or UniversalCognitiveEngine."
        )
```

### File: `broker/components/universal_memory.py`

**Change 2:** Add `retrieve_stratified()` method to `UniversalCognitiveEngine` (after `retrieve()`, ~line 324):

```python
    def retrieve_stratified(
        self,
        agent_id: str,
        allocation: Optional[Dict[str, int]] = None,
        total_k: int = 10,
        contextual_boosters: Optional[Dict[str, float]] = None,
        world_state: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Retrieve memories with source-stratified diversity, applying System 1/2 switching.

        Delegates to HumanCentricMemoryEngine.retrieve_stratified() with
        System 1/2 allocation adjustment:
        - System 1 (routine): recency-weighted → more personal/recent memories
        - System 2 (crisis): importance-weighted → more reflection/community memories

        Args:
            agent_id: Agent to retrieve for
            allocation: Dict mapping source -> max slots.
                        Default: {"personal": 4, "neighbor": 2, "community": 2, "reflection": 1, "abstract": 1}
            total_k: Total memories to return
            contextual_boosters: Optional score boosters
            world_state: Current environment state for surprise calculation

        Returns:
            List of memory content strings, stratified by source
        """
        # Step 1: Compute surprise from environment
        self.last_surprise = self._compute_surprise(world_state)

        # Step 2: Determine cognitive system
        self.current_system = self._determine_system(self.last_surprise)

        # Step 3: Adjust allocation based on cognitive system
        if allocation is None:
            if self.current_system == "SYSTEM_1":
                # System 1: Recency-biased → more personal, fewer reflections
                allocation = {
                    "personal": 5,
                    "neighbor": 2,
                    "community": 1,
                    "reflection": 1,
                    "abstract": 1,
                }
            else:
                # System 2: Importance-biased → more reflection/community
                allocation = {
                    "personal": 3,
                    "neighbor": 2,
                    "community": 2,
                    "reflection": 2,
                    "abstract": 1,
                }

        logger.debug(
            f"[Cognitive] retrieve_stratified: {self.current_system} "
            f"(surprise={self.last_surprise:.2f}), allocation={allocation}"
        )

        # Step 4: Delegate to base engine
        return self._base_engine.retrieve_stratified(
            agent_id=agent_id,
            allocation=allocation,
            total_k=total_k,
            contextual_boosters=contextual_boosters,
        )
```

---

## Verification

### 1. Add test file

**File**: `tests/test_universal_stratified.py`

```python
"""Tests for UniversalCognitiveEngine.retrieve_stratified() (Task-059B)."""
import pytest

from broker.components.universal_memory import UniversalCognitiveEngine
from broker.components.memory_engine import MemoryEngine, WindowMemoryEngine


class TestRetrieveStratifiedExists:
    """Verify retrieve_stratified() is available on Universal engine."""

    def test_method_exists(self):
        engine = UniversalCognitiveEngine(stimulus_key="flood_depth_m")
        assert hasattr(engine, "retrieve_stratified")
        assert callable(engine.retrieve_stratified)

    def test_base_abc_raises(self):
        """MemoryEngine ABC should raise NotImplementedError."""
        engine = WindowMemoryEngine()
        with pytest.raises(NotImplementedError):
            engine.retrieve_stratified("agent_1")


class TestRetrieveStratifiedDelegation:
    """Verify delegation to HumanCentricMemoryEngine."""

    def setup_method(self):
        self.engine = UniversalCognitiveEngine(
            stimulus_key="flood_depth_m",
            arousal_threshold=2.0,
        )

    def _add_memories(self, agent_id: str, count: int = 5):
        for i in range(count):
            self.engine.add_memory(
                agent_id,
                f"Memory {i}",
                metadata={"source": "personal", "importance": 0.5 + i * 0.1},
            )

    def test_returns_list(self):
        self._add_memories("agent_1", 5)
        result = self.engine.retrieve_stratified("agent_1", total_k=3)
        assert isinstance(result, list)

    def test_respects_total_k(self):
        self._add_memories("agent_1", 10)
        result = self.engine.retrieve_stratified("agent_1", total_k=5)
        assert len(result) <= 5

    def test_empty_agent_returns_empty(self):
        result = self.engine.retrieve_stratified("nonexistent")
        assert result == []


class TestSystem12AllocationSwitching:
    """Verify System 1/2 affects allocation."""

    def setup_method(self):
        self.engine = UniversalCognitiveEngine(
            stimulus_key="flood_depth_m",
            arousal_threshold=2.0,
        )

    def test_system1_no_surprise(self):
        """No surprise → System 1 allocation."""
        self.engine.add_memory("a1", "test", {"source": "personal"})
        self.engine.retrieve_stratified("a1", world_state={"flood_depth_m": 0.0})
        assert self.engine.current_system == "SYSTEM_1"

    def test_system2_high_surprise(self):
        """High surprise → System 2 allocation."""
        # Prime with low expectation
        self.engine._compute_surprise({"flood_depth_m": 0.0})
        self.engine.add_memory("a1", "test", {"source": "personal"})
        self.engine.retrieve_stratified("a1", world_state={"flood_depth_m": 10.0})
        assert self.engine.current_system == "SYSTEM_2"

    def test_custom_allocation_overrides(self):
        """Custom allocation should override System 1/2 defaults."""
        self.engine.add_memory("a1", "test", {"source": "personal"})
        custom = {"personal": 10}
        result = self.engine.retrieve_stratified(
            "a1", allocation=custom, world_state={"flood_depth_m": 0.0}
        )
        # Should not crash; custom allocation used as-is
        assert isinstance(result, list)
```

### 2. Run tests

```bash
pytest tests/test_universal_stratified.py -v
pytest tests/test_unified_memory.py -v
pytest tests/test_memory_integration.py -v
```

All tests must pass.

### 3. Quick smoke test

```bash
python -c "
from broker.components.universal_memory import UniversalCognitiveEngine
e = UniversalCognitiveEngine(stimulus_key='flood_depth_m')
print('retrieve_stratified exists:', hasattr(e, 'retrieve_stratified'))
e.add_memory('a1', 'test memory', {'source': 'personal', 'importance': 0.8})
result = e.retrieve_stratified('a1', total_k=3)
print('Result:', result)
"
```

---

## Completion Notes

- **Commit**: `331a8d2` (feat(memory): add universal stratified retrieval)
- **Files**: `broker/components/memory_engine.py`, `broker/components/universal_memory.py`, `tests/test_universal_stratified.py`
- **Tests**: Not run in this session (per request to continue next task)

---

## Domain Wiring (Phase 3) — BOTH locations

Domain wiring must be applied to **both** experiment cases:

### Location 1: `examples/multi_agent/`

**B4**: `examples/multi_agent/ma_agent_types.yaml` — Change `memory_config` engines from `humancentric` to `universal` where applicable.

**B5**: `examples/multi_agent/orchestration/lifecycle_hooks.py` — `_run_ma_reflection()` already calls `retrieve_stratified()`. Verify it works with Universal engine.

### Location 2: `examples/governed_flood/`

**B6**: `examples/governed_flood/run_experiment.py` — If using HumanCentricMemoryEngine, consider upgrading to UniversalCognitiveEngine. The existing `retrieve()` calls remain compatible; `retrieve_stratified()` becomes available for future reflection integration.

**B7**: `examples/governed_flood/config/agent_types.yaml` — No changes needed (SA case uses `global_config.memory` which is engine-agnostic).

---

## DO NOT

- Do NOT modify `retrieve_stratified()` in `humancentric_engine.py` — it stays as-is
- Do NOT change `retrieve()` on UniversalCognitiveEngine — keep existing behavior
- Do NOT make `retrieve_stratified()` abstract on `MemoryEngine` ABC — use default `NotImplementedError` so WindowMemoryEngine and ImportanceMemoryEngine are not broken
