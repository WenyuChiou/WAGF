"""Tests for frequency-matched null model (P1.2)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import numpy as np
import pandas as pd

from validation.metrics.null_model import generate_frequency_matched_null_traces


def _make_profiles(n=20):
    """Create minimal agent profiles."""
    rows = []
    for i in range(n):
        rows.append({
            "agent_id": f"H{i:03d}",
            "tenure": "Owner" if i < n // 2 else "Renter",
            "flood_zone": "HIGH" if i % 3 == 0 else "LOW",
            "mg": i % 4 == 0,
        })
    return pd.DataFrame(rows)


def _make_observed_traces(profiles):
    """Create observed traces with known action distribution."""
    traces = []
    for _, row in profiles.iterrows():
        tenure = str(row["tenure"])
        # Owners: 80% buy_insurance, 20% do_nothing
        # Renters: 60% buy_insurance, 40% relocate
        if tenure == "Owner":
            action = "buy_insurance" if np.random.random() < 0.8 else "do_nothing"
        else:
            action = "buy_insurance" if np.random.random() < 0.6 else "relocate"
        traces.append({
            "agent_id": str(row["agent_id"]),
            "year": 1,
            "approved_skill": {"skill_name": action},
            "outcome": "APPROVED",
        })
    return traces


class TestFrequencyMatchedNull:
    def test_output_structure(self):
        profiles = _make_profiles()
        observed = _make_observed_traces(profiles)
        null_traces = generate_frequency_matched_null_traces(
            profiles, observed, n_years=3, seed=42,
        )
        assert len(null_traces) == len(profiles) * 3
        for t in null_traces:
            assert "agent_id" in t
            assert "year" in t
            assert "approved_skill" in t

    def test_action_frequencies_match_observed(self):
        """Null traces should approximately match observed action frequencies."""
        profiles = _make_profiles(100)
        # All owners do buy_insurance, all renters do relocate
        observed = []
        for _, row in profiles.iterrows():
            action = "buy_insurance" if row["tenure"] == "Owner" else "relocate"
            observed.append({
                "agent_id": str(row["agent_id"]),
                "year": 1,
                "approved_skill": {"skill_name": action},
                "outcome": "APPROVED",
            })

        null_traces = generate_frequency_matched_null_traces(
            profiles, observed, n_years=100, seed=0,
        )

        # Count owner actions
        owner_ids = set(str(row["agent_id"]) for _, row in profiles.iterrows()
                       if row["tenure"] == "Owner")
        owner_actions = [t["approved_skill"]["skill_name"]
                        for t in null_traces if t["agent_id"] in owner_ids]

        # With 100% buy_insurance in observed, null should be 100% buy_insurance
        assert all(a == "buy_insurance" for a in owner_actions)

    def test_rejected_traces_count_as_do_nothing(self):
        """REJECTED proposals should be counted as do_nothing in frequency computation."""
        profiles = _make_profiles(10)
        observed = []
        for _, row in profiles.iterrows():
            observed.append({
                "agent_id": str(row["agent_id"]),
                "year": 1,
                "skill_proposal": {"skill_name": "elevate"},
                "approved_skill": {"skill_name": "elevate"},
                "outcome": "REJECTED",
            })

        null_traces = generate_frequency_matched_null_traces(
            profiles, observed, n_years=10, seed=42,
        )
        # All observed are REJECTED → do_nothing frequency = 100%
        actions = set(t["approved_skill"]["skill_name"] for t in null_traces)
        assert actions == {"do_nothing"}

    def test_custom_hazard_fn(self):
        """Custom hazard function should be respected."""
        profiles = _make_profiles(5)
        observed = _make_observed_traces(profiles)

        def no_hazard(row, rng):
            return False

        null_traces = generate_frequency_matched_null_traces(
            profiles, observed, n_years=3, seed=0, hazard_fn=no_hazard,
        )
        assert all(t["flooded_this_year"] is False for t in null_traces)

    def test_reproducibility(self):
        profiles = _make_profiles()
        observed = _make_observed_traces(profiles)
        t1 = generate_frequency_matched_null_traces(profiles, observed, seed=99)
        t2 = generate_frequency_matched_null_traces(profiles, observed, seed=99)
        actions1 = [t["approved_skill"]["skill_name"] for t in t1]
        actions2 = [t["approved_skill"]["skill_name"] for t in t2]
        assert actions1 == actions2
