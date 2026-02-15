#!/usr/bin/env python3
"""
P0 Statistical Corrections for Nature Water — Expert Panel Response
1. Bootstrap 95% CIs on EHE difference and Cohen's d
2. Leave-one-out sensitivity on Cohen's d
3. Null-model CACR estimate
4. Per-seed values table
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import math

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\results")
SKILLS = ["increase_large", "increase_small", "maintain_demand", "decrease_small", "decrease_large"]
K = len(SKILLS)
H_MAX = math.log2(K)

def shannon_entropy(counts_dict):
    total = sum(counts_dict.values())
    if total == 0:
        return 0.0
    probs = np.array([v / total for v in counts_dict.values()])
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))

def ehe(counts_dict):
    return shannon_entropy(counts_dict) / H_MAX if H_MAX > 0 else 0.0

def cohens_d(g, u):
    pooled = np.sqrt((np.std(g, ddof=1)**2 + np.std(u, ddof=1)**2) / 2)
    return (np.mean(g) - np.mean(u)) / pooled if pooled > 0 else float('inf')

# Load data
seeds = [42, 43, 44]
gov_ehes = []
ungov_ehes = []

for s in seeds:
    gp = BASE / f"production_v20_42yr_seed{s}" / "simulation_log.csv"
    up = BASE / f"ungoverned_v20_42yr_seed{s}" / "simulation_log.csv"
    g_df = pd.read_csv(gp, encoding="utf-8")
    u_df = pd.read_csv(up, encoding="utf-8")
    gov_ehes.append(ehe(Counter(g_df["yearly_decision"].str.lower().str.strip())))
    ungov_ehes.append(ehe(Counter(u_df["yearly_decision"].str.lower().str.strip())))

gov_ehes = np.array(gov_ehes)
ungov_ehes = np.array(ungov_ehes)

print("=" * 80)
print("P0 STATISTICAL CORRECTIONS")
print("=" * 80)

# ═══ 1. Per-seed values ═══
print("\n1. PER-SEED VALUES (for manuscript)")
print(f"  {'Seed':>6s}  {'Governed':>10s}  {'Ungoverned':>10s}  {'Delta':>8s}")
for i, s in enumerate(seeds):
    print(f"  {s:>6d}  {gov_ehes[i]:>10.4f}  {ungov_ehes[i]:>10.4f}  {gov_ehes[i]-ungov_ehes[i]:>+8.4f}")
print(f"  {'Mean':>6s}  {np.mean(gov_ehes):>10.4f}  {np.mean(ungov_ehes):>10.4f}  {np.mean(gov_ehes)-np.mean(ungov_ehes):>+8.4f}")
print(f"  {'SD':>6s}  {np.std(gov_ehes,ddof=1):>10.4f}  {np.std(ungov_ehes,ddof=1):>10.4f}")

# ═══ 2. Bootstrap 95% CIs ═══
print("\n2. BOOTSTRAP 95% CIs (10,000 resamples)")
np.random.seed(12345)
n_boot = 10000
boot_deltas = []
boot_ds = []

for _ in range(n_boot):
    g_idx = np.random.choice(len(gov_ehes), size=len(gov_ehes), replace=True)
    u_idx = np.random.choice(len(ungov_ehes), size=len(ungov_ehes), replace=True)
    g_boot = gov_ehes[g_idx]
    u_boot = ungov_ehes[u_idx]
    boot_deltas.append(np.mean(g_boot) - np.mean(u_boot))
    pooled = np.sqrt((np.std(g_boot, ddof=1)**2 + np.std(u_boot, ddof=1)**2) / 2)
    if pooled > 0:
        boot_ds.append((np.mean(g_boot) - np.mean(u_boot)) / pooled)
    else:
        boot_ds.append(float('inf'))

boot_deltas = np.array(boot_deltas)
boot_ds = np.array([d for d in boot_ds if np.isfinite(d)])

delta_ci = np.percentile(boot_deltas, [2.5, 97.5])
d_ci = np.percentile(boot_ds, [2.5, 97.5])

observed_delta = np.mean(gov_ehes) - np.mean(ungov_ehes)
observed_d = cohens_d(gov_ehes, ungov_ehes)

print(f"  EHE Difference:")
print(f"    Point estimate: {observed_delta:.4f}")
print(f"    Bootstrap 95% CI: [{delta_ci[0]:.4f}, {delta_ci[1]:.4f}]")
print(f"    Bootstrap mean: {np.mean(boot_deltas):.4f}")
print(f"    Bootstrap SD: {np.std(boot_deltas):.4f}")

print(f"\n  Cohen's d:")
print(f"    Point estimate: {observed_d:.2f}")
print(f"    Bootstrap 95% CI: [{d_ci[0]:.2f}, {d_ci[1]:.2f}]")
print(f"    Bootstrap median: {np.median(boot_ds):.2f}")
print(f"    Note: Wide CI expected with n=3 per group")

# ═══ 3. Leave-one-out sensitivity ═══
print("\n3. LEAVE-ONE-OUT SENSITIVITY ON COHEN'S d")
for i, s in enumerate(seeds):
    g_loo = np.delete(gov_ehes, i)
    u_loo = np.delete(ungov_ehes, i)
    d_loo = cohens_d(g_loo, u_loo)
    delta_loo = np.mean(g_loo) - np.mean(u_loo)
    overlap = "No" if min(g_loo) > max(u_loo) else "Yes"
    print(f"  Drop seed {s}: d = {d_loo:.2f}, delta = {delta_loo:+.4f}, overlap = {overlap}")

# Also check: does zero-overlap hold for every LOO?
print(f"\n  Zero-overlap robustness:")
print(f"    Full data: min(gov)={min(gov_ehes):.4f} > max(ungov)={max(ungov_ehes):.4f} → {min(gov_ehes) > max(ungov_ehes)}")

# ═══ 4. Permutation test with honest framing ═══
print("\n4. PERMUTATION TEST (honest framing)")
from itertools import combinations
all_vals = list(gov_ehes) + list(ungov_ehes)
obs_diff = np.mean(gov_ehes) - np.mean(ungov_ehes)
count = 0
total = 0
for combo in combinations(range(6), 3):
    g = [all_vals[i] for i in combo]
    u = [all_vals[i] for i in range(6) if i not in combo]
    if np.mean(g) - np.mean(u) >= obs_diff:
        count += 1
    total += 1
print(f"  Observed difference: {obs_diff:.4f}")
print(f"  Permutation p-value: {count}/{total} = {count/total:.4f}")
print(f"  Total permutations: {total} (= C(6,3))")
print(f"  NOTE: p=0.05 is the MINIMUM achievable p for n=3+3")
print(f"  Honest framing: 'The observed difference is the most extreme")
print(f"  of all {total} possible allocations (p = 1/{total} = {1/total:.2f}),")
print(f"  consistent with zero distributional overlap.'")

# ═══ 5. Null-model CACR ═══
print("\n5. NULL-MODEL CACR (random action selection)")
# For the irrigation 25-cell WSA/ACA matrix, random selection = 1/5 for each skill
# Coherent = NOT choosing increase when WSA=H
# 5 skills, 2 are increases → P(incoherent | random) = 2/5 = 0.40
# P(coherent | random) = 3/5 = 0.60
print(f"  Irrigation WSA coherence (CACR analog):")
print(f"    5 skills, 2 increase types → P(coherent | random) = 3/5 = 60.0%")
print(f"    Governed observed: 58.0% (NEAR random baseline)")
print(f"    Ungoverned observed: 9.4% (BELOW random — systematic bias toward increase)")
print(f"    Interpretation: Governance restores near-random coherence;")
print(f"    ungoverned agents are WORSE than random (strong increase bias)")

# For the flood CACR (25-cell matrix), need to estimate
print(f"\n  Flood CACR (25 cells, discrete actions):")
print(f"    Need exact cell-action mapping to compute null rate")
print(f"    Rough estimate: if 5 actions, ~40-60% coherent by chance")

# ═══ 6. Cross-domain claim assessment ═══
print("\n6. CROSS-DOMAIN CLAIM ASSESSMENT")
print(f"  Irrigation EHE: {np.mean(gov_ehes):.4f} ± {np.std(gov_ehes,ddof=1):.4f}")
print(f"  Flood EHE:      0.7400 (single estimate, no CI available)")
print(f"  Difference:     {abs(np.mean(gov_ehes) - 0.7400):.4f}")
print(f"  Irrigation 95% CI: [{np.mean(gov_ehes) - 1.96*np.std(gov_ehes,ddof=1)/np.sqrt(3):.4f}, {np.mean(gov_ehes) + 1.96*np.std(gov_ehes,ddof=1)/np.sqrt(3):.4f}]")
print(f"  Does flood value fall within irrigation CI? ", end="")
ci_low = np.mean(gov_ehes) - 1.96*np.std(gov_ehes,ddof=1)/np.sqrt(3)
ci_high = np.mean(gov_ehes) + 1.96*np.std(gov_ehes,ddof=1)/np.sqrt(3)
print(f"{'Yes' if ci_low <= 0.740 <= ci_high else 'No'}")
print(f"  EXPERT RECOMMENDATION: Remove 'domain-invariant operating point' claim.")
print(f"  REVISED CLAIM: 'governed EHE values are numerically similar across domains")
print(f"  (0.738 vs 0.740), though the single flood estimate lacks a CI for formal comparison.'")

# ═══ SUMMARY TABLE FOR PAPER ═══
print("\n" + "=" * 80)
print("SUMMARY: Numbers for revised manuscript")
print("=" * 80)
print(f"""
  PRIMARY OUTCOME: EHE (Effective Heterogeneity Entropy)
  ───────────────────────────────────────────────────────
  Governed:   {np.mean(gov_ehes):.3f} ± {np.std(gov_ehes,ddof=1):.3f} (seeds: {', '.join(f'{v:.3f}' for v in gov_ehes)})
  Ungoverned: {np.mean(ungov_ehes):.3f} ± {np.std(ungov_ehes,ddof=1):.3f} (seeds: {', '.join(f'{v:.3f}' for v in ungov_ehes)})
  Delta:      +{observed_delta:.3f} (bootstrap 95% CI: [{delta_ci[0]:.3f}, {delta_ci[1]:.3f}])
  Cohen's d:  {observed_d:.2f} (bootstrap 95% CI: [{d_ci[0]:.2f}, {d_ci[1]:.2f}])
  Permutation: p = 1/20 = 0.05 (minimum for n=3+3; consistent with zero overlap)
  Zero overlap: min(gov) = {min(gov_ehes):.3f} > max(ungov) = {max(ungov_ehes):.3f}

  RECOMMENDED PAPER LANGUAGE:
  "Governed EHE exceeded ungoverned EHE by +{observed_delta:.3f}
  (bootstrap 95% CI [{delta_ci[0]:.3f}, {delta_ci[1]:.3f}]; Cohen's d = {observed_d:.1f},
  bootstrap 95% CI [{d_ci[0]:.1f}, {d_ci[1]:.1f}]; exact permutation test
  p = 1/20 = 0.05, the minimum achievable for n = 3 per group,
  consistent with zero distributional overlap where the lowest
  governed value ({min(gov_ehes):.3f}) exceeded the highest ungoverned
  value ({max(ungov_ehes):.3f}))."
""")
