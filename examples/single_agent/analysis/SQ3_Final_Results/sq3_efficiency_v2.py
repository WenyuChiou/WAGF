import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
import re
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]
OUTPUT_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ3_Final_Results")

TA_KEYWORDS = {"H": ["severe", "critical", "extreme", "catastrophic", "significant harm", "dangerous", "bad", "devastating", "susceptible", "likely", "high risk", "exposed", "probability", "chance", "vulnerable", "afraid", "anxious", "worried", "concerned", "frightened", "emergency", "flee"]}

def get_stats(df, group):
    df.columns = [c.lower() for c in df.columns]
    def map_ta(text):
        text = str(text).lower()
        if any(k in text for k in TA_KEYWORDS['H']): return "H"
        return "L"
    ta_col = 'threat_appraisal' if 'threat_appraisal' in df.columns else 'reason_tp_reason'
    df['tp_level'] = df[ta_col].apply(map_ta)
    dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
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

def get_runtime(run_dir):
    # 1. Try execution.log
    exec_log = run_dir / "execution.log"
    if exec_log.exists():
        try:
            with open(exec_log, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                match = re.search(r"Total simulation time:\s+([\d.]+)\s+seconds", content)
                if match: return float(match.group(1))
        except: pass
    # 2. Try traces.jsonl
    traces_path = run_dir / "raw" / "household_traces.jsonl"
    if not traces_path.exists(): traces_path = run_dir / "household_traces.jsonl"
    if traces_path.exists():
        try:
            with open(traces_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 1:
                    start_ts = datetime.fromisoformat(json.loads(lines[0])['timestamp'])
                    end_ts = datetime.fromisoformat(json.loads(lines[-1])['timestamp'])
                    return (end_ts - start_ts).total_seconds()
        except: pass
    return None

def analyze_efficiency(model, group):
    run_dir = BASE_DIR / model / group / "Run_1"
    sim_path = run_dir / "simulation_log.csv"
    if not sim_path.exists(): sim_path = run_dir / "raw" / "simulation_log.csv"
    if not sim_path.exists(): return None
    
    try:
        df_sim = pd.read_csv(sim_path)
        gain_stats = get_stats(df_sim, group)
    except: return None
    
    interventions, intv_h, intv_s, total_audit = 0, 0, 0, 0
    audit_path = run_dir / "household_governance_audit.csv"
    if not audit_path.exists(): audit_path = run_dir / "raw" / "household_governance_audit.csv"
    
    if audit_path.exists():
        df_audit = pd.read_csv(audit_path)
        df_audit.columns = [c.lower() for c in df_audit.columns]
        total_audit = len(df_audit)
        blocked = df_audit[df_audit['status'] != 'APPROVED']
        interventions = len(blocked)
        rule_search = 'failed_rules' if 'failed_rules' in df_audit.columns else 'error_messages'
        intv_s = len(blocked[blocked[rule_search].str.contains('block|rule|violation', case=False, na=False)])
        intv_h = interventions - intv_s
    
    ir_rate = (interventions / total_audit) if total_audit > 0 else 0
    ir_h_rate = (intv_h / total_audit) if total_audit > 0 else 0
    ir_s_rate = (intv_s / total_audit) if total_audit > 0 else 0
    
    runtime = get_runtime(run_dir)
    # Manual Fallbacks for known Group A runs
    if not runtime and group == "Group_A":
        if "1_5b" in model: runtime = 781.21
        elif "8b" in model: runtime = 11856.23
        elif "14b" in model: runtime = 7667.43
        elif "32b" in model: runtime = 124009.25

    total_n = total_audit if total_audit > 0 else gain_stats["N"]
    throughput = (total_n / (runtime / 60)) if (runtime and runtime > 0) else None

    return {
        "Model": model, "Group": group,
        "Rationality": gain_stats["Rationality_Score"],
        "V1": gain_stats["V1_Panic_Reloc"],
        "V2": gain_stats["V2_Panic_Elev"],
        "V3": gain_stats["V3_Comp"],
        "Intv_Rate": ir_rate, "Intv_H": ir_h_rate, "Intv_S": ir_s_rate,
        "Runtime": runtime, "Throughput": throughput, "Total_N": total_n
    }

all_results = [analyze_efficiency(m, g) for m in models for g in groups]
df_eff = pd.DataFrame([r for r in all_results if r])
df_eff.to_csv(OUTPUT_DIR / "sq3_efficiency_data_v2.csv", index=False)
print("\n === SQ3 SUMMARY ===\n", df_eff[['Model', 'Group', 'Rationality', 'Throughput']].to_string(index=False))
