"""
Figure S2: Cumulative Relocation Curves (SI)
=============================================
Standalone relocation figure for supplementary information.
Data: corrected_entropy_gemma3_4b.csv (N_Active column).

AGU/WRR: 300 DPI, serif, Okabe-Ito.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ENTROPY_CSV = SCRIPT_DIR / "corrected_entropy_gemma3_4b.csv"
N_TOTAL = 100
YEARS = np.arange(1, 11)
FLOOD_YEARS = [3, 4, 9]

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9, "axes.labelsize": 10, "axes.titlesize": 10,
    "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "axes.linewidth": 0.6,
})

C_A, C_B, C_C = "#D55E00", "#0072B2", "#009E73"

if not ENTROPY_CSV.exists():
    print(f"ERROR: {ENTROPY_CSV} not found.")
    sys.exit(1)

entropy = pd.read_csv(ENTROPY_CSV)
fig, ax = plt.subplots(figsize=(4.5, 3.5))

for group, color, label, mkr in [
    ("Group_A", C_A, "A (ungoverned)", "o"),
    ("Group_B", C_B, "B (gov. + window)", "s"),
    ("Group_C", C_C, "C (gov. + memory)", "^"),
]:
    g = entropy[entropy["Group"] == group].sort_values("Year")
    cum = (N_TOTAL - g["N_Active"].values) / N_TOTAL * 100.0
    ax.plot(YEARS, cum, color=color, lw=1.8, marker=mkr, ms=4, label=label)

for fy in FLOOD_YEARS:
    ax.axvline(x=fy, color="gray", ls=":", lw=0.6, alpha=0.5)

# Final value annotations
for group, color, data_vals in [
    ("Group_A", C_A, entropy[entropy["Group"] == "Group_A"]),
    ("Group_B", C_B, entropy[entropy["Group"] == "Group_B"]),
    ("Group_C", C_C, entropy[entropy["Group"] == "Group_C"]),
]:
    g = data_vals.sort_values("Year")
    final = (N_TOTAL - g["N_Active"].values[-1]) / N_TOTAL * 100.0
    ax.annotate(f"{final:.0f}%", xy=(10, final), xytext=(10.3, final),
                fontsize=7.5, color=color, fontweight="bold", ha="left", va="center")

ax.set_xlabel("Simulation Year")
ax.set_ylabel("Cumulative Relocation (%)")
ax.set_xlim(0.5, 11.5)
ax.set_ylim(-2, 50)
ax.set_xticks(YEARS)
ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
ax.legend(loc="upper left", framealpha=0.9, edgecolor="none")
ax.grid(True, alpha=0.2)

out = SCRIPT_DIR / "fig_s2_relocation.png"
fig.savefig(out)
fig.savefig(SCRIPT_DIR / "fig_s2_relocation.pdf")
plt.close()
print(f"Saved: {out}")
