"""
Model Conservatism Diagnostic — detects systematic bias in LLM construct assessments.

Complements CACR (coherence) and EPI (plausibility) by measuring whether a model's
subjective assessments are misaligned with objective context. Motivated by Gemma 4
results where TP=H was reported in only 16% of flooded decisions.

Metrics:
  CCA  — Construct-Context Alignment: does TP rise when flood occurs?
  CSI  — Construct Sensitivity Index: does TP scale with flood severity?
  ACI  — Action Concentration Index: is behavior over-concentrated?
  ESRR — Extreme Scenario Response Rate: does model escalate in worst cases?
"""
from __future__ import annotations

import math
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
from scipy import stats


TP_MAP = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
STRONG_ACTIONS = {"elevate_house", "buyout_program", "relocate"}
PROTECTIVE_ACTIONS = {"buy_insurance", "buy_contents_insurance",
                      "elevate_house", "buyout_program", "relocate"}


@dataclass
class ConservatismReport:
    """Results of conservatism diagnostic for a single model/condition."""
    model: str
    condition: str  # "governed" or "disabled"
    n_decisions: int = 0
    cca: float = float("nan")       # Construct-Context Alignment [0-1]
    csi: float = float("nan")       # Construct Sensitivity Index [-1,1]
    aci: float = float("nan")       # Action Concentration Index [0-1]
    esrr: float = float("nan")      # Extreme Scenario Response Rate [0-1]
    tp_distribution: Dict[str, int] = field(default_factory=dict)
    action_distribution: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def summary_row(self) -> dict:
        return {
            "model": self.model,
            "condition": self.condition,
            "n": self.n_decisions,
            "CCA": round(self.cca, 3) if not math.isnan(self.cca) else "N/A",
            "CSI": round(self.csi, 3) if not math.isnan(self.csi) else "N/A",
            "ACI": round(self.aci, 3) if not math.isnan(self.aci) else "N/A",
            "ESRR": round(self.esrr, 3) if not math.isnan(self.esrr) else "N/A",
            "TP_H+VH%": round(
                sum(self.tp_distribution.get(k, 0) for k in ("H", "VH"))
                / max(self.n_decisions, 1) * 100, 1),
            "top_action": max(self.action_distribution, key=self.action_distribution.get)
                          if self.action_distribution else "N/A",
            "warnings": "; ".join(self.warnings) if self.warnings else "",
        }


def _load_audit(audit_path: str) -> pd.DataFrame:
    """Load governance audit CSV with encoding fallback."""
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return pd.read_csv(audit_path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Cannot read {audit_path}")


def _load_sim_log(sim_log_path: str) -> Optional[pd.DataFrame]:
    """Load simulation_log.csv if available."""
    p = Path(sim_log_path)
    if not p.exists():
        return None
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except Exception:
        return None


def compute_cca(df: pd.DataFrame, sim_log: Optional[pd.DataFrame]) -> float:
    """CCA: Fraction of flooded-year decisions with TP >= H.

    If simulation_log not available, uses all years (assumes flood-prone area).
    """
    tp_num = df["construct_TP_LABEL"].map(TP_MAP)

    if sim_log is not None and "flood_event" in sim_log.columns:
        # Merge flood_event by year
        flood_years = sim_log[sim_log["flood_event"] == True]["year"].unique()
        flooded = df[df["year"].isin(flood_years)]
        if len(flooded) == 0:
            return float("nan")
        tp_flooded = flooded["construct_TP_LABEL"].map(TP_MAP)
        return (tp_flooded >= 4).mean()
    else:
        # Fallback: all years (PRB is flood-prone every year)
        return (tp_num >= 4).mean()


def compute_csi(df: pd.DataFrame, traces_path: Optional[str] = None) -> float:
    """CSI: Spearman correlation between flood exposure proxy and TP.

    Uses year as proxy for cumulative exposure (more floods over time).
    If traces available, could use actual flood_depth.
    """
    tp_num = df["construct_TP_LABEL"].map(TP_MAP).dropna()
    years = df.loc[tp_num.index, "year"]

    if len(tp_num) < 10:
        return float("nan")

    rho, _ = stats.spearmanr(years, tp_num)
    return rho


def compute_aci(df: pd.DataFrame) -> float:
    """ACI: 1 - normalized Shannon entropy of action distribution.

    0 = perfectly diverse, 1 = all same action.
    """
    action_col = "final_skill" if "final_skill" in df.columns else "proposed_skill"
    counts = df[action_col].value_counts()
    n_actions = len(counts)

    if n_actions <= 1:
        return 1.0

    probs = counts / counts.sum()
    entropy = -(probs * np.log2(probs)).sum()
    max_entropy = np.log2(n_actions)

    return 1.0 - (entropy / max_entropy) if max_entropy > 0 else 1.0


def compute_esrr(df: pd.DataFrame, sim_log: Optional[pd.DataFrame]) -> float:
    """ESRR: Among agents with 3+ floods, fraction choosing strong actions."""
    action_col = "final_skill" if "final_skill" in df.columns else "proposed_skill"

    if sim_log is not None and "flood_count" in sim_log.columns:
        # Merge flood_count from sim_log
        merged = df.merge(
            sim_log[["agent_id", "year", "flood_count"]].drop_duplicates(),
            on=["agent_id", "year"], how="left"
        )
        severe = merged[merged["flood_count"] >= 3]
    else:
        # Fallback: use late years (years 7+) as proxy for repeated exposure
        severe = df[df["year"] >= 7]

    if len(severe) == 0:
        return float("nan")

    return severe[action_col].isin(STRONG_ACTIONS).mean()


def run_conservatism_diagnostic(
    audit_path: str,
    sim_log_path: str = None,
    traces_path: str = None,
    model_name: str = "unknown",
    condition: str = "unknown",
) -> ConservatismReport:
    """Run all 4 conservatism metrics on a single experiment."""
    df = _load_audit(audit_path)
    sim_log = _load_sim_log(sim_log_path) if sim_log_path else None

    report = ConservatismReport(model=model_name, condition=condition)
    report.n_decisions = len(df)

    # TP distribution
    tp_counts = df["construct_TP_LABEL"].value_counts().to_dict()
    report.tp_distribution = {k: tp_counts.get(k, 0) for k in ("VL", "L", "M", "H", "VH")}

    # Action distribution
    action_col = "final_skill" if "final_skill" in df.columns else "proposed_skill"
    report.action_distribution = df[action_col].value_counts().to_dict()

    # Metrics
    report.cca = compute_cca(df, sim_log)
    report.csi = compute_csi(df, traces_path)
    report.aci = compute_aci(df)
    report.esrr = compute_esrr(df, sim_log)

    # Warnings
    if report.cca < 0.3:
        report.warnings.append(f"CCA={report.cca:.2f}: model severely under-reports threat")
    elif report.cca < 0.5:
        report.warnings.append(f"CCA={report.cca:.2f}: model under-reports threat")

    if report.aci > 0.5:
        report.warnings.append(f"ACI={report.aci:.2f}: action over-concentration")

    if not math.isnan(report.esrr) and report.esrr < 0.05:
        report.warnings.append(f"ESRR={report.esrr:.2f}: model does not escalate in severe scenarios")

    return report
