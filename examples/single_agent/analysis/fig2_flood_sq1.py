"""Flood Fig 2: consistency with appraisal and variety of household actions.

Panel (a) answers the first half of SQ1: whether LLM-driven agents behave
consistently with their own appraisal. Panel (b) answers the second half:
whether this can be ensured without making behaviour less varied.

Per-year EHE falls below 0.5 later in both groups as households converge on
insurance. The pre-registered 0.5 warning line applies to EHE pooled over the
ten years, so it appears only on the pooled axis. The rule-based baseline EHE
is reported in the caption or a table, not drawn in this figure.

    python -m examples.single_agent.analysis.fig2_flood_sq1 \\
        --results-root DIR --out-dir DIR
"""
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Any, Sequence

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.patches import Patch

from examples.single_agent.analysis.paper_measures import MetricsError, projection_run

SEEDS = set(range(42, 47))
YEARS = range(1, 11)
MODEL = "gemma3:4b"
# Flood years are fixed by the scenario, not read from the runs; the post-run
# checks (flood_run_checks.py, 2026-10-16) found floods in years 3, 4 and 9 in all 15 runs.
FLOOD_SPANS = ((3, 4), (9, 9))
GROUPS = {
    "strict": ("Governed LLM", "#0072B2"),
    "disabled": ("LLM, no validator", "#D55E00"),
}


def _finite(row: dict[str, Any], key: str, run: Path) -> float:
    value = row.get(key)
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MetricsError(f"{run}: {key} must be present and finite, got {value!r}") from exc
    if not math.isfinite(number):
        raise MetricsError(f"{run}: {key} must be finite, got {value!r}")
    return number


def _load_group(results_root: Path, profile: str, commit: str) -> list[dict[str, Any]]:
    folder = results_root / f"JOH_{profile}_defaults_gemma3_4b_{commit}"
    if not folder.is_dir():
        raise MetricsError(f"Missing group folder: {folder}")
    runs = sorted(path for path in folder.glob("Run_*") if path.is_dir())
    expected_names = {f"Run_{seed}" for seed in SEEDS}
    if len(runs) != 5 or {path.name for path in runs} != expected_names:
        raise MetricsError(
            f"{folder}: expected exactly 5 run folders Run_42 through Run_46; "
            f"found {[path.name for path in runs]}"
        )
    rows = []
    for run in runs:
        row = projection_run(run)
        if row.get("seed") not in SEEDS or run.name != f"Run_{row['seed']}":
            raise MetricsError(f"{run}: expected matching seed in 42..46, got {row.get('seed')!r}")
        recorded = (row.get("governance_profile"), row.get("retry_feedback_mode"), row.get("model"))
        if recorded != (profile, "full", MODEL) or not str(row.get("commit") or "").startswith(commit):
            raise MetricsError(f"{run}: manifest says profile/feedback/model {recorded}, "
                               f"commit {row.get('commit')!r}; expected ({profile!r}, 'full', {MODEL!r}), {commit}")
        years = {key for key in row if re.fullmatch(r"year_\d+_ehe", key)}
        if years != {f"year_{year}_ehe" for year in YEARS}:
            raise MetricsError(f"{run}: expected yearly EHE for years 1..10 only, got {sorted(years)}")
        for key in ("n_aborted", "physical_count"):
            if row.get(key) != 0:
                raise MetricsError(f"{run}: expected {key} == 0, got {row.get(key)!r}")
        for key in ("first_behavioural_pct", "behavioural_ibr_pct", "ehe"):
            _finite(row, key, run)
        if profile == "disabled":
            difference = abs(row["first_behavioural_pct"] - row["behavioural_ibr_pct"])
            if difference >= 1e-9:
                raise MetricsError(
                    f"{run}: no-validator first_behavioural_pct must equal "
                    f"behavioural_ibr_pct within abs diff < 1e-9; got {difference}"
                )
        for year in YEARS:
            _finite(row, f"year_{year}_ehe", run)
        rows.append(row)
    if {row["seed"] for row in rows} != SEEDS:
        raise MetricsError(f"{folder}: expected seeds 42..46 exactly once")
    return rows


def _values(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([row[key] for row in rows], dtype=float)


def _summary(label: str, rows: list[dict[str, Any]], key: str) -> None:
    values = _values(rows, key)
    per_seed = ", ".join(f"{row['seed']}={value:.2f}" for row, value in zip(rows, values))
    print(f"{label}: per seed [{per_seed}]; median {np.median(values):.2f}; "
          f"min {values.min():.2f}; max {values.max():.2f}")


def _plot(groups: dict[str, list[dict[str, Any]]], out_dir: Path) -> None:
    plt.rcParams.update({"font.family": "Arial", "axes.spines.top": False,
                         "axes.spines.right": False, "font.size": 7})
    fig = plt.figure(figsize=(7.2, 2.9))
    grid = gridspec.GridSpec(1, 3, width_ratios=[1.0, 2.2, 0.6], wspace=0.3)
    a = fig.add_subplot(grid[0])
    b = fig.add_subplot(grid[1])
    b2 = fig.add_subplot(grid[2], sharey=b)
    fig.subplots_adjust(left=0.09, right=0.985, bottom=0.22, top=0.86)

    bars = [
        ("Governed:\nfirst proposal", "Governed first proposal", "strict",
         "first_behavioural_pct", 0.45),
        ("Governed:\nexecuted", "Governed executed", "strict", "behavioural_ibr_pct", 1.0),
        ("No validator:\nexecuted", "No validator executed", "disabled", "behavioural_ibr_pct", 1.0),
    ]
    largest = 0.0
    for x, (_, label, profile, key, alpha) in enumerate(bars):
        rows = groups[profile]
        values = _values(rows, key)
        largest = max(largest, float(values.max()))
        a.bar(x, np.median(values), color=GROUPS[profile][1], alpha=alpha, width=0.6)
        a.vlines(x, values.min(), values.max(), color="k", lw=0.8)
        a.scatter([x] * len(values), values, s=6, color="k", zorder=3)
        a.annotate(f"{np.median(values):.1f}%", (x, values.max()), xytext=(0, 4),
                   textcoords="offset points", ha="center", va="bottom", fontsize=6)
        _summary(label, rows, key)
    a.set_xticks(range(3), [item[0] for item in bars], fontsize=6)
    a.set_ylabel("Decisions contradicting the\nhousehold's own appraisal (%)")
    a.set_ylim(0, largest * 1.25 if largest else 1.0)
    a.set_title("Consistent with own appraisal?", fontsize=7, loc="left", pad=2)

    years = np.array(list(YEARS))
    for first, last in FLOOD_SPANS:  # adjacent flood years share one span, so no overlap line
        b.axvspan(first - 0.5, last + 0.5, color="#BBBBBB", alpha=0.25, zorder=0)
    for profile, (label, color) in GROUPS.items():
        values = np.array([_values(groups[profile], f"year_{year}_ehe") for year in YEARS])
        b.fill_between(years, values.min(axis=1), values.max(axis=1), color=color, alpha=0.18, lw=0)
        b.plot(years, np.median(values, axis=1), color=color, lw=1.5, marker="o",
               markersize=3, label=label)
    b.set_xticks(years)
    b.set_xlabel("Year")
    b.set_xlim(0.5, 10.5)
    b.set_ylabel("Variety of actions (EHE)")
    b.set_ylim(0, 1)
    b.set_title("Varied behaviour? By year", fontsize=7, loc="left", pad=2)
    handles, labels = b.get_legend_handles_labels()
    b.legend(handles + [Patch(facecolor="#BBBBBB", alpha=0.25)], labels + ["Flood year"],
             fontsize=6, frameon=False, loc="upper right")

    for x, (profile, (label, color)) in enumerate(GROUPS.items()):
        values = _values(groups[profile], "ehe")
        median = float(np.median(values))
        b2.vlines(x, values.min(), values.max(), color="k", lw=0.8)
        b2.scatter([x] * len(values), values, s=6, color="k", zorder=3)
        b2.plot(x, median, marker="o", markersize=5, color=color, zorder=4)
        b2.annotate(f"{median:.2f}", (x, median), xytext=(4, 5), textcoords="offset points",
                    fontsize=6, ha="left", va="bottom")
        _summary(f"Pooled EHE {label}", groups[profile], "ehe")
    b2.axhline(0.5, color="#777777", ls="--", lw=0.8)
    b2.text(0.04, 0.515, "Warning line (0.5)", transform=b2.get_yaxis_transform(),
            fontsize=6, color="#666666", va="bottom")
    b2.set_xticks([0, 1], ["Governed", "No\nvalidator"])
    b2.set_xlim(-0.6, 1.6)
    b2.tick_params(axis="y", left=False, labelleft=False)
    b2.spines["left"].set_visible(False)
    b2.set_title("All years", fontsize=7, loc="left", pad=2)

    for ax in (a, b, b2):
        ax.grid(axis="y", alpha=0.3)
        ax.tick_params(labelsize=6)
    for ax, letter, dx in ((a, "a", -0.25), (b, "b", -0.14)):
        ax.text(dx, 1.02, letter, transform=ax.transAxes, fontsize=9, fontweight="bold")
    for profile, (label, _) in GROUPS.items():
        medians = [np.median(_values(groups[profile], f"year_{year}_ehe")) for year in YEARS]
        print(f"{label} per-year EHE medians: " +
              ", ".join(f"year {year}={value:.2f}" for year, value in zip(YEARS, medians)))
    out_dir.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf"):
        destination = out_dir / f"Fig2_flood_sq1.{extension}"
        fig.savefig(destination, dpi=300, bbox_inches="tight")
        print(f"Wrote {destination}")
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--commit", default="9c4ba160")
    args = parser.parse_args(argv)
    results_root = args.results_root.resolve()
    out_dir = args.out_dir.resolve()
    if out_dir.is_relative_to(results_root):
        raise MetricsError("--out-dir must be outside --results-root")
    groups = {profile: _load_group(results_root, profile, args.commit) for profile in GROUPS}
    _plot(groups, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
