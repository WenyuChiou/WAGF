"""
Health Domain Observers.

Re-exports HealthObserver and HealthEnvironmentObserver from SDK
with additional domain-specific utilities.
"""

from typing import Dict, List, Any

# Re-export from SDK
from cognitive_governance.v1_prototype.social import (
    HealthObserver,
    ObservationResult,
)
from cognitive_governance.v1_prototype.observation import (
    HealthEnvironmentObserver,
    EnvironmentObservation,
)


def create_health_observers() -> Dict[str, Any]:
    """
    Create both social and environment observers for health domain.

    Returns:
        Dict with 'social' and 'environment' observer instances
    """
    return {
        "social": HealthObserver(),
        "environment": HealthEnvironmentObserver(),
    }


def get_observable_health_attributes() -> List[str]:
    """
    List attributes that peers can observe in health context.

    Returns:
        List of observable attribute names
    """
    return [
        "exercises_regularly",
        "healthy_diet",
        "non_smoker",
        "appears_healthy",
        "weight_loss",
    ]


def get_health_events() -> List[str]:
    """
    List detectable health-related events.

    Returns:
        List of event type names
    """
    return [
        "disease_outbreak",
        "health_policy",
        "vaccination_campaign",
        "fitness_facility_opened",
        "health_campaign",
    ]


__all__ = [
    # Re-exports
    "HealthObserver",
    "HealthEnvironmentObserver",
    "ObservationResult",
    "EnvironmentObservation",
    # Utilities
    "create_health_observers",
    "get_observable_health_attributes",
    "get_health_events",
]
