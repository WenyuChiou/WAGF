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
    summary_path = run_path / "governance_summary.json"
    
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, required=True, help="Path to result directory (e.g., results/JOH_Macro/llama3_2_3b_strict)")
    args = parser.parse_args()
    
    results = calculate_kpis(args.dir)
    print("\n" + "="*40)
    print(f" JOH PERFORMANCE REPORT: {args.dir}")
    print("="*40)
    for k, v in results.items():
        if isinstance(v, float):
            print(f"{k:25}: {v:.2%}")
        else:
            print(f"{k:25}: {v}")
    print("="*40 + "\n")
