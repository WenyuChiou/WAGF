"""
Water domain pack — Protection Motivation Theory, Utility Theory, and
Financial Risk Theory frameworks for flood/irrigation agent-based models.

This pack registers three psychological frameworks and their associated
thinking-validator metadata when imported.
"""

from broker.core.psychometric import register_framework

from .pmt import PMTFramework
from .utility import UtilityFramework
from .financial import FinancialFramework


def register() -> None:
    """Register water-domain frameworks and thinking-validator metadata."""
    # Psychological frameworks
    register_framework("pmt", PMTFramework)
    register_framework("utility", UtilityFramework)
    register_framework("financial", FinancialFramework)

    # ThinkingValidator metadata (label orders, constructs, label mappings)
    from .thinking_checks import register_water_metadata
    register_water_metadata()


# Also register on import (for backward compatibility when imported directly)
register()
