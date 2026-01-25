"""Health domain environment observer implementation."""
from typing import Any, Dict, List
from ..environment import EnvironmentObserver


class HealthEnvironmentObserver(EnvironmentObserver):
    """Environment observer for health behavior domain."""

    @property
    def domain(self) -> str:
        return "health"

    def sense_state(self, agent: Any, environment: Any) -> Dict[str, Any]:
        """Sense health-related environment state."""
        state = {}

        # Healthcare access
        if hasattr(environment, "healthcare_access"):
            state["healthcare_access"] = environment.healthcare_access
        elif hasattr(environment, "get_healthcare_access"):
            location = getattr(agent, "location", None)
            state["healthcare_access"] = environment.get_healthcare_access(location)

        # Gym/fitness facility availability
        if hasattr(environment, "fitness_facilities"):
            state["fitness_facilities"] = environment.fitness_facilities

        # Food environment
        if hasattr(environment, "healthy_food_access"):
            state["healthy_food_access"] = environment.healthy_food_access

        # Air quality
        if hasattr(environment, "air_quality_index"):
            state["air_quality"] = environment.air_quality_index

        # Public health campaign active
        if hasattr(environment, "health_campaign_active"):
            state["health_campaign"] = environment.health_campaign_active

        # Smoking ban in effect
        if hasattr(environment, "smoking_ban"):
            state["smoking_ban"] = environment.smoking_ban

        return state

    def detect_events(self, agent: Any, environment: Any) -> List[Dict[str, Any]]:
        """Detect health-related events in environment."""
        events = []

        # Disease outbreak
        if getattr(environment, "disease_outbreak", False):
            disease = getattr(environment, "outbreak_disease", "unknown")
            events.append({
                "event_type": "disease_outbreak",
                "description": f"Health alert: {disease} outbreak reported",
                "severity": "high",
            })

        # New health policy
        if getattr(environment, "new_health_policy", False):
            events.append({
                "event_type": "health_policy",
                "description": "New public health policy announced",
            })

        # Vaccination campaign
        if getattr(environment, "vaccination_campaign", False):
            events.append({
                "event_type": "vaccination_campaign",
                "description": "Vaccination campaign underway",
            })

        # Fitness facility opened
        if getattr(environment, "new_fitness_facility", False):
            events.append({
                "event_type": "fitness_facility_opened",
                "description": "New fitness facility opened nearby",
            })

        return events

    def get_observation_accuracy(self, agent: Any, variable: str) -> float:
        """Get observation accuracy for health variables."""
        base_accuracy = 0.8

        # Health literacy improves accuracy
        health_literacy = getattr(agent, "health_literacy", 0.5)
        if health_literacy > 0.7:
            base_accuracy = 0.9

        # Healthcare access improves information accuracy
        if getattr(agent, "has_regular_doctor", False):
            base_accuracy = min(base_accuracy + 0.05, 1.0)

        return base_accuracy
