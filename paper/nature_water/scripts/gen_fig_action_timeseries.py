"""
gen_fig_action_timeseries.py
----------------------------
Generates a time-resolved action composition figure for the irrigation domain.
Two side-by-side stacked area panels (governed vs ungoverned) over 42 simulation years.

Output: paper/nature_water/figures/Fig_action_timeseries.{png,pdf}
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator

# Ensure UTF-8 output on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = str(Path(__file__).resolve().parents[3])
RESULTS = os.path.join(BASE, "examples", "irrigation_abm", "results")
OUT_DIR = os.path.join(BASE, "paper", "nature_water", "figures")
os.makedirs(OUT_DIR, exist_ok=True)

SEEDS = [42, 43, 44]

GOV_PATTERN   = "production_v20_42yr_seed{seed}"
UNGOV_PATTERN = "ungoverned_v20_42yr_seed{seed}"

# ---------------------------------------------------------------------------
# Action order and colors  (warm→cool semantic ordering, Okabe-Ito based)
# ---------------------------------------------------------------------------
ACTION_ORDER = [
    "increase_large",
    "increase_small",
    "maintain_demand",
    "decrease_small",
    "decrease_large",
]

ACTION_COLORS = {
    "increase_large":  "#D55E00",   # vermillion
    "increase_small":  "#E69F00",   # amber
    "maintain_demand": "#F0E442",   # yellow
    "decrease_small":  "#56B4E9",   # sky blue
    "decrease_large":  "#0072B2",   # blue
}

ACTION_LABELS = {
    "increase_large":  "Increase large",
    "increase_small":  "Increase small",
    "maintain_demand": "Maintain",
    "decrease_small":  "Decrease small",
    "decrease_large":  "Decrease large",
}

DROUGHT_THRESH = 1075.0  # ft — Tier 1 trigger

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_and_aggregate(pattern: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load simulation logs for all 3 seeds, compute per-year action shares,
    and return (mean_shares_df, mean_mead_df).

    mean_shares_df: index=year, columns=ACTION_ORDER, values=fraction [0,1]
    mean_mead_df:   index=year, column='lake_mead_level', values=mean ft
    """
    all_shares = []
    all_mead   = []

    for seed in SEEDS:
        path = os.path.join(RESULTS, pattern.format(seed=seed), "simulation_log.csv")
        df = pd.read_csv(path, encoding="utf-8")

        # --- action share per year ---
        year_counts = (
            df.groupby(["year", "yearly_decision"])
            .size()
            .unstack(fill_value=0)
        )
        # ensure all 5 actions present
        for act in ACTION_ORDER:
            if act not in year_counts.columns:
                year_counts[act] = 0
        year_counts = year_counts[ACTION_ORDER]
        # convert to fraction
        year_share = year_counts.div(year_counts.sum(axis=1), axis=0)
        all_shares.append(year_share)

        # --- Mead level per year ---
        mead = df.groupby("year")["lake_mead_level"].mean()
        all_mead.append(mead)

    # average across seeds
    mean_shares = pd.concat(all_shares).groupby(level=0).mean()
    mean_mead   = pd.concat(all_mead, axis=1).mean(axis=1)

    return mean_shares, mean_mead


def drought_spans(mead_series: pd.Series) -> list[tuple[float, float]]:
    """
    Return list of (year_start, year_end) contiguous drought spans
    where mead_series < DROUGHT_THRESH.
    Spans are expanded by ±0.5 year for visual width.
    """
    drought_years = sorted(mead_series[mead_series < DROUGHT_THRESH].index.tolist())
    if not drought_years:
        return []

    spans = []
    start = drought_years[0]
    prev  = drought_years[0]
    for yr in drought_years[1:]:
        if yr == prev + 1:
            prev = yr
        else:
            spans.append((start - 0.5, prev + 0.5))
            start = yr
            prev  = yr
    spans.append((start - 0.5, prev + 0.5))
    return spans


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def style_axis(ax: plt.Axes) -> None:
    """Apply Nature Water axis style."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3, width=0.8)
    ax.tick_params(axis="x", which="minor", length=2, width=0.6)
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.xaxis.set_minor_locator(MultipleLocator(5))
    ax.yaxis.set_major_locator(MultipleLocator(25))
    ax.yaxis.set_minor_locator(MultipleLocator(12.5))
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_linewidth(0.8)


def plot_panel(
    ax: plt.Axes,
    shares: pd.DataFrame,
    mead: pd.Series,
    label: str,
) -> None:
    """
    Draw stacked area chart of action shares on ax.
    Adds drought shading, panel label, and axis formatting.
    """
    years = shares.index.values
    pct   = shares * 100.0          # convert to %

    # --- stacked area ---
    bottom = np.zeros(len(years))
    for act in ACTION_ORDER:
        vals = pct[act].values
        ax.fill_between(
            years,
            bottom,
            bottom + vals,
            color=ACTION_COLORS[act],
            alpha=0.92,
            linewidth=0,
        )
        # subtle separator line
        ax.plot(
            years,
            bottom + vals,
            color="white",
            linewidth=0.3,
            alpha=0.6,
        )
        bottom += vals

    # --- drought shading ---
    for (x0, x1) in drought_spans(mead):
        ax.axvspan(x0, x1, color="#888888", alpha=0.15, linewidth=0, zorder=0)

    # --- formatting ---
    style_axis(ax)
    ax.set_xlim(1, 42)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Simulation year", fontsize=8, labelpad=4)

    # panel label
    ax.text(
        0.03, 0.97, label,
        transform=ax.transAxes,
        fontsize=9,
        fontweight="bold",
        va="top",
        ha="left",
    )


def build_figure() -> None:
    print("Loading governed data ...", flush=True)
    gov_shares,   gov_mead   = load_and_aggregate(GOV_PATTERN)
    print("Loading ungoverned data ...", flush=True)
    ungov_shares, ungov_mead = load_and_aggregate(UNGOV_PATTERN)

    # --- set font ---
    matplotlib.rcParams.update({
        "font.family": "Arial",
        "font.size": 8,
        "axes.linewidth": 0.8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.labelsize": 8,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })

    fig, axes = plt.subplots(
        1, 2,
        figsize=(7.09, 3.0),
        sharey=True,
        constrained_layout=False,
    )
    fig.subplots_adjust(
        left=0.08, right=0.99,
        bottom=0.22, top=0.95,
        wspace=0.08,
    )

    plot_panel(axes[0], gov_shares,   gov_mead,   "(a) Governed")
    plot_panel(axes[1], ungov_shares, ungov_mead, "(b) Ungoverned")

    axes[0].set_ylabel("Action share (%)", fontsize=8, labelpad=4)
    axes[1].set_ylabel("")
    # remove y-tick labels from right panel (shared y-axis)
    axes[1].tick_params(labelleft=False)

    # --- single legend at bottom, centered ---
    legend_handles = []
    for act in ACTION_ORDER:
        patch = mpatches.Patch(
            facecolor=ACTION_COLORS[act],
            edgecolor="none",
            label=ACTION_LABELS[act],
            alpha=0.92,
        )
        legend_handles.append(patch)

    # drought legend entry
    drought_patch = mpatches.Patch(
        facecolor="#888888",
        edgecolor="none",
        label="Drought (Mead < 1,075 ft)",
        alpha=0.35,
    )
    legend_handles.append(drought_patch)

    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=len(legend_handles),
        fontsize=7,
        frameon=False,
        bbox_to_anchor=(0.535, 0.0),
        handlelength=1.2,
        handletextpad=0.4,
        columnspacing=0.8,
    )

    # --- save ---
    png_path = os.path.join(OUT_DIR, "Fig_action_timeseries.png")
    pdf_path = os.path.join(OUT_DIR, "Fig_action_timeseries.pdf")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved PNG: {png_path}", flush=True)
    print(f"Saved PDF: {pdf_path}", flush=True)

    # --- print summary stats for sanity check ---
    print("\n--- Action share summary (governed, mean across seeds) ---")
    print((gov_shares * 100).round(1).to_string())
    print("\n--- Action share summary (ungoverned, mean across seeds) ---")
    print((ungov_shares * 100).round(1).to_string())

    print("\n--- Mean Mead level (governed, mean across seeds) ---")
    below = gov_mead[gov_mead < DROUGHT_THRESH]
    print(f"Years below {DROUGHT_THRESH} ft: {sorted(below.index.tolist())}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    build_figure()
