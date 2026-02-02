"""Tests for Level 2 MACRO validators: distribution_matcher.py.

Validates:
    - KS test, Wasserstein distance, Chi-squared GoF
    - PEBA feature extraction and comparison
    - Echo chamber detection
    - MA-EBE decomposition
"""

import pytest
import numpy as np
import pandas as pd

from broker.validators.calibration.distribution_matcher import (
    DistributionMatcher,
    DistributionTestResult,
    PEBAFeatures,
    MacroReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def matcher():
    return DistributionMatcher(alpha=0.05, echo_threshold=0.8)


@pytest.fixture
def simulation_df():
    """Simulated flood decisions for 50 agents over 5 years."""
    rng = np.random.RandomState(42)
    rows = []
    actions = ["elevate_house", "buy_insurance", "do_nothing", "relocate"]
    for year in range(1, 6):
        for agent_id in range(1, 51):
            # Gradually increasing adoption
            adopt_prob = 0.3 + 0.1 * year
            if rng.random() < adopt_prob:
                decision = rng.choice(["elevate_house", "buy_insurance", "relocate"])
            else:
                decision = "do_nothing"

            rows.append({
                "agent_id": f"a_{agent_id:03d}",
                "year": year,
                "yearly_decision": decision,
                "agent_type": "household" if agent_id <= 45 else "government",
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# KS test
# ---------------------------------------------------------------------------

class TestKSTest:
    """Kolmogorov-Smirnov test."""

    def test_identical_distributions(self, matcher):
        """Same distribution should not be significant."""
        data = np.random.normal(0, 1, 100)
        result = matcher.ks_test(data, data, label="identical")
        assert result.p_value > 0.05
        assert not result.significant

    def test_different_distributions(self, matcher):
        """Different distributions should be significant."""
        sim = np.random.normal(0, 1, 200)
        ref = np.random.normal(3, 1, 200)
        result = matcher.ks_test(sim, ref, label="different")
        assert result.p_value < 0.05
        assert result.significant
        assert result.statistic > 0.3

    def test_ks_label(self, matcher):
        """Label should be in test name."""
        result = matcher.ks_test(np.array([1, 2, 3]), np.array([1, 2, 3]),
                                 label="adoption")
        assert "adoption" in result.test_name

    def test_ks_result_to_dict(self, matcher):
        """Result serialization."""
        result = matcher.ks_test(np.array([1, 2]), np.array([1, 2]))
        d = result.to_dict()
        assert "test_name" in d
        assert "statistic" in d
        assert "p_value" in d


# ---------------------------------------------------------------------------
# Wasserstein distance
# ---------------------------------------------------------------------------

class TestWasserstein:
    """Wasserstein (earth mover) distance."""

    def test_identical_zero_distance(self, matcher):
        """Same distribution should have ~0 distance."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = matcher.wasserstein_distance(data, data, label="same")
        assert result.statistic == pytest.approx(0.0, abs=1e-10)

    def test_shifted_distribution(self, matcher):
        """Shifted distribution should have distance = shift amount."""
        data1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        data2 = data1 + 2.0
        result = matcher.wasserstein_distance(data1, data2)
        assert result.statistic == pytest.approx(2.0, abs=0.1)

    def test_no_p_value(self, matcher):
        """Wasserstein has no p-value (distance metric only)."""
        result = matcher.wasserstein_distance(
            np.array([1, 2, 3]), np.array([4, 5, 6])
        )
        assert result.p_value is None


# ---------------------------------------------------------------------------
# Chi-squared GoF
# ---------------------------------------------------------------------------

class TestChi2:
    """Chi-squared goodness-of-fit test."""

    def test_matching_proportions(self, matcher):
        """Observed matching expected should not be significant."""
        observed = {"elevate": 25, "insure": 25, "nothing": 25, "relocate": 25}
        expected = {"elevate": 0.25, "insure": 0.25, "nothing": 0.25,
                    "relocate": 0.25}
        result = matcher.chi2_gof(observed, expected, label="actions")
        assert result.p_value > 0.05
        assert not result.significant

    def test_mismatching_proportions(self, matcher):
        """Highly skewed observed vs uniform expected should be significant."""
        observed = {"elevate": 90, "insure": 5, "nothing": 3, "relocate": 2}
        expected = {"elevate": 0.25, "insure": 0.25, "nothing": 0.25,
                    "relocate": 0.25}
        result = matcher.chi2_gof(observed, expected, label="actions")
        assert result.p_value < 0.05
        assert result.significant

    def test_empty_observations(self, matcher):
        """Empty observations should handle gracefully."""
        result = matcher.chi2_gof({}, {"a": 0.5, "b": 0.5})
        assert result.statistic == 0.0
        assert result.p_value == 1.0

    def test_missing_categories(self, matcher):
        """Categories in expected but not observed should be handled."""
        observed = {"a": 50, "b": 50}
        expected = {"a": 0.3, "b": 0.3, "c": 0.4}
        result = matcher.chi2_gof(observed, expected, label="partial")
        assert "c" in result.details["categories"]


# ---------------------------------------------------------------------------
# PEBA features
# ---------------------------------------------------------------------------

class TestPEBA:
    """PEBA distributional feature extraction."""

    def test_normal_features(self, matcher):
        """Normal distribution features."""
        rng = np.random.RandomState(42)
        data = rng.normal(loc=5.0, scale=2.0, size=1000)
        features = matcher.extract_peba_features(data, label="normal")
        assert features.mean == pytest.approx(5.0, abs=0.2)
        assert features.variance == pytest.approx(4.0, abs=0.5)
        assert abs(features.skewness) < 0.3
        assert features.n == 1000
        assert features.label == "normal"

    def test_peba_distance(self, matcher):
        """Distance between same distribution should be ~0."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        f1 = matcher.extract_peba_features(data, label="a")
        f2 = matcher.extract_peba_features(data, label="b")
        assert f1.distance_to(f2) == pytest.approx(0.0, abs=1e-10)

    def test_compare_peba(self, matcher):
        """Compare PEBA features between two distributions."""
        rng = np.random.RandomState(42)
        sim = rng.normal(5, 2, 100)
        ref = rng.normal(5, 2, 100)
        sim_f, ref_f, dist = matcher.compare_peba(sim, ref)
        assert dist < 2.0  # Same distribution, distance should be small

    def test_small_sample(self, matcher):
        """Small samples (n<4) should still return features."""
        data = np.array([1.0, 2.0])
        features = matcher.extract_peba_features(data)
        assert features.n == 2
        assert features.skewness == 0.0  # Not enough data

    def test_to_dict(self, matcher):
        """Feature serialization."""
        features = matcher.extract_peba_features(np.array([1, 2, 3, 4, 5]))
        d = features.to_dict()
        assert "mean" in d
        assert "variance" in d
        assert "skewness" in d
        assert "kurtosis" in d


# ---------------------------------------------------------------------------
# Echo chamber
# ---------------------------------------------------------------------------

class TestEchoChamber:
    """Echo chamber detection."""

    def test_no_echo_chamber(self, matcher, simulation_df):
        """Diverse decisions should not trigger echo chamber."""
        rate = matcher.compute_echo_chamber_rate(simulation_df)
        assert rate < 1.0

    def test_full_echo_chamber(self, matcher):
        """All agents choosing same action should be 100% echo chamber."""
        rows = [
            {"agent_id": f"a_{i}", "year": y, "yearly_decision": "do_nothing"}
            for y in range(1, 4) for i in range(1, 11)
        ]
        df = pd.DataFrame(rows)
        rate = matcher.compute_echo_chamber_rate(df)
        assert rate == 1.0


# ---------------------------------------------------------------------------
# EBE decomposition
# ---------------------------------------------------------------------------

class TestEBEDecomposition:
    """EBE decomposition by agent type."""

    def test_decomposition_exists(self, matcher, simulation_df):
        """Decomposition should return per-type EBE."""
        result = matcher.compute_ebe_decomposition(simulation_df)
        assert "household" in result
        assert "government" in result
        for ebe in result.values():
            assert 0 <= ebe <= 1.0

    def test_decomposition_no_type_col(self, matcher):
        """Missing agent_type column returns empty dict."""
        df = pd.DataFrame({
            "agent_id": ["a1"], "year": [1],
            "yearly_decision": ["do_nothing"],
        })
        result = matcher.compute_ebe_decomposition(df)
        assert result == {}


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------

class TestMacroReport:
    """Full Level-2 macro report."""

    def test_report_without_reference(self, matcher, simulation_df):
        """Report without reference data still has echo + EBE."""
        report = matcher.compute_full_report(simulation_df)
        assert isinstance(report, MacroReport)
        assert 0 <= report.echo_chamber_rate <= 1.0
        assert len(report.ebe_decomposition) > 0

    def test_report_with_reference(self, matcher, simulation_df):
        """Report with reference data includes KS, Wasserstein, chi2."""
        ref_data = {
            "adoption_rates": np.linspace(0.3, 0.7, 5),
            "action_proportions": {
                "elevate_house": 0.2, "buy_insurance": 0.3,
                "do_nothing": 0.4, "relocate": 0.1,
            },
            "adoption_timeseries": np.linspace(0.3, 0.7, 5),
        }
        report = matcher.compute_full_report(
            simulation_df, reference_data=ref_data,
        )
        assert len(report.ks_results) > 0
        assert len(report.chi2_results) > 0
        assert report.peba_distance is not None

    def test_report_to_dict(self, matcher, simulation_df):
        """Report serialization."""
        report = matcher.compute_full_report(simulation_df)
        d = report.to_dict()
        assert "ks_results" in d
        assert "echo_chamber_rate" in d
        assert "ebe_decomposition" in d
