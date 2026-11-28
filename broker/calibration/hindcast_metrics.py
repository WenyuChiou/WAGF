"""Domain-agnostic continuous hindcast verification metrics and period splitting."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def _coerce_series_pair(
    observed: Sequence[float],
    simulated: Sequence[float],
) -> Tuple[np.ndarray, np.ndarray]:
    obs_arr = np.asarray(list(observed), dtype=float)
    sim_arr = np.asarray(list(simulated), dtype=float)
    if obs_arr.shape != sim_arr.shape:
        raise ValueError(
            f"observed and simulated lengths must match, got {len(obs_arr)} vs {len(sim_arr)}"
        )
    mask = np.isfinite(obs_arr) & np.isfinite(sim_arr)
    return obs_arr[mask], sim_arr[mask]


def compute_kge(observed: Sequence[float], simulated: Sequence[float]) -> float:
    """Compute Kling-Gupta Efficiency (KGE, Gupta et al. 2009)."""
    obs, sim = _coerce_series_pair(observed, simulated)
    if len(obs) < 2:
        return float("nan")
    obs_mean = float(np.mean(obs))
    sim_mean = float(np.mean(sim))
    obs_std = float(np.std(obs, ddof=0))
    sim_std = float(np.std(sim, ddof=0))
    if obs_std <= 0.0 or sim_std <= 0.0 or obs_mean == 0.0:
        return float("nan")
    r = float(np.corrcoef(obs, sim)[0, 1])
    if not math.isfinite(r):
        return float("nan")
    alpha = sim_std / obs_std
    beta = sim_mean / obs_mean
    return float(1.0 - math.sqrt((r - 1.0) ** 2 + (alpha - 1.0) ** 2 + (beta - 1.0) ** 2))


def compute_nse(observed: Sequence[float], simulated: Sequence[float]) -> float:
    """Compute Nash-Sutcliffe Efficiency (NSE)."""
    obs, sim = _coerce_series_pair(observed, simulated)
    if len(obs) == 0:
        return float("nan")
    denom = float(np.sum((obs - np.mean(obs)) ** 2))
    if denom <= 0.0:
        return float("nan")
    num = float(np.sum((sim - obs) ** 2))
    return float(1.0 - (num / denom))


def compute_rmse(observed: Sequence[float], simulated: Sequence[float]) -> float:
    """Compute Root Mean Squared Error (RMSE)."""
    obs, sim = _coerce_series_pair(observed, simulated)
    if len(obs) == 0:
        return float("nan")
    return float(math.sqrt(float(np.mean((sim - obs) ** 2))))


def compute_mae(observed: Sequence[float], simulated: Sequence[float]) -> float:
    """Compute Mean Absolute Error (MAE)."""
    obs, sim = _coerce_series_pair(observed, simulated)
    if len(obs) == 0:
        return float("nan")
    return float(np.mean(np.abs(sim - obs)))


def compute_bias(observed: Sequence[float], simulated: Sequence[float]) -> float:
    """Compute Mean Bias (``mean(simulated - observed)``)."""
    obs, sim = _coerce_series_pair(observed, simulated)
    if len(obs) == 0:
        return float("nan")
    return float(np.mean(sim - obs))


def evaluate_hindcast_series(
    observed: Sequence[float],
    simulated: Sequence[float],
) -> Dict[str, float]:
    """Compute all continuous hindcast metrics for paired observed/simulated sequences."""
    obs, _ = _coerce_series_pair(observed, simulated)
    return {
        "kge": compute_kge(observed, simulated),
        "nse": compute_nse(observed, simulated),
        "rmse": compute_rmse(observed, simulated),
        "mae": compute_mae(observed, simulated),
        "bias": compute_bias(observed, simulated),
        "n": float(len(obs)),
    }


def aggregate_seed_metrics(
    seed_metrics: Sequence[Mapping[str, float]],
) -> Dict[str, Dict[str, float]]:
    """Aggregate per-seed metric dicts into summary statistics including median and IQR."""
    if not seed_metrics:
        return {}
    keys = sorted({str(k) for m in seed_metrics for k in m})
    summary: Dict[str, Dict[str, float]] = {}
    for key in keys:
        vals: List[float] = [
            float(m[key])
            for m in seed_metrics
            if key in m and m[key] is not None and math.isfinite(float(m[key]))
        ]
        if not vals:
            continue
        arr = np.asarray(vals, dtype=float)
        q25 = float(np.percentile(arr, 25))
        q75 = float(np.percentile(arr, 75))
        summary[key] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr, ddof=0)),
            "median": float(np.median(arr)),
            "q25": q25,
            "q75": q75,
            "iqr": q75 - q25,
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "n_seeds": float(len(arr)),
        }
    return summary


def split_hindcast_periods(
    df: pd.DataFrame,
    split_period: int,
    *,
    period_col: str = "year",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split a trace DataFrame into calibration (``<= split_period``) and holdout (``> split_period``)."""
    if period_col not in df.columns:
        raise ValueError(f"DataFrame missing period column {period_col!r}")
    cal = df[df[period_col] <= split_period].copy()
    holdout = df[df[period_col] > split_period].copy()
    return cal, holdout


__all__ = [
    "aggregate_seed_metrics",
    "compute_bias",
    "compute_kge",
    "compute_mae",
    "compute_nse",
    "compute_rmse",
    "evaluate_hindcast_series",
    "split_hindcast_periods",
]
