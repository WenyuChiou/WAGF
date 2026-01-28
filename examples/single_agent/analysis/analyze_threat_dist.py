
import pandas as pd
import json
from pathlib import Path

def get_threat_dist(model, group):
    root = Path("examples/single_agent/results/JOH_FINAL")
    group_dir = root / model / group / "Run_1"
    jsonl_file = group_dir / "raw" / "household_traces.jsonl"
    if not jsonl_file.exists(): jsonl_file = group_dir / "household_traces.jsonl"
    csv_file = group_dir / "simulation_log.csv"
    
    if not csv_file.exists(): return None
    
    df = pd.read_csv(csv_file)
    df.columns = [c.lower() for c in df.columns]
    
    # Map Threats
    agent_threats = {}
    if jsonl_file.exists():
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    aid = data.get('agent_id')
                    year = data.get('year')
                    ta = (data.get('skill_proposal', {}).get('reasoning', {}).get('TP_LABEL') or 
                          data.get('skill_proposal', {}).get('reasoning', {}).get('threat_appraisal', {}).get('label'))
                    if aid and year:
                        if aid not in agent_threats: agent_threats[aid] = {}
                        agent_threats[aid][year] = ta
                except: continue

    dist = {'H': 0, 'M': 0, 'L': 0, 'U': 0} # U for Unknown
    total_reloc = 0
    
    dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
    
    for idx, row in df.iterrows():
        d = str(row[dec_col]).lower()
        if 'relocate' in d:
            total_reloc += 1
            aid = row['agent_id']
            year = row['year']
            ta = str(row.get('threat_appraisal', 'M'))
            if aid in agent_threats and year in agent_threats[aid]:
                ta = agent_threats[aid][year]
            
            ta_u = str(ta).upper()
            if 'VH' in ta_u or 'H' in ta_u:
                dist['H'] += 1
            elif 'M' in ta_u:
                dist['M'] += 1
            elif 'L' in ta_u or 'VL' in ta_u:
                dist['L'] += 1
            else:
                dist['U'] += 1 # Likely 'None' or empty
                
    return total_reloc, dist

print(f"{'Group':<10} {'Relocs':<6} {'High':<6} {'Med':<6} {'Low':<6}")
print("-" * 50)

r_a, d_a = get_threat_dist("deepseek_r1_1_5b", "Group_A")
print(f"{'Group_A':<10} {r_a:<6} {d_a['H']:<6} {d_a['M']:<6} {d_a['L']:<6} (Ratio L/Tot: {d_a['L']/r_a:.2f})")

r_b, d_b = get_threat_dist("deepseek_r1_1_5b", "Group_B")
print(f"{'Group_B':<10} {r_b:<6} {d_b['H']:<6} {d_b['M']:<6} {d_b['L']:<6} (Ratio L/Tot: {d_b['L']/r_b:.2f})")
