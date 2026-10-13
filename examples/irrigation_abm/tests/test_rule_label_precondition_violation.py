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
import pytest

from examples.irrigation_abm.irrigation_personas import (
    _RULE_LABELS,
    _precondition_violation_label,
    build_action_outcome_feedback,
)

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def test_precondition_violation_has_a_label():
    """WP3 (spec 3.6): ``_RULE_LABELS`` keeps exactly the six v3 rules; the
    registry backstop ``precondition_violation`` is named by the direction
    of the blocked skill (the cap for an increase, the floor for a
    decrease), never by a fixed entry of its own."""
    assert "precondition_violation" not in _RULE_LABELS
    assert _precondition_violation_label(
        "precondition_violation", "increase_demand") == "the request-increase limit"
    assert _precondition_violation_label(
        "precondition_violation", "decrease_demand") == _RULE_LABELS["minimum_utilisation_floor"]


def test_neutral_feedback_names_shared_increase_limit_for_precondition_violation():
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
        preceding_factor=1,
        basin="upper_basin",
        rejection_line_style="neutral",
    )
    assert feedback.startswith(
        "Year 5: maintain demand was applied under the request-increase limit"
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
        preceding_factor=1,
        basin="upper_basin",
        rejection_line_style="neutral",
    )
    assert "under a governance rule" in feedback


def test_skill_registry_preconditions_are_exactly_the_two_wp2_preconditions():
    """S7, updated WP2 (spec 2.2): the registry now declares exactly two
    precondition strings -- ``not at_allocation_cap`` (increase_demand) and
    ``not below_minimum_utilisation`` (decrease_demand, a new WP2
    backstop) -- each a genuine backstop for the identity-rule menu filter.
    ``_precondition_violation_label`` (guarded by
    ``test_precondition_violation_label_matches_the_two_registry_preconditions``
    below) is what keeps the neutral rejection line correct now that a
    ``precondition_violation`` can mean either one."""
    with open(_CONFIG_DIR / "skill_registry.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    all_preconditions = set()
    for skill in data.get("skills", []):
        all_preconditions.update(skill.get("preconditions") or [])
    assert all_preconditions == {"not at_allocation_cap", "not at_beneficial_use_limit", "not below_minimum_utilisation"}


def test_precondition_violation_label_matches_the_two_registry_preconditions():
    """WP2: _precondition_violation_label resolves a generic
    precondition_violation to the water-right cap for an increase and the
    minimum-use floor for a decrease -- the registry's only two
    preconditions (guarded by the test above), one per direction."""
    assert _precondition_violation_label(
        "precondition_violation", "increase_demand"
    ) == "the request-increase limit"
    assert _precondition_violation_label(
        "precondition_violation", "decrease_demand"
    ) == "the minimum-use floor"
    # Legacy five-skill names still resolve by the same direction prefix.
    assert _precondition_violation_label(
        "precondition_violation", "increase_large"
    ) == "the request-increase limit"
    assert _precondition_violation_label(
        "precondition_violation", "decrease_small"
    ) == "the minimum-use floor"
    # An unrelated rule id is unaffected, still resolved via _RULE_LABELS.
    assert _precondition_violation_label(
        "water_right_cap", "increase_demand"
    ) == _RULE_LABELS["water_right_cap"]


@pytest.mark.parametrize("basin", ["upper_basin", "lower_basin"])
def test_beneficial_precondition_feedback_does_not_claim_water_right_cap(basin):
    feedback = build_action_outcome_feedback(
        action_ctx={"skill_name": "maintain_demand", "was_fallback": True,
                    "proposed_skill": "increase_demand",
                    "blocking_rules": ["precondition_violation"]},
        year=5, request=100_000., diversion=100_000., preceding_factor=1,
        basin=basin, rejection_line_style="neutral")
    assert "under the request-increase limit" in feedback
    assert "the water-right cap" not in feedback
    assert _precondition_violation_label(
        "beneficial_use_limit", "increase_demand") == "the beneficial-use limit"


def test_neutral_feedback_names_minimum_use_floor_for_a_blocked_decrease():
    """WP2: a decrease_demand proposal blocked by the registry's new
    not-below_minimum_utilisation backstop must name the floor, not the
    (wrong) water-right cap the old single-precondition assumption gave
    it."""
    action_ctx = {
        "skill_name": "maintain_demand",
        "was_fallback": True,
        "proposed_skill": "decrease_demand",
        "blocking_rules": ["precondition_violation"],
    }
    feedback = build_action_outcome_feedback(
        action_ctx=action_ctx,
        year=5,
        request=1_000.0,
        diversion=1_000.0,
        preceding_factor=1,
        basin="lower_basin",
        rejection_line_style="neutral",
    )
    assert feedback.startswith(
        "Year 5: maintain demand was applied under the minimum-use floor"
    )
    assert "water-right cap" not in feedback
