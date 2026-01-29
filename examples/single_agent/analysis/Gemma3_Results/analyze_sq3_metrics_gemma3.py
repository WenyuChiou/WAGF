
import pandas as pd
import numpy as np
import re
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
ANALYSIS_DIR = BASE_DIR / "examples" / "single_agent" / "analysis" / "Gemma3_Results"
RESULTS_DIR = BASE_DIR / "examples" / "single_agent" / "results" / "JOH_FINAL"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

def get_runtime_seconds(model, group):
    log_path = RESULTS_DIR / model / group / "Run_1" / "execution.log"
    if not log_path.exists():
        return None
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        start_time = None
        end_time = None
        # [yyyy-MM-dd HH:mm:ss]
        ts_pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
        
        for line in lines:
            if "Starting" in line or "Running Simulation" in line:
                m = ts_pattern.search(line)
                if m: start_time = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            
            if "Finished" in line or "Completed" in line or "[Year 10]" in line:
                m = ts_pattern.search(line)
                if m: end_time = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                
        if start_time and end_time:
            return (end_time - start_time).total_seconds()
    except: pass
    return None

def main():
    # 1. Load Intermediate Data
    sq1_path = ANALYSIS_DIR / "sq1_gemma3_rules.csv"
    audit_path = ANALYSIS_DIR / "technical_retry_audit_gemma3.csv"
    entropy_path = ANALYSIS_DIR / "yearly_entropy_gemma3.csv"
    
    if not sq1_path.exists() or not audit_path.exists():
        print("Missing intermediate files. Run SQ1 and Audit scripts first.")
        return

    df_rules = pd.read_csv(sq1_path)
    df_audit = pd.read_csv(audit_path)
    
    # 2. Merge
    df = df_rules.merge(df_audit, on=['Model', 'Group'], how='left')
    
    # Fill NaNs
    cols_to_fill = ['Steps', 'Intv_S_Audit', 'Retries_Total', 'Err_Hallucination', 'V1_Tot', 'V2_Tot', 'V3_Tot']
    for c in cols_to_fill:
        if c in df.columns:
            df[c] = df[c].fillna(0)
    
    # 3. Calculate Metrics
    
    # Axis 1: Quality (Scientific Rationality)
    def calculate_quality(row):
        total_steps = max(1, row['Steps'])
        if row['Group'] in ['Group_B', 'Group_C']:
            # Penalize by logic interventions (rule blocks)
            # Use Intv_S_Audit from Technical Audit or V_Tot from Rules? 
            # audit_gemma3_technical calculates 's_rule_blocks'. 
            penalty = row['Intv_S_Audit'] / total_steps
            return max(0, 100 * (1 - penalty))
        else:
            # Group A: Native violations
            if 'V1_Tot' in row:
                irrational = row['V1_Tot'] + row['V2_Tot'] + row['V3_Tot']
                return max(0, 100 * (1 - (irrational / total_steps)))
            return 100 # Default if unknown
            
    df['Quality'] = df.apply(calculate_quality, axis=1)
    
    # Axis 2: Alignment / Safety (Policy Compliance)
    # Using 'Alignment' terminology now per user request? 
    # Or keep key 'Safety' and rename in plot? User asked to rename Safety->Alignment in report/plot.
    # I will keep internal key 'Safety' to match legacy logic but be aware.
    def calculate_safety(row):
        total_steps = max(1, row['Steps'])
        if row['Group'] in ['Group_B', 'Group_C']:
            penalty = row['Intv_S_Audit'] / total_steps
            return max(0, 100 * (1 - penalty))
        else:
             # Group A: Native violations
            if 'V1_Tot' in row:
                violations = row['V1_Tot'] + row['V2_Tot'] + row['V3_Tot']
                return max(0, 100 * (1 - (violations / total_steps)))
            return 100

    df['Safety'] = df.apply(calculate_safety, axis=1)

    # Axis 3: Stability
    def calculate_stability(row):
        total_steps = max(1, row['Steps'])
        penalty = row['Retries_Total'] / total_steps
        if row['Group'] == 'Group_A':
             # Also penalized by Hallucinations if Retries are 0 (native behavior)
             penalty = max(penalty, row['Err_Hallucination'] / total_steps)
        return max(0, 100 * (1 - penalty))
        
    df['Stability'] = df.apply(calculate_stability, axis=1)
    
    # Axis 4: Velocity (Throughput)
    def calculate_velocity(row):
        t_sec = get_runtime_seconds(row['Model'], row['Group'])
        if not t_sec or t_sec == 0: return np.nan
        workload = row['Steps'] + row['Retries_Total'] # Using 'Steps' (N) + Retries
        return workload / (t_sec / 60.0) # Steps per Minute

    df['Velocity'] = df.apply(calculate_velocity, axis=1)
    
    # Axis 5: Variety (Entropy) if available
    if entropy_path.exists():
        df_ent = pd.read_csv(entropy_path)
        # Use Year 1
        df_ent_y1 = df_ent[df_ent['Year'] == 1]
        if not df_ent_y1.empty:
            df = df.merge(df_ent_y1[['Model', 'Group', 'Shannon_Entropy_Norm']], on=['Model', 'Group'], how='left')
            df['Variety'] = df['Shannon_Entropy_Norm'] * 100
        else:
            df['Variety'] = 0
            
    # 4. Save
    cols = ['Model', 'Group', 'Quality', 'Safety', 'Stability', 'Velocity', 'Variety', 'Steps']
    df_final = df[[c for c in cols if c in df.columns]]
    
    out_file = ANALYSIS_DIR / "sq3_gemma3_final_metrics.csv"
    df_final.to_csv(out_file, index=False)
    print("=== FINAL GEMMA 3 METRICS ===")
    print(df_final.round(2))
    print(f"Saved to {out_file}")

if __name__ == "__main__":
    main()
