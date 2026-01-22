"""
extract_macro_3x3_metrics.py - Consolidate results from the 3x3 model benchmark.
Tiers: Small vs Large | Groups: A, B, C
"""

import os
import pandas as pd
import numpy as np
import json
from pathlib import Path

# --- Configuration ---
BASE_RESULTS = Path("results/MACRO_3X3")
OUTPUT_SUMMARY = BASE_RESULTS / "macro_3x3_summary.csv"
# ---------------------

def calculate_adaptation_rate(df):
    """Calculate adaptation rate for the final year."""
    if df.empty: return 0.0
    final_year = df['year'].max()
    final_df = df[df['year'] == final_year]
    if len(final_df) == 0: return 0.0
    
    # Adaption = elevated OR has_insurance
    # Parity with classification logic
    adapted = final_df[(final_df['elevated'] == True) | (final_df['has_insurance'] == True)]
    return len(adapted) / len(final_df)

def calculate_cv(df):
    """Calculate Coefficient of Variation of yearly adaptation rates (Behavioral Stability)."""
    if df.empty: return 0.0
    yearly_rates = []
    for year in range(1, df['year'].max() + 1):
        y_df = df[df['year'] == year]
        if len(y_df) == 0: continue
        rate = len(y_df[(y_df['elevated'] == True) | (y_df['has_insurance'] == True)]) / len(y_df)
        yearly_rates.append(rate)
    
    if len(yearly_rates) < 2: return 0.0
    mean = np.mean(yearly_rates)
    std = np.std(yearly_rates)
    return (std / mean) if mean > 0 else 0.0

def main():
    print("--- Macro 3x3 Metric Extraction ---")
    all_results = []
    
    if not BASE_RESULTS.exists():
        print(f"Error: {BASE_RESULTS} not found.")
        return

    for tier in ["Small", "Large"]:
        tier_path = BASE_RESULTS / tier
        if not tier_path.exists(): continue
        
        for model_dir in tier_path.iterdir():
            if not model_dir.is_dir(): continue
            model_name = model_dir.name
            
            for group in ["Group_A", "Group_B", "Group_C"]:
                log_path = model_dir / group / "Run_1" / "simulation_log.csv"
                
                if not log_path.exists():
                    # Fallback for benchmark runs that might produce flood_adaptation_simulation_log.csv
                    log_path = model_dir / group / "Run_1" / "flood_adaptation_simulation_log.csv"
                
                if log_path.exists():
                    print(f" Processing {tier}/{model_name}/{group}...")
                    df = pd.read_csv(log_path)
                    
                    metrics = {
                        "Tier": tier,
                        "Model": model_name,
                        "Group": group,
                        "AdaptationRate": calculate_adaptation_rate(df),
                        "Stability_CV": calculate_cv(df),
                        "NumAgents": len(df['agent_id'].unique()) if 'agent_id' in df.columns else 0,
                        "MaxYear": df['year'].max()
                    }
                    all_results.append(metrics)
                else:
                    print(f" [Missing] {tier}/{model_name}/{group}")

    if all_results:
        final_df = pd.DataFrame(all_results)
        final_df.to_csv(OUTPUT_SUMMARY, index=False)
        print(f"\nSummary saved to {OUTPUT_SUMMARY}")
        
        # Display pivot table
        pivot = final_df.pivot_table(index=["Tier", "Model"], columns="Group", values="AdaptationRate")
        print("\nAdaptation Rate Matrix:")
        print(pivot.applymap(lambda x: f"{x:.1%}" if pd.notnull(x) else "N/A"))
        
        pivot_cv = final_df.pivot_table(index=["Tier", "Model"], columns="Group", values="Stability_CV")
        print("\nBehavioral Stability (CV) Matrix (Lower is better):")
        print(pivot_cv.applymap(lambda x: f"{x:.3f}" if pd.notnull(x) else "N/A"))
        
    else:
        print("No results found to process.")

if __name__ == "__main__":
    main()
