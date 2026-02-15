#!/usr/bin/env python3
"""
Nature Water P0: k sensitivity analysis for EHE normalization.

Key question: Ungoverned agents can choose "both" (insurance+elevation in one year).
Governed agents are restricted to single-skill-per-turn (k=4).

Three scenarios:
  S1: k_ungov=5, k_gov=4 (current — different normalizers)
  S2: k=4 for all (remap "both" → split into two actions, or treat as elevate_house)
  S3: k=5 for all (governed agents COULD do both but governance prevents it)
  S4: k=4 for all, "both" counted as TWO separate decisions (insurance + elevation)

Also: cumulative-state vs annual-behavior framing analysis.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

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

CANONICAL = {
    "Do Nothing": "do_nothing", "Do nothing": "do_nothing", "do nothing": "do_nothing",
    "Only Flood Insurance": "buy_insurance", "Buy flood insurance": "buy_insurance",
    "buy flood insurance": "buy_insurance",
    "Only House Elevation": "elevate_house", "Elevate the house": "elevate_house",
    "elevate the house": "elevate_house",
    "Both Flood Insurance and House Elevation": "both",
    "Relocate": "relocate", "relocate": "relocate",
    "Already relocated": "relocated",
    "do_nothing": "do_nothing", "buy_insurance": "buy_insurance",
    "elevate_house": "elevate_house", "relocated": "relocated",
}


def load_actions(model_dir, group, run):
    """Load and normalize actions from a single run."""
    path = BASE / model_dir / group / run / "simulation_log.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="utf-8")
    col = "yearly_decision" if "yearly_decision" in df.columns else "decision"
    df["action"] = df[col].map(lambda x: CANONICAL.get(str(x).strip(), str(x).strip().lower()))
    # Filter terminal state
    active = df[df["action"] != "relocated"]
    return active["action"].tolist()


def compute_ehe(actions, k):
    """EHE with specified k."""
    counts = Counter(actions)
    counts.pop("relocated", None)
    if not counts:
        return 0.0
    total = sum(counts.values())
    probs = np.array([c / total for c in counts.values()])
    probs = probs[probs > 0]
    H = -np.sum(probs * np.log2(probs))
    H_max = np.log2(k) if k > 1 else 1.0
    return H / H_max


def remap_both_to_elevate(actions):
    """S2: Remap 'both' → 'elevate_house' (most conservative merge)."""
    return [a if a != "both" else "elevate_house" for a in actions]


def split_both(actions):
    """S4: Split 'both' into two separate decisions: insurance + elevation."""
    out = []
    for a in actions:
        if a == "both":
            out.extend(["buy_insurance", "elevate_house"])
        else:
            out.append(a)
    return out


np.random.seed(42)

# ══════════════════════════════════════════════════════════════════════════
# COLLECT ALL RUNS
# ══════════════════════════════════════════════════════════════════════════
all_data = {}  # model -> group -> [actions_run1, actions_run2, actions_run3]

for model_dir, model_name in MODELS.items():
    all_data[model_name] = {}
    for group in GROUPS:
        runs_data = []
        for run in RUNS:
            actions = load_actions(model_dir, group, run)
            if actions:
                runs_data.append(actions)
        all_data[model_name][group] = runs_data

# ══════════════════════════════════════════════════════════════════════════
# "BOTH" FREQUENCY ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
print("=" * 100)
print("0. 'BOTH' ACTION FREQUENCY IN UNGOVERNED RUNS")
print("=" * 100)

total_decisions = 0
total_both = 0
for model_name in MODELS.values():
    for run_actions in all_data[model_name].get("Group_A", []):
        n = len(run_actions)
        n_both = sum(1 for a in run_actions if a == "both")
        total_decisions += n
        total_both += n_both
    n_runs = len(all_data[model_name].get("Group_A", []))
    model_both = sum(sum(1 for a in r if a == "both") for r in all_data[model_name].get("Group_A", []))
    model_total = sum(len(r) for r in all_data[model_name].get("Group_A", []))
    pct = model_both / model_total * 100 if model_total > 0 else 0
    print(f"  {model_name:18s}: {model_both:4d}/{model_total:4d} = {pct:5.1f}% 'both' actions")

print(f"\n  TOTAL: {total_both}/{total_decisions} = {total_both/total_decisions*100:.1f}% 'both' actions across all ungoverned runs")

# ══════════════════════════════════════════════════════════════════════════
# SCENARIO ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
scenarios = {
    "S1: k_ungov=5, k_gov=4 (current)": {"k_a": 5, "k_bc": 4, "remap": None},
    "S2: k=4, both→elevate": {"k_a": 4, "k_bc": 4, "remap": "elevate"},
    "S3: k=5 for all": {"k_a": 5, "k_bc": 5, "remap": None},
    "S4: k=4, both→split(ins+elev)": {"k_a": 4, "k_bc": 4, "remap": "split"},
}

for scenario_name, cfg in scenarios.items():
    print(f"\n{'=' * 100}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'=' * 100}")

    header = f"{'Model':>18s} | {'Ungov EHE':>14s} | {'Gov B EHE':>14s} | {'Gov C EHE':>14s} | {'Delta(best-ungov)':>18s} | {'Scaffolding':>12s}"
    print(f"\n{header}")
    print("-" * len(header))

    scaffolding_count = 0
    all_deltas = []

    for model_name in MODELS.values():
        # Ungoverned
        a_ehe_vals = []
        for run_actions in all_data[model_name].get("Group_A", []):
            actions = list(run_actions)
            if cfg["remap"] == "elevate":
                actions = remap_both_to_elevate(actions)
            elif cfg["remap"] == "split":
                actions = split_both(actions)
            a_ehe_vals.append(compute_ehe(actions, cfg["k_a"]))

        # Governed B
        b_ehe_vals = []
        for run_actions in all_data[model_name].get("Group_B", []):
            b_ehe_vals.append(compute_ehe(list(run_actions), cfg["k_bc"]))

        # Governed C
        c_ehe_vals = []
        for run_actions in all_data[model_name].get("Group_C", []):
            c_ehe_vals.append(compute_ehe(list(run_actions), cfg["k_bc"]))

        a_mean = np.mean(a_ehe_vals) if a_ehe_vals else np.nan
        a_sd = np.std(a_ehe_vals, ddof=1) if len(a_ehe_vals) > 1 else 0
        b_mean = np.mean(b_ehe_vals) if b_ehe_vals else np.nan
        b_sd = np.std(b_ehe_vals, ddof=1) if len(b_ehe_vals) > 1 else 0
        c_mean = np.mean(c_ehe_vals) if c_ehe_vals else np.nan
        c_sd = np.std(c_ehe_vals, ddof=1) if len(c_ehe_vals) > 1 else 0

        best_gov = max(b_mean, c_mean)
        delta = best_gov - a_mean
        all_deltas.append(delta)

        scaff = "Yes" if delta > 0.05 else ("Reversed" if delta < -0.05 else "Marginal")
        if delta > 0.05:
            scaffolding_count += 1

        print(f"{model_name:>18s} | {a_mean:.3f}±{a_sd:.3f} | {b_mean:.3f}±{b_sd:.3f} | {c_mean:.3f}±{c_sd:.3f} | {delta:+.3f}            | {scaff:>12s}")

    all_deltas = np.array(all_deltas)
    print(f"\n  Scaffolding: {scaffolding_count}/6 models")
    print(f"  Mean delta: {np.mean(all_deltas):+.3f} ± {np.std(all_deltas, ddof=1):.3f}")

    # Bootstrap CI on pooled delta
    boot_means = [np.mean(np.random.choice(all_deltas, size=len(all_deltas), replace=True)) for _ in range(10000)]
    ci = np.percentile(boot_means, [2.5, 97.5])
    print(f"  Pooled bootstrap 95% CI: [{ci[0]:.3f}, {ci[1]:.3f}]")

# ══════════════════════════════════════════════════════════════════════════
# CUMULATIVE STATE vs ANNUAL BEHAVIOR ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 100}")
print("CUMULATIVE STATE vs ANNUAL BEHAVIOR FRAMING")
print("=" * 100)

print("""
  ANNUAL BEHAVIOR FRAMING (k depends on what agents CAN choose each year):
    - Each year, agents choose ONE action from their available set
    - Ungoverned: {do_nothing, buy_insurance, elevate_house, relocate, both} → k=5
    - Governed: {do_nothing, buy_insurance, elevate_house, relocate} → k=4
    - Problem: Different k values → EHE not directly comparable
    - "both" is a valid annual choice — the agent chose to do two things this year

  CUMULATIVE STATE FRAMING (k = distinct protection strategies):
    - What matters is the PROTECTION STATE the agent achieves
    - States: {unprotected, insured, elevated, insured+elevated, relocated}
    - k=5 for everyone (same outcome space)
    - But governed agents CAN reach insured+elevated state across multiple years
    - "both" just means they reached that state in one year instead of two

  RECOMMENDATION DIMENSIONS:
    1. If k differs → scaffolding comparison is confounded by normalization
    2. If k=4 for all → "both" must be assigned to an existing category
    3. If k=5 for all → governed agents get penalized (they can't do "both")
    4. Most conservative: Report BOTH k=4 and k=5 as sensitivity check
""")

# ══════════════════════════════════════════════════════════════════════════
# SENSITIVITY SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 100}")
print("SENSITIVITY SUMMARY: Scaffolding count and pooled delta by scenario")
print("=" * 100)

print(f"\n  {'Scenario':45s} | {'Scaff':>5s} | {'Mean Δ':>8s} | {'95% CI':>18s} | {'CI excludes 0?':>15s}")
print("  " + "-" * 100)

for scenario_name, cfg in scenarios.items():
    all_deltas = []
    scaff_count = 0
    for model_name in MODELS.values():
        a_ehe = []
        for run_actions in all_data[model_name].get("Group_A", []):
            actions = list(run_actions)
            if cfg["remap"] == "elevate":
                actions = remap_both_to_elevate(actions)
            elif cfg["remap"] == "split":
                actions = split_both(actions)
            a_ehe.append(compute_ehe(actions, cfg["k_a"]))

        b_ehe = [compute_ehe(list(r), cfg["k_bc"]) for r in all_data[model_name].get("Group_B", [])]
        c_ehe = [compute_ehe(list(r), cfg["k_bc"]) for r in all_data[model_name].get("Group_C", [])]

        a_m = np.mean(a_ehe) if a_ehe else 0
        best = max(np.mean(b_ehe) if b_ehe else 0, np.mean(c_ehe) if c_ehe else 0)
        d = best - a_m
        all_deltas.append(d)
        if d > 0.05:
            scaff_count += 1

    all_deltas = np.array(all_deltas)
    boot = [np.mean(np.random.choice(all_deltas, size=len(all_deltas), replace=True)) for _ in range(10000)]
    ci = np.percentile(boot, [2.5, 97.5])
    excludes = "YES" if ci[0] > 0 else "NO"

    print(f"  {scenario_name:45s} | {scaff_count:>3d}/6 | {np.mean(all_deltas):+.3f}  | [{ci[0]:+.3f}, {ci[1]:+.3f}] | {excludes:>15s}")

# ══════════════════════════════════════════════════════════════════════════
# PER-MODEL ROBUSTNESS: Does scaffolding direction flip across scenarios?
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 100}")
print("PER-MODEL ROBUSTNESS: Does scaffolding direction change across scenarios?")
print("=" * 100)

print(f"\n  {'Model':>18s}", end="")
for sn in scenarios:
    short = sn.split(":")[0]
    print(f" | {short:>18s}", end="")
print()
print("  " + "-" * 100)

for model_name in MODELS.values():
    print(f"  {model_name:>18s}", end="")
    for scenario_name, cfg in scenarios.items():
        a_ehe = []
        for run_actions in all_data[model_name].get("Group_A", []):
            actions = list(run_actions)
            if cfg["remap"] == "elevate":
                actions = remap_both_to_elevate(actions)
            elif cfg["remap"] == "split":
                actions = split_both(actions)
            a_ehe.append(compute_ehe(actions, cfg["k_a"]))

        b_ehe = [compute_ehe(list(r), cfg["k_bc"]) for r in all_data[model_name].get("Group_B", [])]
        c_ehe = [compute_ehe(list(r), cfg["k_bc"]) for r in all_data[model_name].get("Group_C", [])]

        a_m = np.mean(a_ehe) if a_ehe else 0
        best = max(np.mean(b_ehe) if b_ehe else 0, np.mean(c_ehe) if c_ehe else 0)
        d = best - a_m
        label = "+" if d > 0.05 else ("-" if d < -0.05 else "~")
        print(f" | {d:+.3f} ({label})        ", end="")
    print()

print("\n  Legend: + = scaffolding (>0.05), ~ = marginal, - = reversed (<-0.05)")
print("\nSensitivity analysis complete.")
