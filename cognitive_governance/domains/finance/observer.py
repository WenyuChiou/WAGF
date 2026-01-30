"""
Finance Domain Observers.

Re-exports FinanceObserver and FinanceEnvironmentObserver from SDK
with additional domain-specific utilities.
"""

from typing import Dict, List, Any

# Re-export from SDK
from cognitive_governance.v1_prototype.social import (
    FinanceObserver,
    ObservationResult,
)
from cognitive_governance.v1_prototype.observation import (
    FinanceEnvironmentObserver,
    EnvironmentObservation,
)


def create_finance_observers() -> Dict[str, Any]:
    """
    Create both social and environment observers for finance domain.

    Returns:
        Dict with 'social' and 'environment' observer instances
    """
    return {
        "social": FinanceObserver(),
        "environment": FinanceEnvironmentObserver(),
    }


def get_observable_finance_attributes() -> List[str]:
    """
    List attributes that peers can observe in finance context.

    Returns:
        List of observable attribute names
    """
    return [
        "major_purchase",
        "bankruptcy",
        "new_car",
        "home_purchase",
        "visible_wealth",
    ]


def get_finance_events() -> List[str]:
    """
    List detectable finance-related events.

    Returns:
        List of event type names
    """
    return [
        "market_crash",
        "recession",
        "interest_rate_change",
        "inflation_spike",
        "market_rally",
    ]


__all__ = [
    # Re-exports
    "FinanceObserver",
    "FinanceEnvironmentObserver",
    "ObservationResult",
    "EnvironmentObservation",
    # Utilities
    "create_finance_observers",
    "get_observable_finance_attributes",
    "get_finance_events",
]
