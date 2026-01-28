
import pandas as pd
import json
from pathlib import Path

# Inspect the "Unknown" threats for 1.5B Group B
log_path = "examples/single_agent/results/JOH_FINAL/deepseek_r1_1_5b/Group_B/Run_1/simulation_log.csv"
jsonl_path = "examples/single_agent/results/JOH_FINAL/deepseek_r1_1_5b/Group_B/Run_1/raw/household_traces.jsonl"

df = pd.read_csv(log_path)
df.columns = [c.lower() for c in df.columns]

# Get threats
agent_threats = {} # aid -> year -> threat
if Path(jsonl_path).exists():
    with open(jsonl_path, 'r', encoding='utf-8') as f:
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

print("=== INSPECTING 1.5B GROUP B 'UNKNOWN' RELOCATIONS ===")
count = 0
dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'

for idx, row in df.iterrows():
    d = str(row[dec_col]).lower()
    if 'relocate' in d:
        aid = row['agent_id']
        year = row['year']
        ta = str(row.get('threat_appraisal', 'M'))
        if aid in agent_threats and year in agent_threats[aid]:
            ta = agent_threats[aid][year]
            
        ta_u = str(ta).upper()
        # If NOT High, Med, or Low
        if not any(x in ta_u for x in ['H', 'M', 'L', 'VL', 'VH']):
            count += 1
            if count <= 10:
                print(f"Agent {aid} Year {year} -> Decision: {row[dec_col]}")
                print(f"   Threat Raw: '{ta}'")
                
print(f"\nTotal 'Unknown/Vague' Panic Relocations: {count}")
