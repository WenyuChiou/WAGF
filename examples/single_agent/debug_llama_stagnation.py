import pandas as pd
import json
from pathlib import Path

csv_path = Path("examples/single_agent/results_window/llama3_2_3b_strict/household_governance_audit.csv")

def analyze():
    if not csv_path.exists():
        print("Audit CSV not found.")
        return

    df = pd.read_csv(csv_path)
    # Check columns
    print(f"Columns: {df.columns.tolist()}")
    
    # Filter for years 5 and 6
    print(f"Unique years: {df['year'].unique().tolist()}")
    
    y5 = df[df['year'] == 5]
    y6 = df[df['year'] == 6]
    
    print(f"\n--- Year 5 Distribution ---")
    if not y5.empty:
        print(y5['final_skill'].value_counts())

    else:
        print("Step 5 is empty.")
    
    print(f"\n--- Step 6 Distribution ---")
    if not y6.empty:
        print(y6['final_skill'].value_counts())
    else:
        print("Step 6 is empty.")
    
    # Check if exact agents are doing exact same things
    common_agents = set(y5['agent_id']).intersection(set(y6['agent_id']))
    print(f"\nCommon agents: {len(common_agents)}")
    
    same_count = 0
    diff_count = 0
    for agent in common_agents:
        s5 = y5[y5['agent_id'] == agent]['final_skill'].values[0]
        s6 = y6[y6['agent_id'] == agent]['final_skill'].values[0]
        if s5 == s6:
            same_count += 1
        else:
            diff_count += 1
            
    print(f"Agents with SAME decision: {same_count}")
    print(f"Agents with DIFF decision: {diff_count}")

    # Sample reasoning comparison for a few 'same' agents
    if same_count > 0:
        print("\n--- Sample reasoning for stagnant agents ---")
        sample_agents = list(common_agents)[:3]
        for agent in sample_agents:
            r5 = y5[y5['agent_id'] == agent]['reason_threat_appraisal'].values[0]
            r6 = y6[y6['agent_id'] == agent]['reason_threat_appraisal'].values[0]
            print(f"Agent {agent}:")
            print(f"  Year 5 TP Reason: {r5[:100]}...")
            print(f"  Year 6 TP Reason: {r6[:100]}...")

if __name__ == "__main__":
    analyze()
