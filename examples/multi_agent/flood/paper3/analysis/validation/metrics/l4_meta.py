"""
L4 Meta-Validation — Wasserstein distance for cross-run distributional comparison.

Compares simulated action/outcome distributions against empirical reference
distributions or across seeds/models. Uses Earth Mover's Distance (EMD,
aka Wasserstein-1) which respects ordinal structure of categorical outcomes.

Usage:
    from validation.metrics.l4_meta import (
        wasserstein_categorical,
        cross_run_stability,
        empirical_distance,
        L4MetaReport,
    )

    # Compare two categorical distributions
    d = wasserstein_categorical(
        simulated={"buy_insurance": 0.45, "do_nothing": 0.30, "elevate": 0.25},
        reference={"buy_insurance": 0.50, "do_nothing": 0.35, "elevate": 0.15},
    )

    # Cross-run stability across seeds
    stability = cross_run_stability(distributions_by_seed)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


# =============================================================================
# Wasserstein Distance for Categorical Distributions
# =============================================================================

def wasserstein_categorical(
    simulated: Dict[str, float],
    reference: Dict[str, float],
    category_order: Optional[List[str]] = None,
) -> float:
    """Compute Wasserstein-1 distance between two categorical distributions.

    For ordered categories, uses ordinal EMD (cumulative difference).
    For unordered categories, uses total variation distance / 2
    (equivalent to W1 on discrete metric space).

    Args:
        simulated: Dict mapping category -> proportion (must sum to ~1.0).
        reference: Dict mapping category -> proportion (must sum to ~1.0).
        category_order: Optional ordered list of categories. If provided,
            uses ordinal EMD. If None, uses total variation distance.

    Returns:
        Wasserstein-1 distance (0.0 = identical, higher = more different).
    """
    all_cats = sorted(set(simulated.keys()) | set(reference.keys()))

    if category_order is not None:
        # Ordinal EMD: sum of absolute cumulative differences
        cats = category_order
        sim_cdf = 0.0
        ref_cdf = 0.0
        distance = 0.0
        for cat in cats:
            sim_cdf += simulated.get(cat, 0.0)
            ref_cdf += reference.get(cat, 0.0)
            distance += abs(sim_cdf - ref_cdf)
        return round(distance, 6)
    else:
        # Total variation distance (unordered EMD)
        tv = sum(
            abs(simulated.get(cat, 0.0) - reference.get(cat, 0.0))
            for cat in all_cats
        )
        return round(tv / 2, 6)


def _normalize_counts_to_dist(counts: Dict[str, int]) -> Dict[str, float]:
    """Convert count dict to probability distribution."""
    total = sum(counts.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


# =============================================================================
# Cross-Run Stability
# =============================================================================

@dataclass
class CrossRunStability:
    """Stability analysis across multiple simulation runs."""
    mean_pairwise_distance: float
    max_pairwise_distance: float
    std_pairwise_distance: float
    n_runs: int
    pairwise_distances: List[float] = field(default_factory=list)
    stable: bool = True

    @property
    def is_stable(self) -> bool:
        """Stable if mean pairwise distance < 0.10."""
        return self.mean_pairwise_distance < 0.10


def cross_run_stability(
    distributions: List[Dict[str, float]],
    category_order: Optional[List[str]] = None,
    threshold: float = 0.10,
) -> CrossRunStability:
    """Assess distributional stability across multiple runs (seeds/models).

    Computes all pairwise Wasserstein distances between run distributions
    and reports summary statistics.

    Args:
        distributions: List of dicts, each mapping category -> proportion.
        category_order: Optional ordered categories for ordinal EMD.
        threshold: Maximum acceptable mean pairwise distance for "stable".

    Returns:
        CrossRunStability dataclass with pairwise distance statistics.
    """
    n = len(distributions)
    if n < 2:
        return CrossRunStability(
            mean_pairwise_distance=0.0,
            max_pairwise_distance=0.0,
            std_pairwise_distance=0.0,
            n_runs=n,
            pairwise_distances=[],
            stable=True,
        )

    distances = []
    for i in range(n):
        for j in range(i + 1, n):
            d = wasserstein_categorical(
                distributions[i], distributions[j], category_order
            )
            distances.append(d)

    arr = np.array(distances)
    mean_d = float(arr.mean())

    return CrossRunStability(
        mean_pairwise_distance=round(mean_d, 6),
        max_pairwise_distance=round(float(arr.max()), 6),
        std_pairwise_distance=round(float(arr.std()), 6),
        n_runs=n,
        pairwise_distances=[round(d, 6) for d in distances],
        stable=mean_d < threshold,
    )


# =============================================================================
# Empirical Distance (Simulated vs. Reference)
# =============================================================================

@dataclass
class L4MetaReport:
    """L4 meta-validation report."""
    action_distance: float
    action_distances_by_type: Dict[str, float]
    cross_run: Optional[CrossRunStability]
    passes: bool

    @property
    def passes_threshold(self) -> bool:
        """Pass if action distance < 0.15."""
        return self.action_distance < 0.15


def empirical_distance(
    simulated_counts: Dict[str, int],
    reference_counts: Dict[str, int],
    category_order: Optional[List[str]] = None,
) -> float:
    """Compute Wasserstein distance between simulated and empirical action counts.

    Convenience wrapper that normalizes counts to distributions first.

    Args:
        simulated_counts: Action count dict from simulation.
        reference_counts: Action count dict from empirical data.
        category_order: Optional ordering for ordinal EMD.

    Returns:
        Wasserstein-1 distance.
    """
    sim_dist = _normalize_counts_to_dist(simulated_counts)
    ref_dist = _normalize_counts_to_dist(reference_counts)
    return wasserstein_categorical(sim_dist, ref_dist, category_order)


def compute_l4_meta(
    simulated_action_counts: Dict[str, int],
    reference_action_counts: Optional[Dict[str, int]] = None,
    run_distributions: Optional[List[Dict[str, float]]] = None,
    category_order: Optional[List[str]] = None,
) -> L4MetaReport:
    """Compute L4 meta-validation metrics.

    Args:
        simulated_action_counts: Aggregate action counts from simulation.
        reference_action_counts: Empirical reference action counts.
            If None, action_distance is set to -1 (not computable).
        run_distributions: Per-run action distributions for stability check.
        category_order: Optional ordered categories for ordinal EMD.

    Returns:
        L4MetaReport with distances and stability assessment.
    """
    # Action distance vs reference
    if reference_action_counts is not None:
        action_dist = empirical_distance(
            simulated_action_counts, reference_action_counts, category_order
        )
    else:
        action_dist = -1.0

    # Cross-run stability
    cross_run = None
    if run_distributions and len(run_distributions) >= 2:
        cross_run = cross_run_stability(run_distributions, category_order)

    passes = action_dist < 0.15 if action_dist >= 0 else False

    return L4MetaReport(
        action_distance=round(action_dist, 6),
        action_distances_by_type={},
        cross_run=cross_run,
        passes=passes,
    )
