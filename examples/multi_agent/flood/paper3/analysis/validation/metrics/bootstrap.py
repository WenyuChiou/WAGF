"""
Bootstrap Confidence Intervals for validation metrics.

Provides non-parametric bootstrap CIs for any metric function that
operates on a list of traces or a list of values.

Usage:
    from validation.metrics.bootstrap import bootstrap_ci

    result = bootstrap_ci(traces, compute_l1_metrics, n_bootstrap=1000,
                          extractor=lambda m: m.cacr, agent_type="owner")
"""

from typing import Any, Callable, Dict, List, Optional

import numpy as np


def bootstrap_ci(
    data: List,
    metric_fn: Callable,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    seed: int = 0,
    extractor: Optional[Callable] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Bootstrap confidence interval for any metric function.

    Args:
        data: List of items to resample (traces, agents, etc.).
        metric_fn: Function that takes (resampled_data, **kwargs) and returns a metric.
        n_bootstrap: Number of bootstrap iterations.
        ci: Confidence level (default 0.95 for 95% CI).
        seed: Random seed for reproducibility.
        extractor: Optional function to extract a scalar from metric_fn's return value.
                   E.g., `lambda m: m.cacr` to extract CACR from L1Metrics.
        **kwargs: Additional keyword arguments passed to metric_fn.

    Returns:
        Dict with keys: point_estimate, ci_lower, ci_upper, ci_level,
        std, n_bootstrap, samples.
    """
    rng = np.random.default_rng(seed)
    n = len(data)

    if n == 0:
        return {
            "point_estimate": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "ci_level": ci,
            "std": 0.0,
            "n_bootstrap": n_bootstrap,
            "samples": [],
        }

    # Point estimate on original data
    point = metric_fn(data, **kwargs)
    if extractor is not None:
        point = extractor(point)

    # Bootstrap resampling
    samples = []
    for _ in range(n_bootstrap):
        indices = rng.integers(0, n, size=n)
        resampled = [data[i] for i in indices]
        val = metric_fn(resampled, **kwargs)
        if extractor is not None:
            val = extractor(val)
        samples.append(float(val))

    samples_arr = np.array(samples)
    alpha = 1.0 - ci
    lower = float(np.percentile(samples_arr, 100 * alpha / 2))
    upper = float(np.percentile(samples_arr, 100 * (1 - alpha / 2)))

    return {
        "point_estimate": round(float(point), 4),
        "ci_lower": round(lower, 4),
        "ci_upper": round(upper, 4),
        "ci_level": ci,
        "std": round(float(samples_arr.std()), 4),
        "n_bootstrap": n_bootstrap,
        "samples": [round(s, 4) for s in samples],
    }
