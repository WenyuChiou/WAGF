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
        # AD = % of population with ANY adaptation (Elevation or Insurance or Relocated) at Yr 10
        final_yr = df['year'].max()
        final_state = df[df['year'] == final_yr]
        
        # Count non-trivial adaptations
        # Note: 'relocated' agents might be marked in 'cumulative_state' or 'relocated' column
        # We check specific columns.
        adapted = final_state[
            (final_state['elevated'] == True) | 
            (final_state['has_insurance'] == True) |
            (final_state['relocated'] == True)
        ]
        
        # Safe division
        total_agents = len(final_state)
        metrics["AD_AdaptationDensity"] = len(adapted) / total_agents if total_agents > 0 else 0.0
        
        # 4. Process Panic Coefficient (PC)
        # PC = Relocation Rate.
        relocated_count = len(final_state[final_state['relocated'] == True])
        metrics["PC_PanicCoefficient"] = relocated_count / total_agents if total_agents > 0 else 0.0
        metrics["TotalAgents"] = total_agents

    return metrics

if __name__ == "__main__":
    import argparse
    import csv
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, required=True, help="Root directory containing model results (e.g., results/JOH_FINAL)")
    parser.add_argument("--output", type=str, default="joh_metrics_summary.csv", help="Output CSV filename")
    args = parser.parse_args()
    
    root_path = Path(args.root)
    all_results = []
    
    # Walk through the directory to find model run folders (those with simulation_log.csv or audit_summary.json)
    print(f"\nSearching for runs in: {root_path}...")
    
    # Walk through the directory to find model run folders (those with simulation_log.csv or audit_summary.json)
    print(f"\nSearching for runs in: {root_path}...")
    
    # Recursive search for simulation_log.csv
    for log_file in root_path.rglob("simulation_log.csv"):
        run_dir = log_file.parent
        print(f" -> Processing: {run_dir.name} (Found log)")
        metrics = calculate_kpis(str(run_dir))
        if metrics:
            # Try to infer meaningful names
            # path: results/JOH_STRESS/goldfish/llama3_2_3b_strict
            # Group -> goldfish, Model -> llama3_2_3b_strict
            
            # Simple heuristic: parent of run_dir is Group, parent of that is Root
            relative_path = run_dir.relative_to(root_path)
            parts = relative_path.parts
            
            if len(parts) >= 2:
                group_name = parts[0]
                model_name = parts[1]
            elif len(parts) == 1:
                group_name = "Root"
                model_name = parts[0]
            else:
                group_name = "Unknown"
                model_name = "Unknown"

            metrics["Model"] = model_name
            metrics["Group"] = group_name
            metrics["RunPath"] = str(run_dir)
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
