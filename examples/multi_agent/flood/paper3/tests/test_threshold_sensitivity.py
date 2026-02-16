"""Tests for CACR threshold sensitivity analysis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from validation.metrics.l1_micro import L1Metrics, cacr_threshold_sensitivity_batch


def _make_l1(cacr: float) -> L1Metrics:
    return L1Metrics(
        cacr=cacr, r_h=0.05, ebe=1.5, ebe_max=2.0, ebe_ratio=0.75,
        total_decisions=100, coherent_decisions=int(cacr * 100),
        hallucinations=5, action_distribution={"a": 50, "b": 50},
    )


class TestThresholdSensitivity:
    def test_single_experiment_sweep(self):
        """threshold_sensitivity returns correct verdicts for single experiment."""
        m = _make_l1(0.80)
        results = m.threshold_sensitivity()
        # At 0.75, CACR=0.80 passes
        r75 = next(r for r in results if r["threshold"] == 0.75)
        assert r75["cacr_pass"] is True
        assert r75["overall_pass"] is True
        # At 0.85, CACR=0.80 fails
        r85 = next(r for r in results if r["threshold"] == 0.85)
        assert r85["cacr_pass"] is False
        assert r85["overall_pass"] is False

    def test_custom_range(self):
        m = _make_l1(0.70)
        results = m.threshold_sensitivity(cacr_range=[0.60, 0.70, 0.80])
        assert len(results) == 3
        assert results[0]["cacr_pass"] is True   # 0.70 >= 0.60
        assert results[1]["cacr_pass"] is True   # 0.70 >= 0.70
        assert results[2]["cacr_pass"] is False   # 0.70 < 0.80


class TestBatchSensitivity:
    def test_batch_sweep(self):
        """Batch sensitivity correctly counts pass/fail across experiments."""
        metrics = [_make_l1(0.60), _make_l1(0.75), _make_l1(0.90)]
        results = cacr_threshold_sensitivity_batch(
            metrics, labels=["low", "mid", "high"],
        )
        # At 0.50: all 3 pass
        r50 = next(r for r in results if r["threshold"] == 0.50)
        assert r50["n_pass"] == 3
        assert r50["pass_rate"] == 1.0
        # At 0.75: 2 pass (mid, high)
        r75 = next(r for r in results if r["threshold"] == 0.75)
        assert r75["n_pass"] == 2
        assert set(r75["experiments_passing"]) == {"mid", "high"}
        # At 0.90: 1 pass (high)
        r90 = next(r for r in results if r["threshold"] == 0.90)
        assert r90["n_pass"] == 1
        assert r90["experiments_passing"] == ["high"]

    def test_empty_list(self):
        results = cacr_threshold_sensitivity_batch([])
        assert all(r["n_pass"] == 0 for r in results)
        assert all(r["pass_rate"] == 0.0 for r in results)

    def test_default_labels(self):
        metrics = [_make_l1(0.80), _make_l1(0.85)]
        results = cacr_threshold_sensitivity_batch(metrics)
        r75 = next(r for r in results if r["threshold"] == 0.75)
        assert "exp_0" in r75["experiments_passing"]
        assert "exp_1" in r75["experiments_passing"]
