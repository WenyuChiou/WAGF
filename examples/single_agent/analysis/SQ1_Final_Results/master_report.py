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



def is_scale_hallucination(text):
    if not isinstance(text, str): return False
    text = text.upper()
    matches = sum(1 for code in ["VH", "H", "VL", "L", "M"] if re.search(rf'\b{code}\b', text))
    return matches >= 3

def map_text_to_level(text, keywords=None):
    if not isinstance(text, str): return "M"
    text = text.upper()
    
    # 0. Sanity Check: Scale Regurgitation -> Ambiguous (M)
    if is_scale_hallucination(text):
        return "M"

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
    # Updated path for SQ1 subfolder location
    root = Path(__file__).parent.parent.parent / "results" / "JOH_FINAL"
    group_dir = root / model / group / "Run_1"
    
    if not group_dir.exists(): 
        return None
    
    # 1. Data Discovery
    candidates = [
        group_dir / "simulation_log.csv",
        group_dir / f"{model}_disabled" / "simulation_log.csv",
        group_dir / f"{model}_strict" / "simulation_log.csv"
    ]
    
    csv_file = None
    for c in candidates:
        if c.exists():
            csv_file = c
            break
            
    if not csv_file: 
        return None

    # Jsonl check
    jsonl = group_dir / "household_traces.jsonl"
    if not jsonl.exists():
        jsonl = group_dir / "raw" / "household_traces.jsonl"
    if not jsonl.exists():
       jsonl = group_dir / f"{model}_disabled" / "household_traces.jsonl"
       
    jsonl_candidates = [jsonl] if jsonl.exists() else []

    print(f"   [File Check] {model}/{group} -> {csv_file}")
    
    try:
        df = pd.read_csv(csv_file)
        df.columns = [c.lower() for c in df.columns]
        num_agents = df['agent_id'].nunique()
        raw_rows = len(df) 
        
        # 2. High-Fidelity Appraisal Extraction
        appraisals = []
        if jsonl_candidates:
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
            if 'relocated' in full_data.columns:
                full_data = full_data[full_data['relocated'] != True]
            
            # Active N (After Filter)
            active_rows = len(full_data)

            high_labels = ["H", "VH"]
            hi_ta = full_data['ta_level'].isin(high_labels).mean()
            hi_ca = full_data['ca_level'].isin(high_labels).mean()
            
            # 4. Interventions & Granular Rule Analysis
            intv_total = 0
            intv_panic = 0      # V1: Relocation/Elevation blocked due to Low Threat
            intv_complacency = 0 # V3: Do Nothing blocked due to High Threat
            intv_realism = 0    # Constraint: Blocked due to low coping/resources
            intv_format = 0     # Fallout: JSON syntax or missing keys
            intv_hallucination = 0 # Scale Regurgitation (VL L M H VH)
            
            # Helper to classify rules
            def classify_rule(rule_str):
                r = str(rule_str).lower()
                if 'relocation_threat_low' in r or 'elevation_threat_low' in r:
                    return 'panic'
                if 'extreme_threat_block' in r:
                    return 'complacency'
                if 'low_coping_block' in r or 'elevation_block' in r:
                    return 'realism'
                return 'other'

            # Load Traces if available for high-fidelity check
            if jsonl_candidates:
                with open(jsonl_candidates[0], 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            # Robust Intervention Detection
                            retry_active = data.get('retry_count', 0) > 0
                            failed_rules = str(data.get('failed_rules', '') or data.get('validation_issues', '')).lower()
                            has_rules = failed_rules and failed_rules not in ['nan', 'none', '', '[]']
                            
                            # Check for Scale Hallucinations (Independent of intervention status)
                            proposal = data.get('skill_proposal', {})
                            reasoning = proposal.get('reasoning', {})
                            
                            ta_text = str(reasoning.get('threat_appraisal', '') or reasoning.get('TP_LABEL', ''))
                            ca_text = str(reasoning.get('coping_appraisal', '') or reasoning.get('CP_LABEL', ''))
                            
                            if is_scale_hallucination(ta_text) or is_scale_hallucination(ca_text):
                                intv_hallucination += 1


                            if retry_active or has_rules:
                                parsed_error = str(data.get('parsing_warnings', '') or data.get('error_messages', '')).lower()
                                is_syntax = ('json' in parsed_error or 'parse' in parsed_error) and not has_rules
                                
                                if not is_syntax:
                                    intv_total += 1
                                    
                                    # Extract Rule IDs from trace
                                    issues = data.get('validation_issues', [])
                                    found_type = None
                                    if issues:
                                        for i in issues:
                                            rid = i.get('rule_id', '')
                                            rtype = classify_rule(rid)
                                            if rtype != 'other':
                                                found_type = rtype
                                                break
                                    
                                    # Fallback to failed_rules string
                                    if not found_type:
                                        found_type = classify_rule(failed_rules)
                                    
                                    if found_type == 'panic': intv_panic += 1
                                    elif found_type == 'complacency': intv_complacency += 1
                                    elif found_type == 'realism': intv_realism += 1
                                
                                elif is_syntax or 'missing required fields' in parsed_error or 'format' in parsed_error:
                                    # Explicit formatting/syntax failures (Fallout)
                                    intv_total += 1
                                    intv_format += 1
                                    
                        except: continue
            
            # --- VERIFICATION RULES ANALYSIS ---
            if group == "Group_A":
                panic_states = full_data[~full_data['ta_level'].isin(["H", "VH"])]
            else:
                panic_states = full_data[full_data['ta_level'].isin(["L", "VL"])]
            
            v1_count = 0
            v2_count = 0
            
            if len(panic_states) > 0:
                v1_count = panic_states[dec_col].apply(lambda x: normalize_decision(x) == 'Relocate').sum()
                v2_count = panic_states[dec_col].apply(lambda x: normalize_decision(x) == 'Elevation').sum()
            
            high_states = full_data[full_data['ta_level'].isin(["H", "VH"])]
            v3_count = 0
            if len(high_states) > 0:
                v3_count = high_states[dec_col].apply(lambda x: normalize_decision(x) == 'DoNothing').sum()

            # V1: Panic Relocation Rate (Includes attempted-but-blocked panic)
            # We add 'intv_panic' to V1/V2 counts to capture "Intent"
            # Note: intv_panic includes both relocation and elevation blocks. 
            # Ideally we split them, but for this summary, we treat them as "Panic Intent".
            total_panic_intent = v1_count + intv_panic 
            
            # V3: Complacency Rate
            total_complacency_intent = v3_count + intv_complacency

            v1_global_rate = total_panic_intent / active_rows if active_rows > 0 else 0
            v2_global_rate = v2_count / active_rows if active_rows > 0 else 0
            v3_global_rate = total_complacency_intent / active_rows if active_rows > 0 else 0

            
            return {
                "N_Raw": raw_rows,
                "N_Active": active_rows,
                "V1_%": round(v1_global_rate * 100, 1), 
                "V1_N": total_panic_intent,             
                "V2_%": round(v2_global_rate * 100, 1), 
                "V2_N": v2_count,
                "V3_%": round(v3_global_rate * 100, 1), 
                "V3_N": total_complacency_intent,
                "Intv": intv_total,
                "Intv_P": intv_panic,
                "Intv_C": intv_complacency,
                "Intv_F": intv_format,
                "Intv_H": intv_hallucination,
                "Status": "Done"
            }
        return None
    except Exception as e:
        return {"Status": f"Err: {str(e)[:15]}"}

models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]

print("\n=== JOH SCALING REPORT: VERIFICATION RULES (REPAIRED & VERIFIED) ===")
# Headers
h_model = "Model Scale"
h_grp = "Group"
h_n = "N (Activ/Tot)"
h_v1 = "Panic Relocation Freq"
h_v2 = "Panic Elevation Freq"
h_v3 = "Complacency Rate"
h_v3 = "Complacency Rate"
h_intv = "Intv (P|C|F|H)"

print(f"{h_model:<18} {h_grp:<7} {h_n:<16} {h_v1:<30} {h_v2:<25} {h_v3:<20} {h_intv:<15}")
print("-" * 140)

for m in models:
    for g in groups:
        stats = get_stats(m, g)
        if stats:
            if "Status" in stats and str(stats["Status"]).startswith("Err"):
                print(f"{m:<18} {g:<7} ERROR: {stats['Status']}")
                continue
                
            # Format values
            n_str = f"{stats['N_Active']} ({stats['N_Raw']})"
            v1_str = f"{stats['V1_%']}% (n={stats['V1_N']})"
            v2_str = f"{stats['V2_%']}% (n={stats['V2_N']})"
            v3_str = f"{stats['V3_%']}% (n={stats['V3_N']})"
            intv_str = f"{stats['Intv']} ({stats.get('Intv_P',0)}|{stats.get('Intv_C',0)}|{stats.get('Intv_F',0)}|{stats.get('Intv_H',0)})"
            
            print(f"{m:<18} {g:<7} {n_str:<16} {v1_str:<30} {v2_str:<25} {v3_str:<20} {intv_str:<15}")
