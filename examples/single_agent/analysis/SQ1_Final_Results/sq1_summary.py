
import pandas as pd
import json
import re
from pathlib import Path

def is_scale_hallucination(text):
    if not isinstance(text, str): return False
    text = text.upper()
    matches = sum(1 for code in ["VH", "H", "VL", "L", "M"] if re.search(rf'\b{code}\b', text))
    return matches >= 3

def classify_rule(rule_str):
    r = str(rule_str).lower()
    if 'relocation_threat_low' in r or 'elevation_threat_low' in r:
        return 'panic'
    if 'extreme_threat_block' in r:
        return 'complacency'
    if 'low_coping_block' in r or 'elevation_block' in r:
        return 'realism'
    return 'other'

def get_sq1_stats(model, group):
    root = Path("examples/single_agent/results/JOH_FINAL")
    group_dir = root / model / group / "Run_1"
    
    if not group_dir.exists(): return None
    
    csv_file = group_dir / "simulation_log.csv"
    if not csv_file.exists():
        # Try subdirs for 32B/others
        for sd in group_dir.iterdir():
            if sd.is_dir() and (sd / "simulation_log.csv").exists():
                csv_file = sd / "simulation_log.csv"
                break
    
    if not csv_file.exists(): return None
    
    df = pd.read_csv(csv_file)
    df.columns = [c.lower() for c in df.columns]
    
    # Trace Analysis
    jsonl = group_dir / "household_traces.jsonl"
    if not jsonl.exists(): jsonl = group_dir / "raw" / "household_traces.jsonl"
    
    intv_p = 0
    intv_halluc = 0
    
    if jsonl.exists():
        with open(jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    failed_rules = str(data.get('failed_rules', '') or data.get('validation_issues', '')).lower()
                    if classify_rule(failed_rules) == 'panic': intv_p += 1
                    
                    reasoning = data.get('skill_proposal', {}).get('reasoning', {})
                    ta_text = str(reasoning.get('threat_appraisal', '') or reasoning.get('TP_LABEL', ''))
                    ca_text = str(reasoning.get('coping_appraisal', '') or reasoning.get('CP_LABEL', ''))
                    if is_scale_hallucination(ta_text) or is_scale_hallucination(ca_text):
                        intv_halluc += 1
                except: continue
                
    # Basic Decision Analysis
    dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
    if 'relocated' in df.columns:
        df = df[df['relocated'] != True]
    
    v1_n = (df[dec_col].str.lower().str.contains('relocate', na=False)).sum()
    
    return {
        "N": len(df),
        "V1_N": v1_n,
        "Intv_P": intv_p,
        "Intv_H": intv_halluc
    }

models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]

print(f"{'Model':<20} {'Group':<10} {'N':<6} {'V1_N':<6} {'Intv_P':<6} {'Intv_H'}")
print("-" * 60)

for m in models:
    for g in groups:
        res = get_sq1_stats(m, g)
        if res:
            print(f"{m:<20} {g:<10} {res['N']:<6} {res['V1_N']:<6} {res['Intv_P']:<6} {res['Intv_H']}")
