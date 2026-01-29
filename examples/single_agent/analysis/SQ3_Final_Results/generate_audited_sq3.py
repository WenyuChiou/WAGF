
import pandas as pd
import numpy as np
import os
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
SQ1_DIR = BASE_DIR / "examples" / "single_agent" / "analysis" / "SQ1_Final_Results"
SQ3_DIR = BASE_DIR / "examples" / "single_agent" / "analysis" / "SQ3_Final_Results"

# Runtimes (Seconds)
RUNTIMES = {
    ("deepseek_r1_1_5b", "Group_A"): 781.21,
    ("deepseek_r1_1_5b", "Group_B"): 3528.55,
    ("deepseek_r1_1_5b", "Group_C"): 3469.70,
    ("deepseek_r1_8b", "Group_A"): 11856.23,
    ("deepseek_r1_8b", "Group_B"): 27483.66,
    ("deepseek_r1_8b", "Group_C"): 19804.89,
    ("deepseek_r1_14b", "Group_A"): 7667.43,
    ("deepseek_r1_14b", "Group_B"): 16176.87,
    ("deepseek_r1_14b", "Group_C"): 18066.08,
    ("deepseek_r1_32b", "Group_A"): 124009.25,
}

# 1. Load Data
df_rules = pd.read_excel(SQ1_DIR / "sq1_metrics_rules.xlsx")
df_audit = pd.read_csv(SQ3_DIR / "technical_retry_audit_v3.csv")

# 2. Merge Audited Counts
df = df_rules.merge(df_audit[['Model', 'Group', 'Steps', 'Intv_S_Audit', 'Intv_P_Audit', 'Retries_Total', 'Err_Hallucination']], on=['Model', 'Group'], how='left')
df['Intv_S_Audit'] = df['Intv_S_Audit'].fillna(0)
df['Intv_P_Audit'] = df['Intv_P_Audit'].fillna(0)
df['Retries_Total'] = df['Retries_Total'].fillna(0)
df['Err_Hallucination'] = df['Err_Hallucination'].fillna(0)

# Axis 1: Quality (Scientific Rationality - INTENT BASED)
def calculate_quality(row):
    # Intent = Native capacity to reason within rules.
    # We penalize by Logic Interventions (Intv_S_Audit) for B/C,
    # or by raw violation rates for A.
    if row['Group'] in ['Group_B', 'Group_C']:
        penalty = row['Intv_S_Audit'] / row['Steps']
        return max(0, 100 * (1 - penalty))
    else:
        # Native Group A: 1 - Violation Rate
        irrational_total = row['V1_Tot'] + row['V2_Tot'] + row['V3_Tot']
        return max(0, 100 * (1 - (irrational_total / row['Steps'])))

df['Quality'] = df.apply(calculate_quality, axis=1)

# Axis 2: Safety (Policy Compliance - INTENT BASED)
def calculate_safety(row):
    # Intent = Native compliance with policy rules.
    # Group B/C are penalized for every rule breach that needed a block.
    if row['Group'] in ['Group_B', 'Group_C']:
        # We use Intv_S_Audit as a proxy for both logic and policy interventions if not separate.
        # But we assume the Intv_S_Audit captures the "steering effort".
        penalty = row['Intv_S_Audit'] / row['Steps']
        return max(0, 100 * (1 - penalty))
    else:
        # Native Group A: 1 - Policy Breach Rate
        violations = row['V1_Tot'] + row['V2_Tot'] + row['V3_Tot']
        return max(0, 100 * (1 - (violations / row['Steps'])))

df['Safety'] = df.apply(calculate_safety, axis=1)

# Axis 3: Stability (Technical Outcome - INTENT BASED)
def calculate_stability(row):
    # Intent = Native ability to maintain structural integrity.
    # Penalized by technical retries (or audit failures).
    penalty = row['Retries_Total'] / row['Steps'] if row['Steps'] > 0 else 0
    if row['Group'] == 'Group_A':
        # Use native hallucinations if retries were 0
        penalty = max(penalty, row['Err_Hallucination'] / row['Steps']) if row['Steps'] > 0 else 0
    
    return max(0, 100 * (1 - penalty))

df['Stability'] = df.apply(calculate_stability, axis=1)

# Axis 4: Speed (Workload Velocity)
# Numerator: Scientific Steps N + Total Retries. Denominator: Total Elapsed Time.
# This reflects the "Gross Processing Throughput".
def calculate_speed(row):
    t_sec = RUNTIMES.get((row['Model'], row['Group']))
    if not t_sec: return np.nan
    workload = row['N'] + row['Retries_Total']
    return workload / (t_sec / 60.0)

df['Speed'] = df.apply(calculate_speed, axis=1)

# 4. Final Formatting & Variety
entropy_path = BASE_DIR / "examples" / "single_agent" / "analysis" / "SQ2_Final_Results" / "yearly_entropy_audited.csv"
if entropy_path.exists():
    df_entropy = pd.read_csv(entropy_path)
    df_entropy_y1 = df_entropy[df_entropy['Year'] == 1][['Model', 'Group', 'Shannon_Entropy']]
    df_entropy_y1['Variety'] = df_entropy_y1['Shannon_Entropy'] / 2.3219 # Standardized
    df = df.merge(df_entropy_y1[['Model', 'Group', 'Variety']], on=['Model', 'Group'], how='left')

# 5. Export
df_final = df[['Model', 'Group', 'Quality', 'Speed', 'Safety', 'Stability', 'Variety']]
df_final.to_csv(SQ3_DIR / "sq3_efficiency_final_consolidated_v3.csv", index=False)

print("\n=== FINAL SQ3 PERFORMANCE OUTCOMES (REFINED) ===")
print(df_final.to_string(index=False))
