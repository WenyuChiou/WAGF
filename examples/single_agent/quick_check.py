import json
from pathlib import Path

def analyze_traces(path):
    print(f"Analyzing {path}...")
    # Map global step_id to Year (1-10)
    # Assumes years_per_agent = 10
    total_processed = 0
    eh_by_year = [0] * 11 # Year 1 to 10
    total_by_year = [0] * 11
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                d = json.loads(line)
                step = d.get('step_id', 0)
                # Year = ((step - 1) % 10) + 1
                year = ((step - 1) % 10) + 1
                skill = d.get('approved_skill', {}).get('skill_name', '').lower()
                
                total_by_year[year] += 1
                if 'elevate' in skill:
                    eh_by_year[year] += 1
                total_processed += 1
        
        print("\nEH Decision Distribution (Current Progress):")
        for yr in range(1, 11):
            if total_by_year[yr] > 0:
                rate = eh_by_year[yr] / total_by_year[yr]
                print(f"Year {yr}: {eh_by_year[yr]}/{total_by_year[yr]} ({rate:.1%})")
    except Exception as e:
        print(f"Error: {e}")

trace_file = Path("results/JOH_FINAL/gemma3_4b/Group_A/Run_1/gemma3_4b_disabled/raw/household_traces.jsonl")
if trace_file.exists():
    analyze_traces(trace_file)
else:
    print(f"No traces found yet at {trace_file}")
