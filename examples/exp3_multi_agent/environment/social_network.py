"""
Social Network Module (Exp3)

Implements neighbor influence modeling based on:
- ResearchGate/NSF literature on ABM social networks in flood adaptation
- PMT integration for neighbor-influenced risk perception

Key features:
1. Geographic neighbor assignment
2. Observe neighbor actions
3. Update risk perception based on social influence
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import random


@dataclass
class SocialNetwork:
    """
    Manages social connections between household agents.
    
    Design:
    - Each agent has a set of neighbor IDs
    - Neighbors can be geographic (same region) or random
    - Influence flows through observation of neighbor actions
    """
    
    # agent_id -> set of neighbor agent_ids
    connections: Dict[str, Set[str]] = field(default_factory=dict)
    
    # Configuration
    max_neighbors: int = 5
    same_region_weight: float = 0.7  # 70% neighbors from same region
    
    def build_network(self, agents: List, seed: int = 42):
        """
        Build social network from agent list.
        
        Uses weighted random assignment:
        - 70% neighbors from same region (geographic proximity)
        - 30% random (social connections beyond geography)
        
        Args:
            agents: List of HouseholdAgent instances
            seed: Random seed for reproducibility
        """
        random.seed(seed)
        
        # Group agents by region
        by_region: Dict[str, List[str]] = {}
        for agent in agents:
            region = agent.state.region_id
            if region not in by_region:
                by_region[region] = []
            by_region[region].append(agent.state.id)
        
        all_ids = [a.state.id for a in agents]
        
        for agent in agents:
            aid = agent.state.id
            region = agent.state.region_id
            
            # Potential neighbors: same region (weighted) + others
            same_region = [x for x in by_region.get(region, []) if x != aid]
            other_region = [x for x in all_ids if x != aid and x not in same_region]
            
            neighbors = set()
            target_count = min(self.max_neighbors, len(all_ids) - 1)
            
            # Weighted selection
            same_count = int(target_count * self.same_region_weight)
            other_count = target_count - same_count
            
            if same_region:
                neighbors.update(random.sample(same_region, min(same_count, len(same_region))))
            if other_region:
                neighbors.update(random.sample(other_region, min(other_count, len(other_region))))
            
            # Fill remaining slots if needed
            remaining = [x for x in all_ids if x != aid and x not in neighbors]
            while len(neighbors) < target_count and remaining:
                pick = random.choice(remaining)
                neighbors.add(pick)
                remaining.remove(pick)
            
            self.connections[aid] = neighbors
    
    def get_neighbors(self, agent_id: str) -> Set[str]:
        """Get neighbor IDs for an agent."""
        return self.connections.get(agent_id, set())
    
    def observe_neighbors(self, agent_id: str, agents_dict: Dict[str, 'HouseholdAgent']) -> Dict[str, int]:
        """
        Observe neighbor actions and states.
        
        Returns summary of neighbor statuses:
        - elevated_count: How many neighbors have elevated homes
        - insured_count: How many neighbors have insurance
        - relocated_count: How many neighbors have relocated
        - recent_actions: Recent decision summary
        
        Args:
            agent_id: The observing agent's ID
            agents_dict: Dict mapping agent_id -> HouseholdAgent
            
        Returns:
            Dict with observation counts
        """
        neighbors = self.get_neighbors(agent_id)
        
        observations = {
            "elevated_count": 0,
            "insured_count": 0,
            "relocated_count": 0,
            "neighbor_count": len(neighbors)
        }
        
        for nid in neighbors:
            neighbor = agents_dict.get(nid)
            if neighbor:
                if neighbor.state.elevated:
                    observations["elevated_count"] += 1
                if neighbor.state.has_insurance:
                    observations["insured_count"] += 1
                if neighbor.state.relocated:
                    observations["relocated_count"] += 1
        
        return observations
    
    def calculate_social_influence(self, observations: Dict) -> Dict[str, float]:
        """
        Calculate social influence factors based on neighbor observations.
        
        Based on PMT literature:
        - Seeing neighbors adapt increases coping appraisal (SC)
        - Seeing neighbors affected increases threat perception (TP)
        
        Returns influence multipliers for PMT constructs.
        """
        n = observations.get("neighbor_count", 1)
        if n == 0:
            return {"tp_influence": 1.0, "sc_influence": 1.0}
        
        # Elevated neighbors increase SC
        elev_rate = observations.get("elevated_count", 0) / n
        
        # Insured neighbors increase SC
        ins_rate = observations.get("insured_count", 0) / n
        
        # Relocated neighbors might increase TP (area is dangerous)
        reloc_rate = observations.get("relocated_count", 0) / n
        
        # Influence multipliers (1.0 = no influence)
        sc_influence = 1.0 + (elev_rate + ins_rate) * 0.3  # Up to +30%
        tp_influence = 1.0 + reloc_rate * 0.2  # Up to +20%
        
        return {
            "tp_influence": tp_influence,
            "sc_influence": sc_influence,
            "adaptation_exposure": elev_rate + ins_rate
        }


def create_network_from_agents(agents: List, seed: int = 42) -> SocialNetwork:
    """Factory function to create and build a social network."""
    network = SocialNetwork()
    network.build_network(agents, seed)
    return network
