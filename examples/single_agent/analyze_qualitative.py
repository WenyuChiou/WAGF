import json
from pathlib import Path
import os

def analyze_qualitative(filepath):
    print(f"Analyzing: {filepath}")
    
    total_records = 0
    issues_count = 0
    low_threat_high_action = []
    action_counts = {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                record = json.loads(line)
                total_records += 1
                
                # 1. SRR Analysis (Validation Issues)
                if record.get("validation_issues"):
                    issues_count += 1
                
                # 2. Qualitative Mismatch Extraction
                proposal = record.get("skill_proposal", {})
                reasoning = proposal.get("reasoning", {})
                
                threat_label = reasoning.get("THREAT_LABEL", "UNKNOWN")
                skill_name = proposal.get("skill_name", "do_nothing")
                
                threat_label = reasoning.get("TP_LABEL", reasoning.get("THREAT_LABEL", "UNKNOWN"))
                skill_name = proposal.get("skill_name", "do_nothing")
                
                # Debug specific records
                if skill_name == "buy_insurance" and total_records % 50 == 0:
                     print(f"Debug Candidates: Threat='{threat_label}' (Type: {type(threat_label)}) Action='{skill_name}'")
                
                # Debug counts
                if skill_name not in action_counts: action_counts[skill_name] = 0
                action_counts[skill_name] += 1

                # Mismatch: Low Threat but Action taken (Logic 0 -> Action 1/2/3)
                # Loose matching
                is_low = "LOW" in str(threat_label).upper()
                is_action = str(skill_name).lower().strip() not in ["do_nothing", "wait"]
                
                if is_low and is_action:
                    low_threat_high_action.append({
                        "step": record.get("step_id"),
                        "threat": threat_label,
                        "action": skill_name,
                        "strategy": reasoning.get("strategy", ""),
                        "thought": reasoning.get("thought", ""),
                        "reasoning": reasoning.get("TP_REASON", "")
                    })

            except Exception:
                continue

    # Results
    srr = (issues_count / total_records) * 100 if total_records else 0
    print(f"\n--- Stability Metrics (SRR) ---")
    print(f"Total Records: {total_records}")
    print(f"Validation Issues: {issues_count}")
    print(f"Self-Repair Rate (SRR): {srr:.2f}%")

    print(f"\n--- Qualitative Mismatch Analysis (Threat=LOW, Action!=None) ---")
    print(f"Action Distribution: {json.dumps(action_counts, indent=2)}")
    print(f"Found {len(low_threat_high_action)} mismatches.")
    
    print("\n[Top 3 Examples of Governance Overreach / Sophistry?]")
    for i, ex in enumerate(low_threat_high_action[:3]):
        print(f"\nExample #{i+1} (Step {ex['step']}):")
        print(f"  Threat: {ex['threat']} | Action: {ex['action']}")
        print(f"  Reasoning (Why Low?): {ex['reasoning']}")
        print(f"  Strategy (Why Act?): {ex['strategy'][:200]}...")

if __name__ == "__main__":
    path = r"examples/single_agent/results/JOH_FINAL/deepseek_r1_8b/Group_B/Run_1/deepseek_r1_8b_strict/raw/household_traces.jsonl"
    if os.path.exists(path):
        analyze_qualitative(path)
    else:
        print(f"File not found: {path} (Check path!)")
