import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
from matplotlib.lines import Line2D

# =========================
# Publication-grade styling
# =========================
# =========================
# Publication-grade styling
# =========================
# Initialize Seaborn FIRST
sns.set_theme(style="white", rc={
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "pdf.fonttype": 42,
    "ps.fonttype": 42
})

# Then fine-tune params that might not be covered by set_theme
plt.rcParams.update({
    "font.size": 16,
    "axes.labelsize": 18,
    "axes.titlesize": 20,
    "legend.fontsize": 15,
    "legend.title_fontsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14
})

def plot_lifespan():

    csv_path = r"examples/single_agent/analysis/SQ2_Final_Results/yearly_entropy_audited.csv"
    out_dir  = r"examples/single_agent/analysis/SQ2_Final_Results"
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"{csv_path} not found")

    df = pd.read_csv(csv_path)

    # Rename Models for Publication
    name_map = {
        'deepseek_r1_1_5b': 'DeepSeek R1 (1.5B)',
        'deepseek_r1_8b':   'DeepSeek R1 (8B)',
        'deepseek_r1_14b':  'DeepSeek R1 (14B)',
        'deepseek_r1_32b':  'DeepSeek R1 (32B)'
    }
    df['Model'] = df['Model'].map(name_map)

    # =========================
    # Semantic color definitions
    # =========================
    group_palette = {
        "Group_A": "#b22222",  # dark red — collapse
        "Group_B": "#1f77b4",  # blue — governed
        "Group_C": "#2ca02c"   # green — natural/contextual
    }

    model_palette = {
        "DeepSeek R1 (1.5B)": "#8c2d04",
        "DeepSeek R1 (8B)":   "#d94801",
        "DeepSeek R1 (14B)":  "#238b45",
        "DeepSeek R1 (32B)":  "#08519c"
    }

    # =====================================================
    # PLOT 1 — Governance Effect (Facet by Model)
    # =====================================================
    g = sns.relplot(
        data=df,
        x="Year",
        y="Shannon_Entropy_Norm",
        col="Model",
        col_wrap=2,
        kind="line",
        palette=group_palette,
        hue="Group",            # Explicitly added hue
        style="Group",          # Explicitly added style matches hue
        linewidth=3.0,          # Thicker lines
        height=4.5,             # Larger plots
        aspect=1.3,
        legend=False            # No external legend
    )

    g.set_titles("{col_name}", weight="bold") # Cleaner title (just model name)
    g.set_axis_labels("Simulation Year", "Standardized Diversity (H_norm)")
    g.set(
        ylim=(-0.05, 1.05),      # Normalized range
        xlim=(0.5, 10.5),
        yticks=[0, 0.2, 0.4, 0.6, 0.8, 1.0]
    )

    # Custom Legend Construction for Groups
    legend_elements = [
        Line2D([0], [0], color=group_palette['Group_A'], lw=3, label='Group A'),
        Line2D([0], [0], color=group_palette['Group_B'], lw=3, label='Group B'),
        Line2D([0], [0], color=group_palette['Group_C'], lw=3, label='Group C')
    ]

    g.axes.flat[0].legend(
        handles=legend_elements,
        loc='upper right', title="Condition",
        frameon=True, framealpha=1.0, facecolor='white', edgecolor='black',
        fontsize=14, title_fontsize=15
    )

    # Subplot labels
    subplot_labels = ['(a)', '(b)', '(c)', '(d)']

    for i, ax in enumerate(g.axes.flat):
        if i < len(subplot_labels):
            # Place label in top-left corner (scientific standard)
            # transform=ax.transAxes ensures it stays in relative position
            ax.text(-0.05, 1.05, subplot_labels[i], transform=ax.transAxes,
                    fontsize=20, fontweight='bold', va='bottom', ha='right', family='serif')

        ax.axhline(0, color="black", lw=1.2, alpha=0.3)
        ax.axhline(1.0, color="gray", lw=1.2, ls=":", alpha=0.8)
        ax.grid(axis="y", alpha=0.15)
        # Ticks enabled
        ax.tick_params(bottom=True, left=True)


    # g._legend.set_title("Governance condition")
    g.savefig(
        os.path.join(out_dir, "lifespan_by_model.png"),
        dpi=600,
        bbox_inches="tight"
    )

    # =====================================================
    # PLOT 2 — Scaling Law (Facet by Group)
    # =====================================================
    h = sns.relplot(
        data=df,
        x="Year",
        y="Shannon_Entropy",
        col="Group",
        col_wrap=3,
        kind="line",
        palette=model_palette,
        hue="Model",            # Explicitly added hue
        style="Model",          # Explicitly added style matches hue
        linewidth=3.0,
        height=4.5,
        aspect=1.15,
        legend=False            # No external legend
    )

    h.set_titles("Condition: {col_name}", weight="bold")
    h.set_axis_labels("Simulation Year", "Diversity (Shannon Entropy)")
    h.set(
        ylim=(-0.05, 2.3),
        xlim=(1, 10.5),
        yticks=[0, 0.5, 1.0, 1.5, 2.0]
    )

    # Custom Legend Construction for Models
    model_legend_elements = [
        Line2D([0], [0], color=model_palette['DeepSeek R1 (1.5B)'], lw=3, label='DeepSeek R1 (1.5B)'),
        Line2D([0], [0], color=model_palette['DeepSeek R1 (8B)'],   lw=3, label='DeepSeek R1 (8B)'),
        Line2D([0], [0], color=model_palette['DeepSeek R1 (14B)'],  lw=3, label='DeepSeek R1 (14B)'),
        Line2D([0], [0], color=model_palette['DeepSeek R1 (32B)'],  lw=3, label='DeepSeek R1 (32B)')
    ]

    h.axes.flat[0].legend(
        handles=model_legend_elements,
        loc='upper right', title="Model Scale",
        frameon=True, framealpha=1.0, facecolor='white', edgecolor='black',
        fontsize=14, title_fontsize=15
    )

    for ax in h.axes.flat:
        ax.axhline(0, color="black", lw=1.2, alpha=0.3)
        ax.axhline(1.0, color="gray", lw=1.2, ls=":", alpha=0.8)
        ax.grid(axis="y", alpha=0.15)
        ax.tick_params(bottom=True, left=True)

    # h._legend.set_title("Model scale")
    h.savefig(
        os.path.join(out_dir, "lifespan_by_group.png"),
        dpi=600,
        bbox_inches="tight"
    )

    print("✓ Paper-ready figures exported")

if __name__ == "__main__":
    plot_lifespan()
