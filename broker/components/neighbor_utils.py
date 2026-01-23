"""Neighbor summary utilities."""
from typing import Dict, Any, List


def get_neighbor_summary(agents: Dict[str, Any], agent_id: str) -> List[Dict[str, Any]]:
    """Get summary of neighbor agents' observable state."""
    summaries = []
    for name, agent in agents.items():
        if name != agent_id:
            summaries.append({
                "agent_name": name,
                "agent_type": getattr(agent, "agent_type", "default"),
                "state_summary": {
                    k: (round(v, 2) if isinstance(v, (int, float)) else v)
                    for k, v in list(getattr(agent, "get_all_state", lambda: {})().items())[:3]
                },
            })
    return summaries[:5]
