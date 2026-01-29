
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import entropy

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
OUTPUT_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\Gemma3_Results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

models = ["gemma3_1b", "gemma3_4b", "gemma3_12b", "gemma3_27b"]
groups = ["Group_A", "Group_B", "Group_C"]

def normalize_decision(d):
    d = str(d).lower()
    if 'reloc' in d: return 'relocate'
    if 'elev' in d: return 'elevate'
    if 'insur' in d: return 'insurance'
    return 'do_nothing'

def calculate_shannon_entropy(series):
    pk = series.value_counts(normalize=True).values
    return entropy(pk, base=2)

def analyze_cohort_entropy(model, group):
    csv_path = BASE_DIR / model / group / "Run_1" / "simulation_log.csv"
    if not csv_path.exists():
        return None
    
    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.lower() for c in df.columns]
        dec_col = next((c for c in df.columns if 'yearly_decision' in c or 'decision' in c or 'skill' in c), None)
        
        if not dec_col: return None
        
        results = []
        # Support up to max year found
        max_year = int(df['year'].max()) if 'year' in df.columns else 10
        
        for year in range(0, max_year + 1):
            if 'year' in df.columns:
                year_data = df[df['year'] == year]
            else:
                year_data = df # If no year col, assume single snapshot
                
            if year_data.empty: continue
            
            norm_decs = year_data[dec_col].apply(normalize_decision)
            h_val = calculate_shannon_entropy(norm_decs)
            
            # Normalize H to 0-1 scale (Max entropy for 4 options is 2 bits)
            h_norm = h_val / 2.0
            
            results.append({
                "Year": year,
                "Model": model,
                "Group": group,
                "Shannon_Entropy": h_val,
                "Shannon_Entropy_Norm": h_norm,
                "Population": len(year_data)
            })
        return results
    except Exception as e:
        print(f"Error {model}/{group}: {e}")
        return None

all_results = []
for model in models:
    for group in groups:
        res = analyze_cohort_entropy(model, group)
        if res:
            all_results.extend(res)

print("=== SQ2: GEMMA 3 ENTROPY ANALYSIS ===")
if all_results:
    df_entropy = pd.DataFrame(all_results)
    out_path = OUTPUT_DIR / "yearly_entropy_gemma3.csv"
    df_entropy.to_csv(out_path, index=False)
    print(f"Saved entropy data to {out_path}")
    print(df_entropy.head())
else:
    print("No entropy results generated.")
