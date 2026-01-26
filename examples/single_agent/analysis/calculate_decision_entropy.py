import pandas as pd
import numpy as np
import os
import glob
from scipy.stats import entropy

BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL"

def normalize_decision(d):
    d = str(d).lower()
    if 'relocat' in d: return 'Relocate'
    if 'elevat' in d: return 'Elevation'
    if 'insur' in d: return 'Insurance'
    if 'do' in d or 'nothing' in d: return 'DoNothing'
    return 'Other'

def calculate_entropy():
    print(f"{'Model':<20} | {'Group':<10} | {'Entropy (H)':<12} | {'Dominant Action (Freq)'}")
    print("-" * 80)
    
    # Define models and groups to check
    models = ['deepseek_r1_1_5b', 'deepseek_r1_8b', 'deepseek_r1_14b', 'deepseek_r1_32b']
    groups = ['Group_A', 'Group_B', 'Group_C']
    
    results = []

    for model in models:
        for group in groups:
            # Flexible path finding
            path_pattern = os.path.join(BASE_DIR, model, group, "Run_1", "simulation_log.csv")
            files = glob.glob(path_pattern)
            
            if not files:
                # Try flat 14B
                flat_path = os.path.join(BASE_DIR, model, group, "Run_1", "simulation_log.csv")
                if os.path.exists(flat_path):
                     files = [flat_path]
            
            if not files:
                print(f"{model:<20} | {group:<10} | {'MISSING':<12} | -")
                continue
                
            path = files[0]
            try:
                df = pd.read_csv(path)
                decision_col = next((c for c in df.columns if 'yearly_decision' in c or 'decision' in c or 'skill' in c), None)
                
                if not decision_col:
                     continue
                     
                # Calculate Yearly Entropy Trend
                if 'year' in df.columns:
                    years = sorted(df['year'].unique())
                    print(f"Analyzing {model} {group}...")
                    for y in years:
                        y_df = df[df['year'] == y]
                        if len(y_df) == 0: continue
                        y_dec = y_df[decision_col].apply(normalize_decision)
                        y_counts = y_dec.value_counts()
                        y_probs = y_counts / len(y_dec)
                        y_ent = entropy(y_probs, base=2)
                        dom_action = y_counts.idxmax()
                        dom_freq = y_probs.max()
                        
                        results.append({
                            'Model': model,
                            'Group': group,
                            'Year': y,
                            'Entropy': round(y_ent, 4),
                            'Dominant': dom_action,
                            'Dom_Freq': round(dom_freq, 4)
                        })
                
            except Exception as e:
                print(f"{model:<20} | {group:<10} | {'ERROR':<12} | {str(e)}")

    # Export to CSV
    if results:
        res_df = pd.DataFrame(results)
        res_df.to_csv("examples/single_agent/analysis/entropy_analysis_all.csv", index=False)
        print("\nSuccessfully exported to examples/single_agent/analysis/entropy_analysis_all.csv")
        
        # Print Summary of Average Entropy
        print("\n--- Average Entropy Summary ---")
        summary = res_df.groupby(['Model', 'Group'])['Entropy'].mean().reset_index()
        print(summary.to_string())

if __name__ == "__main__":
    calculate_entropy()
