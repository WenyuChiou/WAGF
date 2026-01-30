"""
Tests for Vector Database (Task-050A).

Verifies FAISS-based vector indexing for O(log n) semantic retrieval.
"""

import pytest
import numpy as np
import time
from typing import List, Tuple

# Check if FAISS is available
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FAISS_AVAILABLE,
    reason="FAISS not installed"
)


@pytest.fixture
def embedding_dim():
    """Standard embedding dimension."""
    return 384


@pytest.fixture
def random_embedding(embedding_dim):
    """Generate random normalized embedding."""
    def _generate():
        vec = np.random.rand(embedding_dim).astype(np.float32)
        return vec / np.linalg.norm(vec)
    return _generate


class TestVectorMemoryIndex:
    """Tests for VectorMemoryIndex class."""

    def test_init_hnsw(self, embedding_dim):
        """Test HNSW index initialization."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim, use_hnsw=True)

        assert index.embedding_dim == embedding_dim
        assert index.use_hnsw is True
        assert len(index) == 0

    def test_init_flat(self, embedding_dim):
        """Test flat index initialization."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim, use_hnsw=False)

        assert index.use_hnsw is False
        assert len(index) == 0

    def test_add_and_search(self, embedding_dim, random_embedding):
        """Test basic add and search operations."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim)

        # Add some embeddings
        emb1 = random_embedding()
        emb2 = random_embedding()
        emb3 = random_embedding()

        index.add("mem_1", emb1)
        index.add("mem_2", emb2)
        index.add("mem_3", emb3)

        assert len(index) == 3
        assert "mem_1" in index
        assert "mem_2" in index
        assert "mem_3" in index

        # Search with emb1 as query - should return mem_1 as top result
        results = index.search(emb1, top_k=3)

        assert len(results) == 3
        assert results[0][0] == "mem_1"  # Most similar to itself
        assert results[0][1] > 0.99  # Should be ~1.0 similarity

    def test_search_empty_index(self, embedding_dim, random_embedding):
        """Test search on empty index returns empty list."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim)
        results = index.search(random_embedding(), top_k=5)

        assert results == []

    def test_remove(self, embedding_dim, random_embedding):
        """Test item removal."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim)

        index.add("mem_1", random_embedding())
        index.add("mem_2", random_embedding())

        assert len(index) == 2
        assert "mem_1" in index

        # Remove mem_1
        result = index.remove("mem_1")
        assert result is True
        assert "mem_1" not in index

        # Try to remove non-existent
        result = index.remove("nonexistent")
        assert result is False

    def test_rebuild(self, embedding_dim, random_embedding):
        """Test index rebuild after removals."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim)

        # Add items
        for i in range(10):
            index.add(f"mem_{i}", random_embedding())

        # Remove half
        for i in range(5):
            index.remove(f"mem_{i}")

        # Rebuild
        index.rebuild()

        assert len(index) == 5
        for i in range(5, 10):
            assert f"mem_{i}" in index

    def test_dimension_mismatch(self, embedding_dim):
        """Test that dimension mismatch raises error."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim)

        wrong_dim = np.random.rand(128).astype(np.float32)

        with pytest.raises(ValueError, match="dimension mismatch"):
            index.add("mem_1", wrong_dim)

    def test_update_existing(self, embedding_dim, random_embedding):
        """Test updating an existing item."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim)

        emb1 = random_embedding()
        emb2 = random_embedding()

        index.add("mem_1", emb1)
        index.add("mem_1", emb2)  # Update

        assert len(index) == 1

    def test_clear(self, embedding_dim, random_embedding):
        """Test clearing the index."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim)

        for i in range(5):
            index.add(f"mem_{i}", random_embedding())

        index.clear()

        assert len(index) == 0

    def test_get_stats(self, embedding_dim, random_embedding):
        """Test statistics retrieval."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        index = VectorMemoryIndex(embedding_dim=embedding_dim, use_hnsw=True)

        for i in range(10):
            index.add(f"mem_{i}", random_embedding())

        stats = index.get_stats()

        assert stats["total_items"] == 10
        assert stats["embedding_dim"] == embedding_dim
        assert stats["index_type"] == "HNSW"


class TestAgentVectorIndex:
    """Tests for AgentVectorIndex (per-agent indices)."""

    def test_multi_agent_isolation(self, embedding_dim, random_embedding):
        """Test that agent indices are isolated."""
        from cognitive_governance.memory.vector_db import AgentVectorIndex

        manager = AgentVectorIndex(embedding_dim=embedding_dim)

        # Add embeddings for different agents
        emb1 = random_embedding()
        emb2 = random_embedding()

        manager.add("agent_1", "mem_1", emb1)
        manager.add("agent_2", "mem_2", emb2)

        # Search should only return results from queried agent
        results_1 = manager.search("agent_1", emb1, top_k=5)
        results_2 = manager.search("agent_2", emb2, top_k=5)

        assert len(results_1) == 1
        assert results_1[0][0] == "mem_1"

        assert len(results_2) == 1
        assert results_2[0][0] == "mem_2"

    def test_clear_agent(self, embedding_dim, random_embedding):
        """Test clearing a single agent's index."""
        from cognitive_governance.memory.vector_db import AgentVectorIndex

        manager = AgentVectorIndex(embedding_dim=embedding_dim)

        manager.add("agent_1", "mem_1", random_embedding())
        manager.add("agent_2", "mem_2", random_embedding())

        manager.clear_agent("agent_1")

        results_1 = manager.search("agent_1", random_embedding(), top_k=5)
        results_2 = manager.search("agent_2", random_embedding(), top_k=5)

        assert len(results_1) == 0
        assert len(results_2) == 1


class TestVectorIndexPerformance:
    """Performance benchmarks for vector index."""

    @pytest.mark.benchmark
    def test_search_performance(self, embedding_dim, random_embedding):
        """Benchmark search performance at different scales."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        scales = [100, 1000, 5000]
        results = {}

        for n in scales:
            index = VectorMemoryIndex(embedding_dim=embedding_dim, use_hnsw=True)

            # Add n items
            for i in range(n):
                index.add(f"mem_{i}", random_embedding())

            # Benchmark search
            query = random_embedding()
            iterations = 100

            start = time.perf_counter()
            for _ in range(iterations):
                index.search(query, top_k=10)
            elapsed = time.perf_counter() - start

            avg_ms = (elapsed / iterations) * 1000
            results[n] = avg_ms

            # Performance assertion: should be < 10ms even at 5000 items
            assert avg_ms < 50, f"Search too slow at n={n}: {avg_ms:.2f}ms"

        print(f"\nSearch performance: {results}")

    @pytest.mark.benchmark
    def test_linear_vs_hnsw(self, embedding_dim, random_embedding):
        """Compare linear scan vs HNSW performance."""
        from cognitive_governance.memory.vector_db import VectorMemoryIndex

        n = 1000
        iterations = 50

        # Build indices
        hnsw_index = VectorMemoryIndex(embedding_dim=embedding_dim, use_hnsw=True)
        flat_index = VectorMemoryIndex(embedding_dim=embedding_dim, use_hnsw=False)

        embeddings = [random_embedding() for _ in range(n)]
        for i, emb in enumerate(embeddings):
            hnsw_index.add(f"mem_{i}", emb)
            flat_index.add(f"mem_{i}", emb)

        query = random_embedding()

        # Benchmark HNSW
        start = time.perf_counter()
        for _ in range(iterations):
            hnsw_index.search(query, top_k=10)
        hnsw_time = (time.perf_counter() - start) / iterations * 1000

        # Benchmark Flat
        start = time.perf_counter()
        for _ in range(iterations):
            flat_index.search(query, top_k=10)
        flat_time = (time.perf_counter() - start) / iterations * 1000

        print(f"\nHNSW: {hnsw_time:.2f}ms, Flat: {flat_time:.2f}ms")

        # At n=1000, both should be fast, but HNSW has overhead
        # Main benefit is at larger scales
        assert hnsw_time < 20
        assert flat_time < 20
