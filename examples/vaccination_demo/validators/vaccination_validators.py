"""
Vaccination domain validator checks.

Phase 6C-v3 reference: every check below is a ``BuiltinCheck`` callable
matching the signature ``(skill_name, rules, context) -> List[ValidationResult]``.
They are registered with :class:`ValidatorRegistry` in this package's
``__init__.py`` so the broker's :func:`validate_all` picks them up at
runtime — no edits to broker/ source code.

L3-1C (2026-05-23) design choice: Python checks cover only the PHYSICAL
slot (state-precondition / immutability) because the
``ValidatorRegistry`` slot policy (see ``__init__.py``) rejects
``thinking`` as a registered slot — HBM coherence rules live in YAML
at ``../config/agent_types.yaml`` under the ``thinking_rules:`` key
(NOT ``rules:`` — Phase 6N-C reviewer caught this: the broker's
``get_thinking_rules()`` at ``broker/utils/agent_config.py:859``
recognises only ``thinking_rules`` or ``coherence_rules``; the
original PoC's ``rules:`` block was silently dead config). Consumed by
``ThinkingValidator._validate_yaml_rules``. An earlier draft of this
file mirrored the YAML coherence rules with 5 Python check functions,
but they would have been dead code (never registered, never invoked).
Stripped to the single physical check so the file matches the broker's
actual slot architecture; the L3-1C 5 coherence rules live in YAML and
are exercised end-to-end by the L3-1B smoke flow.

The single physical check sets ``metadata['category']='physical'`` so
the audit CSV's ``rules_physical_hit`` column (Phase 6C W8 fix) gets
populated correctly on rejection.
"""
from __future__ import annotations

from typing import Any, Dict, List

from broker.governance.rule_types import GovernanceRule
from broker.interfaces.skill_types import ValidationResult


# ---------------------------------------------------------------------
# PHYSICAL — state-precondition / immutability rules
# ---------------------------------------------------------------------


def vaccination_recent_dose_no_revaccinate(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Block ``get_vaccinated`` if the agent received a dose within 26 weeks.

    Standard public-health guidance is one seasonal dose per cycle.
    Re-vaccination inside that window is wasteful and rarely recommended.
    This is a STATE-precondition (reads ``weeks_since_dose`` from the
    agent's dynamic state, not from the LLM's HBM reasoning), so it
    lives in Python rather than as a YAML construct rule.
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


# ---------------------------------------------------------------------
# Registry tuples consumed by ValidatorRegistry (see __init__.py)
# ---------------------------------------------------------------------

VACCINATION_PHYSICAL_CHECKS = (
    vaccination_recent_dose_no_revaccinate,
)
