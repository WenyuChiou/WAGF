"""
SAGE Paper -- Figure 1: Architecture Overview
==============================================
Three-layer separation diagram for the WRR Technical Report.

    LLM Agent (Thinking)
        |
    Governed Broker (Validation)   <-- Three Pillars inside
        |
    Simulation Engine (Execution)

Within the Governed Broker the three pillars are shown:
  1. Governance Validator Chain
  2. Cognitive Memory
  3. Priority Context Builder

At the bottom, two domain-instantiation boxes:
  - Flood Adaptation  (100 households x 10 yr)
  - Irrigation Management (78 districts x 42 yr)

AGU/WRR figure requirements:
  - 300 DPI minimum
  - Serif font (Times New Roman)
  - Full-width figure (~7 inches / 170 mm)
  - Clean, muted colour palette

Usage:
  python fig1_architecture.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ---------- paths ----------
SCRIPT_DIR = Path(__file__).resolve().parent

# ---------- style ----------
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# ---------- colour palette (muted) ----------
COL_AGENT    = "#B3CDE3"   # light steel blue
COL_BROKER   = "#ECECEC"   # light gray
COL_ENGINE   = "#FDDBC7"   # light peach / orange
COL_PILLAR1  = "#4A90A4"   # muted teal-blue  (Governance)
COL_PILLAR2  = "#5E8C5E"   # muted sage-green (Memory)
COL_PILLAR3  = "#B8905A"   # muted warm-tan   (Priority)
COL_ARROW    = "#404040"   # dark gray
COL_TEXT     = "#1A1A1A"   # near-black
COL_BORDER   = "#505050"   # medium gray


# ── helpers ──────────────────────────────────────────────────────────
def _box(ax, x, y, w, h, fc, ec=COL_BORDER, lw=1.0, zorder=2):
    """Rounded box. (x,y) is bottom-left corner."""
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=zorder)
    ax.add_patch(p)
    return p


def _sbox(ax, x, y, w, h, fc, ec=COL_BORDER, lw=0.6, zorder=3):
    """Small rounded box. (x,y) is bottom-left corner."""
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=zorder)
    ax.add_patch(p)
    return p


def _txt(ax, x, y, s, fs=8, fw="normal", fc=COL_TEXT, ha="center",
         va="center", zorder=5, **kw):
    return ax.text(x, y, s, fontsize=fs, fontweight=fw, color=fc,
                   ha=ha, va=va, zorder=zorder, **kw)


def _arrow(ax, x, y0, y1, color=COL_ARROW, lw=1.2):
    ax.annotate("", xy=(x, y1), xytext=(x, y0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                mutation_scale=12), zorder=10)


# ══════════════════════════════════════════════════════════════════════
def draw_architecture():
    fig, ax = plt.subplots(figsize=(7.0, 7.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12.0)
    ax.axis("off")

    # ── global geometry ──────────────────────────────────────────────
    x0 = 0.50
    W  = 9.00                         # full width of main layers

    # vertical stack (top to bottom -- all "top" values)
    yA_top = 11.60;  hA = 0.60       # Agent box
    yB_top = 10.50;  hB = 5.90       # Broker box (large)
    yE_top =  4.05;  hE = 0.60       # Engine box
    yD_top =  2.90                    # Domain row top

    # ── 1. LLM Agent ────────────────────────────────────────────────
    _box(ax, x0, yA_top - hA, W, hA, COL_AGENT, lw=1.2)
    _txt(ax, x0 + W/2, yA_top - hA/2,
         "LLM Agent  (Thinking Layer)", fs=10, fw="bold")
    _txt(ax, x0 + W + 0.15, yA_top - hA/2,
         "Prompt \u2192 Decision", fs=6.5, fc="#555555",
         ha="left", fontstyle="italic")

    # arrow Agent --> Broker
    _arrow(ax, x0 + W/2, yA_top - hA - 0.07, yB_top + 0.07)
    _txt(ax, x0 + W/2 + 0.15, (yA_top - hA + yB_top)/2,
         "proposed action", fs=6, fc=COL_ARROW, ha="left", fontstyle="italic")

    # ── 2. Governed Broker ──────────────────────────────────────────
    _box(ax, x0, yB_top - hB, W, hB, COL_BROKER, lw=1.4)
    _txt(ax, x0 + W/2, yB_top - 0.30,
         "Governed Broker  (Validation Layer)", fs=10, fw="bold")

    # --- pillar geometry ---
    # pillar outer boxes
    pTop  = yB_top - 0.68             # top of pillar boxes
    pBot  = yB_top - hB + 0.20       # bottom of pillar boxes
    pH    = pTop - pBot               # pillar height
    pGap  = 0.25
    pMarg = 0.30
    uW    = W - 2*pMarg
    pW    = (uW - 2*pGap) / 3
    pX    = [x0 + pMarg + i*(pW + pGap) for i in range(3)]

    # The pillar header text sits 0.30 below pillar top.
    # The first content box TOP edge sits 0.56 below pillar top.
    hdr_y = pTop - 0.30               # y of header text
    cnt_top = pTop - 0.60             # y of first content box TOP edge

    # ── Pillar 1 : Governance Validator Chain ────────────────────
    _box(ax, pX[0], pBot, pW, pH, "#DCEAF5", ec=COL_PILLAR1, lw=1.0)
    _txt(ax, pX[0] + pW/2, hdr_y,
         "Governance Validator Chain", fs=7.5, fw="bold", fc=COL_PILLAR1)

    validators = ["YAML Rules", "Eligibility", "Identity",
                  "Thinking", "Physical", "Custom"]
    vH = 0.42;  vG = 0.18
    vX = pX[0] + 0.18;  vW = pW - 0.36
    vC = ["#C3DAF0", "#D8E8F6"]
    for i, vl in enumerate(validators):
        # top of box i = cnt_top - i*(vH+vG)
        # bottom-left y = top - vH
        v_top = cnt_top - i*(vH + vG)
        vy = v_top - vH
        _sbox(ax, vX, vy, vW, vH, vC[i % 2], ec=COL_PILLAR1, lw=0.5)
        _txt(ax, vX + vW/2, vy + vH/2, vl, fs=6.5, fc="#2B5F82")
        if i < len(validators) - 1:
            _arrow(ax, vX + vW/2, vy - 0.01, vy - vG + 0.01,
                   color=COL_PILLAR1, lw=0.7)

    # ── Pillar 2 : Cognitive Memory System ───────────────────────
    _box(ax, pX[1], pBot, pW, pH, "#E3EFE3", ec=COL_PILLAR2, lw=1.0)
    _txt(ax, pX[1] + pW/2, hdr_y,
         "Cognitive Memory System", fs=7.5, fw="bold", fc=COL_PILLAR2)

    memories = [
        ("Window Memory",       "Fixed-length sliding\ncontext window"),
        ("HumanCentric Memory", "Emotional salience &\ntrauma persistence"),
        ("Universal Memory",    "Entropy-based\nretention scoring"),
    ]
    mH = 1.10;  mG = 0.30
    mX = pX[1] + 0.15;  mW = pW - 0.30
    mC = ["#C5DFC5", "#D6EBD6", "#C5DFC5"]
    for i, (mn, md) in enumerate(memories):
        m_top = cnt_top - i*(mH + mG)
        my = m_top - mH
        _sbox(ax, mX, my, mW, mH, mC[i], ec=COL_PILLAR2, lw=0.5)
        _txt(ax, mX + mW/2, my + mH*0.68, mn,
             fs=6.5, fw="bold", fc="#2E6B2E")
        _txt(ax, mX + mW/2, my + mH*0.30, md,
             fs=5.2, fc="#4E7A4E", linespacing=1.15)

    # ── Pillar 3 : Priority Context Builder ──────────────────────
    _box(ax, pX[2], pBot, pW, pH, "#F5ECDF", ec=COL_PILLAR3, lw=1.0)
    _txt(ax, pX[2] + pW/2, hdr_y,
         "Priority Context Builder", fs=7.5, fw="bold", fc="#7A5C30")

    tiers = [
        ("Tier 1 \u2014 MUST",   "Governance rules,\nphysical constraints,\nidentity anchors"),
        ("Tier 2 \u2014 SHOULD", "Recent memory,\nemotional context,\nneighbor influence"),
        ("Tier 3 \u2014 NICE",   "Historical trends,\nglobal statistics,\nbackground info"),
    ]
    tH = 1.22;  tG = 0.24
    tX = pX[2] + 0.15;  tW = pW - 0.30
    tC  = ["#F0D8B0", "#F5E4C8", "#FAF0E0"]
    tEC = ["#A07030", "#B08848", "#C0A060"]
    for i, (tn, td) in enumerate(tiers):
        t_top = cnt_top - i*(tH + tG)
        ty = t_top - tH
        _sbox(ax, tX, ty, tW, tH, tC[i], ec=tEC[i], lw=0.5)
        _txt(ax, tX + tW/2, ty + tH*0.80, tn,
             fs=6.5, fw="bold", fc="#6B4E28")
        _txt(ax, tX + tW/2, ty + tH*0.40, td,
             fs=5.2, fc="#7A6040", linespacing=1.15)

    # arrow Broker --> Engine
    _arrow(ax, x0 + W/2, yB_top - hB - 0.07, yE_top + 0.07)
    _txt(ax, x0 + W/2 + 0.15, (yB_top - hB + yE_top)/2,
         "validated action", fs=6, fc=COL_ARROW, ha="left", fontstyle="italic")

    # ── 3. Simulation Engine ────────────────────────────────────────
    _box(ax, x0, yE_top - hE, W, hE, COL_ENGINE, lw=1.2)
    _txt(ax, x0 + W/2, yE_top - hE/2,
         "Simulation Engine  (Execution Layer)", fs=10, fw="bold")
    _txt(ax, x0 + W + 0.15, yE_top - hE/2,
         "State \u2192 Outcome", fs=6.5, fc="#555555",
         ha="left", fontstyle="italic")

    # arrow Engine --> Domain
    _arrow(ax, x0 + W/2, yE_top - hE - 0.07, yD_top + 0.07)
    _txt(ax, x0 + W/2 + 0.15, (yE_top - hE + yD_top)/2,
         "domain instantiation", fs=6, fc=COL_ARROW,
         ha="left", fontstyle="italic")

    # ── 4. Domain Instantiation ─────────────────────────────────────
    dH   = 1.20
    dGap = 0.50
    dW   = (W - dGap) / 2

    # Flood Adaptation
    dxF = x0
    _box(ax, dxF, yD_top - dH, dW, dH, "#DCEAF5", ec="#4A7FA5", lw=1.0)
    _txt(ax, dxF + dW/2, yD_top - 0.26,
         "Flood Adaptation (CHANCE-C)", fs=7.5, fw="bold", fc="#2B5070")
    _txt(ax, dxF + dW/2, yD_top - dH/2 - 0.10,
         "100 households \u00d7 10 years\n"
         "PMT behavioral theory\n"
         "Actions: elevate / insure / relocate",
         fs=6, fc="#3B6080", linespacing=1.35)

    # Irrigation Management
    dxI = x0 + dW + dGap
    _box(ax, dxI, yD_top - dH, dW, dH, "#F5ECDF", ec="#A07838", lw=1.0)
    _txt(ax, dxI + dW/2, yD_top - 0.26,
         "Irrigation Management (UCRC)", fs=7.5, fw="bold", fc="#6B4E28")
    _txt(ax, dxI + dW/2, yD_top - dH/2 - 0.10,
         "78 districts \u00d7 42 years\n"
         "WSA / ACA behavioral theory\n"
         "Actions: increase / decrease / efficiency",
         fs=6, fc="#7A6040", linespacing=1.35)

    # ── 5. Feedback loop (right edge, dashed) ──────────────────────
    fbX = x0 + W + 0.05
    # vertical dashed arrow (Engine level -> Agent level)
    ax.annotate("", xy=(fbX, yA_top - hA/2), xytext=(fbX, yE_top - hE/2),
                arrowprops=dict(arrowstyle="-|>", color="#999999", lw=0.8,
                                linestyle="dashed", mutation_scale=10),
                zorder=1)
    # horizontal ticks connecting main boxes to the vertical line
    ax.plot([x0 + W, fbX], [yE_top - hE/2]*2,
            color="#999999", lw=0.8, ls="--", zorder=1)
    ax.plot([fbX, x0 + W], [yA_top - hA/2]*2,
            color="#999999", lw=0.8, ls="--", zorder=1)
    _txt(ax, fbX + 0.12,
         (yA_top - hA/2 + yE_top - hE/2)/2,
         "updated\nstate", fs=5.5, fc="#888888",
         rotation=90, fontstyle="italic")

    return fig


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    fig = draw_architecture()

    out_pdf = SCRIPT_DIR / "fig1_architecture.pdf"
    out_png = SCRIPT_DIR / "fig1_architecture.png"

    fig.savefig(str(out_pdf), format="pdf", bbox_inches="tight")
    fig.savefig(str(out_png), format="png", bbox_inches="tight")

    print(f"Saved: {out_pdf}")
    print(f"Saved: {out_png}")
    plt.close(fig)
