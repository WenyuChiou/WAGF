"""
R_H 與幻覺率表格
- R_H: 真正洩漏 (retry_exhausted / N_active)
- 幻覺率: 所有 retry 嘗試 (total_interventions / N_active)
- 驗證器解決率: retry_success / total_interventions
"""
import pandas as pd
import numpy as np
import json
import re
import os
from pathlib import Path

BASE = str(Path(__file__).resolve().parents[4] / 'examples' / 'single_agent' / 'results' / 'JOH_FINAL')

TA_KEYWORDS = {
    "H": ["severe", "critical", "extreme", "catastrophic", "dangerous", "devastating",
          "susceptible", "likely", "high risk", "exposed", "vulnerable",
          "afraid", "anxious", "worried", "concerned", "frightened", "emergency", "flee"],
    "L": ["minimal", "safe", "none", "low", "unlikely", "no risk", "protected", "secure"]
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

model = 'gemma3_4b'
results = []

for group in ['Group_A', 'Group_B', 'Group_C']:
    csv_path = os.path.join(BASE, model, group, 'Run_1', 'simulation_log.csv')
    df = pd.read_csv(csv_path)
    df.columns = [c.lower() for c in df.columns]

    if group == 'Group_A':
        dec_col = 'decision'
        active = df[df[dec_col] != 'Already relocated'].copy()
    else:
        dec_col = 'yearly_decision'
        active = df[df[dec_col] != 'relocated'].copy()

    n_active = len(active)

    if group == 'Group_A':
        # Group A: 無驗證器，直接計算 V1+V2+V3
        active['yearly_dec'] = active.get('raw_llm_decision', active[dec_col])
        text_cols = ['threat_appraisal', 'memory']
        active['ta_text'] = active[[c for c in text_cols if c in active.columns]].fillna('').astype(str).agg(' '.join, axis=1)
        active['ta_level'] = active['ta_text'].apply(lambda x: map_text_to_level(x, TA_KEYWORDS))

        low_threat_values = ['L', 'VL', 'M']
        active_sorted = active.sort_values(['agent_id', 'year']).copy()
        active_sorted['relocated_prev'] = active_sorted.groupby('agent_id')['relocated'].shift(1).fillna(False)
        active_sorted['elevated_prev'] = active_sorted.groupby('agent_id')['elevated'].shift(1).fillna(False)

        reloc_trans = (active_sorted['relocated'] == True) & (active_sorted['relocated_prev'] == False)
        low_threat = active_sorted['ta_level'].isin(low_threat_values)
        v1 = (reloc_trans & low_threat).sum()

        elev_trans = (active_sorted['elevated'] == True) & (active_sorted['elevated_prev'] == False)
        v2 = (elev_trans & low_threat).sum()

        vh_threat = active_sorted['ta_level'] == 'VH'
        do_nothing = active_sorted['yearly_dec'].str.contains('nothing', case=False, na=False)
        v3 = (vh_threat & do_nothing).sum()

        n_leaked = v1 + v2 + v3

        results.append({
            'Group': group,
            'N_active': n_active,
            'Total_Attempts': n_leaked,  # Group A 無驗證器，所以嘗試=洩漏
            'Retry_Success': 0,
            'Retry_Exhausted': n_leaked,
            'Parse_Errors': 0,
            'Hallucination_Rate': f'{n_leaked/n_active*100:.2f}%',
            'Validator_Fix_Rate': 'N/A (無驗證器)',
            'R_H': f'{n_leaked/n_active*100:.2f}%'
        })

    else:
        # Group B/C: 使用 governance_summary
        summary_path = os.path.join(BASE, model, group, 'Run_1', 'governance_summary.json')
        with open(summary_path, 'r') as f:
            summary = json.load(f)

        total_interventions = summary.get('total_interventions', 0)
        outcome_stats = summary.get('outcome_stats', {})
        retry_success = outcome_stats.get('retry_success', 0)
        retry_exhausted = outcome_stats.get('retry_exhausted', 0)
        parse_errors = outcome_stats.get('parse_errors', 0)

        hallucination_rate = total_interventions / n_active * 100 if n_active > 0 else 0
        validator_fix_rate = retry_success / total_interventions * 100 if total_interventions > 0 else 0
        rh = retry_exhausted / n_active * 100 if n_active > 0 else 0

        results.append({
            'Group': group,
            'N_active': n_active,
            'Total_Attempts': total_interventions,
            'Retry_Success': retry_success,
            'Retry_Exhausted': retry_exhausted,
            'Parse_Errors': parse_errors,
            'Hallucination_Rate': f'{hallucination_rate:.2f}%',
            'Validator_Fix_Rate': f'{validator_fix_rate:.1f}%',
            'R_H': f'{rh:.2f}%'
        })

# 輸出表格
print('='*100)
print('Table: R_H 與幻覺率分析 (gemma3_4b)')
print('='*100)
print()
print(f'{"Group":<10} {"N_active":<10} {"嘗試違規":<12} {"驗證器修復":<12} {"洩漏":<8} {"Parse錯誤":<10} {"幻覺率":<12} {"修復率":<15} {"R_H":<10}')
print('-'*100)
for r in results:
    print(f'{r["Group"]:<10} {r["N_active"]:<10} {r["Total_Attempts"]:<12} {r["Retry_Success"]:<12} {r["Retry_Exhausted"]:<8} {r["Parse_Errors"]:<10} {r["Hallucination_Rate"]:<12} {r["Validator_Fix_Rate"]:<15} {r["R_H"]:<10}')

print()
print('='*100)
print('指標說明:')
print('  嘗試違規 (Total Attempts): LLM 產生的違規決策總數')
print('  驗證器修復 (Retry Success): 經過重試後成功修正的數量')
print('  洩漏 (Retry Exhausted): 重試後仍然失敗，最終洩漏的數量')
print('  幻覺率 = 嘗試違規 / N_active（體現 LLM 原始錯誤率）')
print('  修復率 = 驗證器修復 / 嘗試違規（體現驗證器效果）')
print('  R_H = 洩漏 / N_active（最終真正的錯誤率）')
print('='*100)
