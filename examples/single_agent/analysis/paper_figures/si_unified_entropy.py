"""
SAGE Paper — SI Table S1: Unified Entropy Dataset
===================================================
Merges all entropy data (DeepSeek R1 + Gemma 3) into a single CSV
with consistent column names for the Supporting Information.

Output: si_table_s1_unified_entropy.csv

Usage:
  python si_unified_entropy.py
"""

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
SQ2 = SCRIPT_DIR.parents[0] / "SQ2_Final_Results"
CORRECTED = SCRIPT_DIR / "corrected_entropy_gemma3_4b.csv"

# Model metadata
MODEL_META = {
    "deepseek_r1_1_5b": {"Family": "DeepSeek R1", "Size_B": 1.5},
    "deepseek_r1_8b":   {"Family": "DeepSeek R1", "Size_B": 8},
    "deepseek_r1_14b":  {"Family": "DeepSeek R1", "Size_B": 14},
    "deepseek_r1_32b":  {"Family": "DeepSeek R1", "Size_B": 32},
    "gemma3_4b":        {"Family": "Gemma 3",     "Size_B": 4},
    "gemma3_12b":       {"Family": "Gemma 3",     "Size_B": 12},
    "gemma3_27b":       {"Family": "Gemma 3",     "Size_B": 27},
}


def main():
    frames = []

    # Load DeepSeek data
    ds_path = SQ2 / "yearly_entropy_audited.csv"
    if ds_path.exists():
        df = pd.read_csv(ds_path)
        df["Family"] = df["Model"].map(lambda m: MODEL_META.get(m, {}).get("Family", ""))
        df["Size_B"] = df["Model"].map(lambda m: MODEL_META.get(m, {}).get("Size_B", 0))
        frames.append(df)
        print(f"Loaded {len(df)} rows from DeepSeek data")
    else:
        print(f"WARNING: {ds_path} not found")

    # Load Gemma data
    gm_path = SQ2 / "gemma3_entropy_audited.csv"
    if gm_path.exists():
        df = pd.read_csv(gm_path)
        df["Family"] = df["Model"].map(lambda m: MODEL_META.get(m, {}).get("Family", ""))
        df["Size_B"] = df["Model"].map(lambda m: MODEL_META.get(m, {}).get("Size_B", 0))
        frames.append(df)
        print(f"Loaded {len(df)} rows from Gemma data")
    else:
        print(f"WARNING: {gm_path} not found")

    if not frames:
        print("No data found. Exiting.")
        sys.exit(1)

    unified = pd.concat(frames, ignore_index=True)

    # Merge corrected entropy for Gemma 4B
    if CORRECTED.exists():
        corr = pd.read_csv(CORRECTED)
        corr_cols = corr[["Model", "Group", "Year", "Corrected_H_norm",
                          "Hallucination_Count", "Hallucination_Rate", "EBE"]]
        unified = unified.merge(
            corr_cols,
            on=["Model", "Group", "Year"],
            how="left"
        )
        print(f"Merged corrected entropy for {len(corr)} rows")
    else:
        unified["Corrected_H_norm"] = None
        unified["Hallucination_Count"] = None
        unified["Hallucination_Rate"] = None
        unified["EBE"] = None

    # Sort
    unified = unified.sort_values(
        ["Family", "Size_B", "Group", "Year"]
    ).reset_index(drop=True)

    # Reorder columns
    col_order = [
        "Family", "Model", "Size_B", "Group", "Year", "Active_Agents",
        "Shannon_Entropy", "Shannon_Entropy_Norm",
        "Corrected_H_norm", "Hallucination_Count", "Hallucination_Rate", "EBE",
        "Dominant_Action", "Dominant_Freq"
    ]
    unified = unified[[c for c in col_order if c in unified.columns]]

    # Save
    out_path = SCRIPT_DIR / "si_table_s1_unified_entropy.csv"
    unified.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")
    print(f"Total rows: {len(unified)}")

    # Summary
    print("\n--- Summary by Model × Group ---")
    summary = unified.groupby(["Family", "Model", "Group"]).agg(
        Years=("Year", "count"),
        Mean_H_norm=("Shannon_Entropy_Norm", "mean"),
        Mean_EBE=("EBE", "mean"),
    ).reset_index()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
