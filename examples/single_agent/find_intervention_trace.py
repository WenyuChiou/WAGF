import pandas as pd
import os

AUDIT_PATH = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\deepseek_r1_1_5b\Group_C\Run_1\deepseek_r1_1_5b_disabled\household_governance_audit.csv"
OUTPUT_FILE = r"c:\Users\wenyu\.gemini\antigravity\brain\174a04b7-b8fb-48c1-b3d5-8f321c21ab80\intervention_traces.txt"

def scan_interventions():
    # Only scan specifically for failed_rules here to answer user query
    path = AUDIT_PATH 
    print(f"Reading audit log from {path}...")
    try:
        df = pd.read_csv(AUDIT_PATH)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Check columns
    print("Columns:", df.columns.tolist())
    
    # We want to find cases where the decision was MODIFIED or BLOCKED.
    # Usually this is indicated by 'outcome' or 'status' or 'modified' column.
    # Or if 'decision' != 'original_decision' (if recorded).
    # Let's verify columns first, but generally look for non-'Approved'.
    
    candidates = []
    
    # Assuming 'assessment' or 'outcome' column holds the status
    # If not sure, we print unique values of likely status columns
    
    target_cols = ['proposed_skill', 'final_skill', 'status', 'failed_rules', 'reason_reasoning']
    print(f"Checking columns: {target_cols}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("Intervention Trace Log (Failed Rules Search)\n\n")
        
        candidates = []
        for _, row in df.iterrows():
            prop = str(row.get('proposed_skill', '')).lower()
            failed_rules = str(row.get('failed_rules', ''))
            
            # Check if failed_rules is not empty/nan
            has_failure = failed_rules and failed_rules.lower() not in ['nan', 'none', '', '[]']
            
            if has_failure:
                candidates.append(row)
                
                f.write(f"[Agent {row.get('agent_id')}, Year {row.get('year')}]\n")
                f.write(f"  Proposed: {row.get('proposed_skill')}\n")
                f.write(f"  Final:    {row.get('final_skill')}\n")
                f.write(f"  Failed Rules: {row.get('failed_rules')}\n")
                f.write(f"  Reasoning: {row.get('reason_reasoning')}\n")
                f.write("-" * 40 + "\n")
                
                if len(candidates) >= 5: break
        
        if not candidates:
            f.write("No Failed Rules found.\n")

    print(f"Found {len(candidates)} candidates. Written to {OUTPUT_FILE}")


scan_interventions()
