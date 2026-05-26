"""
Water domain pack — Protection Motivation Theory, Utility Theory, and
Financial Risk Theory frameworks for flood/irrigation agent-based models.

This pack registers three psychological frameworks and their associated
thinking-validator metadata when imported.
"""

from broker.core.psychometric import register_framework

from .pmt import PMTFramework
from .cognitive_appraisal import CognitiveAppraisalFramework
from .utility import UtilityFramework
from .financial import FinancialFramework

# Phase 6Q-D-2 (2026-05-26): re-export the flood-domain memory-strategy
# factory so callers can do `from broker.domains.water import
# create_flood_surprise_strategy` instead of the longer
# `from broker.domains.water.memory_strategies import …`. The canonical
# home is the sub-module; this is discoverability sugar.
from .memory_strategies import create_flood_surprise_strategy  # noqa: F401


def register() -> None:
    """Register water-domain frameworks and thinking-validator metadata."""
    # Psychological frameworks
    register_framework("pmt", PMTFramework)
    register_framework("cognitive_appraisal", CognitiveAppraisalFramework)
    register_framework("utility", UtilityFramework)
    register_framework("financial", FinancialFramework)

    # ThinkingValidator metadata (label orders, constructs, label mappings)
    from .thinking_checks import register_water_metadata
    register_water_metadata()

    from .social_specs import register_water_social_specs
    register_water_social_specs()


# Also register on import (for backward compatibility when imported directly)
register()
