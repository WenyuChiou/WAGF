
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path
import seaborn as sns

# Data Hardcoded from "Verified" Analysis (to ensure consistency across runs)
# Final Validated Data:
data = {
    'Gemma 3': {
        'Group A': {'Adapt': 28.6, 'Retries': 0, 'GapRate': 0.0, 'TotalSteps': 0},
        'Group B': {'Adapt': 87.7, 'Retries': 0, 'GapRate': 0.27, 'TotalSteps': 8587},
        'Group C': {'Adapt': 86.6, 'Retries': 1, 'GapRate': 0.30, 'TotalSteps': 8245}
    },
    'Llama 3.2': {
        'Group A': {'Adapt': 100.0, 'Retries': 0, 'GapRate': 0.0, 'TotalSteps': 0},
        'Group B': {'Adapt': 99.8, 'Retries': 1673, 'GapRate': 0.83, 'TotalSteps': 3845},
        'Group C': {'Adapt': 99.5, 'Retries': 1118, 'GapRate': 0.83, 'TotalSteps': 2890}
    }
}

OUTPUT_DIR = Path("c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/analysis_tools/analysis/reports/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def setup_plot_style():
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({'font.size': 12, 'figure.dpi': 300})

def plot_composite_error():
    # Chart 1: The "Composite Error" (Reliability)
    # Stacked Bar: Noisy Failures (Retries per 100 steps) + Silent Failures (Gap Rate %)
    
    models = ['Gemma 3', 'Llama 3.2']
    groups = ['Group B', 'Group C']
    
    # Prepare Data
    # Normalize Retries to "Rate %" (Retries / Total Actions * 100) to match Gap Rate scale
    # Note: Retries are technically 'extra' attempts, so Rate = Retries / Steps * 100 is fair proxy
    
    rows = []
    for m in models:
        for g in groups:
            d = data[m][g]
            retry_rate = (d['Retries'] / d['TotalSteps'] * 100) if d['TotalSteps'] > 0 else 0
            silent_rate = d['GapRate']
            rows.append({
                'Model': m,
                'Group': g,
                'Noisy Failures (Retries)': retry_rate,
                'Silent Failures (Gaps)': silent_rate
            })
    
    df = pd.DataFrame(rows)
    df = df.melt(id_vars=['Model', 'Group'], var_name='Error Type', value_name='Error Rate (%)')
    
    # Plot
    plt.figure(figsize=(10, 6))
    
    # Custom Palette
    colors = {"Noisy Failures (Retries)": "#FF6B6B", "Silent Failures (Gaps)": "#4ECDC4"}
    
    # We want grouped stacked bars. Since seaborn doesn't do "grouped stacked" easily,
    # let's just do faceted plots or side-by-side. 
    # Actually, Llama is the main story. Let's plot Llama B vs C specifically.
    
    llama_df = df[df['Model'] == 'Llama 3.2']
    
    # Create Stacked Bar for Llama
    # Pivot for stacking
    pivot_df = llama_df.pivot(index='Group', columns='Error Type', values='Error Rate (%)')
    pivot_df = pivot_df[['Noisy Failures (Retries)', 'Silent Failures (Gaps)']] # Order
    
    ax = pivot_df.plot(kind='bar', stacked=True, color=[colors[c] for c in pivot_df.columns], figsize=(8, 6))
    
    plt.title('Llama 3.2 Reliability Profile: Group B vs C', fontsize=14, fontweight='bold')
    plt.ylabel('Error Rate (% of Total Steps)', fontsize=12)
    plt.xlabel('Experimental Group', fontsize=12)
    plt.xticks(rotation=0)
    plt.legend(title='Failure Mode')
    
    # Annotate
    for c in ax.containers:
        ax.bar_label(c, fmt='%.2f%%', label_type='center', color='black', fontsize=10, weight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "llama_composite_error.png")
    print("Generated composite error plot.")

def plot_adaptation_comparison():
    # Chart 2: Adaptation Saturation
    # Comparing Adaptation Rates across all groups
    
    rows = []
    for m in data.keys():
        for g in ['Group A', 'Group B', 'Group C']:
            rows.append({'Model': m, 'Group': g, 'Adaptation Rate (%)': data[m][g]['Adapt']})
            
    df = pd.DataFrame(rows)
    
    plt.figure(figsize=(10, 6))
    ax = sns.barplot(data=df, x='Model', y='Adaptation Rate (%)', hue='Group', palette="viridis")
    
    plt.title('Adaptation Rate by Model and Governance Tier', fontsize=14, fontweight='bold')
    plt.ylim(0, 110)
    plt.ylabel('Adaptation Rate (%)')
    
    for c in ax.containers:
        ax.bar_label(c, fmt='%.1f%%', padding=3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "adaptation_comparison.png")
    print("Generated adaptation comparison plot.")

if __name__ == "__main__":
    setup_plot_style()
    plot_composite_error()
    plot_adaptation_comparison()
