"""V2 Temporal Validator — Post-Hoc Diagnostic.

Reads household_governance_audit.csv files and computes COUNTERFACTUAL
trigger counts for three temporal validator module types (M1/M2/M3).
These validators are NOT live-enforced; this script only reports what
WOULD have been flagged if V2 validators were active.

Module types (domain-agnostic, flood-instantiated here):

    M1 Appraisal-History Coherence
        flag if: agent had emotion=critical memory within last K=3 years
                 AND current construct_TP_LABEL in {VL, L}

    M2 Behavioral Inertia
        flag runs of N=5 consecutive same `final_skill` years where
        construct_TP_LABEL varied by >= 2 levels across the window

    M3 Evidence-Grounded Irreversibility
        flag year-1 irreversible actions (elevate_house / relocate)
        without prior flood memory evidence

Usage:
    python compute_temporal_diagnostics.py
        --results-root examples/single_agent/results
        --output-md .ai/temporal_diagnostic_report_2026-04-19.md
        [--models gemma3_4b gemma4_26b ...]

Output:
    - one CSV per (model, condition) with per-seed counts
    - one combined markdown report

See also:
    .ai/v2_temporal_validator_diagnostic_plan_2026-04-19.md
    broker/INVARIANTS.md (future Invariant 6 — temporal validators)
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd


_LOW_TP = {"VL", "L"}
_SALIENT_EMOTIONS = {"critical"}
_IRREVERSIBLE_ACTIONS = {"elevate_house", "relocate"}
_TP_ORDER = ["VL", "L", "M", "H", "VH"]
_M1_WINDOW_YEARS = 3
_M2_WINDOW_N = 5
_M2_TP_VOLATILITY_LEVELS = 2


def _read_audit_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    # Normalize expected columns
    df["final_skill"] = df["final_skill"].astype(str).str.strip().str.lower()
    df["construct_TP_LABEL"] = df["construct_TP_LABEL"].astype(str).str.strip().str.upper()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["agent_id"] = df["agent_id"].astype(str)
    if "mem_top_emotion" in df.columns:
        df["mem_top_emotion"] = df["mem_top_emotion"].astype(str).str.strip().str.lower()
    else:
        df["mem_top_emotion"] = ""
    return df.dropna(subset=["year"]).reset_index(drop=True)


def score_m1(df: pd.DataFrame, window_k: int = _M1_WINDOW_YEARS) -> Dict[str, int]:
    """M1 Appraisal-History Coherence — counterfactual trigger count.

    Flag per (agent_id, year) where a critical-emotion memory was retrieved
    within prior K years AND current threat appraisal is VL or L.
    """
    triggers = 0
    eligible_years = 0
    for _, agent_rows in df.groupby("agent_id"):
        agent_rows = agent_rows.sort_values("year").reset_index(drop=True)
        for i, row in agent_rows.iterrows():
            year = int(row["year"])
            window = agent_rows[
                (agent_rows["year"] < year)
                & (agent_rows["year"] >= year - window_k)
            ]
            had_salient = any(
                w in _SALIENT_EMOTIONS
                for w in window["mem_top_emotion"].tolist()
            )
            is_low_tp = row["construct_TP_LABEL"] in _LOW_TP
            if window.empty:
                continue
            eligible_years += 1
            if had_salient and is_low_tp:
                triggers += 1
    return {"m1_triggers": triggers, "m1_eligible": eligible_years,
            "m1_rate": (triggers / eligible_years * 100.0)
                        if eligible_years else 0.0}


def score_m2(df: pd.DataFrame,
             window_n: int = _M2_WINDOW_N,
             min_levels: int = _M2_TP_VOLATILITY_LEVELS) -> Dict[str, int]:
    """M2 Behavioural Inertia — flag runs of N consecutive same-action
    years where TP varied by at least min_levels ordinal steps."""
    triggers = 0
    agents_with_flag: Set[str] = set()
    eligible_windows = 0
    for aid, agent_rows in df.groupby("agent_id"):
        agent_rows = agent_rows.sort_values("year").reset_index(drop=True)
        skills = agent_rows["final_skill"].tolist()
        tps = agent_rows["construct_TP_LABEL"].tolist()
        for i in range(len(skills) - window_n + 1):
            window_skills = skills[i:i + window_n]
            window_tps = tps[i:i + window_n]
            eligible_windows += 1
            if len(set(window_skills)) != 1:
                continue
            tp_numeric = [
                _TP_ORDER.index(t) if t in _TP_ORDER else -1
                for t in window_tps
            ]
            if max(tp_numeric) - min(tp_numeric) >= min_levels:
                triggers += 1
                agents_with_flag.add(aid)
    return {"m2_triggers": triggers,
            "m2_eligible_windows": eligible_windows,
            "m2_agents_flagged": len(agents_with_flag),
            "m2_rate": (triggers / eligible_windows * 100.0)
                        if eligible_windows else 0.0}


def score_m3(df: pd.DataFrame) -> Dict[str, int]:
    """M3 Evidence-Grounded Irreversibility — flag Y=1 irreversible
    actions by agents with no prior critical memory."""
    triggers = 0
    eligible_agents = 0
    for aid, agent_rows in df.groupby("agent_id"):
        year1 = agent_rows[agent_rows["year"] == 1]
        if year1.empty:
            continue
        eligible_agents += 1
        row = year1.iloc[0]
        action = row["final_skill"]
        seen_salient = row["mem_top_emotion"] in _SALIENT_EMOTIONS
        if action in _IRREVERSIBLE_ACTIONS and not seen_salient:
            triggers += 1
    return {"m3_triggers": triggers, "m3_eligible_agents": eligible_agents,
            "m3_rate": (triggers / eligible_agents * 100.0)
                        if eligible_agents else 0.0}


def compute_for_csv(path: Path) -> Dict[str, object]:
    df = _read_audit_csv(path)
    total = len(df)
    n_agents = df["agent_id"].nunique()
    n_years = df["year"].nunique()
    m1 = score_m1(df)
    m2 = score_m2(df)
    m3 = score_m3(df)
    return {
        "total_decisions": total,
        "agents": n_agents,
        "years": int(n_years),
        **m1, **m2, **m3,
    }


def discover_audit_files(
    results_root: Path,
    models: List[str],
    conditions: Dict[str, Tuple[str, str]],
) -> List[Tuple[str, str, str, Path]]:
    """Return list of (model, condition, run_name, csv_path)."""
    found: List[Tuple[str, str, str, Path]] = []
    for model in models:
        for cond_label, (family, group) in conditions.items():
            model_dir = results_root / family / model / group
            if not model_dir.exists():
                continue
            for run_dir in sorted(model_dir.glob("Run_*")):
                csv = run_dir / "household_governance_audit.csv"
                if csv.exists():
                    found.append((model, cond_label, run_dir.name, csv))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path,
                        default=Path("examples/single_agent/results"))
    parser.add_argument("--output-md", type=Path,
                        default=Path(".ai/temporal_diagnostic_report_2026-04-19.md"))
    parser.add_argument("--output-csv", type=Path,
                        default=Path(".ai/temporal_diagnostic_2026-04-19.csv"))
    parser.add_argument("--models", nargs="+", default=[
        "gemma3_4b", "gemma3_12b", "gemma3_27b",
        "ministral3_3b", "ministral3_8b", "ministral3_14b",
        "gemma4_e2b", "gemma4_e4b", "gemma4_26b",
    ])
    parser.add_argument("--conditions", nargs="+", default=["governed", "disabled"])
    args = parser.parse_args()

    condition_map = {
        "governed": ("JOH_FINAL", "Group_C"),
        "disabled": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
    }
    conditions = {k: condition_map[k] for k in args.conditions if k in condition_map}

    rows: List[Dict[str, object]] = []
    for model, cond, run, csv in discover_audit_files(
        args.results_root, args.models, conditions
    ):
        print(f"  [scan] {model} / {cond} / {run}: reading {csv}")
        metrics = compute_for_csv(csv)
        rows.append({
            "model": model,
            "condition": cond,
            "run": run,
            **metrics,
        })

    if not rows:
        print("No audit CSVs found under the given results root.")
        return 1

    df_rows = pd.DataFrame(rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    df_rows.to_csv(args.output_csv, index=False, encoding="utf-8")
    print(f"\n[write] per-run CSV: {args.output_csv}")

    # Aggregate for markdown
    agg = df_rows.groupby(["model", "condition"]).agg(
        runs=("run", "nunique"),
        total_decisions=("total_decisions", "sum"),
        m1_triggers=("m1_triggers", "sum"),
        m1_rate_mean=("m1_rate", "mean"),
        m2_triggers=("m2_triggers", "sum"),
        m2_rate_mean=("m2_rate", "mean"),
        m3_triggers=("m3_triggers", "sum"),
        m3_rate_mean=("m3_rate", "mean"),
    ).reset_index()

    lines: List[str] = []
    lines.append("# V2 Temporal Validator — Post-Hoc Diagnostic Report\n")
    lines.append("**Date**: 2026-04-19  (auto-generated; do not edit by hand)\n")
    lines.append("")
    lines.append(
        "Counterfactual trigger counts for three V2 temporal validator "
        "module types, applied post-hoc to existing audit logs.\n"
    )
    lines.append("## Aggregate per (model, condition)\n")
    lines.append("| Model | Condition | Runs | Total decisions | M1 triggers | M1 rate (%) | M2 triggers | M2 rate (%) | M3 triggers | M3 rate (%) |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in agg.iterrows():
        lines.append(
            f"| {r['model']} | {r['condition']} | {int(r['runs'])} | "
            f"{int(r['total_decisions'])} | "
            f"{int(r['m1_triggers'])} | {r['m1_rate_mean']:.2f} | "
            f"{int(r['m2_triggers'])} | {r['m2_rate_mean']:.2f} | "
            f"{int(r['m3_triggers'])} | {r['m3_rate_mean']:.2f} |"
        )
    lines.append("")
    lines.append("**Definitions**:")
    lines.append("- **M1 (Appraisal-History Coherence)**: agent had critical-emotion memory in prior 3 years AND current TP ∈ {VL, L}.")
    lines.append("- **M2 (Behavioural Inertia)**: 5 consecutive years with same final_skill despite TP variation ≥ 2 ordinal levels.")
    lines.append("- **M3 (Evidence-Grounded Irreversibility)**: Y=1 irreversible action (elevate/relocate) with no prior critical memory.")
    lines.append("")
    lines.append("## Per-run detail\n")
    lines.append("See companion CSV for per-run raw counts.\n")

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[write] markdown report: {args.output_md}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
