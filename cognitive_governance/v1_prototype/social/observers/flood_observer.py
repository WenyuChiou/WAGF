"""Flood domain social observer."""
from typing import Any, Dict, List, Optional
from ..observer import SocialObserver


class FloodObserver(SocialObserver):
    """
    Social observer for flood adaptation domain.

    Neighbors can observe:
    - Physical changes (house elevation, flood barriers)
    - Insurance status (visible through conversations/behavior)
    - Recent flood-related actions
    """

    @property
    def domain(self) -> str:
        return "flood"

    def get_observable_attributes(self, agent: Any) -> Dict[str, Any]:
        """Return flood-relevant visible attributes."""
        attrs = {}

        # Physical characteristics (visible)
        if hasattr(agent, "house_elevated"):
            attrs["house_elevated"] = agent.house_elevated
        if hasattr(agent, "has_flood_barriers"):
            attrs["has_flood_barriers"] = agent.has_flood_barriers
        if hasattr(agent, "flood_zone"):
            attrs["flood_zone"] = agent.flood_zone

        # Insurance status (often known in communities)
        if hasattr(agent, "has_flood_insurance"):
            attrs["has_flood_insurance"] = agent.has_flood_insurance

        # Damage history (visible after floods)
        if hasattr(agent, "flood_damage_visible"):
            attrs["flood_damage_visible"] = agent.flood_damage_visible

        return attrs

    def get_visible_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """Return recent flood-related visible actions."""
        actions = []

        # Check for recent actions
        if getattr(agent, "recently_elevated", False):
            actions.append({
                "action": "elevated_house",
                "description": f"{getattr(agent, 'id', 'Agent')} elevated their house",
            })

        if getattr(agent, "recently_purchased_insurance", False):
            actions.append({
                "action": "purchased_insurance",
                "description": f"{getattr(agent, 'id', 'Agent')} purchased flood insurance",
            })

        if getattr(agent, "recently_evacuated", False):
            actions.append({
                "action": "evacuated",
                "description": f"{getattr(agent, 'id', 'Agent')} evacuated during flood warning",
            })

        return actions

    def get_gossip_content(
        self,
        agent: Any,
        memory: Optional[Any] = None
    ) -> Optional[str]:
        """Return flood-related shareable content."""
        # Check for memorable flood experiences
        if hasattr(agent, "flood_experience") and agent.flood_experience:
            return f"I remember when the flood hit in {agent.flood_experience.year}..."

        if hasattr(agent, "insurance_claim_story") and agent.insurance_claim_story:
            return agent.insurance_claim_story

        return None
