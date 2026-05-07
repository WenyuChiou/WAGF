"""Flood-domain governance validators."""
from .flood_validators import (
    FLOOD_PHYSICAL_CHECKS,
    FLOOD_PERSONAL_CHECKS,
    FLOOD_SOCIAL_CHECKS,
    FLOOD_SEMANTIC_CHECKS,
    ALL_FLOOD_CHECKS,
    flood_already_elevated,
    flood_already_relocated,
    flood_renter_restriction,
    flood_elevation_affordability,
    flood_majority_deviation,
    flood_social_proof_hallucination,
    flood_temporal_grounding,
    flood_state_consistency,
    calculate_social_pressure,
)

# Phase 6B-1: register checks with the broker's plugin registry so
# `validator_bundles.build_domain_validators("flood")` no longer needs
# to import from this example package directly.
try:
    from broker.components.governance.validator_registry import ValidatorRegistry
    ValidatorRegistry.register("flood", "physical", list(FLOOD_PHYSICAL_CHECKS))
    ValidatorRegistry.register("flood", "personal", list(FLOOD_PERSONAL_CHECKS))
    ValidatorRegistry.register("flood", "social", list(FLOOD_SOCIAL_CHECKS))
    ValidatorRegistry.register("flood", "semantic", list(FLOOD_SEMANTIC_CHECKS))
except ImportError:
    pass
