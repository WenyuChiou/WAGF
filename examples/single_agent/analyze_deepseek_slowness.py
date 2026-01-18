import pandas as pd
import json
from pathlib import Path
import numpy as np

# Path to the partial DeepSeek trace
TRACE_PATH = Path(r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\deepseek_r1_8b\Group_B\Run_1\deepseek_r1_8b_strict\raw\household_traces.jsonl")

def analyze_slowness():
    if not TRACE_PATH.exists():
        print("Trace file not found.")
        return

    print(f"Reading {TRACE_PATH}...")
    
    decisions = []
    with open(TRACE_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
                # Extract relevant metrics
                # Assuming entry has 'timestamp', 'raw_output' (CoT), 'year'
                
                # Calculate reasoning length (approx tokens)
                raw_len = len(entry.get('raw_output', ''))
                
                decisions.append({
                    'step': entry.get('step_id'),
                    'agent': entry.get('agent_id'),
                    'year': entry.get('year'),
                    'reasoning_chars': raw_len,
                    'timestamp': pd.to_datetime(entry.get('timestamp'))
                })
            except Exception as e:
                pass

    if not decisions:
        print("No valid decisions found.")
        return

    df = pd.DataFrame(decisions)
    df = df.sort_values('timestamp')
    
    # Calculate time delta between decisions
    df['time_diff'] = df['timestamp'].diff().dt.total_seconds()
    
    avg_time = df['time_diff'].mean()
    avg_chars = df['reasoning_chars'].mean()
    total_decisions = len(df)
    
    print(f"\n=== DeepSeek R1 8B Performance Analysis ===")
    print(f"Total Decisions Processed: {total_decisions}")
    print(f"Average Time per Decision: {avg_time:.2f} seconds")
    print(f"Average CoT Length: {avg_chars:.0f} characters (~{avg_chars/4:.0f} tokens)")
    print(f"Estimated Time for 100 Agents x 10 Years (1000 steps): {(avg_time * 1000)/3600:.2f} hours per Run")
    
    # Save small report
    df[['step', 'agent', 'reasoning_chars', 'time_diff']].head(10).to_csv("deepseek_slowness_sample.csv")

if __name__ == "__main__":
    analyze_slowness()
