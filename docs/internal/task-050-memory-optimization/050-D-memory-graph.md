# Task 050-D: MemoryGraph with NetworkX

> **Status**: Complete
> **Priority**: HIGH
> **Complexity**: High

---

## Overview

Implement a graph-based memory structure using NetworkX, enabling hierarchical organization, associative retrieval, and emergent memory structures inspired by A-MEM (Agentic Memory).

## Problem Statement

Current memory system limitations:
1. Flat `List[UnifiedMemoryItem]` structure cannot represent relationships
2. No way to express temporal causality between memories
3. Missing semantic clustering/hierarchies
4. Cannot traverse related memories via associations
5. Summary/consolidation breaks links to original episodes

## Literature Reference

| Paper | Key Insight |
|-------|-------------|
| **A-MEM** (2025) | Zettelkasten-style bidirectional linking for emergent structure |
| **Generative Agents** (Park et al., 2023) | Memory stream with reflection-based hierarchies |
| **Graphiti** (Neo4j, 2025) | Knowledge graph as agent memory with temporal edges |
| **MemGPT** (Packer et al., 2023) | Tiered memory with archival structure |

### From Zotero (Task-050 Collection)
- L1: A-MEM's atomic notes and bidirectional linking
- L3: Generative Agents' reflection creates higher-level nodes
- L5: Graphiti's temporal edge representation

## Technical Design

### 1. Graph Structure

```
                    ┌─────────────────┐
                    │  Summary Node   │
                    │  (Reflection)   │
                    │  importance=0.9 │
                    └────────┬────────┘
                             │ "summarizes"
              ┌──────────────┼──────────────┐
              ↓              ↓              ↓
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │Episode 1│◄──▶│Episode 2│◄──▶│Episode 3│
        │ Year 3  │    │ Year 5  │    │ Year 7  │
        └─────────┘    └─────────┘    └─────────┘
              │ "temporal"    │ "semantic"
              ▼              ▼
        ┌─────────┐    ┌─────────┐
        │Episode 0│    │Episode 4│
        │ Year 2  │    │ Year 6  │
        └─────────┘    └─────────┘
```

### 2. Edge Types

| Edge Type | Description | Weight Source |
|-----------|-------------|---------------|
| `temporal` | Sequential in time | 1 / time_diff |
| `semantic` | Similar content | Cosine similarity |
| `causal` | Cause-effect | Manual/LLM inference |
| `summarizes` | Hierarchy link | Fixed 1.0 |
| `references` | Explicit mention | Fixed 0.8 |

### 3. Class Design

```python
class MemoryGraph:
    """Graph-based memory structure with NetworkX."""

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        semantic_threshold: float = 0.7,
        temporal_window: float = 86400.0,  # 1 day in seconds
    ):
        self.graph = nx.DiGraph()
        self._embedding_provider = embedding_provider
        self._semantic_threshold = semantic_threshold
        self._temporal_window = temporal_window

    def add_memory(self, memory: UnifiedMemoryItem) -> str:
        """Add memory as node, create edges to related memories."""

    def retrieve_subgraph(
        self,
        query: str,
        seed_memories: Optional[List[str]] = None,
        depth: int = 2,
        max_nodes: int = 20
    ) -> List[UnifiedMemoryItem]:
        """Retrieve memories via graph traversal."""

    def create_summary_node(
        self,
        child_ids: List[str],
        summary_content: str
    ) -> str:
        """Create hierarchical summary node."""

    def get_temporal_sequence(
        self,
        start_id: str,
        direction: str = "forward"
    ) -> List[UnifiedMemoryItem]:
        """Get temporally connected memories."""

    def find_clusters(self, min_size: int = 3) -> List[Set[str]]:
        """Find semantic clusters for consolidation."""
```

### 4. Integration with Retrieval

```python
# Enhanced retrieval with graph traversal
class GraphEnhancedRetrieval:
    def retrieve(self, query: str, agent_id: str, **kwargs):
        # 1. Get seed memories via importance/recency
        seeds = self.base_retrieval(query, top_k=5)

        # 2. Expand via graph
        expanded = self.memory_graph.retrieve_subgraph(
            query=query,
            seed_memories=[m.id for m in seeds],
            depth=2
        )

        # 3. Re-rank by combined score
        return self.rerank(expanded, query)
```

## Implementation Steps

1. [x] Create documentation
2. [x] Implement `MemoryGraph` class
3. [x] Implement edge creation strategies
4. [x] Implement subgraph retrieval
5. [x] Add clustering for consolidation
6. [x] Add unit tests (28 tests passing)
7. [x] Export from memory/__init__.py
8. [ ] Integration with UnifiedCognitiveEngine (optional, future)

---

## Files Created/Modified

| File | Status | Description |
|------|--------|-------------|
| `cognitive_governance/memory/graph.py` | Created | MemoryGraph implementation |
| `cognitive_governance/memory/__init__.py` | Modified | Export new classes |
| `tests/test_memory_graph.py` | Created | 25 unit tests |

## Usage Example

```python
from cognitive_governance.memory import MemoryGraph, UnifiedMemoryItem

# Create graph
graph = MemoryGraph(semantic_threshold=0.7)

# Add memories
mem1 = UnifiedMemoryItem(content="Flood damaged my house", timestamp=1000)
mem2 = UnifiedMemoryItem(content="Insurance denied my claim", timestamp=2000)
mem3 = UnifiedMemoryItem(content="Neighbor helped with repairs", timestamp=3000)

id1 = graph.add_memory(mem1)
id2 = graph.add_memory(mem2)
id3 = graph.add_memory(mem3)

# Manual causal link
graph.add_edge(id1, id2, edge_type="causal", weight=0.9)

# Retrieve related memories
related = graph.retrieve_subgraph(
    query="flood damage",
    seed_memories=[id1],
    depth=2,
    max_nodes=10
)

# Create summary (reflection)
summary_id = graph.create_summary_node(
    child_ids=[id1, id2, id3],
    summary_content="Year 3 flood experience: damage, insurance issues, community support"
)

# Find clusters for consolidation
clusters = graph.find_clusters(min_size=3)

# Get temporal sequence
sequence = graph.get_temporal_sequence(id1, direction="forward")
```

## Algorithm Details

### Subgraph Retrieval (BFS with Scoring)

```python
def retrieve_subgraph(self, query, seed_memories, depth, max_nodes):
    visited = set()
    result = []
    queue = [(seed, 0, 1.0) for seed in seed_memories]  # (node, depth, score)

    while queue and len(result) < max_nodes:
        node, d, score = heapq.heappop(queue)  # Priority by score

        if node in visited or d > depth:
            continue

        visited.add(node)
        memory = self.graph.nodes[node]["memory"]
        memory._graph_score = score
        result.append(memory)

        # Expand to neighbors
        for neighbor in self.graph.neighbors(node):
            edge_weight = self.graph[node][neighbor].get("weight", 0.5)
            new_score = score * edge_weight * (0.8 ** d)  # Decay with depth
            heapq.heappush(queue, (neighbor, d + 1, -new_score))  # Max-heap

    return sorted(result, key=lambda m: m._graph_score, reverse=True)
```

### Clustering (Louvain Community Detection)

```python
def find_clusters(self, min_size=3):
    # Convert to undirected for community detection
    undirected = self.graph.to_undirected()

    # Louvain algorithm
    communities = nx.community.louvain_communities(undirected)

    # Filter by size
    return [c for c in communities if len(c) >= min_size]
```

---

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|------------|-------|
| add_memory | O(n) | n = existing nodes for edge creation |
| retrieve_subgraph | O(d * k) | d = depth, k = avg degree |
| find_clusters | O(n log n) | Louvain algorithm |
| create_summary_node | O(k) | k = number of children |

## Dependencies

- `networkx>=3.0` (already in requirements)
- Optional: `python-louvain` for advanced community detection

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-29 | Initial design document created |
| 2026-01-29 | Implementation complete, 25 tests passing |
