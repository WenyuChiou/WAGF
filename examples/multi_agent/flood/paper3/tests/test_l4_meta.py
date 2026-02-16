"""Tests for L4 meta-validation Wasserstein distance (P2.2)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import pytest
from validation.metrics.l4_meta import (
    wasserstein_categorical,
    cross_run_stability,
    empirical_distance,
    compute_l4_meta,
    _normalize_counts_to_dist,
)


class TestWassersteinCategorical:
    def test_identical_distributions(self):
        d = {"a": 0.5, "b": 0.3, "c": 0.2}
        assert wasserstein_categorical(d, d) == 0.0

    def test_total_variation_unordered(self):
        """Without category_order, uses TV distance / 2."""
        sim = {"a": 0.6, "b": 0.4}
        ref = {"a": 0.4, "b": 0.6}
        # TV = |0.6-0.4| + |0.4-0.6| = 0.4, distance = 0.2
        assert wasserstein_categorical(sim, ref) == 0.2

    def test_ordinal_emd(self):
        """With category_order, uses cumulative EMD."""
        sim = {"low": 0.5, "mid": 0.3, "high": 0.2}
        ref = {"low": 0.2, "mid": 0.3, "high": 0.5}
        # CDF diffs: |0.5-0.2|=0.3, |0.8-0.5|=0.3, |1.0-1.0|=0.0 → sum=0.6
        d = wasserstein_categorical(sim, ref, category_order=["low", "mid", "high"])
        assert d == pytest.approx(0.6, abs=1e-6)

    def test_missing_categories(self):
        """Categories present in one but not the other."""
        sim = {"a": 0.5, "b": 0.5}
        ref = {"a": 0.5, "c": 0.5}
        d = wasserstein_categorical(sim, ref)
        # TV = |0| + |0.5| + |0.5| = 1.0, distance = 0.5
        assert d == 0.5

    def test_dirac_distributions(self):
        sim = {"a": 1.0}
        ref = {"b": 1.0}
        d = wasserstein_categorical(sim, ref)
        # TV = 2.0, distance = 1.0
        assert d == 1.0


class TestNormalizeCounts:
    def test_basic(self):
        d = _normalize_counts_to_dist({"a": 3, "b": 7})
        assert d["a"] == pytest.approx(0.3)
        assert d["b"] == pytest.approx(0.7)

    def test_empty(self):
        assert _normalize_counts_to_dist({}) == {}

    def test_single(self):
        d = _normalize_counts_to_dist({"x": 100})
        assert d["x"] == 1.0


class TestCrossRunStability:
    def test_identical_runs(self):
        d = {"a": 0.5, "b": 0.5}
        result = cross_run_stability([d, d, d])
        assert result.mean_pairwise_distance == 0.0
        assert result.is_stable

    def test_diverse_runs(self):
        runs = [
            {"a": 0.9, "b": 0.1},
            {"a": 0.1, "b": 0.9},
        ]
        result = cross_run_stability(runs)
        assert result.mean_pairwise_distance > 0
        assert result.n_runs == 2
        assert len(result.pairwise_distances) == 1

    def test_single_run(self):
        result = cross_run_stability([{"a": 0.5, "b": 0.5}])
        assert result.mean_pairwise_distance == 0.0
        assert result.is_stable
        assert result.n_runs == 1

    def test_three_runs_pairwise_count(self):
        runs = [{"a": 0.5, "b": 0.5}] * 3
        result = cross_run_stability(runs)
        # C(3,2) = 3 pairs
        assert len(result.pairwise_distances) == 3

    def test_unstable_runs(self):
        runs = [
            {"a": 1.0},
            {"b": 1.0},
            {"c": 1.0},
        ]
        result = cross_run_stability(runs, threshold=0.05)
        assert not result.is_stable


class TestEmpiricalDistance:
    def test_from_counts(self):
        sim = {"ins": 60, "none": 40}
        ref = {"ins": 50, "none": 50}
        d = empirical_distance(sim, ref)
        assert d > 0

    def test_identical_counts(self):
        c = {"a": 10, "b": 20}
        assert empirical_distance(c, c) == 0.0


class TestComputeL4Meta:
    def test_with_reference(self):
        sim = {"buy_insurance": 100, "do_nothing": 50, "elevate": 50}
        ref = {"buy_insurance": 80, "do_nothing": 60, "elevate": 60}
        report = compute_l4_meta(sim, reference_action_counts=ref)
        assert report.action_distance >= 0
        assert isinstance(report.passes, bool)

    def test_without_reference(self):
        sim = {"buy_insurance": 100}
        report = compute_l4_meta(sim)
        assert report.action_distance == -1.0
        assert report.passes is False

    def test_with_cross_run(self):
        sim = {"a": 50, "b": 50}
        runs = [
            {"a": 0.5, "b": 0.5},
            {"a": 0.48, "b": 0.52},
            {"a": 0.51, "b": 0.49},
        ]
        report = compute_l4_meta(sim, run_distributions=runs)
        assert report.cross_run is not None
        assert report.cross_run.n_runs == 3
        assert report.cross_run.is_stable

    def test_passes_close_distributions(self):
        sim = {"a": 50, "b": 50}
        ref = {"a": 48, "b": 52}
        report = compute_l4_meta(sim, reference_action_counts=ref)
        assert report.passes  # Very close → distance < 0.15
