"""
Skill Distribution by Basin — Dual-Panel Stacked Bar Chart
============================================================
78 agents x 42 years (production v20, Gemma 3 4B, seed 42)

Panel (a): Upper Basin (56 agents)
Panel (b): Lower Basin (22 agents)

Five skill categories with Lake Mead elevation overlay (right axis).
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ── Paths ──
SCRIPT_DIR = pathlib.Path(__file__).parent
ROOT = SCRIPT_DIR.parents[2]
SIM_LOG = ROOT / "examples" / "irrigation_abm" / "results" / "production_v20_42yr" / "simulation_log.csv"
METRICS_JSON = SCRIPT_DIR / "v20_metrics.json"

# ── Load data ──
sim = pd.read_csv(SIM_LOG, encoding="utf-8")
with open(METRICS_JSON, "r", encoding="utf-8") as f:
    metrics = json.load(f)

YEAR_OFFSET = 2018

# Mead elevation
mead_by_year = metrics["shortage_tiers"]["mead_by_year"]

# ── Skill config (bottom → top: decrease → maintain → increase) ──
skill_order = ["decrease_large", "decrease_small", "maintain_demand", "increase_small", "increase_large"]
skill_labels = ["Decrease large", "Decrease small", "Maintain", "Increase small", "Increase large"]
skill_colors = ["#3A8A7B", "#8CC5B8", "#E6E1DC", "#E8B4A2", "#C47A6C"]

basins = [
    ("upper_basin", "Upper Basin", 56, "(a)"),
    ("lower_basin", "Lower Basin", 22, "(b)"),
]

# ── WRR Style ──
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.linewidth": 0.5,
})

# ── Figure ──
fig, axes = plt.subplots(
    2, 1, figsize=(7.5, 5.5),
    constrained_layout=True,
)

for ax, (basin_val, basin_name, n_agents, panel_label) in zip(axes, basins):
    sub = sim[sim["basin"] == basin_val]
    ct = pd.crosstab(sub["year"], sub["yearly_decision"])
    for s in skill_order:
        if s not in ct.columns:
            ct[s] = 0
    ct = ct[skill_order]

    years = ct.index.values
    cal_years = years + YEAR_OFFSET
    pct = ct.div(ct.sum(axis=1), axis=0) * 100

    # Stacked bars — edge-to-edge
    bottom = np.zeros(len(years))
    for skill, label, color in zip(skill_order, skill_labels, skill_colors):
        vals = pct[skill].values
        ec = "#FFFFFF" if skill == "maintain_demand" else color
        ax.bar(cal_years, vals, bottom=bottom, width=1.0,
               color=color, edgecolor=ec, linewidth=0.25,
               label=label, zorder=3)
        bottom += vals

    ax.set_ylabel("Agents (%)")
    ax.set_title(f"{panel_label} {basin_name} (n = {n_agents})",
                 fontweight="bold", loc="left", fontsize=10)
    ax.set_xlim(2018.5, 2060.5)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(25))
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.grid(True, axis="y", alpha=0.12, linewidth=0.4, zorder=0)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    # ── Right axis: Lake Mead elevation ──
    ax2 = ax.twinx()
    mead_vals = [mead_by_year[str(y)] for y in years]
    ax2.plot(cal_years, mead_vals, color="#2B4C7E", linewidth=1.6,
             zorder=5, alpha=0.85)
    ax2.set_ylabel("Elevation (ft)", color="#2B4C7E", fontsize=9)
    ax2.tick_params(axis="y", colors="#2B4C7E", labelsize=7.5)
    ax2.set_ylim(980, 1200)
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(50))
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color("#2B4C7E")
    ax2.spines["right"].set_linewidth(0.5)

axes[-1].set_xlabel("Calendar Year")

# Legend — horizontal, inside top-left of panel (a)
handles, labels = axes[0].get_legend_handles_labels()
# Add Mead line to legend
from matplotlib.lines import Line2D
mead_handle = Line2D([0], [0], color="#2B4C7E", linewidth=1.6, alpha=0.85)
all_handles = handles[::-1] + [mead_handle]
all_labels = labels[::-1] + ["Lake Mead"]

axes[0].legend(all_handles, all_labels,
               loc="upper left", bbox_to_anchor=(0.0, 1.0),
               ncol=6, frameon=True, fancybox=False,
               framealpha=0.92, edgecolor="none",
               fontsize=6.5, handlelength=1.0, columnspacing=0.8,
               handletextpad=0.4, borderpad=0.3)

# ── Save ──
out_png = SCRIPT_DIR / "fig_skill_distribution.png"
out_pdf = SCRIPT_DIR / "fig_skill_distribution.pdf"
fig.savefig(out_png)
fig.savefig(out_pdf)
plt.close()

print(f"[OK] Saved: {out_png}")
print(f"[OK] Saved: {out_pdf}")
