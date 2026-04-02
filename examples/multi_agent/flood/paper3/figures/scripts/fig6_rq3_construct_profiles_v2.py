#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Circle
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from paper3_style import (  # noqa: E402
    FIGURE_WIDTH,
    OKABE_ITO,
    add_panel_label,
    apply_style,
    save_figure,
)


PAPER3_DIR = SCRIPT_DIR.parents[1]
TABLES_DIR = PAPER3_DIR / "analysis" / "tables"
OUTPUT_STEM = PAPER3_DIR / "figures" / "main" / "fig6_rq3_construct_profiles_v2"

ACTION_PROFILE_PATH = TABLES_DIR / "rq3_construct_action_profiles.csv"
YEARLY_PATH = TABLES_DIR / "rq3_sp_pa_yearly.csv"

ACTION_ORDER = [
    "buy_insurance",
    "elevate_house",
    "buyout_program",
    "buy_contents_insurance",
    "relocate",
    "do_nothing",
]
CONSTRUCT_ORDER = ["SP", "PA"]
GROUP_ORDER = ["MG-Owner", "NMG-Owner", "MG-Renter", "NMG-Renter"]
DO_NOTHING_RATE = {
    "MG-Owner": 67.2,
    "NMG-Owner": 55.0,
    "MG-Renter": 62.3,
    "NMG-Renter": 65.5,
}


def prettify_action(action: str) -> str:
    return action.replace("_", " ")


def load_action_profiles() -> pd.DataFrame:
    return pd.read_csv(ACTION_PROFILE_PATH).set_index("action").loc[ACTION_ORDER].reset_index()


def compute_group_profiles() -> pd.DataFrame:
    yearly = pd.read_csv(YEARLY_PATH)
    filtered = yearly[
        yearly["construct"].isin(CONSTRUCT_ORDER) & yearly["group"].isin(GROUP_ORDER)
    ].copy()
    grouped = (
        filtered.groupby(["group", "construct"], sort=False)["mean"]
        .mean()
        .unstack("construct")
        .reindex(GROUP_ORDER)
    )
    grouped["do_nothing_rate"] = [DO_NOTHING_RATE[group] for group in GROUP_ORDER]
    return grouped.reset_index()


def compute_overall_construct_means() -> tuple[float, float]:
    yearly = pd.read_csv(YEARLY_PATH)
    overall = yearly[
        yearly["group"].eq("Overall") & yearly["construct"].isin(CONSTRUCT_ORDER)
    ].copy()
    means = overall.groupby("construct", sort=False)["mean"].mean()
    return float(means["SP"]), float(means["PA"])


def build_heatmap_matrix(profiles: pd.DataFrame) -> tuple[list[list[float]], list[list[int]]]:
    mean_matrix = []
    n_matrix = []
    for construct in CONSTRUCT_ORDER:
        mean_matrix.append([float(profiles.loc[profiles["action"].eq(action), f"{construct}_mean"].iloc[0]) for action in ACTION_ORDER])
        n_matrix.append([int(profiles.loc[profiles["action"].eq(action), f"{construct}_n"].iloc[0]) for action in ACTION_ORDER])
    return mean_matrix, n_matrix


def draw_action_heatmap(ax: plt.Axes, profiles: pd.DataFrame) -> None:
    mean_matrix, n_matrix = build_heatmap_matrix(profiles)
    center_value = sum(sum(row) for row in mean_matrix) / (len(mean_matrix) * len(mean_matrix[0]))
    value_min = min(min(row) for row in mean_matrix)
    value_max = max(max(row) for row in mean_matrix)

    image = ax.imshow(
        mean_matrix,
        cmap="RdBu",
        norm=TwoSlopeNorm(vmin=value_min, vcenter=center_value, vmax=value_max),
        aspect="auto",
    )

    ax.set_xticks(range(len(ACTION_ORDER)), [prettify_action(action) for action in ACTION_ORDER])
    ax.set_yticks(range(len(CONSTRUCT_ORDER)), CONSTRUCT_ORDER)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", rotation_mode="anchor")
    ax.set_title("Unconstrained construct means by action")

    ax.set_xticks([x - 0.5 for x in range(1, len(ACTION_ORDER))], minor=True)
    ax.set_yticks([0.5], minor=True)
    ax.grid(which="minor", color="white", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.axvline(4.5, color="black", linewidth=2.0)

    for row_idx, construct in enumerate(CONSTRUCT_ORDER):
        for col_idx, action in enumerate(ACTION_ORDER):
            mean_value = mean_matrix[row_idx][col_idx]
            n_value = n_matrix[row_idx][col_idx]
            ax.text(col_idx, row_idx - 0.10, f"{mean_value:.2f}", ha="center", va="center", fontsize=8)
            ax.text(col_idx, row_idx + 0.18, f"N={n_value:,}", ha="center", va="center", fontsize=6.5)

    cbar = plt.colorbar(image, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("Mean")


def bubble_radius(rate: float) -> float:
    return 0.020 + ((rate - 55.0) / (67.2 - 55.0)) * 0.016


def draw_profile_bubbles(ax: plt.Axes, profiles: pd.DataFrame, overall_sp: float, overall_pa: float) -> None:
    ax.axvline(overall_sp, color="0.75", linestyle="--", linewidth=1.0, zorder=1)
    ax.axhline(overall_pa, color="0.75", linestyle="--", linewidth=1.0, zorder=1)

    for row in profiles.itertuples(index=False):
        is_mg = row.group.startswith("MG")
        is_owner = row.group.endswith("Owner")
        facecolor = OKABE_ITO["vermillion"] if is_mg else OKABE_ITO["blue"]
        linestyle = "-" if is_owner else (0, (4, 2))
        radius = bubble_radius(float(row.do_nothing_rate))
        bubble = Circle(
            (float(row.SP), float(row.PA)),
            radius=radius,
            facecolor=facecolor,
            edgecolor="black",
            linewidth=1.2,
            linestyle=linestyle,
            alpha=0.78,
            zorder=3,
        )
        ax.add_patch(bubble)

        x_offset = -0.060 if "Owner" in row.group else 0.018
        y_offset = 0.065 if row.group == "MG-Owner" else (-0.060 if row.group == "NMG-Renter" else 0.0)
        ax.text(
            float(row.SP) + x_offset,
            float(row.PA) + y_offset,
            f"{row.group}\n{float(row.do_nothing_rate):.1f}%",
            ha="left",
            va="center",
            fontsize=7,
            zorder=4,
        )

    mg_owner = profiles.loc[profiles["group"].eq("MG-Owner")].iloc[0]
    ax.annotate(
        "Highest PA + Lowest SP\nmost trapped",
        xy=(float(mg_owner["SP"]), float(mg_owner["PA"])),
        xytext=(2.44, 3.15),
        ha="left",
        va="center",
        fontsize=7.5,
        arrowprops={"arrowstyle": "->", "linewidth": 0.9, "color": "0.3"},
    )

    ax.set_xlim(2.4, 2.8)
    ax.set_ylim(2.4, 3.2)
    ax.set_xlabel("Mean SP")
    ax.set_ylabel("Mean PA")
    ax.set_title(
        "Adaptation trap: SP, PA, and realized inaction",
        x=0.68,
        fontsize=7.5,
    )


def build_figure() -> plt.Figure:
    apply_style()
    action_profiles = load_action_profiles()
    group_profiles = compute_group_profiles()
    overall_sp, overall_pa = compute_overall_construct_means()

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(FIGURE_WIDTH, 3.0),
        gridspec_kw={"width_ratios": [1.3, 1.0]},
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.23, wspace=0.36)

    draw_action_heatmap(axes[0], action_profiles)
    draw_profile_bubbles(axes[1], group_profiles, overall_sp, overall_pa)

    add_panel_label(axes[0], "(a)")
    add_panel_label(axes[1], "(b)")
    return fig


def main() -> None:
    fig = build_figure()
    save_figure(fig, OUTPUT_STEM)
    print(f"Saved {OUTPUT_STEM.with_suffix('.png')}")
    print(f"Saved {OUTPUT_STEM.with_suffix('.pdf')}")
    plt.close(fig)


if __name__ == "__main__":
    main()
