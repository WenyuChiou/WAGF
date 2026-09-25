"""Irrigation memory must not say "You chose" for a year whose proposal was rejected.

Audit finding F06 (2026-09-25): on a REJECTED year the registry default
(maintain_demand) executes, but the runner never refreshed
`_last_action_context`, so the next year's memory read "Year t: You chose to
<older approved action>". The runner now records the executed fallback with
`was_fallback=True` and `proposed_skill`; the feedback builder must say so.
"""
from examples.irrigation_abm.irrigation_personas import build_action_outcome_feedback


def _fb(ctx, year=2):
    return build_action_outcome_feedback(
        action_ctx=ctx, year=year, request=100_000, diversion=90_000,
        drought_index=0.40, preceding_factor=0,
    )


def test_rejected_year_reports_rejection_and_applied_default():
    ctx = {"skill_name": "maintain_demand", "year": 2,
           "was_fallback": True, "proposed_skill": "increase_large"}
    text = _fb(ctx)
    assert text.startswith(
        "Year 2: your proposal to increase large was rejected; "
        "maintain demand was applied. You requested 100,000 acre-ft"
    ), text
    assert "You chose" not in text


def test_uncertain_year_without_proposal():
    ctx = {"skill_name": "maintain_demand", "year": 2,
           "was_fallback": True, "proposed_skill": None}
    text = _fb(ctx)
    assert text.startswith(
        "Year 2: no valid proposal was made; maintain demand was applied. "), text
    assert "You chose" not in text


def test_approved_year_text_is_byte_identical():
    ctx = {"skill_name": "decrease_large", "magnitude_pct": 20.0}
    assert _fb(ctx) == (
        "Year 2: You chose to decrease large (by 20%). You requested 100,000 "
        "acre-ft and received 90,000 acre-ft. Shortfall: 10,000 acre-ft (10% "
        "unmet). Drought index: 0.40. Precipitation was below last year."
    )


def test_kept_proposal_is_not_a_fallback():
    """keep_proposal: the agent's own rejected choice executed -> "You chose"."""
    ctx = {"skill_name": "increase_large", "was_fallback": False,
           "proposed_skill": "increase_large"}
    assert _fb(ctx).startswith("Year 2: You chose to increase large. ")
