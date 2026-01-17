import pandas as pd
import json
from pathlib import Path
import os
import sys

def calculate_kpis(result_dir: str):
    """
    Unified KPI Evaluator for JOH Technical Note.
    Processes simulation_log.csv and governance_summary.json.
    """
    run_path = Path(result_dir)
    if not run_path.exists():
        print(f"Error: Directory {result_dir} not found.")
        return

    # 1. Load Data
    log_path = run_path / "simulation_log.csv"
    summary_path = run_path / "audit_summary.json"
    
    metrics = {
        "RS_RationalityScore": 0,
        "AD_AdaptationDensity": 0,
        "PC_PanicCoefficient": 0,
        "FI_FidelityIndex": "N/A (Requires manual trace review)"
    }

    # 2. Process Rationality Score (RS)
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            gov = json.load(f)
            # RS = (Total Requests - Interventions) / Total Requests
            total = gov.get("total_evaluations", 1000) # Fallback to 100 agents * 10 years
            interventions = gov.get("total_blocking_events", 0)
            metrics["RS_RationalityScore"] = (total - interventions) / total
            metrics["Interventions"] = interventions

    # 3. Process Adaptation Density (AD)
    if log_path.exists():
        df = pd.read_csv(log_path)
        # AD = % of population with ANY adaptation (Elevation or Insurance) at Yr 10
        final_yr = df['year'].max()
        final_state = df[df['year'] == final_yr]
        
        # Count non-trivial adaptations
        adapted = final_state[
            (final_state['elevated'] == True) | 
            (final_state['has_insurance'] == True) |
            (final_state['relocated'] == True)
        ]
        metrics["AD_AdaptationDensity"] = len(adapted) / len(final_state) if len(final_state) > 0 else 0
        
        # 4. Process Panic Coefficient (PC)
        # PC = Relocation Rate in low-threat scenarios.
        # For simplicity in this script, we look at total relocation rate.
        relocated = final_state[final_state['relocated'] == True]
        metrics["PC_PanicCoefficient"] = len(relocated) / len(final_state) if len(final_state) > 0 else 0

    return metrics

if __name__ == "__main__":
    import argparse
    import csv
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, required=True, help="Root directory containing model results (e.g., results/JOH_FINAL)")
    args = parser.parse_args()
    
    root_path = Path(args.root)
    all_results = []
    
    # Walk through the directory to find model run folders (those with simulation_log.csv or audit_summary.json)
    print(f"\nSearching for runs in: {root_path}...")
    
    for model_dir in root_path.iterdir():
        if model_dir.is_dir():
            # Check for Group subfolders
            for group_dir in model_dir.iterdir():
                if group_dir.is_dir() and "Group_" in group_dir.name:
                    # Found a Group folder (e.g., Group_B_Governance_Window)
                    # The actual run is usually a subdirectory inside this, e.g., llama3_2_3b_strict
                    # Or sometimes the files are directly here. Let's look for the run folder inside.
                    
                    found_run = False
                    for run_subdir in group_dir.iterdir():
                        if run_subdir.is_dir() and "strict" in run_subdir.name:
                            # This is the target run folder
                            print(f" -> Processing: {run_subdir.name} ({group_dir.name})")
                            metrics = calculate_kpis(str(run_subdir))
                            if metrics:
                                metrics["Model"] = model_dir.name
                                metrics["Group"] = group_dir.name
                                metrics["RunPath"] = str(run_subdir)
                                all_results.append(metrics)
                            found_run = True
                            
                    if not found_run:
                        # Fallback: Check if the group dir itself is the run dir (older structure)
                        if (group_dir / "simulation_log.csv").exists():
                             print(f" -> Processing: {group_dir.name} (Direct)")
                             metrics = calculate_kpis(str(group_dir))
                             if metrics:
                                 metrics["Model"] = model_dir.name
                                 metrics["Group"] = group_dir.name
                                 metrics["RunPath"] = str(group_dir)
                                 all_results.append(metrics)

    # Export to CSV
    if all_results:
        output_csv = root_path / "joh_metrics_summary.csv"
        keys = ["Model", "Group", "RS_RationalityScore", "AD_AdaptationDensity", "PC_PanicCoefficient", "Interventions", "FI_FidelityIndex", "RunPath"]
        
        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in all_results:
                # Filter row to only match keys
                clean_row = {k: row.get(k, "N/A") for k in keys}
                writer.writerow(clean_row)
                
        print("\n" + "="*60)
        print(f" BATCH PROCESSING COMPLETE. metrics saved to: {output_csv}")
        print("="*60)
        
        # Print Summary Table to Console
        df_summary = pd.DataFrame(all_results)
        if not df_summary.empty:
            print(df_summary[["Model", "Group", "RS_RationalityScore", "AD_AdaptationDensity"]].to_string(index=False))
    else:
        print("No valid runs found.")
