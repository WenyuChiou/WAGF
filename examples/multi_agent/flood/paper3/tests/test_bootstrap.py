"""Tests for Bootstrap Confidence Interval module."""

import sys
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
ANALYSIS_DIR = SCRIPT_DIR.parent / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import pytest
import numpy as np

from validation.metrics.bootstrap import bootstrap_ci


# =============================================================================
# Basic Functionality
# =============================================================================

class TestBootstrapCI:
    def test_output_structure(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = bootstrap_ci(data, np.mean, n_bootstrap=100, seed=42)
        assert "point_estimate" in result
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert "ci_level" in result
        assert "std" in result
        assert "n_bootstrap" in result
        assert len(result["samples"]) == 100

    def test_ci_contains_point_estimate(self):
        data = list(range(100))
        result = bootstrap_ci(data, np.mean, n_bootstrap=500, seed=0)
        assert result["ci_lower"] <= result["point_estimate"] <= result["ci_upper"]

    def test_ci_level(self):
        data = list(range(100))
        result = bootstrap_ci(data, np.mean, n_bootstrap=200, ci=0.90, seed=0)
        assert result["ci_level"] == 0.90

    def test_narrow_ci_for_constant_data(self):
        data = [5.0] * 50
        result = bootstrap_ci(data, np.mean, n_bootstrap=100, seed=0)
        assert result["ci_lower"] == result["ci_upper"] == 5.0
        assert result["std"] == 0.0

    def test_wider_ci_for_variable_data(self):
        rng = np.random.default_rng(42)
        data = list(rng.normal(50, 10, size=100))
        result = bootstrap_ci(data, np.mean, n_bootstrap=500, seed=0)
        ci_width = result["ci_upper"] - result["ci_lower"]
        assert ci_width > 0

    def test_reproducibility(self):
        data = list(range(50))
        r1 = bootstrap_ci(data, np.mean, n_bootstrap=100, seed=42)
        r2 = bootstrap_ci(data, np.mean, n_bootstrap=100, seed=42)
        assert r1["samples"] == r2["samples"]

    def test_empty_data(self):
        result = bootstrap_ci([], np.mean, n_bootstrap=100)
        assert result["point_estimate"] == 0.0
        assert result["samples"] == []


# =============================================================================
# With Extractor
# =============================================================================

class TestBootstrapWithExtractor:
    def test_extractor_function(self):
        data = [{"value": 1}, {"value": 2}, {"value": 3}, {"value": 4}]

        def metric_fn(d):
            return {"mean_val": np.mean([x["value"] for x in d])}

        result = bootstrap_ci(
            data, metric_fn, n_bootstrap=50, seed=0,
            extractor=lambda r: r["mean_val"]
        )
        assert result["point_estimate"] == 2.5
        assert len(result["samples"]) == 50

    def test_with_kwargs(self):
        data = list(range(20))

        def percentile_fn(d, q=50):
            return float(np.percentile(d, q))

        result = bootstrap_ci(data, percentile_fn, n_bootstrap=50, seed=0, q=75)
        assert result["point_estimate"] > 0


# =============================================================================
# Integration with L1 Metrics
# =============================================================================

class TestBootstrapL1Integration:
    def test_cacr_bootstrap(self):
        """Test bootstrap CI on CACR using L1 compute function."""
        from validation.metrics.l1_micro import compute_l1_metrics

        traces = [
            {
                "skill_proposal": {"reasoning": {"TP_LABEL": "VH", "CP_LABEL": "VH"}, "skill_name": "buy_insurance"},
                "approved_skill": {"skill_name": "buy_insurance"},
                "state_before": {"flood_zone": "HIGH"},
            },
        ] * 20

        result = bootstrap_ci(
            traces, compute_l1_metrics, n_bootstrap=50, seed=0,
            extractor=lambda m: m.cacr, agent_type="owner"
        )
        # All identical traces → no variance
        assert result["point_estimate"] == 1.0
        assert result["ci_lower"] == 1.0
