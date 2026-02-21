#!/usr/bin/env python3
"""
FQL Baseline — Comparison Metrics for Nature Water Paper.

Computes: EHE, demand-Mead correlation, demand ratio, shortage years,
skill distribution, and Mead trajectory across 3 conditions:
  1. LLM Governed (production_v20_42yr)
  2. LLM Ungoverned (ungoverned_v20_42yr)
  3. FQL Baseline (fql_raw — no governance, faithful to Hung & Yang 2021)

EHE is computed on 3 directional categories (increase/maintain/decrease)
for fair comparison: LLM has 5 skills, FQL has 2 actions + maintain.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import math

# ── Paths ──
MAIN_RESULTS = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\results")
FQL_RESULTS = Path(r"C:\Users\wenyu\Desktop\Lehigh\wagf-fql-baseline\examples\irrigation_abm\results\fql_raw")

# LLM 5-skill model
LLM_SKILLS = ["increase_large", "increase_small", "maintain_demand", "decrease_small", "decrease_large"]
# FQL 2-action model (+ maintain from cap)
FQL_SKILLS = ["increase_demand", "decrease_demand", "maintain_demand"]
# Fair comparison: 3 directional categories
DIRECTIONS = ["increase", "maintain", "decrease"]
K_DIR = len(DIRECTIONS)  # 3
H_MAX_DIR = math.log2(K_DIR)  # 1.585

seeds = [42, 43, 44]


def shannon_entropy(counts_dict):
    total = sum(counts_dict.values())
    if total == 0:
        return 0.0
    probs = np.array([v / total for v in counts_dict.values()])
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))


def ehe_3dir(counts_dict):
    """EHE on 3 directional categories (increase/maintain/decrease)."""
    return shannon_entropy(counts_dict) / H_MAX_DIR if H_MAX_DIR > 0 else 0.0


def to_direction(skill_name: str) -> str:
    """Map any skill to directional category."""
    s = skill_name.lower().strip()
    if s.startswith("increase"):
        return "increase"
    elif s.startswith("decrease"):
        return "decrease"
    else:
        return "maintain"


def direction_counts(df):
    """Count decisions by direction."""
    directions = df["yearly_decision"].str.lower().str.strip().map(to_direction)
    return Counter(directions)


# ══════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════════════════════
gov_sim = {}
ungov_sim = {}
fql_sim = {}

for s in seeds:
    gov_sim[s] = pd.read_csv(
        MAIN_RESULTS / f"production_v20_42yr_seed{s}" / "simulation_log.csv",
        encoding="utf-8"
    )
    ungov_sim[s] = pd.read_csv(
        MAIN_RESULTS / f"ungoverned_v20_42yr_seed{s}" / "simulation_log.csv",
        encoding="utf-8"
    )
    fql_sim[s] = pd.read_csv(
        FQL_RESULTS / f"seed{s}" / "simulation_log.csv",
        encoding="utf-8"
    )

print(f"Loaded 3 seeds × 3 conditions")
for s in seeds:
    print(f"  Seed{s}: gov={len(gov_sim[s])}, ungov={len(ungov_sim[s])}, fql={len(fql_sim[s])} rows")


# ══════════════════════════════════════════════════════════════════════════
# 1. EHE (3-direction: increase / maintain / decrease)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("1. EHE — 3-direction (increase / maintain / decrease)")
print("=" * 80)

for label, sim_dict in [("LLM Governed", gov_sim), ("LLM Ungoverned", ungov_sim), ("FQL Baseline", fql_sim)]:
    print(f"\n  {label}:")
    seed_ehes = {}
    for s in seeds:
        df = sim_dict[s]
        counts = direction_counts(df)
        e = ehe_3dir(counts)
        seed_ehes[s] = e
        dist_str = "  ".join(f"{d}={counts.get(d, 0)}" for d in DIRECTIONS)
        print(f"    Seed{s}: EHE={e:.4f}  ({dist_str})")

    vals = list(seed_ehes.values())
    print(f"    Ensemble: {np.mean(vals):.4f} ± {np.std(vals, ddof=1):.4f}")


# ══════════════════════════════════════════════════════════════════════════
# 2. DEMAND RATIO (request / water_right)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("2. DEMAND RATIO (mean yearly aggregate request / water_right)")
print("=" * 80)

for label, sim_dict in [("LLM Governed", gov_sim), ("LLM Ungoverned", ungov_sim), ("FQL Baseline", fql_sim)]:
    print(f"\n  {label}:")
    seed_ratios = {}
    for s in seeds:
        df = sim_dict[s]
        yearly = df.groupby("year").agg({"request": "sum", "water_right": "sum"})
        ratio = yearly["request"] / yearly["water_right"]
        seed_ratios[s] = ratio.mean()
        print(f"    Seed{s}: mean={ratio.mean():.4f} (range: {ratio.min():.4f}-{ratio.max():.4f})")

    vals = list(seed_ratios.values())
    print(f"    Ensemble: {np.mean(vals):.4f} ± {np.std(vals, ddof=1):.4f}")


# ══════════════════════════════════════════════════════════════════════════
# 3. DEMAND-MEAD CORRELATION
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("3. DEMAND-MEAD CORRELATION (yearly demand ratio vs Mead elevation)")
print("=" * 80)

for label, sim_dict in [("LLM Governed", gov_sim), ("LLM Ungoverned", ungov_sim), ("FQL Baseline", fql_sim)]:
    print(f"\n  {label}:")
    seed_corrs = {}
    for s in seeds:
        df = sim_dict[s]
        yearly = df.groupby("year").agg({
            "request": "sum",
            "water_right": "sum",
            "lake_mead_level": "first",
        })
        ratio = yearly["request"] / yearly["water_right"]
        mead = yearly["lake_mead_level"]
        corr = np.corrcoef(mead.values, ratio.values)[0, 1]
        seed_corrs[s] = corr
        print(f"    Seed{s}: r={corr:.4f}")

    vals = list(seed_corrs.values())
    print(f"    Ensemble: r={np.mean(vals):.4f} ± {np.std(vals, ddof=1):.4f}")


# ══════════════════════════════════════════════════════════════════════════
# 4. SHORTAGE YEARS & MEAD TRAJECTORIES
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("4. SHORTAGE YEARS & MEAD STATISTICS")
print("=" * 80)

for label, sim_dict in [("LLM Governed", gov_sim), ("LLM Ungoverned", ungov_sim), ("FQL Baseline", fql_sim)]:
    print(f"\n  {label}:")
    all_shortage = []
    all_min_mead = []
    all_final_mead = []
    all_below_1050 = []
    all_below_1025 = []

    for s in seeds:
        df = sim_dict[s]
        yearly = df.groupby("year").agg({
            "shortage_tier": "first",
            "lake_mead_level": "first",
        })
        shortage_yrs = (yearly["shortage_tier"] > 0).sum()
        min_mead = yearly["lake_mead_level"].min()
        final_mead = yearly["lake_mead_level"].iloc[-1]
        below_1050 = (yearly["lake_mead_level"] < 1050).sum()
        below_1025 = (yearly["lake_mead_level"] < 1025).sum()

        all_shortage.append(shortage_yrs)
        all_min_mead.append(min_mead)
        all_final_mead.append(final_mead)
        all_below_1050.append(below_1050)
        all_below_1025.append(below_1025)

        print(f"    Seed{s}: shortage={shortage_yrs}/42yr, min_Mead={min_mead:.1f}ft, "
              f"final_Mead={final_mead:.1f}ft, <1050ft={below_1050}yr, <1025ft={below_1025}yr")

    print(f"    Ensemble: shortage={np.mean(all_shortage):.1f}±{np.std(all_shortage, ddof=1):.1f}, "
          f"min_Mead={np.mean(all_min_mead):.1f}ft, final_Mead={np.mean(all_final_mead):.1f}ft")


# ══════════════════════════════════════════════════════════════════════════
# 5. SKILL DISTRIBUTION COMPARISON
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("5. SKILL DISTRIBUTION (% of total decisions, ensemble mean)")
print("=" * 80)

# 5a. Direction-level (3 categories — comparable across conditions)
print(f"\n  5a. Directional (3-category):")
print(f"  {'Direction':<20s} {'LLM Gov':>10s} {'LLM Ungov':>10s} {'FQL':>10s}")
print(f"  {'─'*20} {'─'*10} {'─'*10} {'─'*10}")

for direction in DIRECTIONS:
    pcts = {}
    for lbl, sim_dict in [("gov", gov_sim), ("ungov", ungov_sim), ("fql", fql_sim)]:
        seed_pcts = []
        for s in seeds:
            df = sim_dict[s]
            total = len(df)
            dirs = df["yearly_decision"].str.lower().str.strip().map(to_direction)
            count = (dirs == direction).sum()
            seed_pcts.append(100 * count / total if total > 0 else 0)
        pcts[lbl] = np.mean(seed_pcts)
    print(f"  {direction:<20s} {pcts['gov']:9.1f}% {pcts['ungov']:9.1f}% {pcts['fql']:9.1f}%")

# 5b. Raw skills for each condition
print(f"\n  5b. LLM raw skills (5-skill model):")
for skill in LLM_SKILLS:
    pcts = {}
    for lbl, sim_dict in [("gov", gov_sim), ("ungov", ungov_sim)]:
        seed_pcts = []
        for s in seeds:
            df = sim_dict[s]
            total = len(df)
            count = (df["yearly_decision"].str.lower().str.strip() == skill).sum()
            seed_pcts.append(100 * count / total if total > 0 else 0)
        pcts[lbl] = np.mean(seed_pcts)
    print(f"  {skill:<20s} gov={pcts['gov']:5.1f}%  ungov={pcts['ungov']:5.1f}%")

print(f"\n  5c. FQL raw skills (2-action model):")
for skill in FQL_SKILLS:
    seed_pcts = []
    for s in seeds:
        df = fql_sim[s]
        total = len(df)
        count = (df["yearly_decision"].str.lower().str.strip() == skill).sum()
        seed_pcts.append(100 * count / total if total > 0 else 0)
    print(f"  {skill:<20s} {np.mean(seed_pcts):5.1f}%")


# ══════════════════════════════════════════════════════════════════════════
# 6. WSA-ACTION COHERENCE (construct alignment)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("6. WSA-ACTION COHERENCE (high drought → should not increase)")
print("=" * 80)

for label, sim_dict in [("LLM Governed", gov_sim), ("LLM Ungoverned", ungov_sim), ("FQL Baseline", fql_sim)]:
    print(f"\n  {label}:")
    seed_coherence = []
    for s in seeds:
        df = sim_dict[s]
        wsa = df["wsa_label"].fillna("").str.strip()
        skill = df["yearly_decision"].str.lower().str.strip()

        # High scarcity = WSA in {H, VH}
        h_mask = wsa.isin(["H", "VH"])
        h_total = h_mask.sum()
        h_increase = (h_mask & skill.str.startswith("increase")).sum()
        coherence = (h_total - h_increase) / h_total if h_total > 0 else 1.0
        seed_coherence.append(coherence)
        print(f"    Seed{s}: WSA=H/VH total={h_total}, increase={h_increase} → coherence={coherence:.4f}")

    vals = seed_coherence
    print(f"    Ensemble: {np.mean(vals):.4f} ± {np.std(vals, ddof=1):.4f}")


# ══════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE (for paper)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SUMMARY TABLE — Three-Condition Comparison for Nature Water")
print("=" * 80)

def compute_ensemble(sim_dict, metric_fn):
    vals = [metric_fn(sim_dict[s]) for s in seeds]
    return np.mean(vals), np.std(vals, ddof=1)

def ehe_fn(df):
    counts = direction_counts(df)
    return ehe_3dir(counts)

def demand_ratio_fn(df):
    yearly = df.groupby("year").agg({"request": "sum", "water_right": "sum"})
    return (yearly["request"] / yearly["water_right"]).mean()

def demand_mead_r_fn(df):
    yearly = df.groupby("year").agg({
        "request": "sum", "water_right": "sum", "lake_mead_level": "first"
    })
    ratio = yearly["request"] / yearly["water_right"]
    return np.corrcoef(yearly["lake_mead_level"].values, ratio.values)[0, 1]

def shortage_fn(df):
    yearly = df.groupby("year").agg({"shortage_tier": "first"})
    return float((yearly["shortage_tier"] > 0).sum())

def min_mead_fn(df):
    yearly = df.groupby("year").agg({"lake_mead_level": "first"})
    return yearly["lake_mead_level"].min()

def wsa_coherence_fn(df):
    wsa = df["wsa_label"].fillna("").str.strip()
    skill = df["yearly_decision"].str.lower().str.strip()
    h_mask = wsa.isin(["H", "VH"])
    h_total = h_mask.sum()
    h_increase = (h_mask & skill.str.startswith("increase")).sum()
    return (h_total - h_increase) / h_total if h_total > 0 else 1.0

metrics = [
    ("EHE (3-dir)", ehe_fn),
    ("Demand ratio", demand_ratio_fn),
    ("Demand-Mead r", demand_mead_r_fn),
    ("Shortage years", shortage_fn),
    ("Min Mead (ft)", min_mead_fn),
    ("WSA coherence", wsa_coherence_fn),
]

print(f"\n  {'Metric':<20s} {'LLM Governed':>18s} {'LLM Ungoverned':>18s} {'FQL Baseline':>18s}")
print(f"  {'─'*20} {'─'*18} {'─'*18} {'─'*18}")

for name, fn in metrics:
    row = []
    for sim_dict in [gov_sim, ungov_sim, fql_sim]:
        mean, sd = compute_ensemble(sim_dict, fn)
        if sd > 0.001:
            row.append(f"{mean:.3f}±{sd:.3f}")
        else:
            row.append(f"{mean:.3f}")
    print(f"  {name:<20s} {row[0]:>18s} {row[1]:>18s} {row[2]:>18s}")

print(f"  {'Reasoning traces':<20s} {'Yes':>18s} {'Yes':>18s} {'No':>18s}")
print(f"  {'Rule ablation':<20s} {'Yes':>18s} {'N/A':>18s} {'No':>18s}")
