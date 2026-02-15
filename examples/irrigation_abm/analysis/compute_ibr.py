#!/usr/bin/env python3
"""
Irrational Behavioral Ratio (IBR) Computation for Irrigation ABM

Computes IBR metrics for irrigation domain following the dual-appraisal framework
(WSA/ACA → skill coherence). Analogous to CACR (Construct-Action Coherence Rate)
from the flood domain PMT validation.

IBR Decomposition:
    - IBR_physical: Hard constraint violations (economic hallucination)
    - IBR_coherence: Dual-appraisal incoherence (WSA/ACA → skill mismatch)
    - IBR_temporal: Temporal inconsistency (compound growth during drought)
    - CACR_irrigation: 1 - IBR_coherence (coherence rate, higher is better)

Data Sources:
    - simulation_log.csv: agent state (request, diversion, shortage_tier, etc.)
                          + WSA/ACA labels + final decisions
    - governance_audit.csv: proposed_skill (pre-governance) for IBR comparison

Usage:
    # Single run (governed)
    python compute_ibr.py --results-dir results/production_v20_42yr_seed42

    # Single run (ungoverned)
    python compute_ibr.py --results-dir results/ungoverned_v20_42yr_seed42

    # Comparison mode
    python compute_ibr.py --results-dir results/production_v20_42yr_seed42 \
        --compare-ungoverned results/ungoverned_v20_42yr_seed42

References:
    - Flood domain CACR: examples/single_agent/analysis/
    - Dual-appraisal theory: Hung & Yang (2021)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# WSA/ACA → Skill Coherence Rules (Rule Set B)
# =============================================================================

# Rational skills for each (WSA, ACA) combination based on dual-appraisal theory
# WSA = Water Scarcity Assessment (analog to TP in flood domain)
# ACA = Adaptive Capacity Assessment (analog to CP in flood domain)
IRRIGATION_COHERENCE_RULES = {
    # High scarcity → conservation pressure
    ("VH", "VH"): ["decrease_large", "decrease_small"],
    ("VH", "H"): ["decrease_large", "decrease_small"],
    ("VH", "M"): ["decrease_small", "maintain_demand"],
    ("VH", "L"): ["maintain_demand"],  # Adaptive paralysis
    ("VH", "VL"): ["maintain_demand"],

    ("H", "VH"): ["decrease_large", "decrease_small"],
    ("H", "H"): ["decrease_large", "decrease_small"],
    ("H", "M"): ["decrease_small", "maintain_demand"],
    ("H", "L"): ["maintain_demand"],
    ("H", "VL"): ["maintain_demand"],

    # Moderate scarcity → balanced actions
    ("M", "VH"): ["maintain_demand", "decrease_small", "increase_small"],
    ("M", "H"): ["maintain_demand", "decrease_small", "increase_small"],
    ("M", "M"): ["maintain_demand"],
    ("M", "L"): ["maintain_demand"],
    ("M", "VL"): ["maintain_demand"],

    # Low scarcity → expansion justified
    ("L", "VH"): ["increase_small", "increase_large", "maintain_demand"],
    ("L", "H"): ["increase_small", "increase_large", "maintain_demand"],
    ("L", "M"): ["maintain_demand", "increase_small"],
    ("L", "L"): ["maintain_demand"],
    ("L", "VL"): ["maintain_demand"],

    ("VL", "VH"): ["increase_small", "increase_large", "maintain_demand"],
    ("VL", "H"): ["increase_small", "increase_large", "maintain_demand"],
    ("VL", "M"): ["maintain_demand", "increase_small"],
    ("VL", "L"): ["maintain_demand"],
    ("VL", "VL"): ["maintain_demand"],
}

INCREASE_SKILLS = frozenset({"increase_large", "increase_small"})
DECREASE_SKILLS = frozenset({"decrease_large", "decrease_small"})


# =============================================================================
# Data Loading
# =============================================================================

def load_run_data(results_dir: Path) -> pd.DataFrame:
    """
    Load and merge simulation_log + governance_audit from a results directory.

    Returns a single DataFrame with:
        - agent_id, year (index key)
        - wsa_label, aca_label (appraisals)
        - proposed_skill (from audit, pre-governance)
        - final_skill / yearly_decision (post-governance)
        - Physical state: request, diversion, water_right, shortage_tier, etc.
    """
    sim_path = results_dir / "simulation_log.csv"
    audit_path = results_dir / "irrigation_farmer_governance_audit.csv"

    if not sim_path.exists():
        raise FileNotFoundError(f"simulation_log.csv not found in {results_dir}")

    sim = pd.read_csv(sim_path, encoding="utf-8-sig")

    # Merge with audit if available (for proposed_skill)
    if audit_path.exists():
        audit = pd.read_csv(audit_path, encoding="utf-8-sig")
        # Keep only agent rows
        if "agent_id" in audit.columns:
            audit = audit[audit["agent_id"].astype(str).str.len() > 0].copy()

        # Extract proposed_skill and WSA/ACA from audit
        audit_cols = ["agent_id", "year", "proposed_skill", "final_skill", "status"]

        # WSA/ACA from audit: try construct_ columns first, then reason_ columns
        for label, candidates in [
            ("audit_wsa", ["construct_WSA_LABEL", "reason_wsa_label"]),
            ("audit_aca", ["construct_ACA_LABEL", "reason_aca_label"]),
        ]:
            for col in candidates:
                if col in audit.columns:
                    audit[label] = audit[col].astype(str).str.strip().str.upper()
                    break
            else:
                audit[label] = "M"

        keep_cols = [c for c in audit_cols + ["audit_wsa", "audit_aca"] if c in audit.columns]
        audit_slim = audit[keep_cols].copy()

        # Merge on agent_id + year
        df = sim.merge(audit_slim, on=["agent_id", "year"], how="left")
    else:
        df = sim.copy()
        df["proposed_skill"] = df["yearly_decision"]  # Ungoverned: proposed = final
        df["final_skill"] = df["yearly_decision"]

    # Normalize WSA/ACA labels (prefer simulation_log, fallback to audit)
    for label, sim_col, audit_col in [
        ("WSA", "wsa_label", "audit_wsa"),
        ("ACA", "aca_label", "audit_aca"),
    ]:
        if sim_col in df.columns:
            df[label] = df[sim_col].astype(str).str.strip().str.upper()
        elif audit_col in df.columns:
            df[label] = df[audit_col]
        else:
            df[label] = "M"
        # Validate labels
        valid = {"VH", "H", "M", "L", "VL"}
        df[label] = df[label].where(df[label].isin(valid), "M")

    # Fill proposed_skill from yearly_decision if missing
    if "proposed_skill" not in df.columns or df["proposed_skill"].isna().all():
        df["proposed_skill"] = df["yearly_decision"]
    else:
        df["proposed_skill"] = df["proposed_skill"].fillna(df["yearly_decision"])

    if "final_skill" not in df.columns or df["final_skill"].isna().all():
        df["final_skill"] = df["yearly_decision"]
    else:
        df["final_skill"] = df["final_skill"].fillna(df["yearly_decision"])

    return df


# =============================================================================
# Rule Set A: Physical Impossibilities
# =============================================================================

def is_physical_violation(row: pd.Series, skill_col: str = "proposed_skill") -> bool:
    """
    Check if skill violates hard physical constraints.

    Rule A1: Increase at water right cap (utilisation >= 95%)
    Rule A2: Decrease below minimum utilisation (already below 5%)
    Rule A3: Increase during supply gap (fulfillment < 70%)
    Rule A4: Increase during Tier 2+ shortage (DCP mandatory conservation)
    """
    skill = str(row.get(skill_col, "maintain_demand")).lower()

    # Rule A1: Increase at water right cap (utilisation_pct is 0-100 scale)
    if skill in INCREASE_SKILLS:
        util = row.get("utilisation_pct")
        if pd.notna(util):
            if float(util) >= 95.0:
                return True

    # Rule A2: Decrease below minimum utilization
    if skill in DECREASE_SKILLS:
        below_min = row.get("below_minimum_utilisation")
        if pd.notna(below_min) and str(below_min).lower() == "true":
            return True

    # Rule A3: Increase during supply gap (fulfillment < 70%)
    if skill in INCREASE_SKILLS:
        request = row.get("request")
        diversion = row.get("diversion")
        if pd.notna(request) and pd.notna(diversion):
            req = float(request)
            div = float(diversion)
            if req > 0 and div > 0:
                fulfillment = div / req
                if fulfillment < 0.70:
                    return True

    # Rule A4: Increase during Tier 2+ shortage
    if skill in INCREASE_SKILLS:
        tier = row.get("shortage_tier")
        if pd.notna(tier) and int(float(tier)) >= 2:
            return True

    return False


# =============================================================================
# Rule Set B: Dual-Appraisal Coherence
# =============================================================================

def is_coherent_skill(row: pd.Series, skill_col: str = "proposed_skill") -> bool:
    """
    Check if skill is coherent with WSA/ACA appraisals.
    """
    wsa = str(row.get("WSA", "M")).strip().upper()
    aca = str(row.get("ACA", "M")).strip().upper()
    skill = str(row.get(skill_col, "maintain_demand")).lower()

    rational_skills = IRRIGATION_COHERENCE_RULES.get((wsa, aca), ["maintain_demand"])
    return skill in rational_skills


# =============================================================================
# Rule Set C: Temporal Violations
# =============================================================================

def compute_temporal_violations(
    df: pd.DataFrame, skill_col: str = "proposed_skill"
) -> Tuple[int, int]:
    """
    Compute temporal violations (Rule Set C).

    Rule C1: 4+ consecutive increases during drought (drought_index >= 0.7)
    """
    if "agent_id" not in df.columns or "year" not in df.columns:
        return 0, 0

    violations = 0
    total_applicable = 0

    for _, group in df.groupby("agent_id"):
        group = group.sort_values("year")
        consecutive_increase = 0

        for _, row in group.iterrows():
            skill = str(row.get(skill_col, "maintain_demand")).lower()
            drought = row.get("drought_index", 0.5)
            if pd.isna(drought):
                drought = 0.5
            drought = float(drought)

            if skill in INCREASE_SKILLS:
                consecutive_increase += 1
            else:
                consecutive_increase = 0

            if consecutive_increase >= 4 and drought >= 0.7:
                violations += 1
                total_applicable += 1
            elif consecutive_increase >= 3:
                total_applicable += 1

    return violations, total_applicable


# =============================================================================
# EHE (Effective Heterogeneity Entropy)
# =============================================================================

def compute_ehe(df: pd.DataFrame, skill_col: str = "yearly_decision") -> Dict[str, float]:
    """
    Compute Effective Heterogeneity Entropy.

    EHE = H / log2(k) where k = number of available skills (5 for irrigation).
    Returns both per-year mean and aggregate EHE.
    Paper should use ehe_aggregate for cross-domain comparison.
    """
    k = 5  # increase_large, increase_small, maintain_demand, decrease_small, decrease_large
    ehe_by_year = {}

    for year, group in df.groupby("year"):
        skills = group[skill_col].dropna().astype(str).str.lower()
        counts = skills.value_counts()
        probs = counts / counts.sum()
        H = -(probs * np.log2(probs)).sum()
        ehe_by_year[int(year)] = round(H / np.log2(k), 4) if k > 1 else 0.0

    mean_ehe = np.mean(list(ehe_by_year.values())) if ehe_by_year else 0.0

    # Aggregate EHE: from entire distribution (not per-year average)
    all_skills = df[skill_col].dropna().astype(str).str.lower()
    all_counts = all_skills.value_counts()
    all_probs = all_counts / all_counts.sum()
    H_agg = -(all_probs * np.log2(all_probs)).sum()
    agg_ehe = round(float(H_agg / np.log2(k)), 4) if k > 1 else 0.0

    return {
        "ehe_mean": round(float(mean_ehe), 4),
        "ehe_aggregate": agg_ehe,
        "ehe_by_year": ehe_by_year,
        "ehe_min": round(float(min(ehe_by_year.values())), 4) if ehe_by_year else 0.0,
        "ehe_max": round(float(max(ehe_by_year.values())), 4) if ehe_by_year else 0.0,
    }


# =============================================================================
# Main IBR Computation
# =============================================================================

def compute_ibr_metrics(
    results_dir: Path,
    use_proposed: bool = True,
) -> Dict:
    """
    Compute IBR metrics from a results directory.

    Args:
        results_dir: Path to experiment results directory (contains simulation_log.csv
                     and optionally governance_audit.csv).
        use_proposed: If True, evaluate proposed_skill (pre-governance IBR).
                      If False, evaluate final_skill (post-governance effective IBR).

    Returns dict with ibr_physical, ibr_coherence, ibr_temporal, cacr_irrigation,
    ehe_mean, n_decisions, and breakdown counts.
    """
    df = load_run_data(results_dir)

    if len(df) == 0:
        return {
            "ibr_physical": 0.0, "ibr_coherence": 0.0, "ibr_temporal": 0.0,
            "cacr_irrigation": 1.0, "ehe_mean": 0.0, "n_decisions": 0,
        }

    skill_col = "proposed_skill" if use_proposed else "final_skill"

    # Rule Set A: Physical violations
    df["physical_violation"] = df.apply(
        lambda r: is_physical_violation(r, skill_col=skill_col), axis=1
    )
    n_physical = int(df["physical_violation"].sum())
    ibr_physical = n_physical / len(df)

    # Rule Set B: Coherence
    df["coherent"] = df.apply(
        lambda r: is_coherent_skill(r, skill_col=skill_col), axis=1
    )
    n_coherent = int(df["coherent"].sum())
    ibr_coherence = 1 - (n_coherent / len(df))
    cacr_irrigation = n_coherent / len(df)

    # Rule Set C: Temporal violations
    n_temporal, n_temporal_applicable = compute_temporal_violations(df, skill_col=skill_col)
    ibr_temporal = n_temporal / n_temporal_applicable if n_temporal_applicable > 0 else 0.0

    # EHE
    ehe = compute_ehe(df, skill_col="yearly_decision")  # Always on final (effective) decisions

    # Quadrant breakdown
    quadrant_counts = defaultdict(lambda: {"total": 0, "coherent": 0})
    for _, row in df.iterrows():
        wsa = row["WSA"]
        aca = row["ACA"]
        wsa_q = "high" if wsa in ("H", "VH") else "low"
        aca_q = "high" if aca in ("H", "VH") else "low"
        q_key = f"WSA_{wsa_q}_ACA_{aca_q}"
        quadrant_counts[q_key]["total"] += 1
        if row["coherent"]:
            quadrant_counts[q_key]["coherent"] += 1

    quadrant_cacr = {
        k: round(v["coherent"] / v["total"], 4) if v["total"] > 0 else 0.0
        for k, v in quadrant_counts.items()
    }

    # Governance intervention rate (governed runs only)
    gov_rate = None
    gov_warning_rate = None
    gov_block_rate = None
    if "status" in df.columns and not df["status"].isna().all():
        n_rejected = (df["status"] == "REJECTED").sum()
        n_fallback = (df["status"] == "REJECTED_FALLBACK").sum()
        gov_rate = round((n_rejected + n_fallback) / len(df), 4)
        gov_warning_rate = round(n_rejected / len(df), 4)
        gov_block_rate = round(n_fallback / len(df), 4)

    # Skill distribution
    skill_dist = df["yearly_decision"].value_counts().to_dict()

    return {
        "ibr_physical": round(ibr_physical, 4),
        "ibr_coherence": round(ibr_coherence, 4),
        "ibr_temporal": round(ibr_temporal, 4),
        "cacr_irrigation": round(cacr_irrigation, 4),
        "ehe_mean": ehe["ehe_mean"],
        "ehe_by_year": ehe["ehe_by_year"],
        "n_decisions": len(df),
        "n_physical_violations": n_physical,
        "n_coherence_violations": int(len(df) - n_coherent),
        "n_temporal_violations": int(n_temporal),
        "quadrant_cacr": quadrant_cacr,
        "governance_intervention_rate": gov_rate,
        "governance_warning_rate": gov_warning_rate,
        "governance_block_rate": gov_block_rate,
        "skill_distribution": skill_dist,
        "skill_col_used": skill_col,
    }


# =============================================================================
# Comparison Report
# =============================================================================

def generate_comparison_report(
    governed_metrics: Dict,
    ungoverned_metrics: Dict,
) -> str:
    """Generate formatted comparison table."""
    report = []
    report.append("\n" + "=" * 80)
    report.append("IBR Comparison Report: Irrigation ABM")
    report.append("=" * 80)

    report.append(f"\n{'Metric':<30} {'Ungoverned':<15} {'Governed':<15} {'Delta':<15}")
    report.append("-" * 75)

    metrics_to_compare = [
        ("CACR (Coherence Rate)", "cacr_irrigation", True),
        ("IBR Physical", "ibr_physical", False),
        ("IBR Coherence", "ibr_coherence", False),
        ("IBR Temporal", "ibr_temporal", False),
        ("EHE (Mean Entropy)", "ehe_mean", True),
        ("Total Decisions", "n_decisions", None),
    ]

    for label, key, higher_better in metrics_to_compare:
        ug = ungoverned_metrics.get(key, 0)
        gv = governed_metrics.get(key, 0)
        if isinstance(ug, (int, float)) and isinstance(gv, (int, float)):
            delta = gv - ug
            report.append(f"{label:<30} {ug:<15.4f} {gv:<15.4f} {delta:+.4f}")
        else:
            report.append(f"{label:<30} {ug:<15} {gv:<15}")

    # Governance value decomposition
    report.append("\n" + "-" * 75)
    report.append("Governance Value-Add:")
    gov_value = governed_metrics["cacr_irrigation"] - ungoverned_metrics["cacr_irrigation"]
    report.append(f"  CACR improvement: {gov_value:+.4f}  (Governed - Ungoverned)")

    if governed_metrics.get("governance_intervention_rate") is not None:
        report.append(f"  Intervention rate: {governed_metrics['governance_intervention_rate']:.4f}")

    # Quadrant breakdown
    for condition, metrics in [("Governed", governed_metrics), ("Ungoverned", ungoverned_metrics)]:
        report.append(f"\nQuadrant CACR ({condition}):")
        for q, cacr in sorted(metrics.get("quadrant_cacr", {}).items()):
            report.append(f"  {q:<25} {cacr:.4f}")

    report.append("\n" + "=" * 80)
    return "\n".join(report)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Compute IBR metrics for irrigation ABM experiment"
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        required=True,
        help="Path to results directory (contains simulation_log.csv + audit CSV)",
    )
    parser.add_argument(
        "--use-final",
        action="store_true",
        help="Evaluate final_skill (post-governance) instead of proposed_skill",
    )
    parser.add_argument(
        "--compare-ungoverned",
        type=str,
        default=None,
        help="Path to ungoverned results directory for comparison",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file for metrics",
    )

    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}")
        sys.exit(1)

    use_proposed = not args.use_final
    label = "proposed_skill (pre-governance)" if use_proposed else "final_skill (post-governance)"
    print(f"Computing IBR metrics for: {results_dir.name}")
    print(f"  Evaluating: {label}")

    metrics = compute_ibr_metrics(results_dir, use_proposed=use_proposed)

    # Print single-run report
    print("\n" + "=" * 80)
    print("IBR Metrics Report")
    print("=" * 80)
    print(f"Total Decisions:         {metrics['n_decisions']}")
    print(f"CACR (Coherence Rate):   {metrics['cacr_irrigation']:.4f}")
    print(f"IBR Physical:            {metrics['ibr_physical']:.4f}  ({metrics['n_physical_violations']} violations)")
    print(f"IBR Coherence:           {metrics['ibr_coherence']:.4f}  ({metrics['n_coherence_violations']} violations)")
    print(f"IBR Temporal:            {metrics['ibr_temporal']:.4f}  ({metrics['n_temporal_violations']} violations)")
    print(f"EHE (Mean Entropy):      {metrics['ehe_mean']:.4f}")
    if metrics.get("governance_intervention_rate") is not None:
        print(f"Governance Intervention:  {metrics['governance_intervention_rate']:.4f}  "
              f"(warning={metrics['governance_warning_rate']:.4f}, "
              f"block={metrics['governance_block_rate']:.4f})")
    print(f"\nSkill Distribution:")
    for skill, count in sorted(metrics.get("skill_distribution", {}).items()):
        print(f"  {skill:<20} {count}")
    print(f"\nQuadrant Breakdown:")
    for q, cacr in sorted(metrics.get("quadrant_cacr", {}).items()):
        print(f"  {q:<25} {cacr:.4f}")
    print("=" * 80 + "\n")

    # Comparison mode
    if args.compare_ungoverned:
        ungov_dir = Path(args.compare_ungoverned)
        if ungov_dir.exists():
            print(f"Computing ungoverned metrics for: {ungov_dir.name}")
            ungov_metrics = compute_ibr_metrics(ungov_dir, use_proposed=True)
            report = generate_comparison_report(metrics, ungov_metrics)
            print(report)

    # Save to JSON
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Convert ehe_by_year keys to strings for JSON
        save_metrics = dict(metrics)
        if "ehe_by_year" in save_metrics:
            save_metrics["ehe_by_year"] = {
                str(k): v for k, v in save_metrics["ehe_by_year"].items()
            }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(save_metrics, f, indent=2)
        print(f"Metrics saved to: {output_path}")


if __name__ == "__main__":
    main()
