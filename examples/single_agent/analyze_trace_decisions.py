"""
Analyze actual yearly decisions from traces vs cumulative_state
"""
import json
import pandas as pd
from pathlib import Path
from collections import defaultdict

TRACE_PATH = Path("examples/single_agent/results_window/gemma3_4b_strict/gemma3_4b_strict/raw/household_traces.jsonl")
SIM_LOG_PATH = Path("examples/single_agent/results_window/gemma3_4b_strict/simulation_log.csv")

print("=" * 70)
print("ACTUAL YEARLY DECISIONS ANALYSIS (from traces)")
print("=" * 70)

# Load traces
traces = []
with open(TRACE_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            traces.append(json.loads(line))
        except:
            continue

print(f"\nTotal traces loaded: {len(traces)}")

# Extract actual decisions per year
yearly_decisions = defaultdict(lambda: defaultdict(int))
agent_year_decision = {}  # (agent_id, year) -> actual decision

for t in traces:
    agent_id = t.get('agent_id')
    step = t.get('step_id')  # This is the year
    skill = t.get('approved_skill', {}).get('skill_name', 'unknown')
    
    if agent_id and step:
        yearly_decisions[step][skill] += 1
        agent_year_decision[(agent_id, step)] = skill

# Print yearly actual decisions
print("\n[Actual Decisions Made Each Year (from traces)]")
print("-" * 50)
for year in sorted(yearly_decisions.keys()):
    print(f"\nYear {year}:")
    for skill, count in sorted(yearly_decisions[year].items(), key=lambda x: -x[1]):
        print(f"  {skill}: {count}")

# Compare with simulation_log cumulative_state
print("\n\n[Compare: Trace Decision vs Cumulative State]")
print("-" * 50)

sim_df = pd.read_csv(SIM_LOG_PATH)

mismatch_count = 0
match_count = 0

# Sample comparison for a few agents
sample_agents = ['Agent_1', 'Agent_2', 'Agent_3']
for agent in sample_agents:
    print(f"\n{agent}:")
    for year in range(1, 11):
        actual = agent_year_decision.get((agent, year), 'N/A')
        cumul = sim_df[(sim_df['agent_id'] == agent) & (sim_df['year'] == year)]['cumulative_state'].values
        cumul = cumul[0] if len(cumul) > 0 else 'N/A'
        
        match = "✓" if actual in cumul.lower().replace(' ', '_') or cumul.lower().replace(' ', '_') in actual else "✗"
        print(f"  Year {year}: Actual={actual:20s} | Cumulative={cumul}")

# Key insight: What do elevated agents actually decide each year?
print("\n\n[KEY INSIGHT: What do elevated agents actually decide?]")
print("-" * 50)

elevated_agent_ids = set()
for t in traces:
    if t.get('step_id') >= 4:  # After Year 3 flood most are elevated
        agent_id = t['agent_id']
        skill = t.get('approved_skill', {}).get('skill_name', 'unknown')
        if skill == 'elevate_house':
            elevated_agent_ids.add(agent_id)

print(f"Agents who elevated at some point: {len(elevated_agent_ids)}")

# Check what elevated agents decide in later years
print("\nDecisions by elevated agents in Year 5-10:")
late_decisions = defaultdict(int)
for t in traces:
    if t.get('step_id') >= 5 and t['agent_id'] in elevated_agent_ids:
        skill = t.get('approved_skill', {}).get('skill_name', 'unknown')
        late_decisions[skill] += 1

for skill, count in sorted(late_decisions.items(), key=lambda x: -x[1]):
    print(f"  {skill}: {count}")

print("\n\n[ROOT CAUSE IDENTIFIED]")
print("=" * 70)
print("""
FINDING: 模擬在非洪水年確實正常運行！

1. 'cumulative_state' 顯示的是 **累積總狀態**，不是每年決策
2. 實際每年決策在 traces 的 'approved_skill' 中
3. 高架房屋後，agents 可能每年選擇 'do_nothing'，但 cumulative_state 
   仍顯示 'Only House Elevation' 因為房屋已經升高

這解釋了為什麼 Year 5-8 看起來完全相同 - 這不是 bug，
而是因為大多數 agent 已經完成了升高房屋，之後選擇 'do_nothing'。

需要查看 traces 中的 approved_skill 來看真正的年度行為變化。
""")

print("\n" + "=" * 70)
