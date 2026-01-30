"""
Tests for Memory Persistence (Task-050B).

Verifies checkpoint/resume functionality for memory states.
"""

import pytest
import json
import tempfile
import numpy as np
from pathlib import Path
from typing import List

from cognitive_governance.memory import UnifiedMemoryItem
from cognitive_governance.memory.persistence import (
    MemoryCheckpoint,
    MemorySerializer,
    save_checkpoint,
    load_checkpoint,
    CHECKPOINT_VERSION,
)


@pytest.fixture
def sample_memory():
    """Create a sample memory item."""
    return UnifiedMemoryItem(
        content="Flood damaged my basement in Year 3",
        timestamp=1700000000.0,
        emotion="major",
        source="personal",
        base_importance=0.8,
        surprise_score=0.6,
        novelty_score=0.4,
        agent_id="Agent_42",
        year=3,
        tags=["flood", "damage", "personal"],
        metadata={"flood_depth": 0.5},
    )


@pytest.fixture
def sample_memory_with_embedding():
    """Create a memory with embedding."""
    mem = UnifiedMemoryItem(
        content="Flood damaged my basement",
        timestamp=1700000000.0,
        agent_id="Agent_42",
    )
    mem.embedding = np.random.rand(384).astype(np.float32)
    return mem


@pytest.fixture
def sample_memories():
    """Create a list of sample memories."""
    return [
        UnifiedMemoryItem(
            content=f"Memory {i}",
            timestamp=1700000000.0 + i * 1000,
            agent_id="Agent_42",
            base_importance=0.3 + i * 0.1,
        )
        for i in range(5)
    ]


class TestMemorySerializer:
    """Tests for MemorySerializer."""

    def test_serialize_basic(self, sample_memory):
        """Test basic serialization."""
        data = MemorySerializer.serialize_item(sample_memory)

        assert data["content"] == "Flood damaged my basement in Year 3"
        assert data["emotion"] == "major"
        assert data["source"] == "personal"
        assert data["base_importance"] == 0.8
        assert data["agent_id"] == "Agent_42"
        assert data["year"] == 3
        assert "flood" in data["tags"]

    def test_serialize_with_embedding(self, sample_memory_with_embedding):
        """Test serialization with embedding."""
        data = MemorySerializer.serialize_item(sample_memory_with_embedding)

        assert data["embedding"] is not None
        assert len(data["embedding"]) == 384
        assert isinstance(data["embedding"], list)

    def test_deserialize_basic(self, sample_memory):
        """Test deserialization."""
        data = MemorySerializer.serialize_item(sample_memory)
        restored = MemorySerializer.deserialize_item(data)

        assert restored.content == sample_memory.content
        assert restored.emotion == sample_memory.emotion
        assert restored.source == sample_memory.source
        assert restored.base_importance == sample_memory.base_importance
        assert restored.agent_id == sample_memory.agent_id

    def test_roundtrip_with_embedding(self, sample_memory_with_embedding):
        """Test serialize/deserialize roundtrip with embedding."""
        data = MemorySerializer.serialize_item(sample_memory_with_embedding)
        restored = MemorySerializer.deserialize_item(data)

        assert restored.embedding is not None
        np.testing.assert_array_almost_equal(
            restored.embedding,
            sample_memory_with_embedding.embedding
        )

    def test_handles_none_embedding(self, sample_memory):
        """Test handling of None embedding."""
        data = MemorySerializer.serialize_item(sample_memory)
        assert data["embedding"] is None

        restored = MemorySerializer.deserialize_item(data)
        assert restored.embedding is None


class TestMemoryCheckpoint:
    """Tests for MemoryCheckpoint class."""

    def test_save_and_load_agent(self, sample_memories):
        """Test save/load for single agent."""
        checkpoint = MemoryCheckpoint()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agent_checkpoint.json"

            # Save
            checkpoint.save_agent(
                agent_id="Agent_42",
                memories=sample_memories,
                path=path,
                metadata={"year": 5, "experiment": "test"}
            )

            assert path.exists()

            # Load
            agent_id, memories, state = checkpoint.load(path)

            assert agent_id == "Agent_42"
            assert len(memories) == 5
            assert state["metadata"]["year"] == 5
            assert state["metadata"]["experiment"] == "test"

    def test_save_with_belief_state(self, sample_memories):
        """Test saving belief state."""
        checkpoint = MemoryCheckpoint()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"

            checkpoint.save_agent(
                agent_id="Agent_42",
                memories=sample_memories,
                path=path,
                belief_state={
                    "trust_insurance": 0.65,
                    "risk_perception": 0.45
                }
            )

            _, _, state = checkpoint.load(path)

            assert state["belief_state"]["trust_insurance"] == 0.65
            assert state["belief_state"]["risk_perception"] == 0.45

    def test_save_without_embeddings(self, sample_memory_with_embedding):
        """Test saving without embeddings."""
        checkpoint = MemoryCheckpoint(include_embeddings=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"

            checkpoint.save_agent(
                agent_id="Agent_42",
                memories=[sample_memory_with_embedding],
                path=path
            )

            _, memories, _ = checkpoint.load(path)

            # Embedding should be None when loaded back
            assert memories[0].embedding is None

    def test_checksum_verification(self, sample_memories):
        """Test checksum verification."""
        checkpoint = MemoryCheckpoint()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"

            checkpoint.save_agent(
                agent_id="Agent_42",
                memories=sample_memories,
                path=path
            )

            # Tamper with the file
            with open(path, "r") as f:
                data = json.load(f)

            data["memories"][0]["content"] = "TAMPERED"

            with open(path, "w") as f:
                json.dump(data, f)

            # Should raise on checksum mismatch
            with pytest.raises(ValueError, match="checksum"):
                checkpoint.load(path, verify_checksum=True)

    def test_load_without_checksum_verification(self, sample_memories):
        """Test loading with checksum verification disabled."""
        checkpoint = MemoryCheckpoint()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"

            checkpoint.save_agent(
                agent_id="Agent_42",
                memories=sample_memories,
                path=path
            )

            # Should work without verification
            agent_id, memories, _ = checkpoint.load(path, verify_checksum=False)
            assert agent_id == "Agent_42"


class TestMergeStrategies:
    """Tests for memory merge strategies."""

    def test_merge_importance(self):
        """Test importance-based merge."""
        checkpoint = MemoryCheckpoint()

        old = [
            UnifiedMemoryItem(content="Old high", base_importance=0.9, timestamp=1000),
            UnifiedMemoryItem(content="Old low", base_importance=0.2, timestamp=1001),
        ]
        new = [
            UnifiedMemoryItem(content="New medium", base_importance=0.5, timestamp=2000),
        ]

        merged = checkpoint.merge(old, new, strategy="importance", max_memories=2)

        assert len(merged) == 2
        # Should keep highest importance
        assert merged[0].content == "Old high"
        assert merged[1].content == "New medium"

    def test_merge_recency(self):
        """Test recency-based merge."""
        checkpoint = MemoryCheckpoint()

        old = [
            UnifiedMemoryItem(content="Old", timestamp=1000),
        ]
        new = [
            UnifiedMemoryItem(content="New", timestamp=2000),
        ]

        merged = checkpoint.merge(old, new, strategy="recency", max_memories=1)

        assert len(merged) == 1
        assert merged[0].content == "New"

    def test_merge_dedupe(self):
        """Test deduplication during merge."""
        checkpoint = MemoryCheckpoint()

        old = [
            UnifiedMemoryItem(content="Same content", base_importance=0.3),
        ]
        new = [
            UnifiedMemoryItem(content="Same content", base_importance=0.8),
            UnifiedMemoryItem(content="Different content", base_importance=0.5),
        ]

        merged = checkpoint.merge(old, new, strategy="dedupe")

        assert len(merged) == 2
        # Should keep higher importance version of duplicate
        same_content = [m for m in merged if m.content == "Same content"][0]
        assert same_content.base_importance == 0.8


class TestExperimentCheckpoint:
    """Tests for experiment-level checkpoints."""

    def test_save_and_load_experiment(self):
        """Test multi-agent experiment checkpoint."""
        checkpoint = MemoryCheckpoint()

        agents = {
            "Agent_1": [
                UnifiedMemoryItem(content="A1 memory 1", agent_id="Agent_1"),
                UnifiedMemoryItem(content="A1 memory 2", agent_id="Agent_1"),
            ],
            "Agent_2": [
                UnifiedMemoryItem(content="A2 memory 1", agent_id="Agent_2"),
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "experiment.json"

            checkpoint.save_experiment(
                agents=agents,
                path=path,
                metadata={"experiment": "test", "year": 5}
            )

            loaded_agents, metadata = checkpoint.load_experiment(path)

            assert len(loaded_agents) == 2
            assert len(loaded_agents["Agent_1"]) == 2
            assert len(loaded_agents["Agent_2"]) == 1
            assert metadata["experiment"] == "test"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_quick_save_load(self, sample_memories):
        """Test save_checkpoint and load_checkpoint functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "quick.json"

            save_checkpoint("Agent_42", sample_memories, path)

            agent_id, memories, _ = load_checkpoint(path)

            assert agent_id == "Agent_42"
            assert len(memories) == 5
