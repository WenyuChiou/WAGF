#!/usr/bin/env python3
"""
Nature Water Fig 3: Cumulative Adaptation State Evolution (Flood Domain).

Three-panel stacked bar chart comparing protection state trajectories:
  (a) Rule-based PMT baseline
  (b) Ungoverned language agent (Group A)
  (c) Governed language agent (Group B)

All panels: Gemma-3 4B, 100 agents, 10 years, 3 seeds averaged.
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
})

# ── Paths ──────────────────────────────────────────────────────────────────
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results")

CONFIGS = {
    "Rule-based PMT": {
        "paths": [BASE / "rulebased" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
    "Ungoverned language agent": {
        "paths": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_A" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
    "Governed language agent": {
        "paths": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_B" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
}

# ── State categories (cumulative protection state) ─────────────────────────
STATES = ["No protection", "Insurance only", "Elevation only",
          "Insurance + Elevation", "Relocated"]
COLORS = {
    "No protection":         "#d9d9d9",   # light grey
    "Insurance only":        "#4292c6",   # blue
    "Elevation only":        "#ef6548",   # orange-red
    "Insurance + Elevation": "#78c679",   # green
    "Relocated":             "#8c6bb1",   # purple
}

def classify_state_from_columns(df):
    """Classify protection state directly from CSV state columns.

    All three CSV formats (rulebased, ungoverned, governed) record
    post-decision state columns: has_insurance, elevated, relocated.
    Insurance is annual (lapses if not renewed); elevation is permanent.
    These columns already reflect lapse logic from the simulation engine,
    so we read them directly rather than inferring from decisions.

    Returns DataFrame with columns: agent_id, year, state
    """
    records = []
    for _, row in df.iterrows():
        aid = row["agent_id"]
        yr = row["year"]

        # Parse boolean columns (handle True/False/nan/1/0 variants)
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


def compute_yearly_counts(state_df, n_agents=100):
    """Compute per-year state proportions."""
    years = sorted(state_df["year"].unique())
    counts = {s: [] for s in STATES}

    for yr in years:
        yr_states = state_df[state_df["year"] == yr]["state"]
        vc = yr_states.value_counts()
        for s in STATES:
            counts[s].append(vc.get(s, 0))

    return years, counts


def main():
    OUT = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\paper\nature_water\figures")
    OUT.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(10, 4), sharey=True)

    panel_labels = ["a", "b", "c"]

    for idx, (label, cfg) in enumerate(CONFIGS.items()):
        ax = axes[idx]

        # Average across seeds
        all_counts = {s: [] for s in STATES}
        all_years = None

        for csv_path in cfg["paths"]:
            if not csv_path.exists():
                print(f"  WARNING: {csv_path} not found, skipping")
                continue

            df = pd.read_csv(csv_path, encoding="utf-8")
            state_df = classify_state_from_columns(df)
            years, counts = compute_yearly_counts(state_df)
            all_years = years

            for s in STATES:
                all_counts[s].append(counts[s])

        if all_years is None:
            print(f"  ERROR: No data for {label}")
            continue

        # Average across seeds
        avg_counts = {}
        for s in STATES:
            if all_counts[s]:
                avg_counts[s] = np.mean(all_counts[s], axis=0)
            else:
                avg_counts[s] = np.zeros(len(all_years))

        # Stacked bar
        bottom = np.zeros(len(all_years))
        x = np.arange(len(all_years))

        for s in STATES:
            vals = avg_counts[s]
            ax.bar(x, vals, bottom=bottom, color=COLORS[s], label=s, width=0.8,
                   edgecolor="white", linewidth=0.3)
            bottom += vals

        ax.set_xlabel("Simulation year", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in all_years], fontsize=7)
        ax.set_title(f"({panel_labels[idx]}) {label}", fontsize=9, fontweight="bold",
                     loc="left", pad=8)

        if idx == 0:
            ax.set_ylabel("Number of agents", fontsize=8)

        ax.set_ylim(0, 105)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
        ax.grid(axis="y", linestyle="--", alpha=0.3, zorder=0)
        ax.set_axisbelow(True)

    # Single legend at bottom
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=7,
               frameon=False, bbox_to_anchor=(0.5, -0.02))

    plt.suptitle("Flood-adaptation trajectories across agent types",
                 fontsize=10, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.12)

    for ext in ["png", "pdf"]:
        out_path = OUT / f"Fig3_cumulative_adaptation.{ext}"
        fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
        print(f"  Saved: {out_path}")

    plt.close()
    print("Done.")


if __name__ == "__main__":
    main()
