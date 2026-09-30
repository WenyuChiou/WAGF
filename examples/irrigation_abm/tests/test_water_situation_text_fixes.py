"""build_water_situation_text fixes from the regression audit 2026-09-26:

Finding N6 (the drought headline could read "favorable" beside a delivery
shortfall) is superseded by WP4 (irrigation_v3_spec_2026-09-28.md 4.3): the
headline is keyed on r alone, in five bands whose top edge is
FULL_SUPPLY_RATIO, with no drought index anywhere; its tests are
examples/irrigation_abm/tests/test_v3_prompt.py (test_headline_bands).

Finding N7 - an Upper Basin agent whose Lake Powell storage equals the
dead-pool floor used to read "Lake Powell holds 1.9 million acre-ft on
1 January" as if that were usable water. powell_dead_pool_maf, threaded in
from irrigation_env.py (IrrigationEnvironment.get_agent_context), now
switches that sentence to a dead-pool wording.
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
