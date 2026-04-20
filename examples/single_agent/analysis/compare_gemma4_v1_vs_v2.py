"""Compare Gemma-4 V1 (priority-schema confound) vs V2 (V1-matching prompt regime).

Post-rerun analysis for the 2026-04-19 priority-schema fix. After the
master rerun bat `run_rerun_gemma4_all_v2.bat` finishes (~48 hours),
run this script to produce a V1 vs V2 comparison report.

Inputs
------
V1 (pre-fix, with [CRITICAL FACTORS] prompt block):
  examples/single_agent/results/JOH_FINAL/gemma4_{e2b,e4b,26b}/Group_C/Run_{1..5}/
  examples/single_agent/results/JOH_ABLATION_DISABLED/gemma4_{e2b,e4b,26b}/Group_C_disabled/Run_{1..5}/

V2 (post-fix, no priority-schema):
  examples/single_agent/results/JOH_FINAL_v2/gemma4_{e2b,e4b,26b}/Group_C/Run_{1..5}/
  examples/single_agent/results/JOH_ABLATION_DISABLED_v2/gemma4_{e2b,e4b,26b}/Group_C_disabled/Run_{1..5}/

Outputs
-------
.ai/v1_vs_v2_gemma4_summary_2026-04-21.md
.ai/v1_vs_v2_gemma4_per_run.csv
.ai/v1_vs_v2_gemma4_action_by_year.csv

Usage
-----
    cd C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework
    python examples/single_agent/analysis/compare_gemma4_v1_vs_v2.py

Safe to rerun. Tolerates missing V2 data (reports which runs are incomplete).
Does NOT modify V1 files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_ROOT = REPO_ROOT / "examples" / "single_agent" / "results"
AI_DIR = REPO_ROOT / ".ai"

MODELS = ["gemma4_e2b", "gemma4_e4b", "gemma4_26b"]
CONDITIONS = {
    "governed": ("Group_C", "JOH_FINAL", "JOH_FINAL_v2"),
    "disabled": ("Group_C_disabled", "JOH_ABLATION_DISABLED", "JOH_ABLATION_DISABLED_v2"),
}
ACTIONS = ["do_nothing", "buy_insurance", "elevate_house", "relocate"]
TP_ORDER = ["VL", "L", "M", "H", "VH"]


def load_audit(csv_path: Path) -> Optional[pd.DataFrame]:
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except Exception as exc:
        print(f"  [warn] failed to read {csv_path}: {exc}")
        return None
    df["final_skill"] = df["final_skill"].astype(str).str.lower().map(
        lambda x: "relocate" if x == "relocated" else x
    )
    df["construct_TP_LABEL"] = df["construct_TP_LABEL"].astype(str).str.upper()
    return df


def compute_ibr(df: pd.DataFrame) -> Dict[str, float]:
    """IBR = (R1 + R3 + R4) / total * 100, R5 excluded per EDT2."""
    if df.empty:
        return {"R1": 0, "R3": 0, "R4": 0, "IBR%": 0.0, "n": 0}
    tp = df["construct_TP_LABEL"]
    act = df["final_skill"]
    high = tp.isin(["H", "VH"])
    low = tp.isin(["VL", "L"])
    r1 = int((high & (act == "do_nothing")).sum())
    r3 = int((low & (act == "relocate")).sum())
    r4 = int((low & (act == "elevate_house")).sum())
    return {
        "R1": r1,
        "R3": r3,
        "R4": r4,
        "IBR%": round(100.0 * (r1 + r3 + r4) / len(df), 3),
        "n": len(df),
    }


def compute_ehe(df: pd.DataFrame, k: int = 4) -> float:
    """Normalized Shannon entropy over 4 actions."""
    if df.empty:
        return 0.0
    act = df["final_skill"].astype(str).str.lower()
    act = act.map(lambda x: x if x in ACTIONS else "do_nothing")
    counts = act.value_counts()
    total = counts.sum()
    if total == 0:
        return 0.0
    probs = counts / total
    probs = probs[probs > 0]
    H = -(probs * np.log2(probs)).sum()
    return round(H / np.log2(k), 4)


def check_prompt_clean(run_dir: Path) -> Optional[bool]:
    """Open first trace and check whether [CRITICAL FACTORS] is absent.
    Returns True if clean (no contamination), False if contaminated,
    None if trace file missing or unreadable."""
    jsonl = run_dir / "raw" / "household_traces.jsonl"
    if not jsonl.exists():
        return None
    try:
        with open(jsonl, encoding="utf-8") as f:
            first = f.readline()
        d = json.loads(first)
        inp = d.get("input", "")
        return "[CRITICAL FACTORS" not in inp
    except Exception:
        return None


def gather_runs(model: str, condition: str, pipeline: str) -> List[Dict[str, any]]:
    """Load 5 runs for (model, condition, pipeline in {V1, V2})."""
    group, v1_family, v2_family = CONDITIONS[condition]
    family = v1_family if pipeline == "V1" else v2_family
    rows: List[Dict[str, any]] = []
    for run_i in range(1, 6):
        run_dir = RESULTS_ROOT / family / model / group / f"Run_{run_i}"
        csv_path = run_dir / "household_governance_audit.csv"
        df = load_audit(csv_path)
        if df is None:
            rows.append({
                "model": model, "condition": condition, "pipeline": pipeline,
                "run": f"Run_{run_i}", "n": 0, "ibr": None, "ehe": None,
                "R1": None, "R3": None, "R4": None,
                "prompt_clean": None, "status": "missing",
            })
            continue
        ibr = compute_ibr(df)
        ehe = compute_ehe(df)
        clean = check_prompt_clean(run_dir)
        rows.append({
            "model": model, "condition": condition, "pipeline": pipeline,
            "run": f"Run_{run_i}",
            "n": ibr["n"], "ibr": ibr["IBR%"], "ehe": ehe,
            "R1": ibr["R1"], "R3": ibr["R3"], "R4": ibr["R4"],
            "prompt_clean": clean, "status": "ok",
        })
    return rows


def action_distribution_by_year(model: str, condition: str, pipeline: str) -> pd.DataFrame:
    """Per-year action % (averaged across 5 seeds)."""
    group, v1_family, v2_family = CONDITIONS[condition]
    family = v1_family if pipeline == "V1" else v2_family
    frames = []
    for run_i in range(1, 6):
        csv_path = RESULTS_ROOT / family / model / group / f"Run_{run_i}" / "household_governance_audit.csv"
        df = load_audit(csv_path)
        if df is not None:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    big = pd.concat(frames, ignore_index=True)
    if "year" not in big.columns:
        return pd.DataFrame()
    rows = []
    for year, y_df in big.groupby("year"):
        if y_df.empty:
            continue
        total = len(y_df)
        row = {"model": model, "condition": condition, "pipeline": pipeline, "year": int(year)}
        for a in ACTIONS:
            row[f"{a}_pct"] = round(100.0 * (y_df["final_skill"] == a).sum() / total, 2)
        rows.append(row)
    return pd.DataFrame(rows)


def paired_t_delta_ibr(v2_governed: List[Optional[float]], v2_disabled: List[Optional[float]]) -> Tuple[Optional[float], Optional[float]]:
    """Paired t on ΔIBR = disabled − governed, matched seeds."""
    pairs = [(g, d) for g, d in zip(v2_governed, v2_disabled) if g is not None and d is not None]
    if len(pairs) < 2:
        return None, None
    diffs = np.array([d - g for g, d in pairs])
    if diffs.std(ddof=1) < 1e-9:
        return float(diffs.mean()), 1.0 if diffs.mean() == 0 else 0.0
    t, p = stats.ttest_1samp(diffs, 0.0)
    return round(float(diffs.mean()), 3), round(float(p), 4)


def main() -> int:
    AI_DIR.mkdir(parents=True, exist_ok=True)
    per_run_rows: List[Dict[str, any]] = []
    action_frames: List[pd.DataFrame] = []

    print("=== Loading V1 + V2 Gemma-4 audit data ===")
    for model in MODELS:
        for condition in CONDITIONS:
            for pipeline in ("V1", "V2"):
                rows = gather_runs(model, condition, pipeline)
                per_run_rows.extend(rows)
                present = [r for r in rows if r["status"] == "ok"]
                print(f"  {pipeline:<3} {model:<12} {condition:<10}: {len(present)}/5 runs found")
                dist = action_distribution_by_year(model, condition, pipeline)
                if not dist.empty:
                    action_frames.append(dist)

    per_run_df = pd.DataFrame(per_run_rows)
    per_run_csv = AI_DIR / "v1_vs_v2_gemma4_per_run.csv"
    per_run_df.to_csv(per_run_csv, index=False, encoding="utf-8")
    print(f"\n[write] {per_run_csv}")

    action_df = pd.concat(action_frames, ignore_index=True) if action_frames else pd.DataFrame()
    action_csv = AI_DIR / "v1_vs_v2_gemma4_action_by_year.csv"
    action_df.to_csv(action_csv, index=False, encoding="utf-8")
    print(f"[write] {action_csv}")

    # Markdown summary
    lines: List[str] = []
    lines.append("# Gemma-4 V1 vs V2 Comparison (priority-schema fix)\n")
    lines.append("**Generated**: `compare_gemma4_v1_vs_v2.py` (auto)\n")
    lines.append(
        "V1 = JOH_FINAL/JOH_ABLATION_DISABLED (pre-fix with `[CRITICAL FACTORS]` "
        "prompt block). V2 = JOH_FINAL_v2/JOH_ABLATION_DISABLED_v2 (post-fix, "
        "no `--use-priority-schema`). Expected: V2 numbers shift relative to V1 "
        "because the artificial attention-prompt is removed, but ΔIBR direction "
        "(governance reduces violations) should be preserved.\n"
    )

    for model in MODELS:
        lines.append(f"\n## {model}\n")
        # Collect per-run IBR/EHE by (pipeline, condition)
        v1g = [r for r in per_run_rows if r["model"] == model and r["pipeline"] == "V1" and r["condition"] == "governed"]
        v1d = [r for r in per_run_rows if r["model"] == model and r["pipeline"] == "V1" and r["condition"] == "disabled"]
        v2g = [r for r in per_run_rows if r["model"] == model and r["pipeline"] == "V2" and r["condition"] == "governed"]
        v2d = [r for r in per_run_rows if r["model"] == model and r["pipeline"] == "V2" and r["condition"] == "disabled"]

        def stats_of(rows):
            vals = [r["ibr"] for r in rows if r["ibr"] is not None]
            ehes = [r["ehe"] for r in rows if r["ehe"] is not None]
            n_runs = len(vals)
            if n_runs == 0:
                return None, None, None, None, 0
            return (
                round(float(np.mean(vals)), 3),
                round(float(np.std(vals, ddof=1)) if n_runs > 1 else 0.0, 3),
                round(float(np.mean(ehes)), 4),
                round(float(np.std(ehes, ddof=1)) if n_runs > 1 else 0.0, 4),
                n_runs,
            )

        v1g_s = stats_of(v1g)
        v1d_s = stats_of(v1d)
        v2g_s = stats_of(v2g)
        v2d_s = stats_of(v2d)

        lines.append("| Pipeline | Condition | Runs | IBR mean ± sd | EHE mean ± sd |")
        lines.append("|---|---|---:|---:|---:|")
        for label, s in [("V1", v1g_s), ("V1", v1d_s), ("V2", v2g_s), ("V2", v2d_s)]:
            cond = "governed" if s is v1g_s or s is v2g_s else "disabled"
            if s[4] == 0:
                lines.append(f"| {label} | {cond} | 0 | (no data) | (no data) |")
            else:
                lines.append(f"| {label} | {cond} | {s[4]} | {s[0]}% ± {s[1]}% | {s[2]} ± {s[3]} |")

        # Paired ΔIBR
        v1_delta = paired_t_delta_ibr(
            [r["ibr"] for r in v1g], [r["ibr"] for r in v1d]
        )
        v2_delta = paired_t_delta_ibr(
            [r["ibr"] for r in v2g], [r["ibr"] for r in v2d]
        )
        lines.append(f"\n**V1 ΔIBR** (disabled − governed): {v1_delta[0]} pp, p={v1_delta[1]}")
        lines.append(f"**V2 ΔIBR** (disabled − governed): {v2_delta[0]} pp, p={v2_delta[1]}\n")

        # Prompt sanity
        v1_clean = [r["prompt_clean"] for r in v1g + v1d if r["prompt_clean"] is not None]
        v2_clean = [r["prompt_clean"] for r in v2g + v2d if r["prompt_clean"] is not None]
        v1_status = (
            "contaminated (contains [CRITICAL FACTORS])"
            if v1_clean and not all(v1_clean)
            else ("clean" if v1_clean and all(v1_clean) else "no data")
        )
        v2_status = (
            "contaminated (contains [CRITICAL FACTORS])"
            if v2_clean and not all(v2_clean)
            else ("clean" if v2_clean and all(v2_clean) else "no data")
        )
        lines.append(f"**Prompt sanity**: V1={v1_status}, V2={v2_status}")

    lines.append("\n## Verdict\n")
    lines.append(
        "Manual interpretation required. Key questions:\n"
        "1. Does V2 ΔIBR for each model preserve the direction and approximate magnitude seen in V1?\n"
        "2. Are V2 IBR absolute values similar across 9-model family (i.e. Gemma-4 V2 no longer inflated relative to Gemma-3 / Ministral)?\n"
        "3. Does V2 prompt-sanity check pass for all rerun runs?\n"
    )

    md_path = AI_DIR / "v1_vs_v2_gemma4_summary_2026-04-21.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[write] {md_path}")

    missing = [r for r in per_run_rows if r["status"] == "missing"]
    if missing:
        print(f"\n[note] {len(missing)} run(s) missing (expected if rerun incomplete):")
        for r in missing[:10]:
            print(f"  - {r['pipeline']} {r['model']} {r['condition']} {r['run']}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
