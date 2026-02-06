"""
Tests for decision-based state inference in compute_validation_metrics.py.

The flood simulation engine does not populate state_after with decision outcomes
(execution_result.state_changes is empty). These tests validate the
_extract_final_states_from_decisions() function that infers final state from
the sequence of agent decisions.
"""

import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

# Setup path
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from examples.multi_agent.flood.paper3.analysis.compute_validation_metrics import (
    _extract_final_states_from_decisions,
    _extract_final_states,
    _normalize_action,
    _compute_benchmark,
    compute_l2_metrics,
    EMPIRICAL_BENCHMARKS,
)


# =============================================================================
# Test Helper
# =============================================================================


def make_trace(agent_id, year, action, state_after=None):
    """Create a minimal trace dict for testing."""
    sa = state_after or {}
    return {
        "agent_id": agent_id,
        "year": year,
        "approved_skill": {"skill_name": action, "status": "APPROVED"},
        "skill_proposal": {"skill_name": action, "reasoning": {}},
        "outcome": "APPROVED",
        "state_before": dict(sa),
        "state_after": dict(sa),
    }


# =============================================================================
# Unit Tests: _extract_final_states_from_decisions()
# =============================================================================


class TestExtractFinalStatesFromDecisions:
    """Unit tests for decision-based state inference."""

    def test_single_buy_insurance(self):
        traces = [make_trace("H001", year=1, action="buy_insurance")]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["has_insurance"] is True
        assert states["H001"]["elevated"] is False
        assert states["H001"]["bought_out"] is False
        assert states["H001"]["relocated"] is False

    def test_single_elevate(self):
        traces = [make_trace("H001", year=1, action="elevate_house")]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["elevated"] is True
        assert states["H001"]["has_insurance"] is False

    def test_single_do_nothing(self):
        traces = [make_trace("H001", year=1, action="do_nothing")]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["has_insurance"] is False
        assert states["H001"]["elevated"] is False
        assert states["H001"]["bought_out"] is False
        assert states["H001"]["relocated"] is False

    def test_multi_year_cumulative(self):
        """Insurance yr1 + elevate yr2 → both True."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance"),
            make_trace("H001", year=2, action="elevate_house"),
        ]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["has_insurance"] is True
        assert states["H001"]["elevated"] is True

    def test_irreversible_elevation(self):
        """Elevate yr1, do_nothing yr2-13 → still elevated."""
        traces = [make_trace("H001", year=1, action="elevate_house")]
        traces += [make_trace("H001", year=y, action="do_nothing") for y in range(2, 14)]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["elevated"] is True

    def test_irreversible_insurance(self):
        """Insurance yr1, do_nothing yr2-5 → still insured."""
        traces = [make_trace("H001", year=1, action="buy_insurance")]
        traces += [make_trace("H001", year=y, action="do_nothing") for y in range(2, 6)]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["has_insurance"] is True

    def test_buyout(self):
        traces = [
            make_trace("H001", year=1, action="buy_insurance"),
            make_trace("H001", year=3, action="buyout_program"),
        ]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["bought_out"] is True
        assert states["H001"]["has_insurance"] is True

    def test_renter_relocate(self):
        traces = [
            make_trace("H201", year=1, action="buy_contents_insurance"),
            make_trace("H201", year=3, action="relocate"),
        ]
        states = _extract_final_states_from_decisions(traces)
        assert states["H201"]["has_insurance"] is True
        assert states["H201"]["relocated"] is True

    def test_empty_traces(self):
        states = _extract_final_states_from_decisions([])
        assert len(states) == 0

    def test_action_normalization_contents_insurance(self):
        """buy_contents_insurance normalizes to buy_insurance."""
        traces = [make_trace("H001", year=1, action="buy_contents_insurance")]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["has_insurance"] is True

    def test_action_normalization_elevate_home(self):
        """elevate_home normalizes to elevate."""
        traces = [make_trace("H001", year=1, action="elevate_home")]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["elevated"] is True

    def test_unknown_action(self):
        traces = [make_trace("H001", year=1, action="unknown_action")]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["has_insurance"] is False
        assert states["H001"]["elevated"] is False
        assert states["H001"]["bought_out"] is False
        assert states["H001"]["relocated"] is False

    def test_malformed_trace_no_approved_skill(self):
        """Trace without approved_skill → do_nothing."""
        trace = {"agent_id": "H001", "year": 1}
        states = _extract_final_states_from_decisions([trace])
        assert states["H001"]["has_insurance"] is False
        assert states["H001"]["elevated"] is False

    def test_state_after_fallback_for_non_decision_fields(self):
        """Non-decision fields come from state_after of latest trace."""
        traces = [make_trace(
            "H001", year=1, action="buy_insurance",
            state_after={"flood_zone": "HIGH", "cumulative_damage": 50000}
        )]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["flood_zone"] == "HIGH"
        assert states["H001"]["cumulative_damage"] == 50000
        assert states["H001"]["has_insurance"] is True  # overridden by decision

    def test_latest_year_state_used(self):
        """state_after from latest year is used for fallback fields."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance",
                       state_after={"flood_zone": "LOW", "cumulative_damage": 0}),
            make_trace("H001", year=5, action="do_nothing",
                       state_after={"flood_zone": "HIGH", "cumulative_damage": 30000}),
        ]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["flood_zone"] == "HIGH"
        assert states["H001"]["cumulative_damage"] == 30000
        assert states["H001"]["has_insurance"] is True  # from yr1 decision

    def test_multiple_agents(self):
        """Multiple agents are tracked independently."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance"),
            make_trace("H002", year=1, action="elevate_house"),
            make_trace("H003", year=1, action="do_nothing"),
        ]
        states = _extract_final_states_from_decisions(traces)
        assert len(states) == 3
        assert states["H001"]["has_insurance"] is True
        assert states["H002"]["elevated"] is True
        assert states["H003"]["has_insurance"] is False

    def test_empty_agent_id_skipped(self):
        traces = [{"agent_id": "", "year": 1, "approved_skill": {"skill_name": "buy_insurance"}}]
        states = _extract_final_states_from_decisions(traces)
        assert len(states) == 0

    def test_year_tracking(self):
        """_year field should be the latest year seen."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance"),
            make_trace("H001", year=7, action="do_nothing"),
        ]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["_year"] == 7

    def test_out_of_order_traces(self):
        """Traces processed out of order should still use latest year's state."""
        traces = [
            make_trace("H001", year=5, action="elevate_house",
                       state_after={"flood_zone": "HIGH"}),
            make_trace("H001", year=1, action="buy_insurance",
                       state_after={"flood_zone": "LOW"}),
        ]
        states = _extract_final_states_from_decisions(traces)
        assert states["H001"]["flood_zone"] == "HIGH"
        assert states["H001"]["_year"] == 5
        # Both actions should be cumulated regardless of order
        assert states["H001"]["has_insurance"] is True
        assert states["H001"]["elevated"] is True

    def test_missing_agent_id_key(self):
        """Trace without agent_id key entirely should be skipped."""
        traces = [{"year": 1, "approved_skill": {"skill_name": "buy_insurance"}}]
        states = _extract_final_states_from_decisions(traces)
        assert len(states) == 0


# =============================================================================
# Integration Tests: L2 Benchmark Computation with Decision-Based State
# =============================================================================


def _make_agent_profiles(agents):
    """Create a minimal agent_profiles DataFrame.

    agents: list of dicts with keys: agent_id, tenure, flood_zone, mg
    """
    return pd.DataFrame(agents)


class TestBenchmarkWithDecisionState:
    """Integration tests for L2 benchmarks using decision-based inference."""

    def test_insurance_rate_sfha(self):
        """5 HIGH-zone agents, 2 bought insurance → 2/5 = 0.40."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance"),
            make_trace("H002", year=1, action="buy_insurance"),
            make_trace("H003", year=1, action="do_nothing"),
            make_trace("H004", year=1, action="elevate_house"),
            make_trace("H005", year=1, action="do_nothing"),
        ]
        profiles = _make_agent_profiles([
            {"agent_id": "H001", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H002", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H003", "tenure": "Owner", "flood_zone": "HIGH", "mg": False},
            {"agent_id": "H004", "tenure": "Owner", "flood_zone": "HIGH", "mg": False},
            {"agent_id": "H005", "tenure": "Owner", "flood_zone": "LOW", "mg": False},
        ])
        result = compute_l2_metrics(traces, profiles)
        sfha_val = result.benchmark_results["insurance_rate_sfha"]["value"]
        # 2 insured / 4 HIGH-zone agents = 0.50
        assert sfha_val == pytest.approx(0.50, abs=0.01)

    def test_elevation_rate_owners_only(self):
        """3 owners, 1 elevated → 1/3 = 0.333."""
        traces = [
            make_trace("H001", year=1, action="elevate_house"),
            make_trace("H002", year=1, action="buy_insurance"),
            make_trace("H003", year=1, action="do_nothing"),
            make_trace("H004", year=1, action="do_nothing"),
        ]
        profiles = _make_agent_profiles([
            {"agent_id": "H001", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H002", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H003", "tenure": "Owner", "flood_zone": "HIGH", "mg": False},
            {"agent_id": "H004", "tenure": "Renter", "flood_zone": "HIGH", "mg": False},
        ])
        result = compute_l2_metrics(traces, profiles)
        elev_val = result.benchmark_results["elevation_rate"]["value"]
        # 1 elevated / 3 owners = 0.3333
        assert elev_val == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_buyout_rate(self):
        """4 agents: 1 buyout + 1 relocate → 2/4 = 0.50."""
        traces = [
            make_trace("H001", year=1, action="buyout_program"),
            make_trace("H002", year=1, action="relocate"),
            make_trace("H003", year=1, action="buy_insurance"),
            make_trace("H004", year=1, action="do_nothing"),
        ]
        profiles = _make_agent_profiles([
            {"agent_id": "H001", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H002", "tenure": "Renter", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H003", "tenure": "Owner", "flood_zone": "HIGH", "mg": False},
            {"agent_id": "H004", "tenure": "Renter", "flood_zone": "HIGH", "mg": False},
        ])
        result = compute_l2_metrics(traces, profiles)
        buyout_val = result.benchmark_results["buyout_rate"]["value"]
        assert buyout_val == pytest.approx(0.50, abs=0.01)

    def test_mg_adaptation_gap(self):
        """MG: 1/2 insured=0.50, NMG: 0/2 insured=0.0 → gap=0.50."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance"),  # MG, insured
            make_trace("H002", year=1, action="do_nothing"),     # MG, not insured
            make_trace("H003", year=1, action="do_nothing"),     # NMG
            make_trace("H004", year=1, action="elevate_house"),  # NMG
        ]
        profiles = _make_agent_profiles([
            {"agent_id": "H001", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H002", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H003", "tenure": "Owner", "flood_zone": "HIGH", "mg": False},
            {"agent_id": "H004", "tenure": "Owner", "flood_zone": "HIGH", "mg": False},
        ])
        result = compute_l2_metrics(traces, profiles)
        gap_val = result.benchmark_results["mg_adaptation_gap"]["value"]
        assert gap_val == pytest.approx(0.50, abs=0.01)

    def test_renter_uninsured_rate(self):
        """2 HIGH-zone renters, 1 bought insurance → uninsured = 1 - 0.5 = 0.5."""
        traces = [
            make_trace("H001", year=1, action="buy_contents_insurance"),
            make_trace("H002", year=1, action="do_nothing"),
            make_trace("H003", year=1, action="buy_insurance"),
        ]
        profiles = _make_agent_profiles([
            {"agent_id": "H001", "tenure": "Renter", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H002", "tenure": "Renter", "flood_zone": "HIGH", "mg": True},
            {"agent_id": "H003", "tenure": "Owner", "flood_zone": "HIGH", "mg": False},
        ])
        result = compute_l2_metrics(traces, profiles)
        uninsured_val = result.benchmark_results["renter_uninsured_rate"]["value"]
        assert uninsured_val == pytest.approx(0.50, abs=0.01)

    def test_insurance_lapse_rate_no_lapse(self):
        """Agent buys insurance yr1 then continues → no lapse periods to count."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance"),
            make_trace("H001", year=2, action="buy_insurance"),
            make_trace("H001", year=3, action="buy_insurance"),
        ]
        profiles = _make_agent_profiles([
            {"agent_id": "H001", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
        ])
        result = compute_l2_metrics(traces, profiles)
        lapse_val = result.benchmark_results["insurance_lapse_rate"]["value"]
        # insured_periods=2 (yr2 and yr3 where was_insured=True)
        # lapses=0 (always re-bought)
        assert lapse_val == pytest.approx(0.0, abs=0.01)

    def test_insurance_lapse_rate_with_lapse(self):
        """Agent buys insurance yr1, does nothing yr2-3 → 2 lapses / 2 periods."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance"),
            make_trace("H001", year=2, action="do_nothing"),
            make_trace("H001", year=3, action="elevate_house"),
        ]
        profiles = _make_agent_profiles([
            {"agent_id": "H001", "tenure": "Owner", "flood_zone": "HIGH", "mg": True},
        ])
        result = compute_l2_metrics(traces, profiles)
        lapse_val = result.benchmark_results["insurance_lapse_rate"]["value"]
        # insured_periods=2, lapses=2 (yr2 do_nothing != buy_insurance, yr3 elevate != buy_insurance)
        assert lapse_val == pytest.approx(1.0, abs=0.01)


# =============================================================================
# Regression Tests
# =============================================================================


class TestRegression:
    """Regression tests to ensure old function still works."""

    def test_old_extract_final_states_still_works(self):
        """_extract_final_states() returns state_after (backward compat)."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance",
                       state_after={"has_insurance": False, "flood_zone": "HIGH"}),
            make_trace("H001", year=3, action="do_nothing",
                       state_after={"has_insurance": False, "flood_zone": "HIGH"}),
        ]
        old_states = _extract_final_states(traces)
        # Old function reads state_after directly — still False (bug we know about)
        assert old_states["H001"]["has_insurance"] is False

        # New function infers from decisions — True (the fix)
        new_states = _extract_final_states_from_decisions(traces)
        assert new_states["H001"]["has_insurance"] is True

    def test_decision_based_vs_state_based_divergence(self):
        """Demonstrate the bug: state_after never updated, decisions show truth."""
        traces = [
            make_trace("H001", year=1, action="buy_insurance",
                       state_after={"has_insurance": False}),
            make_trace("H002", year=1, action="elevate_house",
                       state_after={"elevated": False}),
            make_trace("H003", year=1, action="buyout_program",
                       state_after={"bought_out": False}),
        ]

        old = _extract_final_states(traces)
        new = _extract_final_states_from_decisions(traces)

        # Old: all False (the bug)
        assert old["H001"]["has_insurance"] is False
        assert old["H002"].get("elevated", False) is False
        assert old["H003"].get("bought_out", False) is False

        # New: correctly True (the fix)
        assert new["H001"]["has_insurance"] is True
        assert new["H002"]["elevated"] is True
        assert new["H003"]["bought_out"] is True


# =============================================================================
# Normalization Tests (sanity checks for _normalize_action)
# =============================================================================


class TestNormalizeAction:
    """Verify action normalization used by decision inference."""

    @pytest.mark.parametrize("raw,expected", [
        ("buy_insurance", "buy_insurance"),
        ("buy_contents_insurance", "buy_insurance"),
        ("purchase_insurance", "buy_insurance"),
        ("elevate_house", "elevate"),
        ("elevate_home", "elevate"),
        ("home_elevation", "elevate"),
        ("buyout_program", "buyout"),
        ("voluntary_buyout", "buyout"),
        ("relocate", "relocate"),
        ("do_nothing", "do_nothing"),
        ("no_action", "do_nothing"),
        ("retrofit", "retrofit"),
    ])
    def test_normalization(self, raw, expected):
        assert _normalize_action(raw) == expected

    def test_dict_input(self):
        assert _normalize_action({"skill_name": "buy_insurance"}) == "buy_insurance"

    def test_none_input(self):
        assert _normalize_action(None) == "do_nothing"
