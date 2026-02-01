"""
Unified hallucination rate (R_H) computation across groups.

Provides a single entry point for computing the hallucination rate using
consistent methodology regardless of data source:

    Group A:  keyword-classified appraisals → thinking rules (V1/V2/V3)
    Group B/C: structured labels from governance → thinking rules + runtime counts

The formula:  R_H = (physical + thinking) / N_active

Where:
    physical  = re-elevation + post-relocation actions (from state transitions)
    thinking  = V1 + V2 + V3 violations (from classified constructs)
    N_active  = agent-year pairs where agent has not yet relocated
"""

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from broker.validators.posthoc.keyword_classifier import KeywordClassifier
from broker.validators.posthoc.thinking_rule_posthoc import ThinkingRulePostHoc


def _compute_physical_hallucinations(df: pd.DataFrame) -> pd.Series:
    """Detect physical hallucinations from state transitions.

    Returns boolean mask where True = physical hallucination.
    Checks:
    - Re-elevation (already elevated, chose elevate again)
    - Post-relocation action (already relocated, chose any property action)

    Insurance renewal is excluded (annual renewable, not hallucination).
    """
    df_s = df.sort_values(["agent_id", "year"]).copy()
    df_s["prev_elevated"] = df_s.groupby("agent_id")["elevated"].shift(1).fillna(False).infer_objects(copy=False)
    df_s["prev_relocated"] = df_s.groupby("agent_id")["relocated"].shift(1).fillna(False).infer_objects(copy=False)

    dec_col = "yearly_decision"
    if dec_col not in df_s.columns:
        dec_col = "decision"

    action = df_s[dec_col].astype(str).str.lower()

    # Re-elevation: chose elevate when already elevated
    re_elevation = df_s["prev_elevated"] & action.str.contains("elevat", na=False)

    # Post-relocation: agent acts after relocating (excluding "relocated" status marker)
    is_active_decision = ~action.isin(["relocated", "n/a", "nan", "none", ""])
    post_relocation = df_s["prev_relocated"] & is_active_decision

    return re_elevation | post_relocation


def compute_hallucination_rate(
    df: pd.DataFrame,
    group: str = "B",
    ta_col: str = "threat_appraisal",
    ca_col: str = "coping_appraisal",
    decision_col: str = "yearly_decision",
    start_year: int = 2,
    classifier: Optional[KeywordClassifier] = None,
    rule_checker: Optional[ThinkingRulePostHoc] = None,
) -> Dict[str, object]:
    """Compute unified R_H for a simulation DataFrame.

    Parameters
    ----------
    df : DataFrame
        Simulation log with columns: agent_id, year, yearly_decision,
        elevated, relocated, has_insurance, and appraisal columns.
    group : str
        ``"A"``, ``"B"``, or ``"C"`` — affects keyword threshold.
    ta_col, ca_col : str
        Columns with threat/coping appraisal text.
    decision_col : str
        Column with yearly decision.
    start_year : int
        First year to include (default 2, skipping initialization year).
    classifier : KeywordClassifier, optional
        Custom classifier (default: standard PMT keywords).
    rule_checker : ThinkingRulePostHoc, optional
        Custom rule checker (default: standard V1/V2/V3).

    Returns
    -------
    dict with keys:
        rh : float — overall R_H
        rh_physical : float — physical hallucination rate
        rh_thinking : float — thinking hallucination rate
        n_physical : int — count of physical hallucinations
        n_thinking : int — count of thinking violations
        n_active : int — total active agent-year observations
        thinking_breakdown : dict — {V1: n, V2: n, V3: n}
        yearly_rh : list[float] — per-year R_H values
        yearly_hn : list[float] — per-year normalized entropy
        yearly_ebe : list[float] — per-year EBE values
        ebe : float — mean EBE
    """
    if classifier is None:
        classifier = KeywordClassifier()
    if rule_checker is None:
        rule_checker = ThinkingRulePostHoc()

    df = df.sort_values(["agent_id", "year"]).copy()

    # Classify appraisals
    if ta_col in df.columns and ca_col in df.columns:
        df = classifier.classify_dataframe(df, ta_col, ca_col)
    else:
        df["ta_level"] = "M"
        df["ca_level"] = "M"

    # Identify active observations (not yet relocated)
    df["prev_relocated"] = df.groupby("agent_id")["relocated"].shift(1).fillna(False).infer_objects(copy=False)
    active_mask = ~df["prev_relocated"] & (df["year"] >= start_year)
    df_active = df[active_mask].copy()

    n_active = len(df_active)
    if n_active == 0:
        return {
            "rh": 0.0, "rh_physical": 0.0, "rh_thinking": 0.0,
            "n_physical": 0, "n_thinking": 0, "n_active": 0,
            "thinking_breakdown": {}, "yearly_rh": [], "yearly_hn": [],
            "yearly_ebe": [], "ebe": 0.0,
        }

    # Physical hallucinations
    phys_mask = _compute_physical_hallucinations(df)
    phys_active = phys_mask.reindex(df_active.index, fill_value=False)
    n_physical = int(phys_active.sum())

    # Thinking violations (V1/V2/V3)
    rule_results = rule_checker.apply(
        df_active, group=group, decision_col=decision_col, ta_level_col="ta_level"
    )
    n_thinking = rule_checker.total_violations(rule_results)
    thinking_breakdown = rule_checker.summary_dict(rule_results)

    # Overall R_H
    n_hall = n_physical + n_thinking
    rh = n_hall / n_active if n_active > 0 else 0.0

    # Per-year metrics
    h_max = np.log2(4)  # max entropy for 4 actions
    yearly_rh, yearly_hn, yearly_ebe = [], [], []

    for yr in sorted(df_active["year"].unique()):
        yr_df = df_active[df_active["year"] == yr]
        n_yr = len(yr_df)
        if n_yr == 0:
            continue

        # Year-level physical hallucinations
        yr_phys = phys_active.reindex(yr_df.index, fill_value=False).sum()

        # Year-level thinking violations
        yr_think_results = rule_checker.apply(
            yr_df, group=group, decision_col=decision_col, ta_level_col="ta_level"
        )
        yr_think = rule_checker.total_violations(yr_think_results)

        yr_hall = yr_phys + yr_think
        yr_rh = yr_hall / n_yr

        # Normalized entropy
        action_counts = yr_df[decision_col].value_counts()
        probs = action_counts / action_counts.sum()
        h_raw = -np.sum(probs * np.log2(probs + 1e-12))
        yr_hn = h_raw / h_max if h_max > 0 else 0.0

        yr_ebe = yr_hn * (1 - yr_rh)

        yearly_rh.append(float(yr_rh))
        yearly_hn.append(float(yr_hn))
        yearly_ebe.append(float(yr_ebe))

    ebe_mean = float(np.mean(yearly_ebe)) if yearly_ebe else 0.0

    return {
        "rh": float(rh),
        "rh_physical": float(n_physical / n_active) if n_active > 0 else 0.0,
        "rh_thinking": float(n_thinking / n_active) if n_active > 0 else 0.0,
        "n_physical": n_physical,
        "n_thinking": n_thinking,
        "n_active": n_active,
        "thinking_breakdown": thinking_breakdown,
        "yearly_rh": yearly_rh,
        "yearly_hn": yearly_hn,
        "yearly_ebe": yearly_ebe,
        "ebe": ebe_mean,
    }
