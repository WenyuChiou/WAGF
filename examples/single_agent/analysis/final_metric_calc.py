
import json
import pandas as pd
from pathlib import Path
import re

def classify_rule(rule_str):
    r = str(rule_str).lower()
    if 'relocation_threat_low' in r or 'elevation_threat_low' in r:
        return 'Panic'
    if 'extreme_threat_block' in r:
        return 'Complacency'
    if 'low_coping_block' in r or 'elevation_block' in r:
        return 'Realism'
    if 'format' in r or 'missing' in r:
        return 'Format'
    return 'Other'

def normalize_decision(d):
    d = str(d).lower()
    if 'relocate' in d: return 'Relocate'
    if 'elevat' in d: return 'Elevation'
    if 'do_nothing' in d or 'nothing' in d: return 'DoNothing'
    return 'Other'

def analyze_model(model, group):
    root = Path("examples/single_agent/results/JOH_FINAL")
    group_dir = root / model / group / "Run_1"
    
    # Files
    csv_file = group_dir / "simulation_log.csv"
    jsonl_file = group_dir / "raw" / "household_traces.jsonl"
    if not jsonl_file.exists(): jsonl_file = group_dir / "household_traces.jsonl"

    if not csv_file.exists(): 
        return None

    # 1. Load CSV for Actual Outcomes
    df = pd.read_csv(csv_file)
    df.columns = [c.lower() for c in df.columns]
    
    # Filter active only?
    # User standard: N=1000 for full traces. 
    # V1 Actual: Count 'Relocate' decisions
    dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
    
    # actual_v1 = df[df[dec_col].str.contains('Relocate', case=False, na=False)] 
    # Better normalization:
    # 1. Load CSV and Appraisal Data
    df = pd.read_csv(csv_file)
    df.columns = [c.lower() for c in df.columns]
    
    # Extract Appraisals (simplified from master_report logic)
    # Group A usually has columns. Group B/C needs jsonl merge or assumes strict compliance.
    # For verification, we check the JSONL reasoning if available.
    
    # Helper to parse threat from JSONL or CSV
    agent_threats = {} # agent_id -> year -> threat
    
    if jsonl_file.exists():
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    step = data.get('step_id')
                    # Approximated Year mapping (assuming standard 50/100 agents)
                    # Better: Read from data if available, or just map sequentially
                    year = data.get('year')
                    aid = data.get('agent_id')
                    
                    reasoning = data.get('skill_proposal', {}).get('reasoning', {})
                    ta = (reasoning.get('TP_LABEL') or 
                          reasoning.get('threat_appraisal', {}).get('label'))
                    
                    if aid and year:
                        if aid not in agent_threats: agent_threats[aid] = {}
                        agent_threats[aid][year] = ta
                except: continue
                
    dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
    
    panic_relocations = 0
    rational_relocations = 0
    
    for idx, row in df.iterrows():
        d = normalize_decision(row[dec_col])
        if d == 'Relocate':
            # Check Threat
            aid = row['agent_id']
            year = row['year']
            
            # Get threat from JSONL map or CSV col
            ta = str(row.get('threat_appraisal', 'M')) # Default M if missing in CSV
            if aid in agent_threats and year in agent_threats[aid]:
                ta = agent_threats[aid][year]
            
            if not ta: ta = "M"
            
            is_high = 'H' in str(ta).upper() # Matches H, VH
            
            if is_high:
                rational_relocations += 1
            else:
                panic_relocations += 1
                
    # 2. Interventions (Intent)
    count_intv_panic = 0
    count_intv_total = 0
    
    if jsonl_file.exists():
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    retry = data.get('retry_count', 0)
                    failed = str(data.get('failed_rules', '') or data.get('validation_issues', ''))
                    
                    if retry > 0 or (failed and failed != '[]'):
                        count_intv_total += 1
                        rtype = classify_rule(failed)
                        if rtype == 'Panic': count_intv_panic += 1
                except: continue

    # V1 Panic Intent = Actual Panic Leak + Blocked Panic
    v1_intent = panic_relocations + count_intv_panic
    
    rate_leak = 0
    if len(df) > 0:
        rate_leak = round(panic_relocations / len(df) * 100, 1)

    return {
        "Model": model,
        "Group": group,
        "N": len(df),
        "Rational_Reloc": rational_relocations,
        "Panic_Leak": panic_relocations,
        "Panic_Block": count_intv_panic,
        "Panic_Intent_Tot": v1_intent,
        "Panic_Leak_%": rate_leak
    }

models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]

print(f"{'Model':<18} {'Grp':<5} {'N':<5} {'Rat_Rel':<7} {'Pn_Leak':<7} {'Pn_Blk':<7} {'Pn_Int_Tot':<10} {'Leak_%':<7}")
print("-" * 100)

for m in models:
    for g in groups:
        res = analyze_model(m, g)
        if res:
             print(f"{res['Model']:<18} {res['Group']:<5} {res['N']:<5} {res['Rational_Reloc']:<7} {res['Panic_Leak']:<7} {res['Panic_Block']:<7} {res['Panic_Intent_Tot']:<10} {res['Panic_Leak_%']:<7}")

