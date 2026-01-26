import pandas as pd
import os

BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\deepseek_r1_1_5b"

def inspect_irrationality(group_name):
    path = os.path.join(BASE_DIR, group_name, "Run_1", "simulation_log.csv")
    output_file = r"c:\Users\wenyu\.gemini\antigravity\brain\174a04b7-b8fb-48c1-b3d5-8f321c21ab80\irrational_traces.txt"
    
    if not os.path.exists(path):
        print(f"File not found: {path} for {group_name}")
        return

    print(f"Scanning {group_name}...")
    df = pd.read_csv(path)
    
    # Standardize decision column
    if 'yearly_decision' not in df.columns and 'decision' in df.columns:
        df['yearly_decision'] = df['decision']
    elif 'raw_llm_decision' in df.columns:
         df['yearly_decision'] = df['raw_llm_decision'] # Fallback
    
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(f"\n--- Scanning {group_name} ---\n")
        
        candidates = []
        for _, row in df.iterrows():
            decision = str(row.get('yearly_decision', '')).lower()
            threat = str(row.get('threat_appraisal', '')).lower()
            
            if 'relocate' in decision:
                # Broader search: Low Threat OR context memory implies safety
                is_low_code = any(x in threat for x in ['low', 'minimal', 'unlikely', 'no immediate', 'moderate risk but uncertain'])
                is_low_mem = any(x in str(row.get('memory', '')).lower() for x in ['no flood occurred', 'minimal damage'])
                
                if is_low_code or is_low_mem:
                    candidates.append(row)
                    if len(candidates) >= 3: break 
                    
        if not candidates:
            f.write("No 'Low Threat + Relocate' found.\n")
        else:
            for i, row in enumerate(candidates):
                f.write(f"\n[Example {i+1}] Agent: {row['agent_id']} (Year {row['year']})\n")
                f.write(f"  Decision: {row.get('yearly_decision')}\n")
                f.write(f"  Threat Appraisal: {row.get('threat_appraisal')}\n")
                f.write(f"  Coping Appraisal: {row.get('coping_appraisal')}\n")
                f.write(f"  Memory Snippet: {str(row.get('memory'))[:300]}...\n")
                f.write("-" * 40 + "\n")
    
    print(f"Results written to {output_file}")

def analyze_governance_guidance(group_name):
    """
    Count explicit attempts by Governance to 'Guide' agents (via Retry).
    A Retry > 0 means the Agent proposed something invalid (e.g., Panic) 
    and was guided to a valid solution.
    """
    if "Group_C" not in group_name:
        return # Only Group C (and maybe B) has governance
        
    audit_path = os.path.join(BASE_DIR, group_name, "Run_1", "deepseek_r1_1_5b_disabled", "household_governance_audit.csv")
    
    # Try alternate path for Group B Strict if needed
    if not os.path.exists(audit_path):
        audit_path = os.path.join(BASE_DIR, group_name, "Run_1", "deepseek_r1_1_5b_strict", "household_governance_audit.csv")
    
    if not os.path.exists(audit_path):
        print(f"Audit log missing for {group_name}")
        return

    df = pd.read_csv(audit_path)
    
    # 1. Successful Guidance (Retry > 0 AND Final Status = Approved/RetrySuccess)
    # We treat 'retry_count' column as the indicator.
    guided_cases = df[df['retry_count'] > 0]
    total_steps = len(df)
    
    print(f"\n--- Governance Guidance Stats ({group_name}) ---")
    print(f"Total Decisions: {total_steps}")
    print(f"Interventions (Retries): {len(guided_cases)}")
    print(f"Intervention Rate: {len(guided_cases)/total_steps*100:.1f}%")
    
    # Breakdown of what was guided from -> to
    if not guided_cases.empty:
        print("\nTop 5 Guided Cases (Self-Corrections):")
        # Try to infer 'From' from failed_rules or reasoning if proposed/final match (sometimes they match after correction)
        # But wait, audit log 'proposed_skill' might be the FINAL proposal after retry?
        # Let's check 'failed_rules'
        
        for i, row in guided_cases.head(5).iterrows():
            print(f"  Agent {row['agent_id']} (Retry {row['retry_count']}): Failed rules '{row.get('failed_rules')}' -> Final '{row['final_skill']}'")

# Clean and Run
output_file_main = r"c:\Users\wenyu\.gemini\antigravity\brain\174a04b7-b8fb-48c1-b3d5-8f321c21ab80\irrational_traces.txt"
with open(output_file_main, 'w', encoding='utf-8') as f:
    f.write("Irrational Trace Log\n")

print("Starting scan...")
inspect_irrationality("Group_A")
inspect_irrationality("Group_C")
print("Done.")

# Add to main execution
analyze_governance_guidance("Group_C")
analyze_governance_guidance("Group_B")
