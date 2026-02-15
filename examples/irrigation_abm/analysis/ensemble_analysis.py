#!/usr/bin/env python3
"""
Governed Irrigation Ensemble Analysis — Seed42 + Seed43 + Seed44
78 agents x 42 years = 3,276 agent-year observations per seed
For Nature Water paper.
"""

import pandas as pd
import numpy as np
import sys, os

# ── Load data ────────────────────────────────────────────────────────────
BASE = r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\results"
seeds = {}
for s in [42, 43, 44]:
    path = os.path.join(BASE, f"production_v20_42yr_seed{s}", "simulation_log.csv")
    if os.path.exists(path):
        seeds[s] = pd.read_csv(path, encoding="utf-8")
        seeds[s]["seed"] = s

df42 = seeds[42]
df43 = seeds[43]
df44 = seeds.get(44)
dfs = [seeds[s] for s in sorted(seeds)]
df = pd.concat(dfs, ignore_index=True)

print(f"Seeds loaded: {sorted(seeds.keys())}")
for s, sub in sorted(seeds.items()):
    print(f"  Seed{s}: {len(sub)} rows, {sub['agent_id'].nunique()} agents, {sub['year'].nunique()} years")
print(f"Ensemble: {len(df)} rows")

SKILLS = ["increase_large", "increase_small", "maintain_demand", "decrease_small", "decrease_large"]

# ══════════════════════════════════════════════════════════════════════════
# 1. PER-SEED SKILL DISTRIBUTION (side by side)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("1. PER-SEED SKILL DISTRIBUTION")
print("="*80)

for s in sorted(seeds):
    sub = seeds[s]
    counts = sub["yearly_decision"].value_counts()
    total = len(sub)
    print(f"\n  Seed{s} (n={total}):")
    for sk in SKILLS:
        c = counts.get(sk, 0)
        print(f"    {sk:25s}  {c:5d}  ({100*c/total:5.1f}%)")

# Ensemble
print(f"\n  Ensemble (n={len(df)}):")
counts_all = df["yearly_decision"].value_counts()
for sk in SKILLS:
    c = counts_all.get(sk, 0)
    print(f"    {sk:25s}  {c:5d}  ({100*c/len(df):5.1f}%)")


# ══════════════════════════════════════════════════════════════════════════
# 2 & 3. EHE PER YEAR PER SEED + ENSEMBLE MEAN ± STD
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("2. EMPIRICAL HETEROGENEITY ENTROPY (EHE) PER YEAR")
print("="*80)


def ehe_for_group(group):
    """Shannon entropy over skill distribution, normalized to [0,1]."""
    counts = group["yearly_decision"].value_counts()
    probs = counts / counts.sum()
    H = -np.sum(probs * np.log2(probs))
    H_max = np.log2(len(SKILLS))  # 5 skills → log2(5) ≈ 2.322
    return H / H_max


ehe_per_seed = {}
for s in sorted(seeds):
    ehe_per_seed[s] = seeds[s].groupby("year").apply(ehe_for_group).rename(f"ehe_{s}")
ehe_df = pd.concat(ehe_per_seed.values(), axis=1)
seed_cols = [f"ehe_{s}" for s in sorted(seeds)]
ehe_df["ensemble_mean"] = ehe_df[seed_cols].mean(axis=1)
ehe_df["ensemble_std"] = ehe_df[seed_cols].std(axis=1)

header = f"  {'Year':>4s}" + "".join(f"  {'Seed'+str(s):>8s}" for s in sorted(seeds)) + f"  {'Mean±Std':>14s}"
print(f"\n{header}")
print(f"  {'----':>4s}" + "".join(f"  {'------':>8s}" for _ in seeds) + f"  {'--------':>14s}")
for yr in sorted(ehe_df.index):
    row = ehe_df.loc[yr]
    vals = "".join(f"  {row[f'ehe_{s}']:8.4f}" for s in sorted(seeds))
    print(f"  {yr:4d}{vals}  {row['ensemble_mean']:6.4f}±{row['ensemble_std']:.4f}")

per_year_means = {s: ehe_per_seed[s].mean() for s in sorted(seeds)}
overall_mean = ehe_df["ensemble_mean"].mean()
overall_std = ehe_df["ensemble_mean"].std()
ci95_lo = overall_mean - 1.96 * overall_std
ci95_hi = overall_mean + 1.96 * overall_std

print(f"\n  3a. PER-YEAR MEAN EHE (for temporal analysis)")
for s in sorted(seeds):
    print(f"     Seed{s} mean EHE: {per_year_means[s]:.4f}")
print(f"     Ensemble mean:   {overall_mean:.4f} ± {overall_std:.4f}")
print(f"     95% range:       [{ci95_lo:.4f}, {ci95_hi:.4f}]")
print(f"     Min year EHE:    {ehe_df['ensemble_mean'].min():.4f} (year {ehe_df['ensemble_mean'].idxmin()})")
print(f"     Max year EHE:    {ehe_df['ensemble_mean'].max():.4f} (year {ehe_df['ensemble_mean'].idxmax()})")

# 3b. AGGREGATE EHE (for cross-domain comparison — matches flood domain method)
H_max = np.log2(len(SKILLS))
def aggregate_ehe(sub):
    counts = sub["yearly_decision"].value_counts()
    probs = counts / counts.sum()
    H = -np.sum(probs * np.log2(probs))
    return H / H_max

agg_per_seed = {s: aggregate_ehe(seeds[s]) for s in sorted(seeds)}
agg_ensemble = aggregate_ehe(df)
agg_values = list(agg_per_seed.values())
agg_mean = np.mean(agg_values)
agg_std = np.std(agg_values, ddof=1) if len(agg_values) > 1 else 0.0

print(f"\n  3b. AGGREGATE EHE (all traces, k={len(SKILLS)} fixed — USE FOR PAPER)")
for s in sorted(seeds):
    print(f"     Seed{s} aggregate EHE: {agg_per_seed[s]:.4f}")
print(f"     Mean ± SD:            {agg_mean:.4f} ± {agg_std:.4f}")
print(f"     Pooled ensemble:      {agg_ensemble:.4f}")


# ══════════════════════════════════════════════════════════════════════════
# 4. AGGREGATE DEMAND RATIO PER YEAR
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("4. AGGREGATE DEMAND RATIO (total_request / total_water_right)")
print("="*80)

def demand_ratio(sub):
    g = sub.groupby("year").agg({"request": "sum", "water_right": "sum"})
    return (g["request"] / g["water_right"])

dr42 = demand_ratio(df42).rename("dr_42")
dr43 = demand_ratio(df43).rename("dr_43")
dr_df = pd.concat([dr42, dr43], axis=1)
dr_df["ensemble_mean"] = dr_df.mean(axis=1)
dr_df["ensemble_std"] = dr_df.std(axis=1)

print(f"\n  {'Year':>4s}  {'Seed42':>8s}  {'Seed43':>8s}  {'Mean':>8s}")
for yr in sorted(dr_df.index):
    row = dr_df.loc[yr]
    print(f"  {yr:4d}  {row['dr_42']:8.4f}  {row['dr_43']:8.4f}  {row['ensemble_mean']:8.4f}")

print(f"\n  Ensemble mean demand ratio:  {dr_df['ensemble_mean'].mean():.4f} ± {dr_df['ensemble_mean'].std():.4f}")
print(f"  Year 1 demand ratio:         {dr_df['ensemble_mean'].iloc[0]:.4f}")
print(f"  Year 42 demand ratio:        {dr_df['ensemble_mean'].iloc[-1]:.4f}")
print(f"  Net change (Y42-Y1):         {dr_df['ensemble_mean'].iloc[-1] - dr_df['ensemble_mean'].iloc[0]:+.4f}")


# ══════════════════════════════════════════════════════════════════════════
# 5. INAPPROPRIATE BEHAVIOR RATE (IBR)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("5. INAPPROPRIATE BEHAVIOR RATE (IBR)")
print("="*80)

for seed_label, sub in [("Seed42", df42), ("Seed43", df43), ("Ensemble", df)]:
    n = len(sub)

    # 5a. Increase at utilisation >= 95%
    high_util = sub[sub["utilisation_pct"] >= 95.0]
    increase_at_high = high_util[high_util["yearly_decision"].str.startswith("increase")]
    ibr_util = len(increase_at_high) / len(high_util) if len(high_util) > 0 else 0

    # 5b. Increase when curtailment > 0.05 (exclude year 1 baseline)
    # Year 1 has curtailment_ratio = 0.05 as default baseline, so exclude
    curt_sub = sub[(sub["curtailment_ratio"] > 0.05) & (sub["year"] > 1)]
    increase_at_curt = curt_sub[curt_sub["yearly_decision"].str.startswith("increase")]
    ibr_curt = len(increase_at_curt) / len(curt_sub) if len(curt_sub) > 0 else 0

    # 5c. WSA=H, ACA=L choosing increase (threat high, coping low → should decrease)
    hl = sub[(sub["wsa_label"] == "H") & (sub["aca_label"] == "L")]
    hl_increase = hl[hl["yearly_decision"].str.startswith("increase")]
    ibr_hl = len(hl_increase) / len(hl) if len(hl) > 0 else 0

    print(f"\n  {seed_label}:")
    print(f"    IBR(util>=95%->increase):    {ibr_util:.4f}  ({len(increase_at_high)}/{len(high_util)} agent-years)")
    print(f"    IBR(curt>0.05->increase):   {ibr_curt:.4f}  ({len(increase_at_curt)}/{len(curt_sub)} agent-years)")
    print(f"    IBR(WSA=H,ACA=L->increase): {ibr_hl:.4f}  ({len(hl_increase)}/{len(hl)} agent-years)")

# Composite IBR (union of all inappropriate)
print(f"\n  Composite IBR (union of all inappropriate behaviors):")
for seed_label, sub in [("Seed42", df42), ("Seed43", df43), ("Ensemble", df)]:
    # All agent-years with any inappropriate increase
    cond_util = (sub["utilisation_pct"] >= 95.0) & sub["yearly_decision"].str.startswith("increase")
    cond_curt = (sub["curtailment_ratio"] > 0.05) & (sub["year"] > 1) & sub["yearly_decision"].str.startswith("increase")
    cond_hl = (sub["wsa_label"] == "H") & (sub["aca_label"] == "L") & sub["yearly_decision"].str.startswith("increase")
    inappropriate = sub[cond_util | cond_curt | cond_hl]
    ibr_composite = len(inappropriate) / len(sub)
    print(f"    {seed_label}: {ibr_composite:.4f}  ({len(inappropriate)}/{len(sub)})")


# ══════════════════════════════════════════════════════════════════════════
# 6. CLUSTER DIFFERENTIATION
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("6. CLUSTER DIFFERENTIATION")
print("="*80)

clusters = df["cluster"].unique()
for seed_label, sub in [("Seed42", df42), ("Seed43", df43)]:
    print(f"\n  {seed_label}:")
    for cl in sorted(clusters):
        cl_sub = sub[sub["cluster"] == cl]
        total = len(cl_sub)
        n_agents = cl_sub["agent_id"].nunique()
        counts = cl_sub["yearly_decision"].value_counts()
        dist_str = "  ".join(f"{sk[:3]}={100*counts.get(sk,0)/total:.1f}%" for sk in SKILLS)
        print(f"    {cl:35s} ({n_agents:2d} agents, {total:4d} obs): {dist_str}")

# Ensemble cluster stats
print(f"\n  Ensemble cluster means:")
for cl in sorted(clusters):
    cl42 = df42[df42["cluster"] == cl]
    cl43 = df43[df43["cluster"] == cl]
    for sk in SKILLS:
        p42 = 100 * (cl42["yearly_decision"] == sk).sum() / len(cl42) if len(cl42) > 0 else 0
        p43 = 100 * (cl43["yearly_decision"] == sk).sum() / len(cl43) if len(cl43) > 0 else 0
        mean_p = (p42 + p43) / 2
    # Just show increase vs decrease
    inc42 = 100 * cl42["yearly_decision"].str.startswith("increase").sum() / len(cl42)
    dec42 = 100 * cl42["yearly_decision"].str.startswith("decrease").sum() / len(cl42)
    inc43 = 100 * cl43["yearly_decision"].str.startswith("increase").sum() / len(cl43)
    dec43 = 100 * cl43["yearly_decision"].str.startswith("decrease").sum() / len(cl43)
    inc_mean = (inc42 + inc43) / 2
    dec_mean = (dec42 + dec43) / 2
    maint42 = 100 * (cl42["yearly_decision"] == "maintain_demand").sum() / len(cl42)
    maint43 = 100 * (cl43["yearly_decision"] == "maintain_demand").sum() / len(cl43)
    maint_mean = (maint42 + maint43) / 2
    print(f"    {cl:35s}  increase={inc_mean:5.1f}%  maintain={maint_mean:5.1f}%  decrease={dec_mean:5.1f}%")


# ══════════════════════════════════════════════════════════════════════════
# 7. BASIN DIFFERENTIATION
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("7. BASIN DIFFERENTIATION")
print("="*80)

basins = sorted(df["basin"].unique())
for seed_label, sub in [("Seed42", df42), ("Seed43", df43)]:
    print(f"\n  {seed_label}:")
    for basin in basins:
        b_sub = sub[sub["basin"] == basin]
        total = len(b_sub)
        n_agents = b_sub["agent_id"].nunique()
        counts = b_sub["yearly_decision"].value_counts()
        dist_str = "  ".join(f"{sk[:3]}={100*counts.get(sk,0)/total:.1f}%" for sk in SKILLS)
        # Also mean utilisation, curtailment
        mu = b_sub["utilisation_pct"].mean()
        mc = b_sub["curtailment_ratio"].mean()
        print(f"    {basin:20s} ({n_agents:2d} agents): {dist_str}  util={mu:.1f}%  curt={mc:.3f}")

print(f"\n  Ensemble basin means:")
for basin in basins:
    b42 = df42[df42["basin"] == basin]
    b43 = df43[df43["basin"] == basin]
    inc42 = 100 * b42["yearly_decision"].str.startswith("increase").sum() / len(b42)
    inc43 = 100 * b43["yearly_decision"].str.startswith("increase").sum() / len(b43)
    dec42 = 100 * b42["yearly_decision"].str.startswith("decrease").sum() / len(b42)
    dec43 = 100 * b43["yearly_decision"].str.startswith("decrease").sum() / len(b43)
    maint42 = 100 * (b42["yearly_decision"] == "maintain_demand").sum() / len(b42)
    maint43 = 100 * (b43["yearly_decision"] == "maintain_demand").sum() / len(b43)
    util42 = b42["utilisation_pct"].mean()
    util43 = b43["utilisation_pct"].mean()
    curt42 = b42["curtailment_ratio"].mean()
    curt43 = b43["curtailment_ratio"].mean()
    print(f"    {basin:20s}  increase={np.mean([inc42,inc43]):5.1f}%  maintain={np.mean([maint42,maint43]):5.1f}%  decrease={np.mean([dec42,dec43]):5.1f}%  util={np.mean([util42,util43]):.1f}%  curt={np.mean([curt42,curt43]):.3f}")


# ══════════════════════════════════════════════════════════════════════════
# 8. GOVERNANCE COMPARISON
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("8. GOVERNANCE COMPARISON (from audit data)")
print("="*80)

gov = {
    "Seed42": {"interventions": 2992, "top_rule_count": 2857, "retry_success": 355, "retry_exhausted": 400},
    "Seed43": {"interventions": 3366, "top_rule_count": 3229, "retry_success": 360, "retry_exhausted": 490},
}

for seed_label, g in gov.items():
    total_ay = 3276
    interv_rate = g["interventions"] / total_ay
    retry_total = g["retry_success"] + g["retry_exhausted"]
    retry_success_rate = g["retry_success"] / retry_total if retry_total > 0 else 0
    top_rule_share = g["top_rule_count"] / g["interventions"]
    print(f"\n  {seed_label}:")
    print(f"    Total interventions:         {g['interventions']:5d}  ({100*interv_rate:.1f}% of agent-years)")
    print(f"    Top rule share:              {g['top_rule_count']:5d}  ({100*top_rule_share:.1f}% of interventions)")
    print(f"    Retry success:               {g['retry_success']:5d}")
    print(f"    Retry exhausted:             {g['retry_exhausted']:5d}")
    print(f"    Retry success rate:          {100*retry_success_rate:.1f}%")

# Ensemble governance
ens_interv = np.mean([gov["Seed42"]["interventions"], gov["Seed43"]["interventions"]])
ens_interv_std = np.std([gov["Seed42"]["interventions"], gov["Seed43"]["interventions"]])
ens_retry_succ = np.mean([gov["Seed42"]["retry_success"], gov["Seed43"]["retry_success"]])
ens_retry_exh = np.mean([gov["Seed42"]["retry_exhausted"], gov["Seed43"]["retry_exhausted"]])
ens_retry_rate = ens_retry_succ / (ens_retry_succ + ens_retry_exh)

print(f"\n  Ensemble Governance:")
print(f"    Mean interventions:          {ens_interv:.0f} ± {ens_interv_std:.0f}")
print(f"    Mean intervention rate:      {100*ens_interv/3276:.1f}%")
print(f"    Mean retry success:          {ens_retry_succ:.0f}")
print(f"    Mean retry exhausted:        {ens_retry_exh:.0f}")
print(f"    Mean retry success rate:     {100*ens_retry_rate:.1f}%")
print(f"    Top rule (H-threat H-cope):  {np.mean([gov['Seed42']['top_rule_count'], gov['Seed43']['top_rule_count']]):.0f} ({100*np.mean([gov['Seed42']['top_rule_count']/gov['Seed42']['interventions'], gov['Seed43']['top_rule_count']/gov['Seed43']['interventions']]):.1f}%)")


# ══════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE FOR PAPER
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "="*80)
print("SUMMARY TABLE — Nature Water Paper")
print("="*80)

# Skill distribution ensemble
inc_pct = 100 * df["yearly_decision"].str.startswith("increase").sum() / len(df)
maint_pct = 100 * (df["yearly_decision"] == "maintain_demand").sum() / len(df)
dec_pct = 100 * df["yearly_decision"].str.startswith("decrease").sum() / len(df)

# Composite IBR ensemble
cond_util_e = (df["utilisation_pct"] >= 95.0) & df["yearly_decision"].str.startswith("increase")
cond_curt_e = (df["curtailment_ratio"] > 0.05) & (df["year"] > 1) & df["yearly_decision"].str.startswith("increase")
cond_hl_e = (df["wsa_label"] == "H") & (df["aca_label"] == "L") & df["yearly_decision"].str.startswith("increase")
ibr_composite_e = 100 * (cond_util_e | cond_curt_e | cond_hl_e).sum() / len(df)

print(f"""
  Metric                          Seed42      Seed43      Ensemble
  ------------------------------- ---------- ---------- ----------
  Agent-years                     {len(df42):>10d} {len(df43):>10d} {len(df):>10d}
  EHE (mean over years)           {ehe_42.mean():>10.4f} {ehe_43.mean():>10.4f} {overall_mean:>10.4f}
  EHE 95% range                                         [{ci95_lo:.4f}, {ci95_hi:.4f}]
  Demand ratio (mean over years)  {dr42.mean():>10.4f} {dr43.mean():>10.4f} {dr_df['ensemble_mean'].mean():>10.4f}
  Increase actions (%)            {100*df42['yearly_decision'].str.startswith('increase').sum()/len(df42):>9.1f}% {100*df43['yearly_decision'].str.startswith('increase').sum()/len(df43):>9.1f}% {inc_pct:>9.1f}%
  Maintain actions (%)            {100*(df42['yearly_decision']=='maintain_demand').sum()/len(df42):>9.1f}% {100*(df43['yearly_decision']=='maintain_demand').sum()/len(df43):>9.1f}% {maint_pct:>9.1f}%
  Decrease actions (%)            {100*df42['yearly_decision'].str.startswith('decrease').sum()/len(df42):>9.1f}% {100*df43['yearly_decision'].str.startswith('decrease').sum()/len(df43):>9.1f}% {dec_pct:>9.1f}%
  Composite IBR (%)               see above   see above {ibr_composite_e:>9.1f}%
  Governance interventions        {gov['Seed42']['interventions']:>10d} {gov['Seed43']['interventions']:>10d} {ens_interv:>10.0f}
  Governance intervention rate    {100*gov['Seed42']['interventions']/3276:>9.1f}% {100*gov['Seed43']['interventions']/3276:>9.1f}% {100*ens_interv/3276:>9.1f}%
  Retry success rate              {100*gov['Seed42']['retry_success']/(gov['Seed42']['retry_success']+gov['Seed42']['retry_exhausted']):>9.1f}% {100*gov['Seed43']['retry_success']/(gov['Seed43']['retry_success']+gov['Seed43']['retry_exhausted']):>9.1f}% {100*ens_retry_rate:>9.1f}%
""")

print("Analysis complete.")
