"""
L1 Micro Validation Metrics.

CACR (Construct-Action Coherence Rate), R_H (Hallucination Rate),
EBE (Effective Behavioral Entropy), and CACR Decomposition.
"""

import math
from pathlib import Path
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np
import pandas as pd

from validation.theories.pmt import (
    PMT_OWNER_RULES,
    PMT_RENTER_RULES,
    PMTTheory,
    _is_sensible_action,
)
from validation.io.trace_reader import (
    _extract_tp_label,
    _extract_cp_label,
    _extract_action,
    _normalize_action,
)
from validation.hallucinations.flood import _is_hallucination, FloodHallucinationChecker
from validation.hallucinations.base import NullHallucinationChecker
from validation.metrics.entropy import _compute_entropy

if TYPE_CHECKING:
    from validation.theories.base import BehavioralTheory
    from validation.hallucinations.base import HallucinationChecker


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
        """Check if metrics pass publication thresholds.

        Threshold justifications:
            CACR >= 0.75: Derived from inter-rater reliability conventions.
                Cohen's kappa >= 0.60 is "substantial agreement" (Landis & Koch, 1977).
                CACR maps to agreement rate; kappa=0.60 corresponds to ~75% agreement
                for typical marginal distributions (Sim & Wright, 2005). Additionally,
                human inter-coder reliability in behavioral coding studies typically
                achieves 70-85% (Bakeman & Gottman, 1997). The 0.75 threshold
                represents the lower bound of acceptable human-level coherence.
            R_H <= 0.10: Physical impossibilities should be rare. 10% tolerance
                accounts for LLM parsing errors and edge cases in state tracking.
            EBE ratio 0.1-0.9: Avoids degenerate distributions (all same action)
                while allowing natural skew toward common actions.
        """
        return {
            "CACR": self.cacr >= 0.75,
            "R_H": self.r_h <= 0.10,
            "EBE": 0.1 < self.ebe_ratio < 0.9 if self.ebe_max > 0 else False,
        }


# =============================================================================
# L1 Metric Computation
# =============================================================================

def compute_l1_metrics(
    traces: List[Dict],
    agent_type: str = "owner",
    theory: Optional["BehavioralTheory"] = None,
    action_space_size: Optional[int] = None,
    hallucination_checker: Optional["HallucinationChecker"] = None,
) -> L1Metrics:
    """Compute L1 micro-level validation metrics.

    Args:
        traces: List of decision trace dicts.
        agent_type: "owner" or "renter".
        theory: BehavioralTheory implementation. Defaults to PMTTheory().
        action_space_size: Fixed action space size for EHE normalization.
            If None, defaults to 4 for owner, 3 for renter.
        hallucination_checker: HallucinationChecker implementation.
            Defaults to FloodHallucinationChecker() for backward compatibility.
    """
    if theory is None:
        theory = PMTTheory()
    if hallucination_checker is None:
        hallucination_checker = FloodHallucinationChecker()

    total = len(traces)
    coherent = 0
    hallucinations = 0
    extraction_failures = 0
    action_counts = Counter()

    for trace in traces:
        action = _extract_action(trace)
        action = _normalize_action(action)
        action_counts[action] += 1

        constructs = theory.extract_constructs(trace)
        if any(v == "UNKNOWN" for v in constructs.values()):
            extraction_failures += 1
            continue

        coherent_actions = theory.get_coherent_actions(constructs, agent_type)
        if coherent_actions:
            if action in coherent_actions:
                coherent += 1
        else:
            if theory.is_sensible_action(constructs, action, agent_type):
                coherent += 1

        if hallucination_checker.is_hallucination(trace):
            hallucinations += 1

    if extraction_failures > 0:
        print(f"  WARNING: {extraction_failures} traces with UNKNOWN TP/CP labels excluded from CACR")

    cacr_eligible = total - extraction_failures
    cacr = coherent / cacr_eligible if cacr_eligible > 0 else 0.0
    r_h = hallucinations / total if total > 0 else 0.0
    ebe = _compute_entropy(action_counts)
    # Use fixed action space size for consistent cross-model/cross-domain comparison
    if action_space_size is not None:
        k = action_space_size
    else:
        k = {"owner": 4, "renter": 3}.get(agent_type, len(action_counts))
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


def compute_cacr_decomposition(
    audit_csv_paths: List[Path],
    theory: Optional["BehavioralTheory"] = None,
) -> Optional[CACRDecomposition]:
    """Compute CACR decomposition from governance audit CSVs.

    Args:
        audit_csv_paths: Paths to governance audit CSV files.
        theory: BehavioralTheory implementation. Defaults to PMTTheory().
    """
    if theory is None:
        theory = PMTTheory()

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

    # Determine agent_type per row: prefer audit CSV column, fallback to heuristic
    has_agent_type_col = "agent_type" in audit.columns

    def _get_agent_type_for_row(row) -> str:
        if has_agent_type_col:
            at = str(row.get("agent_type", "")).strip().lower()
            if at in ("owner", "renter"):
                return at
        # Fallback: agent_id heuristic
        agent_id = str(row.get("agent_id", ""))
        try:
            num = int(agent_id.replace("H", "").replace("h", ""))
            if num > 200:
                return "renter"
            return "owner"
        except (ValueError, IndexError):
            proposed = _normalize_action(row.get("proposed_skill", "do_nothing"))
            if proposed == "relocate":
                return "renter"
            return "owner"

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
        agent_type = _get_agent_type_for_row(row)
        constructs = {"TP": tp, "CP": cp}
        coherent_actions = theory.get_coherent_actions(constructs, agent_type)

        is_coherent = proposed in coherent_actions if coherent_actions else False
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
        agent_type = _get_agent_type_for_row(row)
        constructs = {"TP": tp, "CP": cp}
        coherent_actions = theory.get_coherent_actions(constructs, agent_type)
        if final in coherent_actions:
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
