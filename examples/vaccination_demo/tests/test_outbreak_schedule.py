"""Phase L3-1D unit tests — 5-year COVID-19-anchored outbreak schedule.

Replaces the L3-1A `{year 2: 0.65}` placeholder with a YAML-driven
5-year arc loaded from `examples/vaccination_demo/data/outbreak_schedule.yaml`.
Tests verify:
  1. YAML loads cleanly with the expected 5-year schema.
  2. `VaccinationEnvironment.advance_year()` emits all four global
     signals (severity, label, supply, side-effect) per year.
  3. Year-1 narrative matches the COVID-19-2020 anchor (severe
     outbreak + absent vaccine).
  4. Year-5 narrative matches the COVID-19-2024 anchor (low outbreak
     + ample supply + familiar side effects).
  5. Running past year 5 holds the last-year signals (post-emergency
     steady state).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from examples.vaccination_demo.run_experiment import (
    VaccinationEnvironment,
    _load_outbreak_schedule,
)


def test_outbreak_schedule_yaml_loads():
    """YAML loads with the expected 5-year shape."""
    schedule = _load_outbreak_schedule()
    assert set(schedule.keys()) == {1, 2, 3, 4, 5}, (
        f"Expected 5-year schedule (keys 1-5), got {sorted(schedule.keys())}"
    )
    required = {
        "outbreak_severity",
        "outbreak_label",
        "vaccine_supply",
        "side_effect_signal",
        "description",
    }
    for year, entry in schedule.items():
        assert required.issubset(entry.keys()), (
            f"year {year} missing required keys: "
            f"{required - set(entry.keys())}"
        )


def test_year_1_anchor_covid_2020():
    """Year 1 = COVID-2020 anchor: severe outbreak + no vaccine."""
    env = VaccinationEnvironment(agents={})
    signals = env.advance_year()

    assert signals["outbreak_severity"] >= 0.85, (
        f"Year 1 severity should be severe (≥0.85 per COVID-2020 anchor); "
        f"got {signals['outbreak_severity']}"
    )
    assert signals["outbreak_severity_label"] == "severe"
    assert signals["vaccine_supply_label"] == "absent"
    assert signals["side_effect_signal"] == "unknown"
    assert "Pandemic onset" in signals["outbreak_description"]


def test_year_5_anchor_covid_2024():
    """Year 5 = COVID-2024 anchor: low outbreak + ample supply +
    familiar side effects."""
    env = VaccinationEnvironment(agents={})
    for _ in range(5):
        signals = env.advance_year()

    assert signals["outbreak_severity"] <= 0.30, (
        f"Year 5 severity should be low (≤0.30 per COVID-2024 anchor); "
        f"got {signals['outbreak_severity']}"
    )
    assert signals["outbreak_severity_label"] == "low"
    assert signals["vaccine_supply_label"] == "ample"
    assert signals["side_effect_signal"] == "familiar"


def test_supply_arc_progression():
    """Supply moves absent → limited → ample over years 1-3
    (COVID-19 rollout pattern)."""
    env = VaccinationEnvironment(agents={})
    supply_arc = []
    for _ in range(5):
        signals = env.advance_year()
        supply_arc.append(signals["vaccine_supply_label"])

    # Year 1 = absent, Year 2 = limited, Years 3-5 = ample
    assert supply_arc[0] == "absent"
    assert supply_arc[1] == "limited"
    assert supply_arc[2] == "ample"
    assert supply_arc[3] == "ample"
    assert supply_arc[4] == "ample"


def test_outbreak_active_threshold():
    """outbreak_active toggles correctly per severity threshold (>0.4)."""
    env = VaccinationEnvironment(agents={})
    active_arc = []
    severity_arc = []
    for _ in range(5):
        signals = env.advance_year()
        active_arc.append(signals["outbreak_active"])
        severity_arc.append(signals["outbreak_severity"])

    # Severities: 0.90, 0.75, 0.55, 0.30, 0.20
    # Active threshold: > 0.4
    expected = [True, True, True, False, False]
    assert active_arc == expected, (
        f"outbreak_active arc {active_arc} != expected {expected} for "
        f"severities {severity_arc}"
    )


def test_post_schedule_holds_last_year():
    """Running past year 5 holds the year-5 signals (post-emergency
    steady state) instead of crashing or zeroing out."""
    env = VaccinationEnvironment(agents={})
    for _ in range(5):
        env.advance_year()
    # Sixth and seventh years should mirror year 5
    sig_6 = env.advance_year()
    sig_7 = env.advance_year()
    assert sig_6["outbreak_severity"] == sig_7["outbreak_severity"]
    assert sig_6["vaccine_supply_label"] == "ample"
    assert sig_6["side_effect_signal"] == "familiar"
    # current_year still increments (clock keeps ticking)
    assert sig_7["current_year"] == 7
