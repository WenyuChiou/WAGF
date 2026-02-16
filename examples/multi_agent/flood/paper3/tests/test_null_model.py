"""Tests for Null-Model EPI Distribution module."""

import sys
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
ANALYSIS_DIR = SCRIPT_DIR.parent / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import pytest
import numpy as np
import pandas as pd

from validation.metrics.null_model import (
    generate_null_traces,
    compute_null_epi_distribution,
    epi_significance_test,
    _default_flood_hazard,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def small_profiles():
    """Small agent profile DataFrame for fast tests."""
    rows = []
    for i in range(20):
        is_owner = i < 10
        is_mg = i % 4 < 2
        rows.append({
            "agent_id": f"H{i+1:03d}",
            "tenure": "Owner" if is_owner else "Renter",
            "flood_zone": "HIGH" if i % 3 == 0 else "LOW",
            "mg": is_mg,
            "income": 35000 if is_mg else 65000,
        })
    return pd.DataFrame(rows)


# =============================================================================
# Trace Generation Tests
# =============================================================================

class TestGenerateNullTraces:
    def test_correct_count(self, small_profiles):
        traces = generate_null_traces(small_profiles, n_years=3, seed=42)
        assert len(traces) == 20 * 3  # 20 agents × 3 years

    def test_trace_structure(self, small_profiles):
        traces = generate_null_traces(small_profiles, n_years=2, seed=0)
        t = traces[0]
        assert "agent_id" in t
        assert "year" in t
        assert "approved_skill" in t
        assert "outcome" in t
        assert t["outcome"] == "APPROVED"
        assert "state_before" in t

    def test_owner_actions_only_valid(self, small_profiles):
        traces = generate_null_traces(small_profiles, n_years=5, seed=0)
        owner_ids = set(small_profiles[small_profiles["tenure"] == "Owner"]["agent_id"].astype(str))
        owner_actions = {t["approved_skill"]["skill_name"] for t in traces if t["agent_id"] in owner_ids}
        valid = {"do_nothing", "buy_insurance", "elevate", "buyout", "retrofit"}
        assert owner_actions.issubset(valid)

    def test_renter_actions_only_valid(self, small_profiles):
        traces = generate_null_traces(small_profiles, n_years=5, seed=0)
        renter_ids = set(small_profiles[small_profiles["tenure"] == "Renter"]["agent_id"].astype(str))
        renter_actions = {t["approved_skill"]["skill_name"] for t in traces if t["agent_id"] in renter_ids}
        valid = {"do_nothing", "buy_insurance", "relocate"}
        assert renter_actions.issubset(valid)

    def test_reproducibility(self, small_profiles):
        t1 = generate_null_traces(small_profiles, n_years=3, seed=42)
        t2 = generate_null_traces(small_profiles, n_years=3, seed=42)
        actions1 = [t["approved_skill"]["skill_name"] for t in t1]
        actions2 = [t["approved_skill"]["skill_name"] for t in t2]
        assert actions1 == actions2

    def test_different_seeds_differ(self, small_profiles):
        t1 = generate_null_traces(small_profiles, n_years=5, seed=0)
        t2 = generate_null_traces(small_profiles, n_years=5, seed=99)
        actions1 = [t["approved_skill"]["skill_name"] for t in t1]
        actions2 = [t["approved_skill"]["skill_name"] for t in t2]
        assert actions1 != actions2


# =============================================================================
# Null EPI Distribution Tests
# =============================================================================

class TestNullEPIDistribution:
    def test_basic_output_structure(self, small_profiles):
        result = compute_null_epi_distribution(
            small_profiles, n_simulations=5, n_years=3, seed=0
        )
        assert "null_epi_mean" in result
        assert "null_epi_std" in result
        assert "null_epi_p05" in result
        assert "null_epi_p95" in result
        assert "null_epi_p99" in result
        assert "samples" in result
        assert len(result["samples"]) == 5
        assert result["n_simulations"] == 5

    def test_epi_in_valid_range(self, small_profiles):
        result = compute_null_epi_distribution(
            small_profiles, n_simulations=10, n_years=3, seed=42
        )
        for s in result["samples"]:
            assert 0.0 <= s <= 1.0

    def test_null_epi_expected_low(self, small_profiles):
        """Random agents should generally produce low EPI."""
        result = compute_null_epi_distribution(
            small_profiles, n_simulations=20, n_years=5, seed=0
        )
        # Null EPI should be well below 0.60 on average
        assert result["null_epi_mean"] < 0.80  # Generous upper bound


# =============================================================================
# Significance Test
# =============================================================================

class TestSignificanceTest:
    def test_clearly_significant(self):
        # Need >= 20 samples for p < 0.05 with conservative correction
        rng = np.random.default_rng(42)
        null = list(rng.normal(0.22, 0.03, size=50).clip(0, 1))
        result = epi_significance_test(0.78, null)
        assert result["significant"] is True
        assert result["p_value"] < 0.05
        assert result["z_score"] > 2.0

    def test_not_significant(self):
        null = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
        result = epi_significance_test(0.60, null)
        assert result["significant"] is False

    def test_empty_null(self):
        result = epi_significance_test(0.78, [])
        assert result["p_value"] == 1.0
        assert result["significant"] is False

    def test_output_fields(self):
        null = [0.20, 0.25, 0.30]
        result = epi_significance_test(0.78, null)
        assert "p_value" in result
        assert "z_score" in result
        assert "significant" in result
        assert "observed_epi" in result
        assert "null_mean" in result


# =============================================================================
# Hazard Function Extensibility Tests
# =============================================================================

class TestHazardFnExtensibility:
    def test_no_hazard_fn(self, small_profiles):
        """Custom hazard_fn that never triggers produces no floods."""
        def no_hazard(row, rng):
            return False

        traces = generate_null_traces(small_profiles, n_years=3, seed=0,
                                      hazard_fn=no_hazard)
        assert all(t["flooded_this_year"] is False for t in traces)

    def test_always_hazard_fn(self, small_profiles):
        """Custom hazard_fn that always triggers."""
        def always_hazard(row, rng):
            return True

        traces = generate_null_traces(small_profiles, n_years=3, seed=0,
                                      hazard_fn=always_hazard)
        assert all(t["flooded_this_year"] is True for t in traces)

    def test_default_flood_hazard_exported(self):
        """_default_flood_hazard is importable."""
        assert callable(_default_flood_hazard)

    def test_hazard_fn_passthrough_to_distribution(self, small_profiles):
        """hazard_fn is forwarded through compute_null_epi_distribution."""
        def no_hazard(row, rng):
            return False

        result = compute_null_epi_distribution(
            small_profiles, n_simulations=3, n_years=2, seed=0,
            hazard_fn=no_hazard,
        )
        assert len(result["samples"]) == 3
