import json
from pathlib import Path
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

def pmt_label_to_score(label):
    """Converts a PMT label (VL, L, M, H, VH) to a numerical score."""
    if not isinstance(label, str):
        return np.nan
    label = label.strip().upper()
    score_map = {
        "VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5
    }
    return score_map.get(label, np.nan)

def analyze_pmt_decision_correlation(traces_dir: Path, output_path: Path):
    """
    Analyzes the correlation between PMT constructs and agent decisions,
    generating a heatmap of mean PMT scores for each decision type.
    """
    records = []
    for trace_file in traces_dir.glob('household_*_traces.jsonl'):
        with open(trace_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    trace = json.loads(line)
                    decision = trace.get('approved_skill', {}).get('skill_name')
                    if not decision: continue

                    skill_proposal = trace.get('skill_proposal')
                    reasoning = skill_proposal.get('reasoning', {}) if skill_proposal else {}
                    
                    record = {'decision': decision}
                    pmt_keys = {
                        "TP_LABEL": "threat_perception", "CP_LABEL": "coping_perception",
                        "SP_LABEL": "stakeholder_perception", "SC_LABEL": "social_capital",
                        "PA_LABEL": "place_attachment"
                    }

                    for pmt_key, fallback_key in pmt_keys.items():
                        label = reasoning.get(pmt_key)
                        if not label:
                            appraisal = reasoning.get(fallback_key)
                            if isinstance(appraisal, dict): label = appraisal.get('label')
                            elif isinstance(appraisal, str): label = appraisal
                        record[pmt_key] = pmt_label_to_score(label)
                    records.append(record)
                except json.JSONDecodeError: continue

    if not records:
        print("No valid records found to analyze.")
        return

    df = pd.DataFrame(records)
    correlation_data = df.groupby('decision').mean()
    
    print("--- PMT-Decision Correlation Analysis (Mean PMT Score per Decision) ---")
    print(correlation_data)

    plt.figure(figsize=(12, 7))
    sns.heatmap(
        correlation_data, annot=True, cmap="viridis", linewidths=.5, fmt=".2f"
    )
    plt.title("Mean PMT Construct Score by Decision Type")
    plt.ylabel("Decision")
    plt.xlabel("Protection Motivation Theory (PMT) Construct")
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path)
    print(f"\\nVisualization saved to: {output_path}")

if __name__ == "__main__":
    traces_dir = Path("examples/multi_agent/results_unified/v015_full_bg/llama3_2_3b_strict/raw")
    output_path = Path("examples/multi_agent/analysis/reports/v2_pmt_decision_heatmap.png")
    analyze_pmt_decision_correlation(traces_dir, output_path)