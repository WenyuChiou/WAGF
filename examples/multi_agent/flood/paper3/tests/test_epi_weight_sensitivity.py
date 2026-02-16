"""Tests for EPI weight sensitivity analysis (P1.1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from validation.metrics.l2_macro import epi_weight_sensitivity


def _make_benchmark_results():
    """Create realistic benchmark results for testing."""
    return {
        "insurance_rate_sfha": {
            "value": 0.45, "range": (0.30, 0.60), "in_range": True, "weight": 1.0,
        },
        "insurance_rate_all": {
            "value": 0.35, "range": (0.15, 0.55), "in_range": True, "weight": 0.8,
        },
        "elevation_rate": {
            "value": 0.20, "range": (0.10, 0.35), "in_range": True, "weight": 1.0,
        },
        "buyout_rate": {
            "value": 0.10, "range": (0.05, 0.25), "in_range": True, "weight": 0.8,
        },
        "do_nothing_rate_postflood": {
            "value": 0.50, "range": (0.35, 0.65), "in_range": True, "weight": 1.5,
        },
        "mg_adaptation_gap": {
            "value": 0.40, "range": (0.05, 0.30), "in_range": False, "weight": 2.0,
        },
        "renter_uninsured_rate": {
            "value": 0.25, "range": (0.15, 0.40), "in_range": True, "weight": 1.0,
        },
        "insurance_lapse_rate": {
            "value": 0.20, "range": (0.15, 0.30), "in_range": True, "weight": 1.0,
        },
    }


class TestEpiWeightSensitivity:
    def test_returns_three_schemes(self):
        results = epi_weight_sensitivity(_make_benchmark_results())
        assert set(results.keys()) == {"equal", "current", "relaxed"}

    def test_each_scheme_has_epi_and_passes(self):
        results = epi_weight_sensitivity(_make_benchmark_results())
        for scheme_name, r in results.items():
            assert "epi" in r
            assert "passes" in r
            assert "weights" in r
            assert 0.0 <= r["epi"] <= 1.0

    def test_equal_weights_all_one(self):
        results = epi_weight_sensitivity(_make_benchmark_results())
        for w in results["equal"]["weights"].values():
            assert w == 1.0

    def test_current_preserves_original_weights(self):
        br = _make_benchmark_results()
        results = epi_weight_sensitivity(br)
        for name, w in results["current"]["weights"].items():
            assert w == br[name]["weight"]

    def test_relaxed_halves_heavy_weights(self):
        """Weights > 1.0 are halved (capped at 1.0); others unchanged."""
        results = epi_weight_sensitivity(_make_benchmark_results())
        relaxed = results["relaxed"]["weights"]
        # mg_adaptation_gap: 2.0 → 1.0 (halved)
        assert relaxed["mg_adaptation_gap"] == 1.0
        # do_nothing_rate_postflood: 1.5 → 0.75 (halved)
        assert relaxed["do_nothing_rate_postflood"] == 0.75
        # insurance_rate_sfha: 1.0 → 1.0 (unchanged, not > 1.0)
        assert relaxed["insurance_rate_sfha"] == 1.0

    def test_equal_epi_differs_from_current(self):
        """Equal and current weights give different EPI when weights differ."""
        results = epi_weight_sensitivity(_make_benchmark_results())
        assert results["equal"]["epi"] != results["current"]["epi"]

    def test_all_passing_benchmarks(self):
        """When all benchmarks pass, all schemes should give EPI=1.0."""
        br = {
            "b1": {"value": 0.5, "range": (0.3, 0.7), "in_range": True, "weight": 1.0},
            "b2": {"value": 0.4, "range": (0.2, 0.6), "in_range": True, "weight": 2.0},
        }
        results = epi_weight_sensitivity(br)
        for scheme_name, r in results.items():
            assert r["epi"] == 1.0
            assert r["passes"] is True

    def test_empty_benchmarks(self):
        results = epi_weight_sensitivity({})
        for scheme_name, r in results.items():
            assert r["epi"] == 0.0
            assert r["passes"] is False
