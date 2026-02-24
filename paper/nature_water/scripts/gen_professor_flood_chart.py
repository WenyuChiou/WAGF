"""
Generate professor-facing flood cumulative adaptation chart.
Shows protection distribution of ACTIVE agents only (relocated subtracted).
Cleaner, less busy style.
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
    'font.size': 8,
    'axes.labelsize': 9,
    'axes.titlesize': 10,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
})

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results")
OUT = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\paper\nature_water\professor_briefing")

CONFIGS = {
    "Rule-based PMT": {
        "paths": [BASE / "rulebased" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
    "Ungoverned LLM": {
        "paths": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_A" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
    "Governed LLM": {
        "paths": [BASE / "JOH_FINAL" / "gemma3_4b" / "Group_B" / f"Run_{i}" / "simulation_log.csv" for i in range(1, 4)],
    },
}

# Only show active agent states (no relocated)
STATES = ["No protection", "Insurance only", "Elevation only", "Insurance + Elevation"]
# Clean, muted Okabe-Ito palette
COLORS = {
    "No protection":         "#BBBBBB",
    "Insurance only":        "#0072B2",
    "Elevation only":        "#D55E00",
    "Insurance + Elevation": "#009E73",
}


def _as_bool(val):
    if pd.isna(val):
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    return str(val).strip().lower() in ("true", "1")


def classify_state(df):
    records = []
    for _, row in df.iterrows():
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

        records.append({"agent_id": row["agent_id"], "year": row["year"], "state": state})
    return pd.DataFrame(records)


def compute_active_counts(state_df, n_agents=100):
    """Compute per-year counts EXCLUDING relocated agents, as percentage of active agents."""
    years = sorted(state_df["year"].unique())
    counts = {s: [] for s in STATES}
    relocated_counts = []

    for yr in years:
        yr_states = state_df[state_df["year"] == yr]["state"]
        vc = yr_states.value_counts()
        n_relocated = vc.get("Relocated", 0)
        n_active = n_agents - n_relocated
        relocated_counts.append(n_relocated)

        for s in STATES:
            raw = vc.get(s, 0)
            # As percentage of active agents
            pct = (raw / n_active * 100) if n_active > 0 else 0
            counts[s].append(pct)

    return years, counts, relocated_counts


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5), sharey=True)
    panel_labels = ["a", "b", "c"]

    for idx, (label, cfg) in enumerate(CONFIGS.items()):
        ax = axes[idx]
        all_counts = {s: [] for s in STATES}
        all_relocated = []
        all_years = None

        for csv_path in cfg["paths"]:
            if not csv_path.exists():
                print(f"  WARNING: {csv_path} not found")
                continue
            df = pd.read_csv(csv_path, encoding="utf-8")
            state_df = classify_state(df)
            years, counts, relocated = compute_active_counts(state_df)
            all_years = years
            all_relocated.append(relocated)
            for s in STATES:
                all_counts[s].append(counts[s])

        if all_years is None:
            continue

        avg_counts = {}
        for s in STATES:
            avg_counts[s] = np.mean(all_counts[s], axis=0) if all_counts[s] else np.zeros(len(all_years))
        avg_relocated = np.mean(all_relocated, axis=0) if all_relocated else np.zeros(len(all_years))

        # Stacked bar (clean, no hatching for professor version)
        bottom = np.zeros(len(all_years))
        x = np.arange(len(all_years))

        for s in STATES:
            vals = avg_counts[s]
            ax.bar(x, vals, bottom=bottom, color=COLORS[s], label=s, width=0.7,
                   edgecolor="white", linewidth=0.4)
            bottom += vals

        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in all_years])

        # Panel label + title
        ax.text(-0.08, 1.06, panel_labels[idx], transform=ax.transAxes,
                fontsize=10, fontweight='bold', va='top')
        ax.set_title(label, fontsize=9, fontweight='normal', loc='left', pad=10)

        if idx == 0:
            ax.set_ylabel("Share of active agents (%)", fontsize=9)

        ax.set_ylim(0, 100)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(25))

        # Add relocated annotation
        for yi, yr in enumerate(all_years):
            r = avg_relocated[yi]
            if r >= 1:
                ax.text(yi, 97, f"\u2212{r:.0f}", ha='center', va='top',
                        fontsize=5.5, color='#888888')

    # Shared x label
    fig.text(0.5, 0.02, 'Simulation year', ha='center', fontsize=9)

    # Legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.06))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.18, wspace=0.08)

    out_path = OUT / "flood_cumulative_adaptation.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"  Saved: {out_path}")

    plt.close()
    print("Done.")


if __name__ == "__main__":
    main()
