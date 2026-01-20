import os
import pandas as pd
import json
import glob
from scipy.stats import spearmanr
import numpy as np
from pathlib import Path

def calculate_internal_fidelity(base_dir):
    """
    Calculates Internal Fidelity (IF) - the alignment between 
    Internal Appraisal (Threat Perception) and Action (Adaptation).
    
    Metric: Spearman Rank Correlation (rho)
    Data Source: household_traces.jsonl
    """
    print(f"Analyzing Internal Fidelity in: {base_dir}")
    
    # Robustly find traces file (handle nested "gemma3_4b_disabled" etc)
    # Robustly find traces file
    # Priority 1: Direct path
    traces_path = os.path.join(base_dir, "raw", "household_traces.jsonl")
    print(f"  [Debug] Checking P1: {traces_path} -> {os.path.exists(traces_path)}")
    if not os.path.exists(traces_path):
        traces_path = os.path.join(base_dir, "household_traces.jsonl")
        print(f"  [Debug] Checking P1b: {traces_path} -> {os.path.exists(traces_path)}")
    
    if not os.path.exists(traces_path):
        # Priority 2: Deep search in raw or root with WILDCARD
        print(f"  [Debug] Starting P2 deep search in {base_dir} for *household_traces.jsonl")
        found = list(Path(base_dir).rglob("*household_traces.jsonl"))
        if found:
            traces_path = str(found[0])
            print(f"  [Debug] Found via P2: {traces_path}")
        else:
            # Priority 3: If base_dir is a Group dir, recurse into Run folders
            print(f"  [Debug] Checking P3 runs in {base_dir}")
            run_folders = glob.glob(os.path.join(base_dir, "Run_*"))
            if not run_folders:
                print(f"  [Skip] No traces found in {base_dir} (Checked P1, P2, P3)")
                return None
            else:
                # We do not recurse here for single run analysis, handled by main loop
                print(f"  [Info] Skipping group-level dir, expecting run-level call. Found {len(run_folders)} runs.")
                return None
    
    print(f"Reading traces from: {traces_path}")
    
    data = []
    
    try:
        with open(traces_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    
                    # Extract Skill Proposal (Reasoning)
                    proposal = record.get("skill_proposal", {})
                    reasoning = proposal.get("reasoning", {})
                    
                    # 1. Extract Threat Appraisal (Independent Variable)
                    # Look for THREAT_LABEL, RISK_LABEL, etc.
                    threat_label = reasoning.get("THREAT_LABEL", 
                                  reasoning.get("RISK_LABEL", 
                                  reasoning.get("threat_perception", "LOW")))
                    
                    # Convert semantic label to ordinal rank
                    threat_rank = semantic_to_ordinal(threat_label)
                    
                    # 2. Extract Action (Dependent Variable)
                    skill_name = proposal.get("skill_name", "do_nothing")
                    action_rank = skill_to_ordinal(skill_name)
                    
                    data.append({
                        "agent_id": record.get("agent_id"),
                        "step": record.get("step_id"),
                        "threat_rank": threat_rank,
                        "action_rank": action_rank,
                        "threat_label": threat_label,
                        "skill": skill_name
                    })
                    
                    if len(data) <= 5:
                        print(f"  [Debug Record #{len(data)}]: Threat='{threat_label}'({threat_rank}) -> Action='{skill_name}'({action_rank})")
                    
                except json.JSONDecodeError:
                    continue
                    
    except Exception as e:
        print(f"Error reading trace: {e}")
        return

    df = pd.DataFrame(data)
    if df.empty:
        print("No valid data points found.")
        return

    print(f"Extracted {len(df)} decision points.")
    
    # Debug: Check variance
    print("Threat Distribution:")
    print(df['threat_label'].value_counts())
    print("Action Distribution:")
    print(df['skill'].value_counts())
    print("Threat Ranks:", df['threat_rank'].unique())
    print("Action Ranks:", df['action_rank'].unique())

    # Save to file for easy inspection (Bypass console truncation)
    try:
        with open("distribution_stats.txt", "w", encoding='utf-8') as f:
            f.write(f"Run: {trace_path}\n")
            f.write("--- Threat Distribution ---\n")
            f.write(str(df['threat_label'].value_counts()))
            f.write("\n\n--- Action Distribution ---\n")
            f.write(str(df['skill'].value_counts()))
            f.write("\n\n--- Unique Ranks ---\n")
            f.write(f"Threat: {df['threat_rank'].unique()}\n")
            f.write(f"Action: {df['action_rank'].unique()}\n")
            f.write("\n\n--- Extracted Records ---\n")
            f.write(str(df.head(10)))
    except Exception as e:
        print(f"Failed to write stats: {e}")
    
    # Calculate Spearman Correlation
    # We remove 'do_nothing' noise if needed, or keep it as rank 0
    
    if len(df['threat_rank'].unique()) < 2 or len(df['action_rank'].unique()) < 2:
        print("WARNING: Zero variance in Threat or Action. Correlation is undefined (NaN).")
        rho, p_val = 0.0, 1.0 # technically undefined, but 0 indicates no correlation
    else:
        rho, p_val = spearmanr(df["threat_rank"], df["action_rank"])
    
    print(f"\n--- Internal Fidelity (IF) Results ---")
    print(f"Spearman Rho: {rho:.4f}")
    print(f"P-Value: {p_val:.4e}")
    
    with open("fidelity_result.txt", "w", encoding="utf-8") as f:
        f.write(f"Spearman Rho: {rho:.4f}\n")
        f.write(f"P-Value: {p_val:.4e}\n")
    
    if rho > 0.6:
        print("VERDICT: HIGH Fidelity (Reasoning drives Action)")
    elif rho < 0.3:
        print("VERDICT: LOW Fidelity (Hallucination/Disconnect)")
    else:
        print("VERDICT: Moderate Fidelity")

    return {
        "rho": rho,
        "p_value": p_val,
        "n": len(df)
    }

def semantic_to_ordinal(label):
    """Maps VL/L/M/H/VH to 0-4."""
    if not isinstance(label, str): return 0
    label = label.upper().strip().replace("_", "")
    
    mapping = {
        "VL": 0, "VERYLOW": 0, "NONE": 0,
        "L": 1, "LOW": 1,
        "M": 2, "MEDIUM": 2, "MODERATE": 2, "MOD": 2,
        "H": 3, "HIGH": 3,
        "VH": 4, "VERYHIGH": 4, "SEVERE": 4, "EXTREME": 4
    }
    
    # Partial match fallback
    if "VERY HIGH" in label: return 4
    if "HIGH" in label: return 3
    if "MEDIUM" in label: return 2
    if "LOW" in label: return 1
    
    return mapping.get(label, 0) # Default to 0 (Low/None)

def skill_to_ordinal(skill):
    """Maps actions to 'Adaptation Intensity' (0-2)."""
    skill = skill.lower()
    
    if "relocate" in skill: return 3     # Extreme
    if "elevate" in skill: return 2      # Major
    if "insurance" in skill: return 1    # Minor
    if "do_nothing" in skill: return 0   # None
    if "wait" in skill: return 0
    
    return 0

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default="results/JOH_FINAL", help="Path to JOH_FINAL results")
    args = parser.parse_args()

    models = ["gemma3_4b", "llama3_2_3b"]
    groups = ["Group_A", "Group_B", "Group_C"]
    
    all_scores = []
    metrics_dir = os.path.join(args.base_dir, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)

    print(f"Aggregating Internal Fidelity metrics into: {metrics_dir}")

    for model in models:
        for group in groups:
            path = os.path.join(args.base_dir, model, group)
            if not os.path.exists(path):
                print(f"Skipping {model} {group}: Path not found.")
                continue
            
            run_folders = glob.glob(os.path.join(path, "Run_*"))
            print(f"Found {len(run_folders)} runs for {model} {group}")
            
            for run_path in run_folders:
                run_id = os.path.basename(run_path)
                result = calculate_internal_fidelity(run_path)
                if result:
                    all_scores.append({
                        "Model": model,
                        "Group": group,
                        "Run": run_id,
                        "Internal_Fidelity": result['rho'],
                        "P_Value": result['p_value'],
                        "Sample_Size": result['n']
                    })

    if all_scores:
        df = pd.DataFrame(all_scores)
        out_path = os.path.join(metrics_dir, "internal_fidelity_raw_scores.csv")
        df.to_csv(out_path, index=False)
        print(f"\nSaved consolidated IF scores to: {out_path}")
        
        # Summary
        summary = df.groupby(['Model', 'Group'])['Internal_Fidelity'].agg(['mean', 'std', 'count']).reset_index()
        summary_path = os.path.join(metrics_dir, "internal_fidelity_summary.csv")
        summary.to_csv(summary_path, index=False)
        print(f"Saved summary to: {summary_path}")
        print(summary)
    else:
        print("No data found to analyze. Ensure simulation runs are complete and trace files exist.")
