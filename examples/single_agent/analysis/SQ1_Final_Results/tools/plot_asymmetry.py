
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", type=str, default="results/JOH_FINAL")
    args = parser.parse_args()

    apply_publication_style()
    
    # Load Data
    path = os.path.join(args.base_dir, "metrics", "mcc_analysis_all.csv")
    if not os.path.exists(path):
        print(f"Data not found: {path}. Run analysis first.")
        return
        
    df = pd.read_csv(path)
    
    # Filter for relevant models
    df = df[df['Model'].isin(['gemma3_4b', 'llama3_2_3b'])]
    
    # Clean Model Names for Display
    df['Model'] = df['Model'].replace({
        'llama3_2_3b': 'Llama 3.2 3B',
        'gemma3_4b': 'Gemma 3 4B'
    })
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    
    # Cohort Mapping for Legend
    group_rename = {
        'Group_A': 'Cohort A (Naive)',
        'Group_B': 'Cohort B (Governed)',
        'Group_C': 'Cohort C (Cognitive)'
    }
    df['Group'] = df['Group'].map(group_rename)

    # 1. Panic Rate (Red Palette)
    ax1 = axes[0]
    sns.barplot(x='Model', y='Panic_Rate', hue='Group', data=df, ax=ax1, 
                palette=['#e74c3c', '#fab1a0', '#2ecc71'], capsize=0.1, errorbar=('ci', 95)) 
    ax1.set_title('Type I Error: Panic Rate\n(Unnecessary Action)', fontweight='bold')
    ax1.set_ylabel('False Positive Rate')
    ax1.set_ylim(0, 1.05)
    ax1.axhline(0.05, color='black', linestyle='--', alpha=0.3)
    ax1.text(-0.4, 0.06, 'Target < 5%', color='gray', fontsize=12)
    ax1.legend(title='Cohort', loc='upper right')
    
    # 2. Complacency Rate (Blue Palette)
    ax2 = axes[1]
    sns.barplot(x='Model', y='Complacency_Rate', hue='Group', data=df, ax=ax2, 
                palette=['#3498db', '#74b9ff', '#2ecc71'], capsize=0.1, errorbar=('ci', 95))
    ax2.set_title('Type II Error: Complacency Rate\n(Rationalizing Inaction)', fontweight='bold')
    ax2.set_ylabel('False Negative Rate')
    ax2.set_ylim(0, 1.05)
    ax2.axhline(0.05, color='black', linestyle='--', alpha=0.3)
    ax2.legend(title='Cohort', loc='upper right')
    
    sns.despine()
    plt.tight_layout()
    
    plots_dir = os.path.join(args.base_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    out_path = os.path.join(plots_dir, "Figure_6_Asymmetry.png")
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved Figure_6_Asymmetry.png to {out_path}")

if __name__ == "__main__":
    plot_asymmetry()
