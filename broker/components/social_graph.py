"""
Social Graph Component
Manages connectivity between agents for social influence modeling.

Design Principles:
- Generic: No domain-specific hardcoding
- Extensible: Users can subclass SocialGraph for custom topologies
- Pluggable: Factory function for configuration-driven creation

Usage:
    # Option 1: Use built-in graph types
    graph = create_social_graph("neighborhood", agent_ids, k=5)
    
    # Option 2: Custom graph via edge builder
    def my_edge_builder(agent_ids):
        return [("A1", "A2"), ("A2", "A3")]  # List of (from, to) tuples
    graph = create_social_graph("custom", agent_ids, edge_builder=my_edge_builder)
    
    # Option 3: Subclass SocialGraph
    class MyGraph(SocialGraph):
        def __init__(self, agent_ids):
            super().__init__(agent_ids)
            # Custom connection logic
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Set, Callable, Optional, Tuple
import random


class SocialGraph(ABC):
    """
    Abstract Base Class for social connectivity graphs.
    
    Subclass this to implement custom network topologies.
    
    Required to implement:
        - __init__ should call super().__init__(agent_ids) then build edges
    
    Provided methods:
        - get_neighbors(agent_id) -> List[str]
        - add_edge(a_id, b_id) - bidirectional
        - remove_edge(a_id, b_id)
        - clear()
    """
    
    def __init__(self, agent_ids: List[str]):
        self.agent_ids = agent_ids
        self.graph: Dict[str, Set[str]] = {aid: set() for aid in agent_ids}

    def get_neighbors(self, agent_id: str) -> List[str]:
        """Get list of neighbor IDs for an agent."""
        return list(self.graph.get(agent_id, []))
    
    def get_neighbor_count(self, agent_id: str) -> int:
        """Get number of neighbors for an agent."""
        return len(self.graph.get(agent_id, []))

    def add_edge(self, a_id: str, b_id: str):
        """Add bidirectional edge between two agents."""
        if a_id in self.graph and b_id in self.graph:
            self.graph[a_id].add(b_id)
            self.graph[b_id].add(a_id)
    
    def remove_edge(self, a_id: str, b_id: str):
        """Remove edge between two agents."""
        if a_id in self.graph:
            self.graph[a_id].discard(b_id)
        if b_id in self.graph:
            self.graph[b_id].discard(a_id)
    
    def clear(self):
        """Remove all edges."""
        for aid in self.graph:
            self.graph[aid] = set()
    
    def to_dict(self) -> Dict[str, List[str]]:
        """Serialize graph for logging/debugging."""
        return {aid: list(neighbors) for aid, neighbors in self.graph.items()}
    
    def summary(self) -> Dict[str, any]:
        """Get graph statistics."""
        degrees = [len(neighbors) for neighbors in self.graph.values()]
        return {
            "num_agents": len(self.agent_ids),
            "num_edges": sum(degrees) // 2,
            "avg_degree": sum(degrees) / len(degrees) if degrees else 0,
            "max_degree": max(degrees) if degrees else 0,
            "min_degree": min(degrees) if degrees else 0,
        }


class GlobalGraph(SocialGraph):
    """Fully connected graph. Everyone sees everyone."""
    
    def __init__(self, agent_ids: List[str]):
        super().__init__(agent_ids)
        for i, a in enumerate(agent_ids):
            for b in agent_ids[i+1:]:
                self.add_edge(a, b)


class RandomGraph(SocialGraph):
    """
    Erdős-Rényi random graph.
    
    Args:
        agent_ids: List of agent identifiers
        p: Probability of edge between any two agents (0-1)
        seed: Random seed for reproducibility
    """
    
    def __init__(self, agent_ids: List[str], p: float = 0.1, seed: Optional[int] = None):
        super().__init__(agent_ids)
        if seed is not None:
            random.seed(seed)
        for i, a in enumerate(agent_ids):
            for b in agent_ids[i+1:]:
                if random.random() < p:
                    self.add_edge(a, b)


class NeighborhoodGraph(SocialGraph):
    """
    K-Nearest Neighbor ring graph (Spatial Proximity).
    
    Assumes agents are ordered by proximity (e.g., Agent_1 near Agent_2).
    Each agent connects to k/2 neighbors on each side (circular).
    
    Args:
        agent_ids: List of agent identifiers
        k: Total number of neighbors per agent
    """
    
    def __init__(self, agent_ids: List[str], k: int = 5):
        super().__init__(agent_ids)
        n = len(agent_ids)
        for i in range(n):
            for j in range(1, k // 2 + 1):
                neighbor_idx = (i + j) % n
                self.add_edge(agent_ids[i], agent_ids[neighbor_idx])
                neighbor_idx = (i - j) % n
                self.add_edge(agent_ids[i], agent_ids[neighbor_idx])


class CustomGraph(SocialGraph):
    """
    User-defined graph via edge builder function.

    Args:
        agent_ids: List of agent identifiers
        edge_builder: Callable that returns list of (from_id, to_id) tuples
    """

    def __init__(self, agent_ids: List[str],
                 edge_builder: Callable[[List[str]], List[Tuple[str, str]]]):
        super().__init__(agent_ids)
        edges = edge_builder(agent_ids)
        for a, b in edges:
            self.add_edge(a, b)


class SpatialNeighborhoodGraph(SocialGraph):
    """
    Spatial neighbor graph using actual grid coordinates.

    Connects agents within a configurable radius based on Euclidean or Manhattan
    distance between their (grid_x, grid_y) positions. This is more realistic
    than ring topology as it reflects actual geographic proximity.

    Args:
        agent_ids: List of agent identifiers
        positions: Dict mapping agent_id to (grid_x, grid_y) tuple
        radius: Connection radius in grid cells (default: 3 cells = ~90m at 30m resolution)
        metric: Distance metric ('euclidean' or 'manhattan')
        fallback_k: If an agent has fewer than fallback_k neighbors within radius,
                    connect to k-nearest regardless of radius (handles sparse areas)
        cell_size_m: Physical cell size in meters (default: 30.0) for logging

    Example:
        positions = {"H0001": (100, 200), "H0002": (101, 201), "H0003": (150, 250)}
        graph = SpatialNeighborhoodGraph(
            list(positions.keys()),
            positions=positions,
            radius=3
        )
    """

    def __init__(
        self,
        agent_ids: List[str],
        positions: Dict[str, Tuple[int, int]],
        radius: float = 3.0,
        metric: str = "euclidean",
        fallback_k: int = 2,
        cell_size_m: float = 30.0,
    ):
        super().__init__(agent_ids)
        self.positions = positions
        self.radius = radius
        self.metric = metric.lower()
        self.fallback_k = fallback_k
        self.cell_size_m = cell_size_m

        # Build graph based on spatial proximity
        self._build_spatial_graph()

    def _calculate_distance(
        self, pos1: Tuple[int, int], pos2: Tuple[int, int]
    ) -> float:
        """Calculate distance between two grid positions."""
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]

        if self.metric == "manhattan":
            return abs(dx) + abs(dy)
        else:  # euclidean
            return (dx**2 + dy**2) ** 0.5

    def _build_spatial_graph(self):
        """Build edges based on spatial proximity."""
        # Pre-compute all pairwise distances
        distances: Dict[str, List[Tuple[str, float]]] = {aid: [] for aid in self.agent_ids}

        for i, a_id in enumerate(self.agent_ids):
            if a_id not in self.positions:
                continue
            pos_a = self.positions[a_id]

            for b_id in self.agent_ids[i+1:]:
                if b_id not in self.positions:
                    continue
                pos_b = self.positions[b_id]

                dist = self._calculate_distance(pos_a, pos_b)
                distances[a_id].append((b_id, dist))
                distances[b_id].append((a_id, dist))

                # Add edge if within radius
                if dist <= self.radius:
                    self.add_edge(a_id, b_id)

        # Apply fallback for isolated agents
        for a_id in self.agent_ids:
            if self.get_neighbor_count(a_id) < self.fallback_k and distances[a_id]:
                # Sort by distance and connect to k-nearest
                sorted_neighbors = sorted(distances[a_id], key=lambda x: x[1])
                for b_id, _ in sorted_neighbors[:self.fallback_k]:
                    self.add_edge(a_id, b_id)

    def get_neighbors_within_radius(
        self, agent_id: str, radius: Optional[float] = None
    ) -> List[str]:
        """
        Get neighbors within a custom radius (dynamic query).

        Args:
            agent_id: Agent to query
            radius: Custom radius (uses instance radius if None)

        Returns:
            List of neighbor IDs within radius
        """
        if agent_id not in self.positions:
            return []

        radius = radius if radius is not None else self.radius
        pos_a = self.positions[agent_id]
        neighbors = []

        for b_id in self.agent_ids:
            if b_id == agent_id or b_id not in self.positions:
                continue
            pos_b = self.positions[b_id]
            if self._calculate_distance(pos_a, pos_b) <= radius:
                neighbors.append(b_id)

        return neighbors

    def get_spatial_stats(self) -> Dict[str, any]:
        """Get spatial graph statistics."""
        base_stats = self.summary()

        # Calculate isolation stats
        isolated = sum(1 for aid in self.agent_ids if self.get_neighbor_count(aid) == 0)
        fallback_applied = sum(
            1 for aid in self.agent_ids
            if 0 < self.get_neighbor_count(aid) < self.fallback_k
        )

        # Calculate distance stats for connected pairs
        distances = []
        for a_id in self.agent_ids:
            if a_id not in self.positions:
                continue
            pos_a = self.positions[a_id]
            for b_id in self.get_neighbors(a_id):
                if b_id not in self.positions:
                    continue
                pos_b = self.positions[b_id]
                distances.append(self._calculate_distance(pos_a, pos_b))

        base_stats.update({
            "radius": self.radius,
            "radius_m": self.radius * self.cell_size_m,
            "metric": self.metric,
            "isolated_agents": isolated,
            "fallback_applied": fallback_applied,
            "avg_neighbor_distance": sum(distances) / len(distances) if distances else 0,
            "max_neighbor_distance": max(distances) if distances else 0,
        })

        return base_stats


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_social_graph(
    graph_type: str,
    agent_ids: List[str],
    **kwargs
) -> SocialGraph:
    """
    Factory function to create social graphs.

    Args:
        graph_type: One of "global", "random", "neighborhood", "spatial", "custom"
        agent_ids: List of agent identifiers
        **kwargs: Graph-specific parameters:
            - random: p (float), seed (int)
            - neighborhood: k (int)
            - spatial: positions (Dict), radius (float), metric (str), fallback_k (int)
            - custom: edge_builder (Callable)

    Returns:
        SocialGraph instance

    Example:
        graph = create_social_graph("neighborhood", ["A1", "A2", "A3"], k=2)

        # Spatial graph with grid positions
        positions = {"A1": (0, 0), "A2": (1, 1), "A3": (10, 10)}
        graph = create_social_graph("spatial", list(positions.keys()),
                                    positions=positions, radius=3)
    """
    graph_type = graph_type.lower()

    if graph_type == "global":
        return GlobalGraph(agent_ids)
    elif graph_type == "random":
        return RandomGraph(agent_ids, p=kwargs.get("p", 0.1), seed=kwargs.get("seed"))
    elif graph_type == "neighborhood":
        return NeighborhoodGraph(agent_ids, k=kwargs.get("k", 5))
    elif graph_type == "spatial":
        positions = kwargs.get("positions")
        if not positions:
            raise ValueError("SpatialNeighborhoodGraph requires 'positions' dict")
        return SpatialNeighborhoodGraph(
            agent_ids,
            positions=positions,
            radius=kwargs.get("radius", 3.0),
            metric=kwargs.get("metric", "euclidean"),
            fallback_k=kwargs.get("fallback_k", 2),
            cell_size_m=kwargs.get("cell_size_m", 30.0),
        )
    elif graph_type == "custom":
        edge_builder = kwargs.get("edge_builder")
        if not edge_builder:
            raise ValueError("CustomGraph requires 'edge_builder' function")
        return CustomGraph(agent_ids, edge_builder)
    else:
        raise ValueError(f"Unknown graph type: {graph_type}. "
                         f"Supported: global, random, neighborhood, spatial, custom")

