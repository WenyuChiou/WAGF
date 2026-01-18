import pandas as pd
import os

# Path to the log file (Llama 3.2 3B, Group A, Run 1)
LOG_PATH = r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\llama3_2_3b\Group_A\Run_1\flood_adaptation_simulation_log.csv"

def analyze_cumulative_effects():
    if not os.path.exists(LOG_PATH):
        print(f"Error: Log file not found at {LOG_PATH}")
        return

    df = pd.read_csv(LOG_PATH)
    
    # 1. Sort by Agent and Year
    df = df.sort_values(by=['agent_id', 'year'])
    
    # 2. Track Agents with *cumulative* flood memories
    # We want to find agents who:
    #   - Were flooded multiple times within a 5-year window
    #   - Had "Do Nothing" initially
    #   - Switched to "Insurance" or "Elevate" AFTER the memories accumulated
    
    print(f"Analyzing {len(df['agent_id'].unique())} agents over {df['year'].max()} years...\n")
    
    interesting_cases = []
    
    high_stress_count = 0
    adaptation_count = 0
    
    for agent_id in df['agent_id'].unique():
        agent_df = df[df['agent_id'] == agent_id].reset_index(drop=True)
        
        flood_years = []
        history_summary = []
        max_memories_seen = 0
        
        for i, row in agent_df.iterrows():
            year = row['year']
            flooded = row['flooded_this_year']
            decision = row['decision']
            memory = str(row['memory'])
            
            # Count how many "Got flooded" entries are in memory explicitly
            flood_memories = memory.lower().count("got flooded")
            if flood_memories > max_memories_seen:
                max_memories_seen = flood_memories
            
            if flooded:
                flood_years.append(year)
                
            history_summary.append({
                'year': year,
                'decision': decision,
                'flooded': flooded,
                'flood_memories_count': flood_memories,
                'memory_snippet': memory[-100:] if len(memory) > 100 else memory # Last part of memory
            })
            
            # Check for cumulative logic:
            # If we have >1 flood memories AND we switched from Do Nothing/Insurance -> Elevate or Do Nothing -> Insurance
            if flood_memories >= 2:
                # Look at previous decision (if exists)
                if i > 0:
                    prev_decision = agent_df.iloc[i-1]['decision']
                    if prev_decision == "Do Nothing" and decision != "Do Nothing":
                         interesting_cases.append({
                             'agent_id': agent_id,
                             'year': year,
                             'trigger': f"Accumulated {flood_memories} floods",
                             'change': f"{prev_decision} -> {decision}",
                             'history': history_summary[-3:] # Show last 3 years context
                         })
                         # Break after finding the first major shift to avoid spam
                         break
        
        if max_memories_seen >= 2:
            high_stress_count += 1

    print(f"Stats:")
    print(f"- Total Agents: {len(df['agent_id'].unique())}")
    print(f"- Agents with 2+ Flood Memories (High Stress): {high_stress_count}")
    print(f"- Agents who Adapted under High Stress: {len(interesting_cases)}")
                         
    # 3. Report Results
    print(f"\nFound {len(interesting_cases)} agents showing potential cumulative adaptation:\n")
    for case in interesting_cases[:5]: # Show top 5 examples
        print(f"--- {case['agent_id']} (Year {case['year']}) ---")
        print(f"Trigger: {case['trigger']}")
        print(f"Behavior Change: {case['change']}")
        print("Recent History:")
        for h in case['history']:
            flood_mark = "[FLOOD]" if h['flooded'] else ""
            print(f"  Year {h['year']}: {h['decision']} {flood_mark} (Memories of Flood: {h['flood_memories_count']})")
        print("")

if __name__ == "__main__":
    analyze_cumulative_effects()
