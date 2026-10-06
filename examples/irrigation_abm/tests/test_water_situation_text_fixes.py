"""build_water_situation_text fixes from the regression audit 2026-09-26,
and its item 36d retirement (2026-10-05 design-basis audit + fix proposals):

Finding N6 (the drought headline could read "favorable" beside a delivery
shortfall) is superseded by WP4 (irrigation_v3_spec_2026-09-28.md 4.3): the
headline is keyed on r alone, with no drought index anywhere; its tests are
examples/irrigation_abm/tests/test_v3_prompt.py (test_headline_bands). Item
36a (2026-10-05) later collapsed the headline from five bands to two
(sufficient / short) at FULL_SUPPLY_RATIO -- unrelated to this file, which
is about the (now-removed) Lake Powell sentence, not the headline.

Finding N7 - an Upper Basin agent whose Lake Powell storage equalled the
dead-pool floor used to read "Lake Powell holds 1.9 million acre-ft on
1 January" as if that were usable water. powell_dead_pool_maf, threaded in
from irrigation_env.py (IrrigationEnvironment.get_agent_context), fixed
that by switching the sentence to a dead-pool wording at or below the
floor, and to "Lake Powell holds N million acre-ft on 1 January" above it.

Item 36d (2026-10-05 design-basis audit + fix proposals, spec item 36d,
G5): the Lake Powell sentence -- BOTH forms above -- is REMOVED from
Upper Basin prompts entirely, not just fixed at the dead-pool edge. Under
item 4 / E14 the Upper Basin is never curtailed to protect a Powell
release, so Powell's level cannot affect an Upper Basin agent's delivery;
showing it anyway (correctly worded or not) invited a WSA reading driven
by a number that has no effect on the agent. This file's tests are
rewritten to confirm the ABSENCE of any Powell-storage sentence, at every
storage level the N7 fix used to distinguish, rather than which of the two
forms appears -- env_context still carries powell_storage_maf and
powell_dead_pool_maf (other, non-prompt consumers may read them); only
this one prompt sentence is gone.
"""
from __future__ import annotations

from examples.irrigation_abm.irrigation_personas import build_water_situation_text


def _ub_context(*, powell_storage_maf: float, powell_dead_pool_maf=1.89) -> dict:
    ctx = {
        "year": 5,
        "basin": "upper_basin",
        "drought_index": 0.1,
        "precipitation": 100.0,
        "lake_mead_level": 1080.0,
        "curtailment_ratio": 0.0,
        "shortage_tier": 0,
        "current_request": 100_000.0,
        "current_diversion": 100_000.0,
        "delivery_ratio": 1.0,
        "water_right": 200_000.0,
        "preceding_factor": 1,
        "natural_flow_maf": 10.0,
        "powell_storage_maf": powell_storage_maf,
    }
    if powell_dead_pool_maf is not None:
        ctx["powell_dead_pool_maf"] = powell_dead_pool_maf
    return ctx


# --------------------------------------------------------------------------
# Item 36d: no Lake Powell sentence at all, in any of N7's old cases
# --------------------------------------------------------------------------

def _assert_no_powell_sentence(text: str) -> None:
    assert "Lake Powell" not in text
    assert "dead-pool floor" not in text
    assert "holds" not in text


def test_no_powell_sentence_when_storage_equals_the_floor():
    text = build_water_situation_text(_ub_context(powell_storage_maf=1.89, powell_dead_pool_maf=1.89))
    _assert_no_powell_sentence(text)


def test_no_powell_sentence_when_storage_is_above_the_floor():
    text = build_water_situation_text(_ub_context(powell_storage_maf=5.0, powell_dead_pool_maf=1.89))
    _assert_no_powell_sentence(text)


def test_no_powell_sentence_with_missing_dead_pool_key():
    """An older context dict without powell_dead_pool_maf (pre-N7-fix
    caller) still renders no Powell sentence at all -- item 36d removes
    the sentence outright, so the N7 fix's own fallback path is moot."""
    text = build_water_situation_text(_ub_context(powell_storage_maf=1.89, powell_dead_pool_maf=None))
    _assert_no_powell_sentence(text)


def test_no_powell_sentence_within_the_1e6_tolerance_above_floor():
    """The N7 fix's <= dead_pool + 1e-6 tolerance is moot now too -- no
    sentence either way, regardless of which side of the old edge."""
    text = build_water_situation_text(
        _ub_context(powell_storage_maf=1.89 + 1e-7, powell_dead_pool_maf=1.89)
    )
    _assert_no_powell_sentence(text)


def test_no_powell_sentence_beyond_the_tolerance_above_floor():
    text = build_water_situation_text(
        _ub_context(powell_storage_maf=1.89 + 1e-3, powell_dead_pool_maf=1.89)
    )
    _assert_no_powell_sentence(text)
