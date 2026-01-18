import pandas as pd
import numpy as np
from pathlib import Path

BASE_PATH = Path(r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b")
GROUPS = {
    "Group_A": "flood_adaptation_simulation_log.csv",
    "Group_B": "simulation_log.csv",
    "Group_C": "simulation_log.csv"
}
RUNS = ["Run_1", "Run_2", "Run_3"]

def analyze_stability():
    all_group_results = []
    
    for group_name, log_filename in GROUPS.items():
        group_data = []
        print(f"Analyzing {group_name}...")
        
        for run in RUNS:
            log_path = BASE_PATH / group_name / run / log_filename
            if not log_path.exists():
                print(f"Warning: {log_path} not found.")
                continue
                
            df = pd.read_csv(log_path)
            
            # Group by year and count adapted (elevated) agents
            # Note: 'elevated' is boolean. True.sum() gives count.
            adaptation_by_year = df.groupby('year')['elevated'].apply(lambda x: (x == True).sum()).reset_index()
            adaptation_by_year.columns = ['year', 'adapted_count']
            adaptation_by_year['run'] = run
            group_data.append(adaptation_by_year)
        
        if not group_data:
            continue
            
        group_df = pd.concat(group_data)
        
        # Calculate stats across runs for this group
        stats = group_df.groupby('year')['adapted_count'].agg(['mean', 'std', 'var']).reset_index()
        stats['group'] = group_name
        all_group_results.append(stats)
    
    if not all_group_results:
        print("No data found.")
        return
        
    final_stats_df = pd.concat(all_group_results)
    output_path = BASE_PATH / "all_groups_stability_analysis.csv"
    final_stats_df.to_csv(output_path, index=False)
    print(f"Combined stability stats saved to {output_path}")
    
    # Print summary of average SD per group
    summary = final_stats_df.groupby('group')['std'].mean().reset_index()
    summary.columns = ['group', 'avg_inter_run_std']
    print("\nSummary - Average Inter-run Standard Deviation (Stochastic Instability):")
    print(summary)

if __name__ == "__main__":
    analyze_stability()
