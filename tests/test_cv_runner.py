"""Tests for CVRunner — three-level C&V orchestrator.

Validates:
    - CVRunner.run_posthoc() integration with all Level 1-2 validators
    - CVReport serialization and summary
    - Group comparison functionality
"""

import pytest
import numpy as np
import pandas as pd

from broker.validators.calibration.cv_runner import CVRunner, CVReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simulation_df():
    """Standard flood simulation DataFrame for CVRunner tests."""
    rng = np.random.RandomState(42)
    rows = []
    actions = ["elevate_house", "buy_insurance", "do_nothing", "relocate"]

    for year in range(1, 6):
        for agent_id in range(1, 21):
            # Higher threat in later years
            if year >= 3:
                ta = rng.choice(["H", "VH", "M"])
                ca = rng.choice(["M", "H"])
                decision = rng.choice(["elevate_house", "buy_insurance"])
            else:
                ta = rng.choice(["L", "M"])
                ca = rng.choice(["M", "H", "VH"])
                decision = rng.choice(["do_nothing", "buy_insurance"])

            rows.append({
                "agent_id": f"h_{agent_id:03d}",
                "year": year,
                "threat_appraisal": ta,
                "coping_appraisal": ca,
                "ta_level": ta,
                "ca_level": ca,
                "yearly_decision": decision,
                "elevated": year >= 4 and agent_id <= 5,
                "relocated": False,
                "has_insurance": decision == "buy_insurance",
                "reasoning": f"Given threat level {ta} and coping {ca}, "
                             f"I assess the flood depth risk and my income "
                             f"to decide on {decision}.",
            })

    return pd.DataFrame(rows)


@pytest.fixture
def runner(simulation_df):
    """CVRunner initialized with in-memory DataFrame."""
    r = CVRunner(
        framework="pmt",
        ta_col="threat_appraisal",
        ca_col="coping_appraisal",
        group="B",
        start_year=2,
    )
    r._df = simulation_df
    return r


# ---------------------------------------------------------------------------
# Post-hoc analysis tests
# ---------------------------------------------------------------------------

class TestRunPosthoc:
    """Tests for run_posthoc() integration."""

    def test_full_posthoc(self, runner):
        """Full post-hoc analysis should complete without errors."""
        report = runner.run_posthoc()
        assert isinstance(report, CVReport)
        assert report.micro is not None
        assert report.temporal is not None
        assert report.rh_metrics is not None
        assert report.macro is not None

    def test_micro_only(self, runner):
        """Run only Level 1."""
        report = runner.run_posthoc(levels=[1])
        assert report.micro is not None
        assert report.temporal is not None
        assert report.macro is None

    def test_macro_only(self, runner):
        """Run only Level 2."""
        report = runner.run_posthoc(levels=[2])
        assert report.micro is None
        assert report.macro is not None

    def test_cacr_in_report(self, runner):
        """CACR should be in micro report."""
        report = runner.run_posthoc(levels=[1])
        assert 0 <= report.micro.cacr <= 1.0
        assert report.micro.n_observations > 0

    def test_rh_in_report(self, runner):
        """R_H metrics should include ebe."""
        report = runner.run_posthoc(levels=[1])
        assert "rh" in report.rh_metrics
        assert "ebe" in report.rh_metrics
        assert 0 <= report.rh_metrics["rh"] <= 1.0

    def test_temporal_in_report(self, runner):
        """TCS should be in temporal report."""
        report = runner.run_posthoc(levels=[1])
        assert 0 <= report.temporal.overall_tcs <= 1.0


# ---------------------------------------------------------------------------
# Report tests
# ---------------------------------------------------------------------------

class TestCVReport:
    """Tests for CVReport data class."""

    def test_to_dict(self, runner):
        """Report should serialize to dict."""
        report = runner.run_posthoc()
        d = report.to_dict()
        assert "metadata" in d
        assert "level1_micro" in d
        assert "level2_macro" in d

    def test_summary(self, runner):
        """Summary should contain key metrics."""
        report = runner.run_posthoc()
        s = report.summary
        assert "CACR" in s
        assert "R_H" in s
        assert "EBE" in s
        assert "TCS" in s
        assert "echo_chamber" in s

    def test_metadata(self, runner):
        """Metadata should include group and framework."""
        report = runner.run_posthoc()
        assert report.metadata["group"] == "B"
        assert report.metadata["framework"] == "pmt"
        assert report.metadata["n_agents"] == 20
        assert report.metadata["n_years"] == 5


# ---------------------------------------------------------------------------
# Group comparison tests
# ---------------------------------------------------------------------------

class TestGroupComparison:
    """Tests for cross-group comparison."""

    def test_compare_groups(self, runner, simulation_df):
        """Compare two groups should produce a DataFrame."""
        report_b = runner.run_posthoc()

        # Create a "Group A" report with same data (different label)
        runner_a = CVRunner(framework="pmt", group="A", start_year=2)
        runner_a._df = simulation_df
        report_a = runner_a.run_posthoc()

        comparison = CVRunner.compare_groups({
            "Group A": report_a,
            "Group B": report_b,
        })
        assert isinstance(comparison, pd.DataFrame)
        assert len(comparison) == 2
        assert "CACR" in comparison.columns
        assert "R_H" in comparison.columns
        assert "group_label" in comparison.columns
