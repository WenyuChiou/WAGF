#!/usr/bin/env python
"""Build a denominator-explicit rule-layer decomposition for Paper Figure 2."""
from __future__ import annotations

import csv
import hashlib
import math
import os
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


SUBMISSION = Path(__file__).resolve().parents[1]
SOURCE = SUBMISSION / "supplement" / "fig1_rule_layers.csv"
OUTPUT = SUBMISSION / "figures" / "active" / "fig1_rule_layers"
GENERATION_MARKER = SUBMISSION / "supplement" / "figure2_generation.sha256"
ORDER = ["gemma3:4b", "gemma3:12b", "gemma4:e2b", "gemma4:e4b", "ministral3:8b"]

SELF = "behavioural rule (appraisal-conditioned)"
WORLD = "behavioural rule (world-conditioned only)"
CAP = "world-feasibility precondition"
TEAL = "#05a487"
MAGENTA = "#c777a7"
YELLOW = "#f5df3e"
INK = "#202020"
GRID = "#dddddd"
PDF_METADATA = {
    "Creator": "WAGF ICLR 2027 figure builder",
    "CreationDate": None,
    "ModDate": None,
}


def rows() -> list[dict[str, str]]:
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def percent(data: list[dict[str, str]], panel: str, model: str, arm: str, category: str, basis: str | None = None) -> float:
    matches = [
        row
        for row in data
        if row["panel"] == panel
        and row["model"] == model
        and row["arm"] == arm
        and row["category"] == category
        and (basis is None or row["basis"] == basis)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one row for {panel}/{model}/{arm}/{category}, found {len(matches)}")
    value = float(matches[0]["percent"])
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise RuntimeError(
            f"Invalid percentage for {panel}/{model}/{arm}/{category}: {value}"
        )
    return value


def style(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=7.2, colors=INK)
    ax.grid(axis="x", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def build() -> None:
    data = rows()
    plt.rcParams.update({"font.family": "serif", "font.size": 8, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig = plt.figure(figsize=(7.7, 3.25), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=(0.92, 1.55), wspace=0.18)

    ax_a = fig.add_subplot(grid[0, 0])
    anchor_self = percent(data, "a", "gemma3:4b", "with-validators", SELF,
                          "with-validators rejections (re-based)")
    anchor_world = percent(data, "a", "gemma3:4b", "with-validators", WORLD,
                           "with-validators rejections (re-based)")
    ax_a.barh([0], [anchor_self], color=TEAL, edgecolor=INK, linewidth=0.7, hatch="xx")
    ax_a.barh([0], [anchor_world], left=[anchor_self], color=MAGENTA,
              edgecolor=INK, linewidth=0.7, hatch="..")
    ax_a.text(anchor_self / 2, 0, f"{anchor_self:.1f}%", ha="center", va="center",
              fontsize=8.4, fontweight="bold",
              bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.86, "pad": 1.2})
    ax_a.text(anchor_self + anchor_world / 2, 0, f"{anchor_world:.1f}%", ha="center",
              va="center", fontsize=8.4, fontweight="bold",
              bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.86, "pad": 1.2})
    ax_a.set_title("a  Inputs read by rejection rules\nanchor: gemma3:4b validator-on, n = 6,469", loc="left",
                   fontsize=9.4, fontweight="bold")
    ax_a.set_xlabel("Share of validator-on rejections (%)", fontsize=8.4)
    ax_a.set_yticks([])
    ax_a.set_xlim(0, 100)
    ax_a.set_ylim(-0.8, 0.8)
    style(ax_a)
    ax_a.spines["left"].set_visible(False)

    ax_b = fig.add_subplot(grid[0, 1])
    y = np.arange(len(ORDER))[::-1]
    offset = 0.18
    height = 0.29
    for position, model in zip(y, ORDER):
        self_rate = percent(data, "b", model, "with-validators", SELF)
        world_rate = percent(data, "b", model, "with-validators", WORLD)
        cap_rate = percent(data, "b", model, "no-validator", CAP)
        ax_b.barh(position + offset, self_rate, height=height, color=TEAL,
                  edgecolor=INK, linewidth=0.55, hatch="xx")
        ax_b.barh(position + offset, world_rate, left=self_rate, height=height,
                  color=MAGENTA, edgecolor=INK, linewidth=0.55, hatch="..")
        ax_b.barh(position - offset, cap_rate, height=height, color=YELLOW,
                  edgecolor=INK, linewidth=0.55, hatch="//")
        label_box = {"facecolor": "white", "edgecolor": "none", "alpha": 0.92, "pad": 0.5}
        ax_b.text(-1.3, position + offset, "on", ha="right", va="center", fontsize=8.0,
                  bbox=label_box)
        ax_b.text(-1.3, position - offset, "off", ha="right", va="center", fontsize=8.0,
                  bbox=label_box)
    ax_b.set_title("b  Blocked share of all decisions", loc="left", fontsize=9.4, fontweight="bold")
    ax_b.set_yticks(y)
    ax_b.set_yticklabels(ORDER, fontsize=8.0)
    ax_b.set_xlabel("Blocked decisions (%)", fontsize=8.4)
    ax_b.set_xlim(-8, 72)
    style(ax_b)

    fig.legend(
        handles=[
            Patch(facecolor=TEAL, edgecolor=INK, hatch="xx", label="reads agent report"),
            Patch(facecolor=MAGENTA, edgecolor=INK, hatch="..", label="reads recorded world"),
            Patch(facecolor=YELLOW, edgecolor=INK, hatch="//", label="water-right cap only"),
        ],
        loc="outside upper center",
        ncol=3,
        frameon=False,
        fontsize=8.0,
        columnspacing=1.4,
        handlelength=1.5,
    )

    with tempfile.TemporaryDirectory(prefix="figure2-", dir=SUBMISSION) as temporary:
        output = Path(temporary) / "fig1_rule_layers"
        fig.savefig(output.with_suffix(".png"), dpi=300, facecolor="white")
        fig.savefig(output.with_suffix(".pdf"), facecolor="white", metadata=PDF_METADATA)
        destinations = [OUTPUT.with_suffix(".png"), OUTPUT.with_suffix(".pdf")]
        for source, destination in zip(
            (output.with_suffix(".png"), output.with_suffix(".pdf")),
            destinations,
        ):
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
    plt.close(fig)
    marker_text = "\n".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(SUBMISSION).as_posix()}"
        for path in destinations
    ) + "\n"
    temporary_marker = GENERATION_MARKER.with_suffix(".tmp")
    temporary_marker.write_text(marker_text, encoding="utf-8", newline="\n")
    os.replace(temporary_marker, GENERATION_MARKER)


if __name__ == "__main__":
    build()
    print(f"wrote {OUTPUT.with_suffix('.png')}")
    print(f"wrote {OUTPUT.with_suffix('.pdf')}")
