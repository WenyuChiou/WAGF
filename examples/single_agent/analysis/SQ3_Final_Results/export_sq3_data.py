import json
import re
import os
import pandas as pd
from pathlib import Path

# Config
ROOT_DIR = "examples/single_agent/results/JOH_FINAL"
MODELS = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]

def normalize_decision(d):
    d = str(d).lower()
    if 'relocate' in d: return 'Relocate'
    if 'elevat' in d or 'he' in d: return 'Elevation'
    if 'insur' in d or 'fi' in d: return 'Insurance'
    if 'dn' in d or 'nothing' in d: return 'DoNothing'
    return 'Other'

def analyze_model_group(model, group):
    path = Path(ROOT_DIR) / model / group / "Run_1"
    jsonl_files = list(path.glob("**/household_traces.jsonl"))
    
    if not jsonl_files:
        return None

    target_file = max(jsonl_files, key=lambda p: p.stat().st_size)
    
    stats = {
        "Total_Steps": 0,
        "Parse_Errors": 0,
        "Intervention_Count": 0,
        "Abnormal_Appraisal": 0,
        "Flip_Flops": 0,
        "Active_Years": 0
    }
    
    agent_history = {} # AgentID -> Year -> Action

    with open(target_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                stats["Total_Steps"] += 1
                
                # 1. Parse Errors
                warnings = str(data.get('parsing_warnings', '') or '').lower()
                errors = str(data.get('error_messages', '') or '').lower()
                
                # Explicit Warnings
                is_explicit_fail = 'json' in warnings or 'parse' in warnings or 'format' in warnings
                
                # Silent Failures (Empty Output)
                skill_prop = data.get('skill_proposal')
                is_silent_fail = (skill_prop is None) or (isinstance(skill_prop, dict) and not skill_prop)
                
                if is_explicit_fail or is_silent_fail:
                    stats["Parse_Errors"] += 1
                
                # 2. Intervention (Robust from Master Report)
                retry_active = data.get('retry_count', 0) > 0
                failed_rules_raw = data.get('failed_rules', [])
                failed_rules_str = str(failed_rules_raw).lower()
                has_rules = failed_rules_raw and failed_rules_str not in ['nan', 'none', '', '[]']
                
                if retry_active or has_rules:
                    # Heuristic: exclude pure syntax re-tries unless rules failed
                    is_syntax = ('json' in warnings or 'parse' in warnings) and not has_rules
                    if not is_syntax:
                        stats["Intervention_Count"] += 1

                # 3. Abnormal Format
                reasoning = data.get('skill_proposal', {}).get('reasoning', {})
                ta = reasoning.get('TP_LABEL') or reasoning.get('threat_appraisal', {}).get('label')
                if ta:
                    ta_clean = str(ta).upper().strip()
                    if ta_clean not in {"VL", "L", "M", "H", "VH"}:
                        stats["Abnormal_Appraisal"] += 1

                # 4. History for Flip-Flop
                aid = data.get('agent_id')
                year = data.get('year')
                # If Year missing, estimate
                if year is None:
                     # Year 1=Steps 1-100, etc. (Approx)
                     # But aid is reliable.
                     pass 
                
                dec = data.get('skill_proposal', {}).get('skill_name', '')
                if aid is not None and year is not None:
                     if aid not in agent_history: agent_history[aid] = {}
                     agent_history[aid][year] = normalize_decision(dec)

            except: continue

    # Calculate Flip-Flop
    # Compare Year N vs N-1 for each agent
    for aid, history in agent_history.items():
        years = sorted(history.keys())
        for y in years:
            if y == 1: continue
            if (y-1) in history:
                prev = history[y-1]
                curr = history[y]
                # Filter out Relocaters (they leave)
                if prev == 'Relocate': continue 
                
                stats["Active_Years"] += 1 # Valid interval
                if prev != curr:
                    stats["Flip_Flops"] += 1

    return stats

# Main Execution
all_rows = []
print(f"\n{'Model':<20} {'Group':<8} {'Intv%':<8} {'Parse%':<8} {'Abnormal%':<10} {'FF%':<8}")
print("-" * 80)

for m in MODELS:
    for g in GROUPS:
        s = analyze_model_group(m, g)
        if s:
            n = s["Total_Steps"]
            if n == 0: continue
            
            intv_rate = (s["Intervention_Count"] / n) * 100
            parse_rate = (s["Parse_Errors"] / n) * 100
            abn_rate = (s["Abnormal_Appraisal"] / n) * 100
            
            ff_n = s["Active_Years"]
            ff_rate = (s["Flip_Flops"] / ff_n * 100) if ff_n > 0 else 0.0
            
            print(f"{m:<20} {g:<8} {intv_rate:6.1f}% {parse_rate:6.1f}% {abn_rate:8.1f}% {ff_rate:6.1f}%")
            
            all_rows.append({
                "Model": m,
                "Group": g,
                "Total_Steps": n,
                "Intervention_Rate": intv_rate,
                "Parse_Error_Rate": parse_rate,
                "Abnormal_Format_Rate": abn_rate,
                "Flip_Flop_Rate": ff_rate,
                "Raw_Intervention_Count": s["Intervention_Count"],
                "Raw_Parse_Errors": s["Parse_Errors"],
                "Raw_Abnormal_Count": s["Abnormal_Appraisal"],
                "Raw_Flip_Flops": s["Flip_Flops"],
                "Active_Agent_Years": ff_n
            })

# Save to Excel
if all_rows:
    df = pd.DataFrame(all_rows)
    out_dir = Path("examples/single_agent/analysis/SQ3_Final_Results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sq3_metrics_reliability.xlsx"
    df.to_excel(out_path, index=False)
    print(f"\n[System] Exported full SQ3 analysis to: {out_path}")
