#!/usr/bin/env python3
"""
Nature Water P0: Flood domain statistics across 3 runs per model×group.
Computes: mean±SD EHE, bootstrap CIs, updated Table 1 with error bars.
Also verifies action space and computes constraint violation rates.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import json

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")

MODELS = {
    "gemma3_4b": "Gemma-3 4B",
    "gemma3_12b": "Gemma-3 12B",
    "gemma3_27b": "Gemma-3 27B",
    "ministral3_3b": "Ministral 3B",
    "ministral3_8b": "Ministral 8B",
    "ministral3_14b": "Ministral 14B",
}
GROUPS = ["Group_A", "Group_B", "Group_C"]
RUNS = ["Run_1", "Run_2", "Run_3"]

# Canonical action mapping
CANONICAL_ACTIONS = {
    # Ungoverned (Group A) labels
    "Do Nothing": "do_nothing",
    "Do nothing": "do_nothing",
    "do nothing": "do_nothing",
    "Only Flood Insurance": "buy_insurance",
    "Buy flood insurance": "buy_insurance",
    "buy flood insurance": "buy_insurance",
    "Only House Elevation": "elevate_house",
    "Elevate the house": "elevate_house",
    "elevate the house": "elevate_house",
    "Both Flood Insurance and House Elevation": "both",
    "Relocate": "relocate",
    "relocate": "relocate",
    "Already relocated": "relocated",
    # Governed (Group B/C) labels
    "do_nothing": "do_nothing",
    "buy_insurance": "buy_insurance",
    "elevate_house": "elevate_house",
    "relocated": "relocated",
}

# Valid actions for EHE (exclude terminal "relocated" state)
VALID_ACTIONS = ["do_nothing", "buy_insurance", "elevate_house", "relocate", "both"]

# Physical constraint violations in ungoverned:
# 1. Elevating an already-elevated home
# 2. Making decisions after relocation
# 3. "both" when already elevated (partial violation)
CONSTRAINT_VIOLATION_CHECKS = True


def load_run(model_dir, group, run):
    """Load a single run's simulation log and normalize actions."""
    path = BASE / model_dir / group / run / "simulation_log.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="utf-8")

    # Determine action column
    if "yearly_decision" in df.columns:
        action_col = "yearly_decision"
    elif "decision" in df.columns:
        action_col = "decision"
    else:
        return None

    # Normalize actions
    df["action"] = df[action_col].map(lambda x: CANONICAL_ACTIONS.get(str(x).strip(), str(x).strip().lower()))

    # Track physical state for violation detection
    df["is_valid"] = True  # Will be updated below
    if CONSTRAINT_VIOLATION_CHECKS and group == "Group_A":
        # Detect violations: decisions after relocation, re-elevation
        for agent_id in df["agent_id"].unique():
            mask = df["agent_id"] == agent_id
            agent_df = df[mask].sort_values("year")
            relocated = False
            elevated = False
            for idx, row in agent_df.iterrows():
                if relocated and row["action"] not in ["relocated"]:
                    df.loc[idx, "is_valid"] = False  # Decision after relocation
                if elevated and row["action"] == "elevate_house":
                    df.loc[idx, "is_valid"] = False  # Re-elevation
                if row["action"] == "relocate":
                    relocated = True
                if row["action"] in ["elevate_house", "both"]:
                    elevated = True
    return df


def compute_ehe(actions, k=None):
    """Compute EHE (normalized Shannon entropy) over action distribution."""
    counts = Counter(actions)
    # Remove terminal state
    counts.pop("relocated", None)
    if not counts:
        return 0.0
    total = sum(counts.values())
    if total == 0:
        return 0.0
    probs = np.array([c / total for c in counts.values()])
    probs = probs[probs > 0]
    H = -np.sum(probs * np.log2(probs))
    if k is None:
        k = len(VALID_ACTIONS)  # 5 for ungoverned (includes "both"), 4 for governed
    H_max = np.log2(k) if k > 1 else 1.0
    return H / H_max


def compute_violation_rate(df):
    """Compute physical constraint violation rate."""
    active = df[df["action"] != "relocated"]
    if len(active) == 0:
        return 0.0
    return (~active["is_valid"]).sum() / len(active)


def bootstrap_ci(values, n_boot=10000, ci=0.95):
    """Compute bootstrap confidence interval."""
    values = np.array(values)
    n = len(values)
    boot_means = np.array([np.mean(np.random.choice(values, size=n, replace=True)) for _ in range(n_boot)])
    alpha = (1 - ci) / 2
    return np.percentile(boot_means, [100 * alpha, 100 * (1 - alpha)])


# ══════════════════════════════════════════════════════════════════════════
# COMPUTE ALL METRICS
# ══════════════════════════════════════════════════════════════════════════
np.random.seed(42)

results = {}  # model -> group -> [ehe_run1, ehe_run2, ehe_run3]
violation_rates = {}  # model -> [rate_run1, rate_run2, rate_run3]
ehe_valid_results = {}  # model -> group_A -> [ehe_valid_run1, ...]
action_spaces = {}  # model -> group -> set of actions observed

print("=" * 90)
print("NATURE WATER P0: FLOOD DOMAIN STATISTICS (3 runs per model×group)")
print("=" * 90)

for model_dir, model_name in MODELS.items():
    results[model_name] = {}
    action_spaces[model_name] = {}

    for group in GROUPS:
        ehe_values = []
        viol_values = []
        ehe_valid_values = []
        group_actions = set()

        for run in RUNS:
            df = load_run(model_dir, group, run)
            if df is None:
                print(f"  WARNING: Missing {model_dir}/{group}/{run}")
                continue

            active = df[df["action"] != "relocated"]
            actions = active["action"].tolist()
            group_actions.update(actions)

            # For ungoverned: k=5 (includes "both"); for governed: k=4 (no "both")
            if group == "Group_A":
                k = 5
            else:
                k = 4

            ehe = compute_ehe(actions, k=k)
            ehe_values.append(ehe)

            if group == "Group_A":
                vr = compute_violation_rate(df)
                viol_values.append(vr)
                # EHE on valid-only decisions
                valid_actions = active[active["is_valid"]]["action"].tolist()
                ehe_v = compute_ehe(valid_actions, k=k)
                ehe_valid_values.append(ehe_v)

        results[model_name][group] = ehe_values
        action_spaces[model_name][group] = group_actions

        if group == "Group_A":
            violation_rates[model_name] = viol_values
            ehe_valid_results[model_name] = ehe_valid_values

# ══════════════════════════════════════════════════════════════════════════
# 1. ACTION SPACE VERIFICATION
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("1. ACTION SPACE VERIFICATION")
print("=" * 90)
for model_name in MODELS.values():
    for group in GROUPS:
        actions = action_spaces[model_name].get(group, set())
        print(f"  {model_name:15s} {group}: {sorted(actions)}")

# ══════════════════════════════════════════════════════════════════════════
# 2. TABLE 1 UPDATED: MEAN ± SD ACROSS 3 RUNS
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("2. TABLE 1 UPDATED: EHE mean ± SD (3 runs per condition)")
print("=" * 90)

header = f"{'Model':>18s} | {'Ungov EHE_all':>14s} | {'Ungov EHE_valid':>16s} | {'Violation%':>10s} | {'Gov B EHE':>14s} | {'Gov C EHE':>14s} | {'Delta':>8s} | {'Scaffolding?':>12s}"
print(f"\n{header}")
print("-" * len(header))

table1_data = []
for model_name in MODELS.values():
    a_vals = results[model_name].get("Group_A", [])
    b_vals = results[model_name].get("Group_B", [])
    c_vals = results[model_name].get("Group_C", [])
    v_vals = ehe_valid_results.get(model_name, [])
    vr_vals = violation_rates.get(model_name, [])

    a_mean = np.mean(a_vals) if a_vals else np.nan
    a_sd = np.std(a_vals, ddof=1) if len(a_vals) > 1 else 0
    v_mean = np.mean(v_vals) if v_vals else np.nan
    v_sd = np.std(v_vals, ddof=1) if len(v_vals) > 1 else 0
    b_mean = np.mean(b_vals) if b_vals else np.nan
    b_sd = np.std(b_vals, ddof=1) if len(b_vals) > 1 else 0
    c_mean = np.mean(c_vals) if c_vals else np.nan
    c_sd = np.std(c_vals, ddof=1) if len(c_vals) > 1 else 0
    vr_mean = np.mean(vr_vals) * 100 if vr_vals else np.nan

    best_gov = max(b_mean, c_mean)
    delta = best_gov - v_mean
    scaffolding = "Yes" if delta > 0.05 else ("Reversed" if delta < -0.05 else "Marginal")

    print(f"{model_name:>18s} | {a_mean:.3f}±{a_sd:.3f} | {v_mean:.3f}±{v_sd:.3f}   | {vr_mean:8.1f}% | {b_mean:.3f}±{b_sd:.3f} | {c_mean:.3f}±{c_sd:.3f} | {delta:+.3f} | {scaffolding:>12s}")

    table1_data.append({
        "Model": model_name,
        "Ungov_EHE_all_mean": round(a_mean, 3),
        "Ungov_EHE_all_sd": round(a_sd, 3),
        "Ungov_EHE_valid_mean": round(v_mean, 3),
        "Ungov_EHE_valid_sd": round(v_sd, 3),
        "Violation_pct": round(vr_mean, 1),
        "Gov_B_EHE_mean": round(b_mean, 3),
        "Gov_B_EHE_sd": round(b_sd, 3),
        "Gov_C_EHE_mean": round(c_mean, 3),
        "Gov_C_EHE_sd": round(c_sd, 3),
        "Delta_EHE": round(delta, 3),
        "Scaffolding": scaffolding,
    })

# ══════════════════════════════════════════════════════════════════════════
# 3. BOOTSTRAP CIs FOR FLOOD SCAFFOLDING EFFECT
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("3. BOOTSTRAP CIs: Governed vs Ungoverned (per model)")
print("=" * 90)

for model_name in MODELS.values():
    a_vals = np.array(results[model_name].get("Group_A", []))
    b_vals = np.array(results[model_name].get("Group_B", []))
    c_vals = np.array(results[model_name].get("Group_C", []))

    if len(a_vals) < 2 or len(b_vals) < 2:
        print(f"  {model_name}: insufficient runs for bootstrap")
        continue

    # Best governed = max of B, C per run (paired)
    best_gov = np.maximum(b_vals, c_vals)
    diff = best_gov - a_vals

    mean_diff = np.mean(diff)
    ci = bootstrap_ci(diff, n_boot=10000)

    # Cohen's d (paired)
    sd_diff = np.std(diff, ddof=1)
    d = mean_diff / sd_diff if sd_diff > 0 else np.inf

    # Overlap check
    overlap = np.min(best_gov) > np.max(a_vals)

    print(f"  {model_name:18s}: diff={mean_diff:+.3f}, 95% CI [{ci[0]:.3f}, {ci[1]:.3f}], d={d:.2f}, zero_overlap={'Yes' if overlap else 'No'}")

# ══════════════════════════════════════════════════════════════════════════
# 4. AGGREGATE FLOOD SCAFFOLDING EFFECT (POOLED ACROSS MODELS)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("4. AGGREGATE FLOOD SCAFFOLDING (pooled across all 6 models)")
print("=" * 90)

all_a = []
all_best_gov = []
scaffolding_count = 0
total_models = 0

for model_name in MODELS.values():
    a_vals = results[model_name].get("Group_A", [])
    b_vals = results[model_name].get("Group_B", [])
    c_vals = results[model_name].get("Group_C", [])
    if not a_vals or not b_vals or not c_vals:
        continue
    total_models += 1
    a_mean = np.mean(a_vals)
    best = max(np.mean(b_vals), np.mean(c_vals))
    all_a.append(a_mean)
    all_best_gov.append(best)
    if best > a_mean + 0.05:
        scaffolding_count += 1

all_a = np.array(all_a)
all_best_gov = np.array(all_best_gov)
diffs = all_best_gov - all_a

print(f"  Models with scaffolding effect (delta > 0.05): {scaffolding_count}/{total_models}")
print(f"  Mean ungoverned EHE: {np.mean(all_a):.3f} ± {np.std(all_a, ddof=1):.3f}")
print(f"  Mean best-governed EHE: {np.mean(all_best_gov):.3f} ± {np.std(all_best_gov, ddof=1):.3f}")
print(f"  Mean delta: {np.mean(diffs):+.3f} ± {np.std(diffs, ddof=1):.3f}")
ci_pooled = bootstrap_ci(diffs, n_boot=10000)
print(f"  Bootstrap 95% CI on delta: [{ci_pooled[0]:.3f}, {ci_pooled[1]:.3f}]")

# ══════════════════════════════════════════════════════════════════════════
# 5. FIRST-ATTEMPT EHE (governed groups only)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("5. FIRST-ATTEMPT EHE (retry_count=0, governed groups B/C)")
print("=" * 90)

for model_dir, model_name in MODELS.items():
    for group in ["Group_B", "Group_C"]:
        first_ehe_vals = []
        for run in RUNS:
            audit_path = BASE / model_dir / group / run / "household_governance_audit.csv"
            if not audit_path.exists():
                continue
            try:
                audit = pd.read_csv(audit_path, encoding="utf-8")
                # Find first-attempt approved decisions
                if "retry_count" in audit.columns and "outcome" in audit.columns:
                    first = audit[(audit["retry_count"] == 0) & (audit["outcome"].str.lower().isin(["approved", "accepted"]))]
                    if "proposed_skill" in first.columns:
                        actions = first["proposed_skill"].dropna().tolist()
                        ehe = compute_ehe(actions, k=4)
                        first_ehe_vals.append(ehe)
                elif "attempt" in audit.columns:
                    first = audit[audit["attempt"] == 1]
                    if "proposed_skill" in first.columns:
                        actions = first["proposed_skill"].dropna().tolist()
                        ehe = compute_ehe(actions, k=4)
                        first_ehe_vals.append(ehe)
            except Exception as e:
                print(f"  WARNING: {audit_path.name}: {e}")
                continue

        if first_ehe_vals:
            print(f"  {model_name:18s} {group}: first-attempt EHE = {np.mean(first_ehe_vals):.3f} ± {np.std(first_ehe_vals, ddof=1):.3f} (n={len(first_ehe_vals)})")
        else:
            print(f"  {model_name:18s} {group}: no first-attempt data found")

# ══════════════════════════════════════════════════════════════════════════
# 6. CONSTRAINT VIOLATION DETAILS
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("6. CONSTRAINT VIOLATION RATES (ungoverned Group A)")
print("=" * 90)

for model_name in MODELS.values():
    vr = violation_rates.get(model_name, [])
    if vr:
        print(f"  {model_name:18s}: {np.mean(vr)*100:.1f}% ± {np.std(vr, ddof=1)*100:.1f}% (per-run: {[f'{v*100:.1f}%' for v in vr]})")

# ══════════════════════════════════════════════════════════════════════════
# 7. SAVE TABLE 1 DATA AS CSV
# ══════════════════════════════════════════════════════════════════════════
out_csv = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\paper\tables\Table1_flood_3run_stats.csv")
pd.DataFrame(table1_data).to_csv(out_csv, index=False)
print(f"\nSaved: {out_csv}")

# ══════════════════════════════════════════════════════════════════════════
# 8. COMPARISON: OLD TABLE 1 (single run) vs NEW (3-run mean)
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("8. OLD vs NEW Table 1 comparison")
print("=" * 90)

old_table1 = {
    "Gemma-3 4B": {"a": 0.307, "v": 0.322, "b": 0.606, "c": 0.636},
    "Gemma-3 12B": {"a": 0.282, "v": 0.526, "b": 0.359, "c": 0.310},
    "Gemma-3 27B": {"a": 0.322, "v": 0.333, "b": 0.462, "c": 0.496},
    "Ministral 3B": {"a": 0.448, "v": 0.483, "b": 0.613, "c": 0.571},
    "Ministral 8B": {"a": 0.555, "v": 0.562, "b": 0.564, "c": 0.531},
    "Ministral 14B": {"a": 0.572, "v": 0.539, "b": 0.623, "c": 0.605},
}

print(f"  {'Model':>18s} | {'Old Ungov':>10s} | {'New Ungov':>14s} | {'Old Gov_B':>10s} | {'New Gov_B':>14s} | {'Old Gov_C':>10s} | {'New Gov_C':>14s}")
for model_name in MODELS.values():
    old = old_table1.get(model_name, {})
    a_new = results[model_name].get("Group_A", [])
    b_new = results[model_name].get("Group_B", [])
    c_new = results[model_name].get("Group_C", [])
    print(f"  {model_name:>18s} | {old.get('a', 0):.3f}     | {np.mean(a_new):.3f}±{np.std(a_new, ddof=1):.3f} | {old.get('b', 0):.3f}     | {np.mean(b_new):.3f}±{np.std(b_new, ddof=1):.3f} | {old.get('c', 0):.3f}     | {np.mean(c_new):.3f}±{np.std(c_new, ddof=1):.3f}")

print("\nP0 analysis complete.")
