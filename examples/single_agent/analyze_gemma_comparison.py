import pandas as pd
import numpy as np
from pathlib import Path
import json

ROOT = Path("H:/我的雲端硬碟/github/governed_broker_framework/examples/single_agent/results/JOH_FINAL/gemma3_4b")
DIRS = {
    "Group_B (Window)": ROOT / "Group_B",
    "Group_C (Human)": ROOT / "Group_C"
}

def analyze_run(name, path):
    csv_path = path / "simulation_log.csv"
    if not csv_path.exists():
        print(f"[{name}] Missing log: {csv_path}")
        return None

    df = pd.read_csv(csv_path)
    
    # 1. Adaptation Density (AD)
    # Count unique adaptations (Elevation) per agent
    # Filter for 'elevate_house' action
    adaptations = df[df['yearly_decision'] == 'elevate_house']
    # Total Agents
    total_agents = df['agent_id'].nunique()
    if total_agents == 0: total_agents = 1
    
    ad_metric = len(adaptations) / total_agents # Average elevations per agent (should be < 1 generally)
    
    # 2. Rationality Score (RS)
    # We need to find blocked actions. 
    # The CSV usually records the FINAL action. 
    # We need to check if we have an audit log or 'is_modified' column?
    # In the current CSV schema, we often have 'intended_action' vs 'action'.
    # If not, we might need to parse audit.json. 
    # Let's verify columns first.
    
    # Assuming 'intervention_active' or similar exists, OR we infer from audit.json
    # Fallback to RS = N/A if simpler columns missing
    
    return {
        "Name": name,
        "Total Agents": total_agents,
        "Total Years": df['year'].max(),
        "Adaptation Density": ad_metric,
        "Relocation Rate": len(df[df['relocated'] == True]) / len(df) if len(df) > 0 else 0
    }

results = []
print("--- Gemma 3 4B: Group B vs Group C ---")
for name, path in DIRS.items():
    metrics = analyze_run(name, path)
    if metrics:
        results.append(metrics)
        print(f"\n{name}:")
        for k, v in metrics.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.1%}")
            else:
                print(f"  {k}: {v}")

# Comparison
if len(results) == 2:
    print("\n--- Insight ---")
    b = results[0]
    c = results[1]
    
    diff_ad = c['Adaptation Density'] - b['Adaptation Density']
    print(f"Adaptation Density Delta (C - B): {diff_ad:+.1%} ({'Improved' if diff_ad > 0 else 'Regressed'})")
