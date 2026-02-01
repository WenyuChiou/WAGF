"""
Flood domain governance validators.

Provides BuiltinCheck functions for the flood domain that enforce
physical state preconditions (elevation, relocation, tenure),
financial affordability, social pressure awareness, and semantic
grounding (hallucination detection).

These checks are injected into the framework's generic validators via
the ``builtin_checks`` constructor parameter, following the same pattern
as irrigation-domain checks in ``examples/irrigation_abm/validators/``.

Extracted from broker/validators/governance/ as part of the Phase 6
generalization — broker/ core is now domain-agnostic.
"""

import re
from typing import Any, Dict, List

from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule


# =============================================================================
# Physical checks — state preconditions and immutability
# =============================================================================

def flood_already_elevated(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block elevation if house is already elevated."""
    if skill_name != "elevate_house":
        return []
    state = context.get("state", {})
    if not state.get("elevated", False):
        return []
    return [ValidationResult(
        valid=False,
        validator_name="PhysicalValidator",
        errors=["House is already elevated - cannot elevate again"],
        warnings=[],
        metadata={
            "rule_id": "builtin_already_elevated",
            "category": "physical",
            "subcategory": "state",
            "hallucination_type": "physical",
            "current_state": "elevated"
        }
    )]


def flood_already_relocated(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block property actions after relocation."""
    state = context.get("state", {})
    if not state.get("relocated", False):
        return []
    restricted_after_relocation = {
        "relocate", "elevate_house", "buy_insurance", "buyout"
    }
    if skill_name not in restricted_after_relocation:
        return []
    return [ValidationResult(
        valid=False,
        validator_name="PhysicalValidator",
        errors=[f"Household has relocated - '{skill_name}' is no longer applicable"],
        warnings=[],
        metadata={
            "rule_id": "builtin_already_relocated",
            "category": "physical",
            "subcategory": "state",
            "hallucination_type": "physical",
            "current_state": "relocated"
        }
    )]


def flood_renter_restriction(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block property modifications for renters."""
    state = context.get("state", {})
    is_renter = state.get("tenure", "Owner").lower() == "renter"
    if not is_renter:
        return []
    owner_only_actions = {"elevate_house", "buyout"}
    if skill_name not in owner_only_actions:
        return []
    return [ValidationResult(
        valid=False,
        validator_name="PhysicalValidator",
        errors=[f"Renters cannot perform '{skill_name}' - property modification requires ownership"],
        warnings=[],
        metadata={
            "rule_id": "builtin_renter_restriction",
            "category": "physical",
            "subcategory": "state",
            "tenure": "renter",
            "restricted_action": skill_name
        }
    )]


# =============================================================================
# Personal checks — financial affordability
# =============================================================================

def flood_elevation_affordability(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Check if agent can afford house elevation.

    Only fires for ``elevate_house`` and when no explicit YAML rule
    with id prefix ``elevation_affordability`` exists.
    """
    if skill_name != "elevate_house":
        return []

    # Skip if an explicit YAML rule already covers this
    if any(r.id.startswith("elevation_affordability") for r in rules if r.category == "personal"):
        return []

    state = context.get("state", {})
    savings = state.get("savings", 0)
    elevation_cost = state.get("elevation_cost", 50000)
    subsidy_rate = state.get("subsidy_rate", 0.0)
    effective_cost = elevation_cost * (1 - subsidy_rate)

    if savings < effective_cost:
        return [ValidationResult(
            valid=False,
            validator_name="PersonalValidator",
            errors=[f"Insufficient funds: savings ${savings:.0f} < cost ${effective_cost:.0f}"],
            warnings=[],
            metadata={
                "rule_id": "builtin_elevation_affordability",
                "category": "personal",
                "subcategory": "financial",
                "savings": savings,
                "effective_cost": effective_cost
            }
        )]

    return []


# =============================================================================
# Social checks — neighbor influence awareness
# =============================================================================

def flood_majority_deviation(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Warn if agent deviates from majority neighbor adaptation.

    Fires when > 50% neighbors have elevated but agent chooses do_nothing.
    Always WARNING (valid=True).
    """
    if skill_name != "do_nothing":
        return []
    social_context = context.get("social_context", {})
    elevated_pct = social_context.get("elevated_neighbor_pct", 0)
    if elevated_pct <= 0.5:
        return []
    return [ValidationResult(
        valid=True,
        validator_name="SocialValidator",
        errors=[],
        warnings=[f"Social observation: {elevated_pct*100:.0f}% of neighbors have elevated"],
        metadata={
            "rule_id": "builtin_majority_deviation",
            "category": "social",
            "subcategory": "neighbor",
            "elevated_neighbor_pct": elevated_pct,
            "level": "WARNING"
        }
    )]


# =============================================================================
# Aggregated check lists
# =============================================================================

FLOOD_PHYSICAL_CHECKS = [
    flood_already_elevated,
    flood_already_relocated,
    flood_renter_restriction,
]

FLOOD_PERSONAL_CHECKS = [
    flood_elevation_affordability,
]

FLOOD_SOCIAL_CHECKS = [
    flood_majority_deviation,
]


# =============================================================================
# Semantic checks — hallucination detection
# =============================================================================

def flood_social_proof_hallucination(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Flag when agent reasoning cites social influence but has no neighbors.

    Detects "Hallucinated Consensus" — the agent invents social proof
    (e.g., "my neighbors are elevating") to justify a decision, despite
    being isolated with 0 neighbors in the simulation.
    """
    reasoning = context.get("reasoning", {})
    reasoning_text = str(reasoning).lower()

    social_keywords = [
        "neighbor", "community", "everyone", "others",
        "block", "street", "friends", "people around",
    ]
    has_social_reasoning = any(kw in reasoning_text for kw in social_keywords)
    if not has_social_reasoning:
        return []

    # Check for isolation in spatial context
    local_ctx = context.get("local", {})
    spatial_info = local_ctx.get("spatial", "")
    if isinstance(spatial_info, list):
        spatial_info = " ".join(str(x) for x in spatial_info)
    spatial_text = str(spatial_info).lower()

    is_isolated = (
        "0 neighbors" in spatial_text
        or "no neighbors" in spatial_text
        or "alone" in spatial_text
    )

    if not is_isolated:
        return []

    return [ValidationResult(
        valid=False,
        validator_name="SemanticGroundingValidator",
        errors=[
            "Hallucinated Social Proof: reasoning cites social influence "
            "but context confirms 0 neighbors."
        ],
        warnings=[],
        metadata={
            "rule_id": "semantic_social_hallucination",
            "category": "semantic",
            "subcategory": "social_proof",
            "hallucination_type": "semantic",
        },
    )]


def flood_temporal_grounding(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Warn when reasoning references a flood event that did not occur.

    Checks whether the agent's reasoning text claims a recent flood
    (e.g., "after last year's flood", "the flood this year") when the
    environment context shows no flood event.
    """
    reasoning = context.get("reasoning", {})
    reasoning_text = str(reasoning).lower()

    # Keywords indicating agent believes a flood occurred
    flood_ref_patterns = [
        r"last year'?s? flood",
        r"recent flood",
        r"flood(ed|ing)?\s+(this|last)\s+year",
        r"after the flood",
        r"damage from the flood",
        r"flood hit",
        r"we were flooded",
        r"got flooded",
    ]
    has_flood_reference = any(
        re.search(pat, reasoning_text) for pat in flood_ref_patterns
    )
    if not has_flood_reference:
        return []

    # Check ground truth: did a flood actually occur?
    env_state = context.get("env_state", {})
    flood_event = env_state.get("flood_event", None)

    # Also check flattened context (backward compat)
    if flood_event is None:
        flood_event = context.get("flood_event", None)

    # If we can't determine flood status, don't flag
    if flood_event is None:
        return []

    if flood_event:
        return []  # Flood did occur — reference is grounded

    return [ValidationResult(
        valid=True,  # WARNING only — temporal mismatch is suspicious but not blocking
        validator_name="SemanticGroundingValidator",
        errors=[],
        warnings=[
            "Temporal grounding concern: reasoning references a flood event "
            "but no flood occurred this year."
        ],
        metadata={
            "rule_id": "semantic_temporal_grounding",
            "category": "semantic",
            "subcategory": "temporal",
            "hallucination_type": "semantic",
        },
    )]


def flood_state_consistency(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Warn when reasoning text contradicts agent's known state.

    Checks for inconsistencies such as:
    - Agent claims to be insured when has_insurance=False
    - Agent claims house is elevated when elevated=False
    - Agent claims to have relocated when relocated=False
    """
    reasoning = context.get("reasoning", {})
    reasoning_text = str(reasoning).lower()
    state = context.get("state", {})
    results = []

    # Check: claims insured when not
    if not state.get("has_insurance", False):
        insured_claims = [
            "my insurance", "i have insurance", "i'm insured",
            "already insured", "covered by insurance", "insurance policy",
            "my policy", "as an insured",
        ]
        if any(claim in reasoning_text for claim in insured_claims):
            results.append(ValidationResult(
                valid=True,  # WARNING — state mismatch
                validator_name="SemanticGroundingValidator",
                errors=[],
                warnings=[
                    "State consistency concern: reasoning claims insurance "
                    "coverage but has_insurance=False."
                ],
                metadata={
                    "rule_id": "semantic_state_insurance",
                    "category": "semantic",
                    "subcategory": "state_consistency",
                    "hallucination_type": "semantic",
                    "claimed_state": "has_insurance=True",
                    "actual_state": "has_insurance=False",
                },
            ))

    # Check: claims elevated when not
    if not state.get("elevated", False):
        elevated_claims = [
            "my elevated home", "house is elevated", "already elevated",
            "i elevated", "since elevating", "my elevation",
        ]
        if any(claim in reasoning_text for claim in elevated_claims):
            results.append(ValidationResult(
                valid=True,  # WARNING
                validator_name="SemanticGroundingValidator",
                errors=[],
                warnings=[
                    "State consistency concern: reasoning claims house is "
                    "elevated but elevated=False."
                ],
                metadata={
                    "rule_id": "semantic_state_elevation",
                    "category": "semantic",
                    "subcategory": "state_consistency",
                    "hallucination_type": "semantic",
                    "claimed_state": "elevated=True",
                    "actual_state": "elevated=False",
                },
            ))

    return results


# =============================================================================
# Social utility — flood-specific social pressure calculation
# =============================================================================

def calculate_social_pressure(social_context: Dict[str, Any]) -> float:
    """Calculate social pressure score (0-1) based on neighbor flood actions.

    Uses ``elevated_neighbors`` and ``relocated_neighbors`` keys.
    Weighted: relocation counts more than elevation.
    """
    elevated = social_context.get("elevated_neighbors", 0)
    relocated = social_context.get("relocated_neighbors", 0)
    total = social_context.get("neighbor_count", 1)

    if total == 0:
        return 0.0

    return min(1.0, (elevated + relocated * 1.5) / total)


# =============================================================================
# Aggregated check lists
# =============================================================================

FLOOD_SEMANTIC_CHECKS = [
    flood_social_proof_hallucination,
    flood_temporal_grounding,
    flood_state_consistency,
]

ALL_FLOOD_CHECKS = (
    FLOOD_PHYSICAL_CHECKS + FLOOD_PERSONAL_CHECKS
    + FLOOD_SOCIAL_CHECKS + FLOOD_SEMANTIC_CHECKS
)
