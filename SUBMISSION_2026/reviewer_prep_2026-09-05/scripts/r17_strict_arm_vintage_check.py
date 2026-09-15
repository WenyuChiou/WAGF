"""R17 -- strict irrigation arm (production_v21_42yr_seed{42..46}) vintage + seed-46
outlier check.

WHY THIS EXISTS
  r14's n=5 advise-vs-strict comparison found the strict reference arm's 5 seeds carry
  THREE different git commits (42/43/44) and no recorded commit at all for 45/46 (an
  older, sparser manifest schema), and that strict seed 46 is a wide outlier against
  its own four seed-mates on mead_min / IBR / EHE / approved_first_attempt /
  increase_rate. This script applies r16's method (injected-memory length, prompt
  length, reflection-item counts, by manifest/file vintage) to ONLY the 5 strict
  seeds, plus a seed-vs-seed simulation_log.csv trajectory check (year-by-year mead,
  drought_index, increase_rate) that r16 does not do. It does not touch flood, the
  advise arm, or any other irrigation arm -- see r16 for the cross-domain version.

WHAT THIS DOES NOT DO
  No governance metric computation beyond increase_rate / IBR already defined in
  _loader.py (reused, not reinvented). No code or data is modified anywhere.

OUTPUT
  out/r17_strict_arm_vintage_prompt_check.csv   one row per seed (r16-style columns)
  out/r17_strict_arm_yearly_trajectory.csv      one row per (seed, year): mead, drought
                                                 index, increase_rate

Usage: python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r17_strict_arm_vintage_check.py
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
from _common import L, PrepError  # noqa: E402

SEEDS = (42, 43, 44, 45, 46)
IRR_ROOT = os.path.join(C.REPO, "examples", "irrigation_abm", "results")
AUDIT_NAME = "irrigation_farmer_governance_audit.csv"
RAW_NAME = "irrigation_farmer_traces.jsonl"

MEMORY_MARKER_RE = re.compile(r"Your memory includes:\s*\n(.*?)\n\n", re.S)
MIN_MATCH_RATE = 0.99
REFLECTION_PREFIX = "Consolidated Reflection:"
REFLECTION_TRUNCATED_MAX_LEN = 60
INCREASE = L.INCREASE


def _mean(xs):
    xs = list(xs)
    return statistics.mean(xs) if xs else None


def _median(xs):
    xs = list(xs)
    return statistics.median(xs) if xs else None


def _reflection_len(item):
    if isinstance(item, dict):
        text = item.get("content")
    elif isinstance(item, str):
        text = item
    else:
        text = None
    if not isinstance(text, str) or not text.startswith(REFLECTION_PREFIX):
        return None
    return len(text)


def _extract_memory(input_text):
    m = MEMORY_MARKER_RE.search(input_text)
    return m.group(1) if m else None


def _manifest(rd):
    p = os.path.join(rd, "reproducibility_manifest.json")
    if not os.path.isfile(p):
        raise PrepError(f"missing manifest {p}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _mtimes(rd):
    """File mtimes for every top-level manifest-adjacent file (manifests here carry
    no timestamp for seeds 45/46 -- fall back to filesystem mtime, all clustered
    within ~1s of each other per run, confirming a single write burst)."""
    out = {}
    for name in ("reproducibility_manifest.json", "config_snapshot.yaml",
                 "simulation_log.csv", AUDIT_NAME):
        p = os.path.join(rd, name)
        if os.path.isfile(p):
            out[name] = os.path.getmtime(p)
    return out


def _scan_jsonl(rd, run_label):
    p = os.path.join(rd, "raw", RAW_NAME)
    if not os.path.isfile(p):
        raise PrepError(f"missing raw jsonl {p}")
    prompt_lens, memory_lens = [], []
    by_year_mem = {}
    n_trace_rows = n_marker_hits = 0
    reflection_lens = []
    n_dict_items = n_str_items = 0
    example_miss = None
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            inp = rec.get("input") or rec.get("prompt")
            if inp is None:
                continue
            n_trace_rows += 1
            prompt_lens.append(len(inp))
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
                    n_dict_items += 1
                elif isinstance(item, str):
                    n_str_items += 1
                rlen = _reflection_len(item)
                if rlen is not None:
                    reflection_lens.append(rlen)
    if n_trace_rows == 0:
        raise PrepError(f"{run_label}: zero trace rows with input/prompt in {p}")
    match_rate = n_marker_hits / n_trace_rows
    if match_rate < MIN_MATCH_RATE:
        raise PrepError(
            f"{run_label}: memory marker matched only {match_rate:.1%} of "
            f"{n_trace_rows} rows. Example miss: {example_miss!r}")
    n_truncated = sum(1 for x in reflection_lens if x <= REFLECTION_TRUNCATED_MAX_LEN)
    schema = ("mixed" if (n_dict_items and n_str_items) else
              "dict_with_content" if n_dict_items else
              "plain_string" if n_str_items else "absent")
    years = sorted(y for y in by_year_mem if y is not None)
    return {
        "n_trace_rows": n_trace_rows, "memory_match_rate": match_rate,
        "prompt_lens": prompt_lens, "memory_lens": memory_lens,
        "mem_year1_mean": _mean(by_year_mem.get(years[0], [])) if years else None,
        "mem_yearlast_mean": _mean(by_year_mem.get(years[-1], [])) if years else None,
        "memory_pre_schema": schema, "n_reflection_items": len(reflection_lens),
        "reflection_len_mean": _mean(reflection_lens),
        "pct_reflection_truncated_le60": (
            100.0 * n_truncated / len(reflection_lens) if reflection_lens else None),
    }


def main() -> int:
    C.banner("R17  strict irrigation arm (production_v21_42yr) vintage + seed-46 check")
    run_rows = []
    year_rows = []
    mem_means, prompt_means = [], []

    for s in SEEDS:
        rd = os.path.join(IRR_ROOT, f"production_v21_42yr_seed{s}")
        if not os.path.isdir(rd):
            raise PrepError(f"missing run dir {rd}")
        mf = _manifest(rd)
        mt = _mtimes(rd)
        scan = _scan_jsonl(rd, f"seed{s}")

        sim = L.load_run(rd)
        by_year = {}
        for r in sim:
            by_year.setdefault(int(r["year"]), []).append(r)
        for y in sorted(by_year):
            yr_rows = by_year[y]
            mead_mean = _mean(float(r["lake_mead_level"]) for r in yr_rows)
            di_vals = sorted(set(round(float(r["drought_index"]), 6) for r in yr_rows))
            incr_pct = 100.0 * sum(1 for r in yr_rows if r["yearly_decision"] in INCREASE) / len(yr_rows)
            year_rows.append({
                "seed": s, "year": y, "mead_mean_ft": mead_mean,
                "drought_index_global": di_vals[0] if len(di_vals) == 1 else f"NOT_GLOBAL:{di_vals}",
                "increase_rate_pct": incr_pct,
            })

        row = {
            "seed": s,
            "git_commit": mf.get("git_commit", "ABSENT_FROM_MANIFEST"),
            "manifest_timestamp": mf.get("timestamp", "ABSENT_FROM_MANIFEST"),
            "config_hash": mf.get("config_hash", "ABSENT_FROM_MANIFEST"),
            "model_digest": mf.get("model_digest", "ABSENT_FROM_MANIFEST"),
            "num_ctx": mf.get("num_ctx", "ABSENT_FROM_MANIFEST"),
            "num_predict": mf.get("num_predict", "ABSENT_FROM_MANIFEST"),
            "thinking_mode": mf.get("thinking_mode", "ABSENT_FROM_MANIFEST"),
            "file_mtime_manifest": mt.get("reproducibility_manifest.json"),
            "file_mtime_sim_log": mt.get("simulation_log.csv"),
            "n_trace_rows": scan["n_trace_rows"],
            "memory_match_rate": scan["memory_match_rate"],
            "memory_mean": _mean(scan["memory_lens"]),
            "memory_median": _median(scan["memory_lens"]),
            "prompt_mean": _mean(scan["prompt_lens"]),
            "prompt_median": _median(scan["prompt_lens"]),
            "mem_year1_mean": scan["mem_year1_mean"],
            "mem_yearlast_mean": scan["mem_yearlast_mean"],
            "memory_pre_schema": scan["memory_pre_schema"],
            "n_reflection_items": scan["n_reflection_items"],
            "reflection_len_mean": scan["reflection_len_mean"],
            "pct_reflection_truncated_le60": scan["pct_reflection_truncated_le60"],
        }
        run_rows.append(row)
        mem_means.append(row["memory_mean"])
        prompt_means.append(row["prompt_mean"])

        print(f"  seed {s:3d}  commit={str(row['git_commit'])[:12]:14s}  "
              f"ts={row['manifest_timestamp']}  mem_mean={row['memory_mean']:.1f}  "
              f"prompt_mean={row['prompt_mean']:.1f}  reflection_n={row['n_reflection_items']}  "
              f"reflection_trunc%={row['pct_reflection_truncated_le60']}")

    mem_ref = statistics.median(mem_means)
    prompt_ref = statistics.median(prompt_means)
    print("\n  arm median memory_mean = %.1f, prompt_mean = %.1f" % (mem_ref, prompt_ref))
    for row in run_rows:
        row["memory_pct_dev_from_median"] = 100.0 * (row["memory_mean"] - mem_ref) / mem_ref
        row["prompt_pct_dev_from_median"] = 100.0 * (row["prompt_mean"] - prompt_ref) / prompt_ref
        row["flag_memory_outlier_30pct"] = abs(row["memory_pct_dev_from_median"]) > 30.0
        row["flag_prompt_outlier_30pct"] = abs(row["prompt_pct_dev_from_median"]) > 30.0
        print(f"    seed {row['seed']}: memory {row['memory_pct_dev_from_median']:+.1f}%  "
              f"prompt {row['prompt_pct_dev_from_median']:+.1f}%  "
              f"flagged={row['flag_memory_outlier_30pct'] or row['flag_prompt_outlier_30pct']}")

    cols = ["seed", "git_commit", "manifest_timestamp", "config_hash", "model_digest",
            "num_ctx", "num_predict", "thinking_mode", "file_mtime_manifest",
            "file_mtime_sim_log", "n_trace_rows", "memory_match_rate", "memory_mean",
            "memory_median", "prompt_mean", "prompt_median", "mem_year1_mean",
            "mem_yearlast_mean", "memory_pre_schema", "n_reflection_items",
            "reflection_len_mean", "pct_reflection_truncated_le60",
            "memory_pct_dev_from_median", "prompt_pct_dev_from_median",
            "flag_memory_outlier_30pct", "flag_prompt_outlier_30pct"]
    C.write_csv("r17_strict_arm_vintage_prompt_check.csv", cols, run_rows)
    C.write_csv("r17_strict_arm_yearly_trajectory.csv",
                ["seed", "year", "mead_mean_ft", "drought_index_global", "increase_rate_pct"],
                year_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
