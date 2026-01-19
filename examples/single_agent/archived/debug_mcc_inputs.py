
import pandas as pd
import os

paths = [
    r"results\JOH_FINAL\llama3_2_3b\Group_A\Run_2\simulation_log.csv", # Legacy
    # r"results\JOH_FINAL\llama3_2_3b\Group_C\Run_1\simulation_log.csv", 
    # r"results\JOH_FINAL\gemma3_4b\Group_C\Run_1\simulation_log.csv"
]

for p in paths:
    if os.path.exists(p):
        print(f"\n--- Checking {p} ---")
        df = pd.read_csv(p)
        print("Columns:", df.columns.tolist())
        
        # Check Decision Column
        col = 'yearly_decision' if 'yearly_decision' in df.columns else 'decision'
        if col in df.columns:
            print(f"Unique Decisions ({col}):", df[col].unique()[:10])
            print("Sample Decision:", df[col].iloc[0])
        else:
            print("DECISION COLUMN MISSING")
            
        if 'memory' in df.columns:
            print("Scanning for Panic (No Flood + Relocate/Elevate)...")
            col = 'yearly_decision' if 'yearly_decision' in df.columns else 'decision'
            
            for i in range(len(df)):
                mem = str(df['memory'].iloc[i]).lower()
                dec = str(df[col].iloc[i]).lower()
                
                # Check for "No flood" but "Relocate"
                if "no flood" in mem and ("relocate" in dec or "elevate" in dec or "insurance" in dec):
                    print(f"FOUND PANIC at Index {i}:")
                    print(f"  Mem: {mem[:100]}...")
                    print(f"  Dec: {dec}")
                    break
            else:
                print("No Panic found in first scan.")
