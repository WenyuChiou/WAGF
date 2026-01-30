"""Tests for UniversalCognitiveEngine.retrieve_stratified() (Task-059B)."""
import pytest

from broker.components.universal_memory import UniversalCognitiveEngine
from broker.components.engines.window_engine import WindowMemoryEngine


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
        """No surprise -> System 1 allocation."""
        self.engine.add_memory("a1", "test", {"source": "personal"})
        self.engine.retrieve_stratified("a1", world_state={"flood_depth_m": 0.0})
        assert self.engine.current_system == "SYSTEM_1"

    def test_system2_high_surprise(self):
        """High surprise -> System 2 allocation."""
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
        assert isinstance(result, list)
