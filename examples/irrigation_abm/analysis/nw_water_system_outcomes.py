#!/usr/bin/env python3
"""
Nature Water — Water-System Outcomes Analysis
Phase 2: Governed vs Ungoverned Lake Mead elevation trajectories
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
import json

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\results")
seeds = [42, 43, 44]

# ══════════════════════════════════════════════════════════════════════════
# LOAD ALL DATA
# ══════════════════════════════════════════════════════════════════════════
gov_yearly = {}
ungov_yearly = {}

for s in seeds:
    g = pd.read_csv(BASE / f"production_v20_42yr_seed{s}" / "simulation_log.csv", encoding="utf-8")
    u = pd.read_csv(BASE / f"ungoverned_v20_42yr_seed{s}" / "simulation_log.csv", encoding="utf-8")

    gov_yearly[s] = g.groupby("year").agg(
        mead_ft=("lake_mead_level", "first"),
        storage_maf=("mead_storage_maf", "first"),
        shortage_tier=("shortage_tier", "first"),
        total_request=("request", "sum"),
        total_right=("water_right", "sum"),
        n_agents=("agent_id", "count"),
    ).reset_index()

    ungov_yearly[s] = u.groupby("year").agg(
        mead_ft=("lake_mead_level", "first"),
        storage_maf=("mead_storage_maf", "first"),
        shortage_tier=("shortage_tier", "first"),
        total_request=("request", "sum"),
        total_right=("water_right", "sum"),
        n_agents=("agent_id", "count"),
    ).reset_index()

print(f"Loaded {len(seeds)} seeds × 2 conditions")

# ══════════════════════════════════════════════════════════════════════════
# 1. LAKE MEAD ELEVATION TRAJECTORIES
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("1. LAKE MEAD ELEVATION TRAJECTORIES (governed vs ungoverned)")
print("=" * 80)

print(f"\n  {'Year':>4s}", end="")
for s in seeds:
    print(f"  Gov{s:2d}  Ungov{s:2d}", end="")
print(f"  Gov_mean  Ungov_mean  Delta")

for yr in range(1, 43):
    print(f"  {yr:4d}", end="")
    g_vals = []
    u_vals = []
    for s in seeds:
        g_row = gov_yearly[s][gov_yearly[s]["year"] == yr]
        u_row = ungov_yearly[s][ungov_yearly[s]["year"] == yr]
        g_ft = g_row["mead_ft"].values[0] if len(g_row) > 0 else np.nan
        u_ft = u_row["mead_ft"].values[0] if len(u_row) > 0 else np.nan
        g_vals.append(g_ft)
        u_vals.append(u_ft)
        print(f"  {g_ft:7.1f} {u_ft:7.1f}", end="")
    g_mean = np.nanmean(g_vals)
    u_mean = np.nanmean(u_vals)
    print(f"  {g_mean:8.1f}  {u_mean:10.1f}  {g_mean - u_mean:+7.1f}")

# ══════════════════════════════════════════════════════════════════════════
# 2. SUMMARY STATISTICS
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("2. SUMMARY STATISTICS")
print("=" * 80)

for label, data in [("GOVERNED", gov_yearly), ("UNGOVERNED", ungov_yearly)]:
    all_mead = []
    all_demand_ratio = []
    all_shortage_years = []
    min_mead = []

    for s in seeds:
        df = data[s]
        all_mead.append(df["mead_ft"].values)
        ratio = df["total_request"] / df["total_right"]
        all_demand_ratio.append(ratio.values)
        shortage = (df["shortage_tier"] > 0).sum()
        all_shortage_years.append(shortage)
        min_mead.append(df["mead_ft"].min())

    mead_all = np.concatenate(all_mead)
    dr_all = np.concatenate(all_demand_ratio)

    print(f"\n  {label}:")
    print(f"    Mead elevation: mean={np.mean(mead_all):.1f} ft, min={np.min(mead_all):.1f} ft, max={np.max(mead_all):.1f} ft")
    print(f"    Mead elevation SD (across years): {np.std(mead_all):.1f} ft")
    print(f"    Minimum Mead per seed: {[f'{v:.1f}' for v in min_mead]}")
    print(f"    Demand ratio: mean={np.mean(dr_all):.4f}, SD={np.std(dr_all):.4f}")
    print(f"    Shortage years per seed: {all_shortage_years}")
    print(f"    Below Tier 2 (1050ft) years: ", end="")
    for s in seeds:
        below = (data[s]["mead_ft"] < 1050).sum()
        print(f"seed{s}={below} ", end="")
    print()
    print(f"    Below Tier 3 (1025ft) years: ", end="")
    for s in seeds:
        below = (data[s]["mead_ft"] < 1025).sum()
        print(f"seed{s}={below} ", end="")
    print()

# ══════════════════════════════════════════════════════════════════════════
# 3. DEMAND TRAJECTORY COMPARISON
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("3. DEMAND TRAJECTORIES (total basin demand MAF)")
print("=" * 80)

print(f"\n  {'Year':>4s}  Gov_demand  Ungov_demand  Gov_ratio  Ungov_ratio")
for yr in range(1, 43):
    g_demands = []
    u_demands = []
    g_ratios = []
    u_ratios = []
    for s in seeds:
        g_row = gov_yearly[s][gov_yearly[s]["year"] == yr]
        u_row = ungov_yearly[s][ungov_yearly[s]["year"] == yr]
        if len(g_row) > 0:
            g_demands.append(g_row["total_request"].values[0])
            g_ratios.append(g_row["total_request"].values[0] / g_row["total_right"].values[0])
        if len(u_row) > 0:
            u_demands.append(u_row["total_request"].values[0])
            u_ratios.append(u_row["total_request"].values[0] / u_row["total_right"].values[0])

    print(f"  {yr:4d}  {np.mean(g_demands):10.2f}  {np.mean(u_demands):12.2f}  {np.mean(g_ratios):9.4f}  {np.mean(u_ratios):11.4f}")

# ══════════════════════════════════════════════════════════════════════════
# 4. SHORTAGE TIER DISTRIBUTION
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("4. SHORTAGE TIER DISTRIBUTION")
print("=" * 80)

for label, data in [("GOVERNED", gov_yearly), ("UNGOVERNED", ungov_yearly)]:
    tier_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    total = 0
    for s in seeds:
        for _, row in data[s].iterrows():
            t = int(row["shortage_tier"])
            tier_counts[t] = tier_counts.get(t, 0) + 1
            total += 1
    print(f"\n  {label} (n={total} year-observations across {len(seeds)} seeds):")
    for tier, count in sorted(tier_counts.items()):
        labels = {0: "Normal (≥1100ft)", 1: "Tier 1 (<1075ft)", 2: "Tier 2 (<1050ft)", 3: "Tier 3 (<1025ft)"}
        print(f"    Tier {tier} {labels.get(tier, '')}: {count} years ({100*count/total:.1f}%)")

# ══════════════════════════════════════════════════════════════════════════
# 5. DROUGHT RESPONSE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("5. DROUGHT RESPONSE: Do agents reduce demand when Mead drops?")
print("=" * 80)

for label, data, audit_data_path in [
    ("GOVERNED", gov_yearly, "production_v20_42yr_seed{s}"),
    ("UNGOVERNED", ungov_yearly, "ungoverned_v20_42yr_seed{s}")
]:
    correlations = []
    for s in seeds:
        df = data[s]
        ratio = df["total_request"] / df["total_right"]
        # Correlation between Mead elevation and demand ratio
        corr = np.corrcoef(df["mead_ft"].values, ratio.values)[0, 1]
        correlations.append(corr)
        print(f"  {label} seed{s}: corr(Mead_ft, demand_ratio) = {corr:+.3f}")
    print(f"  {label} mean correlation: {np.mean(correlations):+.3f} ± {np.std(correlations, ddof=1):.3f}")

# ══════════════════════════════════════════════════════════════════════════
# 6. KEY WATER-SYSTEM FINDING
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("6. KEY WATER-SYSTEM FINDING")
print("=" * 80)

# Compare final-year Mead elevation
gov_final = [gov_yearly[s][gov_yearly[s]["year"] == 42]["mead_ft"].values[0] for s in seeds]
ungov_final = [ungov_yearly[s][ungov_yearly[s]["year"] == 42]["mead_ft"].values[0] for s in seeds]

gov_min = [gov_yearly[s]["mead_ft"].min() for s in seeds]
ungov_min = [ungov_yearly[s]["mead_ft"].min() for s in seeds]

print(f"\n  Final year (Y42) Mead elevation:")
print(f"    Governed:   {[f'{v:.1f}' for v in gov_final]}  mean={np.mean(gov_final):.1f} ft")
print(f"    Ungoverned: {[f'{v:.1f}' for v in ungov_final]}  mean={np.mean(ungov_final):.1f} ft")
print(f"    Delta: {np.mean(gov_final) - np.mean(ungov_final):+.1f} ft")

print(f"\n  Minimum Mead elevation (worst year):")
print(f"    Governed:   {[f'{v:.1f}' for v in gov_min]}  mean={np.mean(gov_min):.1f} ft")
print(f"    Ungoverned: {[f'{v:.1f}' for v in ungov_min]}  mean={np.mean(ungov_min):.1f} ft")
print(f"    Delta: {np.mean(gov_min) - np.mean(ungov_min):+.1f} ft")

# Demand ratio summary
gov_dr = [gov_yearly[s]["total_request"].sum() / gov_yearly[s]["total_right"].sum() for s in seeds]
ungov_dr = [ungov_yearly[s]["total_request"].sum() / ungov_yearly[s]["total_right"].sum() for s in seeds]

print(f"\n  42-year cumulative demand ratio:")
print(f"    Governed:   {np.mean(gov_dr):.4f} ± {np.std(gov_dr, ddof=1):.4f}")
print(f"    Ungoverned: {np.mean(ungov_dr):.4f} ± {np.std(ungov_dr, ddof=1):.4f}")
print(f"    Delta: {np.mean(gov_dr) - np.mean(ungov_dr):+.4f}")

# Does ungoverned collapse?
print(f"\n  COMMONS COLLAPSE ASSESSMENT:")
for s in seeds:
    u_df = ungov_yearly[s]
    below_1025 = (u_df["mead_ft"] < 1025).sum()
    below_1050 = (u_df["mead_ft"] < 1050).sum()
    min_ft = u_df["mead_ft"].min()
    print(f"    Ungoverned seed{s}: min={min_ft:.1f}ft, years<1050ft={below_1050}, years<1025ft={below_1025}")

    g_df = gov_yearly[s]
    below_1025 = (g_df["mead_ft"] < 1025).sum()
    below_1050 = (g_df["mead_ft"] < 1050).sum()
    min_ft = g_df["mead_ft"].min()
    print(f"    Governed   seed{s}: min={min_ft:.1f}ft, years<1050ft={below_1050}, years<1025ft={below_1025}")

print(f"\n  INTERPRETATION:")
print(f"  If ungoverned Mead drops significantly lower than governed:")
print(f"  → 'Governance rules encoding physical scarcity signals prevent")
print(f"     collective over-extraction in prior-appropriation water systems'")
print(f"  If similar trajectories:")
print(f"  → Mass balance dominates; demand ratio differences don't translate")
print(f"     to different reservoir outcomes at this scale")

print("\nAnalysis complete.")
