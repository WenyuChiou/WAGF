import pandas as pd
import numpy as np
import os
import re
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

# PMT Keywords for semantic complexity check
# PMT Keywords Dictionary (Grounded in Rogers' Protection Motivation Theory)
# Source: Rogers (1975), Floyd et al. (2000) - Meta-Analysis of PMT
PMT_LEXICON = {
    # 1. Threat Appraisal: Severity (How bad is it?)
    "severity": [
        "severe", "severity", "danger", "dangerous", "deadly", "catastrophe", "catastrophic", 
        "devastating", "extreme", "critical", "serious", "magnitude", "damage", "destruction", "loss"
    ],
    # 2. Threat Appraisal: Vulnerability (Am I at risk?)
    "vulnerability": [
        "vulnerable", "vulnerability", "exposed", "exposure", "risk", "risky", "likely", "likelihood", 
        "probability", "chance", "susceptible", "threat", "threaten", "flood", "water", "near"
    ],
    # 3. Coping Appraisal: Response Efficacy (Will the action work?)
    "efficacy": [
        "effective", "effectiveness", "efficacy", "work", "solution", "solve", "protect", "protection", 
        "prevent", "prevention", "mitigate", "mitigation", "safe", "safety", "secure", "benefit"
    ],
    # 4. Coping Appraisal: Self Efficacy & Cost (Can I afford it?)
    "cost": [
        "cost", "expensive", "cheap", "afford", "affordable", "price", "money", "fund", "funds", 
        "budget", "savings", "expensive", "financial", "economic"
    ]
}

# Flatten for density calculation
PMT_KEYWORDS = set(word for category in PMT_LEXICON.values() for word in category)

def count_pmt_keywords(text):
    if pd.isna(text): return 0
    text = str(text).lower()
    return sum(1 for kw in PMT_KEYWORDS if kw in text)

def analyze_format_tax(results_dir, model_name):
    print(f"\n=== Analyzing Format Tax for Model: {model_name} ===")
    
    # Paths
    base_path = Path(results_dir) / model_name.replace(":", "_").replace("-", "_").replace(".", "_")
    group_a_path = base_path / "Group_A" / "Run_1" / "simulation_log.csv"
    group_b_path = base_path / "Group_B" / "Run_1" / "simulation_log.csv"
    
    if not group_a_path.exists() or not group_b_path.exists():
        print(f" [Error] Missing Group A or B data for {model_name}")
        return
    
    # Load Data
    df_a = pd.read_csv(group_a_path)
    df_b = pd.read_csv(group_b_path)
    
    # 1. Reasoning Volume (Word Count)
    # Group A: Free text in threat_appraisal/coping_appraisal
    # Group B: JSON fields
    df_a['reasoning_len'] = df_a['threat_appraisal'].str.len() + df_a['coping_appraisal'].str.len()
    df_b['reasoning_len'] = df_b['threat_appraisal'].str.len() + df_b['coping_appraisal'].str.len()
    
    # 2. Semantic Complexity (PMT Keyword Count)
    df_a['pmt_score'] = df_a['threat_appraisal'].apply(count_pmt_keywords) + df_a['coping_appraisal'].apply(count_pmt_keywords)
    df_b['pmt_score'] = df_b['threat_appraisal'].apply(count_pmt_keywords) + df_b['coping_appraisal'].apply(count_pmt_keywords)
    
    # 3. Decision Rationality (Heuristic)
    # Does high threat appraisal lead to action?
    # For A: threat text contains "high", "severe", etc.
    # For B: threat label is H or VH
    def is_worried(row, group):
        text = str(row.get('threat_appraisal', '')).lower()
        if group == 'B':
            # In Group B, we can also extract the label if the parser worked
            return "h" in text or "vh" in text
        else:
            return any(kw in text for kw in ["high", "severe", "serious", "vulnerable"])

    def took_action(row):
        return row['decision'] != "Do Nothing"

    df_a['is_worried'] = df_a.apply(lambda r: is_worried(r, 'A'), axis=1)
    df_a['took_action'] = df_a.apply(took_action, axis=1)
    
    df_b['is_worried'] = df_b.apply(lambda r: is_worried(r, 'B'), axis=1)
    df_b['took_action'] = df_b.apply(took_action, axis=1)
    
    # Calculate "Rationality Alignment": % of worried agents who took action
    rational_a = df_a[df_a['is_worried']]['took_action'].mean()
    rational_b = df_b[df_b['is_worried']]['took_action'].mean()
    
    # Results Compilation
    stats = {
        "Metric": ["Avg Reasoning Length", "Avg PMT Score", "Rationality Alignment"],
        "Group A (Free)": [df_a['reasoning_len'].mean(), df_a['pmt_score'].mean(), rational_a],
        "Group B (JSON)": [df_b['reasoning_len'].mean(), df_b['pmt_score'].mean(), rational_b]
    }
    
    results_df = pd.DataFrame(stats)
    results_df["Tax (%)"] = (results_df["Group A (Free)"] - results_df["Group B (JSON)"]) / results_df["Group A (Free)"] * 100
    
    # Explicitly print the T_gov metric for the final report
    t_gov_density = 1 - (results_df.loc[results_df['Metric'] == 'Avg PMT Score', "Group B (JSON)"].values[0] / 
                         results_df.loc[results_df['Metric'] == 'Avg PMT Score', "Group A (Free)"].values[0])
    
    print(f"\n[Metric] Governance Tax (T_gov) based on Semantic Density: {t_gov_density:.2%}")
    
    results_df.to_csv(output_path, index=False)
    print(f"\nSaved analysis to {output_path}")

if __name__ == "__main__":
    # Focus on DeepSeek first since it's most likely to show the effect
    analyze_format_tax("results/BENCHMARK_2026", "deepseek-r1:8b")
