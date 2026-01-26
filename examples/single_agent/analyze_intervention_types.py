import pandas as pd
import os

BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\deepseek_r1_1_5b"

def analyze_intervention_types(group_name):
    # Try disabled/strict paths
    paths = [
        os.path.join(BASE_DIR, group_name, "Run_1", "deepseek_r1_1_5b_disabled", "household_governance_audit.csv"),
        os.path.join(BASE_DIR, group_name, "Run_1", "deepseek_r1_1_5b_strict", "household_governance_audit.csv")
    ]
    
    audit_path = next((p for p in paths if os.path.exists(p)), None)
    if not audit_path:
        print(f"Audit log looking missing for {group_name}")
        return

    print(f"\n--- Analyzing Interventions for {group_name} ---")
    df = pd.read_csv(audit_path)
    
    # Filter for Retries
    retries = df[df['retry_count'] > 0]
    total_steps = len(df)
    total_retries = len(retries)
    
    if total_retries == 0:
        print("No retries found.")
        return

    # Classify Retries
    # Columns to check: 'error_messages', 'failed_rules', 'parsing_warnings'
    # Assuming 'error_messages' contains the feedback sent to LLM
    
    syntax_count = 0
    governance_count = 0
    
    governance_examples = []
    
    for _, row in retries.iterrows():
        errors = str(row.get('error_messages', '')).lower()
        rules = str(row.get('failed_rules', '')).lower()
        
        # Heuristic for Syntax
        is_syntax = 'json' in errors or 'parse' in errors or 'format' in errors or 'schema' in errors
        
        # Heuristic for Governance
        # Often governance errors come from failed_rules or specific rule names
        # Or explicit text "Rule violation"
        is_gov = (rules and rules not in ['nan','']) or 'violation' in errors or 'threat' in errors or 'coping' in errors
        
        if is_gov:
            governance_count += 1
            if len(governance_examples) < 3:
                governance_examples.append(f"Agent {row['agent_id']}: {rules} | Err: {errors[:50]}...")
        elif is_syntax:
            syntax_count += 1
        else:
            # Fallback - assume governance if not explicit syntax? Or mixed?
            # Let's count as Unclassified or Governance? 
            # Usually safe to assume if not Syntax, it's semantic/governance.
            governance_count += 1 
            
    print(f"Total Decisions: {total_steps}")
    print(f"Total Retries: {total_retries}")
    print(f"  - Syntax/Parse Errors: {syntax_count} ({syntax_count/total_retries*100:.1f}%)")
    print(f"  - Governance Interventions: {governance_count} ({governance_count/total_retries*100:.1f}%)")
    print(f"True Intervention Rate: {governance_count/total_steps*100:.2f}%")
    
    if governance_examples:
        print("Examples of Governance Interventions:")
        for ex in governance_examples:
            print(f"  - {ex}")

# Analyze both
analyze_intervention_types("Group_C")
analyze_intervention_types("Group_B")
