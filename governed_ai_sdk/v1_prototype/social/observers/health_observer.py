"""Health domain social observer implementation."""
from typing import Any, Dict, List, Optional
from ..observer import SocialObserver, ObservationResult


class HealthObserver(SocialObserver):
    """Social observer for health behavior domain."""

    @property
    def domain(self) -> str:
        return "health"

    def get_observable_attributes(self, agent: Any) -> Dict[str, bool]:
        """Get observable health-related attributes."""
        return {
            "exercises_regularly": getattr(agent, "activity_level", "sedentary") in [
                "moderately_active",
                "very_active",
            ],
            "healthy_diet": getattr(agent, "diet_quality", "mixed_diet") == "healthy_diet",
            "non_smoker": getattr(agent, "smoking_status", "non_smoker") in [
                "non_smoker",
                "former_smoker",
            ],
            "appears_healthy": getattr(agent, "bmi", 25) < 30,
        }

    def get_visible_actions(self, observer: Any, observed: Any) -> List[Dict[str, Any]]:
        """Get visible health behavior changes."""
        actions = []

        # Joined gym / started exercising
        if getattr(observed, "started_exercising", False):
            actions.append({
                "action": "started_exercising",
                "description": f"{getattr(observed, 'id', 'neighbor')} started exercising regularly",
            })

        # Quit smoking
        if getattr(observed, "quit_smoking", False):
            actions.append({
                "action": "quit_smoking",
                "description": f"{getattr(observed, 'id', 'neighbor')} quit smoking",
            })

        # Changed diet
        if getattr(observed, "improved_diet", False):
            actions.append({
                "action": "improved_diet",
                "description": f"{getattr(observed, 'id', 'neighbor')} improved their diet",
            })

        # Weight loss
        if getattr(observed, "weight_loss", False):
            actions.append({
                "action": "weight_loss",
                "description": f"{getattr(observed, 'id', 'neighbor')} lost weight",
            })

        return actions

    def get_gossip_content(self, observer: Any, observed: Any, memory: Any = None) -> Optional[str]:
        """Generate health-related gossip."""
        activity = getattr(observed, "activity_level", None)
        smoking = getattr(observed, "smoking_status", None)

        if activity == "very_active":
            return "They exercise every day and look great!"
        elif smoking == "trying_to_quit":
            return "They're trying to quit smoking."
        elif getattr(observed, "weight_loss", False):
            return "They've lost a lot of weight recently."

        return None
