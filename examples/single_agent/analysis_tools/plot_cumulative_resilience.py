import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Configuration
RESULTS_DIR = Path(r"results/BENCHMARK_2026")
OUTPUT_DIR = Path(r"C:\Users\wenyu\.gemini\antigravity\brain\0eefc59d-202e-4d45-bd10-0806e60c7837")
MODELS = ["deepseek_r1_8b"]
GROUP_LABELS = {
    "Group_A": "Naive (Amnesia)",
    "Group_B": "Gov Only (Mechanical)",
    "Group_C": "Synergy (Ratchet)"
}

def analyze_model(model):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    for group, label in GROUP_LABELS.items():
        log_path = RESULTS_DIR / model / group / "Run_1" / "simulation_log.csv"
        if not log_path.exists(): continue
        
        df = pd.read_csv(log_path)
        # Bools
        for col in ['elevated', 'relocated', 'has_insurance']:
            df[col] = df[col].astype(str).str.lower() == 'true'
        
        # 1. Cumulative Resilience Curve
        cumulative_counts = []
        acting_agents = set()
        for yr in range(1, 11):
            yr_data = df[df['year'] == yr]
            new_actors = yr_data[(yr_data['elevated']) | (yr_data['has_insurance'])]['agent_id'].unique()
            acting_agents.update(new_actors)
            cumulative_counts.append(len(acting_agents))
        
        ax1.plot(range(1, 11), cumulative_counts, marker='o', label=label, linewidth=2)
        
        # 2. Theoretical Trajectory (Threat Perception)
        # Note: We need a heuristic to map Group A text to 1-5 or use a numeric proxy
        # For this plot, we use the 'threat_appraisal' extraction if it was done during log generation
        # (Assuming the benchmark script extracts a numeric score or we proxy it via Keyword density)
        # As a fallback for this script, we'll use a mocked placeholder if numeric isn't found
        # In our real benchmark, the auditor should have saved a 'threat_score' column.
        if 'threat_score' in df.columns:
            yearly_threat = df.groupby('year')['threat_score'].mean()
            ax2.plot(yearly_threat.index, yearly_threat.values, marker='s', linestyle='--', label=label)
        else:
            # Fallback for now: Semantic Density as a proxy for engagement
            df['threat_len'] = df['threat_appraisal'].str.len()
            yearly_len = df.groupby('year')['threat_len'].mean()
            ax2.plot(yearly_len.index, yearly_len.values, marker='s', linestyle='--', label=f"{label} (Density)")

    # Formatting Ax1
    ax1.set_title("Cumulative Resilience Adoption", fontsize=14, fontweight='bold')
    ax1.set_xlabel("Simulation Year")
    ax1.set_ylabel("Total Unique Agents Protected")
    ax1.legend()
    ax1.grid(alpha=0.3)
    
    # Formatting Ax2
    ax2.set_title("Theoretical Trajectory (Cognitive Stability)", fontsize=14, fontweight='bold')
    ax2.set_xlabel("Simulation Year")
    ax2.set_ylabel("Mean Perception Score / Density")
    ax2.legend()
    ax2.grid(alpha=0.3)
    
    plt.suptitle(f"Longitudinal Impact: {model.upper()} Architecture Analysis", fontsize=18, y=1.02)
    plt.tight_layout()
    
    save_path = OUTPUT_DIR / f"{model}_longitudinal_analysis.png"
    plt.savefig(save_path, dpi=200, bbox_inches='tight')
    print(f"Longitudinal analysis saved to {save_path}")

if __name__ == "__main__":
    analyze_model("deepseek_r1_8b")
