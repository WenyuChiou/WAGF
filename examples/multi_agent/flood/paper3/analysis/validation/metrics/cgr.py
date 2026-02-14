"""
Construct Grounding Rate (CGR) — Rule-based validation of LLM construct labels.

Addresses CACR circularity by grounding TP/CP from objective state_before,
then comparing against LLM-assigned labels.

Metrics:
    cgr_exact:    Exact match rate (grounded == LLM label)
    cgr_adjacent: ±1-level agreement rate
    kappa_tp/cp:  Cohen's kappa for TP/CP
    confusion:    Confusion matrices for TP and CP
"""

from collections import Counter
from typing import Dict, List, Optional, Tuple

from validation.io.trace_reader import _extract_tp_label, _extract_cp_label


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
    """Compute Cohen's kappa from a confusion matrix dict."""
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


def compute_cgr(traces: List[Dict]) -> Dict:
    """Compute Construct Grounding Rate.

    For each trace with state_before:
    1. Rule-based TP/CP from state_before
    2. LLM TP/CP from trace labels
    3. Exact match + ±1-level agreement

    Args:
        traces: List of decision trace dicts (must include state_before).

    Returns:
        Dict with keys:
            cgr_tp_exact, cgr_cp_exact, cgr_tp_adjacent, cgr_cp_adjacent,
            kappa_tp, kappa_cp,
            tp_confusion, cp_confusion,
            n_grounded, n_skipped
    """
    tp_exact = 0
    cp_exact = 0
    tp_adjacent = 0
    cp_adjacent = 0
    n_grounded = 0
    n_skipped = 0

    # Confusion matrices: (grounded, llm) -> count
    tp_confusion: Dict[Tuple[str, str], int] = Counter()
    cp_confusion: Dict[Tuple[str, str], int] = Counter()

    for trace in traces:
        state_before = trace.get("state_before", {})
        if not state_before:
            n_skipped += 1
            continue

        llm_tp = _extract_tp_label(trace)
        llm_cp = _extract_cp_label(trace)

        if llm_tp == "UNKNOWN" or llm_cp == "UNKNOWN":
            n_skipped += 1
            continue

        grounded_tp = ground_tp_from_state(state_before)
        grounded_cp = ground_cp_from_state(state_before)

        n_grounded += 1

        tp_confusion[(grounded_tp, llm_tp)] += 1
        cp_confusion[(grounded_cp, llm_cp)] += 1

        if grounded_tp == llm_tp:
            tp_exact += 1
        if grounded_cp == llm_cp:
            cp_exact += 1
        if _is_adjacent(grounded_tp, llm_tp):
            tp_adjacent += 1
        if _is_adjacent(grounded_cp, llm_cp):
            cp_adjacent += 1

    if n_grounded == 0:
        return {
            "cgr_tp_exact": 0.0,
            "cgr_cp_exact": 0.0,
            "cgr_tp_adjacent": 0.0,
            "cgr_cp_adjacent": 0.0,
            "kappa_tp": 0.0,
            "kappa_cp": 0.0,
            "tp_confusion": {},
            "cp_confusion": {},
            "n_grounded": 0,
            "n_skipped": n_skipped,
        }

    # Convert tuple keys to strings for JSON serialization
    tp_confusion_str = {f"{k[0]}_vs_{k[1]}": v for k, v in tp_confusion.items()}
    cp_confusion_str = {f"{k[0]}_vs_{k[1]}": v for k, v in cp_confusion.items()}

    return {
        "cgr_tp_exact": round(tp_exact / n_grounded, 4),
        "cgr_cp_exact": round(cp_exact / n_grounded, 4),
        "cgr_tp_adjacent": round(tp_adjacent / n_grounded, 4),
        "cgr_cp_adjacent": round(cp_adjacent / n_grounded, 4),
        "kappa_tp": round(_cohens_kappa(dict(tp_confusion), _LEVELS), 4),
        "kappa_cp": round(_cohens_kappa(dict(cp_confusion), _LEVELS), 4),
        "tp_confusion": tp_confusion_str,
        "cp_confusion": cp_confusion_str,
        "n_grounded": n_grounded,
        "n_skipped": n_skipped,
    }
