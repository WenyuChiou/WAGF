"""_RULE_LABELS["precondition_violation"] (regression audit 2026-09-26,
finding N5): the disabled arm's only blocking rule is this precondition
check (an increase proposed while already at the water-right cap), and it
had no entry in ``irrigation_personas.py (_RULE_LABELS)``, so every neutral
rejection memory line in the disabled pilot fell back to the generic
"a governance rule" phrase (910 lines).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from examples.irrigation_abm.irrigation_personas import (
    _RULE_LABELS,
    build_action_outcome_feedback,
)

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def test_precondition_violation_has_a_label():
    assert _RULE_LABELS["precondition_violation"] == "the water-right cap"


def test_neutral_feedback_names_water_right_cap_for_precondition_violation():
    action_ctx = {
        "skill_name": "maintain_demand",
        "was_fallback": True,
        "proposed_skill": "increase_large",
        "blocking_rules": ["precondition_violation"],
    }
    feedback = build_action_outcome_feedback(
        action_ctx=action_ctx,
        year=5,
        request=100_000.0,
        diversion=100_000.0,
        drought_index=0.1,
        preceding_factor=1,
        basin="upper_basin",
        rejection_line_style="neutral",
    )
    assert feedback.startswith(
        "Year 5: maintain demand was applied under the water-right cap"
    )
    assert "a governance rule" not in feedback


def test_other_rule_ids_unaffected():
    action_ctx = {
        "skill_name": "maintain_demand",
        "was_fallback": True,
        "proposed_skill": "increase_large",
        "blocking_rules": ["some_unmapped_rule_id"],
    }
    feedback = build_action_outcome_feedback(
        action_ctx=action_ctx,
        year=5,
        request=100_000.0,
        diversion=100_000.0,
        drought_index=0.1,
        preceding_factor=1,
        basin="upper_basin",
        rejection_line_style="neutral",
    )
    assert "under a governance rule" in feedback


def test_skill_registry_preconditions_are_exactly_the_water_right_cap():
    """S7: guards the _RULE_LABELS["precondition_violation"] mapping above.
    "the water-right cap" is correct only because the water-right cap
    (``not at_allocation_cap``) is the ONLY precondition string declared
    anywhere in config/skill_registry.yaml. If a future skill adds a
    DIFFERENT precondition, this test fails before that label can silently
    misdescribe it."""
    with open(_CONFIG_DIR / "skill_registry.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    all_preconditions = set()
    for skill in data.get("skills", []):
        all_preconditions.update(skill.get("preconditions") or [])
    assert all_preconditions == {"not at_allocation_cap"}
