"""
Figure S3: Economic Hallucination Case Study (SI)
===================================================
Compares FLC (forward-looking conservative) agent demand trajectories:
  v4 = pre-fix (economic hallucination bug: cascading reduce_acreage -> 0)
  v6 = post-fix (P0 MIN_UTIL=10% floor + P1 diminishing taper)

Shows all 5 FLC agents side-by-side with 10% floor annotation.

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
ROOT = SCRIPT_DIR.parents[3]

V4_LOG = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v4" / "simulation_log.csv"
V6_LOG = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v6" / "simulation_log.csv"

for p in [V4_LOG, V6_LOG]:
    if not p.exists():
        print(f"ERROR: {p} not found.")
        sys.exit(1)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9, "axes.labelsize": 10, "axes.titlesize": 10,
    "legend.fontsize": 7.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "axes.linewidth": 0.6,
})

# Okabe-Ito palette for FLC agents
AGENT_COLORS = {
    "GilaMonsterFarms": "#D55E00",
    "Powers": "#0072B2",
    "Bard Unit": "#009E73",
    "PVIDDiversionAG": "#E69F00",
    "UtahUsesAboveGreenRiverConfluence_UtahAgDNRProjects": "#CC79A7",
}
SHORT_NAMES = {
    "GilaMonsterFarms": "GilaMonster",
    "Powers": "Powers",
    "Bard Unit": "Bard Unit",
    "PVIDDiversionAG": "PVIDD AG",
    "UtahUsesAboveGreenRiverConfluence_UtahAgDNRProjects": "UtahAg DNR",
}

# Load data
v4 = pd.read_csv(V4_LOG)
v6 = pd.read_csv(V6_LOG)

FLC_AGENTS = list(AGENT_COLORS.keys())
YEAR_OFFSET = 2018

fig, (ax_v4, ax_v6) = plt.subplots(1, 2, figsize=(7.0, 3.5), constrained_layout=True,
                                     sharey=True)

for ax, df, version, title in [
    (ax_v4, v4, "v4", "(a) v4: Pre-Fix (Economic Hallucination)"),
    (ax_v6, v6, "v6", "(b) v6: Post-Fix (P0+P1 Governance)"),
]:
    ax.set_title(title, fontweight="bold", loc="left", fontsize=9)

    for agent in FLC_AGENTS:
        adf = df[df["agent_id"] == agent].sort_values("year")
        if adf.empty:
            continue
        wr = adf["water_right"].iloc[0]
        pct = adf["request"].values / wr * 100
        cal_years = adf["year"].values + YEAR_OFFSET
        ax.plot(cal_years, pct, color=AGENT_COLORS[agent], lw=1.5,
                label=SHORT_NAMES[agent])

    # 10% floor
    ax.axhline(10, color="#555555", ls=":", lw=1.0, alpha=0.7)
    ax.text(2060, 12, "MIN_UTIL floor (10%)", fontsize=6.5, color="#555555",
            ha="right", va="bottom", fontstyle="italic")

    # Zero line
    ax.axhline(0, color="black", ls="-", lw=0.3, alpha=0.3)

    ax.set_xlabel("Calendar Year")
    ax.set_xlim(2019, 2060)
    ax.set_ylim(-5, 110)
    ax.grid(True, alpha=0.2)

ax_v4.set_ylabel("Demand (% of water right)")
ax_v6.legend(loc="upper right", framealpha=0.9, edgecolor="none", fontsize=7)

# Annotate collapse in v4
ax_v4.annotate("Cascading\ncollapse", xy=(2045, 3), xytext=(2035, 50),
               fontsize=7, color="#D55E00", fontstyle="italic", ha="center",
               arrowprops=dict(arrowstyle="->", color="#D55E00", lw=0.8))

# Annotate stabilisation in v6
ax_v6.annotate("Stabilizes\nabove floor", xy=(2050, 15), xytext=(2040, 55),
               fontsize=7, color="#0072B2", fontstyle="italic", ha="center",
               arrowprops=dict(arrowstyle="->", color="#0072B2", lw=0.8))

out_png = SCRIPT_DIR / "fig_s3_econ_hallucination.png"
out_pdf = SCRIPT_DIR / "fig_s3_econ_hallucination.pdf"
fig.savefig(out_png)
fig.savefig(out_pdf)
plt.close()
print(f"Saved: {out_png}")
print(f"Saved: {out_pdf}")

# Summary
print("\n--- FLC Demand at Year 42 (% of water right) ---")
for agent in FLC_AGENTS:
    v4_row = v4[(v4["agent_id"] == agent) & (v4["year"] == 42)]
    v6_row = v6[(v6["agent_id"] == agent) & (v6["year"] == 42)]
    if not v4_row.empty and not v6_row.empty:
        wr = v4_row["water_right"].iloc[0]
        v4_pct = v4_row["request"].iloc[0] / wr * 100
        v6_pct = v6_row["request"].iloc[0] / wr * 100
        print(f"  {SHORT_NAMES[agent]:12s}: v4={v4_pct:5.1f}%  v6={v6_pct:5.1f}%  WR={wr:,.0f}")
