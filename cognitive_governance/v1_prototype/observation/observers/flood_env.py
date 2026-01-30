"""Flood domain environment observer."""
from typing import Any, Dict, List, Optional
from ..environment import EnvironmentObserver


class FloodEnvironmentObserver(EnvironmentObserver):
    """
    Environment observer for flood adaptation domain.

    Agents can sense:
    - Current flood conditions (water level, warnings)
    - Recent flood history
    - Local infrastructure status
    - Weather forecasts (with uncertainty)
    """

    @property
    def domain(self) -> str:
        return "flood"

    def sense_state(
        self,
        agent: Any,
        environment: Any
    ) -> Dict[str, Any]:
        """Sense flood-relevant environment state."""
        sensed = {}

        # Current flood level (if environment provides it)
        if hasattr(environment, "get_flood_level"):
            location = getattr(agent, "location", None)
            sensed["current_flood_level"] = environment.get_flood_level(location)
        elif hasattr(environment, "flood_level"):
            sensed["current_flood_level"] = environment.flood_level

        # Flood warning status
        if hasattr(environment, "flood_warning_active"):
            sensed["flood_warning"] = environment.flood_warning_active
        elif hasattr(environment, "warning_level"):
            sensed["warning_level"] = environment.warning_level

        # Days since last major flood
        if hasattr(environment, "days_since_flood"):
            sensed["days_since_last_flood"] = environment.days_since_flood

        # Flood zone designation
        if hasattr(environment, "get_flood_zone"):
            location = getattr(agent, "location", None)
            sensed["flood_zone"] = environment.get_flood_zone(location)

        # Sea level / river level
        if hasattr(environment, "sea_level"):
            sensed["sea_level"] = environment.sea_level

        # Current year/time (for temporal context)
        if hasattr(environment, "current_year"):
            sensed["current_year"] = environment.current_year
        if hasattr(environment, "current_tick"):
            sensed["current_tick"] = environment.current_tick

        return sensed

    def detect_events(
        self,
        agent: Any,
        environment: Any
    ) -> List[Dict[str, Any]]:
        """Detect flood-related events."""
        events = []

        # Check for active flood
        if hasattr(environment, "is_flooding") and environment.is_flooding:
            severity = getattr(environment, "flood_severity", "moderate")
            events.append({
                "event_type": "flood_active",
                "description": f"Active flood with {severity} severity",
                "severity": severity,
            })

        # Check for new warning
        if hasattr(environment, "new_warning_issued") and environment.new_warning_issued:
            events.append({
                "event_type": "flood_warning",
                "description": "New flood warning issued",
                "severity": "high",
            })

        # Check for evacuation order
        if hasattr(environment, "evacuation_ordered") and environment.evacuation_ordered:
            events.append({
                "event_type": "evacuation_order",
                "description": "Mandatory evacuation ordered",
                "severity": "critical",
            })

        # Check for infrastructure damage
        if hasattr(environment, "infrastructure_damaged") and environment.infrastructure_damaged:
            events.append({
                "event_type": "infrastructure_damage",
                "description": "Local infrastructure damaged by flooding",
                "severity": "high",
            })

        return events

    def get_observation_accuracy(
        self,
        agent: Any,
        variable: str
    ) -> float:
        """
        Get accuracy based on agent's information access.

        Agents with better information access (e.g., flood insurance,
        community connections) have more accurate observations.
        """
        base_accuracy = 0.8

        # Better accuracy if agent has flood insurance (more engaged)
        if getattr(agent, "has_flood_insurance", False):
            base_accuracy += 0.1

        # Better accuracy if agent has experienced floods
        if getattr(agent, "flood_experience", None):
            base_accuracy += 0.1

        return min(base_accuracy, 1.0)
