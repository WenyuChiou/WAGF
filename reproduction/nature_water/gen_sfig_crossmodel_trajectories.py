#!/usr/bin/env python3
"""Nature Water — Supplementary Figure: cross-model flood adaptation-status
trajectories.

Small-multiples version of main-text Fig. 3a, drawn once per model so the
behavioural shift under validators is visible across all nine flood model
configurations (not only Gemma-3 4B). 3x3 model grid; each model cell holds
two stacked-bar sub-panels (Governed LLM | LLM no-validator), y = mean agent
count per adaptation status across 5 seeds, x = simulation year 1-10, flood
years (3,4,9) shaded. Categories + colours reuse Fig. 3a exactly.

Data: examples/single_agent/results/JOH_FINAL[_v2]/<model>/Group_C (governed)
      + JOH_ABLATION_DISABLED[_v2]/<model>/Group_C_disabled (no validator).
All 9 models x 2 conditions x 5 runs verified complete (1000 rows/run).
No new runs; existing cross-model data only.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from gen_fig3_case2_flood import (  # noqa: E402
    PROT_STATES, PROT_COLORS, PROT_ABBREV,
    _map_state_col, _classify_state_from_cols,
    _compute_prot_counts_per_year, get_flood_years,
)

BASE = SCRIPT_DIR.parents[1]  # reproduction/nature_water -> repo root
SA = BASE / "examples" / "single_agent" / "results"
OUT = BASE / "paper" / "nature_water" / "figures"

# Family-grouped 3x3 order: rows = Gemma-3, Gemma-4, Ministral; cols = small->large
MODELS = [
    ("gemma3_4b",      "Gemma-3 4B"),
    ("gemma3_12b",     "Gemma-3 12B"),
    ("gemma3_27b",     "Gemma-3 27B"),
    ("gemma4_e2b",     "Gemma-4 e2b"),
    ("gemma4_e4b",     "Gemma-4 e4b"),
    ("gemma4_26b",     "Gemma-4 26B"),
    ("ministral3_3b",  "Ministral 3B"),
    ("ministral3_8b",  "Ministral 8B"),
    ("ministral3_14b", "Ministral 14B"),
]
BASE_FONT = 6.5


def _runs_dir(model: str, governed: bool) -> Path | None:
    root = "JOH_FINAL" if governed else "JOH_ABLATION_DISABLED"
    grp = "Group_C" if governed else "Group_C_disabled"
    for r in (root + "_v2", root):
        d = SA / r / model / grp
        if d.exists() and list(d.glob("Run_*/simulation_log.csv")):
            return d
    return None


def _load_runs(model: str, governed: bool) -> list[pd.DataFrame]:
    d = _runs_dir(model, governed)
    if d is None:
        return []
    dfs = []
    for rp in sorted(d.glob("Run_*/simulation_log.csv")):
        df = pd.read_csv(rp, encoding="utf-8-sig")
        if "cumulative_state" in df.columns:
            df["prot_state"] = _map_state_col(df["cumulative_state"])
        elif "decision" in df.columns:
            df["prot_state"] = _map_state_col(df["decision"])
        else:
            df["prot_state"] = df.apply(_classify_state_from_cols, axis=1)
        dfs.append(df)
    return dfs


def _draw_stack(ax, mean_c: pd.DataFrame, show_y: bool):
    flood_years = get_flood_years()
    if mean_c is None or mean_c.empty:
        ax.text(0.5, 0.5, "no data", transform=ax.transAxes,
                ha="center", va="center", fontsize=BASE_FONT - 1, color="#999")
        ax.set_xticks([]); ax.set_yticks([])
        return
    years = mean_c.index.values
    x = np.arange(len(years))
    for j, yr in enumerate(years):
        if yr in flood_years:
            ax.axvspan(x[j] - 0.45, x[j] + 0.45, color="#9ecae1", alpha=0.35, zorder=0)
            ax.text(x[j], 105, "F", ha="center", va="bottom",
                    fontsize=BASE_FONT - 1.5, color="#cc3333", fontweight="bold")
    bottom = np.zeros(len(years))
    for state in PROT_STATES:
        vals = mean_c[state].values if state in mean_c.columns else np.zeros(len(years))
        ax.bar(x, vals, bottom=bottom, width=0.82, color=PROT_COLORS[state],
               edgecolor="white", linewidth=0.15, zorder=2)
        bottom += vals
    ax.set_ylim(0, 114)
    ax.set_xticks([0, 4, 9]); ax.set_xticklabels(["1", "5", "10"], fontsize=BASE_FONT - 1.5)
    ax.tick_params(axis="x", length=2, pad=1)
    if show_y:
        ax.set_yticks([0, 50, 100]); ax.tick_params(axis="y", labelsize=BASE_FONT - 1.5, length=2, pad=1)
    else:
        ax.set_yticks([0, 50, 100]); ax.set_yticklabels([])
        ax.tick_params(axis="y", length=2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_linewidth(0.5); ax.spines["bottom"].set_linewidth(0.5)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(6.7, 6.5))
    outer = gridspec.GridSpec(
        3, 3, figure=fig, hspace=0.46, wspace=0.18,
        left=0.055, right=0.985, top=0.945, bottom=0.10,
    )
    for idx, (key, label) in enumerate(MODELS):
        r, c = divmod(idx, 3)
        inner = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=outer[r, c], wspace=0.06)
        ax_g = fig.add_subplot(inner[0])
        ax_n = fig.add_subplot(inner[1], sharey=ax_g)

        gov_mean, _ = _compute_prot_counts_per_year(_load_runs(key, True))
        nov_mean, _ = _compute_prot_counts_per_year(_load_runs(key, False))
        _draw_stack(ax_g, gov_mean, show_y=True)
        _draw_stack(ax_n, nov_mean, show_y=False)

        ax_g.set_title("Governed", fontsize=BASE_FONT - 1, pad=1.5, color=PROT_COLORS["No protection"])
        ax_n.set_title("No validator", fontsize=BASE_FONT - 1, pad=1.5, color=PROT_COLORS["Insurance + Elevation"])
        # panel letter (a-i) top-left + model name centred above the pair
        pg, pn = ax_g.get_position(), ax_n.get_position()
        fig.text(pg.x0 - 0.006, pg.y1 + 0.014, chr(97 + idx),
                 ha="right", va="bottom", fontsize=BASE_FONT + 2.5, fontweight="bold")
        fig.text((pg.x0 + pn.x1) / 2, pg.y1 + 0.014, label,
                 ha="center", va="bottom", fontsize=BASE_FONT + 0.5, fontweight="bold")
        if c == 0:
            ax_g.set_ylabel("Agent count", fontsize=BASE_FONT - 0.5, labelpad=1)

    # shared x-label + legend
    fig.text(0.52, 0.055, "Simulation year", ha="center", fontsize=BASE_FONT)
    handles = [mpatches.Patch(facecolor=PROT_COLORS[s], edgecolor="white",
                              label=PROT_ABBREV[s]) for s in PROT_STATES]
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=BASE_FONT,
               frameon=False, bbox_to_anchor=(0.52, 0.0), handlelength=1.2,
               columnspacing=1.6, handletextpad=0.4)

    for ext in ("png", "pdf"):
        p = OUT / f"SFig_crossmodel_trajectories.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
