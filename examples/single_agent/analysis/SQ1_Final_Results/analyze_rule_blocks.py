
import json
import pandas as pd
from pathlib import Path

def analyze_rule_interventions():
    root = Path("examples/single_agent/results/JOH_FINAL")
    model = "deepseek_r1_1_5b"
    group = "Group_B"
    run_dir = root / model / group / "Run_1"
    
    jsonl_path = run_dir / "raw" / "household_traces.jsonl"
    
    if not jsonl_path.exists():
        print("File not found.")
        return

    print(f"Analyzing interventions by rule for {model} {group}...")
    rule_counts = {}
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                failed_rules = str(data.get('failed_rules', '')).lower()
                
                if failed_rules and failed_rules not in ['nan', 'none', '', '[]']:
                    # Simple rule ID extraction
                    if 'relocation_threat_low' in failed_rules:
                        rule = 'V1_Blocked'
                    elif 'elevation_threat_low' in failed_rules:
                        rule = 'V2_Blocked'
                    elif 'extreme_threat_block' in failed_rules:
                        rule = 'V3_Blocked'
                    else:
                        rule = f'Other: {failed_rules}'
                    
                    rule_counts[rule] = rule_counts.get(rule, 0) + 1
            except: continue

    print("\n--- Intervention Counts by Rule ---")
    for rule, count in rule_counts.items():
        print(f"{rule}: {count}")

if __name__ == "__main__":
    analyze_rule_interventions()
