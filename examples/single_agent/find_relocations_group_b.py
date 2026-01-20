
import os
import json
from pathlib import Path

BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b\Group_B"

def find_relocations():
    print(f"Scanning for relocations in {BASE_DIR}...")
    
    total_records = 0
    relocation_count = 0
    decisions = {}
    
    for run in os.listdir(BASE_DIR):
        path = os.path.join(BASE_DIR, run)
        if not os.path.isdir(path): continue
        
        # Find traces
        traces = list(Path(path).rglob("household_traces.jsonl"))
        for trace_path in traces:
            try:
                with open(trace_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip(): continue
                        total_records += 1
                        try:
                            data = json.loads(line)
                            
                            # Brute force search in the record
                            decision_found = "None"
                            
                            # Check explicit keys first
                            if 'approved_skill' in data:
                                if isinstance(data['approved_skill'], dict):
                                    decision_found = data['approved_skill'].get('skill', 'Unknown')
                                else:
                                    decision_found = str(data['approved_skill'])
                            elif 'skill_proposal' in data:
                                if isinstance(data['skill_proposal'], dict):
                                    decision_found = data['skill_proposal'].get('skill', 'Unknown')
                                else:
                                    decision_found = str(data['skill_proposal'])
                                    
                            decisions[decision_found] = decisions.get(decision_found, 0) + 1
                            
                            # Deep search for "relocate" anywhere in the line
                            if "relocate" in line.lower():
                                relocation_count += 1
                                # print(f"FOUND RELOCATION in {trace_path}")
                                
                        except: pass
            except Exception as e:
                print(f"Error reading {trace_path}: {e}")

    print("\n=== Group B Analysis Result ===")
    print(f"Total Records Scanned: {total_records}")
    print(f"Relocations Found: {relocation_count}")
    print("\nAll Decision Types Found:")
    for d, c in decisions.items():
        print(f"  {d}: {c}")

if __name__ == "__main__":
    find_relocations()
