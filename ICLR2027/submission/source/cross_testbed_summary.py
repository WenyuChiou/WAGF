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
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parents[3]
ICLR = REPO / "ICLR2027"
SUBMISSION = ICLR / "submission"
UPSTREAM_RELEASE_CSV = ICLR / "flood_control_contrasts.csv"
MECHANISM_CSV = SUBMISSION / "supplement" / "fig2_mechanism.csv"
ACTIVE_FIGURE = SUBMISSION / "figures" / "active" / "fig2_mechanism"
SUMMARY_CSV = SUBMISSION / "supplement" / "cross_testbed_summary.csv"
RELEASE_CELLS_CSV = SUBMISSION / "supplement" / "cross_testbed_release_cells.csv"
SUMMARY_TEX = SUBMISSION / "supplement" / "table3_cross_testbed.tex"
PRESSURE_JSON = SUBMISSION / "supplement" / "enforcement_pressure_source.json"
TABLE1_CSV = SUBMISSION / "supplement" / "table1_cells.csv"
PROVENANCE_JSON = SUBMISSION / "supplement" / "cross_testbed_provenance.json"
GENERATION_MARKER = SUBMISSION / "supplement" / "cross_testbed_generation.sha256"
EXPECTED_KEYS = {
    ("irrigation", model)
    for model in ("gemma3:4b", "gemma3:12b", "gemma4:e2b", "gemma4:e4b", "ministral3:8b")
} | {
    ("flood", model)
    for model in (
        "gemma3:4b", "gemma3:12b", "gemma3:27b", "ministral3:3b",
        "ministral3:8b", "ministral3:14b", "gemma4:e2b", "gemma4:e4b", "gemma4:26b",
    )
}


INK = "#202020"
BLUE = "#1479b8"
ORANGE = "#d66a05"
GRID = "#d9d9d9"
PDF_METADATA = {
    "Creator": "WAGF ICLR 2027 figure builder",
    "CreationDate": None,
    "ModDate": None,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str) -> float:
    return float(value) if value not in ("", None) else math.nan


def require_finite(value: object, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"{label} must be finite")
    return number


def release_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in read_csv(RELEASE_CELLS_CSV):
        parsed = {
                "setting": row["setting"],
                "model": row["model"],
                "gov": require_finite(row["validator_on_pct"], "validator_on_pct"),
                "noval": require_finite(row["no_validator_pct"], "no_validator_pct"),
                "contrast": require_finite(row["contrast_pp"], "contrast_pp"),
                "n_gov": int(row["n_validator_on"]),
                "n_noval": int(row["n_no_validator"]),
                "note": row["release_note"],
            }
        if not (0 <= float(parsed["gov"]) <= 100 and 0 <= float(parsed["noval"]) <= 100):
            raise RuntimeError(f"Release percentages outside [0, 100]: {parsed['setting']}/{parsed['model']}")
        if int(parsed["n_gov"]) <= 0 or int(parsed["n_noval"]) <= 0:
            raise RuntimeError(f"Release run count must be positive: {parsed['setting']}/{parsed['model']}")
        rows.append(parsed)
    return rows


def audit_upstream_release(rows: list[dict[str, object]]) -> None:
    """Fail if the historical handoff source disagrees with the frozen release CSV."""
    upstream = []
    for row in read_csv(UPSTREAM_RELEASE_CSV):
        upstream.append(
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
    if rows != upstream:
        raise RuntimeError("Canonical Table 3 release cells disagree with the upstream handoff CSV")


def pressure_ranges() -> dict[str, str]:
    source = json.loads(PRESSURE_JSON.read_text(encoding="utf-8"))
    ranges = source["ranges_pct"]
    expected = {"irrigation": [28.0, 63.0], "flood": [0.0, 0.638]}
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


def write_summary(summary: list[dict[str, object]], csv_path: Path, tex_path: Path) -> None:
    fields = [
        "setting",
        "n_configurations",
        "gov_range",
        "noval_range",
        "contrast_range",
        "contrast_mean",
        "pressure_range",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
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
        contrast_low, contrast_high = str(row["contrast_range"]).split("--")
        lines.append(
            f"{label} & {row['n_configurations']} & {row['gov_range']}\\% & "
            f"{row['noval_range']}\\% & ${contrast_low}$--${contrast_high}\\pp$ & "
            f"${row['contrast_mean']:+.2f}\\pp$ \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    tex_path.write_text("\n".join(lines), encoding="utf-8")


def build_provenance(rows: list[dict[str, object]], summary: list[dict[str, object]]) -> dict[str, object]:
    """Write the reviewer-facing audit trail behind the secondary Table 3.

    The release contrasts and the audit metadata come from different frozen
    files.  Keeping that join here prevents the manuscript caption from
    silently outrunning the machine-readable submission package.
    """
    audit_list = [row for row in read_csv(TABLE1_CSV) if row["testbed"] == "flood"]
    audit_models = [row["model"] for row in audit_list]
    if len(audit_models) != len(set(audit_models)):
        raise RuntimeError("Flood audit metadata contains duplicate model rows")
    audit_rows = {row["model"]: row for row in audit_list}
    release_rows = [row for row in rows if row["setting"] == "flood"]
    if set(audit_rows) != {str(row["model"]) for row in release_rows}:
        raise RuntimeError("Flood audit rows do not match the nine release configurations")

    configurations = []
    for row in release_rows:
        audit = audit_rows[str(row["model"])]
        alignment = audit["manifest_seeds_aligned"].strip().lower()
        if alignment not in {"true", "false"}:
            raise RuntimeError(f"Invalid reflection-alignment flag for {row['model']}")
        coverage_value = require_finite(
            audit["audit_coverage_pct_min"],
            f"minimum audit coverage for {row['model']}",
        )
        if not 0 <= coverage_value <= 100:
            raise RuntimeError(f"Audit coverage outside [0, 100] for {row['model']}")
        configurations.append(
            {
                "model": row["model"],
                "validator_on_pct": row["gov"],
                "no_validator_pct": row["noval"],
                "contrast_no_validator_minus_on_pp": row["contrast"],
                "n_validator_on_runs_release": row["n_gov"],
                "n_no_validator_runs_release": row["n_noval"],
                "minimum_audit_coverage_pct": coverage_value,
                "manifest_seed_ids_aligned_across_arms": alignment == "true",
                "release_note": row["note"],
            }
        )

    coverage = [float(row["minimum_audit_coverage_pct"]) for row in configurations]
    seed_id_mismatch_count = sum(
        not bool(row["manifest_seed_ids_aligned_across_arms"])
        for row in configurations
    )
    if seed_id_mismatch_count != 6 or min(coverage) != 70.5 or max(coverage) != 99.9:
        raise RuntimeError("Pinned Flood coverage or seed-ID alignment summary changed")

    b6 = next(row for row in configurations if row["model"] == "gemma3:4b")
    if b6["n_validator_on_runs_release"] != 4 or b6["n_no_validator_runs_release"] != 5:
        raise RuntimeError("B6 release run counts changed")

    return {
        "schema_version": "1.0",
        "table": "Table 3 secondary cross-testbed boundary check",
        "contrast_definition": "no-validator minus validator-on, in percentage points",
        "aggregation": "Each configuration is a mean of per-run means; table cells report ranges across configurations.",
        "sources": {
            "canonical_release_cells": "ICLR2027/submission/supplement/cross_testbed_release_cells.csv",
            "upstream_release_decision": "ICLR2027/flood_control_contrasts.csv",
            "coverage_and_manifest_seed_alignment": "ICLR2027/submission/supplement/table1_cells.csv",
            "governance_pressure_ranges": "ICLR2027/submission/supplement/enforcement_pressure_source.json",
            "blank_appraisal_denominator_audit": "SUBMISSION_2026/TAE/evidence/e2_flood_instrument.py",
        },
        "caption_claims": {
            "minimum_audit_coverage_pct_range": [min(coverage), max(coverage)],
            "manifest_seed_id_mismatch_configuration_count": seed_id_mismatch_count,
            "blank_appraisal_policy": "Retry-exhausted Flood rows with blank appraisal remain in the all-row denominator.",
            "b6_release_policy": "Exclude the divergent gemma3:4b governed Run_1; retain four governed and five no-validator runs.",
            "b6_included_sensitivity_pp": -1.16,
            "b6_excluded_release_contrast_pp": b6["contrast_no_validator_minus_on_pp"],
        },
        "summary_rows": summary,
        "flood_configurations": configurations,
    }


def write_provenance(payload: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def mechanism_rows() -> list[dict[str, object]]:
    rows = []
    for row in read_csv(MECHANISM_CSV):
        parsed = {
                **row,
                "x": row["x"] if row["panel"] in ("C", "D") else as_float(row["x"]),
                "value": as_float(row["value"]),
                "lo": as_float(row["lo"]),
                "hi": as_float(row["hi"]),
                "n": int(row["n"]),
            }
        if parsed["panel"] == "A" and parsed["series"] != "delta_high_appraisal_prevalence":
            continue
        if parsed["panel"] == "B" and not str(parsed["series"]).startswith("lake_mead_level["):
            continue
        if parsed["panel"] not in {"A", "B"}:
            continue
        for field in ("x", "value", "lo", "hi"):
            require_finite(parsed[field], f"mechanism {parsed['panel']} {field}")
        if not float(parsed["x"]).is_integer():
            raise RuntimeError(f"Mechanism year must be an integer: {parsed['x']}")
        if int(parsed["n"]) <= 0:
            raise RuntimeError("Mechanism sample size must be positive")
        if float(parsed["lo"]) > float(parsed["value"]) or float(parsed["value"]) > float(parsed["hi"]):
            raise RuntimeError("Mechanism interval does not contain its estimate")
        rows.append(parsed)
    panel_counts = {
        panel: sum(row["panel"] == panel for row in rows)
        for panel in ("A", "B")
    }
    if panel_counts != {"A": 42, "B": 84}:
        raise RuntimeError("Mechanism source must contain both active panels A and B")
    keys = [(str(row["panel"]), str(row["series"]), int(row["x"])) for row in rows]
    expected_keys = {
        ("A", "delta_high_appraisal_prevalence", year)
        for year in range(1, 43)
    } | {
        ("B", series, year)
        for series in ("lake_mead_level[with-validators]", "lake_mead_level[no-validator]")
        for year in range(1, 43)
    }
    if len(keys) != len(set(keys)) or set(keys) != expected_keys:
        raise RuntimeError("Mechanism source has duplicate, missing, or unexpected year/series keys")
    return rows


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
    ax.set_title("a  Reported high-scarcity gap over time", loc="left", fontsize=9, fontweight="bold")
    ax.set_ylabel("No-validator - validator-on (pp)", fontsize=8)
    ax.set_xlim(0.2, 42.8)
    ax.set_xticks([1, 10, 20, 30, 42])
    ax.set_xlabel("year", fontsize=8)
    ax.text(0.08, 0.08, "year 1: matched worlds", transform=ax.transAxes, color="#b45c94", fontsize=6.5)
    _style_axis(ax)


def panel_b(ax: plt.Axes, rows: list[dict[str, object]]) -> None:
    data = [row for row in rows if row["panel"] == "B"]
    for label, color, key in (("validator-on", BLUE, "with-validators"), ("no-validator", ORANGE, "no-validator")):
        arm = sorted((row for row in data if row["series"] == f"lake_mead_level[{key}]"), key=lambda row: row["x"])
        x = np.array([row["x"] for row in arm])
        y = np.array([row["value"] for row in arm])
        lo = np.array([row["lo"] for row in arm])
        hi = np.array([row["hi"] for row in arm])
        ax.fill_between(x, lo, hi, color=color, alpha=0.12, linewidth=0)
        ax.plot(x, y, color=color, linewidth=1.1, marker="o", markersize=2.1, label=label)
    ax.axhline(895, color="#777777", linestyle=(0, (2, 2)), linewidth=0.75)
    ax.axvline(1, color="#cf76ac", linestyle=(0, (1, 2)), linewidth=0.9)
    ax.set_title("b  Recorded worlds diverge after year 1", loc="left", fontsize=9, fontweight="bold")
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
    ax.set_title("c  Never-retried subset", loc="left", fontsize=9, fontweight="bold")
    ax.set_yticks(order)
    ax.set_yticklabels(labels, fontsize=6.5)
    ax.set_xlabel("High-scarcity contrast (pp)", fontsize=8)
    ax.set_xlim(-10, 80)
    ax.legend(frameon=False, fontsize=6.5, loc="upper right", ncol=2,
              handlelength=1.5, columnspacing=0.8)
    _style_axis(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.45, alpha=0.8)


def build_figure(rows: list[dict[str, object]], output: Path) -> None:
    plt.rcParams.update({"font.family": "serif", "font.size": 8, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig = plt.figure(figsize=(7.7, 3.15), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, wspace=0.22)
    panel_a(fig.add_subplot(grid[0, 0]), rows)
    panel_b(fig.add_subplot(grid[0, 1]), rows)
    fig.patch.set_facecolor("white")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output.with_suffix(".png"), dpi=300, facecolor="white")
    fig.savefig(
        output.with_suffix(".pdf"),
        facecolor="white",
        metadata=PDF_METADATA,
    )
    plt.close(fig)


def main() -> None:
    rows = release_rows()
    audit_upstream_release(rows)
    keys = [(str(row["setting"]), str(row["model"])) for row in rows]
    if len(keys) != len(set(keys)) or set(keys) != EXPECTED_KEYS:
        raise RuntimeError("Cross-testbed release cells have duplicate, missing, or unexpected configurations")
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
    provenance = build_provenance(rows, summary)
    mechanism = mechanism_rows()
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cross-testbed-", dir=SUBMISSION) as temporary:
        temp = Path(temporary)
        figure = temp / "fig2_mechanism"
        summary_csv = temp / SUMMARY_CSV.name
        summary_tex = temp / SUMMARY_TEX.name
        provenance_json = temp / PROVENANCE_JSON.name
        build_figure(mechanism, figure)
        write_summary(summary, summary_csv, summary_tex)
        write_provenance(provenance, provenance_json)
        promotions = {
            figure.with_suffix(".png"): ACTIVE_FIGURE.with_suffix(".png"),
            figure.with_suffix(".pdf"): ACTIVE_FIGURE.with_suffix(".pdf"),
            summary_csv: SUMMARY_CSV,
            summary_tex: SUMMARY_TEX,
            provenance_json: PROVENANCE_JSON,
        }
        for source, destination in promotions.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
    write_generation_marker(list(promotions.values()))
    print(f"wrote {ACTIVE_FIGURE.with_suffix('.png')}")
    print(f"wrote {ACTIVE_FIGURE.with_suffix('.pdf')}")
    print(f"wrote {SUMMARY_CSV}")
    print(f"verified canonical {RELEASE_CELLS_CSV}")
    print(f"wrote {SUMMARY_TEX}")
    print(f"wrote {PROVENANCE_JSON}")
    for row in summary:
        print(row)


if __name__ == "__main__":
    main()
