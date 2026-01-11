
import json
from pathlib import Path

def check_log(model_name, log_path):
    print(f"\nScanning {model_name}...")
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = [json.loads(line) for line in f]
            
        found = False
        for l in lines:
            skill = l.get('approved_skill', {}).get('skill_name')
            if skill == 'relocate':
                reasoning = l.get('skill_proposal', {}).get('reasoning', {})
                tp = reasoning.get('TP_LABEL')
                cp = reasoning.get('CP_LABEL')
                year = l.get('year')
                
                print(f"  [Year {year}] Relocate Reasoning Dump:")
                print(json.dumps(reasoning, indent=2))
                found = True
                if found: break # Just show first one
                
        if not found:
            print("  No relocation found.")
            
    except Exception as e:
        print(f"  Error reading log: {e}")

if __name__ == "__main__":
    check_log("Llama", r"h:\我的雲端硬碟\github\governed_broker_framework\results_v4.2\llama3\llama3.2_3b\household_audit.jsonl")
    check_log("Gemma", r"h:\我的雲端硬碟\github\governed_broker_framework\results_v4.2\gemma\gemma3_4b\household_audit.jsonl")
