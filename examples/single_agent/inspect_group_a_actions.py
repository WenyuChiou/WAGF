
import os
import pandas as pd
from pathlib import Path

def inspect_actions():
    base_dir = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL"
    group_a_dir = os.path.join(base_dir, "gemma3_4b", "Group_A")
    
    print(f"Inspecting Group A actions in: {group_a_dir}")
    
    all_decisions = []
    
    for run in os.listdir(group_a_dir):
        if not run.startswith("Run_"): continue
        run_path = os.path.join(group_a_dir, run)
        
        # Find log
        logs = list(Path(run_path).rglob("simulation_log.csv"))
        if not logs: continue
        
        df = pd.read_csv(logs[0])
        if 'yearly_decision' in df.columns:
            all_decisions.extend(df['yearly_decision'].astype(str).tolist())
        elif 'decision' in df.columns:
            all_decisions.extend(df['decision'].astype(str).tolist())
            
    # Count frequencies
    s = pd.Series(all_decisions)
    print("\nAction Counts for Group A:")
    print(s.value_counts())

if __name__ == "__main__":
    inspect_actions()
