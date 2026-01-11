"""
Social Graph Component - PR 2
Manages connectivity between agents.
"""
from typing import List, Dict, Set
import random

class SocialGraph:
    """Base class for social connectivity."""
    def __init__(self, agent_ids: List[str]):
        self.agent_ids = agent_ids
        self.graph: Dict[str, Set[str]] = {aid: set() for aid in agent_ids}

    def get_neighbors(self, agent_id: str) -> List[str]:
        return list(self.graph.get(agent_id, []))

    def add_edge(self, a_id: str, b_id: str):
        if a_id in self.graph and b_id in self.graph:
            self.graph[a_id].add(b_id)
            self.graph[b_id].add(a_id)

class GlobalGraph(SocialGraph):
    """Fully connected graph (Legacy Behavior). Everyone sees everyone."""
    def __init__(self, agent_ids: List[str]):
        super().__init__(agent_ids)
        for i, a in enumerate(agent_ids):
            for b in agent_ids[i+1:]:
                self.add_edge(a, b)

class RandomGraph(SocialGraph):
    """Erdős-Rényi style random graph."""
    def __init__(self, agent_ids: List[str], p: float = 0.1):
        super().__init__(agent_ids)
        for i, a in enumerate(agent_ids):
            for b in agent_ids[i+1:]:
                if random.random() < p:
                    self.add_edge(a, b)

class NeighborhoodGraph(SocialGraph):
    """K-Nearest Neighbor style graph (Spatial Proximity)."""
    def __init__(self, agent_ids: List[str], k: int = 5):
        super().__init__(agent_ids)
        # Assuming agents are indexed by proximity (e.g. Agent_1 is next to Agent_2)
        n = len(agent_ids)
        for i in range(n):
            for j in range(1, k // 2 + 1):
                neighbor_idx = (i + j) % n
                self.add_edge(agent_ids[i], agent_ids[neighbor_idx])
                neighbor_idx = (i - j) % n
                self.add_edge(agent_ids[i], agent_ids[neighbor_idx])
