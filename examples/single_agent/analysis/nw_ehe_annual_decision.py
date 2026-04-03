#!/usr/bin/env python3
"""
Nature Water: Recompute EHE from ANNUAL DECISIONS (not cumulative state).

Ungoverned (Group_A): uses `raw_llm_decision` column (actual LLM choice per year)
Governed (Group_B/C): uses `yearly_decision` column (already annual decision)

This replaces the cumulative-state-based EHE from nw_p0_table1_s4_final.py.
No split_both() needed — "both" doesn't exist as an annual decision.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")

MODELS = {
    "gemma3_4b": "Gemma-3 4B",
    "gemma3_12b": "Gemma-3 12B",
    "gemma3_27b": "Gemma-3 27B",
    "ministral3_3b": "Ministral 3B",
    "ministral3_8b": "Ministral 8B",
    "ministral3_14b": "Ministral 14B",
}
GROUPS = ["Group_A", "Group_B", "Group_C"]
RUNS = ["Run_1", "Run_2", "Run_3"]
K = 4  # {do_nothing, buy_insurance, elevate_house, relocate}

# Map raw_llm_decision text to canonical action names
RAW_LLM_MAP = {
    "Do nothing": "do_nothing",
    "Buy flood insurance": "buy_insurance",
    "Elevate the house": "elevate_house",
    "Relocate": "relocate",
}

# Map governed yearly_decision values
GOVERNED_MAP = {
    "do_nothing": "do_nothing",
    "buy_insurance": "buy_insurance",
    "elevate_house": "elevate_house",
    "relocate": "relocate",
}


def extract_annual_decisions(df, is_ungoverned):
    """Extract annual decisions from CSV, handling format differences."""
    if is_ungoverned:
        # Use raw_llm_decision for ungoverned (Format A)
        if "raw_llm_decision" not in df.columns:
            raise ValueError("Missing raw_llm_decision column in ungoverned data")
        actions = df["raw_llm_decision"].map(
            lambda x: RAW_LLM_MAP.get(str(x).strip(), "unknown") if pd.notna(x) else "relocated"
        )
    else:
        # Use yearly_decision for governed (Format B)
        col = "yearly_decision" if "yearly_decision" in df.columns else "decision"
        if col == "decision":
            # Old format governed — need to use cumulative_state... but governed should have yearly_decision
            raise ValueError(f"Governed run missing yearly_decision column, has: {list(df.columns)}")
        actions = df[col].map(
            lambda x: GOVERNED_MAP.get(str(x).strip(), str(x).strip().lower()) if pd.notna(x) else "relocated"
        )
    return actions


def compute_ehe(actions, k=K):
    """Compute Effective Heterogeneity Entropy from action list."""
    counts = Counter(actions)
    counts.pop("relocated", None)
    counts.pop("unknown", None)
    if not counts:
        return 0.0
    total = sum(counts.values())
    probs = np.array([c / total for c in counts.values()])
    probs = probs[probs > 0]
    H = -np.sum(probs * np.log2(probs))
    H_max = np.log2(k) if k > 1 else 1.0
    return H / H_max


def bootstrap_ci(values, n_boot=10000):
    values = np.array(values)
    n = len(values)
    boot = np.array([np.mean(np.random.choice(values, size=n, replace=True)) for _ in range(n_boot)])
    return np.percentile(boot, [2.5, 97.5])


np.random.seed(42)

# ══════════════════════════════════════════════════════════════════════════
# COMPUTE
# ══════════════════════════════════════════════════════════════════════════

print("=" * 120)
print("EHE FROM ANNUAL DECISIONS (k=4, no split_both)")
print("=" * 120)

results = []

for model_dir, model_name in MODELS.items():
    a_ehe_list, b_ehe_list, c_ehe_list = [], [], []
    a_dist_all, b_dist_all, c_dist_all = Counter(), Counter(), Counter()
    warnings = []

    for run in RUNS:
        # --- Group A (ungoverned) ---
        path_a = BASE / model_dir / "Group_A" / run / "simulation_log.csv"
        if path_a.exists():
            df_a = pd.read_csv(path_a, encoding="utf-8")
            actions_a = extract_annual_decisions(df_a, is_ungoverned=True)
            active_a = actions_a[actions_a != "relocated"]
            a_ehe_list.append(compute_ehe(active_a.tolist()))
            a_dist_all.update(active_a.tolist())
            # Check for unknowns
            n_unknown = (active_a == "unknown").sum()
            if n_unknown > 0:
                warnings.append(f"{model_name} {run} Group_A: {n_unknown} unknown actions")

        # --- Group B (governed) ---
        path_b = BASE / model_dir / "Group_B" / run / "simulation_log.csv"
        if path_b.exists():
            df_b = pd.read_csv(path_b, encoding="utf-8")
            actions_b = extract_annual_decisions(df_b, is_ungoverned=False)
            active_b = actions_b[actions_b != "relocated"]
            b_ehe_list.append(compute_ehe(active_b.tolist()))
            b_dist_all.update(active_b.tolist())

        # --- Group C (governed) ---
        path_c = BASE / model_dir / "Group_C" / run / "simulation_log.csv"
        if path_c.exists():
            df_c = pd.read_csv(path_c, encoding="utf-8")
            actions_c = extract_annual_decisions(df_c, is_ungoverned=False)
            active_c = actions_c[actions_c != "relocated"]
            c_ehe_list.append(compute_ehe(active_c.tolist()))
            c_dist_all.update(active_c.tolist())

    # Compute stats
    a_mean = np.mean(a_ehe_list) if a_ehe_list else 0
    a_sd = np.std(a_ehe_list, ddof=1) if len(a_ehe_list) > 1 else 0
    b_mean = np.mean(b_ehe_list) if b_ehe_list else 0
    b_sd = np.std(b_ehe_list, ddof=1) if len(b_ehe_list) > 1 else 0
    c_mean = np.mean(c_ehe_list) if c_ehe_list else 0
    c_sd = np.std(c_ehe_list, ddof=1) if len(c_ehe_list) > 1 else 0
    best_gov = max(b_mean, c_mean)
    best_gov_sd = b_sd if b_mean >= c_mean else c_sd
    best_group = "B" if b_mean >= c_mean else "C"
    delta = best_gov - a_mean

    results.append({
        "model": model_name,
        "a_ehe": a_mean, "a_sd": a_sd, "a_runs": len(a_ehe_list),
        "b_ehe": b_mean, "b_sd": b_sd, "b_runs": len(b_ehe_list),
        "c_ehe": c_mean, "c_sd": c_sd, "c_runs": len(c_ehe_list),
        "best_gov": best_gov, "best_gov_sd": best_gov_sd, "best_group": best_group,
        "delta": delta,
        "a_dist": dict(a_dist_all), "b_dist": dict(b_dist_all), "c_dist": dict(c_dist_all),
        "a_ehe_list": a_ehe_list, "best_gov_list": [max(b, c) for b, c in zip(b_ehe_list, c_ehe_list)] if b_ehe_list and c_ehe_list else [],
        "warnings": warnings,
    })

# ══════════════════════════════════════════════════════════════════════════
# PRINT RESULTS
# ══════════════════════════════════════════════════════════════════════════

print(f"\n{'Model':>15s} | {'Ungov EHE':>12s} | {'Gov EHE':>12s} | {'Grp':>3s} | {'Delta':>7s} | {'Direction':>10s}")
print("-" * 75)
for r in results:
    direction = "POSITIVE" if r["delta"] > 0.05 else ("NEGATIVE" if r["delta"] < -0.05 else "MARGINAL")
    print(f"{r['model']:>15s} | {r['a_ehe']:.3f} ± {r['a_sd']:.3f} | {r['best_gov']:.3f} ± {r['best_gov_sd']:.3f} | {r['best_group']:>3s} | {r['delta']:+.3f} | {direction:>10s}")

# ══════════════════════════════════════════════════════════════════════════
# ACTION DISTRIBUTIONS
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 120}")
print("ACTION DISTRIBUTIONS (annual decisions, all runs pooled)")
print("=" * 120)

for r in results:
    print(f"\n  {r['model']}:")
    for label, dist in [("Ungov", r["a_dist"]), ("BestGov", r["b_dist"] if r["best_group"] == "B" else r["c_dist"])]:
        total = sum(v for k, v in dist.items() if k not in ["relocated", "unknown"])
        if total > 0:
            pcts = {k: v / total * 100 for k, v in dist.items() if k not in ["relocated", "unknown"]}
            parts = [f"{k}={v:.1f}%" for k, v in sorted(pcts.items())]
            print(f"    {label:>7s}: {', '.join(parts)}  (n={total})")

# ══════════════════════════════════════════════════════════════════════════
# BOOTSTRAP CIs
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 120}")
print("PER-MODEL BOOTSTRAP 95% CIs (best_governed - ungoverned)")
print("=" * 120)

for r in results:
    if len(r["a_ehe_list"]) >= 3 and len(r["best_gov_list"]) >= 3:
        diffs = np.array(r["best_gov_list"]) - np.array(r["a_ehe_list"])
        ci = bootstrap_ci(diffs)
        d = np.mean(diffs) / np.std(diffs, ddof=1) if np.std(diffs, ddof=1) > 0 else float('inf')
        print(f"  {r['model']:>15s}: Δ={np.mean(diffs):+.3f}, CI [{ci[0]:+.3f}, {ci[1]:+.3f}], d={d:.2f}")

# ══════════════════════════════════════════════════════════════════════════
# COMPARISON WITH OLD (cumulative state) VALUES
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 120}")
print("COMPARISON: Annual Decision EHE vs Old Cumulative State EHE")
print("=" * 120)

OLD_VALUES = {
    "Gemma-3 4B":    {"ungov": 0.431, "gov": 0.754, "delta": +0.323},
    "Gemma-3 12B":   {"ungov": 0.632, "gov": 0.424, "delta": -0.209},
    "Gemma-3 27B":   {"ungov": 0.533, "gov": 0.676, "delta": +0.143},
    "Ministral 3B":  {"ungov": 0.787, "gov": 0.692, "delta": -0.095},
    "Ministral 8B":  {"ungov": 0.680, "gov": 0.626, "delta": -0.053},
    "Ministral 14B": {"ungov": 0.665, "gov": 0.700, "delta": +0.035},
}

print(f"\n{'Model':>15s} | {'Old Ungov':>9s} | {'New Ungov':>9s} | {'Old Gov':>9s} | {'New Gov':>9s} | {'Old Δ':>7s} | {'New Δ':>7s} | {'Dir Change?':>12s}")
print("-" * 105)
for r in results:
    old = OLD_VALUES.get(r["model"], {})
    old_dir = "+" if old.get("delta", 0) > 0.05 else ("-" if old.get("delta", 0) < -0.05 else "~")
    new_dir = "+" if r["delta"] > 0.05 else ("-" if r["delta"] < -0.05 else "~")
    changed = "CHANGED" if old_dir != new_dir else "same"
    print(f"{r['model']:>15s} | {old.get('ungov', 0):.3f}     | {r['a_ehe']:.3f}     | {old.get('gov', 0):.3f}     | {r['best_gov']:.3f}     | {old.get('delta', 0):+.3f} | {r['delta']:+.3f} | {changed:>12s}")

# Summary
pos_count = sum(1 for r in results if r["delta"] > 0.05)
neg_count = sum(1 for r in results if r["delta"] < -0.05)
marg_count = len(results) - pos_count - neg_count
print(f"\nSummary: {pos_count}/6 POSITIVE, {marg_count}/6 MARGINAL, {neg_count}/6 NEGATIVE")

# Warnings
all_warnings = [w for r in results for w in r["warnings"]]
if all_warnings:
    print(f"\n⚠ WARNINGS:")
    for w in all_warnings:
        print(f"  {w}")

print("\nDone.")
