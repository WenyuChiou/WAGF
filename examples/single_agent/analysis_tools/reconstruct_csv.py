import json
import pandas as pd
from pathlib import Path
import sys

def reconstruct_csv(jsonl_path, output_csv):
    """Reconstructs simulation_log.csv from household_traces.jsonl."""
    print(f"Processing {jsonl_path}...")
    
    rows = []
    
    # State tracking per agent
    agent_states = {} # agent_id -> {elevated: bool, has_insurance: bool, relocated: bool}

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
            except Exception:
                continue
                
            agent_id = data.get('agent_id')
            step_id = data.get('step_id')
            
            # Estimate year (assuming 100 agents per year)
            # In single-agent parity mode, step_id might be global.
            # Usually step_id 1-100 is Year 1, 101-200 is Year 2 etc.
            year = (step_id - 1) // 100 + 1
            
            # Initial state if new agent
            if agent_id not in agent_states:
                agent_states[agent_id] = {
                    "elevated": False,
                    "has_insurance": False,
                    "relocated": False
                }
            
            curr_state = agent_states[agent_id]
            
            # Get approved skill
            approved = data.get('approved_skill', {})
            skill_name = approved.get('skill_name', 'do_nothing')
            
            # Update state from execution_result
            exec_res = data.get('execution_result', {})
            state_changes = exec_res.get('state_changes', {})
            
            if state_changes:
                if state_changes.get('elevated'): curr_state['elevated'] = True
                if state_changes.get('has_insurance') is not None:
                    curr_state['has_insurance'] = state_changes.get('has_insurance')
                if state_changes.get('relocated'): curr_state['relocated'] = True
            
            # Map skill_name to cumulative_state (narrative)
            # This is a bit heuristic but matches gemma CSV
            state_narrative = "Do Nothing"
            if curr_state['relocated']: state_narrative = "Relocated"
            elif curr_state['elevated']: state_narrative = "Elevated House"
            elif curr_state['has_insurance']: state_narrative = "Only Flood Insurance"

            # Memory
            mem = ""
            if 'memory_pre' in data:
                mem = " | ".join(data['memory_pre'])
            
            rows.append({
                "agent_id": agent_id,
                "year": year,
                "cumulative_state": state_narrative,
                "yearly_decision": skill_name,
                "elevated": curr_state['elevated'],
                "has_insurance": curr_state['has_insurance'],
                "relocated": curr_state['relocated'],
                "trust_insurance": 0.5, # Placeholder if missing
                "trust_neighbors": 0.5, # Placeholder if missing
                "memory": mem
            })
            
    if not rows:
        print(f"No data found in {jsonl_path}")
        return
        
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} rows to {output_csv}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python reconstruct_csv.py <input_jsonl> <output_csv>")
    else:
        reconstruct_csv(sys.argv[1], sys.argv[2])
