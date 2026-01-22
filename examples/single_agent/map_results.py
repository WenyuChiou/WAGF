import os
from pathlib import Path
import json

root = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results")
logs = list(root.rglob("simulation_log.csv"))

mapping = {}

for log in logs:
    rel_path = log.relative_to(root)
    parts = rel_path.parts
    # Typical structure: BENCHMARK_2026/deepseek_r1_8b/Group_A/Run_1/simulation_log.csv
    # Or JOH_STRESS/gemma3_4b/panic/Run_1/simulation_log.csv
    
    if len(parts) >= 4:
        major_cat = parts[0]
        model = parts[1]
        group = parts[2]
        run = parts[3]
        
        if model not in mapping:
            mapping[model] = {}
        if group not in mapping[model]:
            mapping[model][group] = []
        mapping[model][group].append(run)

print(json.dumps(mapping, indent=2))
