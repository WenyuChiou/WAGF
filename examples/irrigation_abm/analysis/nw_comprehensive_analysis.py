#!/usr/bin/env python3
"""
Nature Water — Comprehensive Irrigation Analysis
Tasks: First-attempt EHE (#25), IBR decomposition (#26), Demand ratio (#27)
Plus: governed vs ungoverned comparison for paper tables.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import math
import json

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\results")
SKILLS = ["increase_large", "increase_small", "maintain_demand", "decrease_small", "decrease_large"]
K = len(SKILLS)  # 5
H_MAX = math.log2(K)  # 2.322

def shannon_entropy(counts_dict):
    total = sum(counts_dict.values())
    if total == 0:
        return 0.0
    probs = np.array([v / total for v in counts_dict.values()])
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))

def ehe(counts_dict):
    return shannon_entropy(counts_dict) / H_MAX if H_MAX > 0 else 0.0

# ══════════════════════════════════════════════════════════════════════════
# LOAD ALL DATA
# ══════════════════════════════════════════════════════════════════════════
seeds = [42, 43, 44]

gov_audit = {}
gov_sim = {}
ungov_audit = {}
ungov_sim = {}

for s in seeds:
    gp = BASE / f"production_v20_42yr_seed{s}"
    up = BASE / f"ungoverned_v20_42yr_seed{s}"

    gov_audit[s] = pd.read_csv(gp / "irrigation_farmer_governance_audit.csv", encoding="utf-8-sig")
    gov_sim[s] = pd.read_csv(gp / "simulation_log.csv", encoding="utf-8")
    ungov_audit[s] = pd.read_csv(up / "irrigation_farmer_governance_audit.csv", encoding="utf-8-sig")
    ungov_sim[s] = pd.read_csv(up / "simulation_log.csv", encoding="utf-8")

print(f"Loaded {len(seeds)} seeds x 2 conditions (governed + ungoverned)")
for s in seeds:
    print(f"  Seed{s}: gov={len(gov_audit[s])} traces, ungov={len(ungov_audit[s])} traces")

# ══════════════════════════════════════════════════════════════════════════
# TASK #25: FIRST-ATTEMPT EHE
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("TASK #25: FIRST-ATTEMPT EHE (proposed_skill before governance)")
print("=" * 80)

for label, audit_dict in [("GOVERNED", gov_audit), ("UNGOVERNED", ungov_audit)]:
    print(f"\n  {label}:")
    fa_ehes = {}
    for s in seeds:
        df = audit_dict[s]
        proposed = df["proposed_skill"].str.lower().str.strip()
        counts = Counter(proposed)
        fa_ehe = ehe(counts)
        fa_ehes[s] = fa_ehe
        dist_str = "  ".join(f"{sk[:5]}={counts.get(sk,0)}" for sk in SKILLS)
        print(f"    Seed{s}: first-attempt EHE = {fa_ehe:.4f}  ({dist_str})")

    vals = list(fa_ehes.values())
    print(f"    Mean ± SD: {np.mean(vals):.4f} ± {np.std(vals, ddof=1):.4f}")

# Also compute final (executed) EHE for comparison
print(f"\n  COMPARISON: First-attempt vs Final EHE")
for label, audit_dict in [("GOVERNED", gov_audit), ("UNGOVERNED", ungov_audit)]:
    fa_vals = []
    final_vals = []
    for s in seeds:
        df = audit_dict[s]
        # First-attempt = proposed_skill
        proposed = df["proposed_skill"].str.lower().str.strip()
        fa_vals.append(ehe(Counter(proposed)))
        # Final = final_skill (governed) or proposed_skill (ungoverned, since no governance)
        final_col = "final_skill" if "final_skill" in df.columns else "proposed_skill"
        final = df[final_col].str.lower().str.strip()
        final_vals.append(ehe(Counter(final)))

    fa_mean = np.mean(fa_vals)
    final_mean = np.mean(final_vals)
    print(f"  {label:12s}: first-attempt={fa_mean:.4f}  final={final_mean:.4f}  delta={final_mean - fa_mean:+.4f}")

# ══════════════════════════════════════════════════════════════════════════
# TASK #26: IBR DECOMPOSITION (CACR, retry rate, fallback rate)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("TASK #26: IBR DECOMPOSITION (governance audit)")
print("=" * 80)

for label, audit_dict in [("GOVERNED", gov_audit), ("UNGOVERNED", ungov_audit)]:
    print(f"\n  {label}:")

    all_retry_rates = []
    all_fallback_rates = []
    all_approval_rates = []
    all_rejection_rates = []

    for s in seeds:
        df = audit_dict[s]
        total = len(df)

        # Status breakdown
        status_counts = df["status"].value_counts()
        approved = status_counts.get("APPROVED", 0)
        rejected = status_counts.get("REJECTED", 0)
        retry_success = status_counts.get("RETRY_SUCCESS", 0)
        retry_exhausted = status_counts.get("RETRY_EXHAUSTED", 0)

        # Retry rate: rows with retry_count > 0
        retry_rate = (df["retry_count"].fillna(0).astype(int) > 0).mean()

        # Fallback rate: final_skill != proposed_skill
        if "final_skill" in df.columns:
            fallback = (df["final_skill"].fillna("").str.lower() != df["proposed_skill"].fillna("").str.lower()).mean()
        else:
            fallback = 0.0

        approval_rate = (approved + retry_success) / total
        rejection_rate = (rejected + retry_exhausted) / total

        all_retry_rates.append(retry_rate)
        all_fallback_rates.append(fallback)
        all_approval_rates.append(approval_rate)
        all_rejection_rates.append(rejection_rate)

        print(f"    Seed{s} (n={total}):")
        print(f"      APPROVED:       {approved:5d} ({100*approved/total:.1f}%)")
        print(f"      RETRY_SUCCESS:  {retry_success:5d} ({100*retry_success/total:.1f}%)")
        print(f"      REJECTED:       {rejected:5d} ({100*rejected/total:.1f}%)")
        print(f"      RETRY_EXHAUSTED:{retry_exhausted:5d} ({100*retry_exhausted/total:.1f}%)")
        print(f"      Retry rate:     {100*retry_rate:.1f}%")
        print(f"      Fallback rate:  {100*fallback:.1f}%")
        print(f"      Approval rate:  {100*approval_rate:.1f}%")

    print(f"    Ensemble mean:")
    print(f"      Retry rate:     {100*np.mean(all_retry_rates):.1f}% ± {100*np.std(all_retry_rates, ddof=1):.1f}%")
    print(f"      Fallback rate:  {100*np.mean(all_fallback_rates):.1f}% ± {100*np.std(all_fallback_rates, ddof=1):.1f}%")
    print(f"      Approval rate:  {100*np.mean(all_approval_rates):.1f}% ± {100*np.std(all_approval_rates, ddof=1):.1f}%")
    print(f"      Rejection rate: {100*np.mean(all_rejection_rates):.1f}% ± {100*np.std(all_rejection_rates, ddof=1):.1f}%")

# WSA/ACA construct coherence (CACR analog for irrigation)
print(f"\n  CONSTRUCT COHERENCE (WSA/ACA → Action):")
print(f"  Rule: WSA=H + ACA=H → should NOT increase (drought-aware + capable → conserve)")
print(f"  Rule: WSA=H + ACA=L → should NOT increase (drought-aware + limited → reduce)")

for label, audit_dict in [("GOVERNED", gov_audit), ("UNGOVERNED", ungov_audit)]:
    coherence_rates = []
    for s in seeds:
        df = audit_dict[s]
        # Use the appropriate skill column
        skill_col = "final_skill" if "final_skill" in df.columns and label == "GOVERNED" else "proposed_skill"
        skill = df[skill_col].str.lower().str.strip()
        wsa = df["construct_WSA_LABEL"].fillna("").str.strip()
        aca = df["construct_ACA_LABEL"].fillna("").str.strip()

        # Incoherent: WSA=H (drought severe) but chose increase
        hh_mask = (wsa.isin(["H", "VH"])) & (aca.isin(["H", "VH"]))
        hl_mask = (wsa.isin(["H", "VH"])) & (aca.isin(["L", "VL"]))

        hh_total = hh_mask.sum()
        hl_total = hl_mask.sum()

        hh_increase = (hh_mask & skill.str.startswith("increase")).sum()
        hl_increase = (hl_mask & skill.str.startswith("increase")).sum()

        # CACR analog: fraction of decisions that are construct-coherent
        # For simplicity: incoherent = increase when WSA=H
        h_mask = wsa.isin(["H", "VH"])
        h_total = h_mask.sum()
        h_increase = (h_mask & skill.str.startswith("increase")).sum()
        h_coherent = h_total - h_increase
        coherence = h_coherent / h_total if h_total > 0 else 1.0
        coherence_rates.append(coherence)

        print(f"    {label} Seed{s}: WSA=H→increase = {h_increase}/{h_total} ({100*h_increase/h_total:.1f}% incoherent)")
        print(f"      HH(both high): increase = {hh_increase}/{hh_total} ({100*hh_increase/hh_total:.1f}%)" if hh_total > 0 else f"      HH: n/a")
        print(f"      HL(high-low):  increase = {hl_increase}/{hl_total} ({100*hl_increase/hl_total:.1f}%)" if hl_total > 0 else f"      HL: n/a")

    print(f"    {label} Ensemble WSA-coherence: {100*np.mean(coherence_rates):.1f}% ± {100*np.std(coherence_rates, ddof=1):.1f}%")

# ══════════════════════════════════════════════════════════════════════════
# TASK #27: DEMAND RATIO (all 3 seeds)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("TASK #27: DEMAND RATIO (request / water_right)")
print("=" * 80)

for label, sim_dict in [("GOVERNED", gov_sim), ("UNGOVERNED", ungov_sim)]:
    print(f"\n  {label}:")

    seed_ratios = {}
    for s in seeds:
        df = sim_dict[s]
        yearly = df.groupby("year").agg({"request": "sum", "water_right": "sum"})
        ratio = yearly["request"] / yearly["water_right"]
        seed_ratios[s] = ratio.mean()
        print(f"    Seed{s}: mean demand ratio = {ratio.mean():.4f} (range: {ratio.min():.4f} - {ratio.max():.4f})")

    vals = list(seed_ratios.values())
    print(f"    Ensemble: {np.mean(vals):.4f} ± {np.std(vals, ddof=1):.4f}")

# ══════════════════════════════════════════════════════════════════════════
# AGGREGATE EHE COMPARISON (paper's primary metric)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("AGGREGATE EHE COMPARISON (governed vs ungoverned)")
print("=" * 80)

gov_ehes = []
ungov_ehes = []

for s in seeds:
    # Governed: use simulation_log yearly_decision (final executed action)
    g_counts = Counter(gov_sim[s]["yearly_decision"].str.lower().str.strip())
    g_ehe = ehe(g_counts)
    gov_ehes.append(g_ehe)

    # Ungoverned: same
    u_counts = Counter(ungov_sim[s]["yearly_decision"].str.lower().str.strip())
    u_ehe = ehe(u_counts)
    ungov_ehes.append(u_ehe)

    print(f"  Seed{s}: governed={g_ehe:.4f}  ungoverned={u_ehe:.4f}  delta={g_ehe - u_ehe:+.4f}")

gov_mean, gov_std = np.mean(gov_ehes), np.std(gov_ehes, ddof=1)
ungov_mean, ungov_std = np.mean(ungov_ehes), np.std(ungov_ehes, ddof=1)
delta = gov_mean - ungov_mean

# Cohen's d (pooled SD)
pooled_sd = np.sqrt((gov_std**2 + ungov_std**2) / 2)
cohens_d = delta / pooled_sd if pooled_sd > 0 else float('inf')

# Permutation test (exact for n=3+3)
all_vals = gov_ehes + ungov_ehes
observed_diff = np.mean(gov_ehes) - np.mean(ungov_ehes)
from itertools import combinations
n_total = len(all_vals)
n_gov = len(gov_ehes)
count_extreme = 0
total_perms = 0
for combo in combinations(range(n_total), n_gov):
    perm_gov = [all_vals[i] for i in combo]
    perm_ungov = [all_vals[i] for i in range(n_total) if i not in combo]
    if np.mean(perm_gov) - np.mean(perm_ungov) >= observed_diff:
        count_extreme += 1
    total_perms += 1

p_value = count_extreme / total_perms

print(f"\n  Governed:   {gov_mean:.4f} ± {gov_std:.4f}")
print(f"  Ungoverned: {ungov_mean:.4f} ± {ungov_std:.4f}")
print(f"  Delta:      {delta:+.4f}")
print(f"  Cohen's d:  {cohens_d:.2f}")
print(f"  Permutation test: p = {p_value:.4f} ({count_extreme}/{total_perms})")
print(f"  No overlap: min(gov)={min(gov_ehes):.4f} > max(ungov)={max(ungov_ehes):.4f} → {min(gov_ehes) > max(ungov_ehes)}")

# ══════════════════════════════════════════════════════════════════════════
# SKILL DISTRIBUTION TABLE (for paper)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SKILL DISTRIBUTION TABLE")
print("=" * 80)

print(f"\n  {'Skill':<20s}", end="")
for s in seeds:
    print(f"  Gov{s}     Ungov{s}", end="")
print(f"  Gov_mean  Ungov_mean")

for sk in SKILLS:
    print(f"  {sk:<20s}", end="")
    for s in seeds:
        g_n = (gov_sim[s]["yearly_decision"].str.lower() == sk).sum()
        u_n = (ungov_sim[s]["yearly_decision"].str.lower() == sk).sum()
        g_pct = 100 * g_n / len(gov_sim[s])
        u_pct = 100 * u_n / len(ungov_sim[s])
        print(f"  {g_pct:5.1f}%    {u_pct:5.1f}%", end="")
    # Ensemble means
    g_pcts = [100 * (gov_sim[s]["yearly_decision"].str.lower() == sk).sum() / len(gov_sim[s]) for s in seeds]
    u_pcts = [100 * (ungov_sim[s]["yearly_decision"].str.lower() == sk).sum() / len(ungov_sim[s]) for s in seeds]
    print(f"  {np.mean(g_pcts):5.1f}%   {np.mean(u_pcts):5.1f}%")

# Behavioral collapse indicator
print(f"\n  Behavioral Collapse Check:")
for s in seeds:
    u_counts = Counter(ungov_sim[s]["yearly_decision"].str.lower().str.strip())
    increase_pct = 100 * (u_counts.get("increase_large", 0) + u_counts.get("increase_small", 0)) / len(ungov_sim[s])
    has_decrease_large = u_counts.get("decrease_large", 0) > 0
    print(f"    Ungoverned Seed{s}: increase={increase_pct:.1f}%, decrease_large present={has_decrease_large}")

# ══════════════════════════════════════════════════════════════════════════
# CROSS-DOMAIN COMPARISON
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("CROSS-DOMAIN COMPARISON (irrigation vs flood)")
print("=" * 80)
print(f"  Irrigation governed EHE:  {gov_mean:.4f} ± {gov_std:.4f} (k=5, n=3 seeds)")
print(f"  Flood governed EHE:       0.7400 (k=5, 400 agents × 13yr)")
print(f"  Difference:               {abs(gov_mean - 0.7400):.4f}")
print(f"  Interpretation:           {'Near-identical' if abs(gov_mean - 0.7400) < 0.01 else 'Small difference'} across domains")

# ══════════════════════════════════════════════════════════════════════════
# VALIDATION ERROR COMPARISON
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("VALIDATION ERROR COMPARISON")
print("=" * 80)

for label, audit_dict in [("GOVERNED", gov_audit), ("UNGOVERNED", ungov_audit)]:
    val_errors = []
    for s in seeds:
        summary_path = BASE / (f"production_v20_42yr_seed{s}" if label == "GOVERNED" else f"ungoverned_v20_42yr_seed{s}") / "audit_summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)
        ve = summary.get("validation_errors", 0)
        total = summary.get("total_traces", 3276)
        val_errors.append(ve / total)
        print(f"  {label} Seed{s}: {ve} validation errors ({100*ve/total:.1f}%)")
    print(f"  {label} Ensemble: {100*np.mean(val_errors):.1f}% ± {100*np.std(val_errors, ddof=1):.1f}%")

# ══════════════════════════════════════════════════════════════════════════
# SUMMARY FOR PAPER
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("═══ NATURE WATER PAPER — KEY NUMBERS ═══")
print("=" * 80)

print(f"""
  IRRIGATION ABLATION (78 agents × 42 years × 3 seeds)
  ─────────────────────────────────────────────────────
  Governed EHE:      {gov_mean:.3f} ± {gov_std:.3f}
  Ungoverned EHE:    {ungov_mean:.3f} ± {ungov_std:.3f}
  Delta EHE:         +{delta:.3f}
  Cohen's d:         {cohens_d:.2f}
  Permutation p:     {p_value:.2f}
  No overlap:        {min(gov_ehes) > max(ungov_ehes)}

  CROSS-DOMAIN
  ─────────────────────────────────────────────────────
  Irrigation gov EHE: {gov_mean:.3f}
  Flood gov EHE:      0.740
  Difference:         {abs(gov_mean - 0.740):.3f}

  FIRST-ATTEMPT EHE (governs retry-inflation hypothesis)
  ─────────────────────────────────────────────────────""")

for label, audit_dict in [("Governed", gov_audit), ("Ungoverned", ungov_audit)]:
    fa_vals = []
    for s in seeds:
        proposed = audit_dict[s]["proposed_skill"].str.lower().str.strip()
        fa_vals.append(ehe(Counter(proposed)))
    print(f"  {label:12s} first-attempt: {np.mean(fa_vals):.3f} ± {np.std(fa_vals, ddof=1):.3f}")

print(f"""
  GOVERNANCE MECHANISM
  ─────────────────────────────────────────────────────""")

for label, audit_dict in [("Governed", gov_audit), ("Ungoverned", ungov_audit)]:
    rr = []
    fr = []
    for s in seeds:
        df = audit_dict[s]
        rr.append((df["retry_count"].fillna(0).astype(int) > 0).mean())
        if "final_skill" in df.columns:
            fr.append((df["final_skill"].fillna("").str.lower() != df["proposed_skill"].fillna("").str.lower()).mean())
        else:
            fr.append(0.0)
    print(f"  {label:12s} retry rate:    {100*np.mean(rr):.1f}% ± {100*np.std(rr, ddof=1):.1f}%")
    print(f"  {label:12s} fallback rate: {100*np.mean(fr):.1f}% ± {100*np.std(fr, ddof=1):.1f}%")

print(f"\n  DEMAND CALIBRATION")
print(f"  ─────────────────────────────────────────────────────")
for label, sim_dict in [("Governed", gov_sim), ("Ungoverned", ungov_sim)]:
    dr_vals = []
    for s in seeds:
        yearly = sim_dict[s].groupby("year").agg({"request": "sum", "water_right": "sum"})
        dr_vals.append((yearly["request"] / yearly["water_right"]).mean())
    print(f"  {label:12s} demand ratio:  {np.mean(dr_vals):.4f} ± {np.std(dr_vals, ddof=1):.4f}")

print(f"\nAnalysis complete.")
