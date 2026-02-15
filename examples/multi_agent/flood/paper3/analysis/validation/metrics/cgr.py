"""
Construct Grounding Rate (CGR) — Rule-based validation of LLM construct labels.

Addresses CACR circularity by grounding TP/CP from objective state_before,
then comparing against LLM-assigned labels.

Metrics:
    cgr_exact:    Exact match rate (grounded == LLM label)
    cgr_adjacent: ±1-level agreement rate
    kappa_tp/cp:  Weighted Cohen's kappa for TP/CP (linear weights for ordinal)
    confusion:    Confusion matrices for TP and CP
"""

from collections import Counter
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from validation.io.trace_reader import _extract_tp_label, _extract_cp_label

if TYPE_CHECKING:
    from validation.grounding.base import GroundingStrategy


# Ordered levels for adjacency check
_LEVELS = ["VL", "L", "M", "H", "VH"]
_LEVEL_INDEX = {lv: i for i, lv in enumerate(_LEVELS)}


# =============================================================================
# Rule-Based Grounding
# =============================================================================

def ground_tp_from_state(state_before: Dict) -> str:
    """Rule-based TP grounding from objective flood risk indicators.

    Uses flood_zone, flood_count, years_since_flood, flooded_this_year
    to derive an expected Threat Perception level.
    """
    zone = str(state_before.get("flood_zone", "LOW")).upper()
    flood_count = int(state_before.get("flood_count", 0))
    years_since = state_before.get("years_since_flood")
    if years_since is not None:
        years_since = int(years_since)
    flooded_now = bool(state_before.get("flooded_this_year", False))

    if zone == "HIGH" and flooded_now:
        return "VH"
    if zone == "HIGH" and flood_count >= 1:
        return "H"
    if zone == "MODERATE" and flooded_now:
        return "H"
    if zone == "MODERATE" and years_since is not None and years_since <= 2:
        return "H"
    if zone == "MODERATE":
        return "M"
    if zone == "HIGH" and flood_count == 0:
        return "M"
    if zone == "LOW" and flood_count >= 1:
        return "L"
    if zone == "LOW" and flood_count == 0:
        return "VL"

    # Default fallback
    return "M"


def ground_cp_from_state(state_before: Dict) -> str:
    """Rule-based CP grounding from socioeconomic indicators.

    Uses mg (marginalized group), income, housing_cost_burden, elevated
    to derive an expected Coping Perception level.
    """
    mg = bool(state_before.get("mg", False))
    income = float(state_before.get("income", 50000))
    elevated = bool(state_before.get("elevated", False))

    # Already elevated = high coping resource
    if elevated and not mg:
        return "VH"

    if not mg and income > 75000:
        return "VH"
    if not mg and income >= 50000:
        return "H"
    if income >= 40000 and not mg:
        return "M"
    if mg and income >= 40000:
        return "L"
    if mg and income < 30000:
        return "VL"
    if mg:
        return "L"

    return "M"


# =============================================================================
# CGR Computation
# =============================================================================

def _is_adjacent(level_a: str, level_b: str) -> bool:
    """Check if two levels are within ±1 of each other."""
    idx_a = _LEVEL_INDEX.get(level_a)
    idx_b = _LEVEL_INDEX.get(level_b)
    if idx_a is None or idx_b is None:
        return False
    return abs(idx_a - idx_b) <= 1


def _cohens_kappa(confusion: Dict[Tuple[str, str], int], labels: List[str]) -> float:
    """Compute unweighted Cohen's kappa from a confusion matrix dict.

    Retained for backward compatibility. For ordinal scales, prefer _weighted_kappa.
    """
    n = sum(confusion.values())
    if n == 0:
        return 0.0

    # Observed agreement
    p_o = sum(confusion.get((lv, lv), 0) for lv in labels) / n

    # Expected agreement (chance)
    p_e = 0.0
    for lv in labels:
        row_sum = sum(confusion.get((lv, lv2), 0) for lv2 in labels)
        col_sum = sum(confusion.get((lv2, lv), 0) for lv2 in labels)
        p_e += (row_sum * col_sum) / (n * n) if n > 0 else 0.0

    if abs(1.0 - p_e) < 1e-10:
        return 1.0 if abs(p_o - 1.0) < 1e-10 else 0.0

    return (p_o - p_e) / (1.0 - p_e)


def _weighted_kappa(
    confusion: Dict[Tuple[str, str], int],
    labels: List[str],
    weight_type: str = "linear",
) -> float:
    """Compute weighted Cohen's kappa for ordinal scales.

    Linear weights: w_ij = |i - j| / (k - 1)
    Quadratic weights: w_ij = (i - j)^2 / (k - 1)^2

    For ordinal TP/CP scales (VL/L/M/H/VH), weighted kappa penalizes
    distant disagreements more than adjacent ones. This is the standard
    approach for ordinal reliability assessment (Cohen, 1968; Fleiss, 1981).

    Args:
        confusion: Dict of {(grounded_label, llm_label): count}.
        labels: Ordered list of labels (e.g., ["VL", "L", "M", "H", "VH"]).
        weight_type: "linear" or "quadratic" weights.

    Returns:
        Weighted kappa coefficient in [-1, 1].
    """
    n = sum(confusion.values())
    if n == 0:
        return 0.0

    k = len(labels)
    if k <= 1:
        return 1.0

    label_idx = {lv: i for i, lv in enumerate(labels)}

    # Build weight matrix
    if weight_type == "quadratic":
        w = [[((i - j) ** 2) / ((k - 1) ** 2) for j in range(k)] for i in range(k)]
    else:  # linear
        w = [[abs(i - j) / (k - 1) for j in range(k)] for i in range(k)]

    # Row/column marginals
    row_sums = [sum(confusion.get((labels[i], labels[j]), 0) for j in range(k)) for i in range(k)]
    col_sums = [sum(confusion.get((labels[i], labels[j]), 0) for i in range(k)) for j in range(k)]

    # Observed weighted disagreement
    p_o = 0.0
    for i in range(k):
        for j in range(k):
            p_o += w[i][j] * confusion.get((labels[i], labels[j]), 0)
    p_o /= n

    # Expected weighted disagreement
    p_e = 0.0
    for i in range(k):
        for j in range(k):
            p_e += w[i][j] * (row_sums[i] * col_sums[j])
    p_e /= (n * n)

    if abs(p_e) < 1e-10:
        return 1.0 if abs(p_o) < 1e-10 else 0.0

    return 1.0 - (p_o / p_e)


def compute_cgr(
    traces: List[Dict],
    grounder: Optional["GroundingStrategy"] = None,
    theory=None,
) -> Dict:
    """Compute Construct Grounding Rate.

    For each trace with state_before:
    1. Rule-based construct levels from state_before (via grounder)
    2. LLM construct levels from trace labels (via theory or default TP/CP extraction)
    3. Exact match + ±1-level agreement

    Args:
        traces: List of decision trace dicts (must include state_before).
        grounder: GroundingStrategy implementation for deriving expected constructs.
            Defaults to flood PMT grounding (ground_tp/cp_from_state) for backward compat.
        theory: Optional BehavioralTheory for extracting LLM constructs.
            If None, uses default TP/CP extraction.

    Returns:
        Dict with keys:
            cgr_<dim>_exact, cgr_<dim>_adjacent for each grounded dimension,
            kappa_<dim>, confusion matrices, n_grounded, n_skipped.
    """
    # Determine grounding mode
    use_flood_default = grounder is None

    # For multi-dimension support, we track per-dimension results
    if use_flood_default:
        dimensions = ["tp", "cp"]
    else:
        # Probe first trace to discover dimensions
        for trace in traces:
            sb = trace.get("state_before", {})
            if sb:
                grounded = grounder.ground_constructs(sb)
                dimensions = [d.lower() for d in grounded.keys()]
                break
        else:
            dimensions = []

    exact_counts = {d: 0 for d in dimensions}
    adjacent_counts = {d: 0 for d in dimensions}
    n_grounded = 0
    n_skipped = 0

    # Confusion matrices: dim -> {(grounded, llm): count}
    confusion_matrices: Dict[str, Dict[Tuple[str, str], int]] = {
        d: Counter() for d in dimensions
    }

    for trace in traces:
        state_before = trace.get("state_before", {})
        if not state_before:
            n_skipped += 1
            continue

        # Extract LLM labels
        if theory is not None:
            llm_constructs = theory.extract_constructs(trace)
        else:
            llm_constructs = {
                "TP": _extract_tp_label(trace),
                "CP": _extract_cp_label(trace),
            }

        if any(v == "UNKNOWN" for v in llm_constructs.values()):
            n_skipped += 1
            continue

        # Ground constructs
        if use_flood_default:
            grounded = {
                "TP": ground_tp_from_state(state_before),
                "CP": ground_cp_from_state(state_before),
            }
        else:
            grounded = grounder.ground_constructs(state_before)

        n_grounded += 1

        for dim in dimensions:
            dim_upper = dim.upper()
            g_val = grounded.get(dim_upper, grounded.get(dim, ""))
            l_val = llm_constructs.get(dim_upper, llm_constructs.get(dim, ""))

            confusion_matrices[dim][(g_val, l_val)] += 1

            if g_val == l_val:
                exact_counts[dim] += 1
            if _is_adjacent(g_val, l_val):
                adjacent_counts[dim] += 1

    if n_grounded == 0:
        result = {"n_grounded": 0, "n_skipped": n_skipped}
        for dim in dimensions:
            result[f"cgr_{dim}_exact"] = 0.0
            result[f"cgr_{dim}_adjacent"] = 0.0
            result[f"kappa_{dim}"] = 0.0
            result[f"{dim}_confusion"] = {}
        return result

    result = {
        "n_grounded": n_grounded,
        "n_skipped": n_skipped,
    }
    for dim in dimensions:
        result[f"cgr_{dim}_exact"] = round(exact_counts[dim] / n_grounded, 4)
        result[f"cgr_{dim}_adjacent"] = round(adjacent_counts[dim] / n_grounded, 4)
        result[f"kappa_{dim}"] = round(
            _weighted_kappa(dict(confusion_matrices[dim]), _LEVELS), 4
        )
        # Convert tuple keys to strings for JSON serialization
        result[f"{dim}_confusion"] = {
            f"{k[0]}_vs_{k[1]}": v for k, v in confusion_matrices[dim].items()
        }

    return result
