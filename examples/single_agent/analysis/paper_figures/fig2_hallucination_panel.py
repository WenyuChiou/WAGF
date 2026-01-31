"""
SAGE Paper — Figure 2: Hallucination Correction Panel
======================================================
Two-panel figure for the WRR Technical Report.

Panel (a): Raw vs Corrected H_norm + EBE for Groups A, B, C
  - Group A raw (dashed red) vs corrected (solid red) shows the hallucination gap
  - Groups B, C solid lines (= EBE since hallucination ~ 0)

Panel (b): Cumulative relocation curves
  - A: ~1% (never relocate without governance)
  - B: 33% plateau (window memory forgets)
  - C: 43% with Year 9 surge (human-centric memory persists)

AGU/WRR figure requirements:
  - 300 DPI minimum
  - Serif font (Times New Roman)
  - Single-column (86mm) or double-column (170mm)
  - Color-blind friendly palette

Usage:
  python fig2_hallucination_panel.py
"""

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ---------- paths ----------
SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parents[1]  # examples/single_agent
RESULTS = BASE / "results" / "JOH_FINAL" / "gemma3_4b"
ENTROPY_CSV = SCRIPT_DIR / "corrected_entropy_gemma3_4b.csv"

# ---------- style ----------
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Color-blind friendly palette (Okabe-Ito)
C_A = "#D55E00"   # vermillion (Group A)
C_B = "#0072B2"   # blue (Group B)
C_C = "#009E73"   # teal (Group C)
C_A_RAW = "#D55E00"
C_A_DASH = "#D55E0080"  # semi-transparent for raw dashed

YEARS = np.arange(1, 11)
FLOOD_YEARS = [3, 4, 9]


def load_entropy():
    """Load corrected entropy CSV."""
    if not ENTROPY_CSV.exists():
        print(f"Run corrected_entropy_analysis.py first to generate {ENTROPY_CSV}")
        sys.exit(1)
    return pd.read_csv(ENTROPY_CSV)


def compute_relocation(group: str, sim_path: Path):
    """Compute cumulative relocation for one group."""
    df = pd.read_csv(sim_path)

    if "decision" in df.columns:
        dec_col = "decision"
    else:
        dec_col = "yearly_decision"

    cum_reloc = []
    for yr in sorted(df["year"].unique()):
        yr_df = df[df["year"] == yr]
        n = len(yr_df)
        reloc = yr_df[dec_col].str.lower().str.contains("relocat").sum()
        cum_reloc.append(reloc / n * 100)
    return cum_reloc


def main():
    entropy = load_entropy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.8), constrained_layout=True)

    # ======== Panel (a): Entropy ========
    ax1.set_title("(a) Effective Behavioral Entropy", fontweight="bold", loc="left")

    for group, color, label in [
        ("Group_A", C_A, "A (ungoverned)"),
        ("Group_B", C_B, "B (governance + window)"),
        ("Group_C", C_C, "C (governance + memory)"),
    ]:
        g = entropy[entropy["Group"] == group].sort_values("Year")
        years = g["Year"].values

        if group == "Group_A":
            # Raw (dashed) — the misleading picture
            ax1.plot(years, g["Raw_H_norm"].values, color=color,
                     linestyle="--", linewidth=1.0, alpha=0.5, label=f"{label} raw")
            # EBE (solid) — the corrected truth
            ax1.plot(years, g["EBE"].values, color=color,
                     linestyle="-", linewidth=1.8, marker="o", markersize=3,
                     label=f"{label} EBE")
        else:
            # For B/C, EBE ≈ raw since hallucination is low
            ax1.plot(years, g["EBE"].values, color=color,
                     linestyle="-", linewidth=1.8, marker="s" if "B" in group else "^",
                     markersize=3, label=f"{label} EBE")

    # Flood event markers
    for fy in FLOOD_YEARS:
        ax1.axvline(x=fy, color="gray", linestyle=":", linewidth=0.6, alpha=0.5)
    ax1.annotate("Flood", xy=(3, 0.02), fontsize=7, color="gray", ha="center")
    ax1.annotate("Flood", xy=(9, 0.02), fontsize=7, color="gray", ha="center")

    ax1.set_xlabel("Simulation Year")
    ax1.set_ylabel("EBE (H$_{norm}$ × (1 − R$_H$))")
    ax1.set_xlim(0.5, 10.5)
    ax1.set_ylim(-0.02, 1.0)
    ax1.set_xticks(YEARS)
    ax1.legend(loc="upper right", framealpha=0.9, edgecolor="none")
    ax1.grid(True, alpha=0.2)

    # ======== Panel (b): Cumulative Relocation ========
    ax2.set_title("(b) Cumulative Relocation Rate", fontweight="bold", loc="left")

    groups_paths = {
        "Group_A": RESULTS / "Group_A" / "Run_1" / "simulation_log.csv",
        "Group_B": RESULTS / "Group_B" / "Run_1" / "simulation_log.csv",
        "Group_C": RESULTS / "Group_C" / "Run_1" / "simulation_log.csv",
    }

    for group, color, label, marker in [
        ("Group_A", C_A, "A (ungoverned)", "o"),
        ("Group_B", C_B, "B (governance + window)", "s"),
        ("Group_C", C_C, "C (governance + memory)", "^"),
    ]:
        reloc = compute_relocation(group, groups_paths[group])
        ax2.plot(YEARS, reloc, color=color, linewidth=1.8, marker=marker,
                 markersize=3, label=label)

    # Flood event markers
    for fy in FLOOD_YEARS:
        ax2.axvline(x=fy, color="gray", linestyle=":", linewidth=0.6, alpha=0.5)

    # Year 9 annotation
    ax2.annotate(
        "Memory\npersistence",
        xy=(9, 37), xytext=(7.5, 48),
        fontsize=7, ha="center",
        arrowprops=dict(arrowstyle="->", color=C_C, lw=0.8),
        color=C_C, fontweight="bold",
    )

    ax2.set_xlabel("Simulation Year")
    ax2.set_ylabel("Cumulative Relocation (%)")
    ax2.set_xlim(0.5, 10.5)
    ax2.set_ylim(-2, 55)
    ax2.set_xticks(YEARS)
    ax2.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax2.legend(loc="upper left", framealpha=0.9, edgecolor="none")
    ax2.grid(True, alpha=0.2)

    # ======== Save ========
    out_path = SCRIPT_DIR / "fig2_hallucination_panel.png"
    fig.savefig(out_path, dpi=300)
    print(f"Saved: {out_path}")

    # Also save PDF for AGU submission
    out_pdf = SCRIPT_DIR / "fig2_hallucination_panel.pdf"
    fig.savefig(out_pdf)
    print(f"Saved: {out_pdf}")

    plt.close()


if __name__ == "__main__":
    main()
