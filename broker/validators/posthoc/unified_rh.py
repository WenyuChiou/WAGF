"""
Unified hallucination rate (R_H) computation across groups.

Domain-agnostic R_H computation.  Callers specify column names and
irreversible-state mappings via parameters so this module works for
any domain (flood, irrigation, etc.).

Provides a single entry point for computing the hallucination rate using
consistent methodology regardless of data source:

    Group A:  keyword-classified appraisals → thinking rules (V1/V2/V3)
    Group B/C: structured labels from governance → thinking rules + runtime counts

The formula:  R_H = (physical + thinking) / N_active

Where:
    physical  = irreversible-state violations (from state transitions)
    thinking  = V1 + V2 + V3 violations (from classified constructs)
    N_active  = agent-year pairs where agent has not yet exited

Column names and irreversible states are parameterized; callers
supply domain-appropriate values.
"""

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from broker.validators.posthoc.keyword_classifier import KeywordClassifier
from broker.validators.posthoc.thinking_rule_posthoc import ThinkingRulePostHoc


def _compute_physical_hallucinations(
    df: pd.DataFrame,
    irreversible_states: Optional[Dict[str, Optional[str]]] = None,
    exit_state_col: str = "relocated",
) -> pd.Series:
    """Detect physical hallucinations from state transitions.

    Returns boolean mask where True = physical hallucination.

    Parameters
    ----------
    df : DataFrame
        Must have agent_id, year, a decision column, and state columns
        named by *irreversible_states* keys.
    irreversible_states : dict, optional
        Maps state column name → action substring pattern.
        An agent who already has ``state_col == True`` and whose decision
        contains the pattern is flagged as a physical hallucination.
        Use ``None`` as the pattern value to flag *any* active decision
        after the state becomes True (e.g. post-relocation).
        Default: ``{"elevated": "elevat", "relocated": None}``.
    exit_state_col : str
        Column marking the permanent exit state (agent leaves simulation).
        Default: ``"relocated"``.

    Insurance renewal is excluded (annual renewable, not hallucination).
    """
    if irreversible_states is None:
        irreversible_states = {"elevated": "elevat", "relocated": None}

    df_s = df.sort_values(["agent_id", "year"]).copy()

    dec_col = "yearly_decision"
    if dec_col not in df_s.columns:
        dec_col = "decision"

    action = df_s[dec_col].astype(str).str.lower()
    hallucination_mask = pd.Series(False, index=df_s.index)

    for state_col, action_pattern in irreversible_states.items():
        if state_col not in df_s.columns:
            continue
        prev_state = df_s.groupby("agent_id")[state_col].shift(1).fillna(False).infer_objects(copy=False)
        if action_pattern is not None:
            # Repeated action on an already-achieved irreversible state
            hallucination_mask = hallucination_mask | (
                prev_state & action.str.contains(action_pattern, na=False)
            )
        else:
            # Any active decision after exit (e.g. post-relocation)
            is_active = ~action.isin([state_col, "n/a", "nan", "none", ""])
            hallucination_mask = hallucination_mask | (prev_state & is_active)

    return hallucination_mask


def compute_hallucination_rate(
    df: pd.DataFrame,
    group: str = "B",
    ta_col: str = "threat_appraisal",
    ca_col: str = "coping_appraisal",
    decision_col: str = "yearly_decision",
    start_year: int = 2,
    classifier: Optional[KeywordClassifier] = None,
    rule_checker: Optional[ThinkingRulePostHoc] = None,
    irreversible_states: Optional[Dict[str, Optional[str]]] = None,
    exit_state_col: str = "relocated",
) -> Dict[str, object]:
    """Compute unified R_H for a simulation DataFrame.

    Parameters
    ----------
    df : DataFrame
        Simulation log with columns: agent_id, year, a decision column,
        state columns named by *irreversible_states* keys, and appraisal
        columns.
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
    irreversible_states : dict, optional
        Passed to ``_compute_physical_hallucinations``.
        Default: ``{"elevated": "elevat", "relocated": None}``.
    exit_state_col : str
        Column marking permanent exit state used to filter active
        observations.  Default: ``"relocated"``.

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

    # Identify active observations (not yet exited)
    prev_exit = df.groupby("agent_id")[exit_state_col].shift(1).fillna(False).infer_objects(copy=False)
    active_mask = ~prev_exit & (df["year"] >= start_year)
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
    phys_mask = _compute_physical_hallucinations(
        df, irreversible_states=irreversible_states, exit_state_col=exit_state_col,
    )
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
