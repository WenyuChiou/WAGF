"""
Interaction Hub Component - PR 2
Handles information diffusion across Institutional, Social, and Spatial tiers.
"""
from typing import List, Dict, Any, Optional
import random
from .social_graph import SocialGraph
from .memory_engine import MemoryEngine

class InteractionHub:
    """
    Manages the 'Worldview' of agents by aggregating tiered information.
    """
    def __init__(self, graph: SocialGraph, memory_engine: Optional[MemoryEngine] = None):
        self.graph = graph
        self.memory_engine = memory_engine

    def get_spatial_context(self, agent_id: str, agents: Dict[str, Any]) -> Dict[str, Any]:
        """Tier 1 (Spatial): Aggregated observation of neighbors."""
        neighbor_ids = self.graph.get_neighbors(agent_id)
        if not neighbor_ids:
            return {"elevated_pct": 0, "relocated_pct": 0}
        
        total = len(neighbor_ids)
        elevated = sum(1 for nid in neighbor_ids if getattr(agents[nid], 'elevated', False))
        relocated = sum(1 for nid in neighbor_ids if getattr(agents[nid], 'relocated', False))
        
        return {
            "neighbor_count": total,
            "elevated_pct": round((elevated / total) * 100),
            "relocated_pct": round((relocated / total) * 100)
        }

    def get_social_context(self, agent_id: str, agents: Dict[str, Any], max_gossip: int = 2) -> List[str]:
        """Tier 1 (Social): Gossip/Shared snippets from neighbor memories."""
        if not self.memory_engine:
            return []
            
        neighbor_ids = self.graph.get_neighbors(agent_id)
        gossip = []
        
        # Select chatty neighbors (those who have any memory in the engine)
        chatty_neighbors = [nid for nid in neighbor_ids if self.memory_engine.retrieve(agents[nid], top_k=1)]
        if not chatty_neighbors:
            return []
            
        # Select random snippets from neighbors
        sample_size = min(len(chatty_neighbors), max_gossip)
        for nid in random.sample(chatty_neighbors, sample_size):
            # Retrieve the most recent memory from the neighbor as gossip
            neighbor_mems = self.memory_engine.retrieve(agents[nid], top_k=1)
            if neighbor_mems:
                gossip.append(f"Neighbor {nid} mentioned: '{neighbor_mems[0]}'")
            
        return gossip

    def build_tiered_context(self, agent_id: str, agents: Dict[str, Any], global_news: List[str] = None) -> Dict[str, Any]:
        """Aggregate all tiers into a unified context slice."""
        agent = agents[agent_id]
        personal_memory = self.memory_engine.retrieve(agent, top_k=3) if self.memory_engine else []
        
        # [GENERALIZATION] Gather all non-private attributes for the personal block
        # This removes domain-specific hardcoding (like 'elevated') from the core hub.
        personal = {
            "id": agent_id,
            "memory": personal_memory,
        }
        
        # Safely gather other state attributes
        # We look into getattr(agent, ...) for common attributes if they exist
        # and include anything from agent.dynamic_state or agent.custom_attributes
        
        # 1. Standard attributes (if they exist)
        for attr in ["agent_type", "elevated", "has_insurance", "trust_in_insurance", "trust_in_neighbors", "income", "savings"]:
            val = getattr(agent, attr, None)
            if val is not None:
                personal[attr] = val
        
        # 2. Dynamic state (PR 9 partitioning)
        if hasattr(agent, 'dynamic_state'):
            personal.update(agent.dynamic_state)
            
        # 3. Custom attributes (Legacy/CSV support)
        if hasattr(agent, 'custom_attributes'):
            personal.update(agent.custom_attributes)

        # 4. Adaptation status (Custom summary)
        if hasattr(agent, 'get_adaptation_status'):
            personal["status"] = agent.get_adaptation_status()

        return {
            "personal": personal,
            "local": {
                "spatial": self.get_spatial_context(agent_id, agents),
                "social": self.get_social_context(agent_id, agents)
            },
            "global": global_news or []
        }


