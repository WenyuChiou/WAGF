"""
Deep investigation of static behavior in Gemma Window Memory results
"""
import pandas as pd
from pathlib import Path

WINDOW_PATH = Path("examples/single_agent/results_window/gemma3_4b_strict/simulation_log.csv")

print("=" * 70)
print("INVESTIGATION: Why is agent behavior static in non-flood years?")
print("=" * 70)

df = pd.read_csv(WINDOW_PATH)

# Check if decisions actually change year-over-year for each agent
print("\n[1] Year-over-Year Decision Changes Per Agent]")
print("-" * 50)

changes_by_year = {}
for year in range(2, 11):
    prev_year = year - 1
    prev_df = df[df['year'] == prev_year][['agent_id', 'cumulative_state']].copy()
    curr_df = df[df['year'] == year][['agent_id', 'cumulative_state']].copy()
    
    merged = prev_df.merge(curr_df, on='agent_id', suffixes=('_prev', '_curr'))
    changed = merged[merged['cumulative_state_prev'] != merged['cumulative_state_curr']]
    
    changes_by_year[year] = len(changed)
    print(f"  Year {prev_year} -> {year}: {len(changed)} agents changed decision")

# Check memory content for a few agents across years
print("\n[2] Sample Agent Memory Evolution (Agent_1)]")
print("-" * 50)
agent1 = df[df['agent_id'] == 'Agent_1'][['year', 'cumulative_state', 'memory']].copy()
for _, row in agent1.iterrows():
    year = row['year']
    state = row['cumulative_state']
    memory = row['memory'][:150] + "..." if len(str(row['memory'])) > 150 else row['memory']
    print(f"\n  Year {year}: {state}")
    print(f"    Memory: {memory}")

# Check if elevated agents are making any decisions
print("\n\n[3] Elevated Agent Decisions by Year]")
print("-" * 50)
for year in range(1, 11):
    year_df = df[df['year'] == year]
    elevated_df = year_df[year_df['elevated'] == True]
    if len(elevated_df) > 0:
        elev_decisions = elevated_df['cumulative_state'].value_counts().to_dict()
        print(f"  Year {year} (Elevated={len(elevated_df)}): {elev_decisions}")

# Check trust values - are they changing?
print("\n\n[4] Trust Value Changes]")
print("-" * 50)
for year in range(1, 11):
    year_df = df[df['year'] == year]
    avg_trust_ins = year_df['trust_insurance'].mean()
    avg_trust_nei = year_df['trust_neighbors'].mean()
    print(f"  Year {year}: Avg Trust Insurance={avg_trust_ins:.3f}, Avg Trust Neighbors={avg_trust_nei:.3f}")

# Key Issue: What percentage of agents are making ACTIVE decisions vs repeating?
print("\n\n[5] Decision Pattern Analysis]")
print("-" * 50)
print("Are agents 'stuck' repeating the same decision?")

stuck_agents = []
for agent in df['agent_id'].unique():
    agent_df = df[df['agent_id'] == agent]
    # Check last 5 years (6-10)
    last5 = agent_df[agent_df['year'] >= 6]['cumulative_state'].tolist()
    if len(set(last5)) == 1:
        stuck_agents.append(agent)

print(f"  Agents with same decision for years 6-10: {len(stuck_agents)} / 100")
print(f"  (These agents are behaviorally 'stuck')")

# Sample of stuck agents
if stuck_agents[:5]:
    print(f"\n  Sample stuck agents: {stuck_agents[:5]}")
    for agent in stuck_agents[:3]:
        agent_df = df[df['agent_id'] == agent]
        decisions = agent_df[['year', 'cumulative_state']].to_dict('records')
        print(f"    {agent}: {[d['cumulative_state'] for d in decisions]}")

print("\n\n[6] ROOT CAUSE ANALYSIS]")
print("=" * 70)
print("""
HYPOTHESIS: The 'cumulative_state' column might show the CURRENT TOTAL STATE
rather than the DECISION MADE THIS YEAR. 

Once an agent elevates, their cumulative_state stays "Only House Elevation"
even if they don't make any new decision.

This would explain why years 5-8 are identical - agents who elevated 
in Year 3-4 continue to show that state.
""")

# Verify: Check what column actually represents yearly decisions
print("\n[7] Looking for actual yearly decision column...]")
print(f"  Available columns: {df.columns.tolist()}")

# Check if there's a trace or raw directory with more details
import os
raw_path = Path("examples/single_agent/results_window/gemma3_4b_strict/gemma3_4b_strict/raw")
if raw_path.exists():
    print(f"\n  Found raw traces at: {raw_path}")
    files = list(raw_path.iterdir())[:5]
    print(f"  Files: {[f.name for f in files]}")
else:
    print(f"\n  No raw traces found at expected path")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
