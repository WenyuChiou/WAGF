import pandas as pd
import json
import re
import os
import sys
from pathlib import Path

# --- Flood Years (Ground Truth for V3) ---
# Years when actual flooding occurred in the simulation
FLOOD_YEARS = [3, 4, 9]

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
    
    # Discount if not found
    if not csv: 
        return {"Status": "Missing Log"}

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

            # FILTER: Exclude agents who have already relocated (Zombies)
            # But KEEP the step where they decided to relocate.
            if dec_col in full_data.columns:
                 full_data = full_data[~full_data[dec_col].astype(str).str.lower().str.contains('already relocated|relocated', regex=True) | 
                                       (full_data[dec_col].astype(str).str.lower() == 'relocate')]
            
            # Binary Classification: High vs Low (Everything else is Low)
            # High = H, VH. Low = M, L, VL. (Satisfies L+H=N)
            n_tp_high = len(full_data[full_data['ta_level'].isin(['H', 'VH'])])
            n_tp_low = len(full_data) - n_tp_high
            
            n_cp_high = len(full_data[full_data['ca_level'].isin(['H', 'VH'])])
            n_cp_low = len(full_data) - n_cp_high
            
            # 4. Verification Rules Analysis (Transition-Based for One-Time Skills)
            df_sorted = full_data.sort_values(['agent_id', 'year'])
            df_sorted['relocated_prev'] = df_sorted.groupby('agent_id')['relocated'].shift(1).fillna(False)
            df_sorted['elevated_prev'] = df_sorted.groupby('agent_id')['elevated'].shift(1).fillna(False)
            
            # V1 Actual: Relocated transition under low threat
            v1_mask = (df_sorted['relocated'] == True) & (df_sorted['relocated_prev'] == False)
            v1_mask &= df_sorted['ta_level'].isin(['L', 'VL', 'M'] if group == "Group_A" else ['L', 'VL'])
            v1_count = v1_mask.sum()
            
            # V2 Actual: Elevation transition under low threat
            v2_mask = (df_sorted['elevated'] == True) & (df_sorted['elevated_prev'] == False)
            v2_mask &= df_sorted['ta_level'].isin(['L', 'VL', 'M'] if group == "Group_A" else ['L', 'VL'])
            v2_count = v2_mask.sum()
            
            # V3 Actual: "Do Nothing" under VH threat OR during actual flood years
            # For Group A: Use both keyword-inferred VH AND actual flood years (ground truth)
            # This prevents underestimation when keyword analysis classifies most as "M"
            if group == "Group_A":
                # V3 = Do Nothing when (VH threat OR actual flood year)
                v3_mask = (
                    (full_data['ta_level'].isin(['VH'])) |
                    (full_data['year'].isin(FLOOD_YEARS))
                )
                v3_src = full_data[v3_mask]
            else:
                # Group B/C: Use structured TP_LABEL only
                v3_src = full_data[full_data['ta_level'].isin(['VH', 'H'])]
            v3_count = v3_src[dec_col].apply(lambda x: normalize_decision(x) == 'DoNothing').sum() if len(v3_src) > 0 else 0
            
            # --- Relocation Moment Consistency Analysis (Transition-Based) ---
            reloc_moments = df_sorted[(df_sorted['relocated'] == True) & (df_sorted['relocated_prev'] == False)]
            audit = reloc_moments['ta_level'].value_counts().to_dict()
            high_count = audit.get('H',0) + audit.get('VH',0)
            low_count = sum(audit.values()) - high_count
            audit_str = f"{low_count}|{high_count}"
            intv_rules, intv_thinking_events, intv_hallucination, intv_parse_errors = 0, 0, 0, 0
            intv_v1, intv_v2, intv_v3 = 0, 0, 0
            p_empty, p_label, p_syntax = 0, 0, 0

            # 1. GROUND TRUTH: Logic Blocks from Governance Summary
            summary_path = group_dir / "governance_summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path, 'r', encoding='utf-8') as sf:
                        s_data = json.load(sf)
                        # Intv_R = Total Thinking Rule Violations (incl. retries)
                        intv_rules = s_data.get('total_interventions', 0)
                        
                        # Intv_S = Successful Thinking Events (Decisions blocked)
                        o_stats = s_data.get('outcome_stats', {})
                        intv_thinking_events = o_stats.get('retry_success', 0) + o_stats.get('retry_exhausted', 0)
                        intv_parse_errors = o_stats.get('parse_errors', 0)
                        
                        # Breakdown Counters (Already initialized)
                    
                    # 1.1 BACKFILL TRANSIENT PARSE ERRORS (FOR SQ1 AUDIT)
                    # If repo summary is 0 but retries exist, scan log for transient structural faults
                    exec_log_path = group_dir / "execution.log"
                    if intv_parse_errors == 0 and exec_log_path.exists():
                        try:
                            # Try UTF-16 first (PowerShell default), then UTF-8
                            encodings = ['utf-16', 'utf-8']
                            found_log = False
                            
                            for enc in encodings:
                                try:
                                    if found_log: break
                                    with open(exec_log_path, 'r', encoding=enc, errors='ignore') as f:
                                        # Read first line to check validity / BOM
                                        first = f.read(2)
                                        f.seek(0)
                                        
                                        # Process lines
                                        for line in f:
                                            # Case 1: Broker Retries
                                            if "[Broker:Retry]" in line:
                                                if any(k in line for k in ["Empty/Null response", "Response was empty", "returned truly empty content"]):
                                                    p_empty += 1
                                                elif "Invalid _LABEL values" in line:
                                                    p_label += 1
                                                elif any(k in line for k in ["Missing required constructs", "returned unparsable output"]):
                                                    p_syntax += 1
                                                    
                                            # Case 2: Validation Criticals (Label Hallucination)
                                            elif "[Adapter:Validation] CRITICAL" in line and "Invalid _LABEL values" in line:
                                                p_label += 1
                                                
                                            # Case 3: LLM Retries (Hard Crashes)
                                            elif "[LLM:Retry]" in line and "returned truly empty content" in line:
                                                p_empty += 1
                                        found_log = True
                                        
                                        # Update Total P if scan found anything (and overwrite default 0)
                                        if (p_empty + p_label + p_syntax) > 0:
                                            intv_parse_errors = p_empty + p_label + p_syntax
                                except: continue
                        except: pass

                        
                        # Rule Frequency Mapping (for breakdown)
                        r_freq = s_data.get('rule_frequency', {})
                        intv_v1 = r_freq.get('relocation_threat_low', 0)
                        intv_v2 = r_freq.get('elevation_threat_low', 0)
                        intv_v3 = r_freq.get('extreme_threat_block', 0) + r_freq.get('builtin_high_tp_cp_action', 0)
                        
                        # Cleanup
                        captured = intv_v1 + intv_v2 + intv_v3
                        if captured < intv_rules:
                            intv_v1 += (intv_rules - captured)
                except: pass

            # 2. Hallucination Repairs (Residual Retries)
            trace_total_events = 0
            if jsonl_candidates:
                try:
                    with open(jsonl_candidates[0], 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                data = json.loads(line)
                                if data.get('retry_count', 0) > 0:
                                    trace_total_events += 1
                            except: continue
                except: pass
            
            if intv_thinking_events > 0:
                intv_hallucination = max(0, trace_total_events - intv_thinking_events - intv_parse_errors)
            else:
                intv_thinking_events = trace_total_events
            
            # Format Combined String (Rules/S/P)
            intv_ok_str = f"{intv_rules}/{intv_thinking_events}/{intv_parse_errors}"
            if intv_v1 == 0 and intv_thinking_events > 0:
                 intv_v1 = intv_thinking_events

            # Sub-components for explicit mapping
            v1_int, v2_int, v3_int = intv_v1, intv_v2, intv_v3
            v1_act, v2_act, v3_act = v1_count, v2_count, v3_count
            
            # --- VERIFICATION RULES ANALYSIS (INTENT = ACTUAL + BLOCKED) ---
            v1_total = intv_v1 + v1_count
            v2_total = intv_v2 + v2_count
            v3_total = intv_v3 + v3_count
            
            # METRIC ALIGNMENT: Rules column must represent TOTAL INTENT (Blocked + Leaked)
            total_intent = v1_total + v2_total + v3_total
            
            interv_total = intv_rules + intv_parse_errors # Total Workload
            interv_success = intv_thinking_events 
            intv_ok_str = f"{total_intent}/{interv_success}/{intv_parse_errors}" if (total_intent + intv_parse_errors) > 0 else "-"
            
            # Sub-components
            v1_int, v2_int, v3_int = intv_v1, intv_v2, intv_v3
            
            # --- VERIFICATION RULES ANALYSIS (INTENT = ACTUAL + BLOCKED) ---
            v1_total = intv_v1 + v1_count
            v2_total = intv_v2 + v2_count
            v3_total = intv_v3 + v3_count
            
            # Sub-components for explicit mapping
            v1_int, v2_int, v3_int = intv_v1, intv_v2, intv_v3
            v1_act, v2_act, v3_act = v1_count, v2_count, v3_count
            
            # Global Rates (Now based on Blocked Attempts)
            v1_global_rate = v1_total / len(full_data) if len(full_data) > 0 else 0
            v2_global_rate = v2_total / len(full_data) if len(full_data) > 0 else 0
            v3_global_rate = v3_total / len(full_data) if len(full_data) > 0 else 0

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
            
            # R_H Calculation (Hallucination Rate)
            # Group A: Actual violations (no governance to block)
            # Group B/C: retry_exhausted (leaked despite governance)
            n_data = len(full_data) if full_data is not None else 0
            if group == "Group_A":
                # R_H = (V1_Act + V2_Act + V3_Act) / N
                r_h_leaked = v1_count + v2_count + v3_count
                r_h = round(r_h_leaked / n_data * 100, 2) if n_data > 0 else 0
            else:
                # R_H = retry_exhausted / N (from governance_summary)
                retry_exhausted = 0
                if summary_path.exists():
                    try:
                        with open(summary_path, 'r', encoding='utf-8') as sf:
                            s_data = json.load(sf)
                            retry_exhausted = s_data.get('outcome_stats', {}).get('retry_exhausted', 0)
                    except: pass
                r_h_leaked = retry_exhausted
                r_h = round(r_h_leaked / n_data * 100, 2) if n_data > 0 else 0

            return {
                "Status": "Done" if df['year'].max() >= 10 else f"Y{df['year'].max()}",
                "N": n_data,
                "TP_Pop": f"{n_tp_low}|{n_tp_high}", "CP_Pop": f"{n_cp_low}|{n_cp_high}",
                "V1_Tot": v1_total, "V1_Act": v1_count,
                "V2_Tot": v2_total, "V2_Act": v2_count,
                "V3_Tot": v3_total, "V3_Act": v3_count,
                "R_H": r_h, "R_H_Leaked": r_h_leaked,
                "Intv": intv_rules, "Intv_S": intv_thinking_events, "Intv_P": intv_parse_errors,
                "Intv_P_Empty": p_empty, "Intv_P_Label": p_label, "Intv_P_Syntax": p_syntax,
                "Intv_H": intv_hallucination, "Intv_OK": intv_ok_str,
                "V1_%": round(v1_global_rate * 100, 1),
                "V2_%": round(v2_global_rate * 100, 1),
                "V3_%": round(v3_global_rate * 100, 1),
                "FF": round(weighted_ff * 100, 2),
                "Audit": audit, "Audit_Str": audit_str
            }
        return None
    except Exception as e:
        return {"Status": f"Err: {str(e)}"}

models = ["gemma3_4b", "gemma3_12b", "gemma3_27b", "ministral3_3b", "ministral3_8b", "ministral3_14b"]
groups = ["Group_A", "Group_B", "Group_C"]

print("\n=== JOH SCALING REPORT: VERIFICATION RULES (GLOBAL FREQUENCY - FINAL) ===")
# Headers
h_model = "Model"
h_grp = "Group"
h_n = "N"
h_v1, h_v2, h_v3 = "V1", "V2", "V3"
h_retry = "Retry"
h_rh = "R_H(%)"
h_ff = "FF(%)"

print("\n" + "="*100)
with open('gemma_master_report_output.txt', 'w') as f_out:
    header = f"{h_model:<15} {h_grp:<10} {h_n:<6} {h_v1:<6} {h_v2:<6} {h_v3:<6} {h_retry:<8} {h_rh:<10} {h_ff:<10}"
    print(header)
    f_out.write(header + "\n")
    print("-" * 100)
    f_out.write("-" * 100 + "\n")
    
    all_data = []

    for m in models:
        for g in groups:
            stats = get_stats(m, g)

            if stats:
                if "R_H" not in stats and "Status" in stats and str(stats["Status"]).startswith("Err"):
                    msg = f"{m:<15} {g:<10} ERROR: {stats['Status']}"
                    print(msg)
                    f_out.write(msg + "\n")
                    continue

                if 'R_H' not in stats: continue

                # Get retry count (for Group B/C)
                retry_count = stats.get('Intv', 0) if g != "Group_A" else "-"

                # Print aligned table row
                m_short = m.replace("gemma3_", "").replace("ministral3_", "mist_")
                row_str = f"{m_short:<15} {g:<10} {stats['N']:<6} {stats['V1_Act']:<6} {stats['V2_Act']:<6} {stats['V3_Act']:<6} {str(retry_count):<8} {stats['R_H']:<10} {stats['FF']:<10}"
                print(row_str)
                f_out.write(row_str + "\n")

                # Collect for Export
                row = stats.copy()
                row['Model'] = m
                row['Group'] = g
                all_data.append(row)

print("\n" + "="*100)
print("\n=== R_H CALCULATION GUIDE ===")
print("Group A: R_H = (V1 + V2 + V3) / N  [No governance, all violations leak]")
print("  - V1: Relocate under low threat (L/VL/M)")
print("  - V2: Elevate under low threat (L/VL/M)")
print("  - V3: Do Nothing under VH threat OR during actual flood years")
print("Group B/C: R_H = retry_exhausted / N  [Leaked despite governance]")
print("-" * 100)
print("Retry: Total interventions triggered by governance (Group B/C only)")
print("=" * 100)

from pathlib import Path
import pandas as pd

OUTPUT_DIR = Path("examples/single_agent/analysis/SQ1_Final_Results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True) # Ensure directory exists

# Export to Excel
if all_data:
    try:
        df_out = pd.DataFrame(all_data)
        # Reorder and rename for end-user clarity
        export_cols = [
            'Model', 'Group', 'N',
            'V1_Act', 'V2_Act', 'V3_Act',
            'R_H', 'R_H_Leaked',
            'Intv', 'Intv_S', 'Intv_P', 'FF', 'Audit_Str'
        ]
        # Filter for existing columns
        existing = [c for c in export_cols if c in df_out.columns]
        df_out[existing].to_excel(OUTPUT_DIR / "sq1_metrics_rules.xlsx", index=False)
        print(f"\n[System] Successfully exported to: {OUTPUT_DIR / 'sq1_metrics_rules.xlsx'}")
    except Exception as e:
        print(f"\n[Error] Excel Export Failed: {e}")
