#!/usr/bin/env python
"""Build the executed-action denominator comparison used as Paper Figure 4.

The source CSV is frozen evidence. This builder changes only the display: it
uses a dumbbell rather than arrows so the endpoint direction and the signed
conditional-minus-all gap cannot be confused.
"""
from __future__ import annotations

import csv
import hashlib
import math
import os
import statistics
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import t as student_t


SUBMISSION = Path(__file__).resolve().parents[1]
SOURCE = SUBMISSION / "supplement" / "fig3_denominator_gap.csv"
OUTPUT = SUBMISSION / "figures" / "active" / "fig3_consequence"
GAP_INTERVAL_CSV = SUBMISSION / "supplement" / "fig4_gap_intervals.csv"
PER_SEED_CSV = SUBMISSION / "supplement" / "fig4_per_seed.csv"
GENERATION_MARKER = SUBMISSION / "supplement" / "fig4_generation.sha256"
ORDER = ["gemma3:4b", "gemma3:12b", "gemma4:e2b", "gemma4:e4b", "ministral3:8b"]
EXPECTED_SEEDS = {
    "gemma3:4b": {42, 43, 44, 45, 46},
    "gemma3:12b": {42, 43, 44},
    "gemma4:e2b": {42, 43, 44, 45, 46},
    "gemma4:e4b": {42, 43, 44, 45, 46},
    "ministral3:8b": {42, 43, 44},
}

BLUE = "#1479b8"
ORANGE = "#d66a05"
INK = "#202020"
GRID = "#dddddd"
PDF_METADATA = {
    "Creator": "WAGF ICLR 2027 figure builder",
    "CreationDate": None,
    "ModDate": None,
}


def read_rows() -> dict[str, dict[str, float]]:
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    parsed: dict[str, dict[str, float]] = {}
    for row in rows:
        model = row["model"]
        parsed[model] = {
            key: float(row[key])
            for key in (
                "cond_delta_pp",
                "cond_ci_lo",
                "cond_ci_hi",
                "all_delta_pp",
                "all_ci_lo",
                "all_ci_hi",
                "gap_pp",
            )
        }
        expected = parsed[model]["cond_delta_pp"] - parsed[model]["all_delta_pp"]
        if not math.isclose(expected, parsed[model]["gap_pp"], abs_tol=0.011):
            raise RuntimeError(f"{model}: signed gap does not match source endpoints")
    if set(parsed) != set(ORDER):
        raise RuntimeError("Figure 4 source models changed")
    return parsed


def read_per_seed() -> dict[str, list[dict[str, float]]]:
    grouped: dict[str, list[dict[str, float]]] = {model: [] for model in ORDER}
    seen: set[tuple[str, int]] = set()
    with PER_SEED_CSV.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    fields = (
        "conditional_validator_on_pct",
        "conditional_no_validator_pct",
        "all_validator_on_pct",
        "all_no_validator_pct",
        "conditional_delta_pp",
        "all_delta_pp",
        "gap_pp",
    )
    for row in rows:
        model = row["model"]
        if model not in grouped:
            raise RuntimeError(f"Unexpected Figure 4 model: {model}")
        seed = int(row["seed"])
        key = (model, seed)
        if key in seen:
            raise RuntimeError(f"Duplicate Figure 4 per-seed row: {model}/{seed}")
        seen.add(key)
        values = {field: float(row[field]) for field in fields}
        if not all(math.isfinite(value) for value in values.values()):
            raise RuntimeError(f"Non-finite Figure 4 value: {model}/{seed}")
        expected_cond = values["conditional_no_validator_pct"] - values["conditional_validator_on_pct"]
        expected_all = values["all_no_validator_pct"] - values["all_validator_on_pct"]
        expected_gap = expected_cond - expected_all
        if not math.isclose(expected_cond, values["conditional_delta_pp"], abs_tol=1e-9):
            raise RuntimeError(f"Conditional delta mismatch: {model}/{seed}")
        if not math.isclose(expected_all, values["all_delta_pp"], abs_tol=1e-9):
            raise RuntimeError(f"All-decision delta mismatch: {model}/{seed}")
        if not math.isclose(expected_gap, values["gap_pp"], abs_tol=1e-9):
            raise RuntimeError(f"Gap mismatch: {model}/{seed}")
        grouped[model].append({"seed": float(seed), **values})
    for model, model_rows in grouped.items():
        seeds = {int(row["seed"]) for row in model_rows}
        if seeds != EXPECTED_SEEDS[model]:
            raise RuntimeError(f"Figure 4 seed set changed for {model}: {sorted(seeds)}")
    return grouped


def gap_intervals(data: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Compute paired uncertainty from the submission's frozen per-seed cells."""
    grouped = read_per_seed()
    intervals: dict[str, dict[str, float]] = {}
    for model in ORDER:
        rows = grouped[model]
        values = [row["gap_pp"] for row in rows]
        mean = statistics.mean(values)
        standard_error = statistics.stdev(values) / math.sqrt(len(values))
        critical = float(student_t.ppf(0.975, len(values) - 1))
        intervals[model] = {
            "gap_pp": mean,
            "gap_ci_lo": mean - critical * standard_error,
            "gap_ci_hi": mean + critical * standard_error,
            "n_paired": float(len(values)),
        }
        checks = {
            "cond_delta_pp": statistics.mean(row["conditional_delta_pp"] for row in rows),
            "all_delta_pp": statistics.mean(row["all_delta_pp"] for row in rows),
            "gap_pp": mean,
        }
        for prefix, field in (("cond", "conditional_delta_pp"), ("all", "all_delta_pp")):
            endpoint_values = [row[field] for row in rows]
            endpoint_mean = statistics.mean(endpoint_values)
            endpoint_se = statistics.stdev(endpoint_values) / math.sqrt(len(endpoint_values))
            endpoint_ci = (
                endpoint_mean - critical * endpoint_se,
                endpoint_mean + critical * endpoint_se,
            )
            checks[f"{prefix}_ci_lo"] = endpoint_ci[0]
            checks[f"{prefix}_ci_hi"] = endpoint_ci[1]
        for field, value in checks.items():
            if not math.isclose(value, data[model][field], abs_tol=0.00011):
                raise RuntimeError(f"{model}: paired {field} does not match the display source")

    if set(intervals) != set(ORDER):
        raise RuntimeError("Figure 4 paired-gap models changed")
    return intervals


def write_intervals(intervals: dict[str, dict[str, float]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["model", "n_paired", "gap_pp", "gap_ci_lo", "gap_ci_hi"],
        )
        writer.writeheader()
        for model in ORDER:
            writer.writerow({"model": model, **intervals[model]})


def render(data: dict[str, dict[str, float]], intervals: dict[str, dict[str, float]], output: Path) -> None:
    plt.rcParams.update({"font.family": "serif", "font.size": 8, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(7.7, 2.75), constrained_layout=True)

    y_positions = list(reversed(range(len(ORDER))))
    for y, model in zip(y_positions, ORDER):
        row = data[model]
        cond = row["cond_delta_pp"]
        all_decisions = row["all_delta_pp"]
        ax.plot([cond, all_decisions], [y, y], color="#555555", linewidth=1.05, zorder=2)
        ax.errorbar(
            cond,
            y,
            xerr=[[cond - row["cond_ci_lo"]], [row["cond_ci_hi"] - cond]],
            fmt="o",
            color=BLUE,
            ecolor=BLUE,
            elinewidth=2.4,
            alpha=0.95,
            capsize=0,
            markersize=5.8,
            zorder=3,
        )
        ax.errorbar(
            all_decisions,
            y,
            xerr=[[all_decisions - row["all_ci_lo"]], [row["all_ci_hi"] - all_decisions]],
            fmt="s",
            color=ORANGE,
            ecolor=ORANGE,
            elinewidth=2.4,
            alpha=0.95,
            capsize=0,
            markersize=5.3,
            zorder=4,
        )
        gap = intervals[model]
        ax.text(
            46.5,
            y,
            f"{gap['gap_pp']:+.1f} [{gap['gap_ci_lo']:+.1f}, {gap['gap_ci_hi']:+.1f}]",
            va="center",
            ha="left",
            fontsize=7.7,
            color=INK,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.94, "pad": 1.0},
        )

    ax.axvline(0, color="#777777", linewidth=0.8, linestyle=(0, (4, 3)), zorder=0)
    ax.axvline(44.5, color="#bbbbbb", linewidth=0.6, zorder=0)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(ORDER, fontsize=8)
    ax.set_xlabel("Executed increase-rate contrast: no-validator - validator-on (pp)", fontsize=8.5)
    ax.text(53.5, len(ORDER) - 0.18, "Conditional - all\n(95% CI)", ha="center",
            va="bottom", fontsize=7.8, color="#444444",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.96, "pad": 1.0})
    ax.legend(
        handles=[
            Line2D([], [], marker="o", linestyle="none", color=BLUE,
                   label="conditional (high scarcity)"),
            Line2D([], [], marker="s", linestyle="none", color=ORANGE,
                   label="all decisions"),
        ],
        loc="upper left",
        frameon=False,
        fontsize=7.8,
        handletextpad=0.5,
    )
    ax.set_xticks([0, 10, 20, 30, 40])
    ax.grid(axis="x", color=GRID, linewidth=0.55, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", labelsize=7.5)
    ax.set_xlim(-2.0, 62.0)
    ax.set_ylim(-0.65, len(ORDER) - 0.25)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output.with_suffix(".png"), dpi=300, facecolor="white")
    fig.savefig(output.with_suffix(".pdf"), facecolor="white", metadata=PDF_METADATA)
    plt.close(fig)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_generation_marker(paths: list[Path]) -> None:
    text = "\n".join(
        f"{digest(path)}  {path.relative_to(SUBMISSION).as_posix()}"
        for path in paths
    ) + "\n"
    temporary = GENERATION_MARKER.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, GENERATION_MARKER)


def build() -> None:
    data = read_rows()
    intervals = gap_intervals(data)
    with tempfile.TemporaryDirectory(prefix="figure4-", dir=SUBMISSION) as temporary:
        temp = Path(temporary)
        output = temp / "fig3_consequence"
        intervals_csv = temp / GAP_INTERVAL_CSV.name
        render(data, intervals, output)
        write_intervals(intervals, intervals_csv)
        promotions = {
            output.with_suffix(".png"): OUTPUT.with_suffix(".png"),
            output.with_suffix(".pdf"): OUTPUT.with_suffix(".pdf"),
            intervals_csv: GAP_INTERVAL_CSV,
        }
        for source, destination in promotions.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
    write_generation_marker(list(promotions.values()))


if __name__ == "__main__":
    build()
    print(f"wrote {OUTPUT.with_suffix('.png')}")
    print(f"wrote {OUTPUT.with_suffix('.pdf')}")
    print(f"wrote {GAP_INTERVAL_CSV}")
