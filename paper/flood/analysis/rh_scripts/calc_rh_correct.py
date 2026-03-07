"""
正確的 R_H 計算（根據用戶指示）:
- Group A: 使用關鍵字提取 → V1+V2+V3 實際洩漏
- Group B/C: 使用 retry_exhausted（重試後仍失敗的）
"""
import pandas as pd
import numpy as np
import json
import re
import os
from pathlib import Path

BASE = str(Path(__file__).resolve().parents[4] / 'examples' / 'single_agent' / 'results' / 'JOH_FINAL')

# PMT 關鍵字 (來自 master_report.py)
TA_KEYWORDS = {
    "H": [
        "severe", "critical", "extreme", "catastrophic", "significant harm", "dangerous", "bad", "devastating",
        "susceptible", "likely", "high risk", "exposed", "probability", "chance", "vulnerable",
        "afraid", "anxious", "worried", "concerned", "frightened", "emergency", "flee"
    ],
    "L": [
        "minimal", "safe", "none", "low", "unlikely", "no risk", "protected", "secure"
    ]
}

def map_text_to_level(text, keywords=None):
    """master_report.py 的關鍵字分類邏輯"""
    if not isinstance(text, str): return "M"
    text = text.upper()
    # Tier 1: 顯式標籤
    if re.search(r'\bVH\b', text): return "VH"
    if re.search(r'\bH\b', text): return "H"
    if re.search(r'\bVL\b', text): return "VL"
    if re.search(r'\bL\b', text): return "L"
    if re.search(r'\bM\b', text): return "M"

    # Tier 2: 關鍵字匹配
    if keywords:
        if any(w.upper() in text for w in keywords.get("H", [])): return "H"
        if any(w.upper() in text for w in keywords.get("L", [])): return "L"
    return "M"

model = 'gemma3_4b'
print('='*70)
print('R_H 正確計算（根據用戶指示）')
print('='*70)
print()
print('計算方法:')
print('  Group A: R_H = (V1 + V2 + V3 實際洩漏) / N_active')
print('  Group B/C: R_H = retry_exhausted / N_active')
print('='*70)

results = {}

for group in ['Group_A', 'Group_B', 'Group_C']:
    print(f'\n--- {group} ---')

    csv_path = os.path.join(BASE, model, group, 'Run_1', 'simulation_log.csv')
    df = pd.read_csv(csv_path)
    df.columns = [c.lower() for c in df.columns]

    # 確定 decision column 和過濾條件
    if group == 'Group_A':
        dec_col = 'decision'
        active = df[df[dec_col] != 'Already relocated'].copy()
    else:
        dec_col = 'yearly_decision'
        active = df[df[dec_col] != 'relocated'].copy()

    n_active = len(active)
    print(f'N_active = {n_active}')

    if group == 'Group_A':
        # ===== Group A: 關鍵字提取計算 V1+V2+V3 =====
        active['yearly_dec'] = active.get('raw_llm_decision', active[dec_col])

        # 從多個欄位提取文本進行關鍵字分類
        text_cols = ['threat_appraisal', 'memory']
        active['ta_text'] = active[[c for c in text_cols if c in active.columns]].fillna('').astype(str).agg(' '.join, axis=1)
        active['ta_level'] = active['ta_text'].apply(lambda x: map_text_to_level(x, TA_KEYWORDS))

        # 寬鬆閾值（因為是關鍵字推斷）
        low_threat_values = ['L', 'VL', 'M']

        # TA level 分佈
        print(f'TA level 分佈: {active["ta_level"].value_counts().to_dict()}')

        # 計算 transitions
        active_sorted = active.sort_values(['agent_id', 'year']).copy()
        active_sorted['relocated_prev'] = active_sorted.groupby('agent_id')['relocated'].shift(1).fillna(False)
        active_sorted['elevated_prev'] = active_sorted.groupby('agent_id')['elevated'].shift(1).fillna(False)

        # V1: Relocated transition under low threat
        reloc_trans = (active_sorted['relocated'] == True) & (active_sorted['relocated_prev'] == False)
        low_threat = active_sorted['ta_level'].isin(low_threat_values)
        v1 = (reloc_trans & low_threat).sum()

        # V2: Elevation transition under low threat
        elev_trans = (active_sorted['elevated'] == True) & (active_sorted['elevated_prev'] == False)
        v2 = (elev_trans & low_threat).sum()

        # V3: Do nothing under VH threat
        vh_threat = active_sorted['ta_level'] == 'VH'
        do_nothing = active_sorted['yearly_dec'].str.contains('nothing', case=False, na=False)
        v3 = (vh_threat & do_nothing).sum()

        n_leaked = v1 + v2 + v3
        rh = n_leaked / n_active * 100 if n_active > 0 else 0

        print(f'V1={v1}, V2={v2}, V3={v3}')
        print(f'N_leaked (實際洩漏) = {n_leaked}')
        print(f'R_H = {n_leaked} / {n_active} = {rh:.2f}%')

        results[group] = {'n_active': n_active, 'n_leaked': n_leaked, 'rh': rh, 'method': 'keyword'}

    else:
        # ===== Group B/C: 使用 retry_exhausted =====
        summary_path = os.path.join(BASE, model, group, 'Run_1', 'governance_summary.json')
        with open(summary_path, 'r') as f:
            summary = json.load(f)

        outcome_stats = summary.get('outcome_stats', {})
        retry_success = outcome_stats.get('retry_success', 0)
        retry_exhausted = outcome_stats.get('retry_exhausted', 0)
        parse_errors = outcome_stats.get('parse_errors', 0)
        total_interventions = summary.get('total_interventions', 0)

        print(f'Governance summary:')
        print(f'  total_interventions: {total_interventions}')
        print(f'  retry_success (成功阻擋): {retry_success}')
        print(f'  retry_exhausted (洩漏): {retry_exhausted}')
        print(f'  parse_errors: {parse_errors}')

        # R_H = retry_exhausted / N_active
        n_leaked = retry_exhausted
        rh = n_leaked / n_active * 100 if n_active > 0 else 0

        print(f'N_leaked (retry_exhausted) = {n_leaked}')
        print(f'R_H = {n_leaked} / {n_active} = {rh:.2f}%')

        results[group] = {'n_active': n_active, 'n_leaked': n_leaked, 'rh': rh, 'method': 'retry_exhausted'}

print('\n' + '='*70)
print('總結')
print('='*70)
print(f'{"Group":<10} {"N_active":<10} {"N_leaked":<10} {"R_H":<10} {"Method"}')
print('-'*70)
for g, r in results.items():
    print(f'{g:<10} {r["n_active"]:<10} {r["n_leaked"]:<10} {r["rh"]:.2f}%{"":<5} {r["method"]}')

print('\n' + '='*70)
print('對比 Table 2 預期值:')
print('  Group A: 6.9%')
print('  Group B: 6.1%')
print('  Group C: 1.9%')
print('='*70)
