"""
System Architecture Figure for Paper 3

Generates publication-quality system architecture diagram showing:
1. Stage 1: Agent Initialization (Survey → Balanced Sampler → 400 Agents)
2. Stage 2: SAGA 3-Tier Governance Simulation
3. Stage 3: Three-Level Validation Framework

Output: 300 DPI PNG/PDF for Water Resources Research submission

Usage:
    python fig_system_architecture.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import matplotlib.lines as mlines

# Setup paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Figure settings
FIGURE_SIZE = (12, 9)
DPI = 300

# Color scheme
COLORS = {
    "stage1_bg": "#E3F2FD",      # Light blue
    "stage2_bg": "#FFF3E0",      # Light orange
    "stage3_bg": "#E8F5E9",      # Light green
    "box_survey": "#1976D2",     # Blue
    "box_sampler": "#42A5F5",    # Light blue
    "box_agents": "#2196F3",     # Medium blue
    "box_gov": "#FF7043",        # Orange
    "box_ins": "#FFA726",        # Light orange
    "box_hh": "#FF9800",         # Medium orange
    "box_env": "#8D6E63",        # Brown
    "box_l1": "#66BB6A",         # Green
    "box_l2": "#43A047",         # Medium green
    "box_l3": "#2E7D32",         # Dark green
    "arrow": "#424242",          # Dark gray
    "text": "#212121",           # Near black
    "text_light": "#FFFFFF",     # White
}


def draw_rounded_box(ax, x, y, width, height, color, label, fontsize=9,
                     fontcolor="white", alpha=1.0, edgecolor=None, linewidth=1.5):
    """Draw a rounded rectangle with centered text."""
    if edgecolor is None:
        edgecolor = color

    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        facecolor=color,
        edgecolor=edgecolor,
        linewidth=linewidth,
        alpha=alpha,
        transform=ax.transAxes,
        zorder=2
    )
    ax.add_patch(box)

    # Add label
    ax.text(
        x + width / 2, y + height / 2,
        label,
        ha='center', va='center',
        fontsize=fontsize,
        fontweight='bold',
        color=fontcolor,
        transform=ax.transAxes,
        zorder=3
    )

    return box


def draw_stage_box(ax, x, y, width, height, color, title, alpha=0.3):
    """Draw a stage background box with title."""
    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.01,rounding_size=0.02",
        facecolor=color,
        edgecolor="none",
        alpha=alpha,
        transform=ax.transAxes,
        zorder=0
    )
    ax.add_patch(box)

    # Add stage title
    ax.text(
        x + 0.01, y + height - 0.02,
        title,
        ha='left', va='top',
        fontsize=10,
        fontweight='bold',
        color=COLORS['text'],
        transform=ax.transAxes,
        zorder=1
    )


def draw_arrow(ax, start, end, color=None, style='->', connectionstyle="arc3,rad=0"):
    """Draw an arrow between two points."""
    if color is None:
        color = COLORS['arrow']

    arrow = FancyArrowPatch(
        start, end,
        arrowstyle=style,
        color=color,
        linewidth=2,
        connectionstyle=connectionstyle,
        transform=ax.transAxes,
        zorder=1,
        mutation_scale=15
    )
    ax.add_patch(arrow)


def create_system_architecture_figure():
    """Create the complete system architecture figure."""
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    # Main title
    ax.text(
        0.5, 0.97,
        "LLM-Governed Multi-Agent Flood Adaptation System",
        ha='center', va='top',
        fontsize=14,
        fontweight='bold',
        color=COLORS['text'],
        transform=ax.transAxes
    )

    # =========================================================================
    # STAGE 1: Agent Initialization (top section)
    # =========================================================================
    draw_stage_box(ax, 0.02, 0.72, 0.96, 0.22, COLORS['stage1_bg'],
                   "STAGE 1: Agent Initialization")

    # Survey Data box
    draw_rounded_box(ax, 0.08, 0.76, 0.18, 0.12, COLORS['box_survey'],
                     "Survey Data\n(755 NJ HH)", fontsize=9)

    # Balanced Sampler box
    draw_rounded_box(ax, 0.35, 0.76, 0.20, 0.12, COLORS['box_sampler'],
                     "Balanced Sampler\n(4-cell MG×Tenure)", fontsize=9)

    # 400 Agents box
    draw_rounded_box(ax, 0.64, 0.76, 0.22, 0.12, COLORS['box_agents'],
                     "400 Synthetic Agents\n+ Initial Memories", fontsize=9)

    # Arrows for Stage 1
    draw_arrow(ax, (0.26, 0.82), (0.35, 0.82))
    draw_arrow(ax, (0.55, 0.82), (0.64, 0.82))

    # =========================================================================
    # STAGE 2: SAGA Simulation (middle section)
    # =========================================================================
    draw_stage_box(ax, 0.02, 0.28, 0.96, 0.42, COLORS['stage2_bg'],
                   "STAGE 2: SAGA 3-Tier Governance Simulation (13 years)")

    # Government box
    draw_rounded_box(ax, 0.08, 0.52, 0.18, 0.12, COLORS['box_gov'],
                     "Government\n(NJDEP)\nsubsidy_rate", fontsize=8)

    # Insurance box
    draw_rounded_box(ax, 0.35, 0.52, 0.18, 0.12, COLORS['box_ins'],
                     "Insurance\n(FEMA/CRS)\npremium_rate", fontsize=8)

    # Household Agents box
    draw_rounded_box(ax, 0.62, 0.52, 0.24, 0.12, COLORS['box_hh'],
                     "400 Household Agents\n(LLM decisions + PMT)\nTP/CP → Action", fontsize=8)

    # PRB Environment box
    draw_rounded_box(ax, 0.30, 0.32, 0.40, 0.10, COLORS['box_env'],
                     "PRB Flood Environment (ESRI ASCII Grid 2011-2023)", fontsize=9)

    # Arrows for Stage 2 - horizontal
    draw_arrow(ax, (0.26, 0.58), (0.35, 0.58))
    draw_arrow(ax, (0.53, 0.58), (0.62, 0.58))

    # Feedback loop arrows
    draw_arrow(ax, (0.74, 0.52), (0.74, 0.42), style='->')
    draw_arrow(ax, (0.74, 0.42), (0.70, 0.42), style='->')

    # Arrow from Stage 1 to Stage 2
    draw_arrow(ax, (0.50, 0.72), (0.50, 0.66), style='->')

    # =========================================================================
    # STAGE 3: Validation (bottom section)
    # =========================================================================
    draw_stage_box(ax, 0.02, 0.02, 0.96, 0.24, COLORS['stage3_bg'],
                   "STAGE 3: Three-Level Validation Framework")

    # L1 Micro box
    draw_rounded_box(ax, 0.08, 0.06, 0.24, 0.14, COLORS['box_l1'],
                     "L1 Micro\nCACR, R_H, EBE\n(Per-decision)", fontsize=8)

    # L2 Macro box
    draw_rounded_box(ax, 0.38, 0.06, 0.24, 0.14, COLORS['box_l2'],
                     "L2 Macro\nEPI, 8 Benchmarks\n(Aggregate)", fontsize=8)

    # L3 Cognitive box
    draw_rounded_box(ax, 0.68, 0.06, 0.24, 0.14, COLORS['box_l3'],
                     "L3 Cognitive\nICC, eta², Sensitivity\n(Pre-experiment)", fontsize=8)

    # Arrow from Stage 2 to Stage 3
    draw_arrow(ax, (0.50, 0.28), (0.50, 0.22), style='->')

    # Add annotation for experiment flow
    ax.annotate(
        '',
        xy=(0.50, 0.22),
        xytext=(0.50, 0.28),
        arrowprops=dict(arrowstyle='->', color=COLORS['arrow'], lw=2),
        transform=ax.transAxes
    )

    # Add legend/key
    legend_y = 0.95
    ax.text(0.02, legend_y, "Legend:", fontsize=8, fontweight='bold',
            transform=ax.transAxes, color=COLORS['text'])

    # Phase labels
    phase_labels = [
        ("Phase 1", COLORS['box_gov']),
        ("Phase 2", COLORS['box_ins']),
        ("Phase 3", COLORS['box_hh']),
    ]

    for i, (label, color) in enumerate(phase_labels):
        rect = Rectangle((0.08 + i * 0.08, legend_y - 0.015), 0.02, 0.015,
                          facecolor=color, transform=ax.transAxes, zorder=2)
        ax.add_patch(rect)
        ax.text(0.105 + i * 0.08, legend_y - 0.008, label, fontsize=7,
                va='center', transform=ax.transAxes, color=COLORS['text'])

    # Add model info
    ax.text(
        0.98, 0.02,
        "Model: Gemma 3 4B | Study Area: Passaic River Basin, NJ",
        ha='right', va='bottom',
        fontsize=7,
        style='italic',
        color=COLORS['text'],
        transform=ax.transAxes
    )

    plt.tight_layout()

    return fig


def main():
    """Generate and save the system architecture figure."""
    print("=" * 60)
    print("System Architecture Figure Generator")
    print("=" * 60)

    print("\n[1] Creating figure...")
    fig = create_system_architecture_figure()

    # Save PNG
    output_png = OUTPUT_DIR / "fig1_system_architecture.png"
    fig.savefig(output_png, dpi=DPI, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"Saved: {output_png}")

    # Save PDF
    output_pdf = OUTPUT_DIR / "fig1_system_architecture.pdf"
    fig.savefig(output_pdf, dpi=DPI, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"Saved: {output_pdf}")

    plt.close(fig)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
