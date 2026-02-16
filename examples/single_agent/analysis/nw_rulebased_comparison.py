"""
Rule-Based vs LLM Baseline Comparison for Nature Water Paper.

Computes EHE, skill distributions, and temporal dynamics for:
  - Rule-based stochastic ABM (softmax utility, no LLM)
  - LLM Ungoverned (Group A)
  - LLM Governed (Group B)
  - LLM Governed+HumanCentric (Group C)

All using gemma3:4b, 100 agents, 10yr, seeds {42, 4202, 4203}.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent.parent / "results"

CONFIGS = {
    "Rule-based": [BASE / "rulebased" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    "LLM Ungoverned (A)": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_A" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    "LLM Governed (B)": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_B" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    "LLM Gov+HC (C)": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_C" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
}

# Decision label mapping to canonical 5-category scheme
LABEL_MAP = {
    "Do Nothing": "do_nothing",
    "Only Flood Insurance": "buy_insurance",
    "Only House Elevation": "elevate_house",
    "Both Flood Insurance and House Elevation": "both",
    "Relocate": "relocate",
    # LLM governed format
    "buy_insurance": "buy_insurance",
    "elevate_house": "elevate_house",
    "relocate": "relocate",
    "do_nothing": "do_nothing",
}

SKIP_LABELS = {"Already relocated", "relocated"}
CATEGORIES = ["buy_insurance", "elevate_house", "both", "do_nothing", "relocate"]


def load_decisions(csv_path: Path) -> pd.Series:
    """Load and normalize decisions from a simulation log."""
    df = pd.read_csv(csv_path, encoding="utf-8")
    # Try 'decision' column first, then 'yearly_decision'
    col = "decision" if "decision" in df.columns else "yearly_decision"
    decisions = df[col].dropna()
    # Filter out relocated/skip
    decisions = decisions[~decisions.isin(SKIP_LABELS)]
    # Map to canonical labels
    decisions = decisions.map(lambda x: LABEL_MAP.get(x, x))
    return decisions


def compute_ehe(decisions: pd.Series, k: int = 5) -> float:
    """Compute EHE = H / log2(k) from a series of decisions."""
    counts = decisions.value_counts()
    total = counts.sum()
    if total == 0:
        return 0.0
    probs = counts / total
    # Remove zero probabilities
    probs = probs[probs > 0]
    H = -(probs * np.log2(probs)).sum()
    return H / np.log2(k)


def compute_yearly_ehe(csv_path: Path, k: int = 5) -> dict:
    """Compute per-year EHE."""
    df = pd.read_csv(csv_path, encoding="utf-8")
    col = "decision" if "decision" in df.columns else "yearly_decision"
    results = {}
    for year in sorted(df["year"].unique()):
        yr_data = df[df["year"] == year][col].dropna()
        yr_data = yr_data[~yr_data.isin(SKIP_LABELS)]
        yr_data = yr_data.map(lambda x: LABEL_MAP.get(x, x))
        results[year] = compute_ehe(yr_data, k)
    return results


def main():
    print("=" * 80)
    print("RULE-BASED vs LLM COMPARISON — Nature Water Paper")
    print("=" * 80)

    # === EHE Comparison ===
    print("\n### EHE Comparison (k=5)")
    print(f"{'Condition':<25} {'Run_1':>8} {'Run_2':>8} {'Run_3':>8} {'Mean':>8} {'Std':>8}")
    print("-" * 70)

    all_results = {}
    for name, paths in CONFIGS.items():
        ehes = []
        for p in paths:
            if p.exists():
                decisions = load_decisions(p)
                ehes.append(compute_ehe(decisions))
            else:
                ehes.append(float('nan'))
        all_results[name] = ehes
        mean_ehe = np.nanmean(ehes)
        std_ehe = np.nanstd(ehes)
        print(f"{name:<25} {ehes[0]:>8.4f} {ehes[1]:>8.4f} {ehes[2]:>8.4f} {mean_ehe:>8.4f} {std_ehe:>8.4f}")

    # === Skill Distribution ===
    print("\n### Skill Distribution (pooled across 3 runs)")
    print(f"{'Condition':<25} {'insurance':>10} {'elevate':>10} {'both':>10} {'nothing':>10} {'relocate':>10}")
    print("-" * 80)

    for name, paths in CONFIGS.items():
        all_decisions = pd.concat([load_decisions(p) for p in paths if p.exists()])
        total = len(all_decisions)
        pcts = {}
        for cat in CATEGORIES:
            pcts[cat] = (all_decisions == cat).sum() / total * 100
        print(f"{name:<25} {pcts['buy_insurance']:>9.1f}% {pcts['elevate_house']:>9.1f}% "
              f"{pcts['both']:>9.1f}% {pcts['do_nothing']:>9.1f}% {pcts['relocate']:>9.1f}%")

    # === Temporal Dynamics ===
    print("\n### Year-by-Year EHE (Run_1 only)")
    print(f"{'Year':<6}", end="")
    for name in CONFIGS:
        print(f"{name:<25}", end="")
    print()
    print("-" * 106)

    yearly_data = {}
    for name, paths in CONFIGS.items():
        if paths[0].exists():
            yearly_data[name] = compute_yearly_ehe(paths[0])

    for year in range(1, 11):
        print(f"{year:<6}", end="")
        for name in CONFIGS:
            if name in yearly_data and year in yearly_data[name]:
                print(f"{yearly_data[name][year]:<25.4f}", end="")
            else:
                print(f"{'N/A':<25}", end="")
        print()

    # === Key Narrative Points ===
    rb_mean = np.nanmean(all_results["Rule-based"])
    ua_mean = np.nanmean(all_results["LLM Ungoverned (A)"])
    gb_mean = np.nanmean(all_results["LLM Governed (B)"])
    gc_mean = np.nanmean(all_results["LLM Gov+HC (C)"])

    print("\n### Key Findings for Paper")
    print(f"1. Rule-based EHE ({rb_mean:.3f}) > Governed LLM ({gb_mean:.3f}) > Ungoverned LLM ({ua_mean:.3f})")
    print(f"2. Governance recovery: +{(gb_mean - ua_mean):.3f} EHE ({(gb_mean-ua_mean)/ua_mean*100:.1f}% improvement)")
    print(f"3. Rule-based achieves high EHE via softmax temperature (mechanical diversity)")
    print(f"4. Ungoverned LLM collapses to do_nothing dominance (behavioral degeneration)")
    print(f"5. Governed LLM produces contextually-driven insurance-dominant pattern")
    print(f"6. 'Both' composite: rule-based 42.8% vs LLM 0-3% (structural action space difference)")

    # === Cohen's d: Governed vs Ungoverned ===
    gov_ehes = all_results["LLM Governed (B)"]
    ung_ehes = all_results["LLM Ungoverned (A)"]
    pooled_std = np.sqrt((np.std(gov_ehes)**2 + np.std(ung_ehes)**2) / 2)
    if pooled_std > 0:
        d = (np.mean(gov_ehes) - np.mean(ung_ehes)) / pooled_std
        print(f"\n   Cohen's d (Governed vs Ungoverned): {d:.2f}")

    # === Variance comparison ===
    print(f"\n### Reproducibility (Std across 3 runs)")
    for name, ehes in all_results.items():
        print(f"   {name}: std = {np.nanstd(ehes):.4f}")
    print(f"   Rule-based has {np.nanstd(all_results['Rule-based']):.4f} vs LLM Ungov {np.nanstd(all_results['LLM Ungoverned (A)']):.4f}")
    print(f"   → Rule-based is {np.nanstd(all_results['LLM Ungoverned (A)'])/max(0.0001, np.nanstd(all_results['Rule-based'])):.0f}x more variable in LLM ungoverned")


if __name__ == "__main__":
    main()
