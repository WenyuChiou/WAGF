"""Tests for clustered bootstrap CI (P1.3)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import numpy as np

from validation.metrics.bootstrap import bootstrap_ci, clustered_bootstrap_ci


def _make_agent_traces(n_agents=10, n_years=5):
    """Create traces with multiple years per agent."""
    traces = []
    for i in range(n_agents):
        agent_id = f"H{i:03d}"
        for year in range(1, n_years + 1):
            traces.append({
                "agent_id": agent_id,
                "year": year,
                "skill_proposal": {
                    "reasoning": {"TP_LABEL": "H", "CP_LABEL": "H"},
                    "skill_name": "buy_insurance",
                },
                "approved_skill": {"skill_name": "buy_insurance"},
                "outcome": "APPROVED",
                "state_before": {"flood_zone": "HIGH"},
            })
    return traces


class TestClusteredBootstrap:
    def test_output_structure(self):
        traces = _make_agent_traces()
        result = clustered_bootstrap_ci(
            traces, lambda d: np.mean([1.0 for _ in d]),
            n_bootstrap=50, seed=0,
        )
        assert "point_estimate" in result
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert "n_clusters" in result
        assert result["n_clusters"] == 10
        assert len(result["samples"]) == 50

    def test_ci_contains_point_estimate(self):
        traces = _make_agent_traces(20, 3)
        result = clustered_bootstrap_ci(
            traces, lambda d: len(d),
            n_bootstrap=100, seed=42,
        )
        assert result["ci_lower"] <= result["point_estimate"] <= result["ci_upper"]

    def test_wider_ci_than_trace_level(self):
        """Clustered bootstrap should generally produce wider CIs than trace-level.

        This is because trace-level bootstrap underestimates variance by
        ignoring within-agent correlation.
        """
        # Create heterogeneous agents: some always insure, some never
        traces = []
        for i in range(20):
            action = "buy_insurance" if i < 10 else "do_nothing"
            for year in range(1, 6):
                traces.append({
                    "agent_id": f"H{i:03d}",
                    "year": year,
                    "approved_skill": {"skill_name": action},
                    "outcome": "APPROVED",
                })

        def insurance_rate(data):
            n_ins = sum(1 for t in data
                       if t["approved_skill"]["skill_name"] == "buy_insurance")
            return n_ins / len(data) if data else 0.0

        trace_ci = bootstrap_ci(traces, insurance_rate, n_bootstrap=500, seed=0)
        cluster_ci = clustered_bootstrap_ci(
            traces, insurance_rate, n_bootstrap=500, seed=0,
        )

        trace_width = trace_ci["ci_upper"] - trace_ci["ci_lower"]
        cluster_width = cluster_ci["ci_upper"] - cluster_ci["ci_lower"]
        # Clustered CI should be wider (more conservative)
        assert cluster_width > trace_width

    def test_empty_traces(self):
        result = clustered_bootstrap_ci(
            [], lambda d: 0.0, n_bootstrap=10, seed=0,
        )
        assert result["point_estimate"] == 0.0
        assert result["n_clusters"] == 0
        assert result["samples"] == []

    def test_single_agent(self):
        traces = _make_agent_traces(1, 5)
        result = clustered_bootstrap_ci(
            traces, lambda d: len(d),
            n_bootstrap=50, seed=0,
        )
        assert result["n_clusters"] == 1
        # Single agent → all resamples select the same agent → no variance
        assert result["std"] == 0.0

    def test_reproducibility(self):
        traces = _make_agent_traces()
        r1 = clustered_bootstrap_ci(
            traces, lambda d: len(d), n_bootstrap=50, seed=42,
        )
        r2 = clustered_bootstrap_ci(
            traces, lambda d: len(d), n_bootstrap=50, seed=42,
        )
        assert r1["samples"] == r2["samples"]

    def test_custom_cluster_key(self):
        """Support grouping by arbitrary key, not just agent_id."""
        data = [
            {"group": "A", "value": 1},
            {"group": "A", "value": 2},
            {"group": "B", "value": 3},
            {"group": "B", "value": 4},
        ]
        result = clustered_bootstrap_ci(
            data, lambda d: np.mean([x["value"] for x in d]),
            n_bootstrap=50, seed=0, cluster_key="group",
        )
        assert result["n_clusters"] == 2
        assert result["point_estimate"] == 2.5
