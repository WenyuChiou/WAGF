"""
Generate Fig 1: WAGF Framework Diagram for Nature Water.

Single panel: High-level simulation loop (Agent Population → Institutional
Governance → Simulation Engine → Environmental Context) with 3 example
water-policy rules shown inside the Institutional Governance box.
One rule (demand ceiling) is highlighted as the A1 ablation target.

Style: Nature Water conventions — minimal, white background, sans-serif,
       blue (#2166AC) for governance, grey elsewhere.

Usage:
    python gen_framework_fig.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from pathlib import Path

# ── Colours & fonts ──────────────────────────────────────────────────
BLUE = "#2166AC"
BLUE_LIGHT = "#D1E5F0"
GREY = "#F0F0F0"
GREY_BORDER = "#888888"
BLACK = "#333333"
WHITE = "#FFFFFF"
RED_ACCENT = "#B2182B"
RED_FILL = "#FFF5F5"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7,
    "axes.linewidth": 0.5,
    "text.color": BLACK,
})

# ── Figure setup (180 mm ≈ 7.09 in, height halved to ~4.5 in) ────────
fig = plt.figure(figsize=(7.09, 4.5), dpi=300)
fig.patch.set_facecolor(WHITE)

# Single panel occupies full canvas with narrow margins
ax = fig.add_axes([0.02, 0.10, 0.96, 0.88])
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.set_aspect("equal")
ax.axis("off")


# ── Helper: rounded box ─────────────────────────────────────────────
def draw_box(ax, x, y, w, h, title, subtitle=None,
             facecolor=GREY, edgecolor=BLACK, linewidth=0.8,
             linestyle="-", title_size=7.5, subtitle_size=6,
             title_weight="bold", title_color=BLACK, pad=0.15):
    """Draw a rounded-rectangle box with title and optional subtitle."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad={pad}",
        facecolor=facecolor, edgecolor=edgecolor,
        linewidth=linewidth, linestyle=linestyle,
        zorder=2, transform=ax.transData,
    )
    ax.add_patch(box)
    cy = y + h / 2
    if subtitle:
        # Adaptive vertical offset based on box height
        t_off = min(0.22, h * 0.17)
        ax.text(x + w / 2, cy + t_off, title,
                ha="center", va="center", fontsize=title_size,
                fontweight=title_weight, color=title_color, zorder=3)
        ax.text(x + w / 2, cy - t_off, subtitle,
                ha="center", va="center", fontsize=subtitle_size,
                color="#555555", style="italic", zorder=3)
    else:
        ax.text(x + w / 2, cy, title,
                ha="center", va="center", fontsize=title_size,
                fontweight=title_weight, color=title_color, zorder=3)
    return box


def draw_arrow(ax, xy_start, xy_end, label=None, color=BLACK,
               linewidth=1.0, linestyle="-", connectionstyle="arc3,rad=0",
               label_offset=(0, 0), label_size=6, shrinkA=8, shrinkB=8,
               zorder=1, label_color=BLACK, label_bg=WHITE):
    """Draw a curved arrow with optional label."""
    arrow = FancyArrowPatch(
        xy_start, xy_end,
        arrowstyle="-|>",
        color=color, linewidth=linewidth, linestyle=linestyle,
        connectionstyle=connectionstyle,
        shrinkA=shrinkA, shrinkB=shrinkB,
        mutation_scale=10, zorder=zorder,
        transform=ax.transData,
    )
    ax.add_patch(arrow)
    if label:
        mx = (xy_start[0] + xy_end[0]) / 2 + label_offset[0]
        my = (xy_start[1] + xy_end[1]) / 2 + label_offset[1]
        ax.text(mx, my, label, ha="center", va="center",
                fontsize=label_size, color=label_color,
                bbox=dict(boxstyle="round,pad=0.15", fc=label_bg,
                          ec="none", alpha=0.9),
                zorder=4)
    return arrow


# =====================================================================
# SINGLE PANEL: Simulation loop with rule examples
# =====================================================================

# Box dimensions — 4 boxes arranged clockwise: top, right, bottom, left
bw, bh = 3.0, 1.3   # standard box width, height

# ── Four loop boxes ──────────────────────────────────────────────────

# Agent Population — top centre
ax_top = 5.0 - bw / 2
ay_top = 7.8
draw_box(ax, ax_top, ay_top, bw, bh,
         "Agent Population",
         "Natural-language reasoning\n78 irrigators or 100 households",
         facecolor=GREY)

# Institutional Governance — right (taller to accommodate rule examples)
gov_w = 3.4
gov_h = 3.6   # taller to hold rule sub-boxes
ax_right = 7.5
ay_right = 5.0 - gov_h / 2
draw_box(ax, ax_right, ay_right, gov_w, gov_h,
         "",   # title drawn manually below so we can position it precisely
         facecolor=BLUE_LIGHT, edgecolor=BLUE, linewidth=1.2,
         pad=0.12)

# Governance box title — pinned near top of box
ax.text(ax_right + gov_w / 2, ay_right + gov_h - 0.32,
        "Institutional Governance",
        ha="center", va="center", fontsize=7.5,
        fontweight="bold", color=BLUE, zorder=3)

# ── Rule example sub-boxes inside Governance box ──────────────────────
# Stacked vertically, centred inside the governance box.
# Layout: title pinned to top row, then 3 rule chips below.

rule_w = 2.8
rule_h = 0.68
rule_gap = 0.15
rule_x = ax_right + (gov_w - rule_w) / 2   # horizontally centred

# Start stacking rules from just below the title
rules_top = ay_right + gov_h - 0.72

rules = [
    # (label, is_ablation_target)
    ("Demand ceiling:\nblocks increases above 6.0 MAF", True),
    ("Shortage-tier curtailment\n(pro-rata)", False),
    ("Rate-of-change limit (±15%/yr)", False),
]

rule_positions = []
for i, (rule_text, is_ablation) in enumerate(rules):
    ry = rules_top - i * (rule_h + rule_gap) - rule_h
    rule_positions.append(ry)

    if is_ablation:
        # Highlighted chip: dashed red border, tinted fill
        chip = FancyBboxPatch(
            (rule_x, ry), rule_w, rule_h,
            boxstyle="round,pad=0.08",
            facecolor=RED_FILL, edgecolor=RED_ACCENT,
            linewidth=1.0, linestyle="--",
            zorder=4, transform=ax.transData,
        )
        ax.add_patch(chip)
        ax.text(rule_x + rule_w / 2, ry + rule_h / 2,
                rule_text,
                ha="center", va="center", fontsize=5.5,
                color=RED_ACCENT, fontweight="bold", zorder=5)
        # Small "A1 ablation" tag in top-right corner of chip
        ax.text(rule_x + rule_w - 0.06, ry + rule_h - 0.06,
                "A1",
                ha="right", va="top", fontsize=4.5,
                color=RED_ACCENT, fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.06",
                          fc=RED_FILL, ec=RED_ACCENT,
                          linewidth=0.5, alpha=0.9))
    else:
        # Normal rule chip: solid border, plain grey fill
        chip = FancyBboxPatch(
            (rule_x, ry), rule_w, rule_h,
            boxstyle="round,pad=0.08",
            facecolor=WHITE, edgecolor=BLUE,
            linewidth=0.6, linestyle="-",
            zorder=4, transform=ax.transData,
        )
        ax.add_patch(chip)
        ax.text(rule_x + rule_w / 2, ry + rule_h / 2,
                rule_text,
                ha="center", va="center", fontsize=5.5,
                color=BLACK, zorder=5)

# Simulation Engine — bottom centre
ax_bot = 5.0 - bw / 2
ay_bot = 1.8
draw_box(ax, ax_bot, ay_bot, bw, bh,
         "Simulation Engine",
         "Reservoir model / flood hazard\nMass balance, shortage tiers",
         facecolor=GREY)

# Environmental Context — left
ax_left = -0.6
ay_left = 5.0 - bh / 2
draw_box(ax, ax_left, ay_left, bw, bh,
         "Environmental Context",
         "Drought index, water rights,\nneighbour decisions",
         facecolor=GREY)


# ── Arrows (clockwise around the loop) ───────────────────────────────

# Agent → Broker (top-right corner → governance box top)
draw_arrow(ax,
           (ax_top + bw, ay_top + bh / 2),
           (ax_right, ay_right + gov_h),
           label="Proposed action\n+ reasoning",
           connectionstyle="arc3,rad=0.15",
           label_offset=(0.15, 0.3), shrinkA=12, shrinkB=12)

# Broker → Simulation (governance box bottom → bottom-right corner)
draw_arrow(ax,
           (ax_right + gov_w / 2, ay_right),
           (ax_bot + bw, ay_bot + bh),
           label="Validated\naction",
           connectionstyle="arc3,rad=0.15",
           label_offset=(0.2, 0.1), shrinkA=12, shrinkB=12)

# Simulation → Environmental Context (bottom-left → left box bottom)
draw_arrow(ax,
           (ax_bot, ay_bot + bh / 2),
           (ax_left + bw, ay_left),
           label="Updated\nstate",
           connectionstyle="arc3,rad=0.15",
           label_offset=(-0.15, 0.15), shrinkA=12, shrinkB=12)

# Environmental Context → Agent (left box top → top-left corner)
draw_arrow(ax,
           (ax_left + bw / 2, ay_left + bh),
           (ax_top, ay_top),
           label="Decision\ncontext",
           connectionstyle="arc3,rad=0.15",
           label_offset=(-0.3, 0.4), shrinkA=12, shrinkB=12)

# ── Dashed retry arrow: Governance → Agent ───────────────────────────
draw_arrow(ax,
           (ax_right + 0.3, ay_right + gov_h),
           (ax_top + bw - 0.3, ay_top),
           label="Retry\n(violated rule)",
           color=RED_ACCENT, linestyle="--", linewidth=0.8,
           connectionstyle="arc3,rad=-0.25",
           label_offset=(0.65, -0.05), label_size=5.5,
           shrinkA=10, shrinkB=10, label_color=RED_ACCENT)


# ── Subtitle at the bottom of the figure ─────────────────────────────
fig.text(
    0.5, 0.04,
    "Each time step: agents propose water-use actions; institutional rules validate proposals "
    "against physical and policy constraints;\nthe simulation executes validated actions and "
    "returns updated environmental signals.",
    ha="center", va="center", fontsize=5.5, color="#666666",
    style="italic", transform=fig.transFigure,
)


# ── Save ─────────────────────────────────────────────────────────────
out_dir = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
               r"\paper\nature_water\figures")
out_dir.mkdir(parents=True, exist_ok=True)

png_path = out_dir / "Fig1_framework.png"
pdf_path = out_dir / "Fig1_framework.pdf"

fig.savefig(str(png_path), dpi=300, bbox_inches="tight",
            facecolor=WHITE, edgecolor="none")
fig.savefig(str(pdf_path), bbox_inches="tight",
            facecolor=WHITE, edgecolor="none")
plt.close(fig)

print(f"Saved: {png_path}")
print(f"Saved: {pdf_path}")
