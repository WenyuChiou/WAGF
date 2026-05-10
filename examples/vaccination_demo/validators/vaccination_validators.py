"""
Vaccination domain validator checks.

Phase 6C-v3 reference: every check below is a ``BuiltinCheck`` callable
matching the signature ``(skill_name, rules, context) -> List[ValidationResult]``.
They are registered with :class:`ValidatorRegistry` in this package's
``__init__.py`` so the broker's :func:`validate_all` picks them up at
runtime — no edits to broker/ source code.

Each check sets ``metadata['category']`` so that the audit CSV's
``rules_*_hit`` columns (Phase 6C W8 fix) get populated correctly on
rejection.
"""
from __future__ import annotations

from typing import Any, Dict, List

from broker.governance.rule_types import GovernanceRule
from broker.interfaces.skill_types import ValidationResult


# ─────────────────────────────────────────────────────────────────────
# PHYSICAL — state-precondition / immutability rules
# ─────────────────────────────────────────────────────────────────────

def vaccination_recent_dose_no_revaccinate(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Block ``get_vaccinated`` if the agent received a dose within 26 weeks.

    Standard public-health guidance is one seasonal dose per cycle.
    Re-vaccination inside that window is wasteful and rarely recommended.
    """
    if skill_name != "get_vaccinated":
        return []
    weeks_since = (
        context.get("weeks_since_dose")
        if context.get("weeks_since_dose") is not None
        else context.get("agent_state", {}).get("weeks_since_dose", 999)
    )
    try:
        weeks_since = int(weeks_since)
    except (TypeError, ValueError):
        weeks_since = 999
    if weeks_since < 26:
        return [
            ValidationResult(
                valid=False,
                validator_name="vaccination_recent_dose_no_revaccinate",
                errors=[
                    f"Vaccination too recent: only {weeks_since} weeks since "
                    "last dose. Seasonal protocol recommends one dose per cycle."
                ],
                metadata={
                    "category": "physical",
                    "rule_id": "physical_recent_dose",
                    "weeks_since_dose": weeks_since,
                },
            )
        ]
    return []


# ─────────────────────────────────────────────────────────────────────
# THINKING — HBM construct coherence
# ─────────────────────────────────────────────────────────────────────

def vaccination_high_susceptibility_high_efficacy_no_refuse(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Block ``refuse`` when SUSCEPTIBILITY is high AND SELF_EFFICACY is high.

    Per HBM, an individual who perceives high infection risk AND has
    confidence in their ability to vaccinate is unlikely to refuse on
    coherent grounds.  This catches cases where the LLM provides
    inconsistent reasoning (e.g., reasoning text endorses vaccination
    but action says refuse).
    """
    if skill_name != "refuse":
        return []
    reasoning = context.get("reasoning", {}) or {}
    susc = str(reasoning.get("SUSCEPTIBILITY_LABEL", "")).upper().strip()
    eff = str(reasoning.get("SELF_EFFICACY_LABEL", "")).upper().strip()
    high_set = {"H", "VH"}
    if susc in high_set and eff in high_set:
        return [
            ValidationResult(
                valid=False,
                validator_name="vaccination_high_susceptibility_high_efficacy_no_refuse",
                errors=[
                    f"HBM coherence: SUSCEPTIBILITY={susc} + SELF_EFFICACY={eff} "
                    "do not support refusal. Reconsider with explicit barriers."
                ],
                metadata={
                    "category": "thinking",
                    "rule_id": "hbm_susc_eff_no_refuse",
                },
            )
        ]
    return []


def vaccination_low_susceptibility_no_immediate_action(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Warning when SUSCEPTIBILITY=VL leads to ``get_vaccinated``.

    Not blocking: low-susceptibility individuals sometimes vaccinate for
    altruistic / household-protection reasons, which is a legitimate HBM
    cue-to-action.  But the audit trace should flag the case for review.
    """
    if skill_name != "get_vaccinated":
        return []
    reasoning = context.get("reasoning", {}) or {}
    susc = str(reasoning.get("SUSCEPTIBILITY_LABEL", "")).upper().strip()
    if susc == "VL":
        return [
            ValidationResult(
                valid=True,    # warning, not blocking
                validator_name="vaccination_low_susceptibility_no_immediate_action",
                warnings=[
                    "HBM coherence note: SUSCEPTIBILITY=VL with immediate "
                    "vaccination is unusual — likely altruistic / cue-to-action."
                ],
                metadata={
                    "category": "thinking",
                    "rule_id": "hbm_low_susc_vaccinate",
                },
            )
        ]
    return []


# Tuples consumed by ValidatorRegistry
VACCINATION_PHYSICAL_CHECKS = (
    vaccination_recent_dose_no_revaccinate,
)
VACCINATION_THINKING_CHECKS = (
    vaccination_high_susceptibility_high_efficacy_no_refuse,
    vaccination_low_susceptibility_no_immediate_action,
)
