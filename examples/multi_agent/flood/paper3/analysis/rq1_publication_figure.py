#!/usr/bin/env python3
"""
RQ1 Publication Figure: Traditional ABM vs LLM-ABM Adaptation Trajectories

Generates a 2x3 panel figure comparing yearly action rates between:
  - Traditional ABM (Bayesian regression + Bernoulli, ~52K HH, single run)
  - LLM-ABM (WAGF hybrid_v2, Gemma 3 4B, 400 HH, 3 seeds)

Row 1 (Owner): FI, EH, BP
Row 2 (Renter): FI, RL, DN

Each panel shows Traditional as dashed line, LLM mean as solid line with
±1 SD shading, plus MAD and Pearson r annotations.

Outputs:
  - paper3/results/paper3_hybrid_v2/analysis/rq1_publication_figure.png
  - paper3/analysis/tables/rq1_summary_statistics.csv
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy import stats
from collections import defaultdict

warnings.filterwarnings("ignore", category=FutureWarning)

# ===========================================================================
# Paths
# ===========================================================================
BASE = r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood"
TRAD_CSV = os.path.join(
    r"C:\Users\wenyu\OneDrive - Lehigh University\Desktop\Lehigh\NSF-project\ABM\paper\draft\mg_sensitivity\FLOODABM",
    "outputs", "baseline", "baseline", "decisions",
    "action_share_owner_renter_tract_all_years.csv",
)

SEEDS = [42, 123, 456]
LLM_SEED_DIRS = {}
for seed in SEEDS:
    d = os.path.join(BASE, "paper3", "results", "paper3_hybrid_v2",
                     f"seed_{seed}", "gemma3_4b_strict", "raw")
    if os.path.isdir(d):
        LLM_SEED_DIRS[seed] = d

ANALYSIS_DIR = os.path.join(BASE, "paper3", "results", "paper3_hybrid_v2", "analysis")
TABLES_DIR = os.path.join(BASE, "paper3", "analysis", "tables")
os.makedirs(ANALYSIS_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)


# ===========================================================================
# Helpers
# ===========================================================================
def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode())


def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ===========================================================================
# 1. Load Traditional ABM data
# ===========================================================================
safe_print("=" * 70)
safe_print("RQ1 PUBLICATION FIGURE")
safe_print("=" * 70)

safe_print("\n[1] Loading Traditional ABM data...")
trad_raw = pd.read_csv(TRAD_CSV, encoding="utf-8-sig")

# Aggregate across tracts per year
trad_rows = []
for yr in sorted(trad_raw["year"].unique()):
    ydf = trad_raw[trad_raw["year"] == yr]
    tot_o = ydf["owner_N_total"].sum()
    tot_r = ydf["renter_N_total"].sum()
    trad_rows.append({
        "year": int(yr),
        "owner_FI": ydf["owner_n_FI"].sum() / tot_o,
        "owner_EH": ydf["owner_n_EH"].sum() / tot_o,
        "owner_BP": ydf["owner_n_BP"].sum() / tot_o,
        "owner_DN": ydf["owner_n_DN"].sum() / tot_o,
        "renter_FI": ydf["renter_n_FI"].sum() / tot_r,
        "renter_RL": ydf["renter_n_RL"].sum() / tot_r,
        "renter_DN": ydf["renter_n_DN"].sum() / tot_r,
    })
trad = pd.DataFrame(trad_rows).set_index("year")
safe_print(f"  Loaded {len(trad)} years (2011-2023), 27 tracts aggregated")


# ===========================================================================
# 2. Load LLM-ABM data (3 seeds)
# ===========================================================================
safe_print("\n[2] Loading LLM-ABM traces...")

SKILL_MAP_OWNER = {
    "buy_insurance": "owner_FI",
    "elevate_house": "owner_EH",
    "buyout_program": "owner_BP",
    "do_nothing": "owner_DN",
}
SKILL_MAP_RENTER = {
    "buy_contents_insurance": "renter_FI",
    "relocate": "renter_RL",
    "do_nothing": "renter_DN",
}


def load_llm_seed(seed_dir):
    """Compute yearly action rates for one seed."""
    owners = load_jsonl(os.path.join(seed_dir, "household_owner_traces.jsonl"))
    renters = load_jsonl(os.path.join(seed_dir, "household_renter_traces.jsonl"))

    rows = []
    all_years = sorted(set(t["year"] for t in owners + renters))

    for yr in all_years:
        cal_year = 2010 + yr  # sim year -> calendar year

        # --- owners ---
        o_yr = [t for t in owners if t["year"] == yr]
        o_n = len(o_yr)
        o_counts = defaultdict(int)
        for t in o_yr:
            approved = t.get("approved_skill", {})
            skill = approved.get("skill_name", "do_nothing")
            if approved.get("status", "") == "REJECTED":
                skill = "do_nothing"
            col = SKILL_MAP_OWNER.get(skill, "owner_DN")
            o_counts[col] += 1

        # --- renters ---
        r_yr = [t for t in renters if t["year"] == yr]
        r_n = len(r_yr)
        r_counts = defaultdict(int)
        for t in r_yr:
            approved = t.get("approved_skill", {})
            skill = approved.get("skill_name", "do_nothing")
            if approved.get("status", "") == "REJECTED":
                skill = "do_nothing"
            col = SKILL_MAP_RENTER.get(skill, "renter_DN")
            r_counts[col] += 1

        row = {"year": cal_year}
        for col in ["owner_FI", "owner_EH", "owner_BP", "owner_DN"]:
            row[col] = o_counts[col] / max(o_n, 1)
        for col in ["renter_FI", "renter_RL", "renter_DN"]:
            row[col] = r_counts[col] / max(r_n, 1)
        rows.append(row)

    return pd.DataFrame(rows).set_index("year")


llm_seeds = {}
for seed, sdir in sorted(LLM_SEED_DIRS.items()):
    llm_seeds[seed] = load_llm_seed(sdir)
    safe_print(f"  seed_{seed}: {len(llm_seeds[seed])} years loaded")

n_seeds = len(llm_seeds)
safe_print(f"  Total seeds: {n_seeds}")

# Combine into mean / std
ALL_ACTIONS = ["owner_FI", "owner_EH", "owner_BP", "owner_DN",
               "renter_FI", "renter_RL", "renter_DN"]

llm_concat = pd.concat(
    [df[ALL_ACTIONS] for df in llm_seeds.values()],
    keys=llm_seeds.keys(), names=["seed", "year"],
)
llm_mean = llm_concat.groupby("year").mean()
llm_std = llm_concat.groupby("year").std().fillna(0)


# ===========================================================================
# 3. Compute statistics for each panel
# ===========================================================================
safe_print("\n[3] Computing comparison statistics...")

years = trad.index.values  # 2011-2023

PANELS = [
    # (action_col, row, col, label, panel_letter)
    ("owner_FI", 0, 0, "Flood Insurance (FI)", "(a)"),
    ("owner_EH", 0, 1, "Elevation (EH)", "(b)"),
    ("owner_BP", 0, 2, "Buyout Program (BP)", "(c)"),
    ("renter_FI", 1, 0, "Contents Insurance (FI)", "(d)"),
    ("renter_RL", 1, 1, "Relocation (RL)", "(e)"),
    ("renter_DN", 1, 2, "Do Nothing (DN)", "(f)"),
]

summary_rows = []

for action, row_i, col_i, label, letter in PANELS:
    agent_type = "owner" if action.startswith("owner_") else "renter"
    short_action = action.split("_", 1)[1]

    # Align years
    common_years = sorted(set(years) & set(llm_mean.index))
    trad_vals = trad.loc[common_years, action].values
    llm_vals = llm_mean.loc[common_years, action].values
    llm_sd_vals = llm_std.loc[common_years, action].values

    # MAD
    mad = np.mean(np.abs(trad_vals - llm_vals))
    if mad < 0.05:
        classification = "CONVERGE"
    elif mad < 0.10:
        classification = "MODERATE"
    else:
        classification = "DIVERGE"

    # Pearson r
    if len(common_years) >= 3 and np.std(trad_vals) > 1e-10 and np.std(llm_vals) > 1e-10:
        r_val, p_val = stats.pearsonr(trad_vals, llm_vals)
    else:
        r_val, p_val = np.nan, np.nan

    summary_rows.append({
        "action": short_action,
        "agent_type": agent_type,
        "trad_mean": round(np.mean(trad_vals), 4),
        "llm_mean": round(np.mean(llm_vals), 4),
        "llm_sd": round(np.mean(llm_sd_vals), 4),
        "MAD": round(mad, 4),
        "pearson_r": round(r_val, 4) if not np.isnan(r_val) else np.nan,
        "pearson_p": round(p_val, 4) if not np.isnan(p_val) else np.nan,
        "classification": classification,
    })

    safe_print(f"  {action:>12}: MAD={mad:.3f} ({classification}), "
               f"r={r_val:+.3f}, p={p_val:.4f}" if not np.isnan(r_val)
               else f"  {action:>12}: MAD={mad:.3f} ({classification}), r=N/A")


# ===========================================================================
# 4. Generate publication figure
# ===========================================================================
safe_print("\n[4] Generating publication figure...")

# Style
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.dpi": 150,
})

C_TRAD = "#D55E00"  # vermillion (colorblind-safe)
C_LLM = "#0072B2"   # blue (colorblind-safe)

fig, axes = plt.subplots(2, 3, figsize=(14, 8))

for panel_idx, (action, row_i, col_i, label, letter) in enumerate(PANELS):
    ax = axes[row_i, col_i]

    common_years = sorted(set(years) & set(llm_mean.index))
    x = np.array(common_years)
    trad_vals = trad.loc[common_years, action].values
    llm_m = llm_mean.loc[common_years, action].values
    llm_s = llm_std.loc[common_years, action].values

    # Traditional ABM: dashed red line
    ax.plot(x, trad_vals * 100, linestyle="--", color=C_TRAD, linewidth=1.8,
            marker="s", markersize=4, markerfacecolor="white", markeredgecolor=C_TRAD,
            markeredgewidth=1.2, label="Traditional ABM", zorder=3)

    # LLM-ABM: solid blue line with shading
    ax.plot(x, llm_m * 100, linestyle="-", color=C_LLM, linewidth=1.8,
            marker="o", markersize=4, markerfacecolor="white", markeredgecolor=C_LLM,
            markeredgewidth=1.2, label=f"LLM-ABM (n={n_seeds})", zorder=3)

    if n_seeds > 1:
        ax.fill_between(x, (llm_m - llm_s) * 100, (llm_m + llm_s) * 100,
                        alpha=0.18, color=C_LLM, zorder=1)

    # Panel title with letter
    agent_label = "Owner" if row_i == 0 else "Renter"
    ax.set_title(f"{letter} {agent_label}: {label}", fontsize=11, fontweight="bold",
                 loc="left", pad=8)

    # Axes
    ax.set_ylabel("Action Rate (%)")
    ax.set_xlabel("Year")
    ax.set_xlim(2010.5, 2023.5)
    ax.set_xticks(x[::2])
    ax.set_xticklabels([str(y) for y in x[::2]], rotation=0)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    # Y-axis: start at 0, set reasonable upper bound
    y_max = max(np.max(trad_vals), np.max(llm_m + llm_s)) * 100
    ax.set_ylim(bottom=0, top=max(y_max * 1.25, 5))

    # Grid
    ax.grid(True, alpha=0.2, linewidth=0.5)
    ax.set_axisbelow(True)

    # Annotation: MAD + classification
    stats_row = summary_rows[panel_idx]
    mad_val = stats_row["MAD"]
    cls_label = stats_row["classification"]
    r_val = stats_row["pearson_r"]
    p_val = stats_row["pearson_p"]

    ann_lines = [f"MAD = {mad_val:.3f} [{cls_label}]"]
    if not np.isnan(r_val):
        sig = "*" if p_val < 0.05 else ""
        ann_lines.append(f"r = {r_val:+.3f}{sig}")

    ann_text = "\n".join(ann_lines)

    # Place annotation in top-right area
    ax.text(0.97, 0.95, ann_text, transform=ax.transAxes,
            fontsize=9, verticalalignment="top", horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="gray", alpha=0.85))

    # Legend only in first panel
    if panel_idx == 0:
        ax.legend(loc="upper left", frameon=True, fancybox=False,
                  edgecolor="gray", framealpha=0.9)

# Adjust layout
fig.tight_layout(h_pad=3.0, w_pad=2.5)

# Save
fig_path = os.path.join(ANALYSIS_DIR, "rq1_publication_figure.png")
fig.savefig(fig_path, dpi=300, bbox_inches="tight", facecolor="white")
safe_print(f"  Saved figure: {fig_path}")
plt.close(fig)


# ===========================================================================
# 5. Save summary statistics table
# ===========================================================================
safe_print("\n[5] Saving summary statistics...")
summary_df = pd.DataFrame(summary_rows)
summary_csv = os.path.join(TABLES_DIR, "rq1_summary_statistics.csv")
summary_df.to_csv(summary_csv, index=False, encoding="utf-8")
safe_print(f"  Saved table: {summary_csv}")

safe_print("\n" + "=" * 70)
safe_print("[DONE] RQ1 publication figure and summary table generated.")
safe_print("=" * 70)
