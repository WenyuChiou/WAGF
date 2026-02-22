#!/usr/bin/env python3
"""
A1 Ablation Metrics — Demand Ceiling Removal Analysis for Nature Water Paper.

Computes water-system metrics across 3 conditions × 3 seeds:
  1. LLM Governed (production_v20_42yr)
  2. A1 No Ceiling (ablation_no_ceiling)
  3. LLM Ungoverned (ungoverned_v20_42yr)

Verifies against known values: A1 EHE≈0.798, DR≈0.431, shortage≈23.8, r≈0.234
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import math

# ── Paths ──
RESULTS = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\results")

SKILLS = ["increase_large", "increase_small", "maintain_demand", "decrease_small", "decrease_large"]
K = len(SKILLS)  # 5
H_MAX = math.log2(K)  # 2.322 — consistent with paper (k=5 for irrigation)

DIRECTIONS = ["increase", "maintain", "decrease"]
K_DIR = len(DIRECTIONS)
H_MAX_DIR = math.log2(K_DIR)

seeds = [42, 43, 44]


def shannon_entropy(counts_dict):
    total = sum(counts_dict.values())
    if total == 0:
        return 0.0
    probs = np.array([v / total for v in counts_dict.values()])
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))


def ehe_5skill(df):
    """EHE on 5-skill categories — primary metric (paper uses k=5 for irrigation)."""
    counts = Counter(df["yearly_decision"].str.lower().str.strip())
    skill_counts = {s: counts.get(s, 0) for s in SKILLS}
    return shannon_entropy(skill_counts) / H_MAX if H_MAX > 0 else 0.0


def ehe_3dir(counts_dict):
    """EHE on 3 directional categories (increase/maintain/decrease)."""
    return shannon_entropy(counts_dict) / H_MAX_DIR if H_MAX_DIR > 0 else 0.0


def to_direction(skill_name: str) -> str:
    s = skill_name.lower().strip()
    if s.startswith("increase"):
        return "increase"
    elif s.startswith("decrease"):
        return "decrease"
    else:
        return "maintain"


def direction_counts(df):
    directions = df["yearly_decision"].str.lower().str.strip().map(to_direction)
    return Counter(directions)


# ══════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════════════════════
gov_sim = {}
a1_sim = {}
ungov_sim = {}

for s in seeds:
    gov_sim[s] = pd.read_csv(
        RESULTS / f"production_v20_42yr_seed{s}" / "simulation_log.csv",
        encoding="utf-8"
    )
    a1_sim[s] = pd.read_csv(
        RESULTS / f"ablation_no_ceiling_seed{s}" / "simulation_log.csv",
        encoding="utf-8"
    )
    ungov_sim[s] = pd.read_csv(
        RESULTS / f"ungoverned_v20_42yr_seed{s}" / "simulation_log.csv",
        encoding="utf-8"
    )

print(f"Loaded 3 seeds x 3 conditions (Governed, A1 No-Ceiling, Ungoverned)")
for s in seeds:
    print(f"  Seed{s}: gov={len(gov_sim[s])}, a1={len(a1_sim[s])}, ungov={len(ungov_sim[s])} rows")


# ══════════════════════════════════════════════════════════════════════════
# METRIC FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════
def compute_ensemble(sim_dict, metric_fn):
    vals = [metric_fn(sim_dict[s]) for s in seeds]
    return np.mean(vals), np.std(vals, ddof=1), vals


def ehe_fn(df):
    return ehe_5skill(df)


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


# ══════════════════════════════════════════════════════════════════════════
# COMPUTE ALL METRICS
# ══════════════════════════════════════════════════════════════════════════
conditions = [
    ("Full Governance", gov_sim),
    ("A1 No Ceiling", a1_sim),
    ("Ungoverned", ungov_sim),
]

metrics = [
    ("EHE (5-skill)", ehe_fn),
    ("Demand ratio", demand_ratio_fn),
    ("Demand-Mead r", demand_mead_r_fn),
    ("Shortage years (/42)", shortage_fn),
    ("Min Mead (ft)", min_mead_fn),
    ("WSA coherence", wsa_coherence_fn),
]

print("\n" + "=" * 90)
print("A1 ABLATION — THREE-CONDITION COMPARISON")
print("=" * 90)

# Header
print(f"\n  {'Metric':<22s}", end="")
for cond_name, _ in conditions:
    print(f" {cond_name:>20s}", end="")
print()
print(f"  {'─'*22}", end="")
for _ in conditions:
    print(f" {'─'*20}", end="")
print()

# Rows
results = {}
for metric_name, fn in metrics:
    row_vals = []
    print(f"  {metric_name:<22s}", end="")
    for cond_name, sim_dict in conditions:
        mean, sd, raw = compute_ensemble(sim_dict, fn)
        results[(metric_name, cond_name)] = (mean, sd, raw)
        if sd > 0.001:
            print(f" {mean:>12.3f}±{sd:.3f}", end="")
        else:
            print(f" {mean:>20.3f}", end="")
    print()

# ══════════════════════════════════════════════════════════════════════════
# PER-SEED DETAIL
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("PER-SEED DETAIL (A1 No Ceiling)")
print("=" * 90)

for s in seeds:
    df = a1_sim[s]
    e = ehe_fn(df)
    dr = demand_ratio_fn(df)
    r = demand_mead_r_fn(df)
    sh = shortage_fn(df)
    mm = min_mead_fn(df)
    wc = wsa_coherence_fn(df)
    counts = direction_counts(df)
    dist = "  ".join(f"{d}={counts.get(d,0)}" for d in DIRECTIONS)
    print(f"  Seed{s}: EHE={e:.4f} DR={dr:.4f} r={r:.4f} "
          f"shortage={sh:.0f} minMead={mm:.1f} WSA_coh={wc:.4f}  ({dist})")

# ══════════════════════════════════════════════════════════════════════════
# VERIFICATION vs KNOWN VALUES
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("VERIFICATION vs KNOWN VALUES (A1 ensemble)")
print("=" * 90)

a1_ehe_mean = results[("EHE (5-skill)", "A1 No Ceiling")][0]
a1_dr_mean = results[("Demand ratio", "A1 No Ceiling")][0]
a1_sh_mean = results[("Shortage years (/42)", "A1 No Ceiling")][0]
a1_r_mean = results[("Demand-Mead r", "A1 No Ceiling")][0]

checks = [
    ("EHE (5-skill)", a1_ehe_mean, 0.793, 0.02),
    ("Demand ratio", a1_dr_mean, 0.431, 0.03),
    ("Shortage years", a1_sh_mean, 23.8, 3.0),
    ("Demand-Mead r", a1_r_mean, 0.234, 0.10),
]

all_pass = True
for name, actual, expected, tol in checks:
    ok = abs(actual - expected) <= tol
    status = "PASS" if ok else "WARN"
    if not ok:
        all_pass = False
    print(f"  {name:<20s}: actual={actual:.3f}  expected≈{expected:.3f}  tol={tol}  [{status}]")

print(f"\n  Overall: {'ALL PASS' if all_pass else 'CHECK WARNINGS ABOVE'}")

# ══════════════════════════════════════════════════════════════════════════
# TABLE FOR PAPER (Markdown)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("TABLE FOR PAPER (copy-paste ready)")
print("=" * 90)

def fmt(metric_name, cond_name, precision=3):
    mean, sd, _ = results[(metric_name, cond_name)]
    if sd > 0.001:
        return f"{mean:.{precision}f} +/- {sd:.{precision}f}"
    else:
        return f"{mean:.{precision}f}"

print("""
| Metric | Full Governance | No Ceiling (A1) | Ungoverned |
|--------|:-:|:-:|:-:|""")
for mname, _ in metrics:
    p = 1 if "Shortage" in mname or "Mead" in mname else 3
    g = fmt(mname, "Full Governance", p)
    a = fmt(mname, "A1 No Ceiling", p)
    u = fmt(mname, "Ungoverned", p)
    print(f"| {mname} | {g} | {a} | {u} |")

print(f"\nAnalysis complete.")
