"""
SAGE Paper -- Figure 3: Flood Adaptation Results (gemma3-4b)
=============================================================
Two-panel figure for the WRR Technical Report.

Panel (a): Entropy Comparison -- Raw H_norm vs EBE for Groups A, B, C
  - Grouped bar chart showing Raw H_norm, Corrected H_norm, and EBE
    across simulation years 2-10.
  - Group A's large gap between raw and EBE reveals hallucination inflation.
  - Groups B and C show minimal correction (low hallucination).

Panel (b): Cumulative Relocation Curves for Groups A, B, C
  - Group A: 0% (agents never relocate without governance)
  - Group B: ~32% plateau (window memory forgets; no year-9 response)
  - Group C: ~37% (human-centric memory enables year-9 response)

Data sources:
  - corrected_entropy_gemma3_4b.csv  (entropy metrics by group x year)
  - Simulation logs under results/JOH_FINAL/gemma3_4b/Group_{A,B,C}/Run_1/

AGU/WRR figure requirements:
  - 300 DPI minimum
  - Serif font (Times New Roman or equivalent)
  - Color-blind friendly palette (Okabe-Ito)

Usage:
  python fig3_flood_results.py
"""

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
BASE = SCRIPT_DIR.parents[1]          # examples/single_agent
RESULTS = BASE / "results" / "JOH_FINAL" / "gemma3_4b"
ENTROPY_CSV = SCRIPT_DIR / "corrected_entropy_gemma3_4b.csv"

# ---------- style ----------
plt.rcParams.update({
    "font.family":      "serif",
    "font.serif":       ["Times New Roman", "DejaVu Serif"],
    "font.size":        9,
    "axes.labelsize":   10,
    "axes.titlesize":   10,
    "legend.fontsize":  7.5,
    "xtick.labelsize":  8,
    "ytick.labelsize":  8,
    "figure.dpi":       300,
    "savefig.dpi":      300,
    "savefig.bbox":     "tight",
    "axes.linewidth":   0.6,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
})

# Okabe-Ito color-blind friendly palette
C_A = "#D55E00"   # vermillion  (Group A -- ungoverned)
C_B = "#0072B2"   # blue        (Group B -- governance + window memory)
C_C = "#009E73"   # teal        (Group C -- governance + full memory)

YEARS = np.arange(1, 11)
YEARS_PANEL_A = np.arange(2, 11)      # years 2-10 for entropy panel
FLOOD_YEARS = [3, 4, 9]
N_TOTAL = 100                          # agents per group


# ================================================================
# Data loaders
# ================================================================

def load_entropy():
    """Load the corrected entropy CSV."""
    if not ENTROPY_CSV.exists():
        print(f"ERROR: {ENTROPY_CSV} not found.\n"
              "Run corrected_entropy_analysis.py first.")
        sys.exit(1)
    return pd.read_csv(ENTROPY_CSV)


def compute_cumulative_relocation(entropy_df):
    """
    Compute cumulative relocation rate (%) per group per year
    from the N_Active column in the entropy CSV.

    Relocation is permanent, so:
        cum_reloc(%) = (N - N_Active) / N * 100
    """
    records = {}
    for group in ["Group_A", "Group_B", "Group_C"]:
        g = entropy_df[entropy_df["Group"] == group].sort_values("Year")
        cum = (N_TOTAL - g["N_Active"].values) / N_TOTAL * 100.0
        records[group] = cum
    return records


# ================================================================
# Figure
# ================================================================

def main():
    entropy = load_entropy()
    reloc_data = compute_cumulative_relocation(entropy)

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(7.0, 3.5), constrained_layout=True
    )

    # ==============================================================
    # Panel (a): Entropy comparison  --  Raw H_norm vs EBE (years 2-10)
    # ==============================================================
    ax1.set_title("(a) Raw Entropy vs. Effective Behavioral Entropy",
                  fontweight="bold", loc="left", fontsize=9)

    for group, color, label in [
        ("Group_A", C_A, "A (ungoverned)"),
        ("Group_B", C_B, "B (gov. + window)"),
        ("Group_C", C_C, "C (gov. + memory)"),
    ]:
        g = entropy[entropy["Group"] == group].sort_values("Year")
        g = g[g["Year"] >= 2]          # years 2-10 only
        yrs = g["Year"].values

        # Raw H_norm -- dashed line
        ax1.plot(
            yrs, g["Raw_H_norm"].values,
            color=color, linestyle="--", linewidth=1.0, alpha=0.50,
            label=f"{label} raw H$_{{norm}}$",
        )

        # EBE -- solid line with markers
        mkr = "o" if "A" in group else ("s" if "B" in group else "^")
        ax1.plot(
            yrs, g["EBE"].values,
            color=color, linestyle="-", linewidth=1.8,
            marker=mkr, markersize=3.5,
            label=f"{label} EBE",
        )

    # Shade the hallucination gap for Group A
    ga = entropy[entropy["Group"] == "Group_A"].sort_values("Year")
    ga = ga[ga["Year"] >= 2]
    ax1.fill_between(
        ga["Year"].values,
        ga["EBE"].values,
        ga["Raw_H_norm"].values,
        color=C_A, alpha=0.08,
    )
    # Label the gap
    mid_yr = 6
    ga_mid = ga[ga["Year"] == mid_yr]
    if not ga_mid.empty:
        mid_raw = ga_mid["Raw_H_norm"].values[0]
        mid_ebe = ga_mid["EBE"].values[0]
        ax1.annotate(
            "Hallucination\ngap (Group A)",
            xy=(mid_yr, (mid_raw + mid_ebe) / 2),
            xytext=(mid_yr + 2.1, 0.68),
            fontsize=6.5, color=C_A, ha="center", fontstyle="italic",
            arrowprops=dict(arrowstyle="->", color=C_A, lw=0.7),
        )

    # Flood markers
    for fy in FLOOD_YEARS:
        if fy >= 2:
            ax1.axvline(x=fy, color="gray", linestyle=":", linewidth=0.6, alpha=0.5)
    ax1.annotate("Flood", xy=(3, -0.04), fontsize=6.5, color="gray",
                 ha="center", annotation_clip=False)
    ax1.annotate("Flood", xy=(4, -0.04), fontsize=6.5, color="gray",
                 ha="center", annotation_clip=False)
    ax1.annotate("Flood", xy=(9, -0.04), fontsize=6.5, color="gray",
                 ha="center", annotation_clip=False)

    ax1.set_xlabel("Simulation Year")
    ax1.set_ylabel("Entropy  (H$_{norm}$ or EBE)")
    ax1.set_xlim(1.5, 10.5)
    ax1.set_ylim(-0.05, 1.0)
    ax1.set_xticks(YEARS_PANEL_A)
    ax1.legend(
        loc="upper right", framealpha=0.9, edgecolor="none",
        ncol=2, handlelength=1.6, columnspacing=0.8,
        borderpad=0.3, labelspacing=0.3,
    )
    ax1.grid(True, alpha=0.2)

    # ==============================================================
    # Panel (b): Cumulative relocation
    # ==============================================================
    ax2.set_title("(b) Cumulative Relocation Rate",
                  fontweight="bold", loc="left", fontsize=9)

    for group, color, label, mkr in [
        ("Group_A", C_A, "A (ungoverned)",       "o"),
        ("Group_B", C_B, "B (gov. + window)",    "s"),
        ("Group_C", C_C, "C (gov. + memory)",    "^"),
    ]:
        ax2.plot(
            YEARS, reloc_data[group],
            color=color, linewidth=1.8, marker=mkr, markersize=4,
            label=label,
        )

    # Flood markers
    for fy in FLOOD_YEARS:
        ax2.axvline(x=fy, color="gray", linestyle=":", linewidth=0.6, alpha=0.5)

    # Final-value annotations at year 10
    for group, color, va_offset in [
        ("Group_A", C_A,  +4),
        ("Group_B", C_B,  +4),
        ("Group_C", C_C,  -4),
    ]:
        final_val = reloc_data[group][-1]
        ax2.annotate(
            f"{final_val:.0f}%",
            xy=(10, final_val),
            xytext=(10.3, final_val + va_offset),
            fontsize=7, color=color, fontweight="bold",
            ha="left", va="center",
        )

    # Memory persistence annotation for Group C year 9 jump
    c_vals = reloc_data["Group_C"]
    yr9_val = c_vals[8]   # index 8 = year 9
    yr8_val = c_vals[7]   # index 7 = year 8
    if yr9_val > yr8_val:
        ax2.annotate(
            "Memory\npersistence",
            xy=(9, yr9_val - 1),
            xytext=(6.5, yr9_val + 8),
            fontsize=6.5, ha="center", fontweight="bold", color=C_C,
            arrowprops=dict(arrowstyle="->", color=C_C, lw=0.8),
        )

    ax2.set_xlabel("Simulation Year")
    ax2.set_ylabel("Cumulative Relocation (%)")
    ax2.set_xlim(0.5, 11.5)
    ax2.set_ylim(-2, 50)
    ax2.set_xticks(YEARS)
    ax2.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax2.legend(loc="upper left", framealpha=0.9, edgecolor="none")
    ax2.grid(True, alpha=0.2)

    # ==============================================================
    # Save
    # ==============================================================
    out_png = SCRIPT_DIR / "fig3_flood_results.png"
    out_pdf = SCRIPT_DIR / "fig3_flood_results.pdf"

    fig.savefig(out_png, dpi=300)
    print(f"Saved: {out_png}")

    fig.savefig(out_pdf, dpi=300)
    print(f"Saved: {out_pdf}")

    plt.close()

    # ------ Print summary table for verification ------
    print("\n--- Entropy Summary (years 2-10 mean) ---")
    for group in ["Group_A", "Group_B", "Group_C"]:
        g = entropy[(entropy["Group"] == group) & (entropy["Year"] >= 2)]
        print(f"  {group}:  raw H_norm={g['Raw_H_norm'].mean():.2f}  "
              f"EBE={g['EBE'].mean():.2f}  "
              f"halluc={g['Hallucination_Rate'].mean():.1%}")

    print("\n--- Cumulative Relocation at Year 10 ---")
    for group in ["Group_A", "Group_B", "Group_C"]:
        print(f"  {group}: {reloc_data[group][-1]:.0f}%")


if __name__ == "__main__":
    main()
