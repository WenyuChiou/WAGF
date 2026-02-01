"""
Comprehensive analysis of JOH_FINAL flood experiment results.
Analyzes action distributions, agent states, entropy, and appraisal constructs
across 3 model sizes (4b, 12b, 27b) and 3 governance groups (A, B, C).
"""

import pandas as pd
import numpy as np
import json
import os
from collections import Counter

BASE = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL"

MODELS = ["gemma3_4b", "gemma3_12b", "gemma3_27b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]

# ---- Action normalization ----
# Group A uses 'decision' column with values like "Do Nothing", "Only Flood Insurance", etc.
# Group B/C use 'yearly_decision' column with values like "do_nothing", "buy_insurance", etc.

DECISION_MAP_A = {
    "Do Nothing": "do_nothing",
    "Only Flood Insurance": "buy_insurance",
    "Only House Elevation": "elevate_house",
    "Both Flood Insurance and House Elevation": "insurance_elevation",
    "Relocate": "relocate",
    "Already relocated": "relocated",
}

DECISION_MAP_BC = {
    "do_nothing": "do_nothing",
    "buy_insurance": "buy_insurance",
    "elevate_house": "elevate_house",
    "relocate": "relocate",
    "relocated": "relocated",
}

CANONICAL_ACTIONS = ["do_nothing", "buy_insurance", "elevate_house", "relocate"]
ALL_ACTIONS = ["do_nothing", "buy_insurance", "elevate_house", "relocate", "insurance_elevation", "relocated"]

def entropy(counts):
    """Shannon entropy from a dict of counts."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    probs = [c / total for c in counts.values() if c > 0]
    return -sum(p * np.log2(p) for p in probs)

def max_entropy(n):
    return np.log2(n) if n > 1 else 0.0

def gini_simpson(counts):
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return 1 - sum((c/total)**2 for c in counts.values())

print("=" * 120)
print("COMPREHENSIVE FLOOD EXPERIMENT ANALYSIS - JOH_FINAL")
print("=" * 120)

# ============================================================
# SECTION 1: Load all data, harmonize columns
# ============================================================
all_data = {}
for model in MODELS:
    for group in GROUPS:
        path = os.path.join(BASE, model, group, "Run_1", "simulation_log.csv")
        if not os.path.exists(path):
            print(f"MISSING: {model}/{group}")
            continue
        df = pd.read_csv(path, encoding='utf-8-sig')

        # Harmonize decision column
        if 'yearly_decision' in df.columns:
            # Group B/C schema
            df['action_norm'] = df['yearly_decision'].map(DECISION_MAP_BC).fillna('unknown')
        elif 'decision' in df.columns:
            # Group A schema
            df['action_norm'] = df['decision'].map(DECISION_MAP_A).fillna('unknown')
        else:
            print(f"  WARNING: no decision column found for {model}/{group}")
            continue

        # Harmonize trust columns
        if 'trust_insurance' in df.columns:
            df['trust_ins'] = pd.to_numeric(df['trust_insurance'], errors='coerce')
        elif 'trust_in_insurance' in df.columns:
            df['trust_ins'] = pd.to_numeric(df['trust_in_insurance'], errors='coerce')

        if 'trust_neighbors' in df.columns:
            df['trust_neigh'] = pd.to_numeric(df['trust_neighbors'], errors='coerce')
        elif 'trust_in_neighbors' in df.columns:
            df['trust_neigh'] = pd.to_numeric(df['trust_in_neighbors'], errors='coerce')

        # Ensure boolean columns
        for col in ['elevated', 'has_insurance', 'relocated']:
            if col in df.columns:
                df[col] = df[col].astype(bool)

        all_data[(model, group)] = df
        print(f"Loaded {model}/{group}: {len(df)} rows, years 1-{df['year'].max()}, "
              f"{df['agent_id'].nunique()} agents, actions: {sorted(df['action_norm'].unique())}")

print(f"\nTotal configurations loaded: {len(all_data)} / 9 expected")

# ============================================================
# SECTION 2: Overall Action Distribution per Model x Group
# ============================================================
print("\n" + "=" * 120)
print("SECTION 2: OVERALL ACTION DISTRIBUTION (% of all agent-year decisions)")
print("=" * 120)

header = f"{'Model':<15} {'Group':<10} " + " ".join(f"{a:>14}" for a in ALL_ACTIONS) + f" {'N':>8}"
print(header)
print("-" * len(header))

for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        counts = df['action_norm'].value_counts()
        total = len(df)
        vals = []
        for a in ALL_ACTIONS:
            c = counts.get(a, 0)
            vals.append(f"{100*c/total:>13.1f}%")
        print(f"{model:<15} {group:<10} " + " ".join(vals) + f" {total:>8}")
    print()

# ============================================================
# SECTION 3: Action Distribution by Year
# ============================================================
print("\n" + "=" * 120)
print("SECTION 3: ACTION DISTRIBUTION BY YEAR (condensed: DN/INS/ELEV/RELOC/INS+ELEV %)")
print("=" * 120)

for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        print(f"\n--- {model} / {group} ---")
        print(f"{'Yr':>3} {'DN%':>6} {'INS%':>6} {'ELEV%':>6} {'RELOC%':>7} {'I+E%':>6} {'reld%':>6} {'Entropy':>8} {'NormEnt':>8} {'GiniS':>6} {'N':>5}")

        for yr in sorted(df['year'].unique()):
            ydf = df[df['year'] == yr]
            counts = Counter(ydf['action_norm'])
            total = len(ydf)
            dn = counts.get('do_nothing', 0)
            bi = counts.get('buy_insurance', 0)
            eh = counts.get('elevate_house', 0)
            rl = counts.get('relocate', 0)
            ie = counts.get('insurance_elevation', 0)
            rd = counts.get('relocated', 0)
            ent = entropy(counts)
            me = max_entropy(len([c for c in counts.values() if c > 0]))
            # Use 4-action baseline for norm entropy
            ne = ent / max_entropy(4)
            gs = gini_simpson(counts)
            print(f"{yr:>3} {100*dn/total:>5.1f} {100*bi/total:>5.1f} {100*eh/total:>5.1f} "
                  f"{100*rl/total:>6.1f} {100*ie/total:>5.1f} {100*rd/total:>5.1f} "
                  f"{ent:>8.3f} {ne:>8.3f} {gs:>6.3f} {total:>5}")

# ============================================================
# SECTION 4: Agent Final States
# ============================================================
print("\n" + "=" * 120)
print("SECTION 4: AGENT STATES AT FINAL YEAR")
print("=" * 120)

header4 = f"{'Model':<15} {'Group':<10} {'MaxYr':>6} {'N_agents':>9} {'Elevated%':>10} {'Insured%':>10} {'Relocated%':>11}"
print(header4)
print("-" * len(header4))

final_states = {}
for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        max_yr = df['year'].max()
        final = df[df['year'] == max_yr]
        n = len(final)
        el = final['elevated'].sum()
        ins = final['has_insurance'].sum()
        rel = final['relocated'].sum()
        final_states[key] = {'elevated': el/n, 'insured': ins/n, 'relocated': rel/n, 'n': n}
        print(f"{model:<15} {group:<10} {max_yr:>6} {n:>9} "
              f"{100*el/n:>9.1f}% {100*ins/n:>9.1f}% {100*rel/n:>10.1f}%")

# ============================================================
# SECTION 5: Trust / Appraisal Statistics
# ============================================================
print("\n" + "=" * 120)
print("SECTION 5: TRUST IN INSURANCE & TRUST IN NEIGHBORS (overall)")
print("=" * 120)

header5 = f"{'Model':<15} {'Group':<10} {'TI_mean':>8} {'TI_std':>8} {'TI_med':>8} {'TN_mean':>8} {'TN_std':>8} {'TN_med':>8} {'TI>TN%':>8}"
print(header5)
print("-" * len(header5))

for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        if 'trust_ins' in df.columns and 'trust_neigh' in df.columns:
            ti = df['trust_ins'].dropna()
            tn = df['trust_neigh'].dropna()
            ti_gt_tn = (df['trust_ins'] > df['trust_neigh']).sum() / len(df) * 100
            print(f"{model:<15} {group:<10} {ti.mean():>8.3f} {ti.std():>8.3f} {ti.median():>8.3f} "
                  f"{tn.mean():>8.3f} {tn.std():>8.3f} {tn.median():>8.3f} {ti_gt_tn:>7.1f}%")
    print()

# ============================================================
# SECTION 5b: Trust by Year
# ============================================================
print("\n" + "=" * 120)
print("SECTION 5b: TRUST TRAJECTORIES BY YEAR (mean)")
print("=" * 120)

for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        if 'trust_ins' not in df.columns:
            continue
        print(f"\n--- {model} / {group} ---")
        print(f"{'Yr':>3} {'TI_mean':>8} {'TI_std':>8} {'TN_mean':>8} {'TN_std':>8}")
        for yr in sorted(df['year'].unique()):
            ydf = df[df['year'] == yr]
            print(f"{yr:>3} {ydf['trust_ins'].mean():>8.3f} {ydf['trust_ins'].std():>8.3f} "
                  f"{ydf['trust_neigh'].mean():>8.3f} {ydf['trust_neigh'].std():>8.3f}")

# ============================================================
# SECTION 6: Entropy Summary
# ============================================================
print("\n" + "=" * 120)
print("SECTION 6: ENTROPY SUMMARY TABLE")
print("=" * 120)

entropy_data = {}
header6 = f"{'Model':<15} {'Group':<10} {'MeanEnt':>8} {'StdEnt':>8} {'MinEnt':>8} {'MaxEnt':>8} {'Yr1':>8} {'YrEnd':>8} {'Delta':>8} {'MeanGS':>8}"
print(header6)
print("-" * len(header6))

for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        years = sorted(df['year'].unique())
        ents = []
        gss = []
        for yr in years:
            ydf = df[df['year'] == yr]
            counts = Counter(ydf['action_norm'])
            ne = entropy(counts) / max_entropy(4)
            ents.append(ne)
            gss.append(gini_simpson(counts))
        entropy_data[key] = ents
        me = np.mean(ents)
        se = np.std(ents)
        print(f"{model:<15} {group:<10} {me:>8.3f} {se:>8.3f} {min(ents):>8.3f} {max(ents):>8.3f} "
              f"{ents[0]:>8.3f} {ents[-1]:>8.3f} {ents[-1]-ents[0]:>+8.3f} {np.mean(gss):>8.3f}")

# ============================================================
# SECTION 7: Action Collapse Detection
# ============================================================
print("\n" + "=" * 120)
print("SECTION 7: ACTION COLLAPSE DETECTION (single action > 60% in any year)")
print("=" * 120)

for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        collapses = []
        for yr in sorted(df['year'].unique()):
            ydf = df[df['year'] == yr]
            counts = Counter(ydf['action_norm'])
            total = len(ydf)
            for action, count in counts.most_common(1):
                frac = count / total
                if frac > 0.60:
                    collapses.append((yr, action, frac*100))
        if collapses:
            print(f"{model:<15} {group:<10} | COLLAPSE in {len(collapses)}/{df['year'].nunique()} years:")
            for yr, act, pct in collapses:
                print(f"  Year {yr:>2}: {act:<20} = {pct:.1f}%")
        else:
            print(f"{model:<15} {group:<10} | No collapse (all years < 60% single action)")

# ============================================================
# SECTION 8: Governance Summary
# ============================================================
print("\n" + "=" * 120)
print("SECTION 8: GOVERNANCE INTERVENTION SUMMARY")
print("=" * 120)

gov_header = f"{'Model':<15} {'Group':<10} {'Interventions':>14} {'Rule':>25} {'RetryOK':>8} {'RetryFail':>10} {'Warnings':>9} {'WarnRule':>20}"
print(gov_header)
print("-" * len(gov_header))

for model in MODELS:
    for group in ["Group_B", "Group_C"]:
        path = os.path.join(BASE, model, group, "Run_1", "governance_summary.json")
        if not os.path.exists(path):
            print(f"{model:<15} {group:<10} | NO FILE")
            continue
        with open(path, 'r') as f:
            gov = json.load(f)
        rules = list(gov['rule_frequency'].keys())
        rule_str = ", ".join(f"{k}:{v}" for k, v in gov['rule_frequency'].items())
        warn_str = ", ".join(f"{k}:{v}" for k, v in gov['warnings']['warning_rule_frequency'].items())
        print(f"{model:<15} {group:<10} {gov['total_interventions']:>14} {rule_str:>25} "
              f"{gov['outcome_stats']['retry_success']:>8} {gov['outcome_stats']['retry_exhausted']:>10} "
              f"{gov['warnings']['total_warnings']:>9} {warn_str:>20}")

# ============================================================
# SECTION 9: Cross-Model Comparison
# ============================================================
print("\n" + "=" * 120)
print("SECTION 9: CROSS-MODEL COMPARISON (key metrics)")
print("=" * 120)

# Build a summary table
metrics = ['Mean Norm Entropy', 'Entropy Yr1', 'Entropy YrEnd', 'Entropy Delta',
           'Elevated% Final', 'Insured% Final', 'Relocated% Final',
           'do_nothing% Overall', 'buy_insurance% Overall', 'elevate% Overall', 'relocate% Overall']

print(f"\n{'Metric':<22}", end="")
for model in MODELS:
    for group in GROUPS:
        label = f"{model.split('_')[1]}_{group[-1]}"
        print(f" {label:>10}", end="")
print()
print("-" * (22 + 11 * len(MODELS) * len(GROUPS)))

for metric in metrics:
    print(f"{metric:<22}", end="")
    for model in MODELS:
        for group in GROUPS:
            key = (model, group)
            if key not in all_data:
                print(f" {'N/A':>10}", end="")
                continue
            df = all_data[key]
            if metric == 'Mean Norm Entropy':
                val = np.mean(entropy_data[key])
                print(f" {val:>10.3f}", end="")
            elif metric == 'Entropy Yr1':
                val = entropy_data[key][0]
                print(f" {val:>10.3f}", end="")
            elif metric == 'Entropy YrEnd':
                val = entropy_data[key][-1]
                print(f" {val:>10.3f}", end="")
            elif metric == 'Entropy Delta':
                val = entropy_data[key][-1] - entropy_data[key][0]
                print(f" {val:>+10.3f}", end="")
            elif metric == 'Elevated% Final':
                val = final_states[key]['elevated'] * 100
                print(f" {val:>9.1f}%", end="")
            elif metric == 'Insured% Final':
                val = final_states[key]['insured'] * 100
                print(f" {val:>9.1f}%", end="")
            elif metric == 'Relocated% Final':
                val = final_states[key]['relocated'] * 100
                print(f" {val:>9.1f}%", end="")
            elif metric == 'do_nothing% Overall':
                val = (df['action_norm'] == 'do_nothing').sum() / len(df) * 100
                print(f" {val:>9.1f}%", end="")
            elif metric == 'buy_insurance% Overall':
                val = (df['action_norm'] == 'buy_insurance').sum() / len(df) * 100
                print(f" {val:>9.1f}%", end="")
            elif metric == 'elevate% Overall':
                val = (df['action_norm'] == 'elevate_house').sum() / len(df) * 100
                print(f" {val:>9.1f}%", end="")
            elif metric == 'relocate% Overall':
                val = (df['action_norm'] == 'relocate').sum() / len(df) * 100
                print(f" {val:>9.1f}%", end="")
    print()

# ============================================================
# SECTION 10: Do_Nothing over time (compact)
# ============================================================
print("\n" + "=" * 120)
print("SECTION 10: DO_NOTHING % OVER TIME")
print("=" * 120)

print(f"{'Yr':>3}", end="")
for model in MODELS:
    for group in GROUPS:
        label = f"{model.split('_')[1]}_{group[-1]}"
        print(f" {label:>8}", end="")
print()

for yr in range(1, 11):
    print(f"{yr:>3}", end="")
    for model in MODELS:
        for group in GROUPS:
            key = (model, group)
            if key not in all_data:
                print(f" {'N/A':>8}", end="")
                continue
            df = all_data[key]
            ydf = df[df['year'] == yr]
            if len(ydf) > 0:
                pct = (ydf['action_norm'] == 'do_nothing').sum() / len(ydf) * 100
                print(f" {pct:>7.1f}%", end="")
            else:
                print(f" {'N/A':>8}", end="")
    print()

# ============================================================
# SECTION 11: Relocate % over time
# ============================================================
print("\n" + "=" * 120)
print("SECTION 11: RELOCATE % OVER TIME (action chosen that year)")
print("=" * 120)

print(f"{'Yr':>3}", end="")
for model in MODELS:
    for group in GROUPS:
        label = f"{model.split('_')[1]}_{group[-1]}"
        print(f" {label:>8}", end="")
print()

for yr in range(1, 11):
    print(f"{yr:>3}", end="")
    for model in MODELS:
        for group in GROUPS:
            key = (model, group)
            if key not in all_data:
                print(f" {'N/A':>8}", end="")
                continue
            df = all_data[key]
            ydf = df[df['year'] == yr]
            if len(ydf) > 0:
                pct = (ydf['action_norm'] == 'relocate').sum() / len(ydf) * 100
                print(f" {pct:>7.1f}%", end="")
            else:
                print(f" {'N/A':>8}", end="")
    print()

# ============================================================
# SECTION 12: Elevated state (cumulative) over time
# ============================================================
print("\n" + "=" * 120)
print("SECTION 12: ELEVATED STATE (cumulative) % OVER TIME")
print("=" * 120)

print(f"{'Yr':>3}", end="")
for model in MODELS:
    for group in GROUPS:
        label = f"{model.split('_')[1]}_{group[-1]}"
        print(f" {label:>8}", end="")
print()

for yr in range(1, 11):
    print(f"{yr:>3}", end="")
    for model in MODELS:
        for group in GROUPS:
            key = (model, group)
            if key not in all_data:
                print(f" {'N/A':>8}", end="")
                continue
            df = all_data[key]
            ydf = df[df['year'] == yr]
            if len(ydf) > 0:
                pct = ydf['elevated'].sum() / len(ydf) * 100
                print(f" {pct:>7.1f}%", end="")
            else:
                print(f" {'N/A':>8}", end="")
    print()

# ============================================================
# SECTION 13: Insured state over time
# ============================================================
print("\n" + "=" * 120)
print("SECTION 13: INSURED STATE % OVER TIME")
print("=" * 120)

print(f"{'Yr':>3}", end="")
for model in MODELS:
    for group in GROUPS:
        label = f"{model.split('_')[1]}_{group[-1]}"
        print(f" {label:>8}", end="")
print()

for yr in range(1, 11):
    print(f"{yr:>3}", end="")
    for model in MODELS:
        for group in GROUPS:
            key = (model, group)
            if key not in all_data:
                print(f" {'N/A':>8}", end="")
                continue
            df = all_data[key]
            ydf = df[df['year'] == yr]
            if len(ydf) > 0:
                pct = ydf['has_insurance'].sum() / len(ydf) * 100
                print(f" {pct:>7.1f}%", end="")
            else:
                print(f" {'N/A':>8}", end="")
    print()

# ============================================================
# SECTION 14: Relocated state over time
# ============================================================
print("\n" + "=" * 120)
print("SECTION 14: RELOCATED STATE (cumulative) % OVER TIME")
print("=" * 120)

print(f"{'Yr':>3}", end="")
for model in MODELS:
    for group in GROUPS:
        label = f"{model.split('_')[1]}_{group[-1]}"
        print(f" {label:>8}", end="")
print()

for yr in range(1, 11):
    print(f"{yr:>3}", end="")
    for model in MODELS:
        for group in GROUPS:
            key = (model, group)
            if key not in all_data:
                print(f" {'N/A':>8}", end="")
                continue
            df = all_data[key]
            ydf = df[df['year'] == yr]
            if len(ydf) > 0:
                pct = ydf['relocated'].sum() / len(ydf) * 100
                print(f" {pct:>7.1f}%", end="")
            else:
                print(f" {'N/A':>8}", end="")
    print()

# ============================================================
# SECTION 15: Flood events and post-flood behavioral response
# ============================================================
print("\n" + "=" * 120)
print("SECTION 15: FLOOD EVENTS AND POST-FLOOD BEHAVIORAL RESPONSE")
print("(Only Group A has flooded_this_year column)")
print("=" * 120)

for model in MODELS:
    key = (model, "Group_A")
    if key not in all_data:
        continue
    df = all_data[key]
    if 'flooded_this_year' not in df.columns:
        continue
    print(f"\n--- {model} / Group_A ---")
    for yr in sorted(df['year'].unique()):
        ydf = df[df['year'] == yr]
        flooded = ydf['flooded_this_year'].sum()
        if flooded > 0:
            pct_f = flooded / len(ydf) * 100
            print(f"  Year {yr}: {flooded}/{len(ydf)} agents flooded ({pct_f:.0f}%)", end="")
            # Next year response
            if yr + 1 <= df['year'].max():
                nydf = df[df['year'] == yr + 1]
                counts = Counter(nydf['action_norm'])
                total = len(nydf)
                parts = []
                for a in ['do_nothing', 'buy_insurance', 'elevate_house', 'relocate', 'insurance_elevation']:
                    c = counts.get(a, 0)
                    if c > 0:
                        parts.append(f"{a}={100*c/total:.0f}%")
                print(f"  =>  Yr{yr+1}: {', '.join(parts)}")
            else:
                print()

# ============================================================
# SECTION 16: Agent-level action switching rate (behavioral consistency)
# ============================================================
print("\n" + "=" * 120)
print("SECTION 16: BEHAVIORAL CONSISTENCY - ACTION SWITCHING RATE")
print("(% of agent-year pairs where the agent chose a DIFFERENT action than previous year)")
print("=" * 120)

header16 = f"{'Model':<15} {'Group':<10} {'SwitchRate%':>12} {'MeanSwitches':>13} {'Agents0Switch':>14} {'AgentsAllSwitch':>15}"
print(header16)
print("-" * len(header16))

for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        # For each agent, count how many times they switched action
        total_switches = 0
        total_transitions = 0
        agent_switches = {}
        for aid in df['agent_id'].unique():
            adf = df[df['agent_id'] == aid].sort_values('year')
            actions = adf['action_norm'].values
            switches = sum(1 for i in range(1, len(actions)) if actions[i] != actions[i-1])
            agent_switches[aid] = switches
            total_switches += switches
            total_transitions += len(actions) - 1

        switch_rate = total_switches / total_transitions * 100 if total_transitions > 0 else 0
        mean_sw = np.mean(list(agent_switches.values()))
        zero_sw = sum(1 for v in agent_switches.values() if v == 0)
        all_sw = sum(1 for v in agent_switches.values() if v == len(sorted(df['year'].unique())) - 1)
        print(f"{model:<15} {group:<10} {switch_rate:>11.1f}% {mean_sw:>13.2f} {zero_sw:>14} {all_sw:>15}")

# ============================================================
# SECTION 17: Per-agent action entropy (intra-agent diversity)
# ============================================================
print("\n" + "=" * 120)
print("SECTION 17: INTRA-AGENT ACTION ENTROPY (how diverse are individual agent actions over time?)")
print("=" * 120)

header17 = f"{'Model':<15} {'Group':<10} {'MeanAgentEnt':>13} {'StdAgentEnt':>12} {'Min':>6} {'Max':>6} {'Agents1Act':>11}"
print(header17)
print("-" * len(header17))

for model in MODELS:
    for group in GROUPS:
        key = (model, group)
        if key not in all_data:
            continue
        df = all_data[key]
        agent_ents = []
        single_action_agents = 0
        for aid in df['agent_id'].unique():
            adf = df[df['agent_id'] == aid]
            counts = Counter(adf['action_norm'])
            ent = entropy(counts) / max_entropy(4)
            agent_ents.append(ent)
            if len(counts) == 1:
                single_action_agents += 1
        print(f"{model:<15} {group:<10} {np.mean(agent_ents):>13.3f} {np.std(agent_ents):>12.3f} "
              f"{min(agent_ents):>6.3f} {max(agent_ents):>6.3f} {single_action_agents:>11}")

print("\n" + "=" * 120)
print("ANALYSIS COMPLETE")
print("=" * 120)
