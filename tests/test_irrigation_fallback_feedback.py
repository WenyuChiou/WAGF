"""Irrigation outcomes describe the action that ran for every decision path."""
from examples.irrigation_abm.irrigation_personas import build_action_outcome_feedback


def _fb(ctx, year=2):
    return build_action_outcome_feedback(
        action_ctx=ctx, year=year, request=100_000, diversion=90_000,
        preceding_factor=0,
    )


def test_rejected_year_records_executed_default():
    ctx = {"skill_name": "maintain_demand", "year": 2,
           "was_fallback": True, "proposed_skill": "increase_large"}
    text = _fb(ctx)
    assert text.startswith("Year 2: Action carried out: maintain demand. You requested 100,000 acre-ft")
    assert "You chose" not in text


def test_uncertain_year_without_proposal():
    ctx = {"skill_name": "maintain_demand", "year": 2,
           "was_fallback": True, "proposed_skill": None}
    text = _fb(ctx)
    assert text.startswith(
        "Year 2: Action carried out: maintain demand. "), text
    assert "You chose" not in text


def test_approved_year_records_magnitude_and_physical_outcome():
    ctx = {"skill_name": "decrease_large", "magnitude_pct": 20.0}
    # WP4 (spec 4.5): the unmet share with one decimal, no drought index,
    # the agent's own sub-basin precipitation sentence.
    assert _fb(ctx) == (
        "Year 2: Action carried out: decrease large (by 20%). You requested 100,000 "
        "acre-ft and received 90,000 acre-ft. Shortfall: 10,000 acre-ft (10.0% "
        "unmet). That winter's precipitation in your sub-basin was below the "
        "previous winter's."
    )


def test_kept_proposal_is_not_a_fallback():
    """A kept proposal is recorded as the executed action."""
    ctx = {"skill_name": "increase_large", "was_fallback": False,
           "proposed_skill": "increase_large"}
    assert _fb(ctx).startswith("Year 2: Action carried out: increase large. ")
