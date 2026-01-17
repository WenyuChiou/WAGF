import pandas as pd
import json
from pathlib import Path
import os
import sys

# Discovery
SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def calculate_kpis(result_dir: str):
    """
    Unified KPI Evaluator for JOH Technical Note.
    Processes simulation_log.csv and audit_summary.json.
    """
    run_dir = Path(result_dir)
    log_path = run_dir / "simulation_log.csv"
    summary_path = run_dir / "audit_summary.json"
    
    if not log_path.exists():
        return None

    metrics = {
        "RS_RationalityScore": 0.0,
        "AD_AdaptationDensity": 0.0,
        "PC_PanicCoefficient": 0.0,
        "FI_FidelityIndex": "N/A"
    }

    # 1. Load Data
    df = pd.read_csv(log_path)
    total_agents = len(df['agent_id'].unique())
    final_yr = df['year'].max()
    final_state = df[df['year'] == final_yr]

    # 2. Process Rationality Score (RS)
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            gov = json.load(f)
            total = gov.get("total_evaluations", total_agents * final_yr)
            interventions = gov.get("total_blocking_events", 0)
            metrics["RS_RationalityScore"] = (total - interventions) / max(1, total)
            metrics["Interventions"] = interventions
    else:
        metrics["RS_RationalityScore"] = 1.0 # If no governance summary, assume 1.0 or N/A
        metrics["Interventions"] = 0

    # 3. Process Adaptation Density (AD)
    # Count non-trivial adaptations at Yr 10
    adapted = final_state[
        (final_state['elevated'] == True) | 
        (final_state['has_insurance'] == True) |
        (final_state['relocated'] == True)
    ]
    metrics["AD_AdaptationDensity"] = len(adapted) / total_agents if total_agents > 0 else 0.0
    
    # 4. Process Panic Coefficient (PC)
    relocated_count = len(final_state[final_state['relocated'] == True])
    metrics["PC_PanicCoefficient"] = relocated_count / total_agents if total_agents > 0 else 0.0
    metrics["TotalAgents"] = total_agents

    return metrics

if __name__ == "__main__":
    import argparse
    import csv
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=str(SCRIPT_DIR.parent / "results"), help="Root directory containing model results")
    parser.add_argument("--output", type=str, default="joh_metrics_summary.csv", help="Output CSV filename")
    args = parser.parse_args()
    
    root_path = Path(args.root)
    if not root_path.is_absolute():
        root_path = SCRIPT_DIR.parent / root_path

    all_results = []
    print(f"\nSearching for runs in: {root_path}...")
    
    # Recursive search for simulation_log.csv
    for log_file in root_path.rglob("simulation_log.csv"):
        run_dir = log_file.parent
        # Avoid processing reports or raw subdirs as root
        if "reports" in run_dir.parts or "raw" in run_dir.parts:
            continue
            
        print(f" -> Processing: {run_dir.relative_to(root_path)}")
        metrics = calculate_kpis(str(run_dir))
        if metrics:
            # Heuristic to find Group and Model names
            rel = run_dir.relative_to(root_path)
            parts = rel.parts
            if len(parts) >= 2:
                metrics["Group"] = parts[0]
                metrics["Model"] = parts[1]
            elif len(parts) == 1:
                metrics["Group"] = "Root"
                metrics["Model"] = parts[0]
            else:
                metrics["Group"] = "Unknown"
                metrics["Model"] = "Unknown"

            metrics["RunPath"] = str(run_dir)
            all_results.append(metrics)

    # Export to CSV
    if all_results:
        output_path = REPORT_DIR / args.output
        keys = ["Model", "Group", "RS_RationalityScore", "AD_AdaptationDensity", "PC_PanicCoefficient", "Interventions", "TotalAgents", "RunPath"]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
            writer.writeheader()
            for row in all_results:
                writer.writerow(row)
                
        print("\n" + "="*60)
        print(f" BATCH PROCESSING COMPLETE. metrics saved to: {output_path}")
        print("="*60)
        
        # Print Summary Table
        df_summary = pd.DataFrame(all_results)
        print(df_summary[["Model", "Group", "RS_RationalityScore", "AD_AdaptationDensity", "PC_PanicCoefficient"]].sort_values("Group").to_string(index=False))
    else:
        print(f"No valid runs found in {root_path}.")
