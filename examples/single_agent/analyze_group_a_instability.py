import pandas as pd
import numpy as np
import os
from pathlib import Path

# Paths to the 3 Run logs for Group A
BASE_PATH = Path(r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b\Group_A")
runs = ["Run_1", "Run_2", "Run_3"]

def analyze_stability():
    results = []
    
    for run in runs:
        log_path = BASE_PATH / run / "flood_adaptation_simulation_log.csv"
        if not log_path.exists():
            print(f"Warning: {log_path} not found.")
            continue
            
        df = pd.read_csv(log_path)
        
        # Calculate adaptation count per year
        # Use 'elevated' column (boolean)
        adaptation_by_year = df.groupby('year')['elevated'].apply(lambda x: (x == True).sum()).reset_index()
        adaptation_by_year.columns = ['year', 'adapted_count']
        
        # Add run identifier
        adaptation_by_year['run'] = run
        results.append(adaptation_by_year)
    
    if not results:
        print("No data found.")
        return
        
    all_data = pd.concat(results)
    
    # Pivot to compare runs side-by-side
    pivot_df = all_data.pivot(index='year', columns='run', values='adapted_count')
    
    # Calculate Variance and Standard Deviation per year
    pivot_df['Mean'] = pivot_df[runs].mean(axis=1)
    pivot_df['StdDev'] = pivot_df[runs].std(axis=1)
    pivot_df['Variance'] = pivot_df[runs].var(axis=1)
    
    print("\n=== Group A Adaptation Count Stability Analysis ===\n")
    print(pivot_df)
    
    # Final instability metric: average StdDev across years
    avg_std = pivot_df['StdDev'].mean()
    print(f"\nAverage Inter-Run Standard Deviation (Group A): {avg_std:.2f}")
    
    # Save results for Figure 2 data
    output_path = BASE_PATH / "stability_analysis_results.csv"
    pivot_df.to_csv(output_path)
    print(f"\nResults saved to: {output_path}")

if __name__ == "__main__":
    analyze_stability()
