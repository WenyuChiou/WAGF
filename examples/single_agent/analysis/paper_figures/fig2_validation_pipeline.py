"""
SAGE Paper -- Figure 2: Governance Validation Pipeline Flowchart
=================================================================
Six-phase governance pipeline from SkillBrokerEngine.process_step(),
showing the retry loop with InterventionReport feedback and
dual outcomes (APPROVED / REJECTED with soft governance).

AGU/WRR figure requirements:
  - 300 DPI minimum
  - Serif font (Times New Roman)
  - Full-width (~7 inches / 170 mm)
  - Color-blind friendly palette

Usage:
  python fig2_validation_pipeline.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ---------- paths ----------
SCRIPT_DIR = Path(__file__).resolve().parent

# ---------- style ----------
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "text.usetex": False,
})

# ---------- color palette (muted, color-blind friendly) ----------
CLR_PHASE    = "#4878A8"   # steel blue   -- main pipeline phases
CLR_VALID    = "#5B8C5A"   # sage green   -- validation sub-steps
CLR_APPROVE  = "#2E7D32"   # dark green   -- approved outcome
CLR_RETRY    = "#D4890E"   # amber        -- retry loop
CLR_SOFT     = "#7B5EA7"   # muted purple -- soft governance
CLR_PARSE    = "#3E7CB1"   # lighter blue -- parse sub-box
CLR_LIGHT_BG = "#EDF2F7"   # light blue-gray for validation area
CLR_ARROW    = "#444444"   # arrow color
CLR_CIRCLE   = "#6A8EAE"   # phase circle border
CLR_CIRCLE_F = "#E8EEF4"   # phase circle fill
CLR_AUDIT    = "#3B6E8F"   # teal-blue for audit


# ==========================================================================
# Drawing helpers
# ==========================================================================

def draw_box(ax, x, y, w, h, text, color, fontsize=7, fontweight="normal",
             text_color="white", edgecolor=None, linestyle="-",
             boxstyle="round,pad=0.12", linewidth=0.8, alpha=0.93, zorder=3):
    """Draw a rounded rectangle with centered text."""
    ec = edgecolor if edgecolor else color
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle=boxstyle,
        facecolor=color, edgecolor=ec,
        linewidth=linewidth, alpha=alpha, linestyle=linestyle,
        zorder=zorder,
    )
    ax.add_patch(box)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            fontweight=fontweight, color=text_color, zorder=zorder + 1,
            linespacing=1.25)
    return box


def draw_diamond(ax, x, y, w, h, text, color, fontsize=7,
                 text_color="white", edgecolor=None, linewidth=0.8):
    """Draw a diamond (decision node) with centered text."""
    ec = edgecolor if edgecolor else color
    hw, hh = w / 2, h / 2
    verts = [(x, y + hh), (x + hw, y), (x, y - hh), (x - hw, y), (x, y + hh)]
    diamond = mpatches.Polygon(
        verts, closed=True,
        facecolor=color, edgecolor=ec,
        linewidth=linewidth, alpha=0.93, zorder=3,
    )
    ax.add_patch(diamond)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            fontweight="bold", color=text_color, zorder=4, linespacing=1.15)


def draw_arrow(ax, x1, y1, x2, y2, color=None, style="-|>",
               linewidth=1.0, linestyle="-", zorder=2,
               shrinkA=2, shrinkB=2, connectionstyle="arc3,rad=0",
               mutation_scale=10):
    """Draw a directed arrow."""
    c = color if color else CLR_ARROW
    a = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style,
        connectionstyle=connectionstyle,
        color=c, linewidth=linewidth, linestyle=linestyle,
        shrinkA=shrinkA, shrinkB=shrinkB,
        zorder=zorder, mutation_scale=mutation_scale,
    )
    ax.add_patch(a)
    return a


def txt(ax, x, y, text, fontsize=6, color="#333333", ha="center",
        va="center", fontweight="normal", fontstyle="normal"):
    """Draw a text label."""
    ax.text(x, y, text, ha=ha, va=va, fontsize=fontsize, color=color,
            fontweight=fontweight, fontstyle=fontstyle, zorder=5,
            linespacing=1.2)


# ==========================================================================
# Main figure
# ==========================================================================

def main():
    fig, ax = plt.subplots(1, 1, figsize=(7.0, 8.2))
    ax.set_xlim(-0.5, 15.5)
    ax.set_ylim(-0.5, 14.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # ------------------------------------------------------------------
    # Layout constants
    # ------------------------------------------------------------------
    cx = 5.5           # main pipeline column center

    # Y positions (top to bottom)
    y1 = 13.4          # Phase 1: Context Building
    y2 = 12.05         # Phase 2: LLM Inference
    y3 = 10.6          # Phase 3: Response Parsing

    yv_top = 9.55      # Validation chain top edge
    yv_bot = 5.95      # Validation chain bottom edge

    yd = 4.85          # Decision diamond center
    y5 = 3.40          # Phase 5: Execution
    y6 = 1.95          # Phase 6: Audit Logging
    yo = 0.45          # Outcome boxes

    bw = 5.0           # main box width
    bh = 0.68          # main box height
    vw = 4.2           # validation sub-box width
    vh = 0.42          # validation sub-box height

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------
    ax.text(7.5, 14.30,
            "SAGE Governance Validation Pipeline",
            ha="center", va="center", fontsize=12.5, fontweight="bold",
            color="#1A1A1A")
    ax.text(7.5, 13.90,
            "SkillBrokerEngine.process_step()",
            ha="center", va="center", fontsize=8.5, fontstyle="italic",
            color="#666666")

    # ==================================================================
    # PHASE 1: Context Building
    # ==================================================================
    draw_box(ax, cx, y1, bw, bh,
             "Context Building\n"
             "TieredContextBuilder assembles bounded prompt",
             CLR_PHASE, fontsize=7, fontweight="bold")

    # ==================================================================
    # PHASE 2: LLM Inference
    # ==================================================================
    draw_box(ax, cx, y2, bw, bh,
             "LLM Inference\n"
             "Ollama generates structured response",
             CLR_PHASE, fontsize=7, fontweight="bold")

    # ==================================================================
    # PHASE 3: Response Parsing
    # ==================================================================
    p3h = bh + 0.15
    draw_box(ax, cx, y3, bw, p3h,
             "Response Parsing  (ModelAdapter)\n"
             "JSON \u2192 enclosure \u2192 regex \u2192 digit fallback",
             CLR_PARSE, fontsize=7, fontweight="bold")

    # Arrows 1 -> 2 -> 3
    draw_arrow(ax, cx, y1 - bh / 2, cx, y2 + bh / 2)
    draw_arrow(ax, cx, y2 - bh / 2, cx, y3 + p3h / 2)

    # ==================================================================
    # PHASE 4: Validation Chain (shaded region)
    # ==================================================================
    vpad = 0.35
    val_bg = FancyBboxPatch(
        (cx - bw / 2 - vpad, yv_bot - vpad),
        bw + 2 * vpad,
        yv_top - yv_bot + 2 * vpad,
        boxstyle="round,pad=0.15",
        facecolor=CLR_LIGHT_BG, edgecolor="#9BB5CC",
        linewidth=0.7, linestyle="--", alpha=0.55, zorder=1,
    )
    ax.add_patch(val_bg)
    txt(ax, cx, yv_top + 0.18, "Validation Chain",
        fontsize=8.5, fontweight="bold", color="#3A5F7F")

    # Validation sub-items
    val_items = [
        ("Registry Lookup", vh),
        ("Eligibility Check", vh),
        ("Identity Rules  (physical constraints:\n"
         "already_elevated, water_right_cap)", vh + 0.20),
        ("Thinking Rules  (appraisal coherence:\n"
         "PMT or WSA/ACA)", vh + 0.20),
        ("Custom Validators", vh),
    ]

    # Compute vertical positions
    vy = yv_top - 0.28
    vy_pos = []
    for _, h in val_items:
        cy_v = vy - h / 2
        vy_pos.append((cy_v, h))
        vy -= h + 0.15

    # Draw sub-boxes
    for (cy_v, h), (lbl, _) in zip(vy_pos, val_items):
        draw_box(ax, cx, cy_v, vw, h, lbl, CLR_VALID,
                 fontsize=6.2, text_color="white",
                 boxstyle="round,pad=0.06", linewidth=0.6)

    # Small arrows between sub-steps
    for i in range(len(vy_pos) - 1):
        y_from = vy_pos[i][0] - vy_pos[i][1] / 2
        y_to = vy_pos[i + 1][0] + vy_pos[i + 1][1] / 2
        draw_arrow(ax, cx, y_from, cx, y_to,
                   linewidth=0.6, color="#7A9BBE", mutation_scale=8)

    # Arrow: Phase 3 -> first validation step
    draw_arrow(ax, cx, y3 - p3h / 2,
               cx, vy_pos[0][0] + vy_pos[0][1] / 2)

    # ==================================================================
    # Decision Diamond: All Valid?
    # ==================================================================
    dw, dh = 1.9, 1.0
    draw_diamond(ax, cx, yd, dw, dh, "All\nValid?",
                 "#5A7D9A", fontsize=8)

    # Arrow: last validation step -> diamond
    draw_arrow(ax, cx, vy_pos[-1][0] - vy_pos[-1][1] / 2,
               cx, yd + dh / 2)

    # ==================================================================
    # RETRY LOOP (right side)
    # ==================================================================
    rx = 11.5          # retry column center x
    ry1 = 8.1          # InterventionReport y
    ry2 = 6.5          # Re-prompt box y
    rx_vert = 14.0     # vertical return line x

    # InterventionReport box
    ir_w, ir_h = 3.8, 0.85
    draw_box(ax, rx, ry1, ir_w, ir_h,
             "InterventionReport\n"
             "rule_id, violation_summary,\n"
             "suggested_correction",
             CLR_RETRY, fontsize=6.5, fontweight="bold",
             text_color="white", boxstyle="round,pad=0.10")

    # Re-prompt box
    rp_w, rp_h = 3.4, 0.58
    draw_box(ax, rx, ry2, rp_w, rp_h,
             "Re-prompt LLM with\n"
             "governance explanation",
             "#EDCE8C", fontsize=6.5, fontweight="normal",
             text_color="#4A3000", boxstyle="round,pad=0.08",
             edgecolor=CLR_RETRY, linewidth=0.7)

    # Arrow: Decision FAIL --> InterventionReport
    draw_arrow(ax, cx + dw / 2, yd,
               rx - ir_w / 2, ry1 - 0.1,
               color=CLR_RETRY, linewidth=1.2,
               connectionstyle="arc3,rad=-0.2")
    txt(ax, cx + 2.1, yd + 0.52, "FAIL", fontsize=7.5,
        color=CLR_RETRY, fontweight="bold")

    # Arrow: InterventionReport --> Re-prompt
    draw_arrow(ax, rx, ry1 - ir_h / 2, rx, ry2 + rp_h / 2,
               color=CLR_RETRY, linewidth=0.9)

    # Retry return path: Re-prompt -> right -> up -> left -> Phase 2
    # Segment 1: Re-prompt right edge -> vertical line x
    draw_arrow(ax, rx + rp_w / 2, ry2,
               rx_vert, ry2,
               color=CLR_RETRY, linewidth=0.9,
               style="-", shrinkB=0)
    # Segment 2: vertical up
    draw_arrow(ax, rx_vert, ry2,
               rx_vert, y2,
               color=CLR_RETRY, linewidth=0.9,
               style="-", shrinkA=0, shrinkB=0)
    # Segment 3: left to Phase 2 right edge
    draw_arrow(ax, rx_vert, y2,
               cx + bw / 2, y2,
               color=CLR_RETRY, linewidth=0.9)

    # "max 3 retries" label along vertical return path
    txt(ax, rx_vert + 0.60, (ry2 + y2) / 2 + 0.6,
        "max 3\nretries", fontsize=7, color=CLR_RETRY, fontweight="bold")

    # Small circular arrow icon at top return corner
    circ_arr = FancyArrowPatch(
        (rx_vert - 0.2, y2 + 0.32), (rx_vert + 0.2, y2 + 0.12),
        arrowstyle="-|>", connectionstyle="arc3,rad=0.6",
        color=CLR_RETRY, linewidth=0.7, mutation_scale=7, zorder=3)
    ax.add_patch(circ_arr)

    # ==================================================================
    # APPROVED PATH (down from diamond)
    # ==================================================================
    draw_arrow(ax, cx, yd - dh / 2, cx, y5 + bh / 2,
               color=CLR_APPROVE, linewidth=1.3)
    txt(ax, cx - 0.80, yd - 0.68, "PASS", fontsize=7.5,
        color=CLR_APPROVE, fontweight="bold")

    # Phase 5: Execution
    draw_box(ax, cx, y5, bw, bh,
             "Execution\n"
             "ApprovedSkill \u2192 Simulation state update",
             CLR_APPROVE, fontsize=7, fontweight="bold")

    # Phase 6: Audit Logging
    draw_box(ax, cx, y6, bw, bh,
             "Audit Logging\n"
             "InterventionReport + decision traces",
             CLR_AUDIT, fontsize=7, fontweight="bold")

    # Arrow: Phase 5 -> Phase 6
    draw_arrow(ax, cx, y5 - bh / 2, cx, y6 + bh / 2)

    # ==================================================================
    # Outcome boxes
    # ==================================================================
    ow_app = 3.0
    ow_rej = 4.0
    oh = 0.72

    # APPROVED
    x_app = cx - 2.2
    draw_box(ax, x_app, yo, ow_app, oh,
             "APPROVED\n"
             "Execute \u2192 Log",
             CLR_APPROVE, fontsize=7.5, fontweight="bold")

    # REJECTED (soft governance)
    x_rej = cx + 3.2
    draw_box(ax, x_rej, yo, ow_rej, oh,
             "REJECTED  (soft governance)\n"
             "Executes with REJECTED status\n"
             "for measurement",
             CLR_SOFT, fontsize=6.2, fontweight="bold")

    # Arrows from Phase 6 to outcomes
    draw_arrow(ax, cx - 1.0, y6 - bh / 2,
               x_app, yo + oh / 2,
               color=CLR_APPROVE, linewidth=0.9,
               connectionstyle="arc3,rad=0.12")
    draw_arrow(ax, cx + 1.0, y6 - bh / 2,
               x_rej, yo + oh / 2,
               color=CLR_SOFT, linewidth=0.9,
               connectionstyle="arc3,rad=-0.12")

    txt(ax, x_rej + 0.3, y6 - 0.75,
        "after max retries", fontsize=5.5,
        color=CLR_SOFT, fontstyle="italic")

    # ==================================================================
    # Phase number circles (left margin)
    # ==================================================================
    pcx = 1.9
    phases = [
        (y1,   "1", "Context\nBuilding"),
        (y2,   "2", "LLM\nInference"),
        (y3,   "3", "Response\nParsing"),
        ((yv_top + yv_bot) / 2 + 0.35, "4", "Validation\nChain"),
        (y5,   "5", "Execution"),
        (y6,   "6", "Audit\nLogging"),
    ]

    for py, num, pname in phases:
        circ = plt.Circle((pcx, py), 0.30, facecolor=CLR_CIRCLE_F,
                           edgecolor=CLR_CIRCLE, linewidth=0.8, zorder=3)
        ax.add_patch(circ)
        ax.text(pcx, py, num, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#3A5F7F", zorder=4)
        ax.text(pcx - 1.25, py, pname, ha="center", va="center",
                fontsize=5.8, color="#5A7D9A", fontweight="bold",
                linespacing=1.15)

    # Thin dashed connectors from circles to main boxes
    for py, _, _ in phases:
        ax.plot([pcx + 0.30, cx - bw / 2], [py, py],
                color="#C8D6E5", linewidth=0.35, linestyle=":",
                zorder=1)

    # ==================================================================
    # Save
    # ==================================================================
    out_png = SCRIPT_DIR / "fig2_validation_pipeline.png"
    fig.savefig(out_png, dpi=300, facecolor="white")
    print(f"Saved: {out_png}")

    out_pdf = SCRIPT_DIR / "fig2_validation_pipeline.pdf"
    fig.savefig(out_pdf, facecolor="white")
    print(f"Saved: {out_pdf}")

    plt.close()
    print("Done.")


if __name__ == "__main__":
    main()
