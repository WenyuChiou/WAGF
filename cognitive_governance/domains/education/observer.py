"""
Education Domain Observers.

Re-exports EducationObserver and EducationEnvironmentObserver from SDK
with additional domain-specific utilities.
"""

from typing import Dict, List, Any

# Re-export from SDK
from cognitive_governance.v1_prototype.social import (
    EducationObserver,
    ObservationResult,
)
from cognitive_governance.v1_prototype.observation import (
    EducationEnvironmentObserver,
    EnvironmentObservation,
)


def create_education_observers() -> Dict[str, Any]:
    """
    Create both social and environment observers for education domain.

    Returns:
        Dict with 'social' and 'environment' observer instances
    """
    return {
        "social": EducationObserver(),
        "environment": EducationEnvironmentObserver(),
    }


def get_observable_education_attributes() -> List[str]:
    """
    List attributes that peers can observe in education context.

    Returns:
        List of observable attribute names
    """
    return [
        "graduated",
        "enrolled",
        "changed_major",
        "dropped_out",
        "honors",
    ]


def get_education_events() -> List[str]:
    """
    List detectable education-related events.

    Returns:
        List of event type names
    """
    return [
        "enrollment_deadline",
        "exam_period",
        "graduation_ceremony",
        "scholarship_available",
        "program_change",
    ]


__all__ = [
    # Re-exports
    "EducationObserver",
    "EducationEnvironmentObserver",
    "ObservationResult",
    "EnvironmentObservation",
    # Utilities
    "create_education_observers",
    "get_observable_education_attributes",
    "get_education_events",
]
