
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

def apply_publication_style():
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.serif'] = ['Times New Roman']
    plt.rcParams['font.size'] = 14
    plt.rcParams['axes.labelsize'] = 14
    plt.rcParams['axes.titlesize'] = 16
    plt.rcParams['xtick.labelsize'] = 12
    plt.rcParams['ytick.labelsize'] = 12
    plt.rcParams['legend.fontsize'] = 14
    plt.rcParams['figure.titlesize'] = 18

def plot_asymmetry():
    apply_publication_style()
    
    # Load Data
    path = "results/JOH_FINAL/mcc_analysis_raw.csv"
    if not os.path.exists(path):
        print("Data not found.")
        return
        
    df = pd.read_csv(path)
    
    # Filter for relevant models
    df = df[df['Model'].isin(['gemma3_4b', 'llama3_2_3b'])]
    
    # Clean Model Names for Display
    df['Model'] = df['Model'].replace({
        'llama3_2_3b': 'Llama 3.2 3B\n(Panic)',
        'gemma3_4b': 'Gemma 3 4B\n(Frozen)'
    })
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    
    # 1. Panic Rate (Red Palette)
    ax1 = axes[0]
    # capsize adds the "T" bars to error bars
    sns.barplot(x='Model', y='Panic_Rate', hue='Group', data=df, ax=ax1, 
                palette=['#d62728', '#ff9896', '#2ca02c'], capsize=0.1, errorbar=('ci', 95)) 
    ax1.set_title('Type I Error: Panic Rate\n(Action when Safe)', fontweight='bold')
    ax1.set_ylabel('False Positive Rate')
    ax1.set_ylim(0, 1.05)
    ax1.axhline(0.05, color='gray', linestyle='--', alpha=0.5)
    ax1.text(0.5, 0.06, 'Target < 5%', color='gray', ha='center', fontsize=12)
    ax1.legend(title='Cohort')
    
    # Annotate bars (Only mean value) - DISABLED FREQ USER REQUEST
    # for container in ax1.containers:
    #     # Check if container implies error bars (skip error bar containers)
    #     if isinstance(container, list): continue 
    #     ax1.bar_label(container, fmt='%.2f', padding=3, fontsize=12)

    # 2. Complacency Rate (Blue Palette)
    ax2 = axes[1]
    sns.barplot(x='Model', y='Complacency_Rate', hue='Group', data=df, ax=ax2, 
                palette=['#1f77b4', '#aec7e8', '#2ca02c'], capsize=0.1, errorbar=('ci', 95))
    ax2.set_title('Type II Error: Complacency Rate\n(Inaction when Threatened)', fontweight='bold')
    ax2.set_ylabel('False Negative Rate')
    ax2.set_ylim(0, 1.05)
    ax2.axhline(0.05, color='gray', linestyle='--', alpha=0.5)
    ax2.legend(title='Cohort')
    
    # for container in ax2.containers:
    #     if isinstance(container, list): continue
    #     ax2.bar_label(container, fmt='%.2f', padding=3, fontsize=12)
    
    sns.despine()
    plt.tight_layout()
    plt.savefig('results/JOH_FINAL/Figure_6_Asymmetry.png', dpi=300, bbox_inches='tight')
    print("Saved Figure_6_Asymmetry.png with Publication Style (Times New Roman)")

if __name__ == "__main__":
    plot_asymmetry()
