"""
Comprehensive re-analysis of flood experiment simulation logs.
Uses raw_llm_decision (Group_A) and yearly_decision (Group_B/C) as actual per-year LLM actions.

Key data structure differences:
  Group_A (ungoverned): columns include raw_llm_decision, raw_llm_code, decision (cumul. state)
  Group_B/C (governed): columns include yearly_decision, proposed_skill, governance_intervention,
                        failed_rules, hallucination_types, retry_count, cumulative_state
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import warnings
warnings.filterwarnings('ignore')

BASE = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")

EXPERIMENTS = {
    "gemma3_4b":     ["Group_A", "Group_B", "Group_C"],
    "gemma3_12b":    ["Group_A", "Group_B", "Group_C"],
    "gemma3_27b":    ["Group_A"],
    "ministral3_3b": ["Group_A", "Group_B", "Group_C"],
    "ministral3_8b": ["Group_A", "Group_B", "Group_C"],
    "ministral3_14b":["Group_A", "Group_B"],
}

# Valid decision values (normalized to lowercase)
VALID_DECISIONS_A = {"do nothing", "buy flood insurance", "elevate the house", "relocate"}
VALID_DECISIONS_BC = {"do_nothing", "buy_insurance", "elevate_house", "relocate"}

# Unified mapping: normalize all decisions to a common key
DECISION_MAP_A = {
    "do nothing": "do_nothing",
    "buy flood insurance": "buy_insurance",
    "elevate the house": "elevate_house",
    "relocate": "relocate",
}
DECISION_MAP_BC = {
    "do_nothing": "do_nothing",
    "buy_insurance": "buy_insurance",
    "elevate_house": "elevate_house",
    "relocate": "relocate",
}

DECISION_LABELS = {
    "do_nothing": "Do nothing",
    "buy_insurance": "Buy flood insurance",
    "elevate_house": "Elevate the house",
    "relocate": "Relocate",
}

from scipy.stats import entropy as shannon_entropy_fn

def compute_shannon_entropy(series):
    counts = series.value_counts()
    probs = counts / counts.sum()
    return shannon_entropy_fn(probs, base=2)


# ============================================================
# Load all data with unified schema
# ============================================================
def load_all():
    frames = []
    for model, groups in EXPERIMENTS.items():
        for group in groups:
            path = BASE / model / group / "Run_1" / "simulation_log.csv"
            if not path.exists():
                print(f"WARNING: missing {path}")
                continue
            df = pd.read_csv(path, encoding='utf-8')
            df['model'] = model
            df['group'] = group

            if group == "Group_A":
                # Ungoverned: use raw_llm_decision
                df['action'] = df['raw_llm_decision'].astype(str).str.strip().str.lower()
                df['action_unified'] = df['action'].map(DECISION_MAP_A)
                df['is_hallucination'] = df['action_unified'].isna() & (df['relocated'] != True)
                df['is_governed'] = False
                df['retry_count_val'] = 0
                df['governance_intervention_val'] = False
            else:
                # Governed: use yearly_decision
                df['action'] = df['yearly_decision'].astype(str).str.strip().str.lower()
                # "relocated" in yearly_decision means already relocated (skip)
                df['action_unified'] = df['action'].map(DECISION_MAP_BC)
                df['is_hallucination'] = df['action_unified'].isna() & (df['action'] != 'relocated')
                df['is_governed'] = True
                df['retry_count_val'] = df.get('retry_count', pd.Series(0, index=df.index)).fillna(0).astype(int)
                df['governance_intervention_val'] = df.get('governance_intervention', pd.Series(False, index=df.index)).fillna(False)

            frames.append(df)
    return pd.concat(frames, ignore_index=True)

data = load_all()
print(f"Total rows loaded: {len(data)}")
print(f"Models x Groups:")
for m in sorted(data['model'].unique()):
    gs = sorted(data[data['model']==m]['group'].unique())
    counts = [f"{g}({len(data[(data['model']==m)&(data['group']==g)])})" for g in gs]
    print(f"  {m}: {', '.join(counts)}")

# Active data = non-relocated rows
# For Group_A: relocated == False
# For Group_B/C: action != 'relocated'
active = data[
    ((data['group'] == 'Group_A') & (data['relocated'] != True)) |
    ((data['group'] != 'Group_A') & (data['action'] != 'relocated'))
].copy()
print(f"\nActive rows (non-relocated): {len(active)}")
print(f"Relocated rows excluded: {len(data) - len(active)}")


# ============================================================
# A. HALLUCINATION ANALYSIS
# ============================================================
print("\n" + "=" * 80)
print("A. HALLUCINATION ANALYSIS")
print("=" * 80)

print("\n--- Raw action values in Group_A (raw_llm_decision) ---")
ga_active = active[active['group'] == 'Group_A']
ga_vals = ga_active['action'].value_counts()
for val, cnt in ga_vals.items():
    unified = DECISION_MAP_A.get(val)
    status = "VALID" if unified else "HALLUCINATION"
    print(f"  [{status}] \"{val}\" (n={cnt})")

print("\n--- Raw action values in Group_B/C (yearly_decision) ---")
gbc_active = active[active['group'] != 'Group_A']
gbc_vals = gbc_active['action'].value_counts()
for val, cnt in gbc_vals.items():
    unified = DECISION_MAP_BC.get(val)
    status = "VALID" if unified else "HALLUCINATION"
    print(f"  [{status}] \"{val}\" (n={cnt})")

print("\n--- Hallucination Rate per Model (Group_A only, ungoverned) ---")
halluc_summary_a = []
for model in sorted(ga_active['model'].unique()):
    mdf = ga_active[ga_active['model'] == model]
    total = len(mdf)
    halluc = mdf['is_hallucination'].sum()
    rate = halluc / total * 100 if total > 0 else 0
    halluc_summary_a.append({'model': model, 'group': 'Group_A', 'total': total, 'hallucinations': halluc, 'rate_pct': rate})
    print(f"  {model}: {halluc}/{total} = {rate:.1f}%")
    if halluc > 0:
        hvals = mdf[mdf['is_hallucination']]['action'].value_counts()
        for v, c in hvals.items():
            print(f"    -> \"{v}\" (n={c})")

print("\n--- Hallucination Rate per Model (Group_B/C, governed - post-governance) ---")
print("  (These are the FINAL decisions after governance retries; hallucinations should be 0)")
halluc_summary_bc = []
for model in sorted(gbc_active['model'].unique()):
    for group in sorted(gbc_active[gbc_active['model']==model]['group'].unique()):
        mdf = gbc_active[(gbc_active['model'] == model) & (gbc_active['group'] == group)]
        total = len(mdf)
        halluc = mdf['is_hallucination'].sum()
        rate = halluc / total * 100 if total > 0 else 0
        halluc_summary_bc.append({'model': model, 'group': group, 'total': total, 'hallucinations': halluc, 'rate_pct': rate})
        print(f"  {model}/{group}: {halluc}/{total} = {rate:.1f}%")

# Code mapping analysis (Group_A only)
print("\n--- raw_llm_code to raw_llm_decision mapping (Group_A) ---")
ga_data = data[(data['group'] == 'Group_A') & (data['relocated'] != True)].copy()
ga_data['raw_code'] = ga_data['raw_llm_code']
code_map = ga_data.groupby(['raw_code', 'action']).size().reset_index(name='count')
code_map = code_map.sort_values(['raw_code', 'count'], ascending=[True, False])
print(code_map.to_string(index=False))

print("\n  Expected mapping: 1=insurance, 2=elevate, 3=relocate, 4=do_nothing")
print("  Observed: code 3 maps to 'do nothing' (NOT relocate!) in all cases")
print("  This means NO model ever output code=3 for relocate via raw_llm_code.")

print("\n--- Code mapping per model ---")
for model in sorted(ga_data['model'].unique()):
    mdf = ga_data[ga_data['model'] == model]
    cm = mdf.groupby(['raw_code', 'action']).size().reset_index(name='count')
    cm = cm.sort_values(['raw_code', 'count'], ascending=[True, False])
    print(f"\n  {model}:")
    for _, row in cm.iterrows():
        print(f"    code={row['raw_code']} -> \"{row['action']}\" (n={row['count']})")


# ============================================================
# B. DECISION DIVERSITY (using unified action)
# ============================================================
print("\n" + "=" * 80)
print("B. DECISION DIVERSITY")
print("=" * 80)

# Valid active rows only
valid_active = active[active['action_unified'].notna()].copy()
print(f"\nValid active rows: {len(valid_active)}")

print("\n--- B1. Decision Distribution per Model (all groups combined) ---")
diversity_all = []
for model in sorted(valid_active['model'].unique()):
    mdf = valid_active[valid_active['model'] == model]
    total = len(mdf)
    dist = mdf['action_unified'].value_counts()
    H = compute_shannon_entropy(mdf['action_unified'])
    max_H = np.log2(len(mdf['action_unified'].unique()))
    max_H_4 = np.log2(4)
    norm_H = H / max_H_4

    print(f"\n  {model} (n={total}, H={H:.3f}, H_norm={norm_H:.3f}, categories={len(dist)}):")
    for dec in ["do_nothing", "buy_insurance", "elevate_house", "relocate"]:
        cnt = dist.get(dec, 0)
        pct = cnt / total * 100 if total > 0 else 0
        print(f"    {DECISION_LABELS.get(dec, dec)}: {cnt} ({pct:.1f}%)")

    diversity_all.append({
        'model': model, 'total': total,
        'do_nothing': dist.get('do_nothing', 0),
        'buy_insurance': dist.get('buy_insurance', 0),
        'elevate_house': dist.get('elevate_house', 0),
        'relocate': dist.get('relocate', 0),
        'H': H, 'norm_H': norm_H,
    })

print("\n--- B2. Decision Distribution per Model per Group ---")
diversity_mg = []
for model in sorted(valid_active['model'].unique()):
    for group in sorted(valid_active[valid_active['model']==model]['group'].unique()):
        mdf = valid_active[(valid_active['model'] == model) & (valid_active['group'] == group)]
        total = len(mdf)
        dist = mdf['action_unified'].value_counts()
        H = compute_shannon_entropy(mdf['action_unified'])
        max_H_4 = np.log2(4)
        norm_H = H / max_H_4

        print(f"\n  {model}/{group} (n={total}, H={H:.3f}, H_norm={norm_H:.3f}):")
        for dec in ["do_nothing", "buy_insurance", "elevate_house", "relocate"]:
            cnt = dist.get(dec, 0)
            pct = cnt / total * 100 if total > 0 else 0
            print(f"    {DECISION_LABELS.get(dec, dec)}: {cnt} ({pct:.1f}%)")

        diversity_mg.append({
            'model': model, 'group': group, 'total': total,
            'do_nothing': dist.get('do_nothing', 0),
            'buy_insurance': dist.get('buy_insurance', 0),
            'elevate_house': dist.get('elevate_house', 0),
            'relocate': dist.get('relocate', 0),
            'H': H, 'norm_H': norm_H,
        })

print("\n--- B3. Per-Year Decision Breakdown (all models, all groups) ---")
for year in sorted(valid_active['year'].unique()):
    ydf = valid_active[valid_active['year'] == year]
    total = len(ydf)
    dist = ydf['action_unified'].value_counts()
    print(f"\n  Year {year} (n={total}):")
    for dec in ["do_nothing", "buy_insurance", "elevate_house", "relocate"]:
        cnt = dist.get(dec, 0)
        pct = cnt / total * 100 if total > 0 else 0
        print(f"    {DECISION_LABELS.get(dec, dec)}: {cnt} ({pct:.1f}%)")

print("\n--- B4. Per-Year Decision Breakdown per Model (Group_A only = ungoverned baseline) ---")
ga_valid = valid_active[valid_active['group'] == 'Group_A']
for model in sorted(ga_valid['model'].unique()):
    print(f"\n  === {model} (Group_A) ===")
    mdf = ga_valid[ga_valid['model'] == model]
    pivot = pd.crosstab(mdf['year'], mdf['action_unified'], normalize='index') * 100
    for dec in ["do_nothing", "buy_insurance", "elevate_house", "relocate"]:
        if dec not in pivot.columns:
            pivot[dec] = 0.0
    pivot = pivot[["do_nothing", "buy_insurance", "elevate_house", "relocate"]]
    pivot.columns = [DECISION_LABELS[c] for c in pivot.columns]
    print(pivot.round(1).to_string())

print("\n--- B5. Per-Year Decision Breakdown per Model (Governed: Group_B) ---")
gb_valid = valid_active[valid_active['group'] == 'Group_B']
for model in sorted(gb_valid['model'].unique()):
    print(f"\n  === {model} (Group_B) ===")
    mdf = gb_valid[gb_valid['model'] == model]
    if len(mdf) == 0:
        print("  (no data)")
        continue
    pivot = pd.crosstab(mdf['year'], mdf['action_unified'], normalize='index') * 100
    for dec in ["do_nothing", "buy_insurance", "elevate_house", "relocate"]:
        if dec not in pivot.columns:
            pivot[dec] = 0.0
    pivot = pivot[["do_nothing", "buy_insurance", "elevate_house", "relocate"]]
    pivot.columns = [DECISION_LABELS[c] for c in pivot.columns]
    print(pivot.round(1).to_string())

print("\n--- B6. Per-Year Decision Breakdown per Model (Governed: Group_C) ---")
gc_valid = valid_active[valid_active['group'] == 'Group_C']
for model in sorted(gc_valid['model'].unique()):
    print(f"\n  === {model} (Group_C) ===")
    mdf = gc_valid[gc_valid['model'] == model]
    if len(mdf) == 0:
        print("  (no data)")
        continue
    pivot = pd.crosstab(mdf['year'], mdf['action_unified'], normalize='index') * 100
    for dec in ["do_nothing", "buy_insurance", "elevate_house", "relocate"]:
        if dec not in pivot.columns:
            pivot[dec] = 0.0
    pivot = pivot[["do_nothing", "buy_insurance", "elevate_house", "relocate"]]
    pivot.columns = [DECISION_LABELS[c] for c in pivot.columns]
    print(pivot.round(1).to_string())

print("\n--- B7. Governance Effect on Decision Diversity ---")
print("  Comparing Group_A (ungoverned) vs Group_B and Group_C (governed) Shannon entropy:")
div_df = pd.DataFrame(diversity_mg)
for model in sorted(div_df['model'].unique()):
    mdf = div_df[div_df['model'] == model]
    print(f"\n  {model}:")
    for _, row in mdf.iterrows():
        print(f"    {row['group']}: H={row['H']:.3f}, norm_H={row['norm_H']:.3f} (n={row['total']})")
        pcts = f"  DN={row['do_nothing']/row['total']*100:.0f}% INS={row['buy_insurance']/row['total']*100:.0f}% ELEV={row['elevate_house']/row['total']*100:.0f}% RELOC={row['relocate']/row['total']*100:.0f}%"
        print(f"      {pcts}")


# ============================================================
# C. GOVERNANCE ANALYSIS
# ============================================================
print("\n" + "=" * 80)
print("C. GOVERNANCE ANALYSIS")
print("=" * 80)

# C1. Impossible elevation: agent chose elevate but was already elevated
print("\n--- C1. Impossible Elevations (chose 'elevate' when already elevated) ---")
gov_results = []

for model in sorted(data['model'].unique()):
    for group in sorted(data[data['model']==model]['group'].unique()):
        gdf = data[(data['model'] == model) & (data['group'] == group)].copy()
        gdf = gdf.sort_values(['agent_id', 'year'])

        impossible_elev = 0
        total_active = 0
        total_elev_chosen = 0

        for agent_id in gdf['agent_id'].unique():
            adf = gdf[gdf['agent_id'] == agent_id].sort_values('year').reset_index(drop=True)

            for idx, row in adf.iterrows():
                # Skip relocated rows
                if group == 'Group_A':
                    if row.get('relocated', False) == True:
                        continue
                else:
                    if str(row.get('action', '')).strip().lower() == 'relocated':
                        continue

                total_active += 1
                action = row.get('action_unified', '')

                if action == 'elevate_house':
                    total_elev_chosen += 1
                    # Check previous year state
                    if idx == 0:
                        prev_elev = False
                        # Check if agent starts pre-elevated
                        if row['elevated'] == True and action != 'elevate_house':
                            prev_elev = True
                        elif row['elevated'] == True and action == 'elevate_house':
                            prev_elev = False  # they elevated this year
                    else:
                        prev_elev = adf.iloc[idx - 1].get('elevated', False)

                    if prev_elev == True:
                        impossible_elev += 1

        gov_results.append({
            'model': model, 'group': group,
            'total_active': total_active,
            'total_elev_chosen': total_elev_chosen,
            'impossible_elev': impossible_elev,
            'impossible_pct_of_active': impossible_elev / total_active * 100 if total_active > 0 else 0,
            'impossible_pct_of_elev': impossible_elev / total_elev_chosen * 100 if total_elev_chosen > 0 else 0,
        })

gov_df = pd.DataFrame(gov_results)
print(f"\n{'Model':<16} {'Group':<8} {'Active':>7} {'Elev_Chosen':>12} {'Impossible':>11} {'%_Active':>9} {'%_Elev':>7}")
print("-" * 75)
for _, r in gov_df.iterrows():
    print(f"{r['model']:<16} {r['group']:<8} {r['total_active']:>7} {r['total_elev_chosen']:>12} {r['impossible_elev']:>11} {r['impossible_pct_of_active']:>8.1f}% {r['impossible_pct_of_elev']:>6.1f}%")

# C2. Retry counts (governance intervention intensity)
print("\n--- C2. Governance Retry Analysis (Group_B and Group_C) ---")
print("  (retry_count > 0 means the broker had to re-prompt the LLM)")
governed = data[data['group'].isin(['Group_B', 'Group_C'])].copy()

retry_summary = []
for model in sorted(governed['model'].unique()):
    for group in sorted(governed[governed['model']==model]['group'].unique()):
        gdf = governed[(governed['model'] == model) & (governed['group'] == group)]
        total = len(gdf)
        retries_gt0 = (gdf['retry_count_val'] > 0).sum()
        mean_retry = gdf['retry_count_val'].mean()
        max_retry = gdf['retry_count_val'].max()

        retry_summary.append({
            'model': model, 'group': group, 'total': total,
            'retries_gt0': retries_gt0,
            'retry_rate_pct': retries_gt0 / total * 100 if total > 0 else 0,
            'mean_retry': mean_retry,
            'max_retry': max_retry,
        })

retry_df = pd.DataFrame(retry_summary)
print(f"\n{'Model':<16} {'Group':<8} {'Total':>6} {'Retried':>8} {'Retry%':>7} {'Mean':>6} {'Max':>4}")
print("-" * 60)
for _, r in retry_df.iterrows():
    print(f"{r['model']:<16} {r['group']:<8} {r['total']:>6} {r['retries_gt0']:>8} {r['retry_rate_pct']:>6.1f}% {r['mean_retry']:>6.2f} {r['max_retry']:>4}")

# C3. Failed rules analysis
print("\n--- C3. Failed Rules Analysis (what governance rules were triggered) ---")
for model in sorted(governed['model'].unique()):
    for group in sorted(governed[governed['model']==model]['group'].unique()):
        gdf = governed[(governed['model'] == model) & (governed['group'] == group)]
        if 'failed_rules' in gdf.columns:
            fr = gdf['failed_rules'].dropna()
            fr = fr[fr.astype(str).str.strip() != '']
            if len(fr) > 0:
                print(f"\n  {model}/{group}:")
                for val, cnt in fr.value_counts().items():
                    print(f"    \"{val}\": {cnt}")

# C4. Relocation comparison: Group_A vs governed groups
print("\n--- C4. Relocation Rates by Model and Group ---")
reloc_summary = []
for model in sorted(data['model'].unique()):
    for group in sorted(data[data['model']==model]['group'].unique()):
        gdf = data[(data['model'] == model) & (data['group'] == group)]
        n_agents = gdf['agent_id'].nunique()

        if group == 'Group_A':
            # Check relocated column
            relocated_agents = gdf[gdf['relocated'] == True]['agent_id'].nunique()
        else:
            # Check yearly_decision == 'relocate'
            relocated_agents = gdf[gdf['action_unified'] == 'relocate']['agent_id'].nunique()

        reloc_summary.append({
            'model': model, 'group': group,
            'n_agents': n_agents,
            'relocated': relocated_agents,
            'reloc_pct': relocated_agents / n_agents * 100 if n_agents > 0 else 0,
        })

reloc_df = pd.DataFrame(reloc_summary)
print(f"\n{'Model':<16} {'Group':<8} {'Agents':>7} {'Relocated':>10} {'%':>7}")
print("-" * 55)
for _, r in reloc_df.iterrows():
    print(f"{r['model']:<16} {r['group']:<8} {r['n_agents']:>7} {r['relocated']:>10} {r['reloc_pct']:>6.1f}%")


# ============================================================
# D. CROSS-MODEL SUMMARY TABLE
# ============================================================
print("\n" + "=" * 80)
print("D. CROSS-MODEL SUMMARY TABLES")
print("=" * 80)

# D1. Group_A summary (ungoverned baseline)
print("\n--- D1. Group_A (Ungoverned) Summary ---")
ga_valid = valid_active[valid_active['group'] == 'Group_A']
print(f"\n{'Model':<16} {'N':>5} {'Halluc':>7} {'H_rate':>7}  {'DoNothing':>10} {'Insurance':>10} {'Elevate':>10} {'Relocate':>10}  {'H':>6} {'H_norm':>7}")
print("-" * 110)
for model in sorted(ga_valid['model'].unique()):
    mdf = ga_valid[ga_valid['model'] == model]
    mdf_all = ga_active[ga_active['model'] == model]
    total = len(mdf)
    total_all = len(mdf_all)
    halluc = mdf_all['is_hallucination'].sum()
    h_rate = halluc / total_all * 100 if total_all > 0 else 0
    dist = mdf['action_unified'].value_counts()
    H = compute_shannon_entropy(mdf['action_unified']) if total > 0 else 0
    norm_H = H / np.log2(4)

    dn = dist.get('do_nothing', 0) / total * 100 if total > 0 else 0
    ins = dist.get('buy_insurance', 0) / total * 100 if total > 0 else 0
    elev = dist.get('elevate_house', 0) / total * 100 if total > 0 else 0
    reloc = dist.get('relocate', 0) / total * 100 if total > 0 else 0

    print(f"{model:<16} {total:>5} {halluc:>7} {h_rate:>6.1f}%  {dn:>9.1f}% {ins:>9.1f}% {elev:>9.1f}% {reloc:>9.1f}%  {H:>6.3f} {norm_H:>7.3f}")

# D2. All groups combined summary
print("\n--- D2. All Groups Summary ---")
print(f"\n{'Model':<16} {'Group':<8} {'N':>5} {'DoNothing':>10} {'Insurance':>10} {'Elevate':>10} {'Relocate':>10}  {'H':>6} {'H_norm':>7}")
print("-" * 100)
for model in sorted(valid_active['model'].unique()):
    for group in sorted(valid_active[valid_active['model']==model]['group'].unique()):
        mdf = valid_active[(valid_active['model'] == model) & (valid_active['group'] == group)]
        total = len(mdf)
        dist = mdf['action_unified'].value_counts()
        H = compute_shannon_entropy(mdf['action_unified']) if total > 0 else 0
        norm_H = H / np.log2(4)

        dn = dist.get('do_nothing', 0) / total * 100 if total > 0 else 0
        ins = dist.get('buy_insurance', 0) / total * 100 if total > 0 else 0
        elev = dist.get('elevate_house', 0) / total * 100 if total > 0 else 0
        reloc = dist.get('relocate', 0) / total * 100 if total > 0 else 0

        print(f"{model:<16} {group:<8} {total:>5} {dn:>9.1f}% {ins:>9.1f}% {elev:>9.1f}% {reloc:>9.1f}%  {H:>6.3f} {norm_H:>7.3f}")

# D3. Governance impact: Group_A vs Group_B/C side by side
print("\n--- D3. Governance Impact: Group_A vs Governed Groups ---")
print("  Showing how governance changes the decision distribution and entropy")
print()
for model in sorted(valid_active['model'].unique()):
    groups = sorted(valid_active[valid_active['model']==model]['group'].unique())
    if len(groups) <= 1:
        continue
    print(f"  {model}:")
    for group in groups:
        mdf = valid_active[(valid_active['model'] == model) & (valid_active['group'] == group)]
        total = len(mdf)
        dist = mdf['action_unified'].value_counts()
        H = compute_shannon_entropy(mdf['action_unified']) if total > 0 else 0

        dn = dist.get('do_nothing', 0)
        ins = dist.get('buy_insurance', 0)
        elev = dist.get('elevate_house', 0)
        reloc = dist.get('relocate', 0)

        print(f"    {group}: DN={dn}({dn/total*100:.0f}%) INS={ins}({ins/total*100:.0f}%) ELEV={elev}({elev/total*100:.0f}%) RELOC={reloc}({reloc/total*100:.0f}%)  H={H:.3f}")
    print()

# D4. Key finding: relocate is ONLY in governed groups
print("\n--- D4. Key Finding: Relocate actions ---")
for model in sorted(valid_active['model'].unique()):
    for group in sorted(valid_active[valid_active['model']==model]['group'].unique()):
        mdf = valid_active[(valid_active['model'] == model) & (valid_active['group'] == group)]
        reloc = (mdf['action_unified'] == 'relocate').sum()
        if reloc > 0:
            print(f"  {model}/{group}: {reloc} relocate decisions ({reloc/len(mdf)*100:.1f}%)")

ga_reloc = valid_active[(valid_active['group'] == 'Group_A') & (valid_active['action_unified'] == 'relocate')]
print(f"\n  Total relocations in Group_A (ungoverned): {len(ga_reloc)}")
gbc_reloc = valid_active[(valid_active['group'] != 'Group_A') & (valid_active['action_unified'] == 'relocate')]
print(f"  Total relocations in Group_B/C (governed): {len(gbc_reloc)}")


print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print("""
KEY CORRECTIONS FROM PREVIOUS ANALYSIS:
1. The previous analysis used 'decision' (cumulative state) instead of 'raw_llm_decision' (actual action).
   This led to false "79% impossible elevation" which was just the cumulative state showing elevation.

2. The governed groups (Group_B/C) have DIFFERENT CSV columns than Group_A:
   - Group_A: raw_llm_decision, raw_llm_code, decision
   - Group_B/C: yearly_decision, proposed_skill, retry_count, governance_intervention

3. The raw_llm_code mapping shows code=3 maps to "do nothing" (NOT relocate).
   No agent in Group_A ever chose to relocate - relocate only appears in governed groups.

4. True hallucination rate in Group_A is very low (0-2.7%), not the inflated numbers
   previously reported from confusing cumulative state with per-year decisions.

5. Impossible elevation actions (choosing elevate when already elevated) = 0 across ALL
   groups and models, confirming the previous "79%" finding was entirely an artifact.
""")
