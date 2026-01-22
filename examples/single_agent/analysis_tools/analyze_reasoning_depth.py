
import pandas as pd
import numpy as np
import os
from pathlib import Path

# Goal: Deep qualitative analysis of Reasoning and Rule Violations (even if rare)
# 1. Check Retry Counts (did they fail initially?)
# 2. Extract Reasoning Samples for "Do Nothing" vs "Action"
# 3. Analyze specific Rule Violations if any exist.

SCRIPT_DIR = Path(__file__).parent
BASE_RESULTS = SCRIPT_DIR.parent / "results" / "JOH_FINAL"

MODELS = ["gemma3_4b", "llama3_2_3b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]

def detect_mismatch(row):
    # Thinking-Doing Gap: Talks about action, does nothing.
    reason = str(row.get('reason_tp_reason', '')).lower()
    action = str(row.get('proposed_skill', '')).lower()
    
    # Flags
    intent_insurance = "buy insurance" in reason or "purchase insurance" in reason
    intent_relocate = "relocate" in reason or "move out" in reason
    
    if action == "do_nothing":
        if intent_insurance: return "Mismatch: Wanted Insurance -> Did Nothing"
        if intent_relocate: return "Mismatch: Wanted Relocate -> Did Nothing"
    return None

def analyze_reasoning(model_name, group_name):
    group_path = BASE_RESULTS / model_name / group_name
    if not group_path.exists(): 
        # print(f"Skipping {model_name}/{group_name} (Not found)")
        return None

    # print(f"\n--- Analyzing {model_name} / {group_name} ---")
    
    runs = list(group_path.glob("Run_*"))
    
    all_retries = []
    all_violations = []
    reasoning_samples = {"do_nothing": [], "action": []}
    
    for run in runs:
        audits = list(run.rglob("household_governance_audit.csv"))
        if not audits: continue
        
        try:
            df = pd.read_csv(audits[0])
            
            # 1. Analysis of Retries (The "Near Misses")
            if 'retry_count' in df.columns:
                retries = df[df['retry_count'] > 0]
                all_retries.extend(retries.to_dict('records'))
                
            # 2. Analysis of Violations (The "Hard Failures")
            # If validated=False, what rule broke?
            if 'violation_rule' in df.columns:
                violations = df[df['validated'] == False]
                all_violations.extend(violations['violation_rule'].dropna().tolist())
                
            # 3. Reasoning Sampling & Mismatch Detection
            if 'reason_tp_reason' in df.columns:
                
                # Check for Silent Failures (Mismatches)
                df['mismatch'] = df.apply(detect_mismatch, axis=1)
                mismatches = df[df['mismatch'].notna()]
                for _, r in mismatches.iterrows():
                    # Format: [Agent] Type: Reason
                    reasoning_samples["do_nothing"].append(f"!! {r['mismatch']} !! :: {r['reason_tp_reason']}")

                # Sample Do Nothing (Standard)
                # Sample Do Nothing
                # Note: 'proposed_skill' might also be different column name? 
                # Let's assume proposed_skill is correct as per standard logic.
                
                dn = df[df['proposed_skill'] == 'do_nothing'].sample(n=min(2, len(df[df['proposed_skill'] == 'do_nothing'])))
                for _, r in dn.iterrows():
                    reasoning_samples["do_nothing"].append(f"[{r['agent_id']}] {r['reason_tp_reason']}")
                    
                # Sample Actions (Elevate/Relocate/Buy)
                act = df[df['proposed_skill'].isin(['elevate_house', 'relocate', 'buy_insurance'])].sample(n=min(2, len(df[df['proposed_skill'] != 'do_nothing'])))
                for _, r in act.iterrows():
                    reasoning_samples["action"].append(f"[{r['agent_id']}] ({r['proposed_skill']}) {r['reason_tp_reason']}")

        except Exception as e:
            pass

    # Report results
    print(f"Total Steps Analyzed: {len(runs) * 1000} (approx)")
    print(f"Total Retries (Self-Corrections): {len(all_retries)}")
    print(f"Total Final Violations (Interceptions): {len(all_violations)}")
    
    if all_violations:
        print("\nTop Violation Types:")
        print(pd.Series(all_violations).value_counts().head())

    print("\n--- Reasoning Samples (Why did they act?) ---")
    print("category: DO NOTHING")
    for s in reasoning_samples["do_nothing"][:3]:
        print(f"  > {s[:200]}...") # Truncate for readability
        
    print("\ncategory: ACTION TAKEN")
    if not reasoning_samples["action"]:
        print("  (No actions found)")
    else:
        for s in reasoning_samples["action"][:3]:
            print(f"  > {s[:200]}...")

def main():
    print(f"{'Model':<12} | {'Group':<8} | {'Runs':<4} | {'Retries':<8} | {'Mismatches':<10} | {'Compliance Rate'}")
    print("-" * 75)
    
    for m in MODELS:
        for g in GROUPS:
            res = analyze_reasoning(m, g)
            # We need to return stats from the function to print a table row
            # Modifying function to return dict instead of just printing
            
            # (Note: Since I cannot easily rewrite the whole function body in one go block safely without context drift, 
            # I will just rely on the existing print statements formatted as a row inside the loop if I modify the function below, 
            # or better: I will rewrite the function signature above and let the logic flow, but I need to capture the data.)
            
            # Actually, let's just use the print output for now but make it cleaner.
            pass

    # Re-implementing a cleaner structure:
    results = []
    
    for m in MODELS:
        for g in GROUPS:
            path = BASE_RESULTS / m / g
            if not path.exists(): continue
            
            runs = list(path.glob("Run_*"))
            retries = 0
            mismatches = 0
            total_audits = 0
            
            for run in runs:
                audits = list(run.rglob("household_governance_audit.csv"))
                if not audits: continue
                try:
                    df = pd.read_csv(audits[0])
                    total_audits += len(df)
                    if 'retry_count' in df.columns:
                        retries += df['retry_count'].sum()
                    if 'reason_tp_reason' in df.columns and 'proposed_skill' in df.columns:
                        mismatches += df.apply(lambda r: 1 if detect_mismatch(r) else 0, axis=1).sum()
                except: pass
            
            results.append({
                "Model": m,
                "Group": g,
                "Runs": len(runs),
                "Retries": retries,
                "Mismatches": mismatches,
                "TotalSteps": total_audits
            })

    # Print Table
    print(f"{'Model':<15} | {'Group':<10} | {'Runs':<5} | {'Retries':<8} | {'Mismatches':<10} | {'Gap Rate %':<10}")
    print("-" * 80)
    for r in results:
        gap_rate = (r['Mismatches'] / r['TotalSteps']) * 100 if r['TotalSteps'] > 0 else 0
        print(f"{r['Model']:<15} | {r['Group']:<10} | {r['Runs']:<5} | {r['Retries']:<8} | {r['Mismatches']:<10} | {gap_rate:.2f}%")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
