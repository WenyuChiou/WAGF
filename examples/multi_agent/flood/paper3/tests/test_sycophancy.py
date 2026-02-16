"""Tests for sycophancy testing module (P2.3)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import pytest
from validation.metrics.sycophancy import (
    SycophancyProbe,
    SycophancyReport,
    build_probes,
    evaluate_sycophancy,
)


class TestBuildProbes:
    def test_default_probes(self):
        scenarios = [{"flood_zone": "HIGH", "mg": True}]
        probes = build_probes(scenarios)
        # 1 scenario × 3 actions × 3 nudge_types = 9
        assert len(probes) == 9

    def test_custom_actions(self):
        scenarios = [{"flood_zone": "LOW"}]
        probes = build_probes(scenarios, target_actions=["buyout", "relocate"])
        # 1 × 2 × 3 = 6
        assert len(probes) == 6

    def test_custom_nudge_types(self):
        scenarios = [{"flood_zone": "HIGH"}]
        probes = build_probes(scenarios, nudge_types=["authority"])
        # 1 × 3 × 1 = 3
        assert len(probes) == 3

    def test_probe_ids_unique(self):
        scenarios = [{"a": 1}, {"b": 2}]
        probes = build_probes(scenarios)
        ids = [p.probe_id for p in probes]
        assert len(ids) == len(set(ids))

    def test_nudge_text_contains_action(self):
        probes = build_probes(
            [{"flood_zone": "HIGH"}],
            target_actions=["buy_insurance"],
            nudge_types=["authority"],
        )
        assert "insurance" in probes[0].nudge_text.lower()

    def test_multiple_scenarios(self):
        scenarios = [{"x": 1}, {"x": 2}, {"x": 3}]
        probes = build_probes(scenarios, target_actions=["do_nothing"], nudge_types=["anchoring"])
        assert len(probes) == 3


class TestEvaluateSycophancy:
    def _make_probes(self, n=6):
        return build_probes(
            [{"flood_zone": "HIGH"}, {"flood_zone": "LOW"}],
            target_actions=["buy_insurance"],
            nudge_types=["authority", "anchoring", "contradictory"],
        )

    def test_no_flips(self):
        probes = self._make_probes()
        baseline = ["do_nothing"] * len(probes)
        nudged = ["do_nothing"] * len(probes)
        report = evaluate_sycophancy(probes, baseline, nudged)
        assert report.flip_rate == 0.0
        assert report.passes

    def test_all_flipped(self):
        probes = self._make_probes()
        baseline = ["do_nothing"] * len(probes)
        nudged = ["buy_insurance"] * len(probes)  # all flip to target
        report = evaluate_sycophancy(probes, baseline, nudged)
        assert report.flip_rate == 1.0
        assert report.flip_to_target_rate == 1.0
        assert not report.passes

    def test_partial_flips(self):
        probes = self._make_probes()
        n = len(probes)
        baseline = ["do_nothing"] * n
        # First probe flips, rest don't
        nudged = ["buy_insurance"] + ["do_nothing"] * (n - 1)
        report = evaluate_sycophancy(probes, baseline, nudged)
        assert 0 < report.flip_rate < 1.0
        assert report.total_probes == n

    def test_flip_not_to_target(self):
        """Flip to different action than target."""
        probes = self._make_probes()
        baseline = ["do_nothing"] * len(probes)
        nudged = ["elevate"] * len(probes)  # flipped but NOT to target
        report = evaluate_sycophancy(probes, baseline, nudged)
        assert report.flip_rate == 1.0
        assert report.flip_to_target_rate == 0.0

    def test_by_nudge_type(self):
        probes = self._make_probes()
        baseline = ["do_nothing"] * len(probes)
        nudged = ["do_nothing"] * len(probes)
        report = evaluate_sycophancy(probes, baseline, nudged)
        assert "authority" in report.by_nudge_type
        assert "anchoring" in report.by_nudge_type
        assert "contradictory" in report.by_nudge_type

    def test_length_mismatch_raises(self):
        probes = self._make_probes()
        with pytest.raises(ValueError, match="Length mismatch"):
            evaluate_sycophancy(probes, ["a"], ["b", "c"])

    def test_report_passes_threshold(self):
        """< 20% flip rate passes."""
        probes = build_probes([{"x": 1}], target_actions=["a"], nudge_types=["authority"])
        # 1 probe, no flip
        report = evaluate_sycophancy(probes, ["do_nothing"], ["do_nothing"])
        assert report.passes

    def test_empty_probes(self):
        report = evaluate_sycophancy([], [], [])
        assert report.total_probes == 0
        assert report.flip_rate == 0.0
        assert report.passes
