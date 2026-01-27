import pandas as pd
import numpy as np
import os
import glob
from scipy.stats import entropy

BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL"
OUTPUT_DIR = r"examples/single_agent/analysis/sq2_process_audit"

def normalize_decision(d):
    d = str(d).lower()
    if 'relocat' in d: return 'Relocate'
    if 'elevat' in d: return 'Elevation'
    if 'insur' in d: return 'Insurance'
    if 'do' in d or 'nothing' in d: return 'DoNothing'
    return 'Other'

def export_audit_data():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    models = ['deepseek_r1_1_5b', 'deepseek_r1_8b', 'deepseek_r1_14b', 'deepseek_r1_32b']
    groups = ['Group_A', 'Group_B', 'Group_C']
    
    audit_rows = []
    
    print("Starting Detailed Audit Export...")

    for model in models:
        for group in groups:
            path_pattern = os.path.join(BASE_DIR, model, group, "Run_1", "simulation_log.csv")
            # Try flat structure
            flat_pattern = os.path.join(BASE_DIR, model, group, "Run_1", "simulation_log.csv")
            
            files = glob.glob(path_pattern)
            if not files and os.path.exists(flat_pattern): files = [flat_pattern]
            
            if not files: 
                print(f"Skipping {model} {group} (Files not found)")
                continue
                
            path = files[0]
            try:
                df = pd.read_csv(path)
                dec_col = next((c for c in df.columns if 'decision' in c and 'raw' not in c), None)
                if not dec_col: 
                    # Fallback for some log versions
                    dec_col = next((c for c in df.columns if 'decision' in c), None)
                
                if 'year' not in df.columns or not dec_col: continue
                
                years = sorted(df['year'].unique())
                for y in years:
                    y_df = df[df['year'] == y]
                    
                    # FILTER: Active Agents Only (Step 1 Logic)
                    # Exclude "Already relocated"
                    active_df = y_df[~y_df[dec_col].astype(str).str.contains("Already relocated", case=False, na=False)]
                    
                    active_count = len(active_df)
                    if active_count == 0:
                        audit_rows.append({
                            'Model': model,
                            'Group': group,
                            'Year': y,
                            'Action': 'NONE (All Relocated)',
                            'Count': 0,
                            'Probability': 0.0,
                            'Entropy_Contribution': 0.0,
                            'Total_Entropy': 0.0
                        })
                        continue

                    # DISTRIBUTION (Step 2 Logic)
                    y_dec = active_df[dec_col].apply(normalize_decision)
                    counts = y_dec.value_counts()
                    probs = counts / active_count
                    
                    # ENTROPY (Step 3 Logic)
                    h_val = entropy(probs, base=2)
                    
                    # Export EACH Action as a row
                    for action, count in counts.items():
                        prob = probs[action]
                        contrib = - (prob * np.log2(prob)) if prob > 0 else 0
                        
                        audit_rows.append({
                            'Model': model,
                            'Group': group,
                            'Year': y,
                            'Action': action,
                            'Count': count,
                            'Probability': round(prob, 4),
                            'Entropy_Contribution': round(contrib, 4),
                            'Total_Entropy': round(h_val, 4)
                        })
                        
            except Exception as e:
                print(f"Error processing {model} {group}: {str(e)}")

    # Export
    out_path = os.path.join(OUTPUT_DIR, "detailed_distribution_audit.csv")
    pd.DataFrame(audit_rows).to_csv(out_path, index=False)
    print(f"\n[SUCCESS] Detailed audit exported to {out_path}")
    print(f"Total Rows: {len(audit_rows)}")

if __name__ == "__main__":
    export_audit_data()
