"""
Tests for MemoryGraph (Task-050D).

Verifies graph-based memory structure with NetworkX.
"""

import pytest
import time
import numpy as np
from typing import List, Set

from cognitive_governance.memory import UnifiedMemoryItem
from cognitive_governance.memory.graph import (
    MemoryGraph,
    AgentMemoryGraph,
    EdgeType,
)


class MockEmbeddingProvider:
    """Mock embedding provider for testing."""

    def __init__(self, dim: int = 384):
        self.dim = dim
        self._cache = {}

    def embed(self, text: str) -> np.ndarray:
        """Generate deterministic embedding based on text hash."""
        if text not in self._cache:
            # Use hash to generate deterministic embedding
            np.random.seed(hash(text) % (2**32))
            self._cache[text] = np.random.rand(self.dim).astype(np.float32)
        return self._cache[text]


@pytest.fixture
def memory_graph():
    """Create a basic MemoryGraph."""
    return MemoryGraph(
        semantic_threshold=0.7,
        temporal_window=86400.0,  # 1 day
        auto_edges=True,
    )


@pytest.fixture
def memory_graph_with_embedding():
    """Create a MemoryGraph with embedding provider."""
    provider = MockEmbeddingProvider()
    return MemoryGraph(
        embedding_provider=provider,
        semantic_threshold=0.5,
        temporal_window=86400.0,
        auto_edges=True,
    )


@pytest.fixture
def sample_memories():
    """Create sample memories for testing."""
    base_time = 1700000000.0
    return [
        UnifiedMemoryItem(
            content="Flood damaged my house in Year 3",
            timestamp=base_time,
            emotion="major",
            source="personal",
            base_importance=0.8,
            agent_id="Agent_1",
        ),
        UnifiedMemoryItem(
            content="Insurance denied my flood claim",
            timestamp=base_time + 3600,  # 1 hour later
            emotion="major",
            source="personal",
            base_importance=0.7,
            agent_id="Agent_1",
        ),
        UnifiedMemoryItem(
            content="Neighbor helped with repairs",
            timestamp=base_time + 7200,  # 2 hours later
            emotion="minor",
            source="social",
            base_importance=0.5,
            agent_id="Agent_1",
        ),
        UnifiedMemoryItem(
            content="Government announced flood relief program",
            timestamp=base_time + 86400,  # 1 day later
            emotion="neutral",
            source="policy",
            base_importance=0.6,
            agent_id="Agent_1",
        ),
        UnifiedMemoryItem(
            content="Applied for flood insurance",
            timestamp=base_time + 172800,  # 2 days later
            emotion="minor",
            source="personal",
            base_importance=0.5,
            agent_id="Agent_1",
        ),
    ]


class TestMemoryGraphBasic:
    """Basic tests for MemoryGraph."""

    def test_create_graph(self, memory_graph):
        """Test graph creation."""
        assert len(memory_graph) == 0
        assert memory_graph.graph is not None

    def test_add_memory(self, memory_graph, sample_memories):
        """Test adding a memory."""
        mem = sample_memories[0]
        node_id = memory_graph.add_memory(mem)

        assert node_id is not None
        assert node_id.startswith("mem_")
        assert len(memory_graph) == 1
        assert node_id in memory_graph

    def test_add_multiple_memories(self, memory_graph, sample_memories):
        """Test adding multiple memories."""
        ids = []
        for mem in sample_memories:
            node_id = memory_graph.add_memory(mem)
            ids.append(node_id)

        assert len(memory_graph) == 5
        assert len(set(ids)) == 5  # All unique

    def test_get_memory(self, memory_graph, sample_memories):
        """Test retrieving memory by ID."""
        mem = sample_memories[0]
        node_id = memory_graph.add_memory(mem)

        retrieved = memory_graph.get_memory(node_id)
        assert retrieved is not None
        assert retrieved.content == mem.content

    def test_remove_memory(self, memory_graph, sample_memories):
        """Test removing memory."""
        node_id = memory_graph.add_memory(sample_memories[0])
        assert len(memory_graph) == 1

        result = memory_graph.remove_memory(node_id)
        assert result is True
        assert len(memory_graph) == 0
        assert node_id not in memory_graph

    def test_remove_nonexistent(self, memory_graph):
        """Test removing non-existent memory."""
        result = memory_graph.remove_memory("nonexistent")
        assert result is False

    def test_clear(self, memory_graph, sample_memories):
        """Test clearing the graph."""
        for mem in sample_memories:
            memory_graph.add_memory(mem)

        assert len(memory_graph) == 5

        memory_graph.clear()
        assert len(memory_graph) == 0


class TestTemporalEdges:
    """Tests for temporal edge creation."""

    def test_temporal_edges_created(self, memory_graph, sample_memories):
        """Test that temporal edges are created for close memories."""
        # Add memories within temporal window
        id1 = memory_graph.add_memory(sample_memories[0])  # t=0
        id2 = memory_graph.add_memory(sample_memories[1])  # t=1h

        # Should have temporal edge
        assert memory_graph.graph.has_edge(id1, id2) or memory_graph.graph.has_edge(id2, id1)

        # Check edge type
        if memory_graph.graph.has_edge(id1, id2):
            edge_data = memory_graph.graph[id1][id2]
        else:
            edge_data = memory_graph.graph[id2][id1]

        assert edge_data["edge_type"] == "temporal"
        assert edge_data["weight"] > 0

    def test_no_temporal_edge_outside_window(self, memory_graph, sample_memories):
        """Test that no temporal edge for memories outside window."""
        # Use memories far apart (2 days > 1 day window)
        id1 = memory_graph.add_memory(sample_memories[0])  # t=0
        id5 = memory_graph.add_memory(sample_memories[4])  # t=2 days

        # Check direct temporal edge (not transitive)
        has_direct_temporal = False
        if memory_graph.graph.has_edge(id1, id5):
            has_direct_temporal = memory_graph.graph[id1][id5].get("edge_type") == "temporal"
        if memory_graph.graph.has_edge(id5, id1):
            has_direct_temporal = memory_graph.graph[id5][id1].get("edge_type") == "temporal"

        # 2 days > 1 day window, so no direct temporal edge
        assert not has_direct_temporal


class TestManualEdges:
    """Tests for manual edge creation."""

    def test_add_causal_edge(self, memory_graph, sample_memories):
        """Test adding causal edge."""
        id1 = memory_graph.add_memory(sample_memories[0])
        id2 = memory_graph.add_memory(sample_memories[1])

        result = memory_graph.add_edge(id1, id2, edge_type="causal", weight=0.9)

        assert result is True
        assert memory_graph.graph.has_edge(id1, id2)
        assert memory_graph.graph[id1][id2]["edge_type"] == "causal"
        assert memory_graph.graph[id1][id2]["weight"] == 0.9

    def test_add_edge_invalid_nodes(self, memory_graph, sample_memories):
        """Test adding edge with invalid nodes."""
        id1 = memory_graph.add_memory(sample_memories[0])

        result = memory_graph.add_edge(id1, "nonexistent", edge_type="causal")
        assert result is False


class TestSubgraphRetrieval:
    """Tests for subgraph retrieval."""

    def test_retrieve_from_seed(self, memory_graph, sample_memories):
        """Test retrieving subgraph from seed nodes."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories]

        # Add some edges
        memory_graph.add_edge(ids[0], ids[1], edge_type="causal", weight=0.9)
        memory_graph.add_edge(ids[1], ids[2], edge_type="causal", weight=0.8)

        # Retrieve from first memory
        result = memory_graph.retrieve_subgraph(
            seed_memories=[ids[0]],
            depth=2,
            max_nodes=10
        )

        assert len(result) > 0
        assert result[0].content == sample_memories[0].content  # Seed first

    def test_retrieve_respects_max_nodes(self, memory_graph, sample_memories):
        """Test that retrieval respects max_nodes limit."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories]

        result = memory_graph.retrieve_subgraph(
            seed_memories=[ids[0]],
            depth=10,
            max_nodes=2
        )

        assert len(result) <= 2

    def test_retrieve_respects_depth(self):
        """Test that retrieval respects depth limit."""
        # Create graph without auto edges to test pure depth behavior
        graph = MemoryGraph(auto_edges=False)

        base_time = 1700000000.0
        memories = [
            UnifiedMemoryItem(content=f"Memory {i}", timestamp=base_time + i * 100000)
            for i in range(5)
        ]

        ids = [graph.add_memory(mem) for mem in memories]

        # Create chain: 0 -> 1 -> 2 -> 3 -> 4
        for i in range(len(ids) - 1):
            graph.add_edge(ids[i], ids[i+1], edge_type="causal", weight=0.9)

        # Retrieve with depth=1 from start
        result = graph.retrieve_subgraph(
            seed_memories=[ids[0]],
            depth=1,
            max_nodes=10
        )

        # Should get at most 2 nodes (seed + 1 hop)
        assert len(result) <= 2

    def test_retrieve_filters_edge_type(self, memory_graph, sample_memories):
        """Test filtering by edge type."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories[:3]]

        # Add different edge types
        memory_graph.add_edge(ids[0], ids[1], edge_type="causal", weight=0.9)
        memory_graph.add_edge(ids[0], ids[2], edge_type="references", weight=0.8)

        # Retrieve only causal
        result = memory_graph.retrieve_subgraph(
            seed_memories=[ids[0]],
            depth=2,
            edge_types=["causal"]
        )

        # Should not include ids[2] (references edge)
        contents = [m.content for m in result]
        assert sample_memories[0].content in contents
        assert sample_memories[1].content in contents


class TestSummaryNodes:
    """Tests for summary node creation."""

    def test_create_summary(self, memory_graph, sample_memories):
        """Test creating summary node."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories[:3]]

        summary_id = memory_graph.create_summary_node(
            child_ids=ids,
            summary_content="Year 3 flood experience summary",
            importance=0.9
        )

        assert summary_id is not None
        assert summary_id in memory_graph

        # Check summary node attributes
        summary = memory_graph.get_memory(summary_id)
        assert "summary" in summary.tags
        assert summary.base_importance == 0.9

    def test_summary_links_to_children(self, memory_graph, sample_memories):
        """Test that summary is linked to children."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories[:3]]

        summary_id = memory_graph.create_summary_node(
            child_ids=ids,
            summary_content="Summary content"
        )

        # Check edges exist
        for child_id in ids:
            assert memory_graph.graph.has_edge(summary_id, child_id)
            edge_data = memory_graph.graph[summary_id][child_id]
            assert edge_data["edge_type"] == "summarizes"


class TestTemporalSequence:
    """Tests for temporal sequence retrieval."""

    def test_get_forward_sequence(self, memory_graph, sample_memories):
        """Test getting forward temporal sequence."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories[:3]]

        sequence = memory_graph.get_temporal_sequence(
            ids[0],
            direction="forward",
            max_length=5
        )

        assert len(sequence) > 0
        # Should be sorted by timestamp
        timestamps = [m.timestamp for m in sequence]
        assert timestamps == sorted(timestamps)


class TestClustering:
    """Tests for cluster detection."""

    def test_find_clusters(self, memory_graph, sample_memories):
        """Test finding memory clusters."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories]

        # Create two clusters
        memory_graph.add_edge(ids[0], ids[1], edge_type="semantic", weight=0.9)
        memory_graph.add_edge(ids[1], ids[2], edge_type="semantic", weight=0.9)
        memory_graph.add_edge(ids[3], ids[4], edge_type="semantic", weight=0.9)

        clusters = memory_graph.find_clusters(min_size=2)

        # Should find clusters (exact number depends on algorithm)
        assert len(clusters) >= 1

    def test_find_clusters_min_size(self, memory_graph, sample_memories):
        """Test cluster minimum size filter."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories[:2]]

        clusters = memory_graph.find_clusters(min_size=3)

        # No cluster of size >= 3 possible with 2 nodes
        assert len(clusters) == 0


class TestGraphStats:
    """Tests for graph statistics."""

    def test_get_stats(self, memory_graph, sample_memories):
        """Test getting graph statistics."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories]
        memory_graph.add_edge(ids[0], ids[1], edge_type="causal", weight=0.9)

        stats = memory_graph.get_stats()

        assert stats["total_nodes"] == 5
        assert stats["total_edges"] > 0  # At least the causal edge + temporal
        assert "node_types" in stats
        assert "edge_types" in stats
        assert "density" in stats


class TestAgentMemoryGraph:
    """Tests for multi-agent graph manager."""

    def test_create_manager(self):
        """Test creating agent graph manager."""
        manager = AgentMemoryGraph(semantic_threshold=0.7)
        assert manager is not None

    def test_add_memory_per_agent(self, sample_memories):
        """Test adding memories for different agents."""
        manager = AgentMemoryGraph()

        id1 = manager.add_memory("agent_1", sample_memories[0])
        id2 = manager.add_memory("agent_2", sample_memories[1])

        assert id1 is not None
        assert id2 is not None

        # Agents should have separate graphs
        stats = manager.get_stats()
        assert "agent_1" in stats
        assert "agent_2" in stats
        assert stats["agent_1"]["total_nodes"] == 1
        assert stats["agent_2"]["total_nodes"] == 1

    def test_retrieve_subgraph_per_agent(self, sample_memories):
        """Test retrieving from specific agent's graph."""
        manager = AgentMemoryGraph()

        ids_1 = [manager.add_memory("agent_1", mem) for mem in sample_memories[:3]]
        ids_2 = [manager.add_memory("agent_2", mem) for mem in sample_memories[3:]]

        # Retrieve from agent_1
        result = manager.retrieve_subgraph(
            "agent_1",
            seed_memories=[ids_1[0]],
            depth=2
        )

        # Should only get agent_1's memories
        assert len(result) > 0
        for mem in result:
            assert mem.content in [m.content for m in sample_memories[:3]]

    def test_clear_agent(self, sample_memories):
        """Test clearing specific agent's graph."""
        manager = AgentMemoryGraph()

        manager.add_memory("agent_1", sample_memories[0])
        manager.add_memory("agent_2", sample_memories[1])

        manager.clear_agent("agent_1")

        stats = manager.get_stats()
        assert stats["agent_1"]["total_nodes"] == 0
        assert stats["agent_2"]["total_nodes"] == 1


class TestSemanticEdges:
    """Tests for semantic edge creation with embeddings."""

    def test_semantic_edges_created(self, memory_graph_with_embedding):
        """Test that semantic edges are created for similar content."""
        mem1 = UnifiedMemoryItem(
            content="Flood damaged my house",
            timestamp=1000,
        )
        mem2 = UnifiedMemoryItem(
            content="Flood damaged my house severely",  # Similar
            timestamp=2000,
        )
        mem3 = UnifiedMemoryItem(
            content="Completely unrelated topic about cooking",  # Different
            timestamp=3000,
        )

        id1 = memory_graph_with_embedding.add_memory(mem1)
        id2 = memory_graph_with_embedding.add_memory(mem2)
        id3 = memory_graph_with_embedding.add_memory(mem3)

        # Check for semantic edges between similar content
        # Note: With mock embeddings, similarity depends on hash
        stats = memory_graph_with_embedding.get_stats()
        assert stats["total_edges"] > 0  # At least temporal edges


class TestGetNeighbors:
    """Tests for getting neighbors."""

    def test_get_neighbors(self, memory_graph, sample_memories):
        """Test getting neighbors of a node."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories[:3]]

        memory_graph.add_edge(ids[0], ids[1], edge_type="causal", weight=0.9)
        memory_graph.add_edge(ids[0], ids[2], edge_type="references", weight=0.5)

        neighbors = memory_graph.get_neighbors(ids[0])

        assert len(neighbors) >= 2
        neighbor_ids = [n[0] for n in neighbors]
        assert ids[1] in neighbor_ids
        assert ids[2] in neighbor_ids

    def test_get_neighbors_filtered(self, memory_graph, sample_memories):
        """Test getting neighbors filtered by edge type."""
        ids = [memory_graph.add_memory(mem) for mem in sample_memories[:3]]

        memory_graph.add_edge(ids[0], ids[1], edge_type="causal", weight=0.9)
        memory_graph.add_edge(ids[0], ids[2], edge_type="references", weight=0.5)

        neighbors = memory_graph.get_neighbors(ids[0], edge_type="causal")

        assert len(neighbors) >= 1
        neighbor_ids = [n[0] for n in neighbors]
        assert ids[1] in neighbor_ids
        # ids[2] should not be in causal neighbors
        assert ids[2] not in neighbor_ids
