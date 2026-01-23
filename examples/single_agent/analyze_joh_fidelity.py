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
    
    traces_path = os.path.join(base_dir, "raw", "household_traces.jsonl")
    if not os.path.exists(traces_path):
        traces_path = os.path.join(base_dir, "household_traces.jsonl")
    
    if not os.path.exists(traces_path):
        found = list(Path(base_dir).rglob("*household_traces.jsonl"))
        if found:
            traces_path = str(found[0])
        else:
            print(f"  [Skip] No traces found in {base_dir}")
            return None
    
    print(f"Reading traces from: {traces_path}")
    
    data = []
    
    try:
        with open(traces_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    
                    proposal = record.get("skill_proposal", {})
                    reasoning = proposal.get("reasoning", {})
                    
                    # 1. Extract Threat Appraisal (Independent Variable)
                    # Support multiple key formats used by different models
                    threat_label = reasoning.get("TP_LABEL", 
                                  reasoning.get("THREAT_LABEL", 
                                  reasoning.get("RISK_LABEL", 
                                  reasoning.get("threat_perception", "LOW"))))
                    
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
    
    if len(df['threat_rank'].unique()) < 2 or len(df['action_rank'].unique()) < 2:
        print("WARNING: Zero variance in Threat or Action. Correlation is undefined (NaN).")
        rho, p_val = 0.0, 1.0
    else:
        rho, p_val = spearmanr(df["threat_rank"], df["action_rank"])
    
    print(f"\n--- Internal Fidelity (IF) Results ---")
    print(f"Spearman Rho: {rho:.4f}")
    print(f"P-Value: {p_val:.4e}")
    
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
    
    return mapping.get(label, 0)

def skill_to_ordinal(skill):
    """Maps actions to 'Adaptation Intensity' (0-2)."""
    skill = skill.lower()
    
    if "relocate" in skill: return 3
    if "elevate" in skill: return 2
    if "insurance" in skill: return 1
    if "do_nothing" in skill: return 0
    if "wait" in skill: return 0
    return 0

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=r"examples/single_agent/results/JOH_FINAL", help="Path to JOH_FINAL results")
    args = parser.parse_args()

    models = ["deepseek_r1_8b", "deepseek_r1_1_5b"]
    groups = ["Group_A", "Group_B", "Group_C"]
    
    all_scores = []
    
    print(f"Aggregating Internal Fidelity metrics...")

    for model in models:
        for group in groups:
            path = os.path.join(args.base_dir, model, group)
            if not os.path.exists(path): continue
            
            run_folders = glob.glob(os.path.join(path, "Run_*"))
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
        print("\n=== SUMMARY TABLE ===")
        print(df)
