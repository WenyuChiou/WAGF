
import json
import pandas as pd
from pathlib import Path

def sample_8b_v2():
    root = Path("examples/single_agent/results/JOH_FINAL")
    model = "deepseek_r1_8b"
    group = "Group_A"
    run_dir = root / model / group / "Run_1"
    
    csv_path = run_dir / "simulation_log.csv"
    
    if not csv_path.exists():
        print("CSV not found.")
        return

    df = pd.read_csv(csv_path)
    df.columns = [c.lower() for c in df.columns]
    
    # Check decision distribution
    dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
    print("\n--- Decision Counts for 8B Group A ---")
    print(df[dec_col].value_counts().head(10))
    
    # Find indices where it might be V2
    # V2 = (TP not in H/VH) and (Decision == Elevation)
    # We need to map TP from raw if not in CSV
    
    jsonl_path = run_dir / "raw" / "household_traces.jsonl"
    if jsonl_path.exists():
        print("\n--- Sampling Reasoning for Elevation Decisions ---")
        samples = 0
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    skill = data.get('skill_proposal', {}).get('skill_name', '').lower()
                    if 'elevate' in skill:
                        samples += 1
                        reasoning = data.get('skill_proposal', {}).get('reasoning', {})
                        tp = reasoning.get('TP_LABEL', 'M')
                        print(f"Sample {samples}: TP={tp}, Decision={skill}")
                        # print(f"Reasoning text: {reasoning.get('TP_REASON', '')[:100]}")
                        if samples >= 10: break
                except: continue

if __name__ == "__main__":
    sample_8b_v2()
