"""Irrigation-specific validators for the Water Agent Governance Framework."""

from .irrigation_validators import (
    water_right_cap_check,
    non_negative_diversion_check,
    curtailment_awareness_check,
    compact_allocation_check,
    drought_severity_check,
    magnitude_cap_check,
    demand_ceiling_stabilizer,
    irrigation_governance_validator,
    IRRIGATION_PHYSICAL_CHECKS,
    IRRIGATION_SOCIAL_CHECKS,
    ALL_IRRIGATION_CHECKS,
)

__all__ = [
    "water_right_cap_check",
    "non_negative_diversion_check",
    "curtailment_awareness_check",
    "compact_allocation_check",
    "drought_severity_check",
    "magnitude_cap_check",
    "demand_ceiling_stabilizer",
    "irrigation_governance_validator",
    "IRRIGATION_PHYSICAL_CHECKS",
    "IRRIGATION_SOCIAL_CHECKS",
    "ALL_IRRIGATION_CHECKS",
]

# Phase 6B-1: register checks with the broker's plugin registry so
# `validator_bundles.build_domain_validators("irrigation")` no longer
# needs to import from this example package directly.
try:
    from broker.components.governance.validator_registry import ValidatorRegistry
    ValidatorRegistry.register("irrigation", "physical", list(IRRIGATION_PHYSICAL_CHECKS))
    ValidatorRegistry.register("irrigation", "social", list(IRRIGATION_SOCIAL_CHECKS))
except ImportError:
    # Broker not available (rare; e.g., reading this module standalone) — skip.
    pass
