"""
L1 Micro Validation Metrics.

CACR (Construct-Action Coherence Rate), R_H (Hallucination Rate),
EBE (Effective Behavioral Entropy), and CACR Decomposition.
"""

import math
from pathlib import Path
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from validation.theories.pmt import (
    PMT_OWNER_RULES,
    PMT_RENTER_RULES,
    _is_sensible_action,
)
from validation.io.trace_reader import (
    _extract_tp_label,
    _extract_cp_label,
    _extract_action,
    _normalize_action,
)
from validation.hallucinations.flood import _is_hallucination
from validation.metrics.entropy import _compute_entropy


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CACRDecomposition:
    """CACR decomposition separating LLM reasoning from governance filtering."""
    cacr_raw: float
    cacr_final: float
    retry_rate: float
    fallback_rate: float
    total_proposals: int
    quadrant_cacr: Dict[str, float]


@dataclass
class L1Metrics:
    """L1 Micro validation metrics."""
    cacr: float
    r_h: float
    ebe: float
    ebe_max: float
    ebe_ratio: float
    total_decisions: int
    coherent_decisions: int
    hallucinations: int
    action_distribution: Dict[str, int]
    cacr_decomposition: Optional[CACRDecomposition] = None

    def passes_thresholds(self) -> Dict[str, bool]:
        return {
            "CACR": self.cacr >= 0.75,
            "R_H": self.r_h <= 0.10,
            "EBE": 0.1 < self.ebe_ratio < 0.9 if self.ebe_max > 0 else False,
        }


# =============================================================================
# L1 Metric Computation
# =============================================================================

def compute_l1_metrics(traces: List[Dict], agent_type: str = "owner") -> L1Metrics:
    """Compute L1 micro-level validation metrics."""
    rules = PMT_OWNER_RULES if agent_type == "owner" else PMT_RENTER_RULES

    total = len(traces)
    coherent = 0
    hallucinations = 0
    extraction_failures = 0
    action_counts = Counter()

    for trace in traces:
        tp = _extract_tp_label(trace)
        cp = _extract_cp_label(trace)
        action = _extract_action(trace)
        action = _normalize_action(action)
        action_counts[action] += 1

        if tp == "UNKNOWN" or cp == "UNKNOWN":
            extraction_failures += 1
            continue

        key = (tp, cp)
        if key in rules:
            if action in rules[key]:
                coherent += 1
        else:
            if _is_sensible_action(tp, cp, action, agent_type):
                coherent += 1

        if _is_hallucination(trace):
            hallucinations += 1

    if extraction_failures > 0:
        print(f"  WARNING: {extraction_failures} traces with UNKNOWN TP/CP labels excluded from CACR")

    cacr_eligible = total - extraction_failures
    cacr = coherent / cacr_eligible if cacr_eligible > 0 else 0.0
    r_h = hallucinations / total if total > 0 else 0.0
    ebe = _compute_entropy(action_counts)
    k = len(action_counts)
    ebe_max = math.log2(k) if k > 1 else 0.0
    ebe_ratio = ebe / ebe_max if ebe_max > 0 else 0.0

    return L1Metrics(
        cacr=round(cacr, 4),
        r_h=round(r_h, 4),
        ebe=round(ebe, 4),
        ebe_max=round(ebe_max, 4),
        ebe_ratio=round(ebe_ratio, 4),
        total_decisions=total,
        coherent_decisions=coherent,
        hallucinations=hallucinations,
        action_distribution=dict(action_counts),
    )


# =============================================================================
# CACR Decomposition
# =============================================================================

def _tp_quadrant(tp: str) -> str:
    return "high" if tp in ("H", "VH") else "low"


def _cp_quadrant(cp: str) -> str:
    return "high" if cp in ("H", "VH") else "low"


def compute_cacr_decomposition(audit_csv_paths: List[Path]) -> Optional[CACRDecomposition]:
    """Compute CACR decomposition from governance audit CSVs."""
    rows = []
    for path in audit_csv_paths:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, encoding='utf-8-sig')
            rows.append(df)
        except Exception as e:
            print(f"  Warning: Could not read audit CSV {path}: {e}")
            continue

    if not rows:
        return None

    audit = pd.concat(rows, ignore_index=True)

    tp_col = None
    cp_col = None
    for col in audit.columns:
        if col in ("construct_TP_LABEL", "reason_tp_label"):
            tp_col = col
        if col in ("construct_CP_LABEL", "reason_cp_label"):
            cp_col = col

    if tp_col is None or cp_col is None or "proposed_skill" not in audit.columns:
        print("  Warning: Audit CSV missing required columns for CACR decomposition")
        return None

    household_mask = audit["agent_id"].astype(str).str.startswith("H")
    audit = audit[household_mask].copy()

    if len(audit) == 0:
        return None

    def _get_rules_for_row(row):
        agent_id = str(row.get("agent_id", ""))
        try:
            num = int(agent_id.replace("H", "").replace("h", ""))
            if num > 200:
                return PMT_RENTER_RULES
            return PMT_OWNER_RULES
        except (ValueError, IndexError):
            proposed = _normalize_action(row.get("proposed_skill", "do_nothing"))
            if proposed == "relocate":
                return PMT_RENTER_RULES
            return PMT_OWNER_RULES

    raw_coherent = 0
    total = len(audit)
    quadrant_counts = {}
    extraction_skipped = 0

    for _, row in audit.iterrows():
        tp = str(row.get(tp_col, "")).strip()
        cp = str(row.get(cp_col, "")).strip()
        if not tp or not cp or tp == "nan" or cp == "nan":
            extraction_skipped += 1
            continue
        proposed = _normalize_action(row.get("proposed_skill", "do_nothing"))
        rules = _get_rules_for_row(row)

        key = (tp, cp)
        is_coherent = proposed in rules.get(key, [])
        if is_coherent:
            raw_coherent += 1

        q_key = f"TP_{_tp_quadrant(tp)}_CP_{_cp_quadrant(cp)}"
        if q_key not in quadrant_counts:
            quadrant_counts[q_key] = [0, 0]
        quadrant_counts[q_key][1] += 1
        if is_coherent:
            quadrant_counts[q_key][0] += 1

    total = total - extraction_skipped

    final_col = "final_skill" if "final_skill" in audit.columns else "proposed_skill"
    approved_mask = audit.get("outcome", audit.get("status", "")).isin(["APPROVED", "RETRY_SUCCESS"])
    approved = audit[approved_mask]

    final_coherent = 0
    for _, row in approved.iterrows():
        tp = str(row.get(tp_col, "")).strip()
        cp = str(row.get(cp_col, "")).strip()
        if not tp or not cp or tp == "nan" or cp == "nan":
            continue
        final = _normalize_action(row.get(final_col, "do_nothing"))
        rules = _get_rules_for_row(row)
        key = (tp, cp)
        if final in rules.get(key, []):
            final_coherent += 1

    cacr_raw = raw_coherent / total if total > 0 else 0.0
    cacr_final = final_coherent / len(approved) if len(approved) > 0 else 0.0

    retry_col = "retry_count" if "retry_count" in audit.columns else None
    retry_rate = 0.0
    if retry_col:
        retry_rate = (audit[retry_col].fillna(0).astype(int) > 0).mean()

    fallback_rate = 0.0
    if final_col in audit.columns and "proposed_skill" in audit.columns:
        fallback_rate = (
            audit[final_col].fillna("") != audit["proposed_skill"].fillna("")
        ).mean()

    quadrant_cacr = {
        k: round(v[0] / v[1], 4) if v[1] > 0 else 0.0
        for k, v in quadrant_counts.items()
    }

    return CACRDecomposition(
        cacr_raw=round(cacr_raw, 4),
        cacr_final=round(cacr_final, 4),
        retry_rate=round(retry_rate, 4),
        fallback_rate=round(fallback_rate, 4),
        total_proposals=total,
        quadrant_cacr=quadrant_cacr,
    )
