#!/usr/bin/env python3
"""
Architecture comparison: WRR version vs WAGF version.
Side-by-side annotated block diagram using matplotlib.

Output: paper/nature_water/professor_briefing/architecture_comparison.png
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 9,
    'figure.dpi': 200,
    'savefig.dpi': 200,
})


def draw_box(ax, x, y, w, h, text, color='#E8E8E8', edgecolor='#333333',
             fontsize=9, fontweight='normal', text_color='black', alpha=1.0):
    """Draw a rounded rectangle with centered text."""
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0.05",
                         facecolor=color, edgecolor=edgecolor,
                         linewidth=1.2, alpha=alpha, zorder=2)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text,
            ha='center', va='center', fontsize=fontsize,
            fontweight=fontweight, color=text_color, zorder=3,
            wrap=True)


def draw_arrow(ax, x1, y1, x2, y2, color='#333333', style='->', lw=1.5):
    """Draw an arrow between two points."""
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, color=color,
        linewidth=lw, mutation_scale=12, zorder=1)
    ax.add_patch(arrow)


def generate_figure():
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(12, 6))

    for ax in (ax_left, ax_right):
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.set_aspect('equal')
        ax.axis('off')

    # ═══════════════════════════════════════════════
    # LEFT PANEL: WRR Version (Group A)
    # ═══════════════════════════════════════════════
    ax_left.set_title('WRR Version (Group A)', fontsize=12, fontweight='bold',
                      color='#666666', pad=15)

    # Agent context
    draw_box(ax_left, 1, 8, 8, 1.2,
             'Agent Context\n(state, flood history, memory)',
             color='#DCEDC8', fontsize=8)

    # LLM
    draw_box(ax_left, 2.5, 5.8, 5, 1.4,
             'LLM\n(PMT prompt → prose reasoning)',
             color='#BBDEFB', fontsize=9, fontweight='bold')

    # Arrow: context → LLM
    draw_arrow(ax_left, 5, 8, 5, 7.2)

    # Direct execution (no governance!)
    draw_box(ax_left, 2.5, 3.5, 5, 1.4,
             'Direct Execution\n(action taken as-is)',
             color='#FFCCBC', fontsize=9, fontweight='bold')

    # Arrow: LLM → execution
    draw_arrow(ax_left, 5, 5.8, 5, 4.9)

    # Simulation engine
    draw_box(ax_left, 1, 1, 8, 1.8,
             'Simulation Engine\n(PRB flood model, damage functions)',
             color='#F5F5F5', fontsize=8)

    # Arrow: execution → engine
    draw_arrow(ax_left, 5, 3.5, 5, 2.8)

    # Problem annotations
    ax_left.text(8.2, 5.2, 'No validation!', fontsize=8, color='#D32F2F',
                fontweight='bold', style='italic', rotation=-15)
    ax_left.text(0.5, 5.0, 'IBR = 9.7%\n(irrational\nbehaviour)',
                fontsize=7.5, color='#D32F2F', ha='left',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFEBEE',
                          edgecolor='#D32F2F', linewidth=0.8))

    # ═══════════════════════════════════════════════
    # RIGHT PANEL: WAGF Version (Group B)
    # ═══════════════════════════════════════════════
    ax_right.set_title('WAGF Version (Group B)', fontsize=12, fontweight='bold',
                       color='#0072B2', pad=15)

    # Agent context
    draw_box(ax_right, 1, 8.5, 8, 1.0,
             'Agent Context\n(state, flood history, memory)',
             color='#DCEDC8', fontsize=8)

    # LLM
    draw_box(ax_right, 2.5, 6.5, 5, 1.2,
             'LLM\n(PMT prompt → structured output)',
             color='#BBDEFB', fontsize=9, fontweight='bold')

    # Arrow: context → LLM
    draw_arrow(ax_right, 5, 8.5, 5, 7.7)

    # GOVERNANCE PIPELINE (highlighted)
    gov_box = FancyBboxPatch((0.8, 3.8), 8.4, 2.2,
                             boxstyle="round,pad=0.1",
                             facecolor='#FFF8E1', edgecolor='#F57F17',
                             linewidth=2.5, alpha=0.9, zorder=1)
    ax_right.add_patch(gov_box)

    ax_right.text(5, 5.7, 'Governance Validator Pipeline', fontsize=9,
                 fontweight='bold', ha='center', color='#F57F17', zorder=3)

    # Validator rules
    rules = ['Schema\ncheck', 'Action\nlegal?', 'Physical\nfeasibility',
             'Institutional\ncompliance', 'Theory\nconsistency']
    rule_w = 1.35
    start_x = 0.95
    for i, rule in enumerate(rules):
        x = start_x + i * 1.6
        draw_box(ax_right, x, 4.0, rule_w, 1.3, rule,
                 color='#FFF3E0', edgecolor='#E65100', fontsize=6.5)
        if i < len(rules) - 1:
            draw_arrow(ax_right, x + rule_w, 4.65,
                      x + 1.6, 4.65, color='#E65100', lw=1.0)

    # Arrow: LLM → governance
    draw_arrow(ax_right, 5, 6.5, 5, 6.0)

    # Retry arrow (governance back to LLM)
    ax_right.annotate('', xy=(8.5, 7.1), xytext=(8.5, 5.7),
                     arrowprops=dict(arrowstyle='->', color='#D32F2F',
                                     lw=1.5, connectionstyle='arc3,rad=0.3'))
    ax_right.text(9.2, 6.4, 'Reject\n+ explain\n(retry ≤3)',
                 fontsize=6.5, color='#D32F2F', ha='left',
                 fontweight='bold')

    # Approved execution
    draw_box(ax_right, 2.5, 2, 5, 1.0,
             'Approved Execution + Audit Trail',
             color='#C8E6C9', fontsize=9, fontweight='bold',
             edgecolor='#2E7D32')

    # Arrow: governance → execution
    draw_arrow(ax_right, 5, 3.8, 5, 3.0, color='#2E7D32')
    ax_right.text(5.5, 3.4, 'PASS', fontsize=7, color='#2E7D32',
                 fontweight='bold')

    # Simulation engine
    draw_box(ax_right, 1, 0.5, 8, 1.0,
             'Simulation Engine (PRB flood / CRSS reservoir)',
             color='#F5F5F5', fontsize=8)

    # Arrow: execution → engine
    draw_arrow(ax_right, 5, 2.0, 5, 1.5)

    # Improvement annotations
    ax_right.text(0.3, 2.3, 'IBR = 0.6%\n(16× reduction)',
                 fontsize=7.5, color='#2E7D32', ha='left', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8F5E9',
                           edgecolor='#2E7D32', linewidth=0.8))

    # Improvement callouts at bottom
    improvements = [
        '1. Validator layer: IBR 9.7% → 0.6%',
        '2. Audit trail: every blocked proposal logged',
        '3. Domain-transferable: same code for flood + irrigation',
    ]
    fig.text(0.5, 0.02, '    |    '.join(improvements),
             ha='center', fontsize=8.5, fontweight='bold', color='#1565C0',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#E3F2FD',
                       edgecolor='#1565C0', linewidth=1.0))

    plt.tight_layout(rect=[0, 0.06, 1, 0.96])

    from pathlib import Path
    out_path = Path(__file__).resolve().parent / "architecture_comparison.png"
    fig.savefig(out_path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"Saved: {out_path}")
    plt.close(fig)


if __name__ == '__main__':
    generate_figure()
