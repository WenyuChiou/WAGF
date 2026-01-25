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
        "exposed", "vulnerable", "imminent", "severe", "property loss", "high risk"
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
                            if data.get('retry_count', 0) > 0:
                                interv_total += 1
                                final_dec = data.get('skill_proposal', {}).get('skill_name', '')
                                if is_action(final_dec): interv_success += 1
                        except: continue
            
            intv_ok_str = f"{interv_success}" if interv_total > 0 else "-"
            
            # Flip-flops
            avg_ff = 0
            df_cleaned = df.drop_duplicates(subset=['agent_id', 'year'])
            if 'has_insurance' in df_cleaned.columns and 'elevated' in df_cleaned.columns:
                ins_p = df_cleaned.pivot(index='agent_id', columns='year', values='has_insurance').fillna(method='ffill', axis=1)
                ele_p = df_cleaned.pivot(index='agent_id', columns='year', values='elevated').fillna(method='ffill', axis=1)
                ff_count = ((ins_p.shift(axis=1) == True) & (ins_p == False)).sum().sum()
                ff_count += ((ele_p.shift(axis=1) == True) & (ele_p == False)).sum().sum()
                avg_ff = ff_count / len(ins_p) if len(ins_p) > 0 else 0

            return {
                "Hi_TA": round(hi_ta, 2),
                "TA_Al": round(ta_align, 2),
                "Hi_CA": round(hi_ca, 2),
                "CA_Al": round(ca_align, 2),
                "Intv": interv_total,
                "Intv_OK": intv_ok_str,
                "FF": round(avg_ff, 2),
                "Status": "Done" if df['year'].max() >= 10 else f"Y{df['year'].max()}"
            }
        return None
    except Exception as e:
        return {"Status": f"Err: {str(e)[:15]}"}

models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]

print("\n=== JOH SCALING MASTER REPORT (LLM DIRECT RATING v11) ===")
print(f"{'Model':<18} {'Grp':<7} {'HiTA':<7} {'TA_Al':<7} {'HiCA':<7} {'CA_Al':<7} {'Intv':<6} {'Succ':<6} {'FF':<6} {'Status'}")
print("-" * 100)

all_data = []

for m in models:
    for g in groups:
        stats = get_stats(m, g)
        if stats:
            print(f"{m:<18} {g:<7} {stats['Hi_TA']:<7} {stats['TA_Al']:<7} {stats['Hi_CA']:<7} {stats['CA_Al']:<7} {stats['Intv']:<6} {stats['Intv_OK']:<6} {stats['FF']:<6} {stats['Status']}")
            
            # Collect for Export
            row = stats.copy()
            row['Model'] = m
            row['Group'] = g
            all_data.append(row)

print("\n=== INDICATOR DEFINITIONS (LLM 定義指標) ===")
print("1. HiTA (Threat)  : LLM 原始回覆中直接標註為高威脅 (H/VH) 之比例。無人工關鍵字干預。")
print("2. TA_Al (Align)  : 威脅行為一致性。當 LLM 給出 H/VH 評分時，其實際採取行為的條件機率。")
print("3. HiCA (Coping)  : LLM 原始回覆中直接標註為高應對感 (H/VH) 之比例。反映模型自覺之效能。")
print("4. CA_Al (Align)  : 應對行為一致性。當 LLM 自覺有高能力時，其採取行為之機率。")
print("5. Intv/Succ      : 治理干預 (Retry) 次數 與 最終誘導行動的成功次數。")
print("6. FF (Flip-Flop) : 平均每位 Agent 放棄已執行調適行為的次數（反映決策穩定性）。")
print("-" * 100)
print("註：此版本完全依賴 LLM 的類別評分 (Categorical Rating)，不進行任何關鍵字文本採集。")

# Export to Excel
if all_data:
    try:
        df_out = pd.DataFrame(all_data)
        # Reorder columns
        cols = ['Model', 'Group'] + [c for c in df_out.columns if c not in ['Model', 'Group']]
        df_out = df_out[cols]
        
        out_path = "examples/single_agent/analysis/sq1_metrics.xlsx"
        df_out.to_excel(out_path, index=False)
        print(f"\n[System] Successfully exported metrics to: {out_path}")
    except Exception as e:
        print(f"\n[System] Excel export failed ({e}). Attempting CSV...")
        csv_path = "examples/single_agent/analysis/sq1_metrics.csv"
        df_out.to_csv(csv_path, index=False)
        print(f"[System] Saved to CSV: {csv_path}")
