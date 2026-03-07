"""
Mead Paradox Analysis: Governed vs Ungoverned Irrigation Agents
==============================================================
Nature Water paper — quantifying the "governance lowers Mead" adaptive paradox.

Key insight: drought_index is ENDOGENOUS to Mead level. Governed agents extract
more water → lower Mead → higher drought_index signal → triggers curtailment.
Ungoverned agents hover near full reservoir (Mead ~1200ft) → drought_index near 0
→ no feedback signal → rigid extraction patterns.

Usage: python mead_paradox_analysis.py
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE = str(REPO_ROOT / 'examples' / 'irrigation_abm' / 'results')

FILES = {
    'gov': [
        ('seed42', 'production_v20_42yr_seed42/simulation_log.csv'),
        ('seed43', 'production_v20_42yr_seed43/simulation_log.csv'),
        ('seed44', 'production_v20_42yr_seed44/simulation_log.csv'),
    ],
    'ung': [
        ('seed42', 'ungoverned_v20_42yr_seed42/simulation_log.csv'),
        ('seed43', 'ungoverned_v20_42yr_seed43/simulation_log.csv'),
        ('seed44', 'ungoverned_v20_42yr_seed44/simulation_log.csv'),
    ],
}

OUTPUT_DIR = str(REPO_ROOT / 'paper' / 'nature_water' / 'drafts')
INSERT_PATH = os.path.join(OUTPUT_DIR, 'mead_paradox_insert.md')

# ---------------------------------------------------------------------------
# Helper: load and aggregate to yearly level
# ---------------------------------------------------------------------------

def load_yearly(path: str) -> pd.DataFrame:
    """Load simulation_log.csv and return year-level aggregated DataFrame."""
    df = pd.read_csv(path, encoding='utf-8')

    # Year-level environmental variables (same for all agents in a year)
    env = df.groupby('year').agg(
        drought_index=('drought_index', 'first'),
        lake_mead_level=('lake_mead_level', 'first'),
        shortage_tier=('shortage_tier', 'first'),
    ).reset_index()

    # Year-level aggregate demand ratio: sum(diversion) / sum(water_right)
    demand = df.groupby('year').agg(
        total_diversion=('diversion', 'sum'),
        total_water_right=('water_right', 'sum'),
    ).reset_index()
    demand['demand_ratio'] = demand['total_diversion'] / demand['total_water_right']

    yearly = env.merge(demand, on='year')
    return yearly


print("=" * 70)
print("MEAD PARADOX ANALYSIS — Governed vs Ungoverned Irrigation Agents")
print("=" * 70)

# Load all 6 seeds
data = {}
for cond in ('gov', 'ung'):
    for seed, rel_path in FILES[cond]:
        key = f'{cond}_{seed}'
        full_path = os.path.join(BASE, rel_path)
        data[key] = load_yearly(full_path)
        print(f"Loaded: {key}  (years {data[key]['year'].min()}–{data[key]['year'].max()}, "
              f"n={len(data[key])} year-rows)")

print()

# ---------------------------------------------------------------------------
# METRIC 1: Critical threshold crossing frequency
# Thresholds: 1075 ft (shortage trigger) and 1050 ft (severe shortage)
# ---------------------------------------------------------------------------

print("=" * 70)
print("METRIC 1: Critical Threshold Crossing Frequency")
print("  Mead < 1075 ft = shortage trigger | Mead < 1050 ft = severe shortage")
print("=" * 70)

THRESH_SHORTAGE = 1075.0   # ft  (Tier 1 shortage declaration threshold)
THRESH_SEVERE   = 1050.0   # ft  (Tier 2/3 threshold approximation)

results_thresh = {}
for cond in ('gov', 'ung'):
    below_1075, below_1050 = [], []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        yr = data[key]
        below_1075.append((yr['lake_mead_level'] < THRESH_SHORTAGE).sum())
        below_1050.append((yr['lake_mead_level'] < THRESH_SEVERE).sum())
    results_thresh[cond] = {
        'below_1075_per_seed': below_1075,
        'below_1050_per_seed': below_1050,
        'mean_below_1075': np.mean(below_1075),
        'std_below_1075':  np.std(below_1075, ddof=1),
        'mean_below_1050': np.mean(below_1050),
        'std_below_1050':  np.std(below_1050, ddof=1),
    }

for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    r = results_thresh[cond]
    print(f"\n  {label}:")
    print(f"    Years below 1,075 ft per seed: {r['below_1075_per_seed']}")
    print(f"    Mean ± SD: {r['mean_below_1075']:.1f} ± {r['std_below_1075']:.1f} years / 42")
    print(f"    Years below 1,050 ft per seed: {r['below_1050_per_seed']}")
    print(f"    Mean ± SD: {r['mean_below_1050']:.1f} ± {r['std_below_1050']:.1f} years / 42")

print()
print("  INTERPRETATION: Governed agents draw Mead lower (higher crossing frequency),")
print("  but this is evidence of ENGAGEMENT — they extract productively, then curtail.")
print("  Ungoverned agents maintain Mead near capacity but extract far LESS water total.")

# ---------------------------------------------------------------------------
# METRIC 2: Drought-year curtailment
# NOTE: drought_index is ENDOGENOUS — it rises precisely because governed agents
# lower Mead. Use shortage_tier >= 1 as the drought/stress classification since
# that is the causal mechanism (Mead level triggers shortage tier).
#
# Also report drought_index >= 0.4 (top quartile of observed range) as secondary
# threshold, since original 0.7 threshold is above observed maximum (0.625).
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("METRIC 2: Drought-Year Curtailment")
print("  Primary: years with shortage_tier >= 1 (Mead-triggered stress)")
print("  Secondary: years with drought_index >= 0.40 (top ~15% of observed range)")
print("  NOTE: Original 0.7 threshold exceeds observed maximum (max=0.625).")
print("  drought_index IS endogenous — governed agents lower Mead → higher DI.")
print("=" * 70)

# Shortage-tier classification (tier >= 1 = shortage)
print("\n  [A] Shortage-tier stress years (shortage_tier >= 1):")
for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    ratios = []
    n_stress_years = []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        yr = data[key]
        stress = yr[yr['shortage_tier'] >= 1]
        n_stress_years.append(len(stress))
        if len(stress) > 0:
            ratios.append(stress['demand_ratio'].mean())
        else:
            ratios.append(np.nan)
    print(f"\n    {label}:")
    print(f"      Stress years per seed:  {n_stress_years}  (mean {np.mean(n_stress_years):.1f})")
    print(f"      Mean demand_ratio in stress years: {[f'{r:.4f}' for r in ratios]}")
    print(f"      Across-seed mean ± SD: {np.nanmean(ratios):.4f} ± {np.nanstd(ratios, ddof=1):.4f}")

# DI >= 0.40 threshold
print("\n  [B] High drought_index years (drought_index >= 0.40):")
for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    ratios = []
    n_drought_years = []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        yr = data[key]
        drought = yr[yr['drought_index'] >= 0.40]
        n_drought_years.append(len(drought))
        if len(drought) > 0:
            ratios.append(drought['demand_ratio'].mean())
        else:
            ratios.append(np.nan)
    print(f"\n    {label}:")
    print(f"      High-DI years per seed: {n_drought_years}  (mean {np.mean(n_drought_years):.1f})")
    print(f"      Mean demand_ratio: {[f'{r:.4f}' for r in ratios]}")
    print(f"      Across-seed mean ± SD: {np.nanmean(ratios):.4f} ± {np.nanstd(ratios, ddof=1):.4f}")

# ---------------------------------------------------------------------------
# METRIC 3: Wet-year extraction
# Use shortage_tier == 0 (no shortage, plentiful water) AND drought_index < 0.15
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("METRIC 3: Wet-Year / Plentiful-Year Extraction")
print("  Primary: years with shortage_tier == 0 AND drought_index < 0.15")
print("  Secondary: years with drought_index < 0.15 (low stress)")
print("=" * 70)

print("\n  [A] No-shortage AND low-DI years (tier=0, DI<0.15):")
for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    ratios = []
    n_wet = []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        yr = data[key]
        wet = yr[(yr['shortage_tier'] == 0) & (yr['drought_index'] < 0.15)]
        n_wet.append(len(wet))
        if len(wet) > 0:
            ratios.append(wet['demand_ratio'].mean())
        else:
            ratios.append(np.nan)
    print(f"\n    {label}:")
    print(f"      Wet years per seed:   {n_wet}  (mean {np.mean(n_wet):.1f})")
    print(f"      Mean demand_ratio: {[f'{r:.4f}' for r in ratios]}")
    print(f"      Across-seed mean ± SD: {np.nanmean(ratios):.4f} ± {np.nanstd(ratios, ddof=1):.4f}")

print("\n  [B] Low-DI years only (drought_index < 0.15):")
for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    ratios = []
    n_wet = []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        yr = data[key]
        wet = yr[yr['drought_index'] < 0.15]
        n_wet.append(len(wet))
        if len(wet) > 0:
            ratios.append(wet['demand_ratio'].mean())
        else:
            ratios.append(np.nan)
    print(f"\n    {label}:")
    print(f"      Low-DI years per seed: {n_wet}  (mean {np.mean(n_wet):.1f})")
    print(f"      Mean demand_ratio: {[f'{r:.4f}' for r in ratios]}")
    print(f"      Across-seed mean ± SD: {np.nanmean(ratios):.4f} ± {np.nanstd(ratios, ddof=1):.4f}")

# ---------------------------------------------------------------------------
# METRIC 4: Year-over-year demand variability
# Std dev of year-to-year changes in aggregate demand ratio
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("METRIC 4: Year-Over-Year Demand Variability")
print("  Std dev of Δ(demand_ratio) between consecutive years")
print("  Higher = more adaptive / responsive to conditions")
print("=" * 70)

for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    stdevs = []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        yr = data[key].sort_values('year')
        delta = yr['demand_ratio'].diff().dropna()
        stdevs.append(delta.std())
        print(f"    {label} {seed}: SD(Δdemand_ratio) = {delta.std():.5f}, "
              f"mean_abs_change = {delta.abs().mean():.5f}")
    print(f"  {label} across-seed mean ± SD: "
          f"{np.mean(stdevs):.5f} ± {np.std(stdevs, ddof=1):.5f}\n")

# ---------------------------------------------------------------------------
# METRIC 5: Historical anchoring
# CRSS empirical range ~0.80–1.00; our runs start at ~0.30
# Report pooled demand ratios and contextualize
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("METRIC 5: Historical Anchoring — Demand Ratio Context")
print("=" * 70)

CRSS_LOW  = 0.80
CRSS_HIGH = 1.00
GOV_REPORTED  = 0.394
UNGOV_REPORTED = 0.288

print(f"\n  CRSS historical range (empirical): {CRSS_LOW}–{CRSS_HIGH} of water rights")
print(f"  Governed LLM-ABM (mean, 3 seeds):  {GOV_REPORTED:.3f}")
print(f"  Ungoverned LLM-ABM (mean, 3 seeds): {UNGOV_REPORTED:.3f}")

# Compute actual from data to verify
for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    overall_ratios = []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        yr = data[key]
        overall_ratios.append(yr['demand_ratio'].mean())
    print(f"\n  {label} seed-level mean demand_ratios: {[f'{r:.4f}' for r in overall_ratios]}")
    print(f"  {label} cross-seed mean: {np.mean(overall_ratios):.4f} ± {np.std(overall_ratios, ddof=1):.4f}")

print(f"\n  Governed/CRSS_low ratio:   {GOV_REPORTED/CRSS_LOW:.3f}x (governed = {GOV_REPORTED/CRSS_LOW*100:.1f}% of CRSS low bound)")
print(f"  Ungov/CRSS_low ratio:      {UNGOV_REPORTED/CRSS_LOW:.3f}x")
print(f"\n  NOTE: Simulation initializes agents at ~0.30 utilization to allow bidirectional")
print(f"  decision-making. 42-year mean reflects equilibrating dynamics, not sustained")
print(f"  steady-state. Governed agents ramp toward CRSS range; ungoverned plateau below.")

# Mean Mead level
print("\n  Mean lake_mead_level by condition:")
for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    meads = []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        yr = data[key]
        meads.append(yr['lake_mead_level'].mean())
    print(f"    {label}: {[f'{m:.1f}' for m in meads]}  mean={np.mean(meads):.1f} ± {np.std(meads, ddof=1):.1f} ft")

# ---------------------------------------------------------------------------
# METRIC 6: Recovery behavior — demand ratio trajectory years 5–15
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("METRIC 6: Post-Drought Recovery Trajectory (Years 5–15)")
print("  Early drought: years 1–3 (highest shortage tier, Mead > 1000-1053 ft)")
print("  Recovery window: years 5–15")
print("=" * 70)

print("\n  Year-by-year demand_ratio for years 1–20 (mean across 3 seeds):\n")
print(f"  {'Year':>4}  {'Gov DI':>8}  {'Gov DR':>8}  {'Gov Mead':>10}  "
      f"{'Ung DI':>8}  {'Ung DR':>8}  {'Ung Mead':>10}  {'DeltaDR':>8}")
print(f"  {'-'*4}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*8}")

for yr_num in range(1, 21):
    gov_di, gov_dr, gov_mead = [], [], []
    ung_di, ung_dr, ung_mead = [], [], []
    for seed, _ in FILES['gov']:
        row = data[f'gov_{seed}'][data[f'gov_{seed}']['year'] == yr_num]
        if len(row):
            gov_di.append(row['drought_index'].values[0])
            gov_dr.append(row['demand_ratio'].values[0])
            gov_mead.append(row['lake_mead_level'].values[0])
    for seed, _ in FILES['ung']:
        row = data[f'ung_{seed}'][data[f'ung_{seed}']['year'] == yr_num]
        if len(row):
            ung_di.append(row['drought_index'].values[0])
            ung_dr.append(row['demand_ratio'].values[0])
            ung_mead.append(row['lake_mead_level'].values[0])

    g_di = np.mean(gov_di); g_dr = np.mean(gov_dr); g_m = np.mean(gov_mead)
    u_di = np.mean(ung_di); u_dr = np.mean(ung_dr); u_m = np.mean(ung_mead)
    delta = g_dr - u_dr
    print(f"  {yr_num:>4}  {g_di:>8.3f}  {g_dr:>8.4f}  {g_m:>10.1f}  "
          f"{u_di:>8.3f}  {u_dr:>8.4f}  {u_m:>10.1f}  {delta:>+8.4f}")

# Compute recovery slope (linear regression of demand_ratio over years 5–15)
print("\n  Linear recovery slope (demand_ratio vs year, years 5–15):")
for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    slopes = []
    for seed, _ in FILES[cond]:
        key = f'{cond}_{seed}'
        window = data[key][(data[key]['year'] >= 5) & (data[key]['year'] <= 15)]
        if len(window) > 1:
            slope = np.polyfit(window['year'], window['demand_ratio'], 1)[0]
            slopes.append(slope)
    print(f"    {label}: slopes per seed = {[f'{s:+.5f}' for s in slopes]}")
    print(f"    {label}: mean slope = {np.mean(slopes):+.5f} ± {np.std(slopes, ddof=1):.5f} per year")

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

print()
print("=" * 70)
print("SUMMARY TABLE")
print("=" * 70)

# Gather cross-seed aggregates for summary
def get_cross_seed_dr(cond):
    vals = []
    for seed, _ in FILES[cond]:
        vals.append(data[f'{cond}_{seed}']['demand_ratio'].mean())
    return np.mean(vals), np.std(vals, ddof=1)

def get_cross_seed_mead(cond):
    vals = []
    for seed, _ in FILES[cond]:
        vals.append(data[f'{cond}_{seed}']['lake_mead_level'].mean())
    return np.mean(vals), np.std(vals, ddof=1)

def get_cross_seed_thresh(cond, thresh):
    vals = []
    for seed, _ in FILES[cond]:
        vals.append((data[f'{cond}_{seed}']['lake_mead_level'] < thresh).sum())
    return np.mean(vals), np.std(vals, ddof=1)

def get_cross_seed_dr_conditional(cond, mask_fn):
    vals = []
    for seed, _ in FILES[cond]:
        yr = data[f'{cond}_{seed}']
        subset = yr[mask_fn(yr)]
        if len(subset) > 0:
            vals.append(subset['demand_ratio'].mean())
    return (np.nanmean(vals), np.nanstd(vals, ddof=1)) if vals else (np.nan, np.nan)

def get_cross_seed_variability(cond):
    vals = []
    for seed, _ in FILES[cond]:
        yr = data[f'{cond}_{seed}'].sort_values('year')
        delta = yr['demand_ratio'].diff().dropna()
        vals.append(delta.std())
    return np.mean(vals), np.std(vals, ddof=1)

print(f"\n  {'Metric':<45} {'Governed':>15} {'Ungoverned':>15}")
print(f"  {'-'*45} {'-'*15} {'-'*15}")

g_dr_m, g_dr_s = get_cross_seed_dr('gov')
u_dr_m, u_dr_s = get_cross_seed_dr('ung')
print(f"  {'Mean demand ratio (42yr avg)':<45} {g_dr_m:.3f}±{g_dr_s:.3f}     {u_dr_m:.3f}±{u_dr_s:.3f}")

g_me_m, g_me_s = get_cross_seed_mead('gov')
u_me_m, u_me_s = get_cross_seed_mead('ung')
print(f"  {'Mean Mead level (ft)':<45} {g_me_m:.0f}±{g_me_s:.0f}       {u_me_m:.0f}±{u_me_s:.0f}")

g_t1_m, g_t1_s = get_cross_seed_thresh('gov', THRESH_SHORTAGE)
u_t1_m, u_t1_s = get_cross_seed_thresh('ung', THRESH_SHORTAGE)
print(f"  {'Years Mead < 1075 ft (of 42)':<45} {g_t1_m:.1f}±{g_t1_s:.1f}        {u_t1_m:.1f}±{u_t1_s:.1f}")

g_t2_m, g_t2_s = get_cross_seed_thresh('gov', THRESH_SEVERE)
u_t2_m, u_t2_s = get_cross_seed_thresh('ung', THRESH_SEVERE)
print(f"  {'Years Mead < 1050 ft (of 42)':<45} {g_t2_m:.1f}±{g_t2_s:.1f}        {u_t2_m:.1f}±{u_t2_s:.1f}")

g_str_m, g_str_s = get_cross_seed_dr_conditional('gov', lambda y: y['shortage_tier'] >= 1)
u_str_m, u_str_s = get_cross_seed_dr_conditional('ung', lambda y: y['shortage_tier'] >= 1)
print(f"  {'Mean DR in shortage years (tier>=1)':<45} {g_str_m:.4f}±{g_str_s:.4f}  {u_str_m:.4f}±{u_str_s:.4f}")

g_wet_m, g_wet_s = get_cross_seed_dr_conditional('gov', lambda y: (y['shortage_tier']==0) & (y['drought_index']<0.15))
u_wet_m, u_wet_s = get_cross_seed_dr_conditional('ung', lambda y: (y['shortage_tier']==0) & (y['drought_index']<0.15))
print(f"  {'Mean DR in plentiful years (tier=0, DI<0.15)':<45} {g_wet_m:.4f}±{g_wet_s:.4f}  {u_wet_m:.4f}±{u_wet_s:.4f}")

g_var_m, g_var_s = get_cross_seed_variability('gov')
u_var_m, u_var_s = get_cross_seed_variability('ung')
print(f"  {'YoY demand variability (SD of delta DR)':<45} {g_var_m:.5f}±{g_var_s:.5f} {u_var_m:.5f}±{u_var_s:.5f}")

# Drought-responsiveness correlation: demand_ratio ~ drought_index
print("\n  Drought-responsiveness correlation r(demand_ratio, drought_index):")
for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    cors = []
    for seed, _ in FILES[cond]:
        yr = data[f'{cond}_{seed}']
        r = yr['demand_ratio'].corr(yr['drought_index'])
        cors.append(r)
        print(f"    {label} {seed}: r = {r:.4f}")
    print(f"    {label} mean r = {np.mean(cors):.4f} ± {np.std(cors, ddof=1):.4f}\n")

# ---------------------------------------------------------------------------
# Curtailment: does governed reduce DR more in high-stress vs. plentiful?
# ---------------------------------------------------------------------------

print("=" * 70)
print("SUPPLEMENTARY: Drought-to-Plentiful Curtailment Spread")
print("  DR(plentiful) - DR(drought) = curtailment depth")
print("=" * 70)
print()

for cond, label in [('gov', 'GOVERNED'), ('ung', 'UNGOVERNED')]:
    spreads = []
    for seed, _ in FILES[cond]:
        yr = data[f'{cond}_{seed}']
        wet = yr[(yr['shortage_tier'] == 0) & (yr['drought_index'] < 0.15)]
        dry = yr[yr['shortage_tier'] >= 1]
        if len(wet) > 0 and len(dry) > 0:
            spread = wet['demand_ratio'].mean() - dry['demand_ratio'].mean()
            spreads.append(spread)
            print(f"  {label} {seed}: plentiful={wet['demand_ratio'].mean():.4f}, "
                  f"drought={dry['demand_ratio'].mean():.4f}, spread={spread:+.4f}")
    if spreads:
        print(f"  {label}: mean spread = {np.mean(spreads):+.4f} ± {np.std(spreads, ddof=1):.4f}\n")

print()
print("=" * 70)
print("Analysis complete.")
print("=" * 70)
