"""
Flood Domain Observers.

Re-exports FloodObserver and FloodEnvironmentObserver from SDK
with additional domain-specific utilities.
"""

from typing import Dict, List, Any

# Re-export from SDK
from cognitive_governance.v1_prototype.social import (
    FloodObserver,
    ObservationResult,
)
from cognitive_governance.v1_prototype.observation import (
    FloodEnvironmentObserver,
    EnvironmentObservation,
)


def create_flood_observers() -> Dict[str, Any]:
    """
    Create both social and environment observers for flood domain.

    Returns:
        Dict with 'social' and 'environment' observer instances
    """
    return {
        "social": FloodObserver(),
        "environment": FloodEnvironmentObserver(),
    }


def get_observable_flood_attributes() -> List[str]:
    """
    List attributes that neighbors can observe in flood context.

    Returns:
        List of observable attribute names
    """
    return [
        "elevated",
        "has_flood_insurance",
        "relocated",
        "has_flood_damage",
    ]


def get_flood_events() -> List[str]:
    """
    List detectable flood-related events.

    Returns:
        List of event type names
    """
    return [
        "flood_active",
        "flood_warning",
        "evacuation_order",
        "infrastructure_damage",
        "insurance_claim",
    ]


__all__ = [
    # Re-exports
    "FloodObserver",
    "FloodEnvironmentObserver",
    "ObservationResult",
    "EnvironmentObservation",
    # Utilities
    "create_flood_observers",
    "get_observable_flood_attributes",
    "get_flood_events",
]
