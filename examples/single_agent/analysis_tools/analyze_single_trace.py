import json
import os
import sys

def analyze_trace(file_path, target_agent="Agent_001"):
    with open(file_path, 'r', encoding='utf-8') as f:
        records = []
        for line in f:
            try:
                data = json.loads(line)
                if data.get("agent_id") == target_agent:
                    records.append(data)
            except: pass
            
    # Key by Year, keep last step_id
    history = {}
    for r in records:
        year = r.get("current_year")
        # Fallback year
        if year is None:
            mem = r.get("memory_pre", [])
            if mem and isinstance(mem, list):
                import re
                match = re.search(r"Year (\d+)", mem[0])
                if match:
                    year = int(match.group(1))
        
        if year is None: continue
        
        step = r.get("step_id", 0)
        
        # Keep if year not seen or step is higher
        if year not in history or step > history[year].get("step_id", 0):
            history[year] = r
            
    # Process sequential state
    print(f"Timeline for {target_agent}")
    print(f"{'Year':<5} | {'Action':<15} | {'Elevated':<8} | {'Relocated':<9} | {'Insurance':<9}")
    print("-" * 60)
    
    # Sort years
    sorted_years = sorted(history.keys())
    
    current_state = {'elevated': False, 'relocated': False, 'has_insurance': False}
    
    for y in sorted_years:
        r = history[y]
        approved = r.get("approved_skill", {})
        decision = approved.get("skill_name", "Unknown")
        
        # Trace State (what the log says)
        changes = r.get("execution_result", {}).get("state_changes", {})
        
        # We need to see if the log reports the accumulating state or just delta
        log_elev = changes.get('elevated', 'N/A')
        log_reloc = changes.get('relocated', 'N/A')
        log_ins = changes.get('has_insurance', 'N/A')
        
        print(f"{y:<5} | {decision:<15} | {str(log_elev):<8} | {str(log_reloc):<9} | {str(log_ins):<9}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze a single agent trace from JSONL.")
    parser.add_argument("--run-dir", type=str, help="Directory containing household_traces.jsonl")
    parser.add_argument("--file", type=str, help="Path to household_traces.jsonl")
    parser.add_argument("--agent", type=str, default="Agent_001", help="Target Agent ID")
    
    args = parser.parse_args()
    
    target_file = None
    if args.file:
        target_file = args.file
    elif args.run_dir:
        target_file = os.path.join(args.run_dir, "household_traces.jsonl")
        
    if target_file and os.path.exists(target_file):
        analyze_trace(target_file, target_agent=args.agent)
    else:
        print(f"Error: Could not find trace file at {target_file}")
        print("Usage: python analyze_single_trace.py --run-dir <path> or --file <path>")

