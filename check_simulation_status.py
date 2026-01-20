
import os
import glob
from pathlib import Path

def count_runs(base_dir):
    print(f"Inventory of {base_dir}")
    print(f"{'Model':<15} | {'Group':<10} | {'Runs Found':<10} | {'Traces Found':<12} | {'Status'}")
    print("-" * 70)
    
    models = ["gemma3_4b", "llama3_2_3b"]
    groups = ["Group_A", "Group_B", "Group_C"]
    
    for model in models:
        for group in groups:
            group_path = Path(base_dir) / "JOH_FINAL" / model / group
            if not group_path.exists():
                print(f"{model:<15} | {group:<10} | {'0':<10} | {'0':<12} | Missing Dir")
                continue
                
            runs = [d for d in os.listdir(group_path) if d.startswith("Run_") and os.path.isdir(group_path / d)]
            trace_count = 0
            complete_count = 0
            
            for run in runs:
                trace_path = group_path / run / "household_traces.jsonl"
                log_path = group_path / run / "simulation_log.csv"
                has_trace = trace_path.exists() and trace_path.stat().st_size > 1000
                has_log = log_path.exists() and log_path.stat().st_size > 1000
                
                if has_trace:
                    trace_count += 1
                if has_log: # Simple proxy for completion
                    complete_count += 1
            
            # Identify status
            status = "Partial"
            if len(runs) >= 10 and trace_count >= 10:
                status = "COMPLETE"
            elif len(runs) == 0:
                status = "Empty"
                
            print(f"{model:<15} | {group:<10} | {len(runs):<10} | {trace_count:<12} | {status}")

if __name__ == "__main__":
    count_runs("examples/single_agent/results")
