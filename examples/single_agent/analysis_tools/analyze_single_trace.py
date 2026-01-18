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
    path = r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\llama3_2_3b\Group_C_Full_HumanCentric\llama3_2_3b_strict\raw\household_traces.jsonl"
    analyze_trace(path)
