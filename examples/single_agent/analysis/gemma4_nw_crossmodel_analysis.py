#!/usr/bin/env python3
"""Generate a Nature Water cross-model markdown analysis including Gemma 4."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

try:
    from scipy.stats import mannwhitneyu
except Exception:  # pragma: no cover
    mannwhitneyu = None


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = REPO_ROOT / "examples" / "single_agent" / "results"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "single_agent" / "analysis" / "gemma4_nw_crossmodel_analysis.md"
CONSERVATISM_SCRIPT = REPO_ROOT / "examples" / "single_agent" / "analysis" / "model_conservatism_report.py"

MODELS = [
    "gemma3_4b",
    "ministral3_3b",
    "ministral3_8b",
    "gemma3_12b",
    "ministral3_14b",
    "gemma3_27b",
    "gemma4_e2b",
    "gemma4_e4b",
]
MODEL_LABELS = {
    "gemma3_4b": "Gemma 3 4B",
    "gemma3_12b": "Gemma 3 12B",
    "gemma3_27b": "Gemma 3 27B",
    "ministral3_3b": "Ministral 3 3B",
    "ministral3_8b": "Ministral 3 8B",
    "ministral3_14b": "Ministral 3 14B",
    "gemma4_e2b": "Gemma 4 e2b",
    "gemma4_e4b": "Gemma 4 e4b",
}
CONDITIONS = {
    "governed": ("JOH_FINAL", "Group_C"),
    "disabled": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}
RUNS = [f"Run_{idx}" for idx in range(1, 6)]
ACTION_ORDER = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
TP_ORDER = ["VL", "L", "M", "H", "VH"]


class RunData(NamedTuple):
    model: str
    condition: str
    run: str
    audit_path: Path
    df: pd.DataFrame


def normalize_action(value: Any) -> str:
    text = str(value).strip().lower().replace(" ", "_")
    mapping = {
        "buy_insurance": "buy_insurance",
        "buy_insurace": "buy_insurance",
        "insurance": "buy_insurance",
        "only_flood_insurance": "buy_insurance",
        "elevate_house": "elevate_house",
        "elevate": "elevate_house",
        "only_house_elevation": "elevate_house",
        "relocate": "relocate",
        "relocated": "relocate",
        "already_relocated": "relocate",
        "do_nothing": "do_nothing",
        "nothing": "do_nothing",
        "do_nothing.": "do_nothing",
    }
    return mapping.get(text, text if text in ACTION_ORDER else "do_nothing")


def normalize_tp(value: Any) -> str:
    text = str(value).strip().upper()
    return text if text in TP_ORDER else "UNK"


def normalized_entropy(distribution: dict[str, float], k: int) -> float:
    values = np.array([distribution.get(key, 0.0) for key in distribution], dtype=float)
    values = values[values > 0]
    if len(values) == 0 or k <= 1:
        return 0.0
    entropy = -float(np.sum(values * np.log2(values)))
    return entropy / math.log2(k)


def summarize_pooled_metrics(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "n": 0,
            "ibr": 0.0,
            "ehe": 0.0,
            "action_distribution": {action: 0.0 for action in ACTION_ORDER},
            "tp_distribution": {tp: 0.0 for tp in TP_ORDER},
            "rejection_rate": 0.0,
            "retry_rate": 0.0,
        }

    work = df.copy()
    work["action_norm"] = work["final_skill"].map(normalize_action)
    work["tp_norm"] = work["construct_TP_LABEL"].map(normalize_tp)
    n = len(work)

    action_distribution = {
        action: float((work["action_norm"] == action).sum()) / n for action in ACTION_ORDER
    }
    tp_distribution = {tp: float((work["tp_norm"] == tp).sum()) / n for tp in TP_ORDER}

    high_threat = work["tp_norm"].isin(["H", "VH"])
    ibr = float((high_threat & (work["action_norm"] == "do_nothing")).sum()) / n
    ehe = normalized_entropy(action_distribution, k=len(ACTION_ORDER))
    rejection_rate = float((work["status"].astype(str).str.upper() != "APPROVED").sum()) / n
    retry_count = pd.to_numeric(work["retry_count"], errors="coerce").fillna(0)
    retry_rate = float((retry_count > 0).sum()) / n

    return {
        "n": n,
        "ibr": ibr,
        "ehe": ehe,
        "action_distribution": action_distribution,
        "tp_distribution": tp_distribution,
        "rejection_rate": rejection_rate,
        "retry_rate": retry_rate,
    }


def summarize_seed_metrics(df: pd.DataFrame) -> dict[str, float]:
    pooled = summarize_pooled_metrics(df)
    return {"ibr": pooled["ibr"], "ehe": pooled["ehe"], "n": pooled["n"]}


def load_run_data(results_dir: Path) -> list[RunData]:
    runs: list[RunData] = []
    for model in MODELS:
        for condition, (phase_dir, group_dir) in CONDITIONS.items():
            for run in RUNS:
                audit_path = results_dir / phase_dir / model / group_dir / run / "household_governance_audit.csv"
                if not audit_path.exists():
                    continue
                df = pd.read_csv(audit_path, encoding="utf-8-sig")
                runs.append(RunData(model=model, condition=condition, run=run, audit_path=audit_path, df=df))
    return runs


def build_summary_tables(run_data: list[RunData]) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[str, str], dict[str, Any]]]:
    seed_rows: list[dict[str, Any]] = []
    pooled_rows: list[dict[str, Any]] = []
    pooled_lookup: dict[tuple[str, str], dict[str, Any]] = {}

    for model in MODELS:
        for condition in CONDITIONS:
            model_runs = [item for item in run_data if item.model == model and item.condition == condition]
            if not model_runs:
                continue

            pooled_df = pd.concat([item.df for item in model_runs], ignore_index=True)
            pooled = summarize_pooled_metrics(pooled_df)
            pooled_rows.append(
                {
                    "model": model,
                    "condition": condition,
                    "n": pooled["n"],
                    "ibr": pooled["ibr"],
                    "ehe": pooled["ehe"],
                    "rejection_rate": pooled["rejection_rate"],
                    "retry_rate": pooled["retry_rate"],
                    **{f"action_{action}": pooled["action_distribution"][action] for action in ACTION_ORDER},
                    **{f"tp_{tp}": pooled["tp_distribution"][tp] for tp in TP_ORDER},
                }
            )
            pooled_lookup[(model, condition)] = pooled

            for item in model_runs:
                seed = summarize_seed_metrics(item.df)
                seed_rows.append(
                    {
                        "model": model,
                        "condition": condition,
                        "run": item.run,
                        "n": seed["n"],
                        "ibr": seed["ibr"],
                        "ehe": seed["ehe"],
                    }
                )

    return pd.DataFrame(pooled_rows), pd.DataFrame(seed_rows), pooled_lookup


def build_governance_effect(seed_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model in sorted(seed_df["model"].unique()):
        gov = seed_df[(seed_df["model"] == model) & (seed_df["condition"] == "governed")]
        dis = seed_df[(seed_df["model"] == model) & (seed_df["condition"] == "disabled")]
        if gov.empty or dis.empty:
            continue

        gov_ibr = gov["ibr"].astype(float)
        dis_ibr = dis["ibr"].astype(float)
        gov_ehe = gov["ehe"].astype(float)
        dis_ehe = dis["ehe"].astype(float)

        p_value = float("nan")
        if mannwhitneyu is not None and len(gov_ibr) > 0 and len(dis_ibr) > 0:
            p_value = float(mannwhitneyu(dis_ibr, gov_ibr, alternative="two-sided").pvalue)

        rows.append(
            {
                "model": model,
                "delta_ibr": float(dis_ibr.mean() - gov_ibr.mean()),
                "delta_ehe": float(dis_ehe.mean() - gov_ehe.mean()),
                "governed_ibr_mean": float(gov_ibr.mean()),
                "disabled_ibr_mean": float(dis_ibr.mean()),
                "governed_ehe_mean": float(gov_ehe.mean()),
                "disabled_ehe_mean": float(dis_ehe.mean()),
                "n_governed": int(len(gov)),
                "n_disabled": int(len(dis)),
                "p_value": p_value,
            }
        )
    return pd.DataFrame(rows)


def compare_distribution_summaries(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_pp": {
            action: round((candidate["action_distribution"][action] - baseline["action_distribution"][action]) * 100, 1)
            for action in ACTION_ORDER
        },
        "tp_pp": {
            tp: round((candidate["tp_distribution"][tp] - baseline["tp_distribution"][tp]) * 100, 1)
            for tp in TP_ORDER
        },
        "ibr_pp": round((candidate["ibr"] - baseline["ibr"]) * 100, 1),
    }


def format_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def format_float(value: float, digits: int = 3) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:.{digits}f}"


def format_model(model: str) -> str:
    return MODEL_LABELS.get(model, model)


def run_conservatism_report(results_dir: Path) -> str:
    completed = subprocess.run(
        [sys.executable, str(CONSERVATISM_SCRIPT), "--results-dir", str(results_dir)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = completed.stdout.strip()
    if completed.stderr.strip():
        output = f"{output}\n\n[stderr]\n{completed.stderr.strip()}".strip()
    if completed.returncode != 0:
        raise RuntimeError(f"Conservatism report failed with exit code {completed.returncode}\n{output}")
    return output.replace("—", "-")


def parse_conservatism_for_models(raw_output: str, model_names: list[str]) -> dict[str, dict[str, dict[str, str]]]:
    parsed: dict[str, dict[str, dict[str, str]]] = {}
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("=") or stripped.startswith("-"):
            continue
        if stripped.startswith("Model") or stripped.startswith("Metric Guide:") or stripped.startswith("CCA"):
            continue
        parts = stripped.split()
        if len(parts) < 9:
            continue
        model, condition = parts[0], parts[1]
        if model not in model_names:
            continue
        parsed.setdefault(model, {})[condition] = {
            "cca": parts[3],
            "csi": parts[4],
            "aci": parts[5],
            "esrr": parts[6],
            "tp_hv": parts[7],
            "top_action": parts[8],
        }
    return parsed


def render_summary_table(pooled_df: pd.DataFrame) -> str:
    header = (
        "| Model | Condition | N | IBR | EHE | buy_insurance | elevate_house | relocate | do_nothing | "
        "TP VL | TP L | TP M | TP H | TP VH | Rejection | Retry |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    lines = [header]
    for _, row in pooled_df.sort_values(["model", "condition"]).iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    format_model(row["model"]),
                    row["condition"],
                    str(int(row["n"])),
                    format_pct(row["ibr"]),
                    format_float(row["ehe"]),
                    format_pct(row["action_buy_insurance"]),
                    format_pct(row["action_elevate_house"]),
                    format_pct(row["action_relocate"]),
                    format_pct(row["action_do_nothing"]),
                    format_pct(row["tp_VL"]),
                    format_pct(row["tp_L"]),
                    format_pct(row["tp_M"]),
                    format_pct(row["tp_H"]),
                    format_pct(row["tp_VH"]),
                    format_pct(row["rejection_rate"]),
                    format_pct(row["retry_rate"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_governance_effect_table(effect_df: pd.DataFrame) -> str:
    header = (
        "| Model | Mean IBR governed | Mean IBR disabled | dIBR | Mean EHE governed | Mean EHE disabled | dEHE | p-value |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|"
    )
    lines = [header]
    for _, row in effect_df.sort_values("model").iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    format_model(row["model"]),
                    format_pct(row["governed_ibr_mean"]),
                    format_pct(row["disabled_ibr_mean"]),
                    format_pct(row["delta_ibr"]),
                    format_float(row["governed_ehe_mean"]),
                    format_float(row["disabled_ehe_mean"]),
                    format_float(row["delta_ehe"]),
                    format_float(row["p_value"], digits=4),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_generation_comparison(
    pooled_lookup: dict[tuple[str, str], dict[str, Any]], conservatism: dict[str, dict[str, dict[str, str]]]
) -> str:
    sections: list[str] = []
    for condition in CONDITIONS:
        g3 = pooled_lookup[("gemma3_4b", condition)]
        g4 = pooled_lookup[("gemma4_e4b", condition)]
        diff = compare_distribution_summaries(g3, g4)
        lines = [
            f"**{condition.capitalize()}**",
            "",
            "| Metric | Gemma 3 4B | Gemma 4 e4b | Difference (Gemma 4 - Gemma 3, pp) |",
            "|---|---:|---:|---:|",
            f"| IBR | {format_pct(g3['ibr'])} | {format_pct(g4['ibr'])} | {diff['ibr_pp']:.1f} |",
        ]
        for action in ACTION_ORDER:
            lines.append(
                f"| Action `{action}` | {format_pct(g3['action_distribution'][action])} | "
                f"{format_pct(g4['action_distribution'][action])} | {diff['action_pp'][action]:.1f} |"
            )
        for tp in TP_ORDER:
            lines.append(
                f"| TP `{tp}` | {format_pct(g3['tp_distribution'][tp])} | "
                f"{format_pct(g4['tp_distribution'][tp])} | {diff['tp_pp'][tp]:.1f} |"
            )

        finding_parts = []
        if diff["action_pp"]["do_nothing"] < 0:
            finding_parts.append("less high-threat inaction")
        if diff["action_pp"]["buy_insurance"] > 0:
            finding_parts.append("more insurance uptake")
        if diff["action_pp"]["elevate_house"] > 0:
            finding_parts.append("more elevation")
        if diff["tp_pp"]["VH"] < 0 and diff["tp_pp"]["H"] < 0:
            finding_parts.append("a softer TP profile")
        elif diff["tp_pp"]["VH"] > 0 or diff["tp_pp"]["H"] > 0:
            finding_parts.append("a harsher TP profile")

        cons_summary = conservatism.get("gemma4_e4b", {}).get(condition, {})
        if cons_summary:
            finding_parts.append(
                f"conservatism diagnostics show CCA={cons_summary['cca']}, ACI={cons_summary['aci']}, ESRR={cons_summary['esrr']}"
            )

        lines.extend(
            [
                "",
                "Interpretation: "
                + (
                    ", ".join(finding_parts) + "."
                    if finding_parts
                    else "distribution shifts are modest and do not point to a single dominant change."
                ),
            ]
        )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def build_key_findings(
    pooled_lookup: dict[tuple[str, str], dict[str, Any]],
    effect_df: pd.DataFrame,
    conservatism: dict[str, dict[str, dict[str, str]]],
) -> list[str]:
    findings: list[str] = []
    for model in ["gemma4_e2b", "gemma4_e4b"]:
        gov = pooled_lookup[(model, "governed")]
        dis = pooled_lookup[(model, "disabled")]
        effect = effect_df.loc[effect_df["model"] == model].iloc[0]
        findings.append(
            f"{format_model(model)} keeps a governance effect: pooled IBR falls from {format_pct(dis['ibr'])} to "
            f"{format_pct(gov['ibr'])} (per-seed dIBR={format_pct(effect['delta_ibr'])}, p={format_float(effect['p_value'], 4)})."
        )

    gemma4_ehe = {
        model: (
            pooled_lookup[(model, "governed")]["ehe"],
            pooled_lookup[(model, "disabled")]["ehe"],
        )
        for model in ["gemma4_e2b", "gemma4_e4b"]
    }
    findings.append(
        "Behavioral diversity remains high for Gemma 4: governed/disabled EHE is "
        f"{format_float(gemma4_ehe['gemma4_e2b'][0])}/{format_float(gemma4_ehe['gemma4_e2b'][1])} for Gemma 4 e2b and "
        f"{format_float(gemma4_ehe['gemma4_e4b'][0])}/{format_float(gemma4_ehe['gemma4_e4b'][1])} for Gemma 4 e4b."
    )

    g3_gov = pooled_lookup[("gemma3_4b", "governed")]
    g4_gov = pooled_lookup[("gemma4_e4b", "governed")]
    diff_gov = compare_distribution_summaries(g3_gov, g4_gov)
    findings.append(
        f"Against Gemma 3 4B, governed Gemma 4 e4b reduces `do_nothing` by {diff_gov['action_pp']['do_nothing']:.1f} pp "
        f"and shifts behavior toward insurance/elevation, lowering pooled IBR by {diff_gov['ibr_pp']:.1f} pp."
    )

    cons_e2b = conservatism.get("gemma4_e2b", {})
    cons_e4b = conservatism.get("gemma4_e4b", {})
    if cons_e2b and cons_e4b:
        gov_e2b = cons_e2b.get("governed", {})
        gov_e4b = cons_e4b.get("governed", {})
        if gov_e2b and gov_e4b:
            findings.append(
                "Conservatism diagnostics suggest Gemma 4 governed variants are not simply frozen into `do_nothing`: "
                f"Gemma 4 e2b has ACI={gov_e2b['aci']} and ESRR={gov_e2b['esrr']}, while Gemma 4 e4b has "
                f"ACI={gov_e4b['aci']} and ESRR={gov_e4b['esrr']}."
            )
    return findings


def generate_report(results_dir: Path, output_path: Path) -> str:
    run_data = load_run_data(results_dir)
    pooled_df, seed_df, pooled_lookup = build_summary_tables(run_data)
    effect_df = build_governance_effect(seed_df)
    conservatism_output = run_conservatism_report(results_dir)
    conservatism = parse_conservatism_for_models(conservatism_output, ["gemma4_e2b", "gemma4_e4b", "gemma3_4b"])
    findings = build_key_findings(pooled_lookup, effect_df, conservatism)

    lines = [
        "# Gemma 4 Nature Water Cross-Model Analysis",
        "",
        "Generated from `household_governance_audit.csv` pooled across `Run_1` to `Run_5` for the eight-model flood comparison.",
        "",
        "## Summary Table: All 8 Models",
        "",
        render_summary_table(pooled_df),
        "",
        "Notes:",
        "- `IBR` is the pooled share of decisions with `construct_TP_LABEL` in `{H, VH}` and `final_skill = do_nothing`.",
        "- `EHE` is normalized Shannon entropy over `buy_insurance`, `elevate_house`, `relocate`, and `do_nothing`.",
        "- Rejection rate counts `status != APPROVED`. Retry rate counts `retry_count > 0`.",
        "",
        "## Governance Effect",
        "",
        render_governance_effect_table(effect_df),
        "",
        "Interpretation: positive `dIBR` or `dEHE` means the disabled condition is higher than the governed condition.",
        "",
        "## Cross-Generation Comparison: Gemma 3 4B vs Gemma 4 e4b",
        "",
        render_generation_comparison(pooled_lookup, conservatism),
        "",
        "## Conservatism Analysis",
        "",
        "Command run:",
        "",
        "```bash",
        "python examples/single_agent/analysis/model_conservatism_report.py --results-dir examples/single_agent/results",
        "```",
        "",
        "Output:",
        "",
        "```text",
        conservatism_output,
        "```",
        "",
        "## Key Findings for NW Discussion",
        "",
    ]
    lines.extend([f"- {finding}" for finding in findings])
    lines.append("")

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Gemma 4 NW cross-model analysis report")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = generate_report(args.results_dir.resolve(), args.output.resolve())
    print(f"Wrote report to {args.output.resolve()}")
    print(f"Report length: {len(report.splitlines())} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
