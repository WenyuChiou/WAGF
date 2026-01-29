"""
Social Graph Configuration by Agent Type

This module provides agent-type-specific social network configuration.
Different agent types have different social network characteristics:

- Household (NMG): Spatial radius=2, sees neighbors within 2 grid cells
- Household (MG): Spatial radius=1, smaller network due to mobility constraints
- Government: Global view, sees all agents
- Insurance: Global view of policyholders only (filtered_global)

Part of Task-043: Social Graph Configuration by Agent Type

Usage:
    from broker.components.social_graph_config import (
        get_social_spec,
        configure_social_graph_for_agent,
        AGENT_SOCIAL_SPECS,
    )

    # Get spec for an agent
    spec = get_social_spec(agent)

    # Get neighbors for an agent based on their spec
    neighbors = configure_social_graph_for_agent(graph, agent, all_agents)
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Union


class AgentLike(Protocol):
    """Protocol for agent-like objects with required attributes."""
    agent_type: str


@dataclass
class SocialGraphSpec:
    """
    Specification for an agent type's social network configuration.

    Attributes:
        graph_type: Network topology type - one of:
            - "spatial": Connects to neighbors within a radius
            - "global": Connects to all other agents
            - "filtered_global": Connects to subset of agents based on filter
            - "random": Random connections (for testing/fallback)
        radius: For spatial graph, the connection radius in grid cells.
            Default is 2 cells.
        filter_fn: For filtered_global, the name of the filter function.
            Currently supported: "has_insurance"
        max_connections: Maximum number of connections (0 = unlimited).
            Useful for limiting network size for performance.

    Examples:
        # Household NMG with radius 2
        spec = SocialGraphSpec(graph_type="spatial", radius=2)

        # Government with global view
        spec = SocialGraphSpec(graph_type="global")

        # Insurance seeing only policyholders
        spec = SocialGraphSpec(
            graph_type="filtered_global",
            filter_fn="has_insurance"
        )
    """
    graph_type: str  # "spatial", "global", "filtered_global", "random"
    radius: int = 2  # For spatial graph
    filter_fn: Optional[str] = None  # For filtered_global (e.g., "has_insurance")
    max_connections: int = 0  # 0 = unlimited

    def __post_init__(self):
        """Validate graph_type."""
        valid_types = {"spatial", "global", "filtered_global", "random"}
        if self.graph_type not in valid_types:
            raise ValueError(
                f"Invalid graph_type: {self.graph_type}. "
                f"Must be one of: {valid_types}"
            )


# Pre-defined social graph specifications by agent type
AGENT_SOCIAL_SPECS: Dict[str, SocialGraphSpec] = {
    # Household NMG (Non-Marginalized Group) - larger spatial network
    "household_nmg_owner": SocialGraphSpec(
        graph_type="spatial",
        radius=2,
    ),
    "household_nmg_renter": SocialGraphSpec(
        graph_type="spatial",
        radius=2,
    ),

    # Household MG (Marginalized Group) - smaller spatial network
    # Smaller radius represents mobility constraints
    "household_mg_owner": SocialGraphSpec(
        graph_type="spatial",
        radius=1,
    ),
    "household_mg_renter": SocialGraphSpec(
        graph_type="spatial",
        radius=1,
    ),

    # Government agent - sees all agents
    "government": SocialGraphSpec(
        graph_type="global",
    ),

    # Insurance agent - sees only policyholders
    "insurance": SocialGraphSpec(
        graph_type="filtered_global",
        filter_fn="has_insurance",
    ),
}

# Default spec for unknown agent types
DEFAULT_SOCIAL_SPEC = SocialGraphSpec(
    graph_type="spatial",
    radius=2,
)


def get_social_spec(agent: Any) -> SocialGraphSpec:
    """
    Get the appropriate SocialGraphSpec for an agent.

    The spec is determined by composing a key from agent attributes:
    - For household agents: f"household_{mg_key}_{tenure_key}"
    - For institutional agents: agent_type directly

    Args:
        agent: Agent object with agent_type, is_mg, tenure attributes.
            Can also be a dict with these keys.

    Returns:
        SocialGraphSpec appropriate for this agent type.

    Examples:
        # Agent with attributes
        class Agent:
            agent_type = "household"
            is_mg = False
            tenure = "owner"
        spec = get_social_spec(Agent())  # household_nmg_owner

        # Agent dict
        agent_dict = {"agent_type": "government"}
        spec = get_social_spec(agent_dict)  # government
    """
    # Extract attributes from agent (support both object and dict)
    if isinstance(agent, dict):
        agent_type = agent.get("agent_type", "household")
        is_mg = agent.get("is_mg", False)
        tenure = agent.get("tenure", "owner")
    else:
        agent_type = getattr(agent, "agent_type", "household")
        is_mg = getattr(agent, "is_mg", False)
        tenure = getattr(agent, "tenure", "owner")

    # Normalize agent_type
    agent_type_lower = agent_type.lower() if agent_type else "household"

    # Check for institutional agent types first
    if agent_type_lower in AGENT_SOCIAL_SPECS:
        return AGENT_SOCIAL_SPECS[agent_type_lower]

    # For household agents, compose the key
    if agent_type_lower in ("household", "household_owner", "household_renter"):
        mg_key = "mg" if is_mg else "nmg"
        tenure_key = _normalize_tenure(tenure)
        composed_key = f"household_{mg_key}_{tenure_key}"

        if composed_key in AGENT_SOCIAL_SPECS:
            return AGENT_SOCIAL_SPECS[composed_key]

    # Fallback to default
    return DEFAULT_SOCIAL_SPEC


def _normalize_tenure(tenure: Any) -> str:
    """
    Normalize tenure value to 'owner' or 'renter'.

    Args:
        tenure: Tenure value (string, bool, or other)

    Returns:
        "owner" or "renter"
    """
    if tenure is None:
        return "owner"

    tenure_str = str(tenure).lower()

    if tenure_str in ("owner", "own", "o", "1", "true"):
        return "owner"
    elif tenure_str in ("renter", "rent", "r", "0", "false"):
        return "renter"
    else:
        # Default to owner for unknown values
        return "owner"


def configure_social_graph_for_agent(
    graph: Any,
    agent: Any,
    all_agents: Union[List[Any], Dict[str, Any]],
) -> List[str]:
    """
    Get list of neighbor agent IDs for an agent based on their social spec.

    This function applies the agent's SocialGraphSpec to determine which
    other agents they can see/interact with.

    Args:
        graph: SocialGraph instance (e.g., SpatialNeighborhoodGraph).
            Must have get_neighbors() or get_neighbors_within_radius() method.
        agent: The agent to get neighbors for.
        all_agents: All agents in the simulation (list or dict).

    Returns:
        List of neighbor agent IDs that this agent can see.

    Examples:
        # Spatial graph for household
        neighbors = configure_social_graph_for_agent(
            graph=spatial_graph,
            agent=household_agent,
            all_agents={"H1": agent1, "H2": agent2, "H3": agent3}
        )

        # Global graph for government
        neighbors = configure_social_graph_for_agent(
            graph=global_graph,
            agent=government_agent,
            all_agents=all_agent_dict
        )
    """
    spec = get_social_spec(agent)

    # Get agent ID
    if isinstance(agent, dict):
        agent_id = agent.get("id", agent.get("agent_id", ""))
    else:
        agent_id = getattr(agent, "id", getattr(agent, "agent_id", ""))

    # Convert all_agents to dict if it's a list
    if isinstance(all_agents, list):
        agents_dict = {}
        for a in all_agents:
            if isinstance(a, dict):
                a_id = a.get("id", a.get("agent_id", ""))
            else:
                a_id = getattr(a, "id", getattr(a, "agent_id", ""))
            if a_id:
                agents_dict[a_id] = a
    else:
        agents_dict = all_agents

    # Apply graph type logic
    if spec.graph_type == "spatial":
        return _get_spatial_neighbors(graph, agent_id, spec)

    elif spec.graph_type == "global":
        return _get_global_neighbors(agent_id, agents_dict)

    elif spec.graph_type == "filtered_global":
        return _get_filtered_neighbors(agent_id, agents_dict, spec.filter_fn)

    elif spec.graph_type == "random":
        # For random, just use the graph's existing connections
        if hasattr(graph, "get_neighbors"):
            neighbors = graph.get_neighbors(agent_id)
        else:
            neighbors = []
        return _apply_max_connections(neighbors, spec.max_connections)

    else:
        return []


def _get_spatial_neighbors(
    graph: Any,
    agent_id: str,
    spec: SocialGraphSpec,
) -> List[str]:
    """
    Get neighbors within spatial radius.

    Uses get_neighbors_within_radius if available, otherwise get_neighbors.
    """
    neighbors = []

    # Try get_neighbors_within_radius first (for SpatialNeighborhoodGraph)
    if hasattr(graph, "get_neighbors_within_radius"):
        neighbors = graph.get_neighbors_within_radius(agent_id, spec.radius)
    elif hasattr(graph, "get_neighbors"):
        neighbors = graph.get_neighbors(agent_id)
    else:
        neighbors = []

    return _apply_max_connections(neighbors, spec.max_connections)


def _get_global_neighbors(
    agent_id: str,
    agents_dict: Dict[str, Any],
) -> List[str]:
    """Get all other agents (global view)."""
    return [a_id for a_id in agents_dict.keys() if a_id != agent_id]


def _get_filtered_neighbors(
    agent_id: str,
    agents_dict: Dict[str, Any],
    filter_fn: Optional[str],
) -> List[str]:
    """
    Get neighbors filtered by a condition.

    Currently supported filter functions:
    - "has_insurance": Only includes agents with has_insurance=True
    """
    neighbors = []

    for a_id, agent in agents_dict.items():
        if a_id == agent_id:
            continue

        # Apply filter
        if filter_fn == "has_insurance":
            has_insurance = _get_agent_attr(agent, "has_insurance", False)
            if has_insurance:
                neighbors.append(a_id)
        else:
            # No filter or unknown filter - include all
            neighbors.append(a_id)

    return neighbors


def _get_agent_attr(agent: Any, attr: str, default: Any = None) -> Any:
    """Get attribute from agent (object or dict)."""
    if isinstance(agent, dict):
        # Check direct key
        if attr in agent:
            return agent[attr]
        # Check dynamic_state for household agents
        if "dynamic_state" in agent and isinstance(agent["dynamic_state"], dict):
            return agent["dynamic_state"].get(attr, default)
        # Check state dict
        if "state" in agent and isinstance(agent["state"], dict):
            return agent["state"].get(attr, default)
        return default
    else:
        # Try direct attribute
        if hasattr(agent, attr):
            return getattr(agent, attr)
        # Try dynamic_state
        if hasattr(agent, "dynamic_state"):
            dyn = getattr(agent, "dynamic_state", {})
            if isinstance(dyn, dict):
                return dyn.get(attr, default)
        # Try get_state method
        if hasattr(agent, "get_state"):
            try:
                return agent.get_state(attr, default)
            except (TypeError, AttributeError):
                pass
        return default


def _apply_max_connections(
    neighbors: List[str],
    max_connections: int,
) -> List[str]:
    """Apply max_connections limit if set."""
    if max_connections > 0 and len(neighbors) > max_connections:
        return neighbors[:max_connections]
    return neighbors


def get_spec_for_type_key(type_key: str) -> Optional[SocialGraphSpec]:
    """
    Get SocialGraphSpec by type key directly.

    Useful for testing or when you already have the composed key.

    Args:
        type_key: Composed type key (e.g., "household_nmg_owner", "government")

    Returns:
        SocialGraphSpec if found, None otherwise
    """
    return AGENT_SOCIAL_SPECS.get(type_key)


def list_all_type_keys() -> List[str]:
    """Get list of all defined type keys."""
    return list(AGENT_SOCIAL_SPECS.keys())
