"""
Corrected Trace Analysis - Using proper year extraction
"""
import json
import pandas as pd
from pathlib import Path
from collections import defaultdict

TRACE_PATH = Path("examples/single_agent/results_window/gemma3_4b_strict/gemma3_4b_strict/raw/household_traces.jsonl")

print("=" * 70)
print("CORRECTED TRACE ANALYSIS")
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

# Look for year info in trace - check memory or input
sample = traces[0]
print("\n[Sample trace structure]")
print(f"Keys: {list(sample.keys())}")

# Check memory_pre for year info
print(f"\nMemory Pre: {sample.get('memory_pre', [])[:2]}")

# Extract year from memory - first memory often contains year info  
def extract_year(trace):
    memory = trace.get('memory_pre', [])
    if memory:
        first_mem = memory[0]
        # Pattern: "Year X: ..."
        if 'Year' in first_mem:
            try:
                year_part = first_mem.split(':')[0]
                year = int(year_part.replace('Year', '').strip())
                return year
            except:
                pass
    return None

# Group traces by agent and year
agent_year_traces = defaultdict(dict)
for t in traces:
    agent_id = t.get('agent_id')
    year = extract_year(t)
    skill = t.get('approved_skill', {}).get('skill_name', 'unknown')
    tp_label = t.get('skill_proposal', {}).get('reasoning', {}).get('TP_LABEL', 'N/A')
    cp_label = t.get('skill_proposal', {}).get('reasoning', {}).get('CP_LABEL', 'N/A')
    
    if year and agent_id:
        agent_year_traces[(agent_id, year)] = {
            'skill': skill,
            'tp': tp_label,
            'cp': cp_label
        }

# Summarize by year
print("\n[Actual Decisions by Year]")
print("-" * 50)
yearly_summary = defaultdict(lambda: defaultdict(int))

for (agent, year), data in agent_year_traces.items():
    yearly_summary[year][data['skill']] += 1

for year in sorted(yearly_summary.keys()):
    if year <= 10:  # Only show first 10 years
        print(f"\nYear {year}:")
        for skill, count in sorted(yearly_summary[year].items(), key=lambda x: -x[1]):
            print(f"  {skill}: {count}")

# Show threat/coping appraisal patterns by year
print("\n\n[Threat/Coping Appraisal Patterns by Year]")
print("-" * 50)
yearly_tp_cp = defaultdict(lambda: defaultdict(int))

for (agent, year), data in agent_year_traces.items():
    if year and year <= 10:
        key = f"TP={data['tp']}, CP={data['cp']}"
        yearly_tp_cp[year][key] += 1

for year in sorted(yearly_tp_cp.keys()):
    print(f"\nYear {year}:")
    for pattern, count in sorted(yearly_tp_cp[year].items(), key=lambda x: -x[1])[:5]:
        print(f"  {pattern}: {count}")

# Check Year 5-8 specifically - are agents making decisions or just showing cumulative state?
print("\n\n[DEEP DIVE: Years 5-8]")
print("-" * 50)

for year in [5, 6, 7, 8]:
    print(f"\nYear {year}:")
    year_traces = [(a, d) for (a, y), d in agent_year_traces.items() if y == year]
    
    if year_traces:
        skills = defaultdict(int)
        for agent, data in year_traces:
            skills[data['skill']] += 1
        
        for skill, count in sorted(skills.items(), key=lambda x: -x[1]):
            print(f"  {skill}: {count}")
        
        # Sample reasoning
        sample_agents = [a for a, d in year_traces if d['skill'] == 'do_nothing'][:2]
        if sample_agents:
            print(f"  Sample 'do_nothing' agents: {sample_agents}")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
