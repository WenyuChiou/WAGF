"""
SAGE Paper — Irrigation Case Study Figure
==========================================
Three-panel figure demonstrating framework effectiveness for irrigation domain.

Panel (a): Demand trajectories by cluster vs CRSS baseline
           Shows cluster differentiation and CRSS-scale demand
Panel (b): Annual decision composition (stacked bars)
           Shows agents respond dynamically with diverse actions
Panel (c): Governance enforcement — rule triggers + curtailment
           Shows the governance layer actively prevents infeasible actions

Usage:
    python fig_irrigation_proof.py
"""

from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import glob as globmod

# ── paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parents[3]  # governed_broker_framework root
SIM_LOG = BASE / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v4" / "simulation_log.csv"
GOV_AUDIT = BASE / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v4" / "irrigation_farmer_governance_audit.csv"
CRSS_DIR = BASE / "ref" / "CRSS_DB" / "CRSS_DB"

# ── style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Okabe-Ito palette
C_AGG = "#D55E00"   # vermillion — aggressive
C_FLC = "#0072B2"   # blue — forward-looking conservative
C_MYO = "#009E73"   # teal — myopic conservative
C_CRSS = "#555555"  # dark gray — CRSS baseline

ACTION_COLORS = {
    "increase_demand": "#D55E00",
    "maintain_demand": "#56B4E9",
    "decrease_demand": "#009E73",
    "adopt_efficiency": "#F0E442",
    "reduce_acreage": "#CC79A7",
}
ACTION_LABELS = {
    "increase_demand": "Increase",
    "maintain_demand": "Maintain",
    "decrease_demand": "Decrease",
    "adopt_efficiency": "Efficiency",
    "reduce_acreage": "Reduce acreage",
}
ACTION_ORDER = ["increase_demand", "maintain_demand", "decrease_demand",
                "adopt_efficiency", "reduce_acreage"]


def load_crss_ub_baseline():
    """Load CRSS Upper Basin baseline. No year column; row index = year."""
    pattern = str(CRSS_DIR / "Within_Group_Div" / "Annual_*_Div_req.csv")
    files = sorted(globmod.glob(pattern))
    yearly_totals = defaultdict(float)
    for f in files:
        df = pd.read_csv(f, encoding="utf-8")
        for row_idx, row in df.iterrows():
            yr = int(row_idx) + 1
            for col in df.columns:
                yearly_totals[yr] += float(row[col])
    return yearly_totals


def load_crss_lb_baseline():
    """Load CRSS Lower Basin baseline from RiverWare txt files."""
    lb_dir = CRSS_DIR / "LB_Baseline_DB"
    yearly_totals = defaultdict(float)
    for txt_file in sorted(lb_dir.glob("*_Div_req.txt")):
        with open(txt_file, encoding="utf-8") as f:
            lines = f.readlines()
        data_lines = [l.strip() for l in lines[6:] if l.strip()]
        month_idx = 0
        year_vals = defaultdict(float)
        for val_str in data_lines:
            try:
                val = float(val_str)
            except ValueError:
                continue
            year_num = month_idx // 12 + 1
            year_vals[year_num] += val
            month_idx += 1
        for yr, total in year_vals.items():
            yearly_totals[yr] += total
    return yearly_totals


def main():
    # ── Load simulation data ──
    df = pd.read_csv(SIM_LOG, encoding="utf-8")
    years = sorted(df["year"].unique())
    n_years = len(years)

    # ── Panel (a) data: Demand by cluster ──
    clusters = ["aggressive", "forward_looking_conservative", "myopic_conservative"]
    demand_by_cluster = {}
    for c in clusters:
        cdf = df[df["cluster"] == c]
        demand_by_cluster[c] = cdf.groupby("year")["request"].sum().reindex(years).values

    sage_total = df.groupby("year")["request"].sum().reindex(years).values

    # CRSS baselines
    crss_ub = load_crss_ub_baseline()
    crss_lb = load_crss_lb_baseline()
    crss_total_vals = np.array([crss_ub.get(y, 0) + crss_lb.get(y, 0) for y in years])

    # ── Panel (b) data: Decision composition ──
    decision_counts = defaultdict(lambda: defaultdict(int))
    for _, row in df.iterrows():
        y = row["year"]
        d = row["yearly_decision"]
        decision_counts[y][d] += 1

    # ── Panel (c) data: Governance from audit CSV ──
    gdf = pd.read_csv(GOV_AUDIT, encoding="utf-8-sig")
    # Rule triggers: rows where retry_count > 0 (governance challenged the agent)
    triggered = gdf[gdf["retry_count"] > 0]
    trig_by_year = triggered.groupby("year").size().reindex(range(1, 43), fill_value=0)
    # Rejected (retry exhausted): status == REJECTED
    rejected = gdf[gdf["status"] == "REJECTED"]
    rej_by_year = rejected.groupby("year").size().reindex(range(1, 43), fill_value=0)

    # Curtailment
    curt_by_year = df.groupby("year")["curtailment_ratio"].mean() * 100

    # ════════════════════════════════════════════════════════════════════
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.3), constrained_layout=True)

    # ════════ Panel (a): Demand Trajectories ════════
    ax = axes[0]
    ax.set_title("(a) Demand vs CRSS Baseline", fontweight="bold", loc="left", fontsize=9)

    ax.plot(years, crss_total_vals / 1e6, color=C_CRSS, linewidth=2.0, linestyle="--",
            label="CRSS baseline", zorder=5)
    ax.plot(years, sage_total / 1e6, color="black", linewidth=1.8,
            label="SAGE total", zorder=4)

    # Cluster stacked area
    agg = demand_by_cluster["aggressive"] / 1e6
    flc = demand_by_cluster["forward_looking_conservative"] / 1e6
    myo = demand_by_cluster["myopic_conservative"] / 1e6
    ax.fill_between(years, 0, agg, alpha=0.3, color=C_AGG, label=f"Aggressive (n=67)")
    ax.fill_between(years, agg, agg + flc, alpha=0.3, color=C_FLC, label=f"FLC (n=5)")
    ax.fill_between(years, agg + flc, agg + flc + myo, alpha=0.3, color=C_MYO, label=f"Myopic (n=6)")

    ax.set_xlabel("Simulation Year")
    ax.set_ylabel("Annual Demand (MAF)")
    ax.set_xlim(1, 42)
    ax.set_ylim(0, max(sage_total.max(), crss_total_vals.max()) / 1e6 * 1.15)
    ax.legend(loc="upper right", framealpha=0.9, edgecolor="none", fontsize=6)
    ax.grid(True, alpha=0.2)

    # ════════ Panel (b): Decision Composition ════════
    ax = axes[1]
    ax.set_title("(b) Annual Decision Mix", fontweight="bold", loc="left", fontsize=9)

    bottoms = np.zeros(n_years)
    for action in ACTION_ORDER:
        vals = np.array([decision_counts[y].get(action, 0) for y in years])
        fracs = vals / 78 * 100
        ax.bar(years, fracs, bottom=bottoms, width=0.85,
               color=ACTION_COLORS[action], label=ACTION_LABELS[action],
               edgecolor="none")
        bottoms += fracs

    ax.set_xlabel("Simulation Year")
    ax.set_ylabel("Agent Decisions (%)")
    ax.set_xlim(0, 43)
    ax.set_ylim(0, 105)
    ax.legend(loc="center right", framealpha=0.9, edgecolor="none", fontsize=6)
    ax.grid(True, alpha=0.15, axis="y")

    # ════════ Panel (c): Governance + Curtailment ════════
    ax = axes[2]
    ax.set_title("(c) Governance & Curtailment", fontweight="bold", loc="left", fontsize=9)

    # Rule trigger bars (retried decisions)
    ax.bar(range(1, 43), trig_by_year.values, width=0.8,
           color="#CC79A7", alpha=0.6,
           label=f"Governance challenges (n={int(trig_by_year.sum())})",
           edgecolor="none")
    # Rejected overlay (retry exhausted)
    ax.bar(range(1, 43), rej_by_year.values, width=0.8,
           color="#882255", alpha=0.9,
           label=f"Rejected after retry (n={int(rej_by_year.sum())})",
           edgecolor="none")

    ax.set_xlabel("Simulation Year")
    ax.set_ylabel("Governance Events")
    ax.set_xlim(0, 43)

    # Curtailment on twin axis
    ax2 = ax.twinx()
    ax2.plot(years, curt_by_year.values, color="#E69F00", linewidth=1.5,
             marker=".", markersize=3, label="Curtailment ratio", zorder=5)
    ax2.set_ylabel("Mean Curtailment (%)", color="#E69F00", fontsize=8)
    ax2.tick_params(axis="y", labelcolor="#E69F00")
    ax2.set_ylim(-0.5, 14)

    # Combined legend
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", framealpha=0.9,
              edgecolor="none", fontsize=6)
    ax.grid(True, alpha=0.15, axis="y")

    # ── Save ──
    out = SCRIPT_DIR / "fig_irrigation_proof.png"
    fig.savefig(out, dpi=300)
    print(f"Saved: {out}")
    plt.close()


if __name__ == "__main__":
    main()
