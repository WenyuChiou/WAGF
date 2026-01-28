import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
import re

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]
OUTPUT_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ3_Final_Results")

TA_KEYWORDS = {"H": ["severe", "critical", "extreme", "catastrophic", "significant harm", "dangerous", "bad", "devastating", "susceptible", "likely", "high risk", "exposed", "probability", "chance", "vulnerable", "afraid", "anxious", "worried", "concerned", "frightened", "emergency", "flee"]}

def get_stats(df, group):
    # Same logic as master_report.py
    df.columns = [c.lower() for c in df.columns]
    
    # map TP/CP
    def map_ta(text):
        text = str(text).lower()
        if any(k in text for k in TA_KEYWORDS['H']): return "H"
        return "L"
        
    # Use 'threat_appraisal' from CSV
    ta_col = 'threat_appraisal' if 'threat_appraisal' in df.columns else 'reason_tp_reason'
    df['tp_level'] = df[ta_col].apply(map_ta)
    
    dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
    
    # Binary Rationality Violations
    v1_count = len(df[(df['tp_level'] != 'H') & (df[dec_col].str.contains('Relocate', case=False, na=False))])
    v2_count = len(df[(df['tp_level'] == 'L') & (df[dec_col].str.contains('Elevate', case=False, na=False))])
    v3_count = len(df[(df['tp_level'] == 'H') & (df[dec_col].str.contains('Do nothing', case=False, na=False))])

    total_n = len(df)
    v1_rate = (v1_count / total_n) if total_n > 0 else 0
    v2_rate = (v2_count / total_n) if total_n > 0 else 0
    v3_rate = (v3_count / total_n) if total_n > 0 else 0
    
    return {
        "N": total_n,
        "V1_Panic_Reloc": v1_rate,
        "V2_Panic_Elev": v2_rate,
        "V3_Comp": v3_rate,
        "Rationality_Score": 1.0 - (v1_rate + v2_rate + v3_rate)
    }

def analyze_efficiency(model, group):
    run_dir = BASE_DIR / model / group / "Run_1"
    sim_path = run_dir / "simulation_log.csv"
    audit_path = run_dir / "household_governance_audit.csv"
    
    # Check raw subdir if not found
    if not sim_path.exists():
        sim_path = run_dir / "raw" / "simulation_log.csv"
    if not audit_path.exists():
        audit_path = run_dir / "raw" / "household_governance_audit.csv"
        
    if not sim_path.exists(): 
        print(f"Missing simulation_log.csv for {model}/{group}")
        return None
    
    # 1. Rationality (Gain)
    try:
        df_sim = pd.read_csv(sim_path)
        gain_stats = get_stats(df_sim, group)
    except Exception as e:
        print(f"Error reading sim log for {model}/{group} at {sim_path}: {e}")
        return None
        
    # 2. Oversight Burden (Cost)
    interventions = 0
    intv_h = 0 # Hallucinations (Syntax/Format)
    intv_s = 0 # Successful Behavior Block
    total_audit = 0
    
    if audit_path.exists():
        df_audit = pd.read_csv(audit_path)
        df_audit.columns = [c.lower() for c in df_audit.columns]
        total_audit = len(df_audit)
        
        # Blocked actions
        blocked = df_audit[df_audit['status'] != 'APPROVED']
        interventions = len(blocked)
        
        # Breakdown
        # Intv_S: Behavioral Blocks (Contain 'block', 'rule', or 'violation' in failed_rules)
        rule_search = 'failed_rules' if 'failed_rules' in df_audit.columns else 'error_messages'
        intv_s = len(blocked[blocked[rule_search].str.contains('block|rule|violation', case=False, na=False)])
        
        # Intv_H: Hallucinations / Waste (Everything else that was blocked)
        intv_h = interventions - intv_s
    
    ir_rate = (interventions / total_audit) if total_audit > 0 else 0
    ir_h_rate = (intv_h / total_audit) if total_audit > 0 else 0
    ir_s_rate = (intv_s / total_audit) if total_audit > 0 else 0
    
    return {
        "Model": model,
        "Group": group,
        "Rationality": gain_stats["Rationality_Score"],
        "V1": gain_stats["V1_Panic_Reloc"],
        "V2": gain_stats["V2_Panic_Elev"],
        "V3": gain_stats["V3_Comp"],
        "Intv_Rate": ir_rate,
        "Intv_H": ir_h_rate,
        "Intv_S": ir_s_rate,
        "Total_N": total_audit if total_audit > 0 else gain_stats["N"]
    }

# --- MAIN ---
all_results = []
for model in models:
    for group in groups:
        res = analyze_efficiency(model, group)
        if res: all_results.append(res)

df_eff = pd.DataFrame(all_results)
df_eff.to_csv(OUTPUT_DIR / "sq3_efficiency_data_v2.csv", index=False)

# --- PRINT SUMMARY ---
print("\n === SQ3: SURGICAL GOVERNANCE EFFICIENCY ===")
print(df_eff[['Model', 'Group', 'Rationality', 'Intv_Rate', 'Intv_H', 'Intv_S']].to_string(index=False))

# --- RADAR DATA PREP ---
# For the paper, we want to show 1.5B Group C vs 32B Group A
# Comparison: Performance of small-model-governed vs large-model-natural
print("\n === COST-BENEFIT COMPARISON (1.5B Gov vs 32B Nat) ===")
comparison = df_eff[
    ((df_eff['Model'] == 'deepseek_r1_1_5b') & (df_eff['Group'] == 'Group_C')) |
    ((df_eff['Model'] == 'deepseek_r1_32b') & (df_eff['Group'] == 'Group_A'))
]
print(comparison.to_string(index=False))
