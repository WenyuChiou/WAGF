"""
Interaction Hub Component - PR 2
Handles information diffusion across Institutional, Social, and Spatial tiers.
"""
from typing import List, Dict, Any, Optional
import random
from .social_graph import SocialGraph
from .memory_engine import MemoryEngine
from simulation.environment import TieredEnvironment

class InteractionHub:
    """
    Manages the 'Worldview' of agents by aggregating tiered information.
    """
    def __init__(self, graph: Optional[SocialGraph] = None, memory_engine: Optional[MemoryEngine] = None, 
                 environment: Optional[TieredEnvironment] = None,
                 spatial_observables: List[str] = None,
                 social_graph: Optional[SocialGraph] = None):
        if graph is None and social_graph is None:
            raise ValueError("InteractionHub requires a social graph")
        self.graph = graph or social_graph
        self.memory_engine = memory_engine
        self.environment = environment
        self.spatial_observables = spatial_observables or []

    def get_spatial_context(self, agent_id: str, agents: Dict[str, Any]) -> Dict[str, Any]:
        """Tier 1 (Spatial): Aggregated observation of neighbors."""
        neighbor_ids = self.graph.get_neighbors(agent_id)
        if not neighbor_ids:
            return {}
        
        total = len(neighbor_ids)
        spatial_context = {"neighbor_count": total}
        
        # Aggregate any attributes defined as observable
        for attr in self.spatial_observables:
            # Count neighbors who have this attribute set to True/Positive
            count = sum(1 for nid in neighbor_ids if getattr(agents[nid], attr, False))
            spatial_context[f"{attr}_pct"] = round((count / total) * 100)
            
        return spatial_context

    def get_visible_neighbor_actions(self, agent_id: str, agents: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get visible physical actions of neighbors (e.g., elevation, relocation).

        Real-world grounding: Households can observe neighbors' physical changes
        like house elevation construction or moving trucks, even without direct
        conversation (observational learning per PubMed 29148082).

        Returns:
            List of visible action dicts
        """
        neighbor_ids = self.graph.get_neighbors(agent_id)
        visible_actions = []

        for nid in neighbor_ids:
            neighbor = agents.get(nid)
            if not neighbor:
                continue

            # Check for elevated status (visible: construction/raised foundation)
            if getattr(neighbor, 'elevated', False):
                visible_actions.append({
                    "neighbor_id": nid,
                    "action": "elevated_house",
                    "description": f"Neighbor {nid} has elevated their house",
                })

            # Check for relocated status (visible: moving truck/empty house)
            if getattr(neighbor, 'relocated', False):
                visible_actions.append({
                    "neighbor_id": nid,
                    "action": "relocated",
                    "description": f"Neighbor {nid} has moved away",
                })

            # Check for insurance (visible sign/sticker)
            if getattr(neighbor, 'has_flood_insurance', False):
                visible_actions.append({
                    "neighbor_id": nid,
                    "action": "insured",
                    "description": f"Neighbor {nid} appears to have flood insurance",
                })

        return visible_actions

    def get_social_context(self, agent_id: str, agents: Dict[str, Any], max_gossip: int = 2) -> Dict[str, Any]:
        """
        Tier 1 (Social): Gossip snippets + visible neighbor actions.

        Returns:
            Dict with 'gossip' (list of snippets) and 'visible_actions' (list of observations)
        """
        gossip = []

        # Gossip from memory engine
        if self.memory_engine:
            neighbor_ids = self.graph.get_neighbors(agent_id)

            # Select chatty neighbors (those who have actual content in memory)
            chatty_neighbors = []
            for nid in neighbor_ids:
                mem = self.memory_engine.retrieve(agents[nid], top_k=1)
                if isinstance(mem, dict):
                    if mem.get("episodic") or mem.get("semantic"):
                        chatty_neighbors.append(nid)
                elif mem:
                    chatty_neighbors.append(nid)

            # Select random snippets from neighbors
            if chatty_neighbors:
                sample_size = min(len(chatty_neighbors), max_gossip)
                for nid in random.sample(chatty_neighbors, sample_size):
                    # Retrieve the most recent memory from the neighbor as gossip
                    neighbor_mems = self.memory_engine.retrieve(agents[nid], top_k=1)

                    # Normalize: Hierarchical memory returns a dict, others return a list
                    mems_list = []
                    if isinstance(neighbor_mems, dict):
                        mems_list = neighbor_mems.get("episodic", []) or neighbor_mems.get("semantic", [])
                    else:
                        mems_list = neighbor_mems

                    if mems_list:
                        gossip.append(f"Neighbor {nid} mentioned: '{mems_list[0]}'")

        # Visible neighbor actions (observational learning)
        visible_actions = self.get_visible_neighbor_actions(agent_id, agents)

        return {
            "gossip": gossip,
            "visible_actions": visible_actions,
            "neighbor_count": len(self.graph.get_neighbors(agent_id)),
        }

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
        
        
        # 3. Custom attributes (Legacy/CSV support) - LOAD FIRST (Base Layer)
        if hasattr(agent, 'custom_attributes'):
            personal.update(agent.custom_attributes)

        # 1. Collect all non-private simple attributes from the agent object - LOAD LAST (Overlay Layer)
        # This ensures dynamic runtime updates (e.g. trust scores) override initial static values.
        for k, v in agent.__dict__.items():
            if k == "agent_type": continue
            if not k.startswith('_') and isinstance(v, (str, int, float, bool)) and k not in ["memory", "id"]:
                personal[k] = v

        # 2. Include dynamic_state contents (Task 015 fix: ensure dynamic attributes are visible)
        if hasattr(agent, 'dynamic_state') and isinstance(agent.dynamic_state, dict):
            for k, v in agent.dynamic_state.items():
                if isinstance(v, (str, int, float, bool)):
                    personal[k] = v

        # 4. Adaptation status (Custom summary)
        if hasattr(agent, 'get_adaptation_status'):
            personal["status"] = agent.get_adaptation_status()

        # 5. [NEW] Pull from TieredEnvironment
        env_context = {"global": [], "local": {}, "institutional": {}}
        if self.environment:
            # Global
            env_context["global"] = list(self.environment.global_state.values())
            
            # Local (based on agent location)
            tract_id = getattr(agent, 'tract_id', None) or getattr(agent, 'location', None)
            if tract_id:
                env_context["local"] = self.environment.local_states.get(tract_id, {})
            
            # Institutional (based on agent type or affiliations)
            inst_id = getattr(agent, 'institution_id', None) or getattr(agent, 'agent_type', None)
            if inst_id:
                env_context["institutional"] = self.environment.institutions.get(inst_id, {})

        # Get social context (gossip + visible actions)
        social_context = self.get_social_context(agent_id, agents)

        result = {
            "personal": personal,
            "local": {
                "spatial": self.get_spatial_context(agent_id, agents),
                "social": social_context.get("gossip", []) if isinstance(social_context, dict) else social_context,
                "visible_actions": social_context.get("visible_actions", []) if isinstance(social_context, dict) else [],
                "environment": env_context["local"]
            },
            "global": global_news or env_context["global"],
            "institutional": env_context["institutional"]
        }
        # Add 'state' alias for validator compatibility
        result["state"] = result["personal"]
        
        return result


