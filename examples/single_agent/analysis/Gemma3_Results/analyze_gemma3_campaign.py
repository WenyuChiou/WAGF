
import pandas as pd
import numpy as np
import os
import re
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
RESULTS_DIR = BASE_DIR / "examples" / "single_agent" / "results" / "JOH_FINAL"
OUTPUT_DIR = BASE_DIR / "examples" / "single_agent" / "analysis" / "Gemma3_Results"

def parse_runtime_from_log(log_path):
    """
    Attempts to parse total execution time from execution.log.
    Look for: "Total simulation time: X seconds" or difference between first/last timestamps.
    """
    try:
        if not log_path.exists():
            return None
        
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        start_time = None
        end_time = None
        
        # Simple regex for timestamp [yyyy-MM-dd HH:mm:ss]
        ts_pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
        
        for line in lines:
            if "Starting" in line or "Running Simulation" in line:
                match = ts_pattern.search(line)
                if match:
                    start_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
            
            if "Finished" in line or "Completed" in line or "[Year 10]" in line:
                match = ts_pattern.search(line)
                if match:
                    end_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        
        if start_time and end_time:
            return (end_time - start_time).total_seconds()
            
    except Exception as e:
        print(f"Error parsing log {log_path}: {e}")
    
    return None

def analyze_campaign():
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    
    # 1. Scan for Model Folders (gemma3_1b, etc.)
    if not RESULTS_DIR.exists():
        print(f"Results dir not found: {RESULTS_DIR}")
        return

    model_dirs = [d for d in RESULTS_DIR.iterdir() if d.is_dir()]
    
    for model_dir in model_dirs:
        model_name = model_dir.name # e.g., "gemma3_1b"
        
        for group in ["Group_A", "Group_B", "Group_C"]:
            # Handle potential run subfolders, assume Run_1 for now
            group_dir = model_dir / group / "Run_1"
            if not group_dir.exists():
                # Check directly if no Run_1 subfolder? 
                # The Powershell script creates Run_1.
                continue
                
            print(f"Processing {model_name} - {group}...")
            
            # Paths
            sim_log_path = group_dir / "simulation_log.csv"
            exec_log_path = group_dir / "execution.log"
            
            # 1. Get Runtime (Dynamically)
            runtime_sec = parse_runtime_from_log(exec_log_path)
            
            # 2. Analyze Simulation Log
            if not sim_log_path.exists():
                print(f"  Missing simulation_log.csv for {model_name}/{group}")
                continue
                
            try:
                df = pd.read_csv(sim_log_path)
                
                # N (Total Scientific Steps)
                N = len(df)
                
                # Metrics Extraction
                # V1: Relocations (Outcome)
                if 'cumulative_state' in df.columns:
                    relocated = df['cumulative_state'] == 'Relocate'
                    v1_count = relocated.sum()
                else:
                    v1_count = 0
                
                # Metrics Placeholders - In a real run we'd parse reasoning or audit logs
                # For this baseline, we calculate Velocity and report V1
                
                record = {
                    "Model": model_name,
                    "Group": group,
                    "N": N,
                    "V1_Relocated": v1_count,
                    "Runtime_Min": runtime_sec / 60.0 if runtime_sec else np.nan,
                    "Velocity": (N / (runtime_sec / 60.0)) if runtime_sec and runtime_sec > 0 else np.nan
                }
                
                records.append(record)
                
            except Exception as e:
                print(f"  Error Analyzing CSV: {e}")

    # Save Intermediate Result
    df_res = pd.DataFrame(records)
    output_path = OUTPUT_DIR / "gemma3_preliminary_metrics.csv"
    df_res.to_csv(output_path, index=False)
    print(f"Saved preliminary metrics to {output_path}")

if __name__ == "__main__":
    analyze_campaign()
