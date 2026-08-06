#!/usr/bin/env python
"""Build the ICLR irrigation mechanism figure and cross-testbed summary.

This builder is intentionally owned by the ICLR submission package.  It reads
the pinned Flood contrast CSV and the copied A--C mechanism data, and writes
only ICLR submission artefacts.  It never imports the historical TAE evidence
runner and never recomputes a pooled-row Flood contrast.

Run from the repository root:

    python ICLR2027/submission/source/cross_testbed_summary.py

The Flood contrast is the mean of per-run means, with the single divergent
gemma3:4b governed run excluded as recorded in flood_control_contrasts.csv.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parents[3]
ICLR = REPO / "ICLR2027"
SUBMISSION = ICLR / "submission"
FLOOD_CSV = ICLR / "flood_control_contrasts.csv"
MECHANISM_CSV = SUBMISSION / "supplement" / "fig2_mechanism.csv"
ACTIVE_FIGURE = SUBMISSION / "figures" / "active" / "fig2_mechanism"
FIGURE_CSV = SUBMISSION / "supplement" / "fig2_mechanism.csv"
SUMMARY_CSV = SUBMISSION / "supplement" / "cross_testbed_summary.csv"
SUMMARY_TEX = SUBMISSION / "supplement" / "table2_cross_testbed.tex"
PRESSURE_JSON = SUBMISSION / "supplement" / "enforcement_pressure_source.json"


INK = "#202020"
BLUE = "#1479b8"
ORANGE = "#d66a05"
GRID = "#d9d9d9"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str) -> float:
    return float(value) if value not in ("", None) else math.nan


def flood_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in read_csv(FLOOD_CSV):
        rows.append(
            {
                "setting": row["setting"],
                "model": row["model"],
                "gov": as_float(row["gov"]),
                "noval": as_float(row["noval"]),
                "contrast": as_float(row["contrast"]),
                "n_gov": int(row["n_gov"]),
                "n_noval": int(row["n_noval"]),
                "note": row["note"],
            }
        )
    return rows


def pressure_ranges() -> dict[str, str]:
    source = json.loads(PRESSURE_JSON.read_text(encoding="utf-8"))
    ranges = source["ranges_pct"]
    expected = {"irrigation": [28.0, 63.0], "flood": [0.0, 0.85]}
    if ranges != expected:
        raise RuntimeError("Pinned governance-pressure summary changed")
    return {
        setting: f"{values[0]:g}--{values[1]:g}"
        for setting, values in ranges.items()
    }


def build_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    pressure = pressure_ranges()
    summary: list[dict[str, object]] = []
    for setting in ("irrigation", "flood"):
        group = [row for row in rows if row["setting"] == setting]
        contrasts = [float(row["contrast"]) for row in group]
        gov = [float(row["gov"]) for row in group]
        noval = [float(row["noval"]) for row in group]
        summary.append(
            {
                "setting": setting,
                "n_configurations": len(group),
                "gov_range": f"{min(gov):.2f}--{max(gov):.2f}",
                "noval_range": f"{min(noval):.2f}--{max(noval):.2f}",
                "contrast_range": f"{min(contrasts):+.2f}--{max(contrasts):+.2f}",
                "contrast_mean": round(float(np.mean(contrasts)), 2),
                "pressure_range": pressure[setting],
            }
        )
    return summary


def write_summary(summary: list[dict[str, object]]) -> None:
    fields = [
        "setting",
        "n_configurations",
        "gov_range",
        "noval_range",
        "contrast_range",
        "contrast_mean",
        "pressure_range",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)

    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Setting & Configurations & High-threat share on & High-threat share off & Contrast range & Mean $\Delta$ \\",
        r"\midrule",
    ]
    for row in summary:
        label = row["setting"].capitalize()
        lines.append(
            f"{label} & {row['n_configurations']} & {row['gov_range']}\\% & "
            f"{row['noval_range']}\\% & {row['contrast_range']} & "
            f"{row['contrast_mean']:+.2f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    SUMMARY_TEX.write_text("\n".join(lines), encoding="utf-8")


def mechanism_rows() -> list[dict[str, object]]:
    rows = []
    for row in read_csv(MECHANISM_CSV):
        rows.append(
            {
                **row,
                "x": row["x"] if row["panel"] in ("C", "D") else as_float(row["x"]),
                "value": as_float(row["value"]),
                "lo": as_float(row["lo"]),
                "hi": as_float(row["hi"]),
                "n": int(row["n"]),
            }
        )
    return rows


def _style_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(INK)
    ax.spines["bottom"].set_color(INK)
    ax.tick_params(colors=INK, labelsize=7)
    ax.grid(axis="y", color=GRID, linewidth=0.45, alpha=0.8)
    ax.set_axisbelow(True)


def panel_a(ax: plt.Axes, rows: list[dict[str, object]]) -> None:
    data = sorted((row for row in rows if row["panel"] == "A"), key=lambda row: row["x"])
    x = np.array([row["x"] for row in data])
    y = np.array([row["value"] for row in data])
    lo = np.array([row["lo"] for row in data])
    hi = np.array([row["hi"] for row in data])
    ax.fill_between(x, lo, hi, color="#b9c0c8", alpha=0.42, linewidth=0)
    ax.plot(x, y, color=INK, linewidth=1.15, marker="o", markersize=2.6)
    ax.axhline(0, color="#777777", linestyle=(0, (4, 3)), linewidth=0.8)
    ax.axvline(1, color="#cf76ac", linestyle=(0, (1, 2)), linewidth=0.9)
    ax.scatter([1], [y[0]], marker="D", s=34, facecolor="white", edgecolor="#cf76ac", linewidth=1.1, zorder=4)
    ax.set_title("a  Reported scarcity changes over time", loc="left", fontsize=9, fontweight="bold")
    ax.set_ylabel("High-scarcity contrast (pp)", fontsize=8)
    ax.set_xlim(0.2, 42.8)
    ax.set_xticks([1, 10, 20, 30, 42])
    ax.set_xlabel("year", fontsize=8)
    ax.text(0.08, 0.08, "year 1: matched worlds", transform=ax.transAxes, color="#b45c94", fontsize=6.5)
    _style_axis(ax)


def panel_b(ax: plt.Axes, rows: list[dict[str, object]]) -> None:
    data = [row for row in rows if row["panel"] == "B"]
    for label, color, key in (("with validators", BLUE, "with-validators"), ("no validator", ORANGE, "no-validator")):
        arm = sorted((row for row in data if row["series"] == f"lake_mead_level[{key}]"), key=lambda row: row["x"])
        x = np.array([row["x"] for row in arm])
        y = np.array([row["value"] for row in arm])
        lo = np.array([row["lo"] for row in arm])
        hi = np.array([row["hi"] for row in arm])
        ax.fill_between(x, lo, hi, color=color, alpha=0.12, linewidth=0)
        ax.plot(x, y, color=color, linewidth=1.1, marker="o", markersize=2.1, label=label)
    ax.axhline(895, color="#777777", linestyle=(0, (2, 2)), linewidth=0.75)
    ax.axvline(1, color="#cf76ac", linestyle=(0, (1, 2)), linewidth=0.9)
    ax.set_title("b  World states diverge", loc="left", fontsize=9, fontweight="bold")
    ax.set_ylabel("Lake Mead elevation (ft)", fontsize=8)
    ax.set_xlabel("year", fontsize=8)
    ax.set_xlim(0.2, 42.8)
    ax.set_xticks([1, 10, 20, 30, 42])
    ax.text(0.03, 0.04, "895 ft floor", transform=ax.transAxes, color="#555555", fontsize=7)
    ax.legend(frameon=False, fontsize=5.8, loc="upper left", bbox_to_anchor=(0.0, 1.02),
              ncol=2, handlelength=1.5, columnspacing=0.8)
    _style_axis(ax)


def panel_c(ax: plt.Axes, rows: list[dict[str, object]]) -> None:
    data = [row for row in rows if row["panel"] == "C"]
    labels = []
    all_rows = []
    nr_rows = []
    for row in data:
        if row["series"].endswith("all decisions]"):
            labels.append(str(row["x"]))
            all_rows.append(row)
        elif row["series"].endswith("never retried (retry_count=0)]"):
            nr_rows.append(row)
    order = np.arange(len(labels))
    all_vals = np.array([row["value"] for row in all_rows])
    nr_vals = np.array([row["value"] for row in nr_rows])
    all_lo = np.array([row["lo"] for row in all_rows])
    all_hi = np.array([row["hi"] for row in all_rows])
    nr_lo = np.array([row["lo"] for row in nr_rows])
    nr_hi = np.array([row["hi"] for row in nr_rows])
    ax.barh(order + 0.18, all_vals, height=0.30, color="#77c7b4", label="all decisions")
    ax.barh(order - 0.18, nr_vals, height=0.30, color="#08a083", hatch="//", edgecolor=INK, label="never retried")
    for y, value, lo, hi in zip(order + 0.18, all_vals, all_lo, all_hi):
        if not math.isnan(lo) and not math.isnan(hi):
            ax.errorbar(value, y, xerr=[[value - lo], [hi - value]], color=INK, linewidth=0.7, capsize=2)
    for y, value, lo, hi in zip(order - 0.18, nr_vals, nr_lo, nr_hi):
        if not math.isnan(lo) and not math.isnan(hi):
            ax.errorbar(value, y, xerr=[[value - lo], [hi - value]], color=INK, linewidth=0.7, capsize=2)
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.set_title("c  Filtering changes the gap", loc="left", fontsize=9, fontweight="bold")
    ax.set_yticks(order)
    ax.set_yticklabels(labels, fontsize=6.5)
    ax.set_xlabel("High-scarcity contrast (pp)", fontsize=8)
    ax.set_xlim(-10, 80)
    ax.legend(frameon=False, fontsize=6.5, loc="upper right", ncol=2,
              handlelength=1.5, columnspacing=0.8)
    _style_axis(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.45, alpha=0.8)


def write_figure_csv() -> None:
    existing = [row for row in read_csv(MECHANISM_CSV) if row["panel"] in ("A", "B", "C")]
    fields = ["panel", "series", "x", "value", "lo", "hi", "unit", "n", "note"]
    with FIGURE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(existing)


def build_figure(rows: list[dict[str, object]]) -> None:
    plt.rcParams.update({"font.family": "serif", "font.size": 8})
    fig = plt.figure(figsize=(7.7, 5.55), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=(1.0, 0.9), hspace=0.08, wspace=0.22)
    panel_a(fig.add_subplot(grid[0, 0]), rows)
    panel_b(fig.add_subplot(grid[0, 1]), rows)
    panel_c(fig.add_subplot(grid[1, :]), rows)
    fig.patch.set_facecolor("white")
    ACTIVE_FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ACTIVE_FIGURE.with_suffix(".png"), dpi=300, facecolor="white")
    fig.savefig(ACTIVE_FIGURE.with_suffix(".pdf"), facecolor="white")
    plt.close(fig)
    write_figure_csv()


def main() -> None:
    rows = flood_rows()
    if len(rows) != 14:
        raise RuntimeError(f"Expected 14 pinned configurations, found {len(rows)}")
    if sum(row["setting"] == "flood" for row in rows) != 9:
        raise RuntimeError("Flood must retain nine configurations after excluding only the B6 run")
    if sum(row["setting"] == "irrigation" for row in rows) != 5:
        raise RuntimeError("Expected five irrigation configurations")
    b6 = [row for row in rows if row["setting"] == "flood" and row["model"] == "gemma3:4b"]
    if len(b6) != 1 or b6[0]["n_gov"] != 4 or b6[0]["n_noval"] != 5 or round(float(b6[0]["contrast"]), 4) != 0.3487:
        raise RuntimeError("Pinned Flood B6 eligibility record changed")
    contrasts = {setting: [row["contrast"] for row in rows if row["setting"] == setting] for setting in ("flood", "irrigation")}
    if round(min(contrasts["irrigation"]) - max(contrasts["flood"]), 2) != 15.03:
        raise RuntimeError("Pinned cross-testbed separation changed")
    summary = build_summary(rows)
    write_summary(summary)
    build_figure(mechanism_rows())
    print(f"wrote {ACTIVE_FIGURE.with_suffix('.png')}")
    print(f"wrote {ACTIVE_FIGURE.with_suffix('.pdf')}")
    print(f"wrote {SUMMARY_CSV}")
    print(f"wrote {SUMMARY_TEX}")
    for row in summary:
        print(row)


if __name__ == "__main__":
    main()
