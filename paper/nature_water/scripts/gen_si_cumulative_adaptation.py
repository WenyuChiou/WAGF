#!/usr/bin/env python3
"""
Nature Water Fig 3: Cumulative Adaptation State Evolution (Flood Domain).

Three-panel stacked bar chart comparing protection state trajectories:
  (a) Rule-based PMT baseline
  (b) Ungoverned LLM agent
  (c) Governed LLM agent

All panels: Gemma-3 4B, 100 agents, 10 years, 3 seeds averaged.
Relocated is shown as a 5th category; all 5 states sum to 100%.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 7.5,
    'axes.labelsize': 8,
    'axes.titlesize': 9,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
})

# ── Paths ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]
BASE = REPO_ROOT / "examples" / "single_agent" / "results"

CONFIGS = {
    "Rule-based PMT": {
        "paths": [BASE / "rulebased" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
    "Ungoverned LLM agent": {
        "paths": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_A" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
    "Governed LLM agent": {
        "paths": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_B" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
}

# ── State categories — all 5 states sum to 100% ──────────────────────────
ALL_STATES = ["No protection", "Insurance only", "Elevation only",
              "Insurance + Elevation", "Relocated"]

COLORS = {
    "No protection":         "#BBBBBB",
    "Insurance only":        "#0072B2",   # Okabe-Ito blue
    "Elevation only":        "#D55E00",   # Okabe-Ito vermillion
    "Insurance + Elevation": "#009E73",   # Okabe-Ito bluish green
    "Relocated":             "#CC79A7",   # Okabe-Ito reddish purple
}
HATCHES = {
    "No protection":         "",
    "Insurance only":        "///",
    "Elevation only":        "...",
    "Insurance + Elevation": "xxx",
    "Relocated":             "\\\\\\",
}


def classify_state_from_columns(df):
    """Classify protection state directly from CSV state columns."""
    records = []
    for _, row in df.iterrows():
        aid = row["agent_id"]
        yr = row["year"]

        relocated = _as_bool(row.get("relocated", False))
        has_ins = _as_bool(row.get("has_insurance", False))
        elevated = _as_bool(row.get("elevated", False))

        if relocated:
            state = "Relocated"
        elif has_ins and elevated:
            state = "Insurance + Elevation"
        elif elevated:
            state = "Elevation only"
        elif has_ins:
            state = "Insurance only"
        else:
            state = "No protection"

        records.append({"agent_id": aid, "year": yr, "state": state})

    return pd.DataFrame(records)


def _as_bool(val):
    """Convert various boolean representations to Python bool."""
    if pd.isna(val):
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    return str(val).strip().lower() in ("true", "1")


def compute_yearly_percentages(state_df):
    """Compute per-year state percentages over ALL agents (denominator = n_total).

    All 5 states (including Relocated) sum to 100%.
    """
    years = sorted(state_df["year"].unique())
    pct = {s: [] for s in ALL_STATES}

    for yr in years:
        yr_data = state_df[state_df["year"] == yr]
        vc = yr_data["state"].value_counts()
        n_total = len(yr_data)

        for s in ALL_STATES:
            count = vc.get(s, 0)
            pct[s].append(count / n_total * 100 if n_total > 0 else 0)

    return years, pct


def main():
    OUT = REPO_ROOT / "paper" / "nature_water" / "figures"
    OUT.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(7.09, 3.0), sharey=True)

    panel_labels = ["(a)", "(b)", "(c)"]

    for idx, (label, cfg) in enumerate(CONFIGS.items()):
        ax = axes[idx]

        # Collect across seeds
        all_pct = {s: [] for s in ALL_STATES}
        all_years = None

        for csv_path in cfg["paths"]:
            if not csv_path.exists():
                print(f"  WARNING: {csv_path} not found, skipping")
                continue

            df = pd.read_csv(csv_path, encoding="utf-8")
            state_df = classify_state_from_columns(df)
            years, pct = compute_yearly_percentages(state_df)
            all_years = years

            for s in ALL_STATES:
                all_pct[s].append(pct[s])

        if all_years is None:
            print(f"  ERROR: No data for {label}")
            continue

        # Average and std across seeds
        avg_pct = {}
        std_pct = {}
        for s in ALL_STATES:
            if all_pct[s]:
                avg_pct[s] = np.mean(all_pct[s], axis=0)
                std_pct[s] = np.std(all_pct[s], axis=0)
            else:
                avg_pct[s] = np.zeros(len(all_years))
                std_pct[s] = np.zeros(len(all_years))

        # Stacked bar
        bottom = np.zeros(len(all_years))
        x = np.arange(len(all_years))

        for s in ALL_STATES:
            vals = avg_pct[s]
            ax.bar(x, vals, bottom=bottom, color=COLORS[s], label=s, width=0.8,
                   edgecolor="white", linewidth=0.3, hatch=HATCHES[s])
            # Error bars only for categories with meaningful cross-seed variation
            if np.any(std_pct[s] > 1.0):
                ax.errorbar(x, bottom + vals, yerr=std_pct[s],
                            fmt='none', ecolor='#333333', elinewidth=0.5,
                            capsize=1.5, capthick=0.5, zorder=5)
            bottom += vals

        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in all_years], fontsize=7.5)
        ax.set_title(f"$\\bf{{{panel_labels[idx]}}}$ {label}", fontsize=8,
                     fontweight='normal', loc='center', pad=4)

        if idx == 0:
            ax.set_ylabel("Share of agents (%)", fontsize=8.5)

        ax.set_ylim(0, 100)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
        ax.grid(axis="y", linestyle="--", alpha=0.15, zorder=0)
        ax.set_axisbelow(True)

    # Shared x-axis label
    fig.text(0.5, 0.01, 'Simulation year', ha='center', fontsize=8.5)

    # Single legend at bottom — 5 items in one row
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=6.5,
               frameon=False, bbox_to_anchor=(0.5, -0.08))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.20, wspace=0.08)

    for ext in ["png", "pdf"]:
        out_path = OUT / f"Fig3_cumulative_adaptation.{ext}"
        fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
        print(f"  Saved: {out_path}")

    plt.close()
    print("Done.")


if __name__ == "__main__":
    main()
