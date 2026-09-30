"""build_water_situation_text fixes from the regression audit 2026-09-26:

Finding N6 - the drought headline was keyed on drought_index alone, so it
could read "favorable"/"adequate" while the expected-delivery sentence a few
lines below says the agent will receive well under its full request. The
headline now uses the more severe of the drought-index tier and a
delivery-ratio tier; when the ratio tier is STRICTLY more severe, a
supply-keyed sentence is used instead of the drought-keyed one (a delivery
shortfall must never be described as drought). A tie, or drought more
severe, keeps the original drought-keyed wording byte-identical.

Finding N7 - an Upper Basin agent whose Lake Powell storage equals the
dead-pool floor used to read "Lake Powell holds 1.9 million acre-ft on
1 January" as if that were usable water. powell_dead_pool_maf, threaded in
from irrigation_env.py (IrrigationEnvironment.get_agent_context), now
switches that sentence to a dead-pool wording.
"""
from __future__ import annotations

from examples.irrigation_abm.irrigation_personas import build_water_situation_text


def _lb_context(*, drought_index: float, delivery_ratio: float) -> dict:
    """A minimal Lower Basin context: no Powell fields needed for the
    headline-severity checks."""
    return {
        "year": 5,
        "basin": "lower_basin",
        "drought_index": drought_index,
        "precipitation": 100.0,
        "lake_mead_level": 1080.0,
        "curtailment_ratio": 0.0,
        "shortage_tier": 0,
        "current_request": 100_000.0,
        "current_diversion": 100_000.0 * delivery_ratio,
        "delivery_ratio": delivery_ratio,
        "water_right": 200_000.0,
        "preceding_factor": 1,
    }


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
# N6: drought headline forced by the more severe of drought index / ratio
# --------------------------------------------------------------------------

def test_low_ratio_forces_supply_keyed_headline_despite_benign_drought_index():
    text = build_water_situation_text(_lb_context(drought_index=0.05, delivery_ratio=0.4))
    assert (
        "Water supply is critically short this year: expected deliveries "
        "fall well below requests." in text
    )
    assert "favorable" not in text
    # Must not blame drought for what is actually a delivery shortfall.
    assert "Severe drought" not in text


def test_ratio_in_transition_band_uses_supply_keyed_below_normal_sentence():
    text = build_water_situation_text(_lb_context(drought_index=0.05, delivery_ratio=0.6))
    assert "Water supply is below normal this year." in text
    assert "favorable" not in text
    assert "critically short" not in text
    # Not the drought-keyed "adequate but slightly below normal" wording.
    assert "adequate but slightly below normal" not in text


def test_high_ratio_leaves_favorable_headline_unaffected():
    """WP3 (spec 3.3): only a FULL supply (ratio >= FULL_SUPPLY_RATIO) keeps
    the drought-keyed headline; 0.9 now reads short (it did not before WP3,
    when the edge was the retired supply rule's 0.70)."""
    text = build_water_situation_text(_lb_context(drought_index=0.05, delivery_ratio=0.999))
    assert "Water supply conditions are favorable this year." in text
    short = build_water_situation_text(_lb_context(drought_index=0.05, delivery_ratio=0.9))
    assert "Water supply is below normal this year." in short
    assert "favorable" not in short


def test_drought_tier_still_wins_when_more_severe_than_ratio_tier():
    text = build_water_situation_text(_lb_context(drought_index=0.6, delivery_ratio=0.9))
    assert "Water supply is tight this year." in text


def test_tie_between_drought_tier_3_and_ratio_tier_3_keeps_drought_wording():
    """A tie is NOT "ratio strictly more severe", so the original
    drought-keyed sentence is kept byte-identical."""
    text = build_water_situation_text(_lb_context(drought_index=0.9, delivery_ratio=0.3))
    assert "Water supply is critically short. Severe drought has sharply reduced available water." in text
    assert "expected deliveries fall well below requests" not in text


def test_ratio_exactly_at_half_is_tier_one_not_tier_three():
    """ratio < 0.5 is tier 3; ratio == 0.5 falls into the tier-1 band (0.5 up
    to FULL_SUPPLY_RATIO since WP3), not the most-severe tier."""
    text = build_water_situation_text(_lb_context(drought_index=0.05, delivery_ratio=0.5))
    assert "Water supply is below normal this year." in text
    assert "critically short" not in text


def test_ratio_exactly_at_full_supply_ratio_is_tier_zero():
    """WP3 (spec 3.3): the tier-1 edge is FULL_SUPPLY_RATIO, the supply
    rule's own edge (it was 0.70, the retired rule's cutoff). A ratio of
    exactly FULL_SUPPLY_RATIO is full -- a benign drought index keeps the
    favorable headline -- and the step just below it reads short, so an
    agent the supply rule blocks never reads "favorable"."""
    from examples.irrigation_abm.irrigation_personas import FULL_SUPPLY_RATIO

    text = build_water_situation_text(
        _lb_context(drought_index=0.05, delivery_ratio=FULL_SUPPLY_RATIO))
    assert "Water supply conditions are favorable this year." in text
    assert "below normal" not in text
    below = build_water_situation_text(_lb_context(drought_index=0.05, delivery_ratio=0.998999))
    assert "Water supply is below normal this year." in below
    assert "favorable" not in below
    # 0.7, the old edge, is now inside the short band
    assert "below normal" in build_water_situation_text(
        _lb_context(drought_index=0.05, delivery_ratio=0.7))


# --------------------------------------------------------------------------
# N7: Powell dead-pool wording
# --------------------------------------------------------------------------

def test_dead_pool_sentence_when_storage_equals_the_floor():
    text = build_water_situation_text(_ub_context(powell_storage_maf=1.89, powell_dead_pool_maf=1.89))
    assert "Lake Powell is at its dead-pool floor on 1 January; releases are limited to inflow." in text
    assert "holds" not in text


def test_unchanged_sentence_when_storage_is_above_the_floor():
    text = build_water_situation_text(_ub_context(powell_storage_maf=5.0, powell_dead_pool_maf=1.89))
    assert "Lake Powell holds 5.0 million acre-ft on 1 January." in text
    assert "dead-pool floor" not in text


def test_missing_dead_pool_key_keeps_the_sentence_byte_identical():
    """An older context dict without powell_dead_pool_maf (pre-fix caller)
    must render the exact pre-fix sentence, never the new one."""
    text = build_water_situation_text(_ub_context(powell_storage_maf=1.89, powell_dead_pool_maf=None))
    assert "Lake Powell holds 1.9 million acre-ft on 1 January." in text
    assert "dead-pool floor" not in text


def test_storage_within_the_1e6_tolerance_above_floor_still_dead_pool():
    """The <= dead_pool + 1e-6 tolerance absorbs float noise: a storage only
    1e-7 above the floor is still the dead-pool sentence."""
    text = build_water_situation_text(
        _ub_context(powell_storage_maf=1.89 + 1e-7, powell_dead_pool_maf=1.89)
    )
    assert "Lake Powell is at its dead-pool floor on 1 January; releases are limited to inflow." in text


def test_storage_beyond_the_tolerance_above_floor_is_normal_sentence():
    """A storage 1e-3 above the floor is well outside the float-noise
    tolerance and must render the normal (non-dead-pool) sentence."""
    text = build_water_situation_text(
        _ub_context(powell_storage_maf=1.89 + 1e-3, powell_dead_pool_maf=1.89)
    )
    assert "dead-pool floor" not in text
    assert "Lake Powell holds 1.9 million acre-ft on 1 January." in text
