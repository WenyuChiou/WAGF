
import pandas as pd
import json
import re
import os
from pathlib import Path

# --- Semantic Analysis Logic ---
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
    if re.search(r'\bVH\b', text): return "VH"
    if re.search(r'\bH\b', text): return "H"
    if re.search(r'\bVL\b', text): return "VL"
    if re.search(r'\bL\b', text): return "L"
    if re.search(r'\bM\b', text): return "M"
    
    if keywords:
        if any(w.upper() in text for w in keywords.get("H", [])): return "H"
        if any(w.upper() in text for w in keywords.get("L", [])): return "L"
    return "M"

def normalize_decision(d):
    d = str(d).lower()
    if 'relocate' in d: return 'Relocate'
    if 'elevat' in d: return 'Elevation'
    if 'insur' in d: return 'Insurance'
    if 'dn' in d or 'nothing' in d: return 'DoNothing'
    return 'Other'

def get_base_rates(model, group):
    root = Path("examples/single_agent/results/JOH_FINAL")
    group_dir = root / model / group / "Run_1"
    
    if not group_dir.exists(): return None
    
    candidates = [
        group_dir / "simulation_log.csv",
        group_dir / f"{model}_disabled" / "simulation_log.csv",
        group_dir / f"{model}_strict" / "simulation_log.csv"
    ]
    
    jsonl_candidates = [
        group_dir / "household_traces.jsonl",
        group_dir / "raw" / "household_traces.jsonl"
    ]
    jsonl_candidates = [p for p in jsonl_candidates if p.exists()]
    
    csv = None
    for c in candidates:
        if c.exists():
            csv = c
            break
            
    if not csv: return None
    
    try:
        df = pd.read_csv(csv)
        df.columns = [c.lower() for c in df.columns]
        
        # Determine Appraisal Source
        appraisals = []
        if jsonl_candidates:
             with open(jsonl_candidates[0], 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        year = data.get('year')
                        proposal = data.get('skill_proposal', {})
                        reasoning = proposal.get('reasoning', {})
                        # Standardized key lookup based on master_report.py
                        ta = (reasoning.get('TP_LABEL') or 
                              reasoning.get('threat_appraisal', {}).get('label'))
                        ca = (reasoning.get('CP_LABEL') or 
                              reasoning.get('coping_appraisal', {}).get('label'))
                        
                        if ta or ca:
                            appraisals.append({'agent_id': data.get('agent_id'), 'year': year, 'ta': ta, 'ca': ca})
                    except: continue
        else:
            reason_col = next((c for c in df.columns if 'reasoning' in c), None)
            for idx, row in df.iterrows():
                text_ta = " ".join([str(row.get(c, "")) for c in ['threat_appraisal', reason_col] if c in df.columns])
                text_ca = " ".join([str(row.get(c, "")) for c in ['coping_appraisal', reason_col] if c in df.columns])
                appraisals.append({'agent_id': row['agent_id'], 'year': row['year'], 'ta': text_ta, 'ca': text_ca})

        # Merge Appraisals
        if appraisals:
            ap_df = pd.DataFrame(appraisals).drop_duplicates(subset=['agent_id', 'year'])
            full_data = df.merge(ap_df, on=['agent_id', 'year'], how='left')
            full_data['ta_level'] = full_data['ta'].apply(lambda x: map_text_to_level(x, TA_KEYWORDS))
            full_data['ca_level'] = full_data['ca'].apply(lambda x: map_text_to_level(x, CA_KEYWORDS))
        else:
            full_data = df
            full_data['ta_level'] = "M"
            full_data['ca_level'] = "M"


        # FILTER: Zombie Filter (Exclude 'Already relocated')
        dec_col = next((c for c in ['decision', 'yearly_decision'] if c in df.columns), None)
        if dec_col:
             full_data = full_data[~full_data[dec_col].astype(str).str.lower().str.contains('already relocated|relocated', regex=True) | 
                                   (full_data[dec_col].astype(str).str.lower() == 'relocate')]

        # --- Base Rate Calculation ---
        total_n = len(full_data)
        
        # Binary Classification: High vs Low (Everything else is Low)
        # High = H, VH. Low = M, L, VL. (Satisfies L+H=N)
        n_tp_high = len(full_data[full_data['ta_level'].isin(['H', 'VH'])])
        n_tp_low = total_n - n_tp_high
        
        n_cp_high = len(full_data[full_data['ca_level'].isin(['H', 'VH'])])
        n_cp_low = total_n - n_cp_high
        
        # Rule Trigger Logic (Binary Denominators, Rule-Specific Numerators)
        # V1/V2: Sources are Low TP. 
        # BUT for BC, "Verification Rule" targets ONLY L/VL (Strict Low).
        
        if group == "Group_A":
            v1_src = full_data[full_data['ta_level'].isin(['L', 'VL', 'M'])]
            v2_src = full_data[full_data['ta_level'].isin(['L', 'VL', 'M'])]
        else:
            # Group B/C follows "Verification Rule": Strict Low only
            v1_src = full_data[full_data['ta_level'].isin(['L', 'VL'])]
            v2_src = full_data[full_data['ta_level'].isin(['L', 'VL'])]
            
        v1_reloc = v1_src[dec_col].apply(lambda x: normalize_decision(x) == 'Relocate').sum() if len(v1_src) > 0 else 0
        v2_elev = v2_src[dec_col].apply(lambda x: normalize_decision(x) == 'Elevation').sum() if len(v2_src) > 0 else 0
        
        v3_src = full_data[full_data['ta_level'].isin(['H', 'VH'])]
        v3_compl = v3_src[dec_col].apply(lambda x: normalize_decision(x) == 'DoNothing').sum() if len(v3_src) > 0 else 0
        
        # --- Relocation Moment Consistency Analysis ---
        # We track the TP level AT THE EXACT YEAR of relocation
        reloc_moments = full_data[full_data[dec_col].apply(normalize_decision) == 'Relocate']
        reloc_tp_counts = reloc_moments['ta_level'].value_counts().to_dict()
        
        return {
            "N": total_n,
            "LowTP": n_tp_low,
            "HighTP": n_tp_high,
            "LowCP": n_cp_low,
            "HighCP": n_cp_high,
            "V1": v1_reloc,
            "V2": v2_elev,
            "V3": v3_compl,
            "Reloc_TP_Audit": reloc_tp_counts
        }

    except Exception as e:
        return {"Error": str(e)}

models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]

print(f"{'Model':<18} {'Grp':<7} {'N':<5} {'L-TP':<5} {'H-TP':<5} {'L-CP':<5} {'H-CP':<5} {'V1':<4} {'V2':<4} {'V3':<4} {'Reloc-Moment (L|M|H)':<20}")
print("-" * 120)
for m in models:
    for g in groups:
        s = get_base_rates(m, g)
        if s and "Error" not in s:
            audit = s.get('Reloc_TP_Audit', {})
            # Binary Audit: Low (Non-High) | High
            high_count = audit.get('H',0) + audit.get('VH',0)
            low_count = sum(audit.values()) - high_count
            audit_str = f"{low_count} | {high_count}"
            print(f"{m:<18} {g:<7} {s['N']:<5} {s['LowTP']:<5} {s['HighTP']:<5} {s['LowCP']:<5} {s['HighCP']:<5} {s['V1']:<4} {s['V2']:<4} {s['V3']:<4} {audit_str:<20}")
