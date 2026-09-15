"""R16 -- vintage-of-code prompt/memory length check.

WHY THIS EXISTS
  A reviewer found that a backfilled irrigation run (ministral ungoverned seed44,
  2026-08 real-LLM backfill) has a mean injected-memory length of 340 chars/row,
  against 784-1013 chars/row in its seed42/seed43 arm-mates (both 2026-03). The
  prompt TEMPLATE changed between those two dates -- a code-vintage difference, not
  a config difference, so it is invisible to a `config_snapshot.yaml` diff (r11's
  own config-diff check would not have caught this: it diffs YAML, and the prompt
  renderer is Python). This script asks whether the same thing happened to the
  flood no-validator "live" arm, whose Run_1-3 were backfilled 2026-05-30 (reflection
  re-enabled) while Run_4-5 and the whole governed Group_C arm date from 2026-02, and
  whether today's Sept T0-1b/T0-2b matched top-up (r11) is comparable in prompt input
  to the corpus it is meant to extend.

WHAT COUNTS AS "the memory column"
  Neither `household_governance_audit.csv` nor `irrigation_farmer_governance_audit.csv`
  carries the rendered memory text as its own column (checked: their `mem_*` columns
  are counts/mode/engine-name, e.g. `mem_retrieved_count`, `mem_top_source` -- never
  the text). The rendered memory block DOES appear, verbatim, inside the full prompt
  stored in the raw JSONL's `input` field, introduced by the literal line
  "Your memory includes:" and terminated by the next blank line in both domains (spot
  -checked at 100% match across every vintage read below: Feb/May/Aug backfills and
  the Sept matched top-up). That extracted substring is what this script reports as
  the "memory column" -- named explicitly, per run, in the `memory_col_source` field
  of the output CSV, together with the match rate so a reader can see it was not
  assumed silently.

WHAT THIS DOES NOT DO
  It does not compute IBR/EHE or any governance metric -- purely descriptive prompt-
  and-memory character-length statistics, plus the manifest provenance fields the
  brief asked for (timestamp, git_commit, git_dirty, memory engine, num_ctx).

FLAGGING RULE
  Within each arm (a fixed run grouping defined in ARM_OF below -- e.g. all 5 flood
  no-validator "live" runs are ONE arm, deliberately, so a vintage split inside that
  arm shows up as an outlier rather than being defined away), the median of the
  per-run MEAN is the arm reference. Any run whose mean memory length or mean prompt
  length differs from that reference by more than 30% is flagged in
  `flag_memory_outlier` / `flag_prompt_outlier`.

YEAR-VS-VINTAGE CONTROL
  Memory grows across a run's own years (it accumulates). To keep that from being
  mistaken for a vintage effect, this script ALSO writes a per-year table
  (out/r16_vintage_prompt_check_by_year.csv) with one row per (run, year): the
  headline table's cross-run comparison should be read alongside it, not instead of
  it, whenever runs of different length (flood=10yr, irrigation=42yr) or different
  start dates are compared.

OUTPUT
  out/r16_vintage_prompt_check.csv       one row per run + one row per arm summary
  out/r16_vintage_prompt_check_by_year.csv   one row per (run, year)

Usage: python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r16_vintage_prompt_check.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

FLOOD_ROOT = C.FLOOD_RESULTS                                    # examples/single_agent/results
IRR_ROOT = os.path.join(C.REPO, "examples", "irrigation_abm", "results")

MEMORY_MARKER_RE = re.compile(r"Your memory includes:\s*\n(.*?)\n\n", re.S)
MIN_MATCH_RATE = 0.99   # fail loud if the marker stops matching this often

#: `memory_pre` (the retrieved-memory-object list, upstream of the rendered prompt
#: text) changed its own item SCHEMA between vintages: March ministral runs store
#: plain strings, April+ gemma runs and the August ministral backfill store
#: {"content": ..., "emotion": ..., ...} dicts. Found while chasing the reviewer's
#: 340-vs-784-1013 number: the August ministral-ungoverned-seed44 backfill's
#: "Consolidated Reflection" memory item is truncated to the literal 27-character
#: string "Consolidated Reflection: {" on 3106/3198 rows with memory (97.1%) -- a
#: real reflection-summary write bug, not just a shorter template, and the likely
#: dominant driver of that run's short memory column. A low background rate of the
#: same truncation (11/9590 reflection items, 0.11%) already exists in gemma
#: irrigation runs, so this is a bug that a bad interaction with ministral-3:8b's
#: output turned from rare into near-universal, not something introduced from zero.
REFLECTION_PREFIX = "Consolidated Reflection:"
REFLECTION_TRUNCATED_MAX_LEN = 60

# ---------------------------------------------------------------------------
# Run inventory -- exact paths named in the brief, not a glob. `sub_vintage` records
# the finer-grained split the brief calls out (May backfill vs Feb original inside
# the flood no-validator arm); it is informational, the flag is computed at the
# `arm` level.
# ---------------------------------------------------------------------------
RUNS = []


def _flood(arm, sub_vintage, root, *parts):
    rd = os.path.join(FLOOD_ROOT, root, *parts)
    RUNS.append({
        "domain": "flood", "arm": arm, "sub_vintage": sub_vintage,
        "run_label": f"{root}/{'/'.join(parts)}",
        "run_dir": rd,
        "audit_name": "household_governance_audit.csv",
        "raw_name": "household_traces.jsonl",
    })


def _irr(arm, sub_vintage, dirname):
    rd = os.path.join(IRR_ROOT, dirname)
    RUNS.append({
        "domain": "irrigation", "arm": arm, "sub_vintage": sub_vintage,
        "run_label": dirname, "run_dir": rd,
        "audit_name": "irrigation_farmer_governance_audit.csv",
        "raw_name": "irrigation_farmer_traces.jsonl",
    })


for i in range(1, 6):
    _flood("flood_governed", "feb_2026", "JOH_FINAL", "gemma3_4b", "Group_C", f"Run_{i}")
for i in (1, 2, 3):
    _flood("flood_noval_live", "may_2026_backfill", "JOH_ABLATION_DISABLED",
           "gemma3_4b", "Group_C_disabled", f"Run_{i}")
for i in (4, 5):
    _flood("flood_noval_live", "feb_2026", "JOH_ABLATION_DISABLED",
           "gemma3_4b", "Group_C_disabled", f"Run_{i}")
for i in (1, 2, 3):
    _flood("flood_quarantine_prebackfill", "may_2026_backfill_prequarantine",
           "_QUARANTINE_reflection_missing_2026-05-30", "gemma3_4b", f"Run_{i}")
for r in ("Run_43", "Run_44"):
    _flood("flood_governed_T0-1b_sept_matched", "sept_2026_matched",
           "JOH_T0-1b_strict_gemma3_4b_e0eee08c_matched", r)
for r in ("Run_4202", "Run_4203"):
    _flood("flood_noval_T0-2b_sept_matched", "sept_2026_matched",
           "JOH_T0-2b_disabled_gemma3_4b_e0eee08c_matched", r)

for s in (42, 43, 44, 45, 46):
    _irr("irr_governed", "n/a", f"production_v21_42yr_seed{s}")
for s in (42, 43, 44, 45, 46):
    _irr("irr_ungoverned", "n/a", f"ungoverned_v21_42yr_seed{s}")
for s in (42, 43, 44):
    _irr("irr_ministral_governed", "n/a", f"production_v21_42yr_ministral3_8b_seed{s}")
for s in (42, 43, 44):
    tag = "aug_2026_backfill" if s == 44 else "march_2026"
    _irr("irr_ministral_ungoverned", tag, f"ungoverned_v21_42yr_ministral3_8b_seed{s}")


# ---------------------------------------------------------------------------
def _manifest(rd):
    p = os.path.join(rd, "reproducibility_manifest.json")
    if not os.path.isfile(p):
        raise PrepError(f"missing manifest {p}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _memory_engine(manifest):
    top = manifest.get("memory_engine_class")
    if top:
        return top
    ri = manifest.get("run_integrity") or {}
    nested = ri.get("memory_engine_class")
    return nested if nested else "ABSENT_FROM_MANIFEST"


def _extract_memory(input_text):
    m = MEMORY_MARKER_RE.search(input_text)
    return m.group(1) if m else None


def _reflection_len(item):
    """Length of a 'Consolidated Reflection: ...' memory_pre item, else None.

    Handles both observed memory_pre item schemas: a plain string, or a
    {"content": ..., ...} dict (see REFLECTION_PREFIX note above).
    """
    if isinstance(item, dict):
        text = item.get("content")
    elif isinstance(item, str):
        text = item
    else:
        text = None
    if not isinstance(text, str) or not text.startswith(REFLECTION_PREFIX):
        return None
    return len(text)


#: found while building this table: the raw/*.jsonl trace's own `raw_output` field
#: is HARD-CAPPED at 500 chars + the literal suffix "...[truncated]" (514 chars) in
#: every Feb-May-vintage run checked (flood AND irrigation, gemma AND ministral) --
#: 100% of sampled rows hit the cap. The audit CSV's `raw_output` column, for the
#: SAME rows, carries the untruncated text (verified: JOH_FINAL Run_1 row 1, CSV=775
#: chars vs JSONL=514). The Aug-2026 ministral backfill and the Sept T0-1b/T0-2b
#: top-up do NOT truncate the jsonl copy at all. So a raw_output length read from
#: raw/*.jsonl is confounded with vintage independently of anything about memory or
#: prompts; the audit CSV column is the vintage-stable source and is what this table
#: reports as the headline raw_output number.
TRUNCATION_SUFFIX = "...[truncated]"


def _audit_stats(rd, audit_name):
    p = os.path.join(rd, audit_name)
    if not os.path.isfile(p):
        raise PrepError(f"missing audit csv {p}")
    with open(p, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise PrepError(f"{p}: zero data rows")
    if "raw_output" not in rows[0]:
        raise PrepError(f"{p}: no raw_output column")
    lens = [len(r.get("raw_output") or "") for r in rows]
    return {"n_audit_rows": len(rows), "rawout_csv_mean": _mean(lens),
            "rawout_csv_median": _median(lens)}


def _scan_jsonl(rd, raw_name, run_label):
    p = os.path.join(rd, "raw", raw_name)
    if not os.path.isfile(p):
        raise PrepError(f"missing raw jsonl {p}")
    prompt_lens, memory_lens, rawout_lens = [], [], []
    by_year_mem = {}
    n_total_lines = 0
    n_trace_rows = 0
    n_marker_hits = 0
    example_miss = None
    reflection_lens = []
    n_reflection_dict_items = 0
    n_reflection_str_items = 0
    n_rawout_truncated = 0
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            n_total_lines += 1
            rec = json.loads(line)
            inp = rec.get("input")
            if inp is None:
                inp = rec.get("prompt")
            if inp is None:
                # header/metadata line (e.g. {"_metadata": ..., "agent_type": ...})
                continue
            n_trace_rows += 1
            prompt_lens.append(len(inp))
            rawout = rec.get("raw_output") or ""
            rawout_lens.append(len(rawout))
            if rawout.endswith(TRUNCATION_SUFFIX):
                n_rawout_truncated += 1
            mem_text = _extract_memory(inp)
            if mem_text is not None:
                n_marker_hits += 1
                mlen = len(mem_text)
                memory_lens.append(mlen)
                yr = rec.get("year")
                by_year_mem.setdefault(yr, []).append(mlen)
            elif example_miss is None:
                example_miss = inp[:200]
            for item in (rec.get("memory_pre") or []):
                if isinstance(item, dict):
                    n_reflection_dict_items += 1
                elif isinstance(item, str):
                    n_reflection_str_items += 1
                rlen = _reflection_len(item)
                if rlen is not None:
                    reflection_lens.append(rlen)
    if n_trace_rows == 0:
        raise PrepError(f"{run_label}: zero trace rows with an input/prompt field in {p}")
    match_rate = n_marker_hits / n_trace_rows
    if match_rate < MIN_MATCH_RATE:
        raise PrepError(
            f"{run_label}: 'Your memory includes:' marker matched only "
            f"{match_rate:.1%} of {n_trace_rows} trace rows (need >= "
            f"{MIN_MATCH_RATE:.0%}). Example non-matching input head: {example_miss!r}")
    n_truncated = sum(1 for x in reflection_lens if x <= REFLECTION_TRUNCATED_MAX_LEN)
    if n_reflection_dict_items and n_reflection_str_items:
        schema = "mixed"
    elif n_reflection_dict_items:
        schema = "dict_with_content"
    elif n_reflection_str_items:
        schema = "plain_string"
    else:
        schema = "absent"
    return {
        "n_jsonl_lines": n_total_lines,
        "n_trace_rows": n_trace_rows,
        "memory_match_rate": match_rate,
        "prompt_lens": prompt_lens,
        "memory_lens": memory_lens,
        "rawout_lens": rawout_lens,
        "by_year_mem": by_year_mem,
        "rawout_jsonl_truncated_pct": 100.0 * n_rawout_truncated / n_trace_rows,
        "memory_pre_schema": schema,
        "n_reflection_items": len(reflection_lens),
        "reflection_len_mean": _mean(reflection_lens),
        "reflection_len_median": _median(reflection_lens),
        "pct_reflection_truncated": (100.0 * n_truncated / len(reflection_lens)
                                      if reflection_lens else None),
    }


def _mean(xs):
    return statistics.mean(xs) if xs else None


def _median(xs):
    return statistics.median(xs) if xs else None


def _pct_dev(value, ref):
    if ref in (None, 0):
        return None
    return 100.0 * (value - ref) / ref


def main(argv=None) -> int:
    C.banner("R16  vintage-of-code prompt/memory length check")
    run_rows = []
    year_rows = []
    by_arm = {}

    for spec in RUNS:
        rd = spec["run_dir"]
        label = spec["run_label"]
        if not os.path.isdir(rd):
            raise PrepError(f"missing run dir {rd}")
        manifest = _manifest(rd)
        audit_stats = _audit_stats(rd, spec["audit_name"])
        scan = _scan_jsonl(rd, spec["raw_name"], label)

        years_seen = sorted(y for y in scan["by_year_mem"] if y is not None)
        year_min = years_seen[0] if years_seen else None
        year_max = years_seen[-1] if years_seen else None
        mem_year1 = _mean(scan["by_year_mem"].get(year_min, [])) if year_min is not None else None
        mem_yearlast = _mean(scan["by_year_mem"].get(year_max, [])) if year_max is not None else None

        row = {
            "row_type": "run",
            "domain": spec["domain"], "arm": spec["arm"], "sub_vintage": spec["sub_vintage"],
            "run_label": label,
            "run_dir": os.path.relpath(rd, C.REPO).replace("\\", "/"),
            "n_audit_rows": audit_stats["n_audit_rows"],
            "n_jsonl_lines": scan["n_jsonl_lines"], "n_trace_rows": scan["n_trace_rows"],
            "memory_col_source": "JSONL raw/<traces>.jsonl 'input' field, text after "
                                  "'Your memory includes:' up to the next blank line "
                                  "(no memory column exists in the audit CSV)",
            "memory_match_rate": scan["memory_match_rate"],
            "year_min": year_min, "year_max": year_max,
            "memory_mean": _mean(scan["memory_lens"]), "memory_median": _median(scan["memory_lens"]),
            "prompt_mean": _mean(scan["prompt_lens"]), "prompt_median": _median(scan["prompt_lens"]),
            "rawout_mean": audit_stats["rawout_csv_mean"],
            "rawout_median": audit_stats["rawout_csv_median"],
            "rawout_jsonl_mean": _mean(scan["rawout_lens"]),
            "rawout_jsonl_median": _median(scan["rawout_lens"]),
            "rawout_jsonl_truncated_pct": scan["rawout_jsonl_truncated_pct"],
            "mem_year1_mean": mem_year1, "mem_yearlast_mean": mem_yearlast,
            "memory_pre_schema": scan["memory_pre_schema"],
            "n_reflection_items": scan["n_reflection_items"],
            "reflection_len_mean": scan["reflection_len_mean"],
            "reflection_len_median": scan["reflection_len_median"],
            "pct_reflection_truncated_le60chars": scan["pct_reflection_truncated"],
            "manifest_timestamp": manifest.get("timestamp", "ABSENT_FROM_MANIFEST"),
            "manifest_git_commit": manifest.get("git_commit", "ABSENT_FROM_MANIFEST"),
            "manifest_git_dirty": manifest.get("git_dirty", "ABSENT_FROM_MANIFEST"),
            "manifest_memory_engine": _memory_engine(manifest),
            "manifest_num_ctx": manifest.get("num_ctx", "ABSENT_FROM_MANIFEST"),
            "manifest_model": manifest.get("model", "ABSENT_FROM_MANIFEST"),
        }
        run_rows.append(row)
        by_arm.setdefault(spec["arm"], []).append(row)

        for yr, lens in sorted(scan["by_year_mem"].items(), key=lambda kv: (kv[0] is None, kv[0])):
            year_rows.append({
                "domain": spec["domain"], "arm": spec["arm"], "run_label": label,
                "year": yr, "n_rows": len(lens), "memory_mean": _mean(lens),
                "memory_median": _median(lens),
            })

        pct_trunc = row["pct_reflection_truncated_le60chars"]
        pct_trunc_s = f"{pct_trunc:5.1f}%" if pct_trunc is not None else "   NA"
        print(f"  {label:70s} n={scan['n_trace_rows']:5d}  "
              f"mem_mean={row['memory_mean']:7.1f}  prompt_mean={row['prompt_mean']:8.1f}  "
              f"rawout_mean(csv)={row['rawout_mean']:7.1f}  "
              f"rawout_mean(jsonl)={row['rawout_jsonl_mean']:7.1f} "
              f"[{row['rawout_jsonl_truncated_pct']:5.1f}% capped@514]  "
              f"ts={row['manifest_timestamp']}  git={str(row['manifest_git_commit'])[:12]}  "
              f"engine={row['manifest_memory_engine']}  num_ctx={row['manifest_num_ctx']}  "
              f"reflection_schema={row['memory_pre_schema']}  reflection_truncated={pct_trunc_s}")

    # ---- arm-level medians + flagging ---------------------------------
    for arm, rows in by_arm.items():
        mem_means = [r["memory_mean"] for r in rows]
        prompt_means = [r["prompt_mean"] for r in rows]
        mem_ref = statistics.median(mem_means)
        prompt_ref = statistics.median(prompt_means)
        for r in rows:
            r["arm_median_memory_mean"] = mem_ref
            r["memory_pct_dev_from_arm_median"] = _pct_dev(r["memory_mean"], mem_ref)
            r["flag_memory_outlier"] = abs(r["memory_pct_dev_from_arm_median"]) > 30.0
            r["arm_median_prompt_mean"] = prompt_ref
            r["prompt_pct_dev_from_arm_median"] = _pct_dev(r["prompt_mean"], prompt_ref)
            r["flag_prompt_outlier"] = abs(r["prompt_pct_dev_from_arm_median"]) > 30.0

    print("\n  arm summaries (median of per-run means; spread = max/min of per-run means):")
    arm_summary_rows = []
    for arm, rows in by_arm.items():
        mem_means = sorted(r["memory_mean"] for r in rows)
        prompt_means = sorted(r["prompt_mean"] for r in rows)
        flagged = [r["run_label"] for r in rows if r["flag_memory_outlier"] or r["flag_prompt_outlier"]]
        arm_summary_rows.append({
            "row_type": "arm_summary", "arm": arm, "n_runs": len(rows),
            "memory_mean_min": mem_means[0], "memory_mean_median": statistics.median(mem_means),
            "memory_mean_max": mem_means[-1],
            "memory_spread_ratio_max_over_min": mem_means[-1] / mem_means[0] if mem_means[0] else None,
            "prompt_mean_min": prompt_means[0], "prompt_mean_median": statistics.median(prompt_means),
            "prompt_mean_max": prompt_means[-1],
            "prompt_spread_ratio_max_over_min": prompt_means[-1] / prompt_means[0] if prompt_means[0] else None,
            "flagged_runs": "; ".join(flagged) if flagged else "(none)",
        })
        print(f"    {arm:40s} n={len(rows)}  mem [{mem_means[0]:.1f} .. {mem_means[-1]:.1f}] "
              f"median={statistics.median(mem_means):.1f}  "
              f"prompt [{prompt_means[0]:.1f} .. {prompt_means[-1]:.1f}] "
              f"median={statistics.median(prompt_means):.1f}  "
              f"flagged={flagged if flagged else '(none)'}")

    base_cols = [
        "row_type", "domain", "arm", "sub_vintage", "run_label", "run_dir",
        "n_audit_rows", "n_jsonl_lines", "n_trace_rows", "memory_col_source",
        "memory_match_rate", "year_min", "year_max",
        "memory_mean", "memory_median", "prompt_mean", "prompt_median",
        "rawout_mean", "rawout_median", "rawout_jsonl_mean", "rawout_jsonl_median",
        "rawout_jsonl_truncated_pct", "mem_year1_mean", "mem_yearlast_mean",
        "memory_pre_schema", "n_reflection_items", "reflection_len_mean",
        "reflection_len_median", "pct_reflection_truncated_le60chars",
        "manifest_timestamp", "manifest_git_commit", "manifest_git_dirty",
        "manifest_memory_engine", "manifest_num_ctx", "manifest_model",
        "arm_median_memory_mean", "memory_pct_dev_from_arm_median", "flag_memory_outlier",
        "arm_median_prompt_mean", "prompt_pct_dev_from_arm_median", "flag_prompt_outlier",
    ]
    arm_cols = [
        "row_type", "arm", "n_runs", "memory_mean_min", "memory_mean_median",
        "memory_mean_max", "memory_spread_ratio_max_over_min",
        "prompt_mean_min", "prompt_mean_median", "prompt_mean_max",
        "prompt_spread_ratio_max_over_min", "flagged_runs",
    ]
    all_cols = list(dict.fromkeys(base_cols + arm_cols))
    C.write_csv("r16_vintage_prompt_check.csv", all_cols, run_rows + arm_summary_rows)
    C.write_csv("r16_vintage_prompt_check_by_year.csv",
                ["domain", "arm", "run_label", "year", "n_rows", "memory_mean", "memory_median"],
                year_rows)

    n_flagged = sum(1 for r in run_rows if r["flag_memory_outlier"] or r["flag_prompt_outlier"])
    print(f"\n  {n_flagged}/{len(run_rows)} runs flagged (>30% deviation from arm median, "
          f"memory or prompt).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
