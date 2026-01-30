"""Compute Shannon entropy for Gemma 3 flood ABM experiment data.

Reads simulation_log.csv for each model × group × year and computes:
- Active_Agents: agents not yet relocated
- Shannon_Entropy: -sum(p_i * log2(p_i))
- Shannon_Entropy_Norm: entropy / log2(5)
- Dominant_Action, Dominant_Freq

Output matches yearly_entropy_audited.csv format.
"""

import math
import os
from pathlib import Path

import pandas as pd

BASE = Path("examples/single_agent/results/JOH_FINAL")
OUT = Path("examples/single_agent/analysis/SQ2_Final_Results/gemma3_entropy_audited.csv")

MODELS = ["gemma3_4b", "gemma3_12b", "gemma3_27b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]

# Canonical action labels for entropy (exclude "Already relocated")
ACTION_LABELS = {
    "Do Nothing": "DoNothing",
    "Only Flood Insurance": "Insurance",
    "Only House Elevation": "Elevation",
    "Both Flood Insurance and House Elevation": "Both",
    "Relocate": "Relocate",
}
NUM_ACTIONS = len(ACTION_LABELS)  # 5
LOG2_K = math.log2(NUM_ACTIONS)


def shannon_entropy(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return h


def process_file(model: str, group: str, csv_path: Path) -> list[dict]:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    # Normalise column names (strip BOM / whitespace)
    df.columns = df.columns.str.strip()

    # Handle two column naming conventions:
    # Group A: "decision" column
    # Groups B/C: "cumulative_state" column
    if "decision" in df.columns:
        decision_col = "decision"
    elif "cumulative_state" in df.columns:
        decision_col = "cumulative_state"
    else:
        raise KeyError(f"No decision column found. Columns: {list(df.columns)}")

    rows = []
    for year in sorted(df["year"].unique()):
        year_df = df[df["year"] == year]

        # Filter out "Already relocated"
        active_df = year_df[year_df[decision_col] != "Already relocated"]
        active_agents = len(active_df)

        if active_agents == 0:
            rows.append({
                "Model": model,
                "Group": group,
                "Year": int(year),
                "Active_Agents": 0,
                "Shannon_Entropy": 0.0,
                "Shannon_Entropy_Norm": 0.0,
                "Dominant_Action": "N/A",
                "Dominant_Freq": 0.0,
            })
            continue

        # Count decisions
        counts = {}
        for raw_decision, label in ACTION_LABELS.items():
            counts[label] = len(active_df[active_df[decision_col] == raw_decision])

        h = shannon_entropy(counts)
        h_norm = h / LOG2_K if LOG2_K > 0 else 0.0

        # Dominant action
        dominant_label = max(counts, key=counts.get)
        dominant_freq = round(counts[dominant_label] / active_agents, 4)

        rows.append({
            "Model": model,
            "Group": group,
            "Year": int(year),
            "Active_Agents": active_agents,
            "Shannon_Entropy": round(h, 4),
            "Shannon_Entropy_Norm": round(h_norm, 4),
            "Dominant_Action": dominant_label,
            "Dominant_Freq": dominant_freq,
        })

    return rows


def main():
    all_rows = []

    for model in MODELS:
        for group in GROUPS:
            csv_path = BASE / model / group / "Run_1" / "simulation_log.csv"
            if not csv_path.exists():
                print(f"  SKIP {model}/{group} — file not found")
                continue

            size = csv_path.stat().st_size
            if size < 500:
                print(f"  SKIP {model}/{group} — file too small ({size} bytes)")
                continue

            print(f"  Processing {model}/{group} ...")
            try:
                rows = process_file(model, group, csv_path)
                all_rows.extend(rows)
                print(f"    -> {len(rows)} year-rows computed")
            except Exception as e:
                print(f"    ERROR: {e}")

    if not all_rows:
        print("No data processed!")
        return

    result = pd.DataFrame(all_rows)
    os.makedirs(OUT.parent, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f"\nSaved {len(result)} rows to {OUT}")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
