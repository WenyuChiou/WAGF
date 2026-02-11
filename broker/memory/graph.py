"""
Graph-based Memory Structure with NetworkX.

Provides hierarchical organization, associative retrieval, and emergent
memory structures inspired by A-MEM (Agentic Memory).

Reference:
- Task-050D: MemoryGraph Implementation
- A-MEM (2025): Zettelkasten-style bidirectional linking
- Generative Agents (Park et al., 2023): Reflection-based hierarchies
- Graphiti (Neo4j, 2025): Knowledge graph with temporal edges

Example:
    >>> graph = MemoryGraph(semantic_threshold=0.7)
    >>> id1 = graph.add_memory(UnifiedMemoryItem(content="Flood event", timestamp=1000))
    >>> id2 = graph.add_memory(UnifiedMemoryItem(content="Insurance claim", timestamp=2000))
    >>> related = graph.retrieve_subgraph(query="flood", seed_memories=[id1], depth=2)
"""

from __future__ import annotations

import hashlib
import heapq
import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    Union,
)

import numpy as np

# NetworkX import
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

from .store import UnifiedMemoryItem


class EmbeddingProviderProtocol(Protocol):
    """Protocol for embedding providers."""

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        ...


EdgeType = Literal["temporal", "semantic", "causal", "summarizes", "references"]


@dataclass
class MemoryEdge:
    """Represents an edge between memory nodes."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryGraph:
    """
    Graph-based memory structure using NetworkX.

    Provides hierarchical organization, associative retrieval, and
    emergent memory structures.

    Features:
    - Temporal edges: Connect sequential memories
    - Semantic edges: Connect similar content
    - Causal edges: Connect cause-effect relationships
    - Summary nodes: Hierarchical consolidation
    - Subgraph retrieval: BFS with scoring

    Args:
        embedding_provider: Optional provider for semantic similarity
        semantic_threshold: Minimum similarity for semantic edges (0.0-1.0)
        temporal_window: Time window for temporal edges (seconds)
        auto_edges: Automatically create temporal/semantic edges on add

    Example:
        >>> graph = MemoryGraph(semantic_threshold=0.7)
        >>> id1 = graph.add_memory(mem1)
        >>> id2 = graph.add_memory(mem2)
        >>> graph.add_edge(id1, id2, edge_type="causal", weight=0.9)
        >>> related = graph.retrieve_subgraph(query="flood", depth=2)
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProviderProtocol] = None,
        semantic_threshold: float = 0.7,
        temporal_window: float = 86400.0,  # 1 day in seconds
        auto_edges: bool = True,
    ):
        if not NETWORKX_AVAILABLE:
            raise ImportError(
                "NetworkX is required for MemoryGraph. "
                "Install with: pip install networkx"
            )

        self.graph: nx.DiGraph = nx.DiGraph()
        self._embedding_provider = embedding_provider
        self._semantic_threshold = semantic_threshold
        self._temporal_window = temporal_window
        self._auto_edges = auto_edges

        # Index for fast lookup
        self._id_to_memory: Dict[str, UnifiedMemoryItem] = {}
        self._timestamp_index: List[Tuple[float, str]] = []  # (timestamp, id)

    def _generate_id(self, memory: UnifiedMemoryItem) -> str:
        """Generate unique ID for memory."""
        content_hash = hashlib.md5(
            f"{memory.content}:{memory.timestamp}".encode()
        ).hexdigest()[:12]
        return f"mem_{content_hash}"

    def add_memory(
        self,
        memory: UnifiedMemoryItem,
        create_temporal: bool = True,
        create_semantic: bool = True,
    ) -> str:
        """
        Add memory as node, optionally create edges to related memories.

        Args:
            memory: The memory item to add
            create_temporal: Create edges to temporally adjacent memories
            create_semantic: Create edges to semantically similar memories

        Returns:
            The generated node ID
        """
        node_id = self._generate_id(memory)

        # Skip if already exists
        if node_id in self.graph:
            return node_id

        # Add node
        self.graph.add_node(
            node_id,
            memory=memory,
            content=memory.content,
            timestamp=memory.timestamp,
            importance=memory.importance,
            node_type="episode",
        )

        # Update indices
        self._id_to_memory[node_id] = memory
        self._timestamp_index.append((memory.timestamp, node_id))
        self._timestamp_index.sort(key=lambda x: x[0])

        # Create automatic edges
        if self._auto_edges:
            if create_temporal:
                self._create_temporal_edges(node_id, memory)
            if create_semantic and self._embedding_provider is not None:
                self._create_semantic_edges(node_id, memory)

        return node_id

    def _create_temporal_edges(self, node_id: str, memory: UnifiedMemoryItem) -> None:
        """Create edges to temporally adjacent memories."""
        ts = memory.timestamp

        for other_ts, other_id in self._timestamp_index:
            if other_id == node_id:
                continue

            time_diff = abs(ts - other_ts)
            if time_diff <= self._temporal_window and time_diff > 0:
                # Weight inversely proportional to time difference
                weight = 1.0 / (1.0 + time_diff / 3600.0)  # Normalize by hours

                # Direction based on time order
                if other_ts < ts:
                    self.graph.add_edge(
                        other_id, node_id,
                        edge_type="temporal",
                        weight=weight,
                        time_diff=time_diff
                    )
                else:
                    self.graph.add_edge(
                        node_id, other_id,
                        edge_type="temporal",
                        weight=weight,
                        time_diff=time_diff
                    )

    def _create_semantic_edges(self, node_id: str, memory: UnifiedMemoryItem) -> None:
        """Create edges to semantically similar memories."""
        if self._embedding_provider is None:
            return

        # Get embedding for new memory
        try:
            new_embedding = self._embedding_provider.embed(memory.content)
        except Exception:
            return

        # Compare with existing memories
        for other_id, other_memory in self._id_to_memory.items():
            if other_id == node_id:
                continue

            try:
                other_embedding = self._embedding_provider.embed(other_memory.content)
                similarity = self._cosine_similarity(new_embedding, other_embedding)

                if similarity >= self._semantic_threshold:
                    # Bidirectional semantic edges
                    self.graph.add_edge(
                        node_id, other_id,
                        edge_type="semantic",
                        weight=similarity
                    )
                    self.graph.add_edge(
                        other_id, node_id,
                        edge_type="semantic",
                        weight=similarity
                    )
            except Exception:
                continue

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        **metadata: Any,
    ) -> bool:
        """
        Manually add an edge between two memory nodes.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Type of relationship
            weight: Edge weight (0.0-1.0)
            **metadata: Additional edge attributes

        Returns:
            True if edge was created, False if nodes don't exist
        """
        if source_id not in self.graph or target_id not in self.graph:
            return False

        self.graph.add_edge(
            source_id, target_id,
            edge_type=edge_type,
            weight=weight,
            **metadata
        )
        return True

    def retrieve_subgraph(
        self,
        query: Optional[str] = None,
        seed_memories: Optional[List[str]] = None,
        depth: int = 2,
        max_nodes: int = 20,
        edge_types: Optional[List[EdgeType]] = None,
    ) -> List[UnifiedMemoryItem]:
        """
        Retrieve memories via graph traversal from seed nodes.

        Uses priority-based BFS where priority is determined by:
        - Edge weight
        - Node importance
        - Depth decay

        Args:
            query: Optional query for semantic seed selection
            seed_memories: List of seed node IDs to start traversal
            depth: Maximum traversal depth
            max_nodes: Maximum nodes to return
            edge_types: Filter by edge types (None = all)

        Returns:
            List of memories sorted by graph score
        """
        if not seed_memories:
            if query and self._embedding_provider:
                seed_memories = self._semantic_seed_selection(query, top_k=3)
            else:
                # Fall back to most important memories
                seed_memories = self._importance_seed_selection(top_k=3)

        if not seed_memories:
            return []

        visited: Set[str] = set()
        result: List[Tuple[float, str, UnifiedMemoryItem]] = []

        # Priority queue: (-score, node_id, depth)
        # Negative score for max-heap behavior
        heap: List[Tuple[float, int, str]] = []
        for seed in seed_memories:
            if seed in self.graph:
                heapq.heappush(heap, (-1.0, 0, seed))

        while heap and len(result) < max_nodes:
            neg_score, d, node_id = heapq.heappop(heap)
            score = -neg_score

            if node_id in visited:
                continue

            if d > depth:
                continue

            visited.add(node_id)

            if node_id in self._id_to_memory:
                memory = self._id_to_memory[node_id]
                result.append((score, node_id, memory))

            # Expand to neighbors
            for neighbor in self.graph.neighbors(node_id):
                if neighbor in visited:
                    continue

                edge_data = self.graph[node_id][neighbor]

                # Filter by edge type
                if edge_types and edge_data.get("edge_type") not in edge_types:
                    continue

                edge_weight = edge_data.get("weight", 0.5)
                neighbor_importance = self.graph.nodes[neighbor].get("importance", 0.5)

                # Score decay with depth
                depth_decay = 0.8 ** d
                new_score = score * edge_weight * neighbor_importance * depth_decay

                heapq.heappush(heap, (-new_score, d + 1, neighbor))

        # Sort by score and return memories
        result.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, _, mem in result]

    def _semantic_seed_selection(self, query: str, top_k: int = 3) -> List[str]:
        """Select seed nodes based on semantic similarity to query."""
        if self._embedding_provider is None:
            return []

        try:
            query_embedding = self._embedding_provider.embed(query)
        except Exception:
            return []

        scores: List[Tuple[float, str]] = []
        for node_id, memory in self._id_to_memory.items():
            try:
                mem_embedding = self._embedding_provider.embed(memory.content)
                similarity = self._cosine_similarity(query_embedding, mem_embedding)
                scores.append((similarity, node_id))
            except Exception:
                continue

        scores.sort(key=lambda x: x[0], reverse=True)
        return [node_id for _, node_id in scores[:top_k]]

    def _importance_seed_selection(self, top_k: int = 3) -> List[str]:
        """Select seed nodes based on importance."""
        nodes_with_importance = [
            (self.graph.nodes[n].get("importance", 0.5), n)
            for n in self.graph.nodes
        ]
        nodes_with_importance.sort(key=lambda x: x[0], reverse=True)
        return [node_id for _, node_id in nodes_with_importance[:top_k]]

    def create_summary_node(
        self,
        child_ids: List[str],
        summary_content: str,
        importance: float = 0.9,
    ) -> str:
        """
        Create hierarchical summary node linked to child memories.

        Used for reflection-based consolidation where multiple episodic
        memories are summarized into a higher-level semantic memory.

        Args:
            child_ids: List of child memory IDs to summarize
            summary_content: The summary text
            importance: Importance of summary (default 0.9)

        Returns:
            The summary node ID
        """
        # Create summary memory
        summary_memory = UnifiedMemoryItem(
            content=summary_content,
            timestamp=time.time(),
            emotion="neutral",
            source="reflection",
            base_importance=importance,
            tags=["summary", "reflection"],
        )

        summary_id = self._generate_id(summary_memory)

        # Add summary node
        self.graph.add_node(
            summary_id,
            memory=summary_memory,
            content=summary_content,
            timestamp=summary_memory.timestamp,
            importance=importance,
            node_type="summary",
        )

        self._id_to_memory[summary_id] = summary_memory

        # Link to children with "summarizes" edge
        for child_id in child_ids:
            if child_id in self.graph:
                self.graph.add_edge(
                    summary_id, child_id,
                    edge_type="summarizes",
                    weight=1.0
                )

        return summary_id

    def get_temporal_sequence(
        self,
        start_id: str,
        direction: Literal["forward", "backward", "both"] = "forward",
        max_length: int = 10,
    ) -> List[UnifiedMemoryItem]:
        """
        Get temporally connected memories starting from a node.

        Args:
            start_id: Starting node ID
            direction: Traverse forward, backward, or both in time
            max_length: Maximum sequence length

        Returns:
            List of memories in temporal order
        """
        if start_id not in self.graph:
            return []

        result: List[Tuple[float, UnifiedMemoryItem]] = []
        visited: Set[str] = set()

        def traverse(node_id: str, remaining: int):
            if remaining <= 0 or node_id in visited:
                return

            visited.add(node_id)
            if node_id in self._id_to_memory:
                memory = self._id_to_memory[node_id]
                result.append((memory.timestamp, memory))

            # Get temporal neighbors
            if direction in ("forward", "both"):
                for neighbor in self.graph.neighbors(node_id):
                    edge_data = self.graph[node_id][neighbor]
                    if edge_data.get("edge_type") == "temporal":
                        traverse(neighbor, remaining - 1)

            if direction in ("backward", "both"):
                for neighbor in self.graph.predecessors(node_id):
                    edge_data = self.graph[neighbor][node_id]
                    if edge_data.get("edge_type") == "temporal":
                        traverse(neighbor, remaining - 1)

        traverse(start_id, max_length)

        # Sort by timestamp
        result.sort(key=lambda x: x[0])
        return [mem for _, mem in result]

    def find_clusters(
        self,
        min_size: int = 3,
        resolution: float = 1.0,
    ) -> List[Set[str]]:
        """
        Find memory clusters for consolidation using community detection.

        Uses Louvain algorithm on the undirected projection of the graph.

        Args:
            min_size: Minimum cluster size to return
            resolution: Louvain resolution parameter (higher = more clusters)

        Returns:
            List of sets, each containing node IDs in a cluster
        """
        if len(self.graph) < min_size:
            return []

        # Convert to undirected for community detection
        undirected = self.graph.to_undirected()

        try:
            # Use Louvain community detection
            communities = nx.community.louvain_communities(
                undirected,
                resolution=resolution,
                seed=42  # For reproducibility
            )

            # Filter by minimum size
            return [c for c in communities if len(c) >= min_size]

        except Exception:
            # Fallback: connected components
            components = list(nx.connected_components(undirected))
            return [c for c in components if len(c) >= min_size]

    def get_memory(self, node_id: str) -> Optional[UnifiedMemoryItem]:
        """Get memory by node ID."""
        return self._id_to_memory.get(node_id)

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[EdgeType] = None,
    ) -> List[Tuple[str, UnifiedMemoryItem, float]]:
        """
        Get neighboring memories with edge weights.

        Args:
            node_id: Node ID to get neighbors for
            edge_type: Filter by edge type (None = all)

        Returns:
            List of (neighbor_id, memory, weight) tuples
        """
        if node_id not in self.graph:
            return []

        result = []
        for neighbor in self.graph.neighbors(node_id):
            edge_data = self.graph[node_id][neighbor]

            if edge_type and edge_data.get("edge_type") != edge_type:
                continue

            if neighbor in self._id_to_memory:
                memory = self._id_to_memory[neighbor]
                weight = edge_data.get("weight", 0.5)
                result.append((neighbor, memory, weight))

        return result

    def remove_memory(self, node_id: str) -> bool:
        """
        Remove a memory node and its edges.

        Args:
            node_id: Node ID to remove

        Returns:
            True if removed, False if not found
        """
        if node_id not in self.graph:
            return False

        self.graph.remove_node(node_id)
        self._id_to_memory.pop(node_id, None)

        # Update timestamp index
        self._timestamp_index = [
            (ts, nid) for ts, nid in self._timestamp_index
            if nid != node_id
        ]

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        edge_types_count: Dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            et = data.get("edge_type", "unknown")
            edge_types_count[et] = edge_types_count.get(et, 0) + 1

        node_types_count: Dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            nt = data.get("node_type", "unknown")
            node_types_count[nt] = node_types_count.get(nt, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": node_types_count,
            "edge_types": edge_types_count,
            "density": nx.density(self.graph) if self.graph.number_of_nodes() > 1 else 0.0,
            "is_connected": nx.is_weakly_connected(self.graph) if self.graph.number_of_nodes() > 0 else True,
        }

    def clear(self) -> None:
        """Clear all nodes and edges."""
        self.graph.clear()
        self._id_to_memory.clear()
        self._timestamp_index.clear()

    def __len__(self) -> int:
        """Return number of memory nodes."""
        return self.graph.number_of_nodes()

    def __contains__(self, node_id: str) -> bool:
        """Check if node exists in graph."""
        return node_id in self.graph


class AgentMemoryGraph:
    """
    Per-agent memory graph manager.

    Maintains separate graphs for each agent while providing
    a unified interface for multi-agent systems.

    Args:
        **kwargs: Arguments passed to MemoryGraph constructor

    Example:
        >>> manager = AgentMemoryGraph(semantic_threshold=0.7)
        >>> manager.add_memory("agent_1", memory1)
        >>> related = manager.retrieve_subgraph("agent_1", depth=2)
    """

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._graphs: Dict[str, MemoryGraph] = {}

    def _get_or_create_graph(self, agent_id: str) -> MemoryGraph:
        """Get or create graph for agent."""
        if agent_id not in self._graphs:
            self._graphs[agent_id] = MemoryGraph(**self._kwargs)
        return self._graphs[agent_id]

    def add_memory(
        self,
        agent_id: str,
        memory: UnifiedMemoryItem,
        **kwargs,
    ) -> str:
        """Add memory to agent's graph."""
        graph = self._get_or_create_graph(agent_id)
        return graph.add_memory(memory, **kwargs)

    def retrieve_subgraph(
        self,
        agent_id: str,
        **kwargs,
    ) -> List[UnifiedMemoryItem]:
        """Retrieve memories from agent's graph."""
        if agent_id not in self._graphs:
            return []
        return self._graphs[agent_id].retrieve_subgraph(**kwargs)

    def create_summary_node(
        self,
        agent_id: str,
        child_ids: List[str],
        summary_content: str,
        **kwargs,
    ) -> str:
        """Create summary node in agent's graph."""
        graph = self._get_or_create_graph(agent_id)
        return graph.create_summary_node(child_ids, summary_content, **kwargs)

    def find_clusters(
        self,
        agent_id: str,
        **kwargs,
    ) -> List[Set[str]]:
        """Find clusters in agent's graph."""
        if agent_id not in self._graphs:
            return []
        return self._graphs[agent_id].find_clusters(**kwargs)

    def get_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for one or all agents."""
        if agent_id:
            if agent_id in self._graphs:
                return {agent_id: self._graphs[agent_id].get_stats()}
            return {}

        return {
            aid: graph.get_stats()
            for aid, graph in self._graphs.items()
        }

    def clear_agent(self, agent_id: str) -> None:
        """Clear graph for specific agent."""
        if agent_id in self._graphs:
            self._graphs[agent_id].clear()

    def clear_all(self) -> None:
        """Clear all graphs."""
        self._graphs.clear()
