import pandas as pd
from pathlib import Path
import json

base_dir = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b"]
groups = ["Group_B", "Group_C"]

print(f"{'Model':<20} | {'Group':<8} | {'Total Steps':<12} | {'Interventions':<15} | {'Rate (%)':<10}")
print("-" * 80)

for model in models:
    for group in groups:
        trace_path = base_dir / model / group / "Run_1"
        # Find trace file (handle diverse structure)
        jsonl_files = list(trace_path.rglob("household_traces.jsonl"))
        
        if not jsonl_files:
            print(f"{model:<20} | {group:<8} | {'MISSING':<12} | {'-':<15} | {'-':<10}")
            continue
            
        total_steps = 0
        intervention_count = 0
        
        for f in jsonl_files:
            with open(f, 'r', encoding='utf-8') as file:
                for line in file:
                    try:
                        data = json.loads(line)
                        total_steps += 1
                        if data.get("retry_count", 0) > 0:
                            intervention_count += 1
                    except:
                        pass
                        
        rate = (intervention_count / total_steps * 100) if total_steps > 0 else 0
        print(f"{model:<20} | {group:<8} | {total_steps:<12} | {intervention_count:<15} | {rate:<10.2f}")
