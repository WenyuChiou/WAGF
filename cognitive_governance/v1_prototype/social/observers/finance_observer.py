"""Finance domain social observer."""
from typing import Any, Dict, List, Optional
from ..observer import SocialObserver


class FinanceObserver(SocialObserver):
    """
    Social observer for financial psychology domain.

    Neighbors can observe:
    - Lifestyle indicators (car, house, visible spending)
    - Major financial events (bankruptcy, new home, new car)
    - NOT: actual income, savings, debt amounts
    """

    @property
    def domain(self) -> str:
        return "finance"

    def get_observable_attributes(self, agent: Any) -> Dict[str, Any]:
        """Return finance-relevant visible attributes."""
        attrs = {}

        # Lifestyle indicators (visible)
        if hasattr(agent, "owns_home"):
            attrs["owns_home"] = agent.owns_home
        if hasattr(agent, "car_type"):
            attrs["car_type"] = agent.car_type  # "luxury", "economy", "none"
        if hasattr(agent, "visible_spending_level"):
            attrs["visible_spending_level"] = agent.visible_spending_level

        # Employment status (often known)
        if hasattr(agent, "employment_status"):
            attrs["employed"] = agent.employment_status == "employed"

        return attrs

    def get_visible_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """Return recent finance-related visible actions."""
        actions = []

        if getattr(agent, "recently_bought_house", False):
            actions.append({
                "action": "bought_house",
                "description": f"{getattr(agent, 'id', 'Agent')} bought a new house",
            })

        if getattr(agent, "recently_bought_car", False):
            actions.append({
                "action": "bought_car",
                "description": f"{getattr(agent, 'id', 'Agent')} bought a new car",
            })

        if getattr(agent, "declared_bankruptcy", False):
            actions.append({
                "action": "bankruptcy",
                "description": f"{getattr(agent, 'id', 'Agent')} declared bankruptcy",
            })

        return actions

    def get_gossip_content(
        self,
        agent: Any,
        memory: Optional[Any] = None
    ) -> Optional[str]:
        """Return finance-related shareable content."""
        if hasattr(agent, "financial_tip") and agent.financial_tip:
            return agent.financial_tip
        return None
