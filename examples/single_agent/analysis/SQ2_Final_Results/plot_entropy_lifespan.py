import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

# Set style for Publication Quality
sns.set_theme(style="whitegrid")
sns.set_context("talk") # Larger fonts for presentation/papers
plt.rcParams['font.family'] = 'DejaVu Sans'

def plot_lifespan():
    # Input is now local in this folder, but we use relative path from root for safety
    csv_path = r"examples/single_agent/analysis/SQ2_Final_Results/yearly_entropy_audited.csv" 
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found (Expected in current directory).")
        return

    df = pd.read_csv(csv_path)
    
    # Custom palette
    palette = {
        'Group_A': '#d62728', # Red (Danger/Collapse)
        'Group_B': '#1f77b4', # Blue (Stable/Governed)
        'Group_C': '#2ca02c'  # Green (Context/Natural)
    }
    
    # --- PLOT 1: FACET BY MODEL (The "Governance Effect" View) ---
    # Shows how Governance (Group A vs B vs C) affects each specific brain size.
    
    g = sns.relplot(
        data=df,
        x="Year",
        y="Shannon_Entropy",
        hue="Group",
        col="Model",
        col_wrap=2,  # 2x2 grid
        kind="line",
        palette=palette,
        style="Group",
        markers=True,
        dashes=False,
        linewidth=3, # Thicker lines
        height=5,    # Larger charts
        aspect=1.4
    )
    
    # Beautify
    g.fig.suptitle("The Governance Effect: Cognitive Lifespan by Model Scale", fontsize=22, fontweight='bold', y=1.05)
    g.set_titles("Model: {col_name}", size=18, fontweight='bold')
    g.set_ylabels("Diversity (Entropy)", size=16, weight='bold')
    g.set_xlabels("Simulation Year", size=16, weight='bold')
    g.set(ylim=(-0.1, 2.3), xlim=(1, 10.5))
    
    # Add High-Quality Annotations to every subplot
    for ax in g.axes.flat:
        ax.axhline(y=0, color='black', linewidth=1.5, linestyle='-', alpha=0.3)
        ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=1.5, alpha=0.8)
        # Add text in a fixed position
        ax.text(1.2, 0.08, "Mode Collapse (H=0)", color='black', fontsize=12, alpha=0.6, style='italic')
        ax.text(1.2, 1.05, "Viability Threshold", color='gray', fontsize=12, alpha=0.8)
    
    output_model = "lifespan_by_model.png"
    g.savefig(output_model, dpi=300, bbox_inches='tight')
    print(f"Chart saved to {output_model}")
    
    # --- PLOT 2: FACET BY GROUP (The "Scaling Law" View) ---
    # Shows how Models (1.5B vs 14B) differ within the same condition.
    
    model_palette = {
        'deepseek_r1_1_5b': '#d62728', # Red (Weakest)
        'deepseek_r1_8b': '#ff7f0e',   # Orange
        'deepseek_r1_14b': '#2ca02c',  # Green
        'deepseek_r1_32b': '#1f77b4'   # Blue (Strongest)
    }
    
    h = sns.relplot(
        data=df,
        x="Year",
        y="Shannon_Entropy",
        hue="Model",
        col="Group",
        col_wrap=3,
        kind="line",
        palette=model_palette,
        style="Model",
        markers=True, 
        dashes=False,
        linewidth=3,
        height=5, 
        aspect=1.1
    )

    h.fig.suptitle("Scaling Laws: Cognitive Lifespan by Condition", fontsize=22, fontweight='bold', y=1.05)
    h.set_titles("Condition: {col_name}", size=18, fontweight='bold')
    h.set_ylabels("Diversity (Entropy)", size=16, weight='bold')
    h.set_xlabels("Simulation Year", size=16, weight='bold')
    h.set(ylim=(-0.1, 2.3), xlim=(1, 10.5))
    
    for ax in h.axes.flat:
        ax.axhline(y=0, color='black', linewidth=1.5, linestyle='-', alpha=0.3)
        ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=1.5, alpha=0.8)
        
    output_group = "lifespan_by_group.png"
    h.savefig(output_group, dpi=300, bbox_inches='tight')
    print(f"Chart saved to {output_group}")

if __name__ == "__main__":
    plot_lifespan()
