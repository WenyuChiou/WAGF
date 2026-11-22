"""compute_flood_metrics summarises seeds as median and range (min-max), not mean and sd."""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "examples" / "single_agent" / "analysis" / "compute_flood_metrics.py"


def _module():
    spec = importlib.util.spec_from_file_location("compute_flood_metrics_under_test", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_median_range_over_seeds():
    mod = _module()
    assert mod.median_range(pd.Series([0.9, 0.5, 0.7, 0.6, 0.8]), 2) == "0.70 [0.50-0.90]"
    assert mod.median_range(pd.Series([2.0, 4.0]), 1) == "3.0 [2.0-4.0]"


def test_median_range_without_values():
    mod = _module()
    assert mod.median_range(pd.Series([float("nan")]), 2) == "N/A"


def test_summary_text_names_median_and_range_not_sd():
    text = PATH.read_text(encoding="utf-8")
    assert "median and range" in text
    assert "+/- sd" not in text and "mean+/-sd" not in text
