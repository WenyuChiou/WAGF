import json
from pathlib import Path
import pandas as pd

BASE_DIR = Path("examples/single_agent/results_window")

models = [
    {
        "name": "Llama 3.2 (3B)",
        "path": "llama3_2_3b_strict/raw/household_traces.jsonl"
    },
    {
        "name": "Gemma 3 (4B)",
        "path": "gemma3_4b_strict/raw/household_traces.jsonl"
    }
]

def check_status():
    print("--- Current Benchmark Status (Parity Edition) ---")
    for m in models:
        file_path = BASE_DIR / m["path"]
        if not file_path.exists():
            print(f"[{m['name']}] Waiting for data... (File not found: {file_path})")
            continue
            
        try:
            decisions = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        trace = json.loads(line)
                        skill = trace.get("approved_skill", {}).get("skill_name", "unknown")
                        decisions.append(skill)
                    except:
                        continue
            
            total = len(decisions)
            if total == 0:
                print(f"[{m['name']}] Log initialized but empty.")
                continue

            # Count Relocations & Insurance
            relocs = decisions.count("relocate")
            insure = decisions.count("buy_insurance")
            
            r_rate = (relocs / total) * 100
            i_rate = (insure / total) * 100
            
            print(f"[{m['name']}]")
            print(f"  - Total Decisions: {total}")
            print(f"  - Relocations:     {relocs} ({r_rate:.1f}%)")
            print(f"  - Buy Insurance:   {insure} ({i_rate:.1f}%)")
            
            # Simple Behavioral Check
            if "Llama" in m["name"]:
                if r_rate > 20: 
                    print("  -> TREND: HIGH Relocation (Baseline behavior restoring)")
                elif r_rate < 5:
                    print("  -> TREND: LOW Relocation (Still dropped?)")
                
                if i_rate < 5:
                     print("  -> NOTICE: Very Low Insurance rate (Confirmation: 'No Insurance' hypothesis)")

            
        except Exception as e:
            print(f"[{m['name']}] Error reading log: {e}")

if __name__ == "__main__":
    check_status()
