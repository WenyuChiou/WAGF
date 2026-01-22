import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Configuration
RESULTS_DIR = Path(r"results/BENCHMARK_2026")
OUTPUT_DIR = Path(r"C:\Users\wenyu\.gemini\antigravity\brain\0eefc59d-202e-4d45-bd10-0806e60c7837")
MODELS = ["deepseek_r1_8b"] # Add more as data comes in
GROUP_LABELS = {
    "Group_A": "Naive (Cognitive Ceiling)",
    "Group_B": "Gov Only (Governance Tax)",
    "Group_C": "Governed + Mem (Cognitive Subsidy)"
}

def analyze_population_states(model, group):
    log_path = RESULTS_DIR / model / group / "Run_1" / "simulation_log.csv"
    if not log_path.exists():
        return None
    
    df = pd.read_csv(log_path)
    # Ensure booleans
    for col in ['elevated', 'relocated', 'has_insurance']:
        df[col] = df[col].astype(str).str.lower() == 'true'
    
    # State per year
    yearly_stats = []
    for yr in range(1, 11):
        yr_data = df[df['year'] == yr]
        if yr_data.empty: continue
        
        relocated = yr_data['relocated'].sum()
        # Resilient = elevated OR insured (and NOT relocated)
        resilient = yr_data[~yr_data['relocated']][(yr_data['elevated']) | (yr_data['has_insurance'])].shape[0]
        # Fragile = neither elevated nor insured (and NOT relocated)
        fragile = yr_data[~yr_data['relocated']][(~yr_data['elevated']) & (~yr_data['has_insurance'])].shape[0]
        
        total = relocated + resilient + fragile
        yearly_stats.append({
            'Year': yr,
            'Fragile': fragile / total * 100,
            'Resilient': resilient / total * 100,
            'Relocated': relocated / total * 100
        })
    
    return pd.DataFrame(yearly_stats)

def plot_behavior_stacks():
    for model in MODELS:
        fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
        
        for i, (group, label) in enumerate(GROUP_LABELS.items()):
            df_states = analyze_population_states(model, group)
            if df_states is None: continue
            
            ax = axes[i]
            # Stacked Area Chart
            ax.stackplot(df_states['Year'], 
                         df_states['Fragile'], df_states['Resilient'], df_states['Relocated'],
                         labels=['At Risk', 'Protected', 'Relocated'],
                         colors=["#FFD166", "#118AB2", "#EF476F"], alpha=0.8)
            
            ax.set_title(label, fontsize=14, fontweight='bold')
            ax.set_xlabel("Simulation Year")
            if i == 0: ax.set_ylabel("Population %")
            ax.set_ylim(0, 100)
            ax.set_xlim(1, 10)
            ax.grid(axis='y', linestyle='--', alpha=0.5)

        plt.suptitle(f"Behavioral Evolution: {model.upper()} across ABC Groups", fontsize=18, fontweight='bold', y=1.05)
        plt.tight_layout()
        
        save_path = OUTPUT_DIR / f"{model}_behavior_evolution.png"
        plt.savefig(save_path, dpi=200, bbox_inches='tight')
        print(f"Saved behavioral stack for {model} to {save_path}")

if __name__ == "__main__":
    plot_behavior_stacks()
