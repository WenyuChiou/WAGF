import pandas as pd
import json
import re
import os
import sys
from pathlib import Path

# --- Semantic Analysis Logic ---
# Based on Protection Motivation Theory (PMT)
# Using broad descriptors to capture the 'essence' of high/low constructs in natural language
TA_KEYWORDS = {
    "H": [
        "flood", "storm", "damage", "warning", "danger", "threat", "risky", 
        "exposed", "vulnerable", "imminent", "severe", "property loss", "high risk",
        "critical", "extreme", "destroy", "devastat", "unsafe", "peril", "crisis",
        "emergency", "evacuate", "run", "flee", "disaster", "catastrophe"
    ],
    "L": [
        "minimal", "safe", "none", "low", "unlikely", "no risk", "protected", "secure"
    ]
}

CA_KEYWORDS = {
    "H": [
        "grant", "subsidy", "effective", "capable", "confident", "support", "benefit", 
        "protection", "affordable", "successful", "prepared", "mitigate", "action plan"
    ],
    "L": [
        "expensive", "costly", "unable", "uncertain", "weak", "unaffordable", 
        "insufficient", "debt", "financial burden"
    ]
}

def map_text_to_level(text, keywords=None):
    if not isinstance(text, str): return "M"
    text = text.upper()
    # 1. Primary: Explicit Categorical Codes (Standard in JOH traces)
    if re.search(r'\bVH\b', text): return "VH"
    if re.search(r'\bH\b', text): return "H"
    if re.search(r'\bVL\b', text): return "VL"
    if re.search(r'\bL\b', text): return "L"
    if re.search(r'\bM\b', text): return "M"
    
    # 2. Secondary: Keyword match (For Group A / unstructured responses)
    if keywords:
        if any(w.upper() in text for w in keywords.get("H", [])): return "H"
        if any(w.upper() in text for w in keywords.get("L", [])): return "L"
        
    return "M"

def normalize_decision(d):
    d = str(d).lower()
    if 'relocate' in d: return 'Relocate'
    if 'elevat' in d or 'he' in d: return 'Elevation'
    if 'insur' in d or 'fi' in d: return 'Insurance'
    if 'dn' in d or 'nothing' in d: return 'DoNothing'
    return 'Other'

def get_stats(model, group):
    root = Path("examples/single_agent/results/JOH_FINAL")
    group_dir = root / model / group / "Run_1"
    
    if not group_dir.exists(): return None
    
    # 1. Data Discovery
    csv_candidates = list(group_dir.glob("**/simulation_log.csv"))
    jsonl_candidates = list(group_dir.glob("**/household_traces.jsonl"))
    
    if not csv_candidates: return None
    csv = max(csv_candidates, key=lambda p: p.stat().st_size)
    
    try:
        df = pd.read_csv(csv)
        df.columns = [c.lower() for c in df.columns]
        num_agents = df['agent_id'].nunique()
        
        # 2. High-Fidelity Appraisal Extraction
        appraisals = []
        if jsonl_candidates:
            # Group B/C: Use Traces for all years
            with open(jsonl_candidates[0], 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        step = data.get('step_id', 0)
                        year = data.get('year') or ((step - 1) // num_agents + 1)
                        proposal = data.get('skill_proposal', {})
                        reasoning = proposal.get('reasoning', {})
                        ta = (reasoning.get('TP_LABEL') or 
                              reasoning.get('threat_appraisal', {}).get('label') or
                              reasoning.get('threat_appraisals', {}).get('label'))
                        ca = (reasoning.get('CP_LABEL') or 
                              reasoning.get('coping_appraisal', {}).get('label') or
                              reasoning.get('coping_appraisals', {}).get('label'))
                        
                        if not ta or not ca:
                            raw = data.get('raw_output', '')
                            if isinstance(raw, str):
                                ta_m = re.search(r'"threat_appraisals?":\s*{\s*"label":\s*"([^"]+)"', raw, re.I)
                                ca_m = re.search(r'"coping_appraisals?":\s*{\s*"label":\s*"([^"]+)"', raw, re.I)
                                ta = ta_m.group(1) if ta_m else ta
                                ca = ca_m.group(1) if ca_m else ca
                        
                        if ta or ca:
                            appraisals.append({'agent_id': data.get('agent_id'), 'year': year, 'ta': ta, 'ca': ca})
                    except: continue
        else:
            # Group A: Use Direct Appraisal columns or Reasoning for all years
            reason_col = next((c for c in df.columns if 'reasoning' in c), None)
            cols_to_check = ['threat_appraisal', 'coping_appraisal', reason_col, 'memory']
            
            for idx, row in df.iterrows():
                text_ta = " ".join([str(row.get(c, "")) for c in ['threat_appraisal', reason_col, 'memory'] if c in df.columns])
                text_ca = " ".join([str(row.get(c, "")) for c in ['coping_appraisal', reason_col, 'memory'] if c in df.columns])
                appraisals.append({'agent_id': row['agent_id'], 'year': row['year'], 'ta': text_ta, 'ca': text_ca})

        # 3. Behavioral Stats & Alignment
        dec_col = next((c for c in ['decision', 'yearly_decision'] if c in df.columns), None)
        if dec_col:
            def is_action(d):
                d = str(d).lower()
                return not any(x in d for x in ['do nothing', 'do_nothing', 'nothing', 'no action'])
            
            df['acted'] = df[dec_col].apply(is_action)
            
            if appraisals:
                ap_df = pd.DataFrame(appraisals).drop_duplicates(subset=['agent_id', 'year'])
                full_data = df.merge(ap_df, on=['agent_id', 'year'], how='left')
                full_data['ta_level'] = full_data['ta'].apply(lambda x: map_text_to_level(x, TA_KEYWORDS))
                full_data['ca_level'] = full_data['ca'].apply(lambda x: map_text_to_level(x, CA_KEYWORDS))
            else:
                full_data = df
                full_data['ta_level'] = "M"
                full_data['ca_level'] = "M"

            # FILTER: Exclude agents who have already relocated
            # Because "Do Nothing" after relocation is valid, not irrational
            if 'relocated' in full_data.columns:
                # We want to analyze decisions made while the agent was still present
                # If 'relocated' is boolean True/False, we keep False
                # But typically 'relocated' becomes True AFTER the decision to relocate.
                # So we should be careful. 
                # Better approach: If decision was "relocate", that counts as Action. 
                # If they are ALREADY relocated in previous steps, they shouldn't be in the dataset or should be filtered.
                # Assuming standard log where agents exit or stay 'relocated=True'
                full_data = full_data[full_data['relocated'] != True]

            high_labels = ["H", "VH"]
            hi_ta = full_data['ta_level'].isin(high_labels).mean()
            hi_ca = full_data['ca_level'].isin(high_labels).mean()
            
            ta_align = full_data[full_data['ta_level'].isin(high_labels)]['acted'].mean() if hi_ta > 0 else 0
            ca_align = full_data[full_data['ca_level'].isin(high_labels)]['acted'].mean() if hi_ca > 0 else 0

            # 4. Interventions & Flip-flops
            interv_total = 0
            interv_success = 0
            if jsonl_candidates:
                with open(jsonl_candidates[0], 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            # Robust Intervention Detection
                            retry_active = data.get('retry_count', 0) > 0
                            failed_rules = str(data.get('failed_rules', '')).lower()
                            has_rules = failed_rules and failed_rules not in ['nan', 'none', '', '[]']
                            
                            # Intervention occurred if Retry > 0 OR explicit Rule Failures detected
                            # (We prioritize Failed Rules as the source of truth for Governance)
                            if retry_active or has_rules:
                                parsed_error = str(data.get('parsing_warnings', '') or data.get('error_messages', '')).lower()
                                
                                # Heuristic: It is Governance if Rules Failed OR Error is not purely syntax
                                is_syntax = ('json' in parsed_error or 'parse' in parsed_error) and not has_rules
                                
                                if not is_syntax:
                                    interv_total += 1
                                    final_dec = data.get('skill_proposal', {}).get('skill_name', '')
                                    if is_action(final_dec): interv_success += 1
                        except: continue
            
            intv_ok_str = f"{interv_success}" if interv_total > 0 else "-"
            
            # --- VERIFICATION RULES ANALYSIS ---
            # Rule 1: No Panic Relocation (L/M Threat -> Relocate)
            # Rule 2: No Panic Elevation (L/M Threat -> Elevate)
            # Rule 3: No Complacency (H/VH Threat -> DoNothing)
            
            # V1: Panic Relocation
            # Hybrid Logic v14:
            # - Group A (Keywords): Panic = Not High (L, VL, M) -> Relocate. (Since M is default)
            # - Group B/C (JSON):   Panic = Strict Low (L, VL)  -> Relocate/Elevate.
            
            if group == "Group_A":
                # For Group A, "Medium" usually means "No keyword found". 
                # So if they Relocate without Explicit High Risk ('H', 'VH'), it's Panic.
                # using ~isin(['H', 'VH']) is safer than listing L/VL/M
                panic_states = full_data[~full_data['ta_level'].isin(["H", "VH"])]
            else:
                # For Group B/C, "Medium" is a valid calibrated state allowing Elevation.
                # Panic is strictly L/VL.
                panic_states = full_data[full_data['ta_level'].isin(["L", "VL"])]
            
            v1_count = 0
            v1_rate = 0.0
            v2_count = 0
            v2_rate = 0.0
            
            # Global Frequency Calculation (User Request Step 578)
            # Metric: (Actual V1 + Blocked Attempts) / Total Active Steps
            # We treat Successful Interventions as "Blocked Panic Attempts" (mostly Relocation/Elevation)
            
            # For Group A: Intv=0, so it's just Actual / Total
            # For Group B/C: Actual=0 (usually), so it's Intv / Total
            
            # Calculate actual V1 and V2 counts based on panic_states
            if len(panic_states) > 0:
                v1_count = panic_states[dec_col].apply(lambda x: normalize_decision(x) == 'Relocate').sum()
                v2_count = panic_states[dec_col].apply(lambda x: normalize_decision(x) == 'Elevation').sum()
            
            # V3: Complacency (Under-reaction)
            # Definition: High/Very High Threat -> DoNothing
            high_states = full_data[full_data['ta_level'].isin(["H", "VH"])]
            v3_count = 0
            if len(high_states) > 0:
                v3_count = high_states[dec_col].apply(lambda x: normalize_decision(x) == 'DoNothing').sum()

            total_panic_intent = v1_count + interv_success
            v1_global_rate = total_panic_intent / len(full_data) if len(full_data) > 0 else 0
            
            # V2 (Elevation) is usually allowed, so Intv mostly maps to V1 or drastic V2 blocks.
            # We will report V2 based on Actual / Total for now, as Intv is lump sum.
            v2_global_rate = v2_count / len(full_data) if len(full_data) > 0 else 0
            
            # V3 (Complacency) / Total
            v3_global_rate = v3_count / len(full_data) if len(full_data) > 0 else 0

            # Flip-flops (Weighted Calculation: Total Flips / Total Active Intervals)
            total_flips = 0
            total_active_intervals = 0
            weighted_ff = 0.0
            
            # Robust FF Calculation Logic using Year-over-Year comparison
            try:
                dec_col_ff = next((c for c in df.columns if 'yearly_decision' in c or 'decision' in c or 'skill' in c), None)
                if dec_col_ff:
                    df_sorted = df.sort_values(['agent_id', 'year'])
                    
                    for year in range(1, df['year'].max() + 1):
                        prev = df_sorted[df_sorted['year'] == year-1][['agent_id', dec_col_ff]].set_index('agent_id')
                        curr = df_sorted[df_sorted['year'] == year][['agent_id', dec_col_ff]].set_index('agent_id')
                        
                        if prev.empty: continue
                        
                        # Filter Stayers (Active Population) - Exclude those who relocated
                        stayers = prev[~prev[dec_col_ff].astype(str).str.contains('Relocate', case=False, na=False)].index
                        
                        merged = prev.loc[stayers].join(curr, lsuffix='_prev', rsuffix='_curr').dropna()
                        
                        n_active = len(merged)
                        if n_active > 0:
                            flips = (merged[f'{dec_col_ff}_prev'].apply(normalize_decision) != merged[f'{dec_col_ff}_curr'].apply(normalize_decision)).sum()
                            total_flips += flips
                            total_active_intervals += n_active
                    
                    weighted_ff = (total_flips / total_active_intervals) if total_active_intervals > 0 else 0
            except Exception as e_ff:
                print(f"FF Calc Error: {e_ff}")
                weighted_ff = 0.0
            
            return {
                "N": len(full_data),
                "N_L": len(panic_states),
                "N_H": len(high_states),
                "V1_%": round(v1_global_rate * 100, 1), # Global Panic Intent
                "V1_N": total_panic_intent,             # Count = Actual + Blocked
                "V1_Act": v1_count,                     # Keep Actual for reference
                "V2_%": round(v2_global_rate * 100, 1), 
                "V2_N": v2_count,
                "V3_%": round(v3_global_rate * 100, 1), 
                "V3_N": v3_count,
                "Intv": interv_total,
                "Intv_S": interv_success,
                "FF": round(weighted_ff * 100, 2),
                "Status": "Done" if df['year'].max() >= 10 else f"Y{df['year'].max()}"
            }
        return None
    except Exception as e:
        return {"Status": f"Err: {str(e)[:15]}"}

models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]

print("\n=== JOH SCALING REPORT: VERIFICATION RULES (GLOBAL FREQUENCY - FINAL) ===")
# Headers
h_model = "Model Scale"
h_grp = "Group"
h_n = "Total Steps"
h_v1 = "Panic Relocation Frequency"
h_v2 = "Panic Elevation Frequency"
h_v3 = "Complacency Rate"
h_intv = "Interventions (Success)"
h_ff = "Decision Instability"

print(f"{h_model:<18} {h_grp:<7} {h_n:<12} {h_v1:<30} {h_v2:<28} {h_v3:<20} {h_intv:<25} {h_ff:<20}")
print("-" * 180)

all_data = []

for m in models:
    for g in groups:
        stats = get_stats(m, g)
        if stats:
            # Format values
            v1_str = f"{stats['V1_%']}% (n={stats['V1_N']})"
            v2_str = f"{stats['V2_%']}% (n={stats['V2_N']})"
            v3_str = f"{stats['V3_%']}% (n={stats['V3_N']})"
            intv_str = f"{stats['Intv']} ({stats['Intv_S']})"
            ff_str = f"{stats['FF']}%"
            
            print(f"{m:<18} {g:<7} {stats['N']:<12} {v1_str:<30} {v2_str:<28} {v3_str:<20} {intv_str:<25} {ff_str:<20}")
            
            # Collect for Export
            row = stats.copy()
            row['Model'] = m
            row['Group'] = g
            row['N_Audit'] = stats['N_L']
            # Add full name keys for Excel
            row['Panic Relocation Freq'] = row['V1_%']
            row['Panic Elevation Freq'] = row['V2_%']
            row['Complacency Rate'] = row['V3_%']
            row['Flip-Flop Rate'] = row['FF']
            all_data.append(row)

print("\n=== LEGEND ===")
print("V1 (Panic Intent)  : (Actual Relocate + Blocked Intv) / Total Steps.")
print("V2 (Panic Elevate) : Actual Elevate / Total Steps. (Side Effect)")
print("V3 (Complacency)   : Actual Complacency / Total Steps.")
print("N_Tot              : Total Active Agent Steps.")
print("-" * 120)

# Export to Excel
if all_data:
    try:
        df_out = pd.DataFrame(all_data)
        out_path = "examples/single_agent/analysis/sq1_metrics_rules.xlsx"
        df_out.to_excel(out_path, index=False)
        print(f"\n[System] Successfully exported to: {out_path}")
    except Exception as e:
        print(f"\n[System] Excel export failed ({e}).")
