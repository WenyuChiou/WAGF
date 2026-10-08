"""Regression tests for the spec-45p junior-tier recovery prompt."""

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
        "current_diversion": 2_857.0 if tier else 3_826.0,
        "water_right": senior + junior,
        "gap_reason": current_gap,
        "at_allocation_cap": at_allocation_cap,
        "lb_junior_request_af": 3_826.0 if junior else 0.0,
        "lb_junior_tier_cut_fraction": 0.2532 if tier else 0.0,
        "lb_senior_entitlement_af": senior,
        "lb_junior_entitlement_af": junior,
    }


def _last_year(*, gap: str = "lb_junior_tier_cut", request: float = 4_798.0,
               diversion: float = 3_826.0) -> dict:
    return {
        "request": request,
        "diversion": diversion,
        "gap_reason": gap,
        "lb_junior_tier_cut_fraction": 0.2026,
    }


def test_fully_junior_restore_sentence_is_exact_and_follows_tier_line():
    text = build_water_situation_text(_context(), _last_year())
    lines = text.splitlines()
    tier_index = next(i for i, line in enumerate(lines)
                      if line.startswith("A Tier 2 Lower Basin shortage"))
    assert lines[tier_index + 1] == (
        "The tier cut is a fixed share of the junior-priority water you request; it does "
        "not change your water right. If you choose to keep your request, you ask for the reduced "
        "3,826 acre-ft you received last year. To return toward the 4,798 acre-ft you "
        "requested last year, choose to increase your request."
    )


def test_partly_junior_restore_sentence_names_senior_entitlement():
    text = build_water_situation_text(
        _context(senior=5_940.0, junior=35_060.0), _last_year(request=28_295.0)
    )
    assert (
        "The tier cut is a fixed share of the junior-priority part of your request, the "
        "part above 5,940 acre-ft; it does not change your water right. If you choose "
        "to keep your request, you ask for the reduced 3,826 acre-ft you received last year. "
        "To return toward the 28,295 acre-ft you requested last year, choose to increase "
        "your request."
    ) in text


def test_restore_sentence_uses_past_tense_when_no_tier_is_declared():
    text = build_water_situation_text(
        _context(tier=0, current_gap="none"), _last_year()
    )
    assert (
        "Last year's tier cut was a fixed share of the junior-priority water you requested; "
        "it did not change your water right. If you choose to keep your request, you ask for the reduced "
        "3,826 acre-ft you received last year. To return toward the 4,798 acre-ft you "
        "requested last year, choose to increase your request."
    ) in text
    assert "The tier cut is a fixed share of the junior-priority water you request" not in text


def test_partly_junior_restore_sentence_uses_past_tense_without_a_tier():
    text = build_water_situation_text(
        _context(tier=0, current_gap="none", senior=5_940.0, junior=35_060.0),
        _last_year(request=28_295.0),
    )
    assert (
        "Last year's tier cut was a fixed share of the junior-priority part of your request, "
        "the part above 5,940 acre-ft; it did not change your water right. If you choose "
        "to keep your request, you ask for the reduced 3,826 acre-ft you received last year. "
        "To return toward the 28,295 acre-ft you requested last year, choose to increase "
        "your request."
    ) in text


@pytest.mark.parametrize(
    ("context", "last_year"),
    [
        (_context(), _last_year(gap="lb_junior_tier_cut+lb_mead_availability")),
        (_context(current_gap="lb_junior_tier_cut+lb_mead_availability"), _last_year()),
        (_context(senior=10_000.0, junior=0.0), _last_year()),
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
