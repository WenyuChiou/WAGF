"""R21 -- Compute cost and runtime metrics across experimental arms.

Scans irrigation and flood run directories to extract wall-clock time, decision counts,
LLM calls, reflection log counts, and estimated prompt/response tokens. Produces run-level
and arm-level summary tables for reviewer compute-cost analysis.

Usage:
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r21_compute_cost.py

Token-count column semantics (added 2026-09-19; read this before comparing
any of the four prompt/response token columns to each other):

  - est_prompt_tokens / est_response_tokens: chars/4 heuristic applied to
    the SINGLE prompt recorded per decision in raw/*.jsonl. Verified
    empirically that raw/*.jsonl records exactly one line per DECISION
    (not per LLM call attempt), and that its length matches the audit
    CSV's LAST-attempt prompt_tokens column, not prompt_tokens_total --
    i.e. this estimate reflects the final attempt only, never the sum of
    retries.
  - measured_prompt_tokens_last / measured_response_tokens_last: sum,
    over all decisions in a run, of the audit CSV's per-decision
    prompt_tokens / response_tokens columns (tokenizer-measured, LAST
    attempt only). The COLUMN HEADERS exist in both the faf1bb12
    gemma3:4b corpus and the c3391a53 gemma4:12b corpus, but verified
    empirically across all 20 faf1bb12 runs (all 4 gemma3:4b arms x 5
    seeds) that the per-decision values are 0 for every single row --
    this granular per-decision telemetry was never wired up before
    c3391a53, only the column header was already present. compute_run()
    therefore treats an all-zero column the same as an absent column
    (blank in the CSV, not a fabricated measured-zero); a printed note
    fires per run when this happens. Net effect: measured_prompt_tokens_last
    is blank for all four gemma3:4b arms too, same as the _total columns.
  - measured_prompt_tokens_total / measured_response_tokens_total: sum
    of the audit CSV's prompt_tokens_total / response_tokens_total
    columns (tokenizer-measured, ALL attempts of a decision including
    every governance retry -- exists ONLY at c3391a53).
  - retry_multiplier: measured_prompt_tokens_total / measured_prompt_tokens_last
    for a run -- how much retries alone inflate the true token count
    above the final-attempt-only count. Exists only where both inputs
    exist (c3391a53).

  Two SEPARATE comparisons, do not conflate them (both are c3391a53-only
  in practice, since measured_prompt_tokens_last is blank for gemma3:4b
  per the point above -- there is currently no measured tokenizer
  comparator for the gemma3:4b arms, only the chars/4 estimate):
    est_prompt_tokens        vs measured_prompt_tokens_last   -> isolates
        the TOKENIZER effect (chars/4 heuristic vs the model's real
        tokenizer), both counting the final attempt only.
    measured_prompt_tokens_total vs measured_prompt_tokens_last -> isolates
        RETRY MULTIPLICITY (how many attempts a decision needed), holding
        the tokenizer fixed. (retry_multiplier column is exactly this
        ratio.)
  A prior draft of this analysis compared est_prompt_tokens directly to
  measured_prompt_tokens_total and wrongly attributed the entire gap to
  the tokenizer; most of the irrigation gap is retry multiplicity
  (most irrigation-12b decisions retry at least once), not tokenizer
  divergence.
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
from _common import PrepError  # noqa: E402

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
    # gemma4:12b cross-model arms at c3391a53 (added 2026-09-19). Names of the
    # four arms above are UNCHANGED -- these are four NEW, separate arm rows,
    # not renames.
    {
        "arm": "flood_strict_gemma4_12b",
        "pattern": os.path.join(C.REPO, "examples", "single_agent", "results", "JOH_strict_gemma4_12b_c3391a53", "Run_*"),
        "audit_name": None,
    },
    {
        "arm": "flood_disabled_gemma4_12b",
        "pattern": os.path.join(C.REPO, "examples", "single_agent", "results", "JOH_disabled_gemma4_12b_c3391a53", "Run_*"),
        "audit_name": None,
    },
    {
        "arm": "irrigation_strict_gemma4_12b",
        "pattern": os.path.join(C.REPO, "examples", "irrigation_abm", "results", "strict_42yr_gemma4_12b_c3391a53_seed*"),
        "audit_name": "irrigation_farmer_governance_audit.csv",
    },
    {
        "arm": "irrigation_ungoverned_gemma4_12b",
        "pattern": os.path.join(C.REPO, "examples", "irrigation_abm", "results", "ungoverned_42yr_gemma4_12b_c3391a53_seed*"),
        "audit_name": "irrigation_farmer_governance_audit.csv",
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
    # measured (audit-CSV) telemetry -- only present at c3391a53 (gemma4:12b);
    # blank (not 0) for gemma3:4b arms where the audit CSV lacks these
    # columns. Appended at the end per the 2026-09-19 follow-up so the
    # existing columns above are untouched.
    "measured_prompt_tokens_total",
    "measured_response_tokens_total",
    "measured_latency_ms_mean",
    # 2026-09-19 second follow-up: last-attempt-only measured counts (exist
    # in ALL 8 arms -- prompt_tokens/response_tokens are not c3391a53-only)
    # plus the retry-inflation ratio (c3391a53-only, needs _total). See the
    # module docstring for what each comparison isolates.
    "measured_prompt_tokens_last",
    "measured_response_tokens_last",
    "retry_multiplier",
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

# Measured-telemetry summary metrics, appended at the END of the by-arm
# table (after all SUMMARY_METRICS mean/sd columns) -- present only for
# gemma4:12b (c3391a53) arms; blank for gemma3:4b arms with no such data.
MEASURED_SUMMARY_METRICS = [
    "measured_prompt_tokens_total",
    "measured_response_tokens_total",
    "measured_latency_ms_mean",
    # last-attempt-only measured counts exist for ALL 8 arms (not
    # c3391a53-only); retry_multiplier needs _total, so it stays
    # c3391a53-only. See module docstring.
    "measured_prompt_tokens_last",
    "measured_response_tokens_last",
    "retry_multiplier",
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

    # Measured telemetry from the audit CSV itself -- only present at
    # c3391a53 (gemma4:12b runs write prompt_tokens_total /
    # response_tokens_total / llm_latency_ms; faf1bb12 gemma3:4b runs do
    # not). Left as None (rendered blank, never 0) when the column is
    # absent, so "no data" is never confused with "measured zero".
    if "prompt_tokens_total" in df_audit.columns:
        measured_prompt_tokens_total = int(
            pd.to_numeric(df_audit["prompt_tokens_total"], errors="raise").sum()
        )
    else:
        measured_prompt_tokens_total = None

    if "response_tokens_total" in df_audit.columns:
        measured_response_tokens_total = int(
            pd.to_numeric(df_audit["response_tokens_total"], errors="raise").sum()
        )
    else:
        measured_response_tokens_total = None

    if "llm_latency_ms" in df_audit.columns:
        lat = pd.to_numeric(df_audit["llm_latency_ms"], errors="raise")
        measured_latency_ms_mean = round(float(lat.mean()), 1)
    else:
        measured_latency_ms_mean = None

    # Last-attempt-only measured (tokenizer) token counts. The
    # prompt_tokens/response_tokens COLUMNS exist in both corpora (faf1bb12
    # gemma3:4b and c3391a53 gemma4:12b), but verified empirically across
    # all 20 faf1bb12 runs (all 4 gemma3:4b arms, all 5 seeds each) that
    # the per-decision values are a placeholder 0 for EVERY row -- this
    # granular telemetry was never wired up before c3391a53, only the
    # column header was already present. A column that is 100% zero across
    # an entire run is therefore treated the same as an absent column
    # (blank, not a fabricated measured-zero), with an explicit printed
    # note distinguishing this from "column missing entirely". A run where
    # SOME but not all rows are zero (a real possibility -- a row that
    # never reached the LLM) is not degenerate and is summed normally.
    if "prompt_tokens" in df_audit.columns:
        _pt_last = pd.to_numeric(df_audit["prompt_tokens"], errors="raise")
        if (_pt_last != 0).any():
            measured_prompt_tokens_last = int(_pt_last.sum())
        else:
            print(
                f"  {run_dir}: prompt_tokens column present but 0 for all {decisions} "
                f"decisions -- pre-c3391a53 schema never wired this telemetry up; "
                f"treated as absent (blank), not measured-zero."
            )
            measured_prompt_tokens_last = None
    else:
        measured_prompt_tokens_last = None

    if "response_tokens" in df_audit.columns:
        _rt_last = pd.to_numeric(df_audit["response_tokens"], errors="raise")
        if (_rt_last != 0).any():
            measured_response_tokens_last = int(_rt_last.sum())
        else:
            print(
                f"  {run_dir}: response_tokens column present but 0 for all {decisions} "
                f"decisions -- pre-c3391a53 schema never wired this telemetry up; "
                f"treated as absent (blank), not measured-zero."
            )
            measured_response_tokens_last = None
    else:
        measured_response_tokens_last = None

    # retry_multiplier = total (all attempts) / last (final attempt only).
    # Needs BOTH measured_prompt_tokens_total (c3391a53-only) and
    # measured_prompt_tokens_last (both corpora) -- so this is effectively
    # c3391a53-only too, since the total input is None elsewhere. Blank
    # (never 0 or a divide-by-zero crash) if either input is missing.
    # A zero last-attempt sum across an entire run would mean every
    # decision recorded zero prompt tokens -- that is corrupted data, not
    # a legitimate "no data" case, so it is raised loudly rather than
    # silently rendered blank.
    if measured_prompt_tokens_total is None or measured_prompt_tokens_last is None:
        retry_multiplier = None
    elif measured_prompt_tokens_last == 0:
        raise PrepError(
            f"{run_dir}: measured_prompt_tokens_last is 0 across {decisions} decisions "
            f"but measured_prompt_tokens_total={measured_prompt_tokens_total} -- "
            f"cannot compute retry_multiplier (divide by zero); audit data looks corrupted."
        )
    else:
        retry_multiplier = round(measured_prompt_tokens_total / measured_prompt_tokens_last, 4)

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
        "measured_prompt_tokens_total": measured_prompt_tokens_total,
        "measured_response_tokens_total": measured_response_tokens_total,
        "measured_latency_ms_mean": measured_latency_ms_mean,
        "measured_prompt_tokens_last": measured_prompt_tokens_last,
        "measured_response_tokens_last": measured_response_tokens_last,
        "retry_multiplier": retry_multiplier,
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
            "measured_prompt_tokens_total": (
                "" if r["measured_prompt_tokens_total"] is None else r["measured_prompt_tokens_total"]
            ),
            "measured_response_tokens_total": (
                "" if r["measured_response_tokens_total"] is None else r["measured_response_tokens_total"]
            ),
            "measured_latency_ms_mean": (
                "" if r["measured_latency_ms_mean"] is None else f"{r['measured_latency_ms_mean']:.1f}"
            ),
            "measured_prompt_tokens_last": (
                "" if r["measured_prompt_tokens_last"] is None else r["measured_prompt_tokens_last"]
            ),
            "measured_response_tokens_last": (
                "" if r["measured_response_tokens_last"] is None else r["measured_response_tokens_last"]
            ),
            "retry_multiplier": (
                "" if r["retry_multiplier"] is None else f"{r['retry_multiplier']:.4f}"
            ),
        })
    C.write_csv("r21_compute_cost.csv", RUN_COLS, csv_run_rows)

    # Compute arm-level summaries
    by_arm: dict[str, list[dict]] = {}
    for r in run_data:
        by_arm.setdefault(r["arm"], []).append(r)

    arm_cols = ["arm", "n_runs"]
    for m in SUMMARY_METRICS:
        arm_cols.extend([f"{m}_mean", f"{m}_sd"])
    # measured-telemetry summary columns appended at the END, per the
    # 2026-09-19 follow-up instruction to keep the existing column order.
    for m in MEASURED_SUMMARY_METRICS:
        arm_cols.extend([f"{m}_mean", f"{m}_sd"])

    def _none_safe_mean_sd(raw_vals: list) -> tuple[str, str]:
        """Mean/sd over only the non-None entries of raw_vals.

        Returns ("", "") if every entry is None (arm has no measured data
        at all for this metric -- e.g. all four gemma3:4b arms). Never
        substitutes 0 for a missing value; missing values are simply
        excluded from the mean/sd, not zeroed.
        """
        present = [v for v in raw_vals if v is not None]
        if not present:
            return "", ""
        mean_val = C.fmt(C.mean(present))
        sd_val = C.fmt(C.sd(present)) if len(present) >= 2 else ""
        return mean_val, sd_val

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
        for m in MEASURED_SUMMARY_METRICS:
            raw_vals = [r[m] for r in rs]
            mean_val, sd_val = _none_safe_mean_sd(raw_vals)
            row[f"{m}_mean"] = mean_val
            row[f"{m}_sd"] = sd_val
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

    C.banner("R21 Notes -- token-column comparison (read before citing any gap)")
    print(
        "  est_prompt_tokens        = chars/4 heuristic, LAST attempt only (raw/*.jsonl records\n"
        "                              one line per decision; verified it matches the audit CSV's\n"
        "                              last-attempt prompt_tokens, not prompt_tokens_total).\n"
        "  measured_prompt_tokens_last  = sum of audit CSV prompt_tokens (tokenizer, LAST attempt\n"
        "                              only). Column header exists in both corpora, but verified\n"
        "                              all 20 faf1bb12 (gemma3:4b) runs have this column all-zero\n"
        "                              (never wired up pre-c3391a53) -- so in practice this is\n"
        "                              populated for the 4 gemma4:12b arms only; blank elsewhere.\n"
        "  measured_prompt_tokens_total = sum of audit CSV prompt_tokens_total (tokenizer, ALL\n"
        "                              attempts incl. every governance retry). c3391a53-only.\n"
        "  retry_multiplier          = measured_prompt_tokens_total / measured_prompt_tokens_last.\n"
        "\n"
        "  Compare est_prompt_tokens vs measured_prompt_tokens_last to isolate the TOKENIZER\n"
        "  effect (chars/4 heuristic vs the model's real tokenizer, both last-attempt-only).\n"
        "  Compare measured_prompt_tokens_total vs measured_prompt_tokens_last (i.e. read\n"
        "  retry_multiplier) to isolate RETRY MULTIPLICITY, holding the tokenizer fixed.\n"
        "  Do NOT compare est_prompt_tokens directly to measured_prompt_tokens_total -- that\n"
        "  conflates both effects and overstates the apparent tokenizer gap on irrigation,\n"
        "  where the majority of decisions retry at least once."
    )
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
