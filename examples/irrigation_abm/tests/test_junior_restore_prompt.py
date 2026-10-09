"""Regression tests for removing the superseded spec-45p recovery prompt."""

from __future__ import annotations

import pytest

from examples.irrigation_abm.irrigation_personas import build_water_situation_text


def _context(*, tier: int = 2, current_gap: str = "lb_junior_tier_cut",
             senior: float = 0.0, junior: float = 10_000.0,
             at_allocation_cap: bool = False, request: float = 3_826.0) -> dict:
    return {
        "year": 2021,
        "basin": "lower_basin",
        "lake_mead_level": 1049.0,
        "preceding_factor": 0,
        "shortage_tier": tier,
        "lb_shortage_volume_maf": {0: 0.0, 2: 0.417}[tier],
        "shortage_tier_threshold_ft": {0: None, 2: 1050.0}[tier],
        "current_request": request,
        "current_diversion": (request if current_gap == "none" or not junior
                              else (2_857.0 if tier else 3_826.0)),
        "water_right": senior + junior,
        "gap_reason": current_gap,
        "at_allocation_cap": at_allocation_cap,
        "lb_junior_request_af": 3_826.0 if junior else 0.0,
        "lb_junior_tier_cut_fraction": 0.2532 if tier else 0.0,
        "lb_senior_entitlement_af": senior,
        "lb_junior_entitlement_af": junior,
        "lb_junior_ceiling_af": junior * (1.0 - (0.2532 if tier else 0.0)),
        "lb_tier_ceiling_af": senior + junior * (1.0 - (0.2532 if tier else 0.0)),
        "lb_p56_entitlement_af": 0.0,
        "lb_p56_in_tier": "zero",
    }


def _last_year(*, gap: str = "lb_junior_tier_cut", request: float = 4_798.0,
               diversion: float = 3_826.0) -> dict:
    return {
        "request": request,
        "diversion": diversion,
        "gap_reason": gap,
        "lb_junior_tier_cut_fraction": 0.2026,
        "lb_junior_ceiling_af": 7_974.0,
        "lb_junior_entitlement_af": 10_000.0,
    }


def test_restore_sentence_is_absent_after_a_fully_junior_tier_cut():
    text = build_water_situation_text(_context(), _last_year())
    assert "To return toward" not in text
    assert "choose to increase your request" not in text


def test_restore_sentence_is_absent_after_a_partly_junior_tier_cut():
    text = build_water_situation_text(
        _context(senior=5_940.0, junior=35_060.0), _last_year(request=28_295.0)
    )
    assert "To return toward" not in text
    assert "choose to increase your request" not in text


def test_restore_sentence_is_absent_when_no_tier_is_declared():
    text = build_water_situation_text(
        _context(tier=0, current_gap="none"), _last_year()
    )
    assert "To return toward" not in text
    assert "tier cut was a fixed share" not in text


def test_partly_junior_restore_sentence_is_absent_without_a_tier():
    text = build_water_situation_text(
        _context(tier=0, current_gap="none", senior=5_940.0, junior=35_060.0),
        _last_year(request=28_295.0),
    )
    assert "To return toward" not in text
    assert "tier cut was a fixed share" not in text


@pytest.mark.parametrize(
    ("context", "last_year"),
    [
        (_context(), _last_year(gap="lb_junior_tier_cut+lb_mead_availability")),
        (_context(current_gap="lb_junior_tier_cut+lb_mead_availability"), _last_year()),
        (_context(senior=10_000.0, junior=0.0, current_gap="none"), _last_year()),
        (_context(), _last_year(request=3_826.0, diversion=3_826.0)),
    ],
    ids=("physical-shortage-last-year", "physical-shortage-this-year",
         "senior-only", "fully-delivered-last-year"),
)
def test_restore_sentence_is_absent_outside_eligibility(context, last_year):
    text = build_water_situation_text(context, last_year)
    assert "does not change your water right" not in text
    assert "did not change your water right" not in text


def test_restore_sentence_is_hidden_when_formatted_amounts_match():
    """NorthBaja-like sub-acre amounts both display as 2 acre-ft."""
    text = build_water_situation_text(
        _context(tier=0, current_gap="none", request=1.75),
        _last_year(request=2.19, diversion=1.75),
    )
    assert "did not change your water right" not in text


def test_restore_sentence_is_hidden_at_allocation_cap():
    text = build_water_situation_text(
        _context(at_allocation_cap=True), _last_year()
    )
    assert "does not change your water right" not in text


def test_physical_shortage_hides_sentence_above_full_supply_display_threshold():
    context = _context(current_gap="lb_junior_tier_cut+lb_mead_availability")
    context["delivery_ratio"] = 0.9995
    context["current_diversion"] = context["current_request"] * 0.9995
    text = build_water_situation_text(context, _last_year())
    assert "Water supply is sufficient for your full request this year." in text
    assert "does not change your water right" not in text
