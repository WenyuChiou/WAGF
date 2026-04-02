"""Generate Paper 3 Figure 5 (RQ2 equity)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from paper3_style import (  # noqa: E402
    DPI,
    FIGURE_WIDTH,
    OKABE_ITO,
    add_panel_label,
    apply_style,
    ensure_parent,
)


ROOT = SCRIPT_DIR.parents[1]
TABLES_DIR = ROOT / "analysis" / "tables"
OUTPUT_STEM = ROOT / "figures" / "main" / "fig5_rq2_equity"

COLOR_MG = OKABE_ITO["vermillion"]
COLOR_NMG = OKABE_ITO["blue"]
COLOR_INSURANCE = OKABE_ITO["blue"]
COLOR_ELEVATION = OKABE_ITO["orange"]
COLOR_BUYOUT = OKABE_ITO["green"]
COLOR_DO_NOTHING = OKABE_ITO["vermillion"]


def sim_to_calendar(sim_year: int) -> int:
    return int(sim_year) + 2010


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trajectory = pd.read_csv(TABLES_DIR / "rq2_policy_trajectory.csv")
    summary = pd.read_csv(TABLES_DIR / "rq2_equity_summary.csv")
    proposed_vs_executed = pd.read_csv(TABLES_DIR / "rq2_4cell_proposed_vs_executed.csv")
    return trajectory, summary, proposed_vs_executed


def plot_policy_trajectory(ax: plt.Axes, trajectory: pd.DataFrame) -> None:
    years = trajectory["year"].map(sim_to_calendar)

    ax.plot(
        years,
        trajectory["full_subsidy"] * 100,
        color=OKABE_ITO["blue"],
        linewidth=1.8,
        label="Full subsidy",
    )
    ax.plot(
        years,
        trajectory["fixed_subsidy"] * 100,
        color=OKABE_ITO["sky_blue"],
        linewidth=1.8,
        linestyle="--",
        label="Flat subsidy",
    )
    ax.plot(
        years,
        trajectory["full_crs"] * 100,
        color=OKABE_ITO["orange"],
        linewidth=1.8,
        label="Full CRS",
    )
    ax.plot(
        years,
        trajectory["fixed_crs"] * 100,
        color="#F3C567",
        linewidth=1.8,
        linestyle="--",
        label="Flat CRS",
    )

    ax.set_xlim(2011, 2023)
    ax.set_xticks([2011, 2014, 2017, 2020, 2023])
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel("Year")
    ax.set_ylabel("Adoption rate")
    ax.legend(loc="upper left", frameon=False, ncol=2, handlelength=2.8)


def plot_affordability_blocking(ax: plt.Axes, summary: pd.DataFrame) -> None:
    order = [("Full", "MG"), ("Full", "NMG"), ("Flat", "MG"), ("Flat", "NMG")]
    labels = ["Full-MG", "Full-NMG", "Flat-MG", "Flat-NMG"]
    values = [
        int(
            summary.loc[
                (summary["condition"] == condition) & (summary["group"] == group),
                "affordability_rejections",
            ].iloc[0]
        )
        for condition, group in order
    ]

    colors = [COLOR_MG, COLOR_NMG, COLOR_MG, COLOR_NMG]
    hatches = [None, None, "///", "///"]
    x = range(len(labels))
    bars = []
    for idx, (label, value) in enumerate(zip(labels, values)):
        bars.append(
            ax.bar(
                idx,
                value,
                width=0.68,
                color=colors[idx],
                hatch=hatches[idx],
                edgecolor="black" if hatches[idx] else colors[idx],
                linewidth=0.8,
            )[0]
        )

    ax.set_xticks(list(x), labels)
    ax.set_ylabel("Affordability rejections")
    ax.set_ylim(0, max(values) * 1.34)

    for idx in [0, 2]:
        ax.text(
            bars[idx].get_x() + bars[idx].get_width() / 2,
            values[idx] + 8,
            f"{values[idx]}",
            ha="center",
            va="bottom",
        )

    start_x = bars[0].get_x() + bars[0].get_width() / 2
    end_x = bars[2].get_x() + bars[2].get_width() / 2
    start_y = values[0] + 28
    end_y = values[2] + 28
    ax.annotate(
        "",
        xy=(end_x, end_y),
        xytext=(start_x, start_y),
        arrowprops=dict(arrowstyle="->", color="0.25", linewidth=1.0),
    )
    ax.text(
        (start_x + end_x) / 2,
        max(start_y, end_y) + 12,
        "+147%",
        ha="center",
        va="bottom",
        color="0.25",
    )


def plot_do_nothing_gap(ax: plt.Axes, proposed_vs_executed: pd.DataFrame) -> None:
    owner_rows = proposed_vs_executed[
        proposed_vs_executed["cell"].isin(["MG-Owner", "NMG-Owner"])
        & (proposed_vs_executed["skill"] == "do_nothing")
    ].copy()
    owner_rows["cell"] = pd.Categorical(owner_rows["cell"], ["MG-Owner", "NMG-Owner"])
    owner_rows = owner_rows.sort_values("cell")

    labels = owner_rows["cell"].tolist()
    proposed = owner_rows["proposed_pct"].tolist()
    executed = owner_rows["executed_pct"].tolist()

    x = [0, 1]
    width = 0.34
    proposed_bars = ax.bar(
        [v - width / 2 for v in x],
        proposed,
        width=width,
        color=[OKABE_ITO["sky_blue"], "#8EBFE5"],
        label="Proposed",
    )
    executed_bars = ax.bar(
        [v + width / 2 for v in x],
        executed,
        width=width,
        color=[COLOR_MG, COLOR_NMG],
        label="Executed",
    )

    for idx, (p_val, e_val) in enumerate(zip(proposed, executed)):
        ax.plot([x[idx], x[idx]], [p_val + 1.0, e_val - 1.0], color="0.35", linewidth=0.9)
        ax.text(
            x[idx],
            e_val + 2.2,
            f"+{e_val - p_val:.1f}pp",
            ha="center",
            va="bottom",
        )

    proposed_gap = proposed[0] - proposed[1]
    executed_gap = executed[0] - executed[1]
    ax.text(
        0.5,
        max(executed) + 10.0,
        f"Gap: {proposed_gap:.1f}pp -> {executed_gap:.1f}pp",
        ha="center",
        va="bottom",
        fontsize=7,
        color="0.3",
    )

    ax.bar_label(proposed_bars, fmt="%.1f%%", padding=2, fontsize=7)
    ax.bar_label(executed_bars, fmt="%.1f%%", padding=2, fontsize=7)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Do-nothing rate")
    ax.set_ylim(0, 82)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.legend(loc="upper left", frameon=False)


def plot_executed_distribution(ax: plt.Axes, summary: pd.DataFrame) -> None:
    order = [("Full", "MG"), ("Full", "NMG"), ("Flat", "MG"), ("Flat", "NMG")]
    labels = ["Full-MG", "Full-NMG", "Flat-MG", "Flat-NMG"]
    display_names = ["Insurance", "Elevation", "Buyout", "Do nothing"]
    data_columns = ["FI_pct", "EH_pct", "BP_pct", "DN_pct"]
    colors = [COLOR_INSURANCE, COLOR_ELEVATION, COLOR_BUYOUT, COLOR_DO_NOTHING]

    left = [0.0] * len(order)
    y_pos = list(range(len(order)))
    for display_name, data_column, color in zip(display_names, data_columns, colors):
        values = [
            float(
                summary.loc[
                    (summary["condition"] == condition) & (summary["group"] == group),
                    data_column,
                ].iloc[0]
            )
            for condition, group in order
        ]
        ax.barh(y_pos, values, left=left, color=color, height=0.68, label=display_name)
        left = [l + v for l, v in zip(left, values)]

    ax.set_yticks(y_pos, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Executed action share")
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=2,
        frameon=False,
        columnspacing=1.2,
    )


def build_figure() -> plt.Figure:
    apply_style()
    trajectory, summary, proposed_vs_executed = load_inputs()

    fig, axes = plt.subplots(2, 2, figsize=(FIGURE_WIDTH, 5.0), dpi=DPI)
    fig.subplots_adjust(wspace=0.28, hspace=0.42, bottom=0.18)

    plot_policy_trajectory(axes[0, 0], trajectory)
    plot_affordability_blocking(axes[0, 1], summary)
    plot_do_nothing_gap(axes[1, 0], proposed_vs_executed)
    plot_executed_distribution(axes[1, 1], summary)

    for ax, label in zip(axes.flat, ["a", "b", "c", "d"]):
        add_panel_label(ax, f"({label})")

    return fig


def main() -> None:
    ensure_parent(OUTPUT_STEM.with_suffix(".png"))
    fig = build_figure()
    fig.savefig(f"{OUTPUT_STEM}.png", dpi=DPI, bbox_inches="tight")
    fig.savefig(f"{OUTPUT_STEM}.pdf", bbox_inches="tight")
    print(f"Saved: {OUTPUT_STEM}.png and {OUTPUT_STEM}.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
