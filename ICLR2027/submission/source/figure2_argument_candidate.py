#!/usr/bin/env python
"""Build the review candidate for Paper Figure 2 without touching active assets."""
from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


SUBMISSION = Path(__file__).resolve().parents[1]
RULE_SOURCE = SUBMISSION / "supplement" / "fig1_rule_layers.csv"
CELL_SOURCE = SUBMISSION / "supplement" / "table1_cells.csv"
OUTPUT = SUBMISSION / "figures" / "candidates" / "figure2_argument_v1"

ORDER = ["gemma3:4b", "gemma3:12b", "gemma4:e2b", "gemma4:e4b", "ministral3:8b"]
REPORT_RULE = "behavioural rule (appraisal-conditioned)"
WORLD_RULE = "behavioural rule (world-conditioned only)"
CAP_RULE = "world-feasibility precondition"

REPORT = "#12A58B"
WORLD = "#B56898"
CAP = "#E7C83A"
VALIDATOR = "#1685B8"
NO_VALIDATOR = "#D86B00"
INK = "#202020"
GRID = "#D9D9D9"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def rule_percent(
    rows: list[dict[str, str]], model: str, arm: str, category: str
) -> float:
    matches = [
        row
        for row in rows
        if row["panel"] == "b"
        and row["model"] == model
        and row["arm"] == arm
        and row["category"] == category
        and row["basis"] == "all decisions"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one rule row for {model}/{arm}/{category}")
    value = float(matches[0]["percent"])
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise RuntimeError(f"Invalid rule percentage: {value}")
    return value


def irrigation_cells(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for row in rows:
        if row["testbed"] != "irrigation" or row["model"] not in ORDER:
            continue
        result[row["model"]] = {
            "validator": float(row["high_gov"]),
            "no_validator": float(row["high_noval"]),
            "delta": float(row["high_delta"]),
        }
    if set(result) != set(ORDER):
        raise RuntimeError(f"Missing irrigation cells: {set(ORDER) - set(result)}")
    for model, values in result.items():
        for key, value in values.items():
            if not math.isfinite(value) or not -100 <= value <= 100:
                raise RuntimeError(f"Invalid {key} for {model}: {value}")
        computed = values["no_validator"] - values["validator"]
        if not math.isclose(computed, values["delta"], abs_tol=0.02):
            raise RuntimeError(f"Condition-share delta mismatch for {model}")
    return result


def clean_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(colors=INK, labelsize=8)
    ax.grid(axis="x", color=GRID, linewidth=0.55)
    ax.set_axisbelow(True)


def build() -> None:
    rules = read_csv(RULE_SOURCE)
    cells = irrigation_cells(read_csv(CELL_SOURCE))
    y = np.arange(len(ORDER))[::-1]

    report = np.array([rule_percent(rules, model, "with-validators", REPORT_RULE) for model in ORDER])
    world = np.array([rule_percent(rules, model, "with-validators", WORLD_RULE) for model in ORDER])
    cap = np.array([rule_percent(rules, model, "no-validator", CAP_RULE) for model in ORDER])
    totals = report + world
    validator_share = np.array([cells[model]["validator"] for model in ORDER])
    no_validator_share = np.array([cells[model]["no_validator"] for model in ORDER])
    deltas = np.array([cells[model]["delta"] for model in ORDER])

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig = plt.figure(figsize=(7.7, 3.35), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=(1.03, 1.17), wspace=0.12)

    ax_a = fig.add_subplot(grid[0, 0])
    ax_a.barh(y, report, height=0.46, color=REPORT, edgecolor=INK, linewidth=0.55)
    ax_a.barh(y, world, left=report, height=0.46, color=WORLD, edgecolor=INK, linewidth=0.55)
    ax_a.scatter(cap, y, marker="D", s=42, facecolor=CAP, edgecolor=INK, linewidth=0.7, zorder=4)
    for position, total in zip(y, totals):
        ax_a.text(total + 1.0, position, f"{total:.1f}", va="center", ha="left", fontsize=7.4, color=INK)
    ax_a.set_title("a  Which checks block decisions", loc="left", fontsize=9.5, fontweight="bold")
    ax_a.set_yticks(y)
    ax_a.set_yticklabels(ORDER, fontsize=8.0)
    ax_a.set_xlim(0, 70)
    ax_a.set_ylim(-0.45, 5.05)
    ax_a.set_xlabel("Share of all decisions (%)", fontsize=8.4)
    clean_axis(ax_a)
    ax_a.legend(
        handles=[
            Patch(facecolor=REPORT, edgecolor=INK, label="agent report"),
            Patch(facecolor=WORLD, edgecolor=INK, label="recorded world"),
            Line2D([], [], marker="D", linestyle="none", markerfacecolor=CAP,
                   markeredgecolor=INK, label="cap (validator off)"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.50, 0.99),
        ncol=3,
        frameon=False,
        fontsize=7.1,
        columnspacing=0.8,
        handlelength=1.3,
        handletextpad=0.4,
    )

    ax_b = fig.add_subplot(grid[0, 1], sharey=ax_a)
    for position, on, off in zip(y, validator_share, no_validator_share):
        ax_b.plot([on, off], [position, position], color="#6E6E6E", linewidth=1.35, zorder=1)
    ax_b.scatter(validator_share, y, marker="o", s=48, facecolor=VALIDATOR,
                 edgecolor=INK, linewidth=0.7, zorder=3)
    ax_b.scatter(no_validator_share, y, marker="s", s=46, facecolor=NO_VALIDATOR,
                 edgecolor=INK, linewidth=0.7, zorder=3)
    for position, delta in zip(y, deltas):
        ax_b.text(111.0, position, f"+{delta:.1f}", va="center", ha="right",
                  fontsize=7.5, fontweight="bold", color=INK)
    ax_b.text(111.0, 4.52, "difference", ha="right", va="bottom",
              fontsize=7.0, color="#555555")
    ax_b.set_title("b  The scored population differs", loc="left",
                   fontsize=9.5, fontweight="bold")
    ax_b.set_xlim(0, 112)
    ax_b.set_xlabel("Decisions reporting high scarcity (%)", fontsize=8.4)
    ax_b.tick_params(axis="y", left=False, labelleft=False)
    clean_axis(ax_b)
    ax_b.legend(
        handles=[
            Line2D([], [], marker="o", linestyle="none", markerfacecolor=VALIDATOR,
                   markeredgecolor=INK, label="validator on"),
            Line2D([], [], marker="s", linestyle="none", markerfacecolor=NO_VALIDATOR,
                   markeredgecolor=INK, label="no validator"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.45, 0.99),
        ncol=2,
        frameon=False,
        fontsize=7.3,
        columnspacing=1.1,
        handletextpad=0.4,
    )

    fig.patch.set_facecolor("white")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT.with_suffix(".png"), dpi=300, facecolor="white")
    fig.savefig(
        OUTPUT.with_suffix(".pdf"),
        facecolor="white",
        metadata={"Creator": "WAGF ICLR 2027 figure candidate", "CreationDate": None, "ModDate": None},
    )
    plt.close(fig)
    print(f"wrote {OUTPUT.with_suffix('.png')}")
    print(f"wrote {OUTPUT.with_suffix('.pdf')}")


if __name__ == "__main__":
    build()
