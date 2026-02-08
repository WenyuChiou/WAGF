"""
WAGF Paper -- Figure 1: Architecture Overview
==============================================
Three-layer separation diagram for the WRR Technical Note.

    LLM Agent (Thinking)
        |
    Governed Broker (Validation)   <-- Three Pillars inside
        |
    Simulation Engine (Execution)

The Broker NEVER makes decisions (LLM does) or mutates state
(Simulation does). It only validates and audits.

Three Pillars of the Broker:
  1. Governance Rules      -- YAML validator chain
  2. Cognitive Memory       -- HumanCentric emotional encoding
  3. Priority Context       -- Tiered context builder

Bottom strip: domain-agnostic instantiation
  - Flood Adaptation  (100 households x 10 yr)
  - Irrigation Management (78 districts x 42 yr)

Usage:
  python fig1_architecture.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe

# ---------- paths ----------
SCRIPT_DIR = Path(__file__).resolve().parent

# ---------- style ----------
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 12,
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

# ---------- colour palette ----------
# Blues for broker
BLUE_DARK   = "#1a3a5c"
BLUE_MED    = "#2196F3"
BLUE_LIGHT  = "#90CAF9"
BLUE_WASH   = "#E3F2FD"  # very light blue wash
BLUE_PALE   = "#BBDEFB"

# Grays for LLM and Simulation
GRAY_DARK   = "#424242"
GRAY_MED    = "#757575"
GRAY_LIGHT  = "#E0E0E0"
GRAY_BG     = "#F5F5F5"
GRAY_WASH   = "#FAFAFA"

# Accent colors
WHITE       = "#FFFFFF"
NEAR_BLACK  = "#212121"
ARROW_COLOR = "#37474F"

# Domain colors
FLOOD_BG    = "#E8F5E9"
FLOOD_EC    = "#388E3C"
FLOOD_TEXT  = "#1B5E20"
IRRIG_BG    = "#FFF3E0"
IRRIG_EC    = "#E65100"
IRRIG_TEXT  = "#BF360C"


# -- helpers ---------------------------------------------------------------
def _rounded_box(ax, x, y, w, h, fc, ec="#9E9E9E", lw=1.0, zorder=2,
                 pad=0.015, alpha=1.0):
    """Draw a rounded rectangle. (x, y) is bottom-left."""
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad={pad}",
        facecolor=fc, edgecolor=ec, linewidth=lw,
        zorder=zorder, alpha=alpha,
    )
    ax.add_patch(p)
    return p


def _text(ax, x, y, s, fs=9, fw="normal", fc=NEAR_BLACK, ha="center",
          va="center", zorder=5, **kw):
    return ax.text(x, y, s, fontsize=fs, fontweight=fw, color=fc,
                   ha=ha, va=va, zorder=zorder, **kw)


def _arrow_down(ax, x, y_from, y_to, color=ARROW_COLOR, lw=1.5, ls="-"):
    """Downward arrow."""
    ax.annotate(
        "", xy=(x, y_to), xytext=(x, y_from),
        arrowprops=dict(
            arrowstyle="-|>", color=color, lw=lw,
            linestyle=ls, mutation_scale=14,
        ),
        zorder=10,
    )


def _arrow_up(ax, x, y_from, y_to, color=ARROW_COLOR, lw=1.2, ls="--"):
    """Upward arrow (for feedback)."""
    ax.annotate(
        "", xy=(x, y_to), xytext=(x, y_from),
        arrowprops=dict(
            arrowstyle="-|>", color=color, lw=lw,
            linestyle=ls, mutation_scale=12,
        ),
        zorder=10,
    )


# ==========================================================================
def draw_architecture():
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    # -- global geometry ---------------------------------------------------
    margin = 0.40
    W = 10 - 2 * margin  # 9.2
    x0 = margin

    # Vertical layout (top to bottom, all positions are TOP of each band)
    # Title region sits at the very top
    yTitle = 9.85

    # LLM Agent layer
    yA_top = 9.35;  hA = 0.70

    # Gap for arrow
    # Broker layer
    yB_top = 8.20;  hB = 4.20

    # Gap for arrow
    # Simulation Engine layer
    yE_top = 3.55;  hE = 0.70

    # Gap for arrow
    # Domain strip
    yD_top = 2.40;  hD = 1.10

    # Caption space below

    # -- figure title (subtle) -------------------------------------------
    _text(ax, 5.0, yTitle,
          "WAGF: Water Agent Governance Framework",
          fs=12.5, fw="bold", fc=BLUE_DARK)
    _text(ax, 5.0, yTitle - 0.28,
          "Three-Layer Separation Architecture",
          fs=9, fw="normal", fc=GRAY_MED, fontstyle="italic")

    # ======================================================================
    # 1. LLM AGENT LAYER
    # ======================================================================
    _rounded_box(ax, x0, yA_top - hA, W, hA, GRAY_LIGHT, ec=GRAY_DARK,
                 lw=1.5, pad=0.02)
    _text(ax, x0 + W / 2, yA_top - hA / 2 + 0.08,
          "LLM Agent", fs=11, fw="bold", fc=GRAY_DARK)
    _text(ax, x0 + W / 2, yA_top - hA / 2 - 0.18,
          "Thinking Layer  \u2014  Perceives context, reasons about risk, proposes actions",
          fs=7.5, fc=GRAY_MED, fontstyle="italic")

    # Arrow: Agent --> Broker
    _arrow_down(ax, x0 + W / 2, yA_top - hA - 0.06, yB_top + 0.06)
    _text(ax, x0 + W / 2 + 0.12, (yA_top - hA + yB_top) / 2,
          "proposed action", fs=7, fc=ARROW_COLOR, ha="left", fontstyle="italic")

    # ======================================================================
    # 2. GOVERNED BROKER LAYER (main blue region)
    # ======================================================================
    _rounded_box(ax, x0, yB_top - hB, W, hB, BLUE_WASH, ec=BLUE_DARK,
                 lw=2.0, pad=0.02)

    # Broker header
    _text(ax, x0 + W / 2, yB_top - 0.25,
          "Governed Broker", fs=11, fw="bold", fc=BLUE_DARK)
    _text(ax, x0 + W / 2, yB_top - 0.52,
          "Validation Layer  \u2014  Never decides. Never mutates state. Validates & audits only.",
          fs=7.5, fc=BLUE_MED, fontstyle="italic")

    # -- Pillar geometry ---------------------------------------------------
    pMargin = 0.30
    pGap = 0.22
    pTop = yB_top - 0.80     # top of pillar boxes
    pBot = yB_top - hB + 0.20  # bottom of pillar boxes
    pH = pTop - pBot
    usableW = W - 2 * pMargin
    pW = (usableW - 2 * pGap) / 3
    pX = [x0 + pMargin + i * (pW + pGap) for i in range(3)]

    # -- Pillar 1: Governance Rules ----------------------------------------
    _rounded_box(ax, pX[0], pBot, pW, pH, WHITE, ec=BLUE_DARK, lw=1.2,
                 pad=0.012, zorder=3)

    # Pillar header
    hdr_y = pTop - 0.22
    _text(ax, pX[0] + pW / 2, hdr_y,
          "Governance Rules", fs=9.5, fw="bold", fc=BLUE_DARK)
    _text(ax, pX[0] + pW / 2, hdr_y - 0.25,
          "YAML-Defined Validator Chain", fs=6.5, fc=BLUE_MED)

    # Sub-items as small boxes in a chain
    validators = [
        ("Identity Check", "persona consistency"),
        ("Thinking\u2013Action\nCoherence", "reasoning must\nmatch chosen skill"),
        ("Physical\nConstraints", "budget, geography,\nprior-state feasibility"),
        ("Block \u2192 Retry", "explanation sent\nback to LLM"),
    ]
    vMarg = 0.12
    vW = pW - 2 * vMarg
    vX = pX[0] + vMarg
    vH = 0.50
    vGap = 0.12
    v_start_y = hdr_y - 0.55  # top of first validator box

    for i, (label, desc) in enumerate(validators):
        vy_top = v_start_y - i * (vH + vGap)
        vy = vy_top - vH
        color_cycle = [BLUE_PALE, "#D6EAFF"]
        _rounded_box(ax, vX, vy, vW, vH, color_cycle[i % 2],
                     ec=BLUE_MED, lw=0.6, zorder=4, pad=0.008)
        _text(ax, vX + vW / 2, vy + vH * 0.62, label,
              fs=6.8, fw="bold", fc=BLUE_DARK, zorder=5)
        _text(ax, vX + vW / 2, vy + vH * 0.22, desc,
              fs=5.5, fc="#546E7A", zorder=5, linespacing=1.1)
        # Chain arrow between boxes
        if i < len(validators) - 1:
            _arrow_down(ax, vX + vW / 2, vy - 0.01, vy - vGap + 0.01,
                        color=BLUE_MED, lw=0.8)

    # -- Pillar 2: Cognitive Memory ----------------------------------------
    _rounded_box(ax, pX[1], pBot, pW, pH, WHITE, ec=BLUE_DARK, lw=1.2,
                 pad=0.012, zorder=3)

    hdr_y2 = pTop - 0.22
    _text(ax, pX[1] + pW / 2, hdr_y2,
          "Cognitive Memory", fs=9.5, fw="bold", fc=BLUE_DARK)
    _text(ax, pX[1] + pW / 2, hdr_y2 - 0.25,
          "HumanCentric Memory Engine", fs=6.5, fc=BLUE_MED)

    # Memory sub-components
    mem_items = [
        ("Emotional Encoding", "salience from appraisal\n(threat + coping)"),
        ("Arousal-Weighted\nStorage", "high-arousal events\nresist decay"),
        ("Stochastic\nConsolidation", "probabilistic retention\nmimics human forgetting"),
        ("Surprise-Driven\nRetrieval", "unexpected stimuli\ntrigger recall"),
    ]
    mMarg = 0.12
    mW = pW - 2 * mMarg
    mX = pX[1] + mMarg
    mH = 0.50
    mGap = 0.12
    m_start_y = hdr_y2 - 0.55

    mem_colors = ["#B3E5FC", "#E1F5FE", "#B3E5FC", "#E1F5FE"]
    for i, (label, desc) in enumerate(mem_items):
        my_top = m_start_y - i * (mH + mGap)
        my = my_top - mH
        _rounded_box(ax, mX, my, mW, mH, mem_colors[i % 2],
                     ec=BLUE_MED, lw=0.6, zorder=4, pad=0.008)
        _text(ax, mX + mW / 2, my + mH * 0.62, label,
              fs=6.8, fw="bold", fc=BLUE_DARK, zorder=5)
        _text(ax, mX + mW / 2, my + mH * 0.22, desc,
              fs=5.5, fc="#546E7A", zorder=5, linespacing=1.1)

    # -- Pillar 3: Priority Context ----------------------------------------
    _rounded_box(ax, pX[2], pBot, pW, pH, WHITE, ec=BLUE_DARK, lw=1.2,
                 pad=0.012, zorder=3)

    hdr_y3 = pTop - 0.22
    _text(ax, pX[2] + pW / 2, hdr_y3,
          "Priority Context", fs=9.5, fw="bold", fc=BLUE_DARK)
    _text(ax, pX[2] + pW / 2, hdr_y3 - 0.25,
          "Tiered Context Builder", fs=6.5, fc=BLUE_MED)

    # Tiers with visual hierarchy (decreasing opacity / saturation)
    tiers = [
        ("Tier 1 \u2014 MUST",
         "governance rules,\nphysical constraints,\nidentity anchors",
         "#90CAF9", BLUE_DARK),     # strongest blue
        ("Tier 2 \u2014 SHOULD",
         "recent memory,\nemotional context,\nneighbor influence",
         "#BBDEFB", BLUE_DARK),     # medium blue
        ("Tier 3 \u2014 MAY",
         "historical trends,\nglobal statistics,\nbackground info",
         "#E3F2FD", "#455A64"),     # lightest
    ]
    tMarg = 0.12
    tW = pW - 2 * tMarg
    tX = pX[2] + tMarg
    tH = 0.70
    tGap = 0.12
    t_start_y = hdr_y3 - 0.55

    for i, (label, desc, bg, text_col) in enumerate(tiers):
        ty_top = t_start_y - i * (tH + tGap)
        ty = ty_top - tH
        _rounded_box(ax, tX, ty, tW, tH, bg,
                     ec=BLUE_MED, lw=0.6, zorder=4, pad=0.008)
        _text(ax, tX + tW / 2, ty + tH * 0.72, label,
              fs=7.5, fw="bold", fc=text_col, zorder=5)
        _text(ax, tX + tW / 2, ty + tH * 0.32, desc,
              fs=5.5, fc="#546E7A", zorder=5, linespacing=1.15)

    # Tier priority indicator (small downward arrow with label on right edge)
    tier_top_y = t_start_y - tH * 0.5
    tier_bot_y = t_start_y - 2 * (tH + tGap) - tH * 0.5
    tier_arrow_x = pX[2] + pW + 0.06
    _arrow_down(ax, tier_arrow_x, tier_top_y, tier_bot_y,
                color="#B0BEC5", lw=0.8)
    _text(ax, tier_arrow_x + 0.12, (tier_top_y + tier_bot_y) / 2,
          "priority", fs=5.5, fc="#90A4AE", rotation=90, fontstyle="italic",
          va="center", ha="center")

    # Arrow: Broker --> Engine
    _arrow_down(ax, x0 + W / 2, yB_top - hB - 0.06, yE_top + 0.06)
    _text(ax, x0 + W / 2 + 0.12, (yB_top - hB + yE_top) / 2,
          "validated action", fs=7, fc=ARROW_COLOR, ha="left", fontstyle="italic")

    # ======================================================================
    # 3. SIMULATION ENGINE LAYER
    # ======================================================================
    _rounded_box(ax, x0, yE_top - hE, W, hE, GRAY_LIGHT, ec=GRAY_DARK,
                 lw=1.5, pad=0.02)
    _text(ax, x0 + W / 2, yE_top - hE / 2 + 0.08,
          "Simulation Engine", fs=11, fw="bold", fc=GRAY_DARK)
    _text(ax, x0 + W / 2, yE_top - hE / 2 - 0.18,
          "Execution Layer  \u2014  Applies validated action, advances state, returns outcome",
          fs=7.5, fc=GRAY_MED, fontstyle="italic")

    # Arrow: Engine --> Domain
    _arrow_down(ax, x0 + W / 2, yE_top - hE - 0.06, yD_top + 0.06)
    _text(ax, x0 + W / 2 + 0.12, (yE_top - hE + yD_top) / 2,
          "domain instantiation", fs=7, fc=ARROW_COLOR, ha="left",
          fontstyle="italic")

    # ======================================================================
    # 4. DOMAIN INSTANTIATION STRIP
    # ======================================================================
    dGap = 0.35
    dW = (W - dGap) / 2

    # -- Flood Case --
    fx = x0
    _rounded_box(ax, fx, yD_top - hD, dW, hD, FLOOD_BG, ec=FLOOD_EC,
                 lw=1.0, pad=0.012)
    _text(ax, fx + dW / 2, yD_top - 0.20,
          "Flood Adaptation  (CHANCE-C)", fs=8, fw="bold", fc=FLOOD_TEXT)
    _text(ax, fx + dW / 2, yD_top - hD / 2 - 0.08,
          "100 households \u00d7 10 years\n"
          "Skills: elevate | insure | relocate | do_nothing\n"
          "Governance: threat\u2013action coherence",
          fs=6.5, fc="#2E7D32", linespacing=1.35)

    # -- Irrigation Case --
    ix = x0 + dW + dGap
    _rounded_box(ax, ix, yD_top - hD, dW, hD, IRRIG_BG, ec=IRRIG_EC,
                 lw=1.0, pad=0.012)
    _text(ax, ix + dW / 2, yD_top - 0.20,
          "Irrigation Management  (UCRC)", fs=8, fw="bold", fc=IRRIG_TEXT)
    _text(ax, ix + dW / 2, yD_top - hD / 2 - 0.08,
          "78 CRSS districts \u00d7 42 years\n"
          "Skills: increase | decrease | efficiency | acreage | maintain\n"
          "Governance: water-right constraints",
          fs=6.5, fc="#E65100", linespacing=1.35)

    # "Same framework" label centered between the two domain boxes
    _text(ax, x0 + W / 2, yD_top - hD - 0.22,
          "Same architecture, different domain adapters",
          fs=7, fc=GRAY_MED, fontstyle="italic")

    # ======================================================================
    # 5. FEEDBACK LOOP (right edge, dashed)
    # ======================================================================
    fb_x = x0 + W + 0.08
    # Horizontal ticks connecting layers to the feedback line
    ax.plot([x0 + W, fb_x], [yE_top - hE / 2] * 2,
            color="#90A4AE", lw=1.0, ls="--", zorder=1)
    ax.plot([fb_x, x0 + W], [yA_top - hA / 2] * 2,
            color="#90A4AE", lw=1.0, ls="--", zorder=1)
    # Vertical dashed arrow (Engine level --> Agent level, upward)
    _arrow_up(ax, fb_x, yE_top - hE / 2, yA_top - hA / 2,
              color="#90A4AE", lw=1.0)
    _text(ax, fb_x + 0.14,
          (yA_top - hA / 2 + yE_top - hE / 2) / 2,
          "updated state\n& memory", fs=6, fc="#78909C",
          rotation=90, fontstyle="italic")

    # ======================================================================
    # 6. LEFT-SIDE LAYER LABELS (subtle role annotations)
    # ======================================================================
    label_x = x0 - 0.06
    _text(ax, label_x, yA_top - hA / 2, "DECIDES",
          fs=7, fw="bold", fc=GRAY_MED, ha="right", rotation=90)
    _text(ax, label_x, yB_top - hB / 2, "VALIDATES",
          fs=7, fw="bold", fc=BLUE_MED, ha="right", rotation=90)
    _text(ax, label_x, yE_top - hE / 2, "EXECUTES",
          fs=7, fw="bold", fc=GRAY_MED, ha="right", rotation=90)

    return fig


# ==========================================================================
if __name__ == "__main__":
    fig = draw_architecture()

    out_png = SCRIPT_DIR / "fig1_architecture.png"
    fig.savefig(str(out_png), format="png", bbox_inches="tight")
    print(f"Saved: {out_png}")
    plt.close(fig)

