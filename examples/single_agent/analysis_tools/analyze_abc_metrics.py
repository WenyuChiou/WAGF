
import pandas as pd
import numpy as np
import os
from pathlib import Path
from collections import defaultdict
import re

# Logic:
# RS (Rationality Score): % of actions compliant with governance rules (Standard: 1.0 for B/C, <1.0 for A).
# IF (Internal Fidelity): Correlation between 'Threat' Appraisal and 'Action' Intensity.
#     Action Intensity: 0=None, 1=Insurance, 2=Elevate, 3=Relocate.
#     Threat: Extracted from 'reasoning' or 'state' log (using proxy if numeric not avail).
# IRA (Identity-Rule Alignment): Density of community keywords in reasoning vs total words.

SCRIPT_DIR = Path(__file__).parent
BASE_RESULTS = SCRIPT_DIR.parent / "results" / "JOH_FINAL"
MODELS = ["gemma3_4b", "llama3_2_3b"]
REPORT_DIR = SCRIPT_DIR.parent / "analysis" / "reports"

KEYWORDS_SOCIAL = ["neighbor", "community", "collective", "friend", "local", "town", "we", "us", "our"]
KEYWORDS_SELF = ["i", "my", "me", "assets", "money", "savings", "protect myself"]

def calculate_ira(reasoning):
    text = str(reasoning).lower()
    words = text.split()
    if len(words) == 0: return 0
    count = sum(1 for w in words if any(k in w for k in KEYWORDS_SOCIAL))
    return count / len(words)

def get_threat_score(row):
    # Convert label to numeric
    label = str(row.get('reason_tp_label', '')).lower()
    if 'high' in label or 'critical' in label: return 3
    if 'medium' in label: return 2
    if 'low' in label: return 1
    # Fallback to text parsing if label missing
    text = str(row.get('reason_tp_reason', '')).lower()
    if "high threat" in text: return 3
    if "medium threat" in text: return 2
    return 1

def get_action_intensity_audit(row):
    skill = str(row.get('proposed_skill', '')).lower()
    if 'relocate' in skill: return 3
    if 'elevate' in skill: return 2
    if 'insurance' in skill: return 1
    return 0

def analyze_group(model, group_name):
    # Base directory for the group (e.g. results/.../Group_B)
    group_base = BASE_RESULTS / model / group_name
    if not group_base.exists(): 
        # print(f"Skipping {group_name} (Not found at {group_base})")
        return None

    run_metrics = []
    
    # Recursively find all Run_X folders
    runs = list(group_base.glob("Run_*"))
    # print(f"Found {len(runs)} runs in {model}/{group_name}")

    for run in runs:
        # Find audit file recursively
        audits = list(run.rglob("household_governance_audit.csv"))
        if not audits: 
            print(f"  No audit file in {run}")
            continue
        
        audit_path = audits[0]
        
        try:
            df = pd.read_csv(audit_path)
            
            # --- IF (Internal Fidelity) ---
            # 1. Action Intensity (Proposed)
            df['action_intensity'] = df.apply(get_action_intensity_audit, axis=1)
            # 2. Threat Appraisal
            df['threat_score'] = df.apply(get_threat_score, axis=1)
            
            # Compute Correlation
            if df['threat_score'].std() == 0 or df['action_intensity'].std() == 0:
                fidelity = 0 # No variance
            else:
                fidelity = df['threat_score'].corr(df['action_intensity'])

            # --- IRA (Identity Alignment) ---
            if 'reason_tp_reason' in df.columns:
                df['ira_score'] = df['reason_tp_reason'].apply(calculate_ira)
                ira = df['ira_score'].mean()
            else:
                ira = 0

            # --- RS (Rationality) ---
            total = len(df)
            intercepts = len(df[ (df['validated']==False) | (df['status']!='APPROVED') ])
            rationality = 1.0 - (intercepts / total) if total > 0 else 1.0
            
            run_metrics.append({
                "IF": fidelity,
                "IRA": ira,
                "RS": rationality
            })
            
        except Exception as e:
            print(f"Error in {run}: {e}")

    if not run_metrics: return None
    
    # Average across runs
    avg_if = np.nanmean([m['IF'] for m in run_metrics])
    avg_ira = np.nanmean([m['IRA'] for m in run_metrics])
    avg_rs = np.nanmean([m['RS'] for m in run_metrics])
    
    return {"IF": avg_if, "IRA": avg_ira, "RS": avg_rs}

def main():
    print("running ABC analysis...")
    print(f"{'Model':<12} | {'Group':<8} | {'RS':<6} | {'IF':<6} | {'IRA':<6}")
    print("-" * 50)

    for m in MODELS:
        for g in ["Group_A", "Group_B", "Group_C"]:
            res = analyze_group(m, g)
            if res:
                print(f"{m:<12} | {g:<8} | {res['RS']:.3f}  | {res['IF']:.3f}  | {res['IRA']:.3f}")
            else:
                 print(f"{m:<12} | {g:<8} | N/A     | N/A     | N/A")

if __name__ == "__main__":
    main()
