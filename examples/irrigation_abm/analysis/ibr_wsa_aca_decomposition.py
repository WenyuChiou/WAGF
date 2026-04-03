"""
IBR Decomposition by WSA x ACA Quadrants
Nature Water Paper — Insight B / R2: Structured Non-Compliance at Institutional Boundaries
"""
import pandas as pd
import numpy as np
from collections import Counter

# ── Load data ──
base = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/irrigation_abm/results"

gov_dfs = []
for s in [42, 43, 44]:
    path = f"{base}/production_v20_42yr_seed{s}/irrigation_farmer_governance_audit.csv"
    df = pd.read_csv(path, encoding='utf-8')
    df['seed'] = s
    df['condition'] = 'governed'
    gov_dfs.append(df)

ungov_dfs = []
for s in [42, 43, 44]:
    path = f"{base}/ungoverned_v20_42yr_seed{s}/irrigation_farmer_governance_audit.csv"
    df = pd.read_csv(path, encoding='utf-8')
    df['seed'] = s
    df['condition'] = 'ungoverned'
    ungov_dfs.append(df)

gov = pd.concat(gov_dfs, ignore_index=True)
ungov = pd.concat(ungov_dfs, ignore_index=True)

print(f"Governed: {len(gov)} decisions across 3 seeds")
print(f"Ungoverned: {len(ungov)} decisions across 3 seeds")
print(f"WSA levels (gov): {sorted(gov['construct_WSA_LABEL'].dropna().unique())}")
print(f"ACA levels (gov): {sorted(gov['construct_ACA_LABEL'].dropna().unique())}")
print(f"WSA levels (ungov): {sorted(ungov['construct_WSA_LABEL'].dropna().unique())}")
print(f"ACA levels (ungov): {sorted(ungov['construct_ACA_LABEL'].dropna().unique())}")
print(f"Status distribution (gov): {gov['status'].value_counts().to_dict()}")
print(f"Status distribution (ungov): {ungov['status'].value_counts().to_dict()}")
print(f"Proposed skills (gov): {gov['proposed_skill'].value_counts().to_dict()}")
print(f"Proposed skills (ungov): {ungov['proposed_skill'].value_counts().to_dict()}")

# Define orderings
wsa_order = ['VL', 'L', 'M', 'H', 'VH']
aca_order = ['VL', 'L', 'M', 'H', 'VH']
skill_order = ['increase_large', 'increase_small', 'maintain_demand', 'decrease_small', 'decrease_large']

# Flag increase proposals
gov['is_increase'] = gov['proposed_skill'].isin(['increase_small', 'increase_large'])
ungov['is_increase'] = ungov['proposed_skill'].isin(['increase_small', 'increase_large'])
gov['is_rejected'] = gov['status'] == 'REJECTED'

# ═══════════════════════════════════════════════
# 1. WSA x ACA HEATMAP DATA
# ═══════════════════════════════════════════════
print("\n" + "=" * 80)
print("1. WSA x ACA CROSS-TABULATION")
print("=" * 80)

for label, df in [("GOVERNED", gov), ("UNGOVERNED", ungov)]:
    print(f"\n{'_' * 40}")
    print(f"  {label} -- Decision Count per WSA x ACA cell")
    print(f"{'_' * 40}")
    ct = pd.crosstab(df['construct_WSA_LABEL'], df['construct_ACA_LABEL'], margins=True)
    wsa_present = [w for w in wsa_order if w in ct.index]
    aca_present = [a for a in aca_order if a in ct.columns]
    ct = ct.reindex(index=wsa_present + ['All'], columns=aca_present + ['All'], fill_value=0)
    print(ct.to_string())

    print(f"\n  {label} -- % Demand Increases (proposed) per WSA x ACA cell")
    inc_ct = pd.crosstab(df['construct_WSA_LABEL'], df['construct_ACA_LABEL'],
                         values=df['is_increase'], aggfunc='mean', margins=True)
    inc_ct = inc_ct.reindex(index=wsa_present + ['All'], columns=aca_present + ['All'], fill_value=0)
    print((inc_ct * 100).round(1).to_string())

    if label == "GOVERNED":
        print(f"\n  {label} -- % REJECTED per WSA x ACA cell")
        rej_ct = pd.crosstab(df['construct_WSA_LABEL'], df['construct_ACA_LABEL'],
                             values=df['is_rejected'], aggfunc='mean', margins=True)
        rej_ct = rej_ct.reindex(index=wsa_present + ['All'], columns=aca_present + ['All'], fill_value=0)
        print((rej_ct * 100).round(1).to_string())

# ═══════════════════════════════════════════════
# 2. HIGH-SCARCITY QUADRANT FOCUS
# ═══════════════════════════════════════════════
print("\n" + "=" * 80)
print("2. HIGH-SCARCITY QUADRANT (WSA in {H,VH}, ACA in {H,VH})")
print("=" * 80)

high_wsa = ['H', 'VH']
high_aca = ['H', 'VH']

gov_hh = gov[(gov['construct_WSA_LABEL'].isin(high_wsa)) & (gov['construct_ACA_LABEL'].isin(high_aca))]
ungov_hh = ungov[(ungov['construct_WSA_LABEL'].isin(high_wsa)) & (ungov['construct_ACA_LABEL'].isin(high_aca))]

print(f"\nGoverned high-scarcity decisions: {len(gov_hh)} ({len(gov_hh)/len(gov)*100:.1f}% of all)")
print(f"Ungoverned high-scarcity decisions: {len(ungov_hh)} ({len(ungov_hh)/len(ungov)*100:.1f}% of all)")

gov_hh_inc = gov_hh['is_increase'].mean() * 100 if len(gov_hh) > 0 else 0
ungov_hh_inc = ungov_hh['is_increase'].mean() * 100 if len(ungov_hh) > 0 else 0
print(f"\n% proposing increases in high-scarcity quadrant:")
print(f"  Governed:   {gov_hh_inc:.1f}%")
print(f"  Ungoverned: {ungov_hh_inc:.1f}%")

# Rejection details
rej_rate_hh = gov_hh['is_rejected'].mean() * 100 if len(gov_hh) > 0 else 0
print(f"\nGoverned high-scarcity rejection rate: {rej_rate_hh:.1f}%")
rejected_hh = gov_hh[gov_hh['is_rejected']]
print(f"  Total rejected: {len(rejected_hh)}")

# Which rules blocked
print(f"\n  Rules that blocked proposals (governed, high-scarcity quadrant):")
all_rules = []
for rules_str in gov_hh['failed_rules'].dropna():
    for r in str(rules_str).split('|'):
        r = r.strip()
        if r:
            all_rules.append(r)

rule_counts = Counter(all_rules)
for rule, count in rule_counts.most_common(15):
    pct = count / len(gov_hh) * 100
    print(f"    {rule}: {count} ({pct:.1f}%)")

# Final skill after governance
print(f"\n  Final skill distribution (governed, high-scarcity, REJECTED only):")
if len(rejected_hh) > 0:
    for sk in skill_order:
        n = (rejected_hh['final_skill'] == sk).sum()
        if n > 0:
            print(f"    {sk}: {n} ({n/len(rejected_hh)*100:.1f}%)")
    other = rejected_hh[~rejected_hh['final_skill'].isin(skill_order)]
    if len(other) > 0:
        print(f"    other/NaN: {len(other)}")

print(f"\n  Proposed -> Final mapping (governed, high-scarcity, REJECTED):")
if len(rejected_hh) > 0:
    mapping = rejected_hh.groupby(['proposed_skill', 'final_skill']).size().reset_index(name='count')
    print(mapping.to_string(index=False))

# Also show ALL governed HH (not just rejected)
print(f"\n  Proposed -> Final mapping (governed, high-scarcity, ALL):")
if len(gov_hh) > 0:
    mapping_all = gov_hh.groupby(['proposed_skill', 'final_skill']).size().reset_index(name='count')
    print(mapping_all.to_string(index=False))

# ═══════════════════════════════════════════════
# 3. NON-COMPLIANCE ARCHETYPES
# ═══════════════════════════════════════════════
print("\n" + "=" * 80)
print("3. NON-COMPLIANCE ARCHETYPES")
print("   (Governed, WSA in {H,VH}, ACA in {H,VH}, APPROVED, proposed increase)")
print("=" * 80)

noncompliant = gov_hh[(gov_hh['status'] == 'APPROVED') & (gov_hh['is_increase'])]
print(f"\nNon-compliant (approved increases in high-scarcity): {len(noncompliant)}")
if len(gov_hh) > 0:
    print(f"  As % of high-scarcity governed: {len(noncompliant)/len(gov_hh)*100:.1f}%")
print(f"  As % of all governed: {len(noncompliant)/len(gov)*100:.1f}%")

print(f"\n  By proposed skill:")
for sk in ['increase_small', 'increase_large']:
    n = (noncompliant['proposed_skill'] == sk).sum()
    print(f"    {sk}: {n}")

# Sample reasoning
print(f"\n  Sample reasoning texts (up to 5):")
sample = noncompliant.head(5)
for i, (_, row) in enumerate(sample.iterrows()):
    reasoning = str(row.get('reason_reasoning', ''))[:300]
    print(f"\n  [{i+1}] WSA={row['construct_WSA_LABEL']}, ACA={row['construct_ACA_LABEL']}, "
          f"skill={row['proposed_skill']}, year={row.get('year','?')}, seed={row['seed']}")
    print(f"      {reasoning}")

# What rules were triggered but not blocking?
print(f"\n  Rules triggered (but not blocking) for non-compliant decisions:")
nc_rules = []
for rules_str in noncompliant['failed_rules'].dropna():
    for r in str(rules_str).split('|'):
        r = r.strip()
        if r:
            nc_rules.append(r)
nc_rule_counts = Counter(nc_rules)
for rule, count in nc_rule_counts.most_common(10):
    print(f"    {rule}: {count}")

# Also check: what WSA/ACA sub-cells do non-compliant come from?
if len(noncompliant) > 0:
    print(f"\n  Non-compliant by WSA x ACA sub-cell:")
    nc_ct = noncompliant.groupby(['construct_WSA_LABEL', 'construct_ACA_LABEL']).size()
    for (wsa, aca), n in nc_ct.items():
        print(f"    WSA={wsa}, ACA={aca}: {n}")

# ═══════════════════════════════════════════════
# 4. ACTION DISTRIBUTION PER QUADRANT
# ═══════════════════════════════════════════════
print("\n" + "=" * 80)
print("4. ACTION DISTRIBUTION PER WSA x ACA QUADRANT")
print("=" * 80)

for label, df, skill_col in [("GOVERNED (proposed)", gov, 'proposed_skill'),
                              ("GOVERNED (final)", gov, 'final_skill'),
                              ("UNGOVERNED (proposed=final)", ungov, 'proposed_skill')]:
    print(f"\n{'_' * 60}")
    print(f"  {label}")
    print(f"{'_' * 60}")

    wsa_present = [w for w in wsa_order if w in df['construct_WSA_LABEL'].values]
    aca_present = [a for a in aca_order if a in df['construct_ACA_LABEL'].values]

    rows = []
    for wsa in wsa_present:
        for aca in aca_present:
            cell = df[(df['construct_WSA_LABEL'] == wsa) & (df['construct_ACA_LABEL'] == aca)]
            n = len(cell)
            if n == 0:
                continue
            row = {'WSA': wsa, 'ACA': aca, 'N': n}
            for sk in skill_order:
                row[sk] = round((cell[skill_col] == sk).sum() / n * 100, 1)
            rows.append(row)

    result = pd.DataFrame(rows)
    if len(result) > 0:
        print(result.to_string(index=False))

# ═══════════════════════════════════════════════
# 5. TEMPORAL PATTERNS
# ═══════════════════════════════════════════════
print("\n" + "=" * 80)
print("5. TEMPORAL PATTERNS -- High-Scarcity Non-Compliance by Year")
print("=" * 80)

if 'year' in gov.columns:
    print(f"\nYear range: {gov['year'].min()} to {gov['year'].max()}")

    year_all = gov_hh.groupby('year').size()
    year_inc_proposed = gov_hh[gov_hh['is_increase']].groupby('year').size()
    year_inc_approved = noncompliant.groupby('year').size()
    year_rejected = rejected_hh.groupby('year').size() if len(rejected_hh) > 0 else pd.Series(dtype=int)

    years = sorted(gov_hh['year'].unique())
    print(f"\n{'Year':>6} {'N_HH':>6} {'Inc_Prop':>10} {'Inc_Appr':>10} {'Rejected':>10} {'%Inc_Prop':>10} {'%Rej':>10}")
    for y in years:
        n = year_all.get(y, 0)
        ip = year_inc_proposed.get(y, 0)
        ia = year_inc_approved.get(y, 0)
        rej = year_rejected.get(y, 0)
        pct_inc = ip / n * 100 if n > 0 else 0
        pct_rej = rej / n * 100 if n > 0 else 0
        print(f"{y:>6} {n:>6} {ip:>10} {ia:>10} {rej:>10} {pct_inc:>9.1f}% {pct_rej:>9.1f}%")

    # Ungoverned comparison
    if len(ungov_hh) > 0:
        print(f"\n  Ungoverned high-scarcity % proposing increases by year:")
        print(f"  {'Year':>6} {'N':>6} {'%Inc':>8}")
        for y in sorted(ungov_hh['year'].unique()):
            cell = ungov_hh[ungov_hh['year'] == y]
            print(f"  {y:>6} {len(cell):>6} {cell['is_increase'].mean()*100:>7.1f}%")

    # Also: overall temporal pattern for ALL governed decisions (not just HH)
    print(f"\n  Overall governed rejection rate by year:")
    print(f"  {'Year':>6} {'N':>6} {'%Rej':>8} {'%Inc_prop':>10} {'%Inc_final':>11}")
    for y in sorted(gov['year'].unique()):
        cell = gov[gov['year'] == y]
        rej_pct = cell['is_rejected'].mean() * 100
        inc_prop = cell['is_increase'].mean() * 100
        inc_final = cell['final_skill'].isin(['increase_small', 'increase_large']).mean() * 100
        print(f"  {y:>6} {len(cell):>6} {rej_pct:>7.1f}% {inc_prop:>9.1f}% {inc_final:>10.1f}%")
else:
    print("No 'year' column found")

# ═══════════════════════════════════════════════
# SUMMARY STATISTICS
# ═══════════════════════════════════════════════
print("\n" + "=" * 80)
print("SUMMARY FOR PAPER")
print("=" * 80)
print(f"\nTotal governed decisions: {len(gov)}")
print(f"Total ungoverned decisions: {len(ungov)}")
print(f"Overall rejection rate (governed): {gov['is_rejected'].mean()*100:.1f}%")
print(f"Overall % increases proposed (governed): {gov['is_increase'].mean()*100:.1f}%")
print(f"Overall % increases proposed (ungoverned): {ungov['is_increase'].mean()*100:.1f}%")

print(f"\nHigh-scarcity quadrant (WSA in {{H,VH}}, ACA in {{H,VH}}):")
print(f"  Governed: {len(gov_hh)} decisions, {gov_hh_inc:.1f}% propose increase, {rej_rate_hh:.1f}% rejected")
print(f"  Ungoverned: {len(ungov_hh)} decisions, {ungov_hh_inc:.1f}% propose increase")
print(f"  Non-compliant (approved increases): {len(noncompliant)}")
if len(gov_hh) > 0:
    print(f"    ({len(noncompliant)/len(gov_hh)*100:.1f}% of HH)")

gov_hh_final_inc = gov_hh['final_skill'].isin(['increase_small', 'increase_large']).mean() * 100 if len(gov_hh) > 0 else 0
print(f"\nGovernance effect on increase proposals in high-scarcity quadrant:")
print(f"  Ungoverned: {ungov_hh_inc:.1f}%")
print(f"  Governed (proposed): {gov_hh_inc:.1f}%")
print(f"  Governed (final/executed): {gov_hh_final_inc:.1f}%")
print(f"  Reduction from ungov to gov-final: {ungov_hh_inc - gov_hh_final_inc:.1f} pp")

# BRI
high_wsa_gov = gov[gov['construct_WSA_LABEL'].isin(high_wsa)]
high_wsa_ungov = ungov[ungov['construct_WSA_LABEL'].isin(high_wsa)]
gov_bri = 1 - high_wsa_gov['is_increase'].mean() if len(high_wsa_gov) > 0 else 0
ungov_bri = 1 - high_wsa_ungov['is_increase'].mean() if len(high_wsa_ungov) > 0 else 0
print(f"\nBRI (high-WSA non-increase rate):")
print(f"  Governed BRI (proposed): {gov_bri:.3f}")
print(f"  Ungoverned BRI: {ungov_bri:.3f}")

# BRI on final skill
gov_bri_final = 1 - high_wsa_gov['final_skill'].isin(['increase_small', 'increase_large']).mean()
print(f"  Governed BRI (final): {gov_bri_final:.3f}")

# Broader context: what fraction of decisions are in each WSA level?
print(f"\n  Decision count by WSA level:")
print(f"  {'WSA':>4} {'Gov':>8} {'Ungov':>8}")
for wsa in wsa_order:
    ng = (gov['construct_WSA_LABEL'] == wsa).sum()
    nu = (ungov['construct_WSA_LABEL'] == wsa).sum()
    if ng > 0 or nu > 0:
        print(f"  {wsa:>4} {ng:>8} {nu:>8}")
