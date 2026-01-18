import pandas as pd
import numpy as np
from pathlib import Path

BASE_ROOT = Path(r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
# Models to analyze
MODELS = ["gemma3_4b", "llama3_2_3b", "deepseek_r1_8b", "gpt_oss_safeguard_20b"]

GROUPS = {
    "Group_A": "flood_adaptation_simulation_log.csv",
    "Group_B": "simulation_log.csv",
    "Group_C": "simulation_log.csv"
}
RUNS = ["Run_1", "Run_2", "Run_3"]

def analyze_stability():
    report_rows = []
    
    for model in MODELS:
        print(f"\n--- Analyzing Model: {model} ---")
        model_path = BASE_ROOT / model
        if not model_path.exists():
            print(f"Skipping {model} (Not found)")
            continue

        model_results = []
        for group_name, log_filename in GROUPS.items():
            group_data = []
            
            for run in RUNS:
                log_path = model_path / group_name / run / log_filename
                if not log_path.exists():
                    continue
                    
                try:
                    df = pd.read_csv(log_path)
                    # Count adapted agents per year
                    if 'elevated' in df.columns:
                        adaptation_by_year = df.groupby('year')['elevated'].apply(lambda x: (x == True).sum()).reset_index()
                        adaptation_by_year.columns = ['year', 'adapted_count']
                        group_data.append(adaptation_by_year)
                except Exception as e:
                    print(f"Error reading {log_path}: {e}")
            
            if not group_data:
                report_rows.append({"Model": model, "Group": group_name, "SD": "N/A"})
                continue
                
            group_df = pd.concat(group_data)
            # Calculate Unstability (Inter-run SD roughly approximated by SD of counts across all datapoints or grouped by year)
            # Better metric based on previous script: Group by Year -> std -> average across years
            try:
                yearly_stats = group_df.groupby('year')['adapted_count'].agg(['std']).reset_index()
                avg_sd = yearly_stats['std'].mean()
                print(f"  {group_name}: SD = {avg_sd:.2f}")
                report_rows.append({"Model": model, "Group": group_name, "SD": round(avg_sd, 2)})
            except:
                 report_rows.append({"Model": model, "Group": group_name, "SD": "Err"})

    # Print Comparative Table
    print("\n\n=== FINAL COMPARISON (Stochastic Instability SD) ===")
    df_res = pd.DataFrame(report_rows)
    # Pivot for readability
    pivot = df_res.pivot(index='Group', columns='Model', values='SD')
    print(pivot)
    
    # Save
    pivot.to_csv(BASE_ROOT / "comparison_all_models_sd.csv")
    print(f"\nSaved to {BASE_ROOT / 'comparison_all_models_sd.csv'}")

if __name__ == "__main__":
    analyze_stability()
