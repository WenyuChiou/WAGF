"""
Generate Fig 1: WAGF Framework Diagram for Nature Water.

Panel (a): High-level simulation loop (Agent → Broker → Sim → Signals)
Panel (b): Governance pipeline detail (6-step validation)

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

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7,
    "axes.linewidth": 0.5,
    "text.color": BLACK,
})

# ── Figure setup (180 mm ≈ 7.09 in) ─────────────────────────────────
fig = plt.figure(figsize=(7.09, 9.0), dpi=300)
fig.patch.set_facecolor(WHITE)

# Two panels stacked vertically
ax_a = fig.add_axes([0.02, 0.50, 0.96, 0.48])  # panel (a) top
ax_b = fig.add_axes([0.02, 0.02, 0.96, 0.46])  # panel (b) bottom

for ax in (ax_a, ax_b):
    ax.set_xlim(0, 10)
    ax.set_aspect("equal")
    ax.axis("off")

ax_a.set_ylim(0, 10)
ax_b.set_ylim(0, 7)  # shorter y range → wider effective x space


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
# PANEL (a): Simulation loop
# =====================================================================
ax_a.text(0.15, 9.6, "(a)", fontsize=9, fontweight="bold",
          transform=ax_a.transData)

# Box positions — clockwise: top, right, bottom, left
bw, bh = 3.0, 1.3  # box width, height

# Agent Population — top centre
ax_top = 5.0 - bw / 2
ay_top = 7.8
draw_box(ax_a, ax_top, ay_top, bw, bh,
         "Agent Population",
         "Natural-language reasoning\n78 irrigators or 100 households",
         facecolor=GREY)

# Governance Broker — right
ax_right = 7.8
ay_right = 5.0 - bh / 2
draw_box(ax_a, ax_right, ay_right, bw, bh,
         "Institutional Governance",
         "Physical + institutional +\nbehavioural rules",
         facecolor=BLUE_LIGHT, edgecolor=BLUE, linewidth=1.2,
         title_color=BLUE)

# Simulation Engine — bottom centre
ax_bot = 5.0 - bw / 2
ay_bot = 1.5
draw_box(ax_a, ax_bot, ay_bot, bw, bh,
         "Simulation Engine",
         "Reservoir model / flood hazard\nMass balance, shortage tiers",
         facecolor=GREY)

# Signal Assembly — left
ax_left = -0.8
ay_left = 5.0 - bh / 2
draw_box(ax_a, ax_left, ay_left, bw, bh,
         "Environmental Context",
         "Drought index, water rights,\nneighbour decisions",
         facecolor=GREY)

# ── Arrows (clockwise) ──────────────────────────────────────────────
# Agent → Broker (top-right to right-top)
draw_arrow(ax_a,
           (ax_top + bw, ay_top + bh / 2),
           (ax_right, ay_right + bh),
           label="Proposed action\n+ reasoning",
           connectionstyle="arc3,rad=0.15",
           label_offset=(0.15, 0.35), shrinkA=12, shrinkB=12)

# Broker → Simulation (right-bottom to bottom-right)
draw_arrow(ax_a,
           (ax_right + bw / 2, ay_right),
           (ax_bot + bw, ay_bot + bh),
           label="Validated\naction",
           connectionstyle="arc3,rad=0.15",
           label_offset=(0.2, 0.1), shrinkA=12, shrinkB=12)

# Simulation → Signal Assembly (bottom-left to left-bottom)
draw_arrow(ax_a,
           (ax_bot, ay_bot + bh / 2),
           (ax_left + bw, ay_left),
           label="Updated\nstate",
           connectionstyle="arc3,rad=0.15",
           label_offset=(-0.15, 0.15), shrinkA=12, shrinkB=12)

# Signal Assembly → Agent (left-top to top-left)
draw_arrow(ax_a,
           (ax_left + bw / 2, ay_left + bh),
           (ax_top, ay_top),
           label="Decision\ncontext",
           connectionstyle="arc3,rad=0.15",
           label_offset=(-0.3, 0.4), shrinkA=12, shrinkB=12)

# ── Dashed retry arrow: Broker → Agent ──────────────────────────────
draw_arrow(ax_a,
           (ax_right + 0.3, ay_right + bh),
           (ax_top + bw - 0.3, ay_top),
           label="Retry\n(violated rule)",
           color=RED_ACCENT, linestyle="--", linewidth=0.8,
           connectionstyle="arc3,rad=-0.3",
           label_offset=(0.65, -0.05), label_size=5.5,
           shrinkA=10, shrinkB=10, label_color=RED_ACCENT)

# Subtitle for panel (a)
ax_a.text(5.0, 0.4,
          "Each time step: every agent proposes an action; "
          "institutional rules validate it;\n"
          "the simulation executes validated actions and returns updated environmental signals.",
          ha="center", va="center", fontsize=5.5, color="#666666",
          style="italic")


# =====================================================================
# PANEL (b): Governance pipeline
# =====================================================================
ax_b.text(0.15, 6.75, "(b)", fontsize=9, fontweight="bold",
          transform=ax_b.transData)

ax_b.text(5.0, 6.5, "Governance pipeline (six-step institutional rule validation)",
          ha="center", va="center", fontsize=7.5, fontweight="bold",
          color=BLUE)

# ── Pipeline steps ───────────────────────────────────────────────────
steps = [
    ("Format\ncheck", None, False),
    ("Action-vocabulary\ncheck", None, False),
    ("Physical\nfeasibility", "Mass balance,\ncapacity limits", False),
    ("Institutional\ncompliance", "Prior-appropriation\nrules, programme\neligibility", True),   # ablation
    ("Magnitude\nplausibility", "Rate-of-change\nbounds (±15 %/yr)", False),
    ("Theory\nconsistency", "Appraisal–action\nalignment", False),
]

n = len(steps)
step_w = 1.3
step_h = 1.35
gap = 0.13
total_w = n * step_w + (n - 1) * gap
x_start = (10 - total_w) / 2 + 0.25  # shift right slightly for input label
y_pipe = 3.8

# Input arrow
ax_b.annotate("", xy=(x_start - 0.05, y_pipe + step_h / 2),
              xytext=(x_start - 0.75, y_pipe + step_h / 2),
              arrowprops=dict(arrowstyle="-|>", color=BLACK, lw=1.0))
ax_b.text(x_start - 0.85, y_pipe + step_h / 2, "Agent\nproposal",
          ha="right", va="center", fontsize=6, fontweight="bold")

for i, (title, sub, is_ablation) in enumerate(steps):
    x = x_start + i * (step_w + gap)

    ec = BLUE if is_ablation else GREY_BORDER
    ls = "--" if is_ablation else "-"
    lw = 1.2 if is_ablation else 0.8
    fc = BLUE_LIGHT if is_ablation else GREY

    # Step number label
    ax_b.text(x + step_w / 2, y_pipe + step_h + 0.15, f"Step {i + 1}",
              ha="center", va="center", fontsize=5, color="#AAAAAA")

    # The box
    draw_box(ax_b, x, y_pipe, step_w, step_h,
             title, subtitle=sub,
             facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls,
             title_size=6, subtitle_size=4.8, pad=0.08)

    # Arrow between steps
    if i < n - 1:
        x_next = x_start + (i + 1) * (step_w + gap)
        ax_b.annotate("", xy=(x_next, y_pipe + step_h / 2),
                      xytext=(x + step_w, y_pipe + step_h / 2),
                      arrowprops=dict(arrowstyle="-|>", color=BLACK, lw=0.6))

# ── Ablation callout on step 4 ──────────────────────────────────────
abl_x = x_start + 3 * (step_w + gap) + step_w / 2
abl_y = y_pipe - 0.2

# Callout line
ax_b.plot([abl_x, abl_x], [y_pipe, abl_y - 0.15],
          color=RED_ACCENT, linewidth=0.7, linestyle="--", zorder=3)

# Callout box
callout_w, callout_h = 2.3, 0.42
cx = abl_x - callout_w / 2
cy = abl_y - callout_h - 0.25
callout = FancyBboxPatch(
    (cx, cy), callout_w, callout_h,
    boxstyle="round,pad=0.10",
    facecolor="#FFF5F5", edgecolor=RED_ACCENT,
    linewidth=0.8, linestyle="--", zorder=3,
)
ax_b.add_patch(callout)
ax_b.text(abl_x, cy + callout_h / 2,
          "A1 ablation: demand ceiling removed",
          ha="center", va="center", fontsize=5.2,
          color=RED_ACCENT, fontweight="bold", zorder=4)

# ── Output arrows ───────────────────────────────────────────────────
x_last = x_start + (n - 1) * (step_w + gap) + step_w

# Fork point
fork_x = x_last + 0.25
fork_y = y_pipe + step_h / 2
ax_b.annotate("", xy=(fork_x, fork_y),
              xytext=(x_last, fork_y),
              arrowprops=dict(arrowstyle="-", color=BLACK, lw=1.0))

# "Validated action" — top branch
ax_b.annotate("", xy=(fork_x + 0.8, fork_y + 0.4),
              xytext=(fork_x, fork_y),
              arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.0))
ax_b.text(fork_x + 0.9, fork_y + 0.4, "Validated\naction",
          ha="left", va="center", fontsize=5.5, fontweight="bold",
          color=BLUE)

# "Retry with feedback" — bottom branch
ax_b.annotate("", xy=(fork_x + 0.8, fork_y - 0.5),
              xytext=(fork_x, fork_y),
              arrowprops=dict(arrowstyle="-|>", color=RED_ACCENT, lw=1.0,
                              linestyle="--"))
ax_b.text(fork_x + 0.9, fork_y - 0.5, "Retry with\nfeedback",
          ha="left", va="center", fontsize=5.5, fontweight="bold",
          color=RED_ACCENT)

# ── Audit trail box ─────────────────────────────────────────────────
audit_w = total_w + 0.6
audit_x = x_start - 0.3
audit_y = 1.0
audit_h = 0.65

audit_box = FancyBboxPatch(
    (audit_x, audit_y), audit_w, audit_h,
    boxstyle="round,pad=0.10",
    facecolor="#F8F8F8", edgecolor=GREY_BORDER,
    linewidth=0.6, zorder=2,
)
ax_b.add_patch(audit_box)

ax_b.text(audit_x + audit_w / 2, audit_y + audit_h / 2 + 0.10,
          "Decision audit trail",
          ha="center", va="center", fontsize=6.5, fontweight="bold",
          color=BLACK, zorder=3)
ax_b.text(audit_x + audit_w / 2, audit_y + audit_h / 2 - 0.12,
          "All proposals, reasoning traces, and rule violations recorded",
          ha="center", va="center", fontsize=5.2, color="#666666",
          style="italic", zorder=3)

# Dashed connector from pipeline to audit box
pipe_mid_x = x_start + total_w / 2
ax_b.plot([pipe_mid_x, pipe_mid_x],
          [y_pipe, audit_y + audit_h],
          color=GREY_BORDER, linewidth=0.5, linestyle=":", zorder=1)

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
