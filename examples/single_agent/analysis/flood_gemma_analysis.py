"""
Comprehensive analysis of Gemma 3 flood experiment simulation logs.
Handles two CSV schemas: old (decision col) and new (cumulative_state + yearly_decision).
"""
import pandas as pd
import numpy as np
import json
import os
from collections import Counter

BASE = r"c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/results/JOH_FINAL"

RUNS = {
    "gemma3_4b_A":  f"{BASE}/gemma3_4b/Group_A/Run_1/simulation_log.csv",
    "gemma3_4b_B":  f"{BASE}/gemma3_4b/Group_B/Run_1/simulation_log.csv",
    "gemma3_4b_C":  f"{BASE}/gemma3_4b/Group_C/Run_1/simulation_log.csv",
    "gemma3_12b_A": f"{BASE}/gemma3_12b/Group_A/Run_1/simulation_log.csv",
    "gemma3_12b_B": f"{BASE}/gemma3_12b/Group_B/Run_1/simulation_log.csv",
    "gemma3_12b_C": f"{BASE}/gemma3_12b/Group_C/Run_1/simulation_log.csv",
    "gemma3_27b_A": f"{BASE}/gemma3_27b/Group_A/Run_1/simulation_log.csv",
    "gemma3_27b_B": f"{BASE}/gemma3_27b/Group_B/Run_1/simulation_log.csv",
}

CANONICAL_ACTIONS = ["Do Nothing", "Elevate", "Insure", "Elevate + Insure", "Relocate"]

def normalize_action(action_str):
    """Normalize action names to canonical forms."""
    if pd.isna(action_str):
        return "Do Nothing"
    s = str(action_str).strip().lower()
    # yearly_decision style: do_nothing, elevate_house, buy_insurance, elevate_and_insure, relocate
    if s in ("do_nothing", "do nothing", "nothing"):
        return "Do Nothing"
    elif s in ("elevate_and_insure", "both flood insurance and house elevation",
               "both house elevation and flood insurance"):
        return "Elevate + Insure"
    elif s in ("elevate_house", "only house elevation") or ("elevat" in s and "insur" not in s):
        return "Elevate"
    elif s in ("buy_insurance", "only flood insurance") or ("insur" in s and "elevat" not in s):
        return "Insure"
    elif s in ("relocate",) or "reloc" in s:
        return "Relocate"
    # Fallback: try broader matching
    elif "nothing" in s:
        return "Do Nothing"
    elif "elevat" in s and "insur" in s:
        return "Elevate + Insure"
    elif "elevat" in s:
        return "Elevate"
    elif "insur" in s:
        return "Insure"
    else:
        return action_str.strip()

def normalize_cumulative_state(state_str):
    """Normalize cumulative_state labels."""
    if pd.isna(state_str):
        return "Do Nothing"
    s = str(state_str).strip().lower()
    if "nothing" in s or s == "do nothing":
        return "Do Nothing"
    elif "elevat" in s and "insur" in s:
        return "Elevate + Insure"
    elif "elevat" in s:
        return "Elevate"
    elif "insur" in s:
        return "Insure"
    elif "reloc" in s:
        return "Relocate"
    else:
        return state_str.strip()

def shannon_entropy(counts, n_categories=5):
    """Compute normalized Shannon entropy."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    probs = [c / total for c in counts.values() if c > 0]
    H = -sum(p * np.log2(p) for p in probs)
    H_max = np.log2(n_categories)
    return H / H_max if H_max > 0 else 0.0

def analyze_run(name, path):
    """Full analysis of one simulation run."""
    print(f"\n{'='*70}")
    print(f"  ANALYZING: {name}")
    print(f"{'='*70}")

    df = pd.read_csv(path, encoding='utf-8-sig')

    # Detect schema
    if 'decision' in df.columns:
        schema = 'old'
        df['action'] = df['decision'].apply(normalize_action)
        trust_ins_col = 'trust_in_insurance'
        trust_neigh_col = 'trust_in_neighbors'
    elif 'yearly_decision' in df.columns:
        schema = 'new'
        df['action'] = df['yearly_decision'].apply(normalize_action)
        trust_ins_col = 'trust_insurance'
        trust_neigh_col = 'trust_neighbors'
    else:
        print(f"  ERROR: Unknown schema. Columns: {list(df.columns)}")
        return None

    print(f"  Schema: {schema}, Columns: {list(df.columns)[:8]}...")

    n_agents = df['agent_id'].nunique()
    years = sorted(df['year'].unique())
    n_years = len(years)

    print(f"  Agents: {n_agents}, Years: {n_years} ({min(years)}-{max(years)})")

    # -------------------------------------------------------
    # 1. Per-year action distribution
    # -------------------------------------------------------
    print(f"\n  --- Per-Year Action Distribution ---")
    action_by_year = {}
    for yr in years:
        yr_df = df[df['year'] == yr]
        counts = yr_df['action'].value_counts().to_dict()
        action_by_year[yr] = counts

    all_actions = sorted(df['action'].unique())
    header_str = f"  {'Year':>4}"
    for a in CANONICAL_ACTIONS:
        if a in all_actions:
            header_str += f"  {a:>16}"
    print(header_str)

    for yr in years:
        row_str = f"  {yr:>4}"
        for a in CANONICAL_ACTIONS:
            if a in all_actions:
                c = action_by_year[yr].get(a, 0)
                row_str += f"  {c:>16}"
        print(row_str)

    # -------------------------------------------------------
    # 2. Cumulative state by year
    # -------------------------------------------------------
    print(f"\n  --- Cumulative State by Year (% of agents) ---")
    print(f"  {'Year':>4}  {'Elevated%':>10}  {'Insured%':>10}  {'Relocated%':>10}")

    cumulative_data = {}
    for yr in years:
        yr_df = df[df['year'] == yr]
        pct_elevated = yr_df['elevated'].sum() / len(yr_df) * 100
        pct_insured = yr_df['has_insurance'].sum() / len(yr_df) * 100
        pct_relocated = yr_df['relocated'].sum() / len(yr_df) * 100
        cumulative_data[yr] = {
            'elevated': pct_elevated,
            'insured': pct_insured,
            'relocated': pct_relocated
        }
        print(f"  {yr:>4}  {pct_elevated:>10.1f}  {pct_insured:>10.1f}  {pct_relocated:>10.1f}")

    # -------------------------------------------------------
    # 3. Overall action frequency
    # -------------------------------------------------------
    print(f"\n  --- Overall Action Frequency ---")
    overall_counts = df['action'].value_counts()
    total_decisions = len(df)
    oc_dict = {}
    for action, count in overall_counts.items():
        pct = count / total_decisions * 100
        oc_dict[action] = count
        print(f"    {action:>20}: {count:>5} ({pct:>5.1f}%)")

    # -------------------------------------------------------
    # 4. Normalized Shannon entropy per year
    # -------------------------------------------------------
    print(f"\n  --- Normalized Shannon Entropy per Year ---")
    entropy_series = {}
    for yr in years:
        counts = action_by_year[yr]
        H_norm = shannon_entropy(counts)
        entropy_series[yr] = H_norm
        print(f"    Year {yr:>2}: H_norm = {H_norm:.4f}")

    avg_entropy = np.mean(list(entropy_series.values()))
    print(f"    Average entropy: {avg_entropy:.4f}")

    # -------------------------------------------------------
    # 5. TP/CP distribution & trust stats
    # -------------------------------------------------------
    print(f"\n  --- Threat/Coping Appraisal & Trust Stats ---")
    tp_cp_by_year = {}
    has_numeric_tp = False

    if 'threat_appraisal' in df.columns:
        df['tp_val'] = pd.to_numeric(df['threat_appraisal'], errors='coerce')
        df['cp_val'] = pd.to_numeric(df['coping_appraisal'], errors='coerce')
        if df['tp_val'].notna().sum() > 10:
            has_numeric_tp = True
            print(f"    TP mean: {df['tp_val'].mean():.3f}, std: {df['tp_val'].std():.3f}")
            print(f"    CP mean: {df['cp_val'].mean():.3f}, std: {df['cp_val'].std():.3f}")

            print(f"\n    TP/CP by year:")
            print(f"    {'Year':>4}  {'TP_mean':>8}  {'CP_mean':>8}")
            for yr in years:
                yr_df = df[df['year'] == yr]
                tp_m = yr_df['tp_val'].mean()
                cp_m = yr_df['cp_val'].mean()
                tp_cp_by_year[yr] = {'tp_mean': tp_m, 'cp_mean': cp_m}
                print(f"    {yr:>4}  {tp_m:>8.3f}  {cp_m:>8.3f}")

            df['tp_label'] = df['tp_val'].apply(lambda x: 'High' if x >= 0.5 else 'Low')
            df['cp_label'] = df['cp_val'].apply(lambda x: 'High' if x >= 0.5 else 'Low')
            df['construct'] = df['tp_label'] + ' TP / ' + df['cp_label'] + ' CP'
            print(f"\n    Construct distribution (TP/CP quadrant):")
            construct_counts = df['construct'].value_counts()
            for label, count in construct_counts.items():
                pct = count / len(df) * 100
                print(f"      {label:>25}: {count:>5} ({pct:>5.1f}%)")
        else:
            print("    TP/CP: textual (not numeric)")

    # Trust stats
    if trust_ins_col in df.columns:
        ti = pd.to_numeric(df[trust_ins_col], errors='coerce')
        tn = pd.to_numeric(df[trust_neigh_col], errors='coerce')
        if ti.notna().sum() > 0:
            print(f"\n    Trust in Insurance: mean={ti.mean():.3f}, std={ti.std():.3f}")
            print(f"    Trust in Neighbors: mean={tn.mean():.3f}, std={tn.std():.3f}")

    # -------------------------------------------------------
    # 6. Year 10 final state summary
    # -------------------------------------------------------
    final_yr = max(years)
    final_data = cumulative_data[final_yr]
    print(f"\n  --- FINAL STATE (Year {final_yr}) ---")
    print(f"    Elevated: {final_data['elevated']:.1f}%")
    print(f"    Insured:  {final_data['insured']:.1f}%")
    print(f"    Relocated: {final_data['relocated']:.1f}%")
    dn_final = action_by_year[final_yr].get('Do Nothing', 0)
    yr_total = sum(action_by_year[final_yr].values())
    do_nothing_final_pct = dn_final / yr_total * 100 if yr_total > 0 else 0
    print(f"    Do Nothing in final year: {do_nothing_final_pct:.1f}%")

    return {
        'name': name,
        'n_agents': n_agents,
        'n_years': n_years,
        'action_by_year': action_by_year,
        'cumulative_data': cumulative_data,
        'overall_counts': oc_dict,
        'entropy_series': entropy_series,
        'avg_entropy': avg_entropy,
        'final_state': final_data,
        'all_actions': all_actions,
        'tp_cp_by_year': tp_cp_by_year,
        'has_numeric_tp': has_numeric_tp,
    }


# ============================================================
# Run all analyses
# ============================================================
results = {}
for name, path in RUNS.items():
    if os.path.exists(path):
        r = analyze_run(name, path)
        if r is not None:
            results[name] = r
    else:
        print(f"SKIPPING {name}: file not found")

# ============================================================
# CROSS-MODEL COMPARISON TABLES
# ============================================================
print("\n\n" + "="*80)
print("  CROSS-MODEL COMPARISON SUMMARY")
print("="*80)

# Table 1: Final year cumulative states
print("\n  TABLE 1: Cumulative Protective Action Adoption (Final Year)")
print(f"  {'Run':>20}  {'Elevated%':>10}  {'Insured%':>10}  {'Relocated%':>10}  {'AvgEntropy':>12}")
for name in sorted(results.keys()):
    r = results[name]
    fs = r['final_state']
    print(f"  {name:>20}  {fs['elevated']:>10.1f}  {fs['insured']:>10.1f}  {fs['relocated']:>10.1f}  {r['avg_entropy']:>12.4f}")

# Table 2: Overall action distribution (%)
print(f"\n  TABLE 2: Overall Action Distribution (%)")
header = f"  {'Run':>20}"
for a in CANONICAL_ACTIONS:
    header += f"  {a:>16}"
print(header)

for name in sorted(results.keys()):
    r = results[name]
    total = sum(r['overall_counts'].values())
    row = f"  {name:>20}"
    for a in CANONICAL_ACTIONS:
        c = r['overall_counts'].get(a, 0)
        pct = c / total * 100
        row += f"  {pct:>15.1f}%"
    print(row)

# Table 3: Entropy time series
print(f"\n  TABLE 3: Entropy Time Series (Normalized Shannon H)")
all_years = sorted(set(yr for r in results.values() for yr in r['entropy_series'].keys()))
header = f"  {'Run':>20}"
for yr in all_years:
    header += f"  {'Y'+str(yr):>8}"
header += f"  {'Avg':>8}"
print(header)

for name in sorted(results.keys()):
    r = results[name]
    row = f"  {name:>20}"
    for yr in all_years:
        e = r['entropy_series'].get(yr, float('nan'))
        row += f"  {e:>8.4f}"
    row += f"  {r['avg_entropy']:>8.4f}"
    print(row)

# Table 4: Do Nothing % by year
print(f"\n  TABLE 4: 'Do Nothing' Percentage by Year")
header = f"  {'Run':>20}"
for yr in all_years:
    header += f"  {'Y'+str(yr):>8}"
print(header)

for name in sorted(results.keys()):
    r = results[name]
    row = f"  {name:>20}"
    for yr in all_years:
        yr_counts = r['action_by_year'].get(yr, {})
        total_yr = sum(yr_counts.values())
        dn = yr_counts.get('Do Nothing', 0)
        pct = dn / total_yr * 100 if total_yr > 0 else 0
        row += f"  {pct:>7.1f}%"
    print(row)

# Table 5: Scaling comparison
print(f"\n  TABLE 5: Scaling Comparison by Group")
for group_label, models in [("Group A (Baseline)", ['gemma3_4b_A', 'gemma3_12b_A', 'gemma3_27b_A']),
                             ("Group B (Governed)", ['gemma3_4b_B', 'gemma3_12b_B', 'gemma3_27b_B']),
                             ("Group C (Full Gov)", ['gemma3_4b_C', 'gemma3_12b_C'])]:
    print(f"\n  {group_label}:")
    print(f"    {'Model':>16}  {'Elev%':>6}  {'Ins%':>6}  {'Reloc%':>6}  {'DN%':>6}  {'AvgH':>8}")
    for model in models:
        if model in results:
            r = results[model]
            fs = r['final_state']
            total = sum(r['overall_counts'].values())
            dn_pct = r['overall_counts'].get('Do Nothing', 0) / total * 100
            print(f"    {model:>16}  {fs['elevated']:>6.1f}  {fs['insured']:>6.1f}  {fs['relocated']:>6.1f}  {dn_pct:>6.1f}  {r['avg_entropy']:>8.4f}")

# Table 6: Governance effectiveness
print(f"\n  TABLE 6: Governance Effectiveness (A vs B vs C Final Elevated%)")
for model_size in ['gemma3_4b', 'gemma3_12b', 'gemma3_27b']:
    a_key = f"{model_size}_A"
    b_key = f"{model_size}_B"
    c_key = f"{model_size}_C"
    row = f"  {model_size:>12}:"
    for key, label in [(a_key, 'A'), (b_key, 'B'), (c_key, 'C')]:
        if key in results:
            fs = results[key]['final_state']
            row += f"  {label}:Elev={fs['elevated']:.0f}%,Ins={fs['insured']:.0f}%,Reloc={fs['relocated']:.0f}%"
        else:
            row += f"  {label}:N/A"
    print(row)

# Table 7: 12b collapse analysis
print(f"\n  TABLE 7: 12b Collapse Analysis")
for key in ['gemma3_12b_A', 'gemma3_12b_B', 'gemma3_12b_C']:
    if key in results:
        r = results[key]
        final_yr = max(r['entropy_series'].keys())
        first_yr = min(r['entropy_series'].keys())
        print(f"  {key}: entropy Y1={r['entropy_series'][first_yr]:.4f}, Y{final_yr}={r['entropy_series'][final_yr]:.4f}, "
              f"avg={r['avg_entropy']:.4f}")
        # Check how many years have DN > 90%
        collapse_years = 0
        for yr, counts in r['action_by_year'].items():
            total = sum(counts.values())
            dn = counts.get('Do Nothing', 0)
            if total > 0 and dn / total > 0.9:
                collapse_years += 1
        print(f"         Years with DN > 90%: {collapse_years}/{len(r['action_by_year'])}")

print("\n\nDone. All analysis complete.")
