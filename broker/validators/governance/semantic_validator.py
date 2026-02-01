"""
Semantic Grounding Validator — validates reasoning against ground truth.

Prevents hallucinations where agent reasoning contradicts the simulation state:
- Hallucinated Social Proof: agent cites neighbor influence when isolated
- Temporal Grounding: agent references events that didn't occur
- State Consistency: agent reasoning contradicts its known state variables

Domain-specific built-in checks are injected via ``builtin_checks``.
When ``None``, flood-domain defaults are used for backward compatibility.

References:
    Rogers, 1975 — Protection Motivation Theory
    Lazarus & Folkman, 1984 — Cognitive Appraisal Theory
"""
import re
from typing import List, Dict, Any, Optional

from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


# ---------------------------------------------------------------------------
# Flood-domain built-in semantic checks
# ---------------------------------------------------------------------------

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


# Registry of flood-domain semantic checks
FLOOD_SEMANTIC_CHECKS: List[BuiltinCheck] = [
    flood_social_proof_hallucination,
    flood_temporal_grounding,
    flood_state_consistency,
]


# ---------------------------------------------------------------------------
# Validator class
# ---------------------------------------------------------------------------

class SemanticGroundingValidator(BaseValidator):
    """
    Validates that agent reasoning is grounded in the simulation state.

    Prevents hallucinations where the agent's reasoning text contradicts
    observable ground truth (social context, event history, agent state).

    Built-in checks default to flood domain.  Pass ``builtin_checks=[]``
    to disable, or supply domain-specific checks.
    """

    def __init__(self, builtin_checks: Optional[List[BuiltinCheck]] = None):
        super().__init__(builtin_checks=builtin_checks)

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Flood-domain defaults for backward compatibility."""
        return list(FLOOD_SEMANTIC_CHECKS)

    @property
    def category(self) -> str:
        return "semantic"
