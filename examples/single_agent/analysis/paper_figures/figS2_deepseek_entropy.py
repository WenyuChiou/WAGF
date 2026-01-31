"""
SAGE Paper — Figure S2: DeepSeek R1 Entropy Time Series
========================================================
4×3 panel grid: 4 model sizes × 3 governance groups.
Shows H_norm over simulation years with dominant action annotations.

Key finding: DeepSeek R1 1.5B loses agents via relocation (100→2),
8B collapses to Elevation (97%), 14B collapses to Elevation (87%),
while governance (B/C) maintains diversity across all sizes.

Usage:
  python figS2_deepseek_entropy.py
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------- paths ----------
SCRIPT_DIR = Path(__file__).resolve().parent
SQ2 = SCRIPT_DIR.parents[0] / "SQ2_Final_Results"

# ---------- style ----------
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

C_A = "#D55E00"
C_B = "#0072B2"
C_C = "#009E73"

MODELS = [
    ("deepseek_r1_1_5b", "DeepSeek R1 1.5B"),
    ("deepseek_r1_8b", "DeepSeek R1 8B"),
    ("deepseek_r1_14b", "DeepSeek R1 14B"),
    ("deepseek_r1_32b", "DeepSeek R1 32B"),
]

GROUPS = [
    ("Group_A", C_A, "A (ungoverned)", "o"),
    ("Group_B", C_B, "B (gov + window)", "s"),
    ("Group_C", C_C, "C (gov + memory)", "^"),
]


def main():
    csv_path = SQ2 / "yearly_entropy_audited.csv"
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)

    df = pd.read_csv(csv_path)

    fig, axes = plt.subplots(4, 1, figsize=(5.5, 8.0), sharex=True,
                             constrained_layout=True)

    for row, (model_id, model_label) in enumerate(MODELS):
        ax = axes[row]
        mdf = df[df["Model"] == model_id]

        for group_id, color, glabel, marker in GROUPS:
            gdf = mdf[mdf["Group"] == group_id].sort_values("Year")
            if gdf.empty:
                continue

            years = gdf["Year"].values
            hnorm = gdf["Shannon_Entropy_Norm"].values
            active = gdf["Active_Agents"].values
            dominant = gdf["Dominant_Action"].values

            ax.plot(years, hnorm, color=color, marker=marker,
                    markersize=3, linewidth=1.5, label=glabel)

            # Annotate agent loss for Group A
            if group_id == "Group_A" and active[-1] < 50:
                ax.annotate(
                    f"N={active[-1]}",
                    xy=(years[-1], hnorm[-1]),
                    xytext=(years[-1] + 0.3, hnorm[-1] + 0.08),
                    fontsize=6, color=color,
                    arrowprops=dict(arrowstyle="->", color=color, lw=0.5),
                )

            # Annotate dominant action at year 10 for Group A
            if group_id == "Group_A" and len(years) >= 8:
                last_dom = dominant[-1]
                last_freq = gdf["Dominant_Freq"].values[-1]
                if last_freq > 0.7:
                    ax.annotate(
                        f"{last_dom} ({last_freq:.0%})",
                        xy=(years[-1], hnorm[-1]),
                        xytext=(years[-1] - 2, hnorm[-1] - 0.12),
                        fontsize=6, color=color, ha="center",
                        arrowprops=dict(arrowstyle="->", color=color, lw=0.5),
                    )

        ax.set_ylabel("H$_{norm}$")
        ax.set_ylim(-0.02, 1.0)
        ax.set_title(model_label, fontweight="bold", loc="left")
        ax.grid(True, alpha=0.2)

        # Flood markers
        for fy in [3, 4, 9]:
            ax.axvline(x=fy, color="gray", linestyle=":", linewidth=0.5, alpha=0.4)

        if row == 0:
            ax.legend(loc="upper right", framealpha=0.9, edgecolor="none")

    axes[-1].set_xlabel("Simulation Year")
    axes[-1].set_xticks(range(1, 11))

    fig.suptitle("Figure S2: DeepSeek R1 — Entropy by Model Size",
                 fontsize=11, fontweight="bold", y=1.01)

    # Save
    out_png = SCRIPT_DIR / "figS2_deepseek_entropy.png"
    fig.savefig(out_png, dpi=300)
    print(f"Saved: {out_png}")

    out_pdf = SCRIPT_DIR / "figS2_deepseek_entropy.pdf"
    fig.savefig(out_pdf)
    print(f"Saved: {out_pdf}")

    plt.close()


if __name__ == "__main__":
    main()
