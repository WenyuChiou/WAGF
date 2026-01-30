# Task 050-A: Vector Database Integration

> **Status**: In Progress
> **Priority**: HIGH
> **Complexity**: Medium

---

## Overview

Integrate FAISS (Facebook AI Similarity Search) for O(log n) semantic retrieval, replacing the current O(n) linear scan approach.

## Problem Statement

Current memory retrieval in `AdaptiveRetrievalEngine.retrieve()` performs:
1. Linear scan over all memories: O(n)
2. Cosine similarity computation for each: O(n × d) where d = embedding dimension

For large memory stores (n > 1000), this becomes a significant bottleneck.

## Literature Reference

| Paper | Key Insight |
|-------|-------------|
| **FAISS: A Library for Efficient Similarity Search** (Johnson et al., 2017) | Hierarchical Navigable Small World (HNSW) graphs achieve O(log n) approximate nearest neighbor search |
| **Billion-scale similarity search with GPUs** (Johnson et al., 2019) | GPU-accelerated similarity search for large-scale retrieval |

### From Zotero (Task-050 Collection)
- L1: A-MEM uses vector indexing for memory linking
- L2: MemGPT's archival memory benefits from efficient retrieval

## Technical Design

### 1. New Module: `vector_db.py`

```
cognitive_governance/memory/
├── vector_db.py          # NEW: FAISS-based vector index
├── retrieval.py          # Modified: integrate vector_db
├── store.py              # Modified: auto-index on add
└── embeddings.py         # Unchanged
```

### 2. Class Design

```python
class VectorMemoryIndex:
    """FAISS-based vector index for O(log n) semantic retrieval."""

    def __init__(self, embedding_dim: int = 384):
        """
        Args:
            embedding_dim: Dimension of embeddings (384 for MiniLM)
        """

    def add(self, item_id: str, embedding: np.ndarray) -> None:
        """Add embedding to index."""

    def search(self, query_embedding: np.ndarray, top_k: int) -> List[Tuple[str, float]]:
        """Return top-k item_ids with distances."""

    def remove(self, item_id: str) -> None:
        """Remove item from index."""
```

### 3. Integration Points

**In `UnifiedMemoryStore.add()`:**
```python
def add(self, item: UnifiedMemoryItem) -> None:
    # ... existing logic ...

    # NEW: Update vector index if embedding present
    if item.embedding is not None and self._vector_index is not None:
        self._vector_index.add(item.id, item.embedding)
```

**In `AdaptiveRetrievalEngine.retrieve()`:**
```python
def retrieve(self, ..., use_vector_index: bool = True) -> List[UnifiedMemoryItem]:
    # If vector index available and query provided, use FAISS
    if use_vector_index and self._vector_index and query:
        candidate_ids = self._vector_index.search(query_embedding, top_k * 2)
        all_items = [self._id_to_item[id] for id in candidate_ids]
    else:
        all_items = store.get_all(agent_id)  # Fallback to linear scan
```

## Performance Expectations

| Metric | Before (O(n)) | After (O(log n)) |
|--------|---------------|------------------|
| 100 memories | ~5ms | ~1ms |
| 1,000 memories | ~50ms | ~2ms |
| 10,000 memories | ~500ms | ~5ms |
| 100,000 memories | ~5s | ~10ms |

## Dependencies

```
faiss-cpu>=1.7.4
# or faiss-gpu for CUDA support
```

## Test Plan

```python
def test_vector_index_basic():
    """Test basic add/search operations."""

def test_vector_index_consistency():
    """Verify index matches memory store state."""

def test_retrieval_speedup():
    """Benchmark O(log n) vs O(n) performance."""
```

## Implementation Steps

1. [x] Create documentation
2. [x] Implement `VectorMemoryIndex` class
3. [x] Add unit tests (14 tests passing)
4. [x] Export from `__init__.py`
5. [ ] Integrate with `UnifiedMemoryStore` (optional, can use standalone)
6. [ ] Integrate with `AdaptiveRetrievalEngine` (optional)
7. [x] Run benchmarks

---

## Files Created/Modified

| File | Status | Description |
|------|--------|-------------|
| `cognitive_governance/memory/vector_db.py` | Created | FAISS-based VectorMemoryIndex |
| `cognitive_governance/memory/__init__.py` | Modified | Export new classes |
| `tests/test_vector_db.py` | Created | 14 unit tests |
| `docs/task-050-memory-optimization/050-A-vector-db.md` | Created | This documentation |

## Usage Example

```python
from cognitive_governance.memory import VectorMemoryIndex, AgentVectorIndex
import numpy as np

# Single index
index = VectorMemoryIndex(embedding_dim=384)
index.add("mem_1", np.random.rand(384))
results = index.search(query_embedding, top_k=10)

# Per-agent index
manager = AgentVectorIndex(embedding_dim=384)
manager.add("agent_1", "mem_1", embedding)
results = manager.search("agent_1", query, top_k=5)
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-29 | Initial design document created |
| 2026-01-29 | Implementation complete, 14 tests passing |
