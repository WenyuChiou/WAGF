"""
Interaction Hub Component - PR 2
Handles information diffusion across Institutional, Social, and Spatial tiers.

Phase 8 Update: Supports SDK observers for domain-agnostic observation.
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import random
from .social_graph import SocialGraph
from .memory_engine import MemoryEngine
from broker.simulation.environment import TieredEnvironment

# SDK observer imports (optional, for v2 methods)
if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.social import SocialObserver
    from cognitive_governance.v1_prototype.observation import EnvironmentObserver


class InteractionHub:
    """
    Manages the 'Worldview' of agents by aggregating tiered information.

    Phase 8: Now supports SDK observers for domain-agnostic observation.
    Use `social_observer` and `environment_observer` params for SDK integration,
    or omit them to use legacy hardcoded observation logic.
    """
    def __init__(
        self,
        graph: Optional[SocialGraph] = None,
        memory_engine: Optional[MemoryEngine] = None,
        environment: Optional[TieredEnvironment] = None,
        spatial_observables: List[str] = None,
        social_graph: Optional[SocialGraph] = None,
        # Phase 8: SDK observer support
        social_observer: Optional["SocialObserver"] = None,
        environment_observer: Optional["EnvironmentObserver"] = None,
    ):
        if graph is None and social_graph is None:
            raise ValueError("InteractionHub requires a social graph")
        self.graph = graph or social_graph
        self.memory_engine = memory_engine
        self.environment = environment
        self.spatial_observables = spatial_observables or []
        # SDK observers (None = use legacy logic)
        self.social_observer = social_observer
        self.environment_observer = environment_observer

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
            spatial_context[f"{attr}_pct"] = count / total
            
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

    def get_visible_neighbor_actions_v2(
        self,
        agent_id: str,
        agents: Dict[str, Any],
        observer: Optional["SocialObserver"] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get visible neighbor actions using SDK SocialObserver.

        Phase 8: Uses domain-agnostic observer pattern instead of hardcoded checks.

        Args:
            agent_id: The observing agent's ID
            agents: Dictionary of all agents
            observer: SDK SocialObserver instance (uses self.social_observer if None)

        Returns:
            List of visible action dicts from SDK observer
        """
        obs = observer or self.social_observer
        if obs is None:
            # Fallback to legacy method
            return self.get_visible_neighbor_actions(agent_id, agents)

        neighbor_ids = self.graph.get_neighbors(agent_id)
        visible_actions = []

        for nid in neighbor_ids:
            neighbor = agents.get(nid)
            if not neighbor:
                continue

            # Use SDK observer
            result = obs.observe(agents[agent_id], neighbor)
            for action in result.visible_actions:
                # Add neighbor_id for consistency with legacy format
                action_copy = dict(action)
                action_copy["neighbor_id"] = nid
                visible_actions.append(action_copy)

        return visible_actions

    def get_social_context_v2(
        self,
        agent_id: str,
        agents: Dict[str, Any],
        observer: Optional["SocialObserver"] = None,
        max_gossip: int = 2,
    ) -> Dict[str, Any]:
        """
        Get social context using SDK SocialObserver.

        Phase 8: Uses domain-agnostic observer pattern for visible actions and gossip.

        Args:
            agent_id: The observing agent's ID
            agents: Dictionary of all agents
            observer: SDK SocialObserver instance (uses self.social_observer if None)
            max_gossip: Maximum number of gossip snippets

        Returns:
            Dict with 'gossip', 'visible_actions', 'neighbor_count', 'observable_attrs'
        """
        obs = observer or self.social_observer
        if obs is None:
            # Fallback to legacy method
            return self.get_social_context(agent_id, agents, max_gossip)

        neighbor_ids = self.graph.get_neighbors(agent_id)
        gossip = []
        visible_actions = []
        observable_attrs = {}  # Aggregated observable attributes

        for nid in neighbor_ids:
            neighbor = agents.get(nid)
            if not neighbor:
                continue

            # Use SDK observer
            result = obs.observe(agents[agent_id], neighbor)

            # Collect visible actions
            for action in result.visible_actions:
                action_copy = dict(action)
                action_copy["neighbor_id"] = nid
                visible_actions.append(action_copy)

            # Collect gossip
            if result.gossip and len(gossip) < max_gossip:
                gossip.append(f"Neighbor {nid} mentioned: '{result.gossip}'")

            # Aggregate observable attributes
            for attr, value in result.visible_attributes.items():
                if attr not in observable_attrs:
                    observable_attrs[attr] = {"count": 0, "total": 0}
                observable_attrs[attr]["total"] += 1
                if value:  # Count truthy values
                    observable_attrs[attr]["count"] += 1

        # Convert to percentages
        for attr in observable_attrs:
            total = observable_attrs[attr]["total"]
            count = observable_attrs[attr]["count"]
            observable_attrs[attr] = count / total if total > 0 else 0.0

        return {
            "gossip": gossip,
            "visible_actions": visible_actions,
            "neighbor_count": len(neighbor_ids),
            "observable_attrs": observable_attrs,
        }

    def get_environment_observation(
        self,
        agent_id: str,
        agents: Dict[str, Any],
        observer: Optional["EnvironmentObserver"] = None,
    ) -> Dict[str, Any]:
        """
        Get environment observation using SDK EnvironmentObserver.

        Phase 8: Uses domain-agnostic observer pattern for environment sensing.

        Args:
            agent_id: The observing agent's ID
            agents: Dictionary of all agents
            observer: SDK EnvironmentObserver instance (uses self.environment_observer if None)

        Returns:
            Dict with 'sensed_state', 'detected_events', 'observation_accuracy'
        """
        obs = observer or self.environment_observer
        if obs is None or self.environment is None:
            return {}

        agent = agents.get(agent_id)
        if not agent:
            return {}

        # Use SDK observer
        result = obs.observe(agent, self.environment)

        return {
            "sensed_state": result.sensed_state,
            "detected_events": result.detected_events,
            "observation_accuracy": result.observation_accuracy,
        }

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

        # 2a. Include fixed_attributes (demographics, RCV, flood zone, PMT scores)
        # These must be in `personal` for prompt template variables like
        # {rcv_building}, {income}, {flood_zone} to resolve correctly.
        if hasattr(agent, 'fixed_attributes') and isinstance(agent.fixed_attributes, dict):
            for k, v in agent.fixed_attributes.items():
                if isinstance(v, (str, int, float, bool)):
                    personal[k] = v

        # 2b. Include dynamic_state contents (Task 015 fix: ensure dynamic attributes are visible)
        # Dynamic state overwrites fixed_attributes when keys collide (intentional).
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
        # Phase 8: Use SDK observer if available
        if self.social_observer:
            social_context = self.get_social_context_v2(agent_id, agents)
        else:
            social_context = self.get_social_context(agent_id, agents)

        # Phase 8: Get environment observation via SDK if available
        env_sdk_observation = {}
        if self.environment_observer:
            env_sdk_observation = self.get_environment_observation(agent_id, agents)

        result = {
            "personal": personal,
            "local": {
                "spatial": self.get_spatial_context(agent_id, agents),
                "social": social_context.get("gossip", []) if isinstance(social_context, dict) else social_context,
                "visible_actions": social_context.get("visible_actions", []) if isinstance(social_context, dict) else [],
                "environment": env_context["local"],
                # Phase 8: SDK environment observation
                "sensed_environment": env_sdk_observation.get("sensed_state", {}),
                "detected_events": env_sdk_observation.get("detected_events", []),
            },
            "global": global_news or env_context["global"],
            "institutional": env_context["institutional"]
        }
        # Add 'state' alias for validator compatibility
        result["state"] = result["personal"]
        
        return result


