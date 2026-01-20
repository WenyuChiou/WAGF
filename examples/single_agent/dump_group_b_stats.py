
import json
import pandas as pd
import os

target_file = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b\Group_B\Run_1\gemma3_4b_strict\raw\household_traces.jsonl"

print(f"Reading {target_file}...")

threats = []
actions = []

try:
    with open(target_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            try:
                record = json.loads(line)
                
                # Threat
                if 'threat_appraisal' in record:
                    if isinstance(record['threat_appraisal'], dict):
                        threats.append(record['threat_appraisal'].get('threat_label', 'Unknown'))
                    else:
                        threats.append(str(record['threat_appraisal']))
                        
                # Action
                if 'decision' in record:
                    if isinstance(record['decision'], dict):
                        actions.append(record['decision'].get('skill', 'Unknown'))
                    else:
                        actions.append(str(record['decision']))
            except Exception as e:
                pass

    print("\n--- THREAT DISTRIBUTION ---")
    print(pd.Series(threats).value_counts())
    
    print("\n--- ACTION DISTRIBUTION ---")
    print(pd.Series(actions).value_counts())

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
