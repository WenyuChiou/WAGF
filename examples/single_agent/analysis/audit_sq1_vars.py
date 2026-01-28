
import json
from collections import Counter
import re

jsonl_path = "examples/single_agent/results/JOH_FINAL/deepseek_r1_1_5b/Group_B/Run_1/raw/household_traces.jsonl"

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

print(f"Auditing: {jsonl_path}")

stats = Counter()
rule_counts = Counter()

try:
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                retry = data.get('retry_count', 0)
                failed = str(data.get('failed_rules', '') or data.get('validation_issues', ''))
                
                if retry > 0 or (failed and failed != '[]'):
                    stats['Total_Intervention_Traces'] += 1
                    rtype = classify_rule(failed)
                    rule_counts[rtype] += 1
                    
                    # Check final decision
                    final_dec = data.get('skill_proposal', {}).get('skill_name', '').lower()
                    is_action = 'relocate' in final_dec or 'elevat' in final_dec or 'insur' in final_dec
                    
                    if is_action:
                        stats[f'Action_Result_from_{rtype}'] += 1
                    else:
                        stats[f'NoAction_Result_from_{rtype}'] += 1

            except Exception as e:
                print(f"Error: {e}")
                continue

    print("\n=== AUDIT RESULTS ===")
    print(f"Total Interventions Found: {stats['Total_Intervention_Traces']}")
    print("\nRule Breakdown:")
    for r, c in rule_counts.items():
        print(f"  - {r}: {c}")
        
    print("\nOutcomes (Action Taken?):")
    for k, v in stats.items():
        if 'Result' in k:
            print(f"  - {k}: {v}")

except FileNotFoundError:
    print("File not found.")
