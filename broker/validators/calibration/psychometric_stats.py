"""
Psychometric Battery — Statistical computations.

Extracted from psychometric_battery.py for modularity.
Contains pure statistical functions: ICC(2,1), Cronbach's alpha,
and Fleiss' kappa.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from .psychometric_types import ICCResult


def compute_icc_2_1(
    ratings: np.ndarray,
    construct_name: str = "",
) -> ICCResult:
    """Compute ICC(2,1) -- two-way random, single measures.

    This is the standard ICC for test-retest reliability where both
    subjects (archetypes) and raters (replicates) are random effects.

    Parameters
    ----------
    ratings : ndarray, shape (n_subjects, n_raters)
        Rating matrix where rows = subjects, columns = replicates.
    construct_name : str
        Label for the construct being measured.

    Returns
    -------
    ICCResult

    References
    ----------
    Shrout & Fleiss (1979). Intraclass Correlations: Uses in Assessing
        Rater Reliability. Psychological Bulletin, 86(2), 420-428.
    """
    n, k = ratings.shape  # n subjects, k raters

    if n < 2 or k < 2:
        return ICCResult(
            construct=construct_name,
            icc_value=0.0,
            n_subjects=n,
            n_raters=k,
        )

    # Grand mean
    grand_mean = np.mean(ratings)

    # Between-subjects sum of squares
    subject_means = np.mean(ratings, axis=1)
    ss_between = k * np.sum((subject_means - grand_mean) ** 2)

    # Within-subjects sum of squares
    ss_within = np.sum((ratings - subject_means[:, np.newaxis]) ** 2)

    # Between-raters sum of squares
    rater_means = np.mean(ratings, axis=0)
    ss_raters = n * np.sum((rater_means - grand_mean) ** 2)

    # Residual (error) sum of squares
    ss_error = ss_within - ss_raters

    # Mean squares
    ms_between = ss_between / (n - 1) if n > 1 else 0
    ms_raters = ss_raters / (k - 1) if k > 1 else 0
    ms_error = ss_error / ((n - 1) * (k - 1)) if (n > 1 and k > 1) else 0

    # ICC(2,1) = (MS_between - MS_error) / (MS_between + (k-1)*MS_error + k*(MS_raters - MS_error)/n)
    denom = (
        ms_between
        + (k - 1) * ms_error
        + k * (ms_raters - ms_error) / n
    )

    if denom == 0:
        icc = 0.0
    else:
        icc = (ms_between - ms_error) / denom

    # F-value for significance test
    f_val = ms_between / ms_error if ms_error > 0 else 0.0

    # Approximate p-value from F distribution
    try:
        from scipy import stats as sp_stats
        df1 = n - 1
        df2 = (n - 1) * (k - 1)
        p_val = 1 - sp_stats.f.cdf(f_val, df1, df2) if f_val > 0 else 1.0

        # 95% CI using Shrout-Fleiss formulas
        fl = f_val / sp_stats.f.ppf(0.975, df1, df2) if f_val > 0 else 0
        fu = f_val * sp_stats.f.ppf(0.975, df2, df1) if f_val > 0 else 0

        ci_lower = max(-1.0, (fl - 1) / (fl + k - 1)) if fl > 0 else -1.0
        ci_upper = min(1.0, (fu - 1) / (fu + k - 1)) if fu > 0 else 1.0
    except ImportError:
        p_val = 1.0
        ci_lower = 0.0
        ci_upper = 0.0

    return ICCResult(
        construct=construct_name,
        icc_value=float(np.clip(icc, -1.0, 1.0)),
        f_value=float(f_val),
        p_value=float(p_val),
        n_subjects=n,
        n_raters=k,
        ci_lower=float(ci_lower),
        ci_upper=float(ci_upper),
    )


def compute_cronbach_alpha(items: np.ndarray) -> float:
    """Compute Cronbach's alpha for internal consistency.

    Parameters
    ----------
    items : ndarray, shape (n_observations, n_items)
        Each column is an "item" (construct rating), each row is
        a response.

    Returns
    -------
    float
        Cronbach's alpha (0-1, target > 0.7).
    """
    n_items = items.shape[1]
    if n_items < 2:
        return 0.0

    item_vars = np.var(items, axis=0, ddof=1)
    total_var = np.var(np.sum(items, axis=1), ddof=1)

    if total_var == 0:
        return 0.0

    alpha = (n_items / (n_items - 1)) * (1 - np.sum(item_vars) / total_var)
    return float(np.clip(alpha, 0.0, 1.0))


def compute_fleiss_kappa(
    decisions: List[List[str]],
) -> float:
    """Compute Fleiss' kappa for nominal agreement.

    Parameters
    ----------
    decisions : list of list of str
        Outer list = subjects (archetype-vignette combos),
        inner list = rater decisions (replicates).

    Returns
    -------
    float
        Fleiss' kappa (-1 to 1, target > 0.4 for moderate agreement).
    """
    if not decisions:
        return 0.0

    # Collect all unique categories
    categories = sorted(set(d for sublist in decisions for d in sublist))
    n_cat = len(categories)
    cat_idx = {c: i for i, c in enumerate(categories)}

    n_subjects = len(decisions)
    n_raters = len(decisions[0]) if decisions else 0

    if n_subjects < 2 or n_raters < 2 or n_cat < 2:
        return 0.0

    # Build rating matrix: n_subjects x n_categories
    rating_matrix = np.zeros((n_subjects, n_cat), dtype=float)
    for i, subject_decisions in enumerate(decisions):
        for d in subject_decisions:
            if d in cat_idx:
                rating_matrix[i, cat_idx[d]] += 1

    # Proportion of ratings per category
    p_j = np.sum(rating_matrix, axis=0) / (n_subjects * n_raters)

    # Per-subject agreement
    p_i = np.sum(rating_matrix ** 2, axis=1) - n_raters
    p_i = p_i / (n_raters * (n_raters - 1))

    # Overall agreement
    p_bar = np.mean(p_i)

    # Expected agreement by chance
    p_e = np.sum(p_j ** 2)

    if p_e == 1.0:
        return 1.0

    kappa = (p_bar - p_e) / (1 - p_e)
    return float(np.clip(kappa, -1.0, 1.0))
