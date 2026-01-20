
import os
import pandas as pd
import json
from pathlib import Path

BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b"

def get_group_a_stats():
    # Group A: Simulation Logs only
    path = os.path.join(BASE_DIR, "Group_A")
    actions = []
    
    # We can try to infer threat from memory, but for now let's just get Actions
    if os.path.exists(path):
        for run in os.listdir(path):
            if not run.startswith("Run_"): continue
            logs = list(Path(os.path.join(path, run)).rglob("simulation_log.csv"))
            if not logs: continue
            
            try:
                df = pd.read_csv(logs[0])
                if 'yearly_decision' in df.columns:
                    actions.extend(df['yearly_decision'].astype(str).tolist())
                elif 'decision' in df.columns:
                    actions.extend(df['decision'].astype(str).tolist())
            except: pass
            
    return pd.Series(actions).value_counts()

def get_group_b_stats():
    # Group B: Household Traces (Rich Data)
    path = os.path.join(BASE_DIR, "Group_B")
    actions = []
    threats = []
    
    if os.path.exists(path):
        for run in os.listdir(path):
            # Look for traces in potential subdirectories
            files = list(Path(os.path.join(path, run)).rglob("household_traces.jsonl"))
            if not files: continue
            
            fpath = files[0]
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            record = json.loads(line)
                            
                            # Extract Threat
                            if 'threat_appraisal' in record:
                                if isinstance(record['threat_appraisal'], dict):
                                    t_lbl = record['threat_appraisal'].get('threat_label', 'Unknown')
                                    threats.append(t_lbl)
                                else:
                                    threats.append(str(record['threat_appraisal'])) # Legacy format?
                            
                            # Extract Action
                            if 'decision' in record:
                                if isinstance(record['decision'], dict):
                                    skill = record['decision'].get('skill', 'Unknown')
                                    actions.append(skill)
                                else:
                                    actions.append(str(record['decision']))
                        except: pass
            except Exception as e:
                print(f"Error reading {fpath}: {e}")
        
    return pd.Series(actions).value_counts(), pd.Series(threats).value_counts()

def main():
    print("Collecting Group A Stats...")
    a_acts = get_group_a_stats()
    
    print("Collecting Group B Stats...")
    b_acts, b_throats = get_group_b_stats()
    
    print("\n" + "="*40)
    print("  COMPARATIVE DISTRIBUTION ANALYSIS")
    print("="*40)
    
    print("\n[GROUP A: BASELINE] (Actions Only)")
    print(a_acts)
    
    print("\n[GROUP B: GOVERNED] (Internal State)")
    print("--- Threat Perception ---")
    print(b_throats)
    print("\n--- Actions Taken ---")
    print(b_acts)
    
    print("\n" + "="*40)

if __name__ == "__main__":
    main()
