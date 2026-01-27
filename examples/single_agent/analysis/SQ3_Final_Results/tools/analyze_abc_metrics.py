
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
# tools -> SQ3 -> analysis -> single_agent -> results
BASE_RESULTS = SCRIPT_DIR.parent.parent.parent / "results" / "JOH_FINAL"
MODELS = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b", "gemma3_4b", "llama3_2_3b"]
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
            
            # --- PARSE & COMPLIANCE METRICS (Efficiency) ---
            # Source of Truth: household_traces.jsonl (Raw Model Output)
            jsonl_path = run / "raw" / "household_traces.jsonl"
            
            n_strict_fail = 0  # Markdown, comments, dirty JSON
            n_fatal_fail = 0   # Unparseable or Schema Violation (Dropped)
            n_traces = 0
            
            if jsonl_path.exists():
                with open(jsonl_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        n_traces += 1
                        try:
                            record = json.loads(line)
                            raw_val = record.get('raw_output')
                            
                            # 1. Check Strict JSON Syntax
                            clean_json = None
                            try:
                                if isinstance(raw_val, dict):
                                    clean_json = raw_val
                                else:
                                    raw_str = str(raw_val).strip()
                                    clean_json = json.loads(raw_str)
                            except:
                                n_strict_fail += 1
                                # If strict fail, try to recover (simulate engine)
                                try:
                                    # Strip markdown
                                    raw_str = str(raw_val).strip()
                                    if "```" in raw_str:
                                        # Simple extraction logic
                                        match = re.search(r"```(?:json)?(.*?)```", raw_str, re.DOTALL)
                                        if match:
                                            clean_json = json.loads(match.group(1).strip())
                                        else:
                                            n_fatal_fail += 1
                                            continue
                                    else:
                                        n_fatal_fail += 1
                                        continue
                                except:
                                    n_fatal_fail += 1
                                    continue
                                    
                            # 2. Check Schema (If we have potential JSON)
                            if clean_json:
                                req_keys = ["threat_appraisal", "coping_appraisal", "skill_proposal"]
                                if not all(k in clean_json for k in req_keys):
                                    n_fatal_fail += 1
                                    
                        except:
                            pass # Line read error
            
            # Fallback if no traces
            if n_traces == 0:
                parse_rate_strict = 0
                parse_rate_fatal = 0
            else:
                parse_rate_strict = n_strict_fail / n_traces
                parse_rate_fatal = n_fatal_fail / n_traces

            run_metrics[-1]["PF_Strict"] = parse_rate_strict
            run_metrics[-1]["PF_Fatal"] = parse_rate_fatal
            run_metrics[-1]["PF"] = parse_rate_fatal # Default to Fatal for main table
            
            # --- FF (Flip-Flop / Instability) ---
            # Track agent proposals over time. 
            df_sorted = df.sort_values(['agent_id', 'year'])
            ff_count = 0
            total_transitions = 0
            
            for ag_id, group_df in df_sorted.groupby('agent_id'):
                seq = group_df['action_intensity'].tolist()
                if len(seq) < 2: continue
                
                # Count reversals
                diffs = [seq[i] - seq[i-1] for i in range(1, len(seq)) if seq[i] != seq[i-1]]
                total_transitions += (len(seq) - 1)
                
                # If signs flip (e.g. +1 then -1), that's a flip-flop
                for k in range(1, len(diffs)):
                    if (diffs[k] > 0 and diffs[k-1] < 0) or (diffs[k] < 0 and diffs[k-1] > 0):
                        ff_count += 1
                        
            ff_rate = ff_count / total_transitions if total_transitions > 0 else 0

            run_metrics[-1]["PF"] = parse_rate
            run_metrics[-1]["FF"] = ff_rate

            
        except Exception as e:
            print(f"Error in {run}: {e}")

    if not run_metrics: return None
    
    # Average across runs
    avg_if = np.nanmean([m['IF'] for m in run_metrics])
    avg_ira = np.nanmean([m['IRA'] for m in run_metrics])
    avg_rs = np.nanmean([m['RS'] for m in run_metrics])
    avg_pf = np.nanmean([m.get('PF', 0) for m in run_metrics])
    avg_ff = np.nanmean([m.get('FF', 0) for m in run_metrics])
    
    return {"IF": avg_if, "IRA": avg_ira, "RS": avg_rs, "PF": avg_pf, "FF": avg_ff}

def main():
    print("running ABC analysis (SQ3 Efficiency)...")
    print(f"{'Model':<16} | {'Group':<8} | {'RS (Comp)':<10} | {'PF_Fatal':<10} | {'PF_Strict':<10} | {'FF':<8} | {'IF':<8}")
    print("-" * 90)

    rows = []

    for m in MODELS:
        for g in ["Group_A", "Group_B", "Group_C"]:
            res = analyze_group(m, g)
            if res:
                pf_fatal = res.get('PF_Fatal', 0)
                pf_strict = res.get('PF_Strict', 0)
                ff = res.get('FF', 0)
                print(f"{m:<16} | {g:<8} | {res['RS']:.1%}      | {pf_fatal:.1%}      | {pf_strict:.1%}      | {ff:.1%}    | {res['IF']:.3f}")
                
                # Add to rows for CSV
                row = {
                    "Model": m,
                    "Group": g,
                    "RS_Compliance": round(res['RS'], 4),
                    "PF_Fatal_Waste": round(pf_fatal, 4),
                    "PF_Strict_Dirty": round(pf_strict, 4),
                    "FF_Instability": round(ff, 4),
                    "IF_Alignment": round(res['IF'], 4)
                }
                rows.append(row)
            else:
                pass # Silent skip for cleaner output if missing

    if rows:
        df = pd.DataFrame(rows)
        # Determine output path (in SQ3_Final_Results)
        out_csv = Path(__file__).parent.parent / "sq3_efficiency_metrics.csv"
        df.to_csv(out_csv, index=False)
        print(f"\nSaved metrics to: {out_csv}")
    else:
        print("\nNo data found to save.")

if __name__ == "__main__":
    main()
