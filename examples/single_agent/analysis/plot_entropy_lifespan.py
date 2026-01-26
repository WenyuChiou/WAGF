import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'

def plot_lifespan():
    csv_path = r"examples/single_agent/analysis/yearly_entropy_audited.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    
    # Filter for relevant comparisons if needed, or plot all
    # Let's focus on the main narrative: 1.5B (A vs B) and 14B (Benchmark)
    
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
        linewidth=2.5,
        height=4, 
        aspect=1.5
    )
    
    # Customize titles and axes
    g.fig.suptitle("Cognitive Lifespan by Model Scale (Governance Effect)", fontsize=16, fontweight='bold', y=1.02)
    g.set_titles("{col_name}")
    g.set_ylabels("Shannon Entropy (Bits)")
    g.set(ylim=(-0.1, 2.3), xlim=(1, 10.5))
    
    # Add reference lines to each subplot
    for ax in g.axes.flat:
        ax.axhline(y=0, color='black', linewidth=1, linestyle='--')
        ax.axhline(y=1.0, color='gray', linestyle=':', alpha=0.5)
    
    output_model = r"examples/single_agent/analysis/lifespan_by_model.png"
    g.savefig(output_model, dpi=300)
    print(f"Chart saved to {output_model}")
    
    # --- PLOT 2: FACET BY GROUP (The "Scaling Law" View) ---
    # Shows how Models (1.5B vs 14B) differ within the same condition.
    
    # Define model palette
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
        linewidth=2.5,
        height=4, 
        aspect=1.2
    )

    h.fig.suptitle("Cognitive Lifespan by Condition (Scaling Law)", fontsize=16, fontweight='bold', y=1.02)
    h.set_titles("{col_name}")
    h.set_ylabels("Shannon Entropy (Bits)")
    h.set(ylim=(-0.1, 2.3), xlim=(1, 10.5))
    
    for ax in h.axes.flat:
        ax.axhline(y=0, color='black', linewidth=1, linestyle='--')
        ax.axhline(y=1.0, color='gray', linestyle=':', alpha=0.5)
        
    output_group = r"examples/single_agent/analysis/lifespan_by_group.png"
    h.savefig(output_group, dpi=300)
    print(f"Chart saved to {output_group}")

if __name__ == "__main__":
    plot_lifespan()
