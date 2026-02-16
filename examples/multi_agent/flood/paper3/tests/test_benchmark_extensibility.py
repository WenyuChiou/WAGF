"""Tests for BenchmarkRegistry extensibility (kwargs dispatch)."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from validation.benchmarks.registry import BenchmarkRegistry


def test_custom_benchmark_with_kwargs():
    """Custom benchmark function receives kwargs correctly."""
    reg = BenchmarkRegistry()

    @reg.register("water_efficiency")
    def _compute_water_efficiency(df, traces, **kwargs):
        col = kwargs.get("efficiency_col", "efficiency")
        if col not in df.columns:
            return None
        return df[col].mean()

    df = pd.DataFrame({"agent_id": ["a1", "a2"], "my_eff": [0.8, 0.6]})
    result = reg.dispatch("water_efficiency", df, [], efficiency_col="my_eff")
    assert result == 0.7


def test_custom_benchmark_kwargs_default():
    """Custom benchmark works when kwargs not provided."""
    reg = BenchmarkRegistry()

    @reg.register("simple")
    def _compute_simple(df, traces, **kwargs):
        return len(df)

    df = pd.DataFrame({"agent_id": ["a1"]})
    assert reg.dispatch("simple", df, []) == 1


def test_flood_backward_compat():
    """Flood _compute_benchmark wrapper still works."""
    from validation.benchmarks.flood import _compute_benchmark

    df = pd.DataFrame({
        "agent_id": ["a1", "a2"],
        "flood_zone": ["HIGH", "LOW"],
        "tenure": ["Owner", "Renter"],
        "mg": [True, False],
        "final_has_insurance": [True, False],
        "final_elevated": [False, False],
    })
    # insurance_rate_sfha: 1 HIGH agent, 1 insured => 1.0
    val = _compute_benchmark("insurance_rate_sfha", df, [])
    assert val == 1.0


def test_unknown_benchmark_returns_none():
    """Dispatching unknown name returns None."""
    reg = BenchmarkRegistry()
    assert reg.dispatch("nonexistent", pd.DataFrame(), []) is None
