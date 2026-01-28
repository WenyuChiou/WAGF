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
        # Perceived Severity (Rogers, 1975; Maddux & Rogers, 1983)
        "severe", "critical", "extreme", "catastrophic", "significant harm", "dangerous", "bad", "devastating",
        # Perceived Susceptibility / Vulnerability
        "susceptible", "likely", "high risk", "exposed", "probability", "chance", "vulnerable",
        # Fear Arousal
        "afraid", "anxious", "worried", "concerned", "frightened", "emergency", "flee"
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
    # STRICT PATH SELECTION (No Glob Ghosts)
    candidates = [
        group_dir / "simulation_log.csv",
        group_dir / f"{model}_disabled" / "simulation_log.csv",
        group_dir / f"{model}_strict" / "simulation_log.csv"
    ]
    
    csv = None
    for c in candidates:
        if c.exists():
            csv = c
            break
    
    # Discovery of JSONL Trace Files (Fix)
    jsonl_candidates = [
        group_dir / "household_traces.jsonl",
        group_dir / "raw" / "household_traces.jsonl"
    ]
    jsonl_candidates = [p for p in jsonl_candidates if p.exists()]
    
    # if not csv: 
    #     print(f"   [Warning] No simulation_log.csv found in {group_dir}")
    #     return None

    # print(f"   [File Check] {model}/{group} -> {csv}")
    
    try:
        df = pd.read_csv(csv)
        df.columns = [c.lower() for c in df.columns]
        # print(f"   [Year Check] Max Year: {df['year'].max()}")
        num_agents = df['agent_id'].nunique()
        
        # 2. High-Fidelity Appraisal Extraction
        appraisals = []
        if jsonl_candidates:
            # DEBUG: Verify Data Integrity (Proposed Edit)
            # try:
            #     with open(jsonl_candidates[0], 'r', encoding='utf-8') as f:
            #         jsonl_count = sum(1 for _ in f)
            #     print(f"   [Data Audit] {model}/{group}: CSV rows={len(df)}, JSONL lines={jsonl_count} (Delta={jsonl_count - len(df)})")
            # except:
            #     pass

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

            # FILTER: Exclude agents who have already relocated (Zombies)
            # But KEEP the step where they decided to relocate.
            if dec_col in full_data.columns:
                 full_data = full_data[~full_data[dec_col].astype(str).str.lower().str.contains('already relocated|relocated', regex=True) | 
                                       (full_data[dec_col].astype(str).str.lower() == 'relocate')]
            
            # Binary Classification: High vs Low (Everything else is Low)

            # Binary Classification: High vs Low (Everything else is Low)
            # High = H, VH. Low = M, L, VL. (Satisfies L+H=N)
            n_tp_high = len(full_data[full_data['ta_level'].isin(['H', 'VH'])])
            n_tp_low = len(full_data) - n_tp_high
            
            n_cp_high = len(full_data[full_data['ca_level'].isin(['H', 'VH'])])
            n_cp_low = len(full_data) - n_cp_high
            
            # 4. Verification Rules Analysis
            # V1/V2: Sources are Low TP. 
            # BUT for BC, "Verification Rule" targets ONLY L/VL (Strict Low).
            if group == "Group_A":
                v12_src = full_data[full_data['ta_level'].isin(['L', 'VL', 'M'])]
            else:
                # Group B/C follows "Verification Rule": Strict Low only
                v12_src = full_data[full_data['ta_level'].isin(['L', 'VL'])]
            
            v1_count = v12_src[dec_col].apply(lambda x: normalize_decision(x) == 'Relocate').sum() if len(v12_src) > 0 else 0
            v2_count = v12_src[dec_col].apply(lambda x: normalize_decision(x) == 'Elevation').sum() if len(v12_src) > 0 else 0
            
            v3_src = full_data[full_data['ta_level'].isin(['H', 'VH'])]
            v3_count = v3_src[dec_col].apply(lambda x: normalize_decision(x) == 'DoNothing').sum() if len(v3_src) > 0 else 0
            
            # --- Relocation Moment Consistency Analysis ---
            reloc_moments = full_data[full_data[dec_col].apply(normalize_decision) == 'Relocate']
            audit = reloc_moments['ta_level'].value_counts().to_dict()
            high_count = audit.get('H',0) + audit.get('VH',0)
            low_count = sum(audit.values()) - high_count
            audit_str = f"{low_count}|{high_count}"
            interv_total = 0
            interv_success = 0
            intv_hallucination = 0 # Track Ghosting/Invalid Values
            
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
                                combined_error = parsed_error + " " + failed_rules
                                
                                # Heuristic: it is Governance if Rules Failed OR Error is not purely syntax
                                is_syntax = ('json' in parsed_error or 'parse' in parsed_error) and not has_rules
                                
                                # Ghosting / Hallucination Check (Invalid Values or Scale Regurgitation)
                                if 'invalid label values' in combined_error or 'missing required constructs' in combined_error:
                                    interv_total += 1
                                    intv_hallucination += 1
                                
                                elif not is_syntax:
                                    interv_total += 1
                                    final_dec = data.get('skill_proposal', {}).get('skill_name', '')
                                    if is_action(final_dec): interv_success += 1

                        except: continue
            
            intv_ok_str = f"{interv_success}" if interv_total > 0 else "-"
            
            # --- VERIFICATION RULES ANALYSIS ---
            # Global Frequency Calculation
            total_panic_intent = v1_count + interv_success
            v1_global_rate = total_panic_intent / len(full_data) if len(full_data) > 0 else 0
            v2_global_rate = v2_count / len(full_data) if len(full_data) > 0 else 0
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
                "L_TP": n_tp_low,
                "H_TP": n_tp_high,
                "L_CP": n_cp_low,
                "H_CP": n_cp_high,
                "V1_%": round(v1_global_rate * 100, 1), # Global Panic Intent
                "V1_N": total_panic_intent,             # Count = Actual + Blocked
                "V1_Act": v1_count,                     # Keep Actual for reference
                "V2_%": round(v2_global_rate * 100, 1), 
                "V2_N": v2_count,
                "V3_%": round(v3_global_rate * 100, 1), 
                "V3_N": v3_count,
                "Intv": interv_total,
                "Intv_S": interv_success,
                "Intv_H": intv_hallucination,
                "FF": round(weighted_ff * 100, 2),
                "Audit_Str": audit_str,
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
h_n = "Steps"
h_pop = "L|H TP  |  L|H CP"
h_v1 = "Panic(V1)"
h_v2 = "Elev(V2)"
h_v3 = "Comp(V3)"
h_intv = "Intv(S|H)"
h_ff = "FF"
h_audit = "Reloc Audit(L|H)"

print(f"{h_model:<18} {h_grp:<7} {h_n:<6} {h_pop:<25} {h_v1:<18} {h_v2:<18} {h_v3:<16} {h_intv:<15} {h_ff:<10} {h_audit:<15}")
print("-" * 155)

all_data = []

for m in models:
    for g in groups:
        stats = get_stats(m, g)
        if stats:
            if "V1_% " not in stats and "Status" in stats and str(stats["Status"]).startswith("Err"):
                print(f"{m:<18} {g:<7} ERROR: {stats['Status']}")
                continue
            
            if 'V1_%' not in stats: continue

            # Format values
            v1_str = f"{stats['V1_%']}% (n={stats['V1_N']})"
            v2_str = f"{stats['V2_%']}% (n={stats['V2_N']})"
            v3_str = f"{stats['V3_%']}% (n={stats['V3_N']})"
            pop_str = f"{stats['L_TP']}|{stats['H_TP']} | {stats['L_CP']}|{stats['H_CP']}"
            intv_str = f"{stats['Intv']} ({stats['Intv_S']}|{stats['Intv_H']})"
            ff_str = f"{stats['FF']}%"
            audit_str = stats['Audit_Str']
            
            print(f"{m:<18} {g:<7} {stats['N']:<8} {pop_str:<25} {v1_str:<18} {v2_str:<18} {v3_str:<18} {intv_str:<15} {ff_str:<10} {audit_str:<15}")
            
            # Collect for Export
            row = stats.copy()
            row['Model'] = m
            row['Group'] = g
            all_data.append(row)

print("\n=== LEGEND ===")
print("V1 (Panic Intent)  : (Actual Relocate + Blocked Intv) / Total Steps.")
print("V2 (Panic Elevate) : Actual Elevate / Total Steps. (Side Effect)")
print("V3 (Complacency)   : Actual Complacency / Total Steps.")
print("Intv (S|H)         : Total Interventions (Successful Block | Hallucination/Ghosting).")
print("FF (Flip-Flop)     : % of decisions changed vs previous year (active agents).")
print("-" * 120)

# Export to Excel
if all_data:
    try:
        df_out = pd.DataFrame(all_data)
        out_path = "examples/single_agent/analysis/SQ1_Final_Results/sq1_metrics_rules.xlsx"
        df_out.to_excel(out_path, index=False)
        print(f"\n[System] Successfully exported to: {out_path}")
    except Exception as e:
        print(f"\n[System] Excel export failed ({e}).")
