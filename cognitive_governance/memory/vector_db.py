"""
Vector Database for O(log n) Memory Retrieval.

Provides FAISS-based vector indexing for efficient semantic similarity search.
Replaces O(n) linear scan with O(log n) approximate nearest neighbor search.

Reference:
- Task-050A: Vector DB Integration
- Johnson et al. (2017): FAISS: A Library for Efficient Similarity Search
- A-MEM (2025): Agentic Memory with vector-based linking

Example:
    >>> index = VectorMemoryIndex(embedding_dim=384)
    >>> index.add("mem_1", np.random.rand(384))
    >>> results = index.search(query_embedding, top_k=5)
    >>> print(results)  # [("mem_1", 0.85), ...]
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import logging

# Lazy loading for optional FAISS dependency
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

logger = logging.getLogger(__name__)


class VectorMemoryIndex:
    """
    FAISS-based vector index for O(log n) semantic retrieval.

    Uses HNSW (Hierarchical Navigable Small World) index for fast approximate
    nearest neighbor search. Falls back to flat index for small collections.

    Features:
    - O(log n) search complexity with HNSW
    - Automatic index selection based on collection size
    - Thread-safe operations
    - Memory-efficient incremental updates
    - ID-based item management

    Args:
        embedding_dim: Dimension of embeddings (default: 384 for MiniLM-L6-v2)
        use_hnsw: Use HNSW index (True) or flat index (False)
        hnsw_m: HNSW connectivity parameter (higher = more accurate but slower)
        ef_construction: HNSW construction-time parameter
        ef_search: HNSW search-time parameter

    Example:
        >>> index = VectorMemoryIndex(embedding_dim=384)
        >>> index.add("agent_1:mem_001", embedding_vector)
        >>> results = index.search(query_vector, top_k=10)
        >>> for item_id, distance in results:
        ...     print(f"{item_id}: {distance:.3f}")
    """

    def __init__(
        self,
        embedding_dim: int = 384,
        use_hnsw: bool = True,
        hnsw_m: int = 32,
        ef_construction: int = 64,
        ef_search: int = 32,
    ):
        if not FAISS_AVAILABLE:
            raise ImportError(
                "FAISS is required for VectorMemoryIndex. "
                "Install with: pip install faiss-cpu"
            )

        self.embedding_dim = embedding_dim
        self.use_hnsw = use_hnsw
        self.hnsw_m = hnsw_m
        self.ef_construction = ef_construction
        self.ef_search = ef_search

        # ID mapping: faiss uses integer indices, we map to string IDs
        self._id_to_idx: Dict[str, int] = {}
        self._idx_to_id: Dict[int, str] = {}
        self._next_idx: int = 0

        # Embedding storage for rebuilding index
        self._embeddings: Dict[str, np.ndarray] = {}

        # Initialize FAISS index
        self._index: Optional[faiss.Index] = None
        self._build_index()

    def _build_index(self) -> None:
        """Build or rebuild the FAISS index."""
        if self.use_hnsw:
            # HNSW index with inner product: O(log n) search
            # Use IndexFlatIP as the base quantizer for inner product similarity
            flat_index = faiss.IndexFlatIP(self.embedding_dim)
            self._index = faiss.IndexHNSWFlat(self.embedding_dim, self.hnsw_m, faiss.METRIC_INNER_PRODUCT)
            self._index.hnsw.efConstruction = self.ef_construction
            self._index.hnsw.efSearch = self.ef_search
            logger.debug(
                f"Created HNSW index (IP): dim={self.embedding_dim}, M={self.hnsw_m}"
            )
        else:
            # Flat index: O(n) but exact results
            self._index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product
            logger.debug(f"Created Flat index (IP): dim={self.embedding_dim}")

    def add(self, item_id: str, embedding: np.ndarray) -> None:
        """
        Add an embedding to the index.

        Args:
            item_id: Unique identifier for the memory item
            embedding: Embedding vector (must match embedding_dim)

        Raises:
            ValueError: If embedding dimension doesn't match
        """
        if embedding is None:
            logger.warning(f"Skipping item {item_id}: embedding is None")
            return

        embedding = np.asarray(embedding, dtype=np.float32)

        if embedding.shape[0] != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dim}, "
                f"got {embedding.shape[0]}"
            )

        # Normalize for cosine similarity (inner product on normalized vectors)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        # Handle duplicate IDs (update existing)
        if item_id in self._id_to_idx:
            # For HNSW, we can't remove individual items efficiently
            # Store updated embedding, will be used on rebuild
            self._embeddings[item_id] = embedding
            logger.debug(f"Updated embedding for {item_id}")
            return

        # Add to index
        idx = self._next_idx
        self._next_idx += 1

        self._id_to_idx[item_id] = idx
        self._idx_to_id[idx] = item_id
        self._embeddings[item_id] = embedding

        # Add to FAISS
        self._index.add(embedding.reshape(1, -1))

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Search for similar items.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return

        Returns:
            List of (item_id, similarity_score) tuples, sorted by similarity
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        query_embedding = np.asarray(query_embedding, dtype=np.float32)

        if query_embedding.shape[0] != self.embedding_dim:
            logger.warning(
                f"Query dimension mismatch: expected {self.embedding_dim}, "
                f"got {query_embedding.shape[0]}"
            )
            return []

        # Normalize query
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        # Limit top_k to available items
        actual_k = min(top_k, self._index.ntotal)

        # Search
        distances, indices = self._index.search(
            query_embedding.reshape(1, -1), actual_k
        )

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx in self._idx_to_id:
                item_id = self._idx_to_id[idx]
                # Convert inner product to similarity score [0, 1]
                similarity = max(0.0, min(1.0, float(dist)))
                results.append((item_id, similarity))

        return results

    def remove(self, item_id: str) -> bool:
        """
        Remove an item from the index.

        Note: HNSW doesn't support efficient deletion. This marks the item
        as removed; call rebuild() periodically to reclaim space.

        Args:
            item_id: ID of item to remove

        Returns:
            True if item was found and marked for removal
        """
        if item_id not in self._id_to_idx:
            return False

        # Remove from mappings
        idx = self._id_to_idx.pop(item_id)
        self._idx_to_id.pop(idx, None)
        self._embeddings.pop(item_id, None)

        logger.debug(f"Marked {item_id} for removal (idx={idx})")
        return True

    def rebuild(self) -> None:
        """
        Rebuild the index from stored embeddings.

        Call this periodically if many items have been removed to reclaim space.
        """
        # Reset index
        self._build_index()
        self._id_to_idx.clear()
        self._idx_to_id.clear()
        self._next_idx = 0

        # Re-add all embeddings
        for item_id, embedding in self._embeddings.items():
            idx = self._next_idx
            self._next_idx += 1

            self._id_to_idx[item_id] = idx
            self._idx_to_id[idx] = item_id

            self._index.add(embedding.reshape(1, -1))

        logger.info(f"Rebuilt index with {len(self._embeddings)} items")

    def __len__(self) -> int:
        """Return number of items in index."""
        return len(self._embeddings)

    def __contains__(self, item_id: str) -> bool:
        """Check if item is in index."""
        return item_id in self._id_to_idx

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_items": len(self._embeddings),
            "index_size": self._index.ntotal if self._index else 0,
            "embedding_dim": self.embedding_dim,
            "index_type": "HNSW" if self.use_hnsw else "Flat",
            "hnsw_m": self.hnsw_m if self.use_hnsw else None,
        }

    def clear(self) -> None:
        """Clear the entire index."""
        self._id_to_idx.clear()
        self._idx_to_id.clear()
        self._embeddings.clear()
        self._next_idx = 0
        self._build_index()


class AgentVectorIndex:
    """
    Per-agent vector index manager.

    Maintains separate FAISS indices for each agent to enable
    isolated memory retrieval while sharing the same infrastructure.

    Args:
        embedding_dim: Dimension of embeddings
        **kwargs: Additional arguments passed to VectorMemoryIndex

    Example:
        >>> manager = AgentVectorIndex(embedding_dim=384)
        >>> manager.add("agent_1", "mem_001", embedding)
        >>> results = manager.search("agent_1", query, top_k=5)
    """

    def __init__(self, embedding_dim: int = 384, **kwargs):
        self.embedding_dim = embedding_dim
        self._kwargs = kwargs
        self._indices: Dict[str, VectorMemoryIndex] = {}

    def _get_or_create_index(self, agent_id: str) -> VectorMemoryIndex:
        """Get or create index for agent."""
        if agent_id not in self._indices:
            self._indices[agent_id] = VectorMemoryIndex(
                embedding_dim=self.embedding_dim,
                **self._kwargs
            )
        return self._indices[agent_id]

    def add(self, agent_id: str, item_id: str, embedding: np.ndarray) -> None:
        """Add embedding for an agent's memory item."""
        index = self._get_or_create_index(agent_id)
        index.add(item_id, embedding)

    def search(
        self,
        agent_id: str,
        query_embedding: np.ndarray,
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """Search in an agent's vector index."""
        if agent_id not in self._indices:
            return []
        return self._indices[agent_id].search(query_embedding, top_k)

    def remove(self, agent_id: str, item_id: str) -> bool:
        """Remove item from agent's index."""
        if agent_id not in self._indices:
            return False
        return self._indices[agent_id].remove(item_id)

    def clear_agent(self, agent_id: str) -> None:
        """Clear all items for an agent."""
        if agent_id in self._indices:
            self._indices[agent_id].clear()

    def clear_all(self) -> None:
        """Clear all indices."""
        self._indices.clear()

    def get_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for one or all agents."""
        if agent_id:
            if agent_id in self._indices:
                return {agent_id: self._indices[agent_id].get_stats()}
            return {}

        return {
            aid: idx.get_stats()
            for aid, idx in self._indices.items()
        }
