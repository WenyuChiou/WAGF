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
