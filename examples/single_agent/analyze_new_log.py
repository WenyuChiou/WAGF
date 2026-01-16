"""
Analyze the new simulation_log.csv with yearly_decision column
and verify traces file cleanliness.
"""
import pandas as pd
import json
from pathlib import Path
from collections import Counter

LOG_PATH = Path("examples/single_agent/results/gemma3_4b_strict/simulation_log.csv")
TRACE_PATH = Path("examples/single_agent/results_window/gemma3_4b_strict/gemma3_4b_strict/raw/household_traces.jsonl")

print("=" * 80)
print("ANALYSIS OF NEW RUN (Clean Context & Yearly Decisions)")
print("=" * 80)

# 1. Verify Traces Cleanliness
print("\n[Trace File Verification]")
if TRACE_PATH.exists():
    with open(TRACE_PATH, 'r', encoding='utf-8') as f:
        traces = [json.loads(line) for line in f]
    
    print(f"Total traces found: {len(traces)}")
    run_ids = set(t.get('run_id') for t in traces)
    print(f"Unique run_ids: {run_ids}")
    
    if len(run_ids) == 1:
        print("[OK] SUCCESS: Only one run_id present. Context clean.")
    else:
        print(f"[WARNING] {len(run_ids)} run_ids found! Cleanup failed?")
else:
    print("[WARNING] Traces file not found yet (maybe run incomplete?)")

# 2. Analyze Yearly Decisions from CSV
print("\n[Yearly Decision Analysis from CSV]")
if LOG_PATH.exists():
    df = pd.read_csv(LOG_PATH)
    
    if 'yearly_decision' not in df.columns:
        print("[ERROR] 'yearly_decision' column missing in CSV!")
    else:
        # Filter out relocated agents for clearer decision view? 
        # Actually we want to see what active agents did.
        
        # Group by Year and Yearly Decision
        pivot = df.pivot_table(index='year', columns='yearly_decision', aggfunc='size', fill_value=0)
        
        print("\nYearly Decision Counts:")
        print(pivot)
        
        print("\n[Detailed Breakdown]")
        for year in sorted(df['year'].unique()):
            print(f"\nYear {year}:")
            year_df = df[df['year'] == year]
            counts = year_df['yearly_decision'].value_counts()
            total = len(year_df)
            for decision, count in counts.items():
                print(f"  {decision}: {count} ({count/total*100:.1f}%)")
                
            # Check Cumulative vs Yearly
            # E.g. how many "Only House Elevation" people chose "do_nothing"?
            elevated_agents = year_df[year_df['cumulative_state'] == 'Only House Elevation']
            if not elevated_agents.empty:
                print(f"  --> Of {len(elevated_agents)} elevated agents:")
                elev_decisions = elevated_agents['yearly_decision'].value_counts()
                for d, c in elev_decisions.items():
                    print(f"      Choose {d}: {c}")

else:
    print("[ERROR] Simulation log not found.")
