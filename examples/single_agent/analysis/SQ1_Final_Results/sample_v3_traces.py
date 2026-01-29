
import json
import pandas as pd
from pathlib import Path

def find_v3_traces():
    root = Path("examples/single_agent/results/JOH_FINAL")
    model = "deepseek_r1_14b"
    group = "Group_B"
    run_dir = root / model / group / "Run_1"
    
    csv_path = run_dir / "simulation_log.csv"
    jsonl_path = run_dir / "raw" / "household_traces.jsonl"
    
    if not csv_path.exists() or not jsonl_path.exists():
        print("Files not found.")
        return

    df = pd.read_csv(csv_path)
    # Filter for Do Nothing when TP is H or VH (V3)
    # We don't have TP in CSV for 14B usually unless it was extracted.
    # Let's just look for 'do_nothing' in JSONL and check their labels.
    
    print(f"Sampling V3 traces for {model} {group}...")
    samples = 0
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                proposal = data.get('skill_proposal', {})
                skill = proposal.get('skill_name', '').lower()
                
                reasoning = proposal.get('reasoning', {})
                tp = reasoning.get('TP_LABEL', 'M')
                cp = reasoning.get('CP_LABEL', 'M')
                
                if skill == 'do_nothing' and tp in ['H', 'VH']:
                    samples += 1
                    print(f"\n[Sample {samples}] Step: {data.get('step_id')}")
                    print(f"Skill: {skill}")
                    print(f"TP: {tp} | CP: {cp}")
                    # print(f"Reasoning: {reasoning}")
                    print(f"Retry Count: {data.get('retry_count', 0)}")
                    print(f"Validation Results: {data.get('validation_results', [])}")
                    
                    if samples >= 5: break
            except: continue

if __name__ == "__main__":
    find_v3_traces()
