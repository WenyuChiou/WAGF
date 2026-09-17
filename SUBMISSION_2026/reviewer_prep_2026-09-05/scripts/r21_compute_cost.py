"""R21 -- Compute cost and runtime metrics across experimental arms.

Scans irrigation and flood run directories to extract wall-clock time, decision counts,
LLM calls, reflection log counts, and estimated prompt/response tokens. Produces run-level
and arm-level summary tables for reviewer compute-cost analysis.

Usage:
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r21_compute_cost.py
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402

RUN_SPECS = [
    {
        "arm": "irrigation_strict",
        "pattern": os.path.join(C.REPO, "examples", "irrigation_abm", "results", "strict_42yr_gemma3_4b_faf1bb12_seed*"),
        "audit_name": "irrigation_farmer_governance_audit.csv",
    },
    {
        "arm": "irrigation_ungoverned",
        "pattern": os.path.join(C.REPO, "examples", "irrigation_abm", "results", "ungoverned_42yr_gemma3_4b_faf1bb12_seed*"),
        "audit_name": "irrigation_farmer_governance_audit.csv",
    },
    {
        "arm": "flood_strict",
        "pattern": os.path.join(C.REPO, "examples", "single_agent", "results", "JOH_strict_gemma3_4b_faf1bb12", "Run_*"),
        "audit_name": None,
    },
    {
        "arm": "flood_disabled",
        "pattern": os.path.join(C.REPO, "examples", "single_agent", "results", "JOH_disabled_gemma3_4b_faf1bb12", "Run_*"),
        "audit_name": None,
    },
]

RUN_COLS = [
    "arm",
    "seed",
    "wall_hours",
    "decisions",
    "llm_calls",
    "reflections",
    "est_prompt_tokens",
    "est_response_tokens",
    "prompt_tokens_per_decision",
    "response_tokens_per_decision",
    "seconds_per_decision",
    "jsonl_bad_lines",
]

SUMMARY_METRICS = [
    "wall_hours",
    "decisions",
    "llm_calls",
    "reflections",
    "est_prompt_tokens",
    "est_response_tokens",
    "seconds_per_decision",
]


def compute_run(run_dir: str, arm: str = "", audit_name: str | None = None) -> dict | None:
    if not os.path.isdir(run_dir):
        print(f"  skipped {run_dir}: not a directory")
        return None
    manifest_path = os.path.join(run_dir, "reproducibility_manifest.json")
    if not os.path.isfile(manifest_path):
        print(f"  skipped {run_dir}: missing reproducibility_manifest.json")
        return None

    m = re.search(r"(?:seed|Run_)(\d+)", os.path.basename(run_dir))
    if not m:
        print(f"  skipped {run_dir}: cannot extract seed from directory name")
        return None
    seed = int(m.group(1))

    if audit_name:
        audit_path = os.path.join(run_dir, audit_name)
        if not os.path.isfile(audit_path):
            print(f"  skipped {run_dir}: missing audit CSV")
            return None
    else:
        candidates = sorted(glob.glob(os.path.join(run_dir, "*_governance_audit.csv")))
        if not candidates:
            print(f"  skipped {run_dir}: missing audit CSV")
            return None
        if len(candidates) > 1:
            print(f"  {run_dir}: multiple audit candidates {candidates}; chose {candidates[0]}")
        audit_path = candidates[0]

    df_audit = pd.read_csv(audit_path)
    decisions = len(df_audit)
    if decisions == 0:
        print(f"  skipped {run_dir}: zero decisions")
        return None

    ts = pd.to_datetime(df_audit["timestamp"])
    diff_seconds = (ts.max() - ts.min()).total_seconds()
    wall_hours = round(diff_seconds / 3600.0, 3)

    if "retry_count" in df_audit.columns:
        retries = pd.to_numeric(df_audit["retry_count"], errors="coerce").fillna(0).sum()
    else:
        retries = 0
    llm_calls = int(decisions + retries)

    ref_path = os.path.join(run_dir, "reflection_log.jsonl")
    reflections = 0
    if os.path.isfile(ref_path):
        with open(ref_path, "r", encoding="utf-8") as fh:
            reflections = sum(1 for line in fh if line.strip())

    prompt_tokens = 0
    response_tokens = 0
    raw_dir = os.path.join(run_dir, "raw")
    if not os.path.isdir(raw_dir):
        print(f"  {run_dir}: no raw/ directory — token estimates are 0")
        jsonl_bad_lines = -1
    else:
        jsonl_bad_lines = 0
        raw_files = sorted(glob.glob(os.path.join(raw_dir, "*.jsonl")))
        for rf in raw_files:
            bad_lines = 0
            with open(rf, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        bad_lines += 1
                        continue
                    inp = rec["input"] if "input" in rec and rec["input"] is not None else rec.get("prompt", "")
                    out = rec.get("raw_output", "")
                    prompt_tokens += len(inp or "") // 4
                    response_tokens += len(out or "") // 4
            if bad_lines > 0:
                print(f"  {rf}: {bad_lines} unparseable lines ignored")
            jsonl_bad_lines += bad_lines

    pt_per_dec = round(prompt_tokens / decisions, 1) if decisions else 0.0
    rt_per_dec = round(response_tokens / decisions, 1) if decisions else 0.0
    sec_per_dec = round(wall_hours * 3600.0 / decisions, 1) if decisions else 0.0

    return {
        "arm": arm,
        "seed": seed,
        "wall_hours": wall_hours,
        "decisions": decisions,
        "llm_calls": llm_calls,
        "reflections": reflections,
        "est_prompt_tokens": prompt_tokens,
        "est_response_tokens": response_tokens,
        "prompt_tokens_per_decision": pt_per_dec,
        "response_tokens_per_decision": rt_per_dec,
        "seconds_per_decision": sec_per_dec,
        "jsonl_bad_lines": jsonl_bad_lines,
    }


def scan_and_compute_runs() -> list[dict]:
    runs = []
    for spec in RUN_SPECS:
        arm = spec["arm"]
        pattern = spec["pattern"]
        audit_name = spec["audit_name"]

        matched_dirs = sorted(glob.glob(pattern))
        for run_dir in matched_dirs:
            rec = compute_run(run_dir, arm=arm, audit_name=audit_name)
            if rec is None:
                continue
            runs.append(rec)

    runs.sort(key=lambda r: (r["arm"], r["seed"]))
    return runs


def main() -> int:
    run_data = scan_and_compute_runs()

    # Format run-level rows for CSV output
    csv_run_rows = []
    for r in run_data:
        csv_run_rows.append({
            "arm": r["arm"],
            "seed": r["seed"],
            "wall_hours": f"{r['wall_hours']:.3f}",
            "decisions": r["decisions"],
            "llm_calls": r["llm_calls"],
            "reflections": r["reflections"],
            "est_prompt_tokens": r["est_prompt_tokens"],
            "est_response_tokens": r["est_response_tokens"],
            "prompt_tokens_per_decision": f"{r['prompt_tokens_per_decision']:.1f}",
            "response_tokens_per_decision": f"{r['response_tokens_per_decision']:.1f}",
            "seconds_per_decision": f"{r['seconds_per_decision']:.1f}",
            "jsonl_bad_lines": r["jsonl_bad_lines"],
        })
    C.write_csv("r21_compute_cost.csv", RUN_COLS, csv_run_rows)

    # Compute arm-level summaries
    by_arm: dict[str, list[dict]] = {}
    for r in run_data:
        by_arm.setdefault(r["arm"], []).append(r)

    arm_cols = ["arm", "n_runs"]
    for m in SUMMARY_METRICS:
        arm_cols.extend([f"{m}_mean", f"{m}_sd"])

    arm_rows = []
    for arm, rs in by_arm.items():
        n_runs = len(rs)
        row: dict[str, object] = {
            "arm": arm,
            "n_runs": n_runs,
        }
        for m in SUMMARY_METRICS:
            vals = [r[m] for r in rs]
            mean_val = C.mean(vals)
            sd_val = "" if n_runs < 2 else C.sd(vals)
            row[f"{m}_mean"] = C.fmt(mean_val)
            row[f"{m}_sd"] = C.fmt(sd_val) if n_runs >= 2 else ""
        arm_rows.append(row)

    C.write_csv("r21_compute_cost_by_arm.csv", arm_cols, arm_rows)

    # Print both tables to stdout
    df_runs = pd.DataFrame(csv_run_rows)
    df_arm = pd.DataFrame(arm_rows)

    print()
    C.banner("R21 Compute Cost -- Per Run")
    print(df_runs.to_string(index=False))
    print()
    C.banner("R21 Compute Cost -- By Arm")
    print(df_arm.to_string(index=False))
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
