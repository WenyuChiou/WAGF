import os
import pandas as pd
import numpy as np
import glob

def calculate_consistency(group_dir):
    """
    Calculates the 'Agent-Level Consistency Score' across multiple runs.
    Consistency = % of runs where the agent made the SAME final adaptation choice (e.g., Elevated vs Not).
    """
    print(f"Analyzing Consistency in: {group_dir}")
    
    # 1. Gather all Run folders
    run_folders = glob.glob(os.path.join(group_dir, "*Run_*"))
    if not run_folders:
        # Try raw Run_X folders if model name prefix missing
        run_folders = glob.glob(os.path.join(group_dir, "Run_*"))
        
    print(f"Found {len(run_folders)} runs.")
    if len(run_folders) < 2:
        print("Need at least 2 runs to calculate consistency.")
        return

    # 2. Build Agent State Matrix
    # Rows = Agents, Cols = Runs, Value = Final State (Elevated/Relocated/None)
    agent_states = {} # {agent_id: [state_run1, state_run2, ...]}

    for run_path in run_folders:
        log_path = os.path.join(run_path, "simulation_log.csv")
        if not os.path.exists(log_path):
            print(f"Skipping missing log: {log_path}")
            continue
            
        df = pd.read_csv(log_path)
        
        # Get final state for each agent
        # We look at the last recorded year for each agent
        # Assuming agents don't die (or we take last active state)
        # We need 'Elevated' column or 'Action' history.
        # simulation_log has 'Action', 'AgentID'.
        # State = Elevated if they *ever* elevated.
        
        # Group by Agent
        for agent_id, group in df.groupby("agent_id"):
            # Determine final status
            # Check if 'Elevate House' or 'Relocate' occurred ANYWHERE in history
            actions = group["yearly_decision"].unique()
            
            is_relocated = any("relocate" in str(a).lower() for a in actions)
            is_elevated = any("elevate" in str(a).lower() for a in actions)
            
            if is_relocated:
                state = "Relocated"
            elif is_elevated:
                state = "Elevated"
            else:
                state = "None"
                
            if agent_id not in agent_states:
                agent_states[agent_id] = []
            agent_states[agent_id].append(state)

    # 3. Calculate Consistency
    # For each agent, consistency = (Max Count of Dominant State) / (Total Runs)
    # e.g., [Elevated, Elevated, None] -> 2/3 = 0.66
    
    consistencies = []
    
    for agent_id, states in agent_states.items():
        if not states:
            continue
            
        # Count frequency of each state
        counts = pd.Series(states).value_counts()
        most_common_count = counts.iloc[0]
        total = len(states)
        
        score = most_common_count / total
        consistencies.append(score)
        
    avg_consistency = np.mean(consistencies)
    std_consistency = np.std(consistencies)
    
    print(f"\n--- Results for {os.path.basename(group_dir)} ---")
    print(f"Total Agents Analyzed: {len(consistencies)}")
    print(f"Average Agent Consistency: {avg_consistency:.4f} (1.0 = Perfect Determinism)")
    print(f"Std Dev: {std_consistency:.4f}")
    
    if avg_consistency > 0.9:
        print("VERDICT: Highly Rigid/Stable (Deterministic Governance wins)")
    elif avg_consistency < 0.6:
        print("VERDICT: Highly Stochastic (LLM Creativity wins)")
    else:
        print("VERDICT: Balanced (Bounded Rationality)")

if __name__ == "__main__":
    # Point this to Group C
    BASE_PATH = r"results/JOH_FINAL/gemma3_4b/Group_C"
    calculate_consistency(BASE_PATH)
