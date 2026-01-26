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

def calculate_audited_entropy():
    # Audit Log Header
    print(f"{'Model':<16} | {'Group':<8} | {'Year':<4} | {'Elev%':<5} | {'H_Obs':<6} | {'H_Max':<6} | {'H_Norm':<6} | {'Dominant'}")
    print("-" * 90)

    models = ['deepseek_r1_1_5b', 'deepseek_r1_8b', 'deepseek_r1_14b', 'deepseek_r1_32b']
    groups = ['Group_A', 'Group_B', 'Group_C']
    
    results = []
    
    for model in models:
        for group in groups:
            path_pattern = os.path.join(BASE_DIR, model, group, "Run_1", "simulation_log.csv")
            # Try flat structure for 14B if needed
            flat_pattern = os.path.join(BASE_DIR, model, group, "Run_1", "simulation_log.csv")
            
            files = glob.glob(path_pattern)
            if not files and os.path.exists(flat_pattern): files = [flat_pattern]
            
            if not files: continue
            
            df = pd.read_csv(files[0])
            dec_col = next((c for c in df.columns if 'decision' in c or 'skill' in c), None)
            
            if 'year' not in df.columns or not dec_col: continue
            
            years = sorted(df['year'].unique())
            for y in years:
                y_df = df[df['year'] == y]
                if len(y_df) == 0: continue
                
                # --- SIMPLIFIED AUDIT: ACTIVE AGENTS ONLY ---
                # We simply calculate the Entropy of decisions made by agents who are still here.
                # Exclude 'relocated' (they are gone).
                
                # --- SIMPLIFIED AUDIT: ACTIVE AGENTS ONLY ---
                # We want to capture the decisions of agents who are participating in this step.
                # This includes agents who choose to 'Relocate' NOW.
                # It EXCLUDES agents who 'Already relocated' in previous years.
                
                # Filter out 'Already relocated' from decision strings
                # Check for decision column
                
                # Filter logic:
                # 1. Get all rows for this year.
                # 2. Exclude rows where decision implies "Already".
                
                active_df = y_df[~y_df[dec_col].astype(str).str.contains("Already relocated", case=False, na=False)]
                
                if len(active_df) == 0:
                     print(f"{model:<16} | {group:<8} | {y:<4} | {'0':<5} | {0.000:<6} | -")
                     continue

                # --- CALCULATE RAW ENTROPY ---
                # Just the distribution of actions taken this year
                y_dec = active_df[dec_col].apply(normalize_decision)
                counts = y_dec.value_counts()
                
                if len(y_dec) > 0:
                    probs = counts / len(y_dec)
                    h_obs = entropy(probs, base=2)
                else:
                    h_obs = 0.0
                
                dom_action = counts.idxmax() if not counts.empty else "None"
                dom_freq = probs.max() if not counts.empty else 0
                
                # Report Raw Entropy
                dom_str = f"{dom_action} ({dom_freq:.0%})"
                print(f"{model:<16} | {group:<8} | {y:<4} | {len(active_df):<5} | {h_obs:<6.4f} | {dom_str}")
                
                results.append({
                    'Model': model,
                    'Group': group,
                    'Year': y,
                    'Active_Agents': len(active_df),
                    'Shannon_Entropy': round(h_obs, 4),
                    'Dominant_Action': dom_action,
                    'Dominant_Freq': round(dom_freq, 4)
                })

    # Export to CSV
    if results:
        out_path = "examples/single_agent/analysis/yearly_entropy_audited.csv"
        pd.DataFrame(results).to_csv(out_path, index=False)
        print(f"\n[SUCCESS] Audited data exported to {out_path}")

if __name__ == "__main__":
    calculate_audited_entropy()
