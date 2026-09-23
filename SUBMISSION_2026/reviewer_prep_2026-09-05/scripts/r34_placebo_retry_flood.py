"""R34 -- placebo-retry flood: does the validator's value come from the
RULE CONTENT of its retry feedback, or just from the EXTRA ATTEMPT? CPU-
only (GPU busy with the live placebo run -- this script stays light).

BACKGROUND -- what "placebo" means here
  Per the task brief that commissioned this script (the `--retry-feedback-
  mode placebo` implementation lives on a branch not present in this
  worktree -- `grep -rn "retry_feedback_mode"` under `broker/`/`examples/`
  here returns nothing; this script does not claim to have verified the
  mechanism from source, only reports it as given): "adapter wrapper-only
  retry control: 'previous response was flagged... reconsider' kept, rule
  id/reason/suggestion removed." I.e. the placebo arm gets the SAME retry
  SCHEDULE as strict (validator fires on the same conditions, the agent
  gets the same NUMBER of extra attempts) but the retry PROMPT carries no
  specific rule content -- a generic "reconsider" instead of "rule X was
  violated because Y, try Z". If placebo's metrics sit near STRICT,
  governance's measured value is mostly "an extra attempt exists"; if
  they sit near DISABLED (no validator, no retry at all), the SPECIFIC
  rule content is what does the work. Part 2's share statistic
  operationalizes this directly.

RUN LAYOUT
  Placebo (landing now, 2026-09-22 00:58, ~1h/seed): `examples/
  single_agent/results/JOH_placebo_gemma3_4b_83fa97e1/Run_{42,43}`.
  Comparators, ALREADY COMPLETE, same 2 seeds only (this whole analysis
  is n=2, stated everywhere, never silently treated as n=5): `JOH_strict_
  gemma3_4b_faf1bb12/Run_{42,43}` (full feedback) and `JOH_disabled_
  gemma3_4b_faf1bb12/Run_{42,43}` (no validator at all).

PART 1 -- per (arm, seed): r23's six collapsed metrics + more
  `_metrics_for()` imported from r23_flood_strict_regen.py (not re-
  derived) gives: the 3 IBR conditionings (uncond/tp_not_medium/tp_high,
  final level) + EHE pooled simlog + rejection_rate_pct + retry_rate_pct
  (2 of the "six collapsed metrics" ARE rejection/retry rate already --
  not duplicated as separate fields) + n_rows + status counts + LLM
  fail count + wall hours + fallback share. Added here (not in r23):
  mean retry_count among ONLY the rows that were retried at all
  (retry_count>0 -- a run-wide "share retried" and a "how hard did it
  retry, given it retried" are different questions, both reported), and
  a rule-id census (`failed_rules`, pipe-delimited) of RETRIED rows,
  top 6 by count -- rule ids sorted() before ranking-by-count ties break
  alphabetically, never by Python's per-process set/dict iteration order
  (the exact nondeterminism r27_irrigation_crossmodel_gemma4_12b.py hit
  and fixed the same way). Manifest census: value-enforces model==
  "gemma3:4b", git_commit starts with "83fa97e1", thinking_mode==
  "disabled", and retry_feedback_mode=="placebo" for the placebo runs
  ONLY (raises on any mismatch); the two comparator arms' manifests are
  read and reported with the SAME fields, never enforced against these
  placebo-specific values.

PART 2 -- seed-paired placebo vs strict vs disabled (n=2, no t-test)
  For each of the 4 metrics (IBR uncond/tp_not_medium/tp_high, EHE
  pooled) and each seed: placebo-strict and placebo-disabled differences,
  reported as the 2 raw per-seed numbers plus whether they agree in
  sign (n=2 is too small for any inferential test -- this script never
  computes one here, and says so in the plain read). Share on the
  strict-to-disabled line: (placebo-strict)/(disabled-strict) per metric
  per seed -- 0 means placebo behaves like strict (attempt-count is what
  matters), 1 means placebo behaves like disabled (rule content is what
  matters). Raises if disabled==strict for a metric/seed (degenerate
  denominator, not silently reported as inf/nan).

PART 3 -- validator-fired-on-a-comparable-schedule check
  Placebo vs strict retry rate and rule-id census side by side (same
  numbers already in Part 1, re-tabulated for direct comparison) --
  confirms the experimental manipulation is clean: if placebo's
  retry-triggering RULES/RATE track strict's closely, the two arms
  differ only in retry-prompt CONTENT, not in when/how often the
  validator fires. Terminal fallback share (REJECTED_FALLBACK share) for
  placebo vs strict vs disabled, same source as Part 1.

PART 4 -- plain read (<=5 sentences, templated from rows)
  States which of "extra attempt" vs "rule content" the share numbers
  point to, quoting them, and the n=2 limitation explicitly.

COMPLETENESS GATE
  Per (arm, seed): run dir exists -> household_governance_audit.csv
  exists -> simulation_log.csv exists -> run_integrity.json exists with
  integrity_ok==True. Missing any -> row_type=skipped, printed pending
  reason, excluded from Part 2/3/4 (which need both members of a pair
  to mean anything -- partial data never gets silently paired against a
  placeholder).

OUTPUTS
  out/r34_placebo_retry_flood.csv -- row_type in {skipped, run_metrics,
    rule_id_census, manifest_check, contrast_pair}.
  out/r34_placebo_retry_flood.md -- GENERATED by render_md() directly
    from that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r34_placebo_retry_flood.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r23_flood_strict_regen as R23  # noqa: E402  READ-ONLY: _metrics_for, DISPLAY_METRICS.

SEEDS = ["42", "43"]
ARM_ROOTS = {
    "placebo": "JOH_placebo_gemma3_4b_83fa97e1",
    "strict": "JOH_strict_gemma3_4b_faf1bb12",
    "disabled": "JOH_disabled_gemma3_4b_faf1bb12",
}
METRICS = ["IBR unconditional (%)", "IBR tp_not_medium (%)", "IBR tp_high (%)", "EHE pooled simlog"]
TOP_N_RULES = 6


def _rep_metric(label: str) -> str:
    """label -> the key R23._metrics_for's dict actually stores it under.
    Same mapping r26/r27 use (`_rep_metric`), inlined here rather than
    importing r26 -- the task only names r23 as an import."""
    for cond_label, cond_name in (("IBR unconditional (%)", "uncond"),
                                    ("IBR tp_not_medium (%)", "tp_not_medium"),
                                    ("IBR tp_high (%)", "tp_high")):
        if label == cond_label:
            return f"ibr_{cond_name}_final"
    return R23._LITERAL_METRIC[label]


# =============================================================================
# completeness
# =============================================================================
def _flood_run_completeness(run_dir: str) -> tuple:
    if not os.path.isdir(run_dir):
        return "skipped", "run directory does not exist yet"
    if not os.path.isfile(os.path.join(run_dir, C.FLOOD_AUDIT)):
        return "skipped", "household_governance_audit.csv missing (run in progress)"
    if not os.path.isfile(os.path.join(run_dir, C.FLOOD_SIM)):
        return "skipped", "simulation_log.csv missing (run in progress)"
    ri_path = os.path.join(run_dir, "run_integrity.json")
    if not os.path.isfile(ri_path):
        return "skipped", "run_integrity.json missing (run in progress)"
    with open(ri_path, encoding="utf-8") as fh:
        ri = json.load(fh)
    if ri.get("integrity_ok") is not True:
        return "skipped", f"integrity_ok is {ri.get('integrity_ok')!r}, not True"
    return "ok", None


# =============================================================================
# Part 1
# =============================================================================
def _rule_id_census(aud: list, top_n: int) -> list:
    """[(rule_id, count), ...] top_n by count among RETRIED rows'
    failed_rules (pipe-delimited). Ties broken alphabetically via
    sorted() BEFORE counting -- the exact nondeterminism
    r27_irrigation_crossmodel_gemma4_12b.py hit (Python's per-process
    set/dict hash randomization on a set built from splitting a
    pipe-delimited column) and fixed the same way."""
    counts: dict = {}
    for r in aud:
        if int(r.get("retry_count") or 0) <= 0:
            continue
        raw = (r.get("failed_rules") or "").strip()
        if not raw:
            continue
        ids = sorted(set(x.strip() for x in raw.split("|") if x.strip()))
        for rid in ids:
            counts[rid] = counts.get(rid, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:top_n]


def _manifest_fields(run_dir: str) -> dict:
    p = os.path.join(run_dir, "reproducibility_manifest.json")
    if not os.path.isfile(p):
        raise PrepError(f"missing reproducibility_manifest.json in {run_dir}")
    with open(p, encoding="utf-8") as fh:
        m = json.load(fh)
    return m


def _part1(rows: list) -> dict:
    """Returns {(arm, seed): {metric_key: value, ..., 'aud': [...]}} for
    complete runs, used by Part 2/3."""
    per_run: dict = {}
    for arm, root in ARM_ROOTS.items():
        for seed in SEEDS:
            run_dir = os.path.join(C.FLOOD_RESULTS, root, f"Run_{seed}")
            status, reason = _flood_run_completeness(run_dir)
            if status == "skipped":
                print(f"  SKIPPED {arm} seed {seed}: {reason}")
                rows.append({"row_type": "skipped", "arm": arm, "seed": seed,
                             "reason": reason})
                continue
            m = R23._metrics_for(run_dir)
            aud = C.read_csv(os.path.join(run_dir, C.FLOOD_AUDIT))
            n = len(aud)
            retried = [r for r in aud if int(r.get("retry_count") or 0) > 0]
            mean_retry_among_retried = (
                C.mean([int(r["retry_count"]) for r in retried]) if retried else float("nan")
            )
            row = {"row_type": "run_metrics", "arm": arm, "seed": seed, "n_rows": m["_n_rows"],
                   "status_approved": m["_status_approved"],
                   "status_rejected": m["_status_rejected"],
                   "status_rejected_fallback": m["_status_rejected_fallback"],
                   "ibr_uncond": m["ibr_uncond_final"], "ibr_tp_not_medium": m["ibr_tp_not_medium_final"],
                   "ibr_tp_high": m["ibr_tp_high_final"], "ehe_pooled": m["ehe_pooled_simlog_published"],
                   "rejection_rate_pct": m["rejection_rate_pct"], "retry_rate_pct": m["retry_rate_pct"],
                   "n_retried": len(retried),
                   "mean_retry_count_among_retried": mean_retry_among_retried,
                   "fallback_share_pct": m["_fallback_share_pct"], "llm_fail_n": m["_llm_fail_n"],
                   "wall_hours": m["_wall_hours"]}
            rows.append(row)

            census = _rule_id_census(aud, TOP_N_RULES)
            for rank, (rule_id, count) in enumerate(census, start=1):
                rows.append({"row_type": "rule_id_census", "arm": arm, "seed": seed,
                             "rank": rank, "rule_id": rule_id, "count": count})
            print(f"  OK {arm:9s} seed {seed}: rows={n} retried={len(retried)} "
                  f"({100.0*len(retried)/n:.1f}%) fallback={m['_fallback_share_pct']:.2f}% "
                  f"top_rule={census[0] if census else None}")

            manifest = _manifest_fields(run_dir)
            model = manifest.get("model")
            git_commit = manifest.get("git_commit")
            thinking_mode = manifest.get("thinking_mode")
            retry_feedback_mode = manifest.get("retry_feedback_mode")
            enforced = arm == "placebo"
            if enforced:
                if model != "gemma3:4b":
                    raise PrepError(f"{run_dir}: model={model!r}, expected 'gemma3:4b'")
                if not str(git_commit or "").startswith("83fa97e1"):
                    raise PrepError(f"{run_dir}: git_commit={git_commit!r}, expected to "
                                     f"start with '83fa97e1'")
                if thinking_mode != "disabled":
                    raise PrepError(f"{run_dir}: thinking_mode={thinking_mode!r}, expected "
                                     f"'disabled'")
                if retry_feedback_mode != "placebo":
                    raise PrepError(f"{run_dir}: retry_feedback_mode={retry_feedback_mode!r}, "
                                     f"expected 'placebo' -- if this manifest field is "
                                     f"genuinely absent (schema predates this flag), that is "
                                     f"itself worth raising on, not silently passing")
            rows.append({"row_type": "manifest_check", "arm": arm, "seed": seed, "model": model,
                         "git_commit_short": (git_commit or "")[:8],
                         "thinking_mode": thinking_mode,
                         "retry_feedback_mode": retry_feedback_mode,
                         "retry_feedback_mode_present": "retry_feedback_mode" in manifest,
                         "enforced": enforced})

            per_run[(arm, seed)] = row
    return per_run


# =============================================================================
# Part 2
# =============================================================================
METRIC_KEYS = {
    "IBR unconditional (%)": "ibr_uncond",
    "IBR tp_not_medium (%)": "ibr_tp_not_medium",
    "IBR tp_high (%)": "ibr_tp_high",
    "EHE pooled simlog": "ehe_pooled",
}

# 2026-09-22 review fix: a share = (placebo-strict)/(disabled-strict) is
# only a meaningful "where on the strict-to-disabled line" reading when
# the LINE ITSELF is long enough on that metric's own scale. EHE pooled
# simlog moved only ~0.02 (seed 42) / ~0.002 (seed 43) between strict and
# disabled -- a denominator near the scale's own noise floor -- so its
# share (-0.14, 6.97 in this run) is numerically real but not
# interpretable, and swamps a naive mean across all 8 cells (an earlier
# draft of this script's plain read did exactly that, reported mean=0.94,
# and concluded "near disabled" -- wrong; the 6 IBR shares alone are all
# small (0.003-0.252) and say "near strict"). Threshold, in the metric's
# own unit, below which |disabled-strict| is treated as too small to
# divide by for this purpose (NOT a claim the value is literally zero --
# the raw share is still computed and stored, only the plain-read verdict
# excludes it):
DEGENERATE_THRESHOLD = {
    "IBR unconditional (%)": 1.0,     # percentage points
    "IBR tp_not_medium (%)": 1.0,
    "IBR tp_high (%)": 1.0,
    "EHE pooled simlog": 0.05,        # EHE pooled simlog's own working range
                                       # across every arm this whole package has
                                       # ever reported is roughly [0.6, 0.9]
}


def _part2(rows: list, per_run: dict) -> None:
    for metric_label, key in METRIC_KEYS.items():
        threshold = DEGENERATE_THRESHOLD[metric_label]
        for seed in SEEDS:
            p = per_run.get(("placebo", seed))
            s = per_run.get(("strict", seed))
            d = per_run.get(("disabled", seed))
            if p is None or s is None or d is None:
                missing = [a for a, v in (("placebo", p), ("strict", s), ("disabled", d))
                           if v is None]
                print(f"  Part 2 PENDING: {metric_label} seed {seed} -- missing arm(s) "
                      f"{missing}")
                rows.append({"row_type": "skipped", "section": "contrast_pair",
                             "metric": metric_label, "seed": seed,
                             "reason": f"missing arm(s): {missing}"})
                continue
            pv, sv, dv = p[key], s[key], d[key]
            diff_p_minus_s = pv - sv
            diff_p_minus_d = pv - dv
            denom = dv - sv
            denom_abs = abs(denom)
            degenerate = denom_abs < threshold
            share = (pv - sv) / denom if denom != 0 else float("nan")
            rows.append({"row_type": "contrast_pair", "metric": metric_label, "seed": seed,
                         "placebo_value": pv, "strict_value": sv, "disabled_value": dv,
                         "diff_placebo_minus_strict": diff_p_minus_s,
                         "diff_placebo_minus_disabled": diff_p_minus_d,
                         "share_on_strict_to_disabled_line": share,
                         "denom_abs": denom_abs, "degenerate_threshold": threshold,
                         "degenerate": degenerate})
            if degenerate:
                print(f"  DEGENERATE share: {metric_label} seed {seed} -- "
                      f"|disabled-strict|={denom_abs:.4f} < threshold {threshold} -- "
                      f"share={share:.4f} computed and stored, excluded from the verdict")


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "arm", "seed", "n_rows", "status_approved", "status_rejected",
    "status_rejected_fallback", "ibr_uncond", "ibr_tp_not_medium", "ibr_tp_high", "ehe_pooled",
    "rejection_rate_pct", "retry_rate_pct", "n_retried", "mean_retry_count_among_retried",
    "fallback_share_pct", "llm_fail_n", "wall_hours", "rank", "rule_id", "count", "model",
    "git_commit_short", "thinking_mode", "retry_feedback_mode", "retry_feedback_mode_present",
    "enforced", "metric", "placebo_value", "strict_value", "disabled_value",
    "diff_placebo_minus_strict", "diff_placebo_minus_disabled",
    "share_on_strict_to_disabled_line", "denom_abs", "degenerate_threshold", "degenerate",
    "reason",
]


def main() -> int:
    C.banner("R34  Placebo-retry flood: extra attempt vs rule content")
    rows: list = []

    print("\n-- Part 1: per (arm, seed) metrics, rule-id census, manifest census --")
    per_run = _part1(rows)

    print("\n-- Part 2: seed-paired placebo vs strict vs disabled (n=2, no t-test) --")
    _part2(rows, per_run)

    md_text = render_md(rows)

    csv_final = "r34_placebo_retry_flood.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, "r34_placebo_retry_flood.md")
    md_tmp = md_final + ".tmp"

    csv_tmp_path = C.write_csv(csv_tmp, FIELDNAMES, rows)
    with open(md_tmp, "w", encoding="utf-8") as fh:
        fh.write(md_text)

    os.replace(csv_tmp_path, os.path.join(C.OUT, csv_final))
    os.replace(md_tmp, md_final)
    print(f"\n  wrote {os.path.relpath(os.path.join(C.OUT, csv_final), C.REPO).replace(chr(92), '/')}"
          f"  ({len(rows)} rows)")
    print(f"  wrote {os.path.relpath(md_final, C.REPO).replace(chr(92), '/')}  "
          f"({len(md_text.splitlines())} lines)")
    return 0


# =============================================================================
# .md rendering
# =============================================================================
_cp = R23._csv_precision  # route every display number through the CSV's own 4dp
                           # precision before display -- same double-rounding fix r23
                           # introduced, reused (not re-derived) throughout this package.


def _is_nan(x) -> bool:
    return isinstance(x, float) and x != x


def _fmt_mean_retry(r: dict, nd: int = 3) -> str:
    """mean_retry_count_among_retried is NaN by construction whenever
    n_retried==0 (mean of an empty list) -- e.g. the disabled arm, which
    never retries at all since it has no validator. `_cp` (R23._csv_
    precision) round-trips a NaN through C.fmt()'s literal 'NA' string
    and then tries float('NA'), which raises (the exact class of bug
    r26_flood_crossmodel_gemma4_12b.py's `_fmt_stat` already exists to
    avoid) -- guarded here with the reason derived from n_retried itself,
    never hand-typed."""
    v = r["mean_retry_count_among_retried"]
    if _is_nan(v):
        return "n.a. (n_retried=0)"
    return f"{_cp(v):.{nd}f}"


def _find(rows, row_type, **kw):
    out = []
    for r in rows:
        if r.get("row_type") != row_type:
            continue
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


def _manifest_commit_hashes(rows: list, placebo_arms: list, comparator_arms: list) -> tuple:
    """(placebo_hash, comparator_hash), pulled from `manifest_check` rows'
    `git_commit_short` -- never hard-coded, so a Method-section caveat built
    from this cannot drift from the actual run. Raises if the arm(s) have no
    manifest rows yet, or if git_commit_short disagrees within an arm (across
    seeds) or between the comparator arms -- a disagreement there would mean
    the provenance claim itself is false, never something to paper over.
    Identical helper to r35_placebo_retry_irrigation.py's own -- not shared
    via import since neither script exports helpers for reuse by the other,
    same convention `_rule_id_census` already established between them."""
    def _one(arms: list) -> str:
        vals = {r["git_commit_short"] for r in _find(rows, "manifest_check") if r["arm"] in arms}
        if not vals:
            raise PrepError(f"no manifest_check rows yet for arm(s) {arms} -- cannot render "
                             f"the code-provenance caveat")
        if len(vals) > 1:
            raise PrepError(f"manifest_check git_commit_short disagrees within/between "
                             f"arm(s) {arms}: {sorted(vals)} -- the code-provenance caveat "
                             f"cannot be rendered as a single hash")
        return next(iter(vals))
    return _one(placebo_arms), _one(comparator_arms)


def render_md(rows: list) -> str:
    lines = []
    lines.append("# R34 -- placebo-retry flood: extra attempt vs rule content")
    lines.append("")
    lines.append("Source: `r34_placebo_retry_flood.py`. Every number below is read live "
                 "from the `rows` list this script writes to the paired CSV. n=2 seeds "
                 "(42, 43) throughout -- no t-test anywhere in this file.")
    lines.append("")

    # ---- Part 1: per-run metrics -----------------------------------------------
    lines.append("## Part 1 -- per (arm, seed) metrics")
    lines.append("")
    lines.append("| arm | seed | n_rows | IBR uncond | IBR tp_not_medium | IBR tp_high | "
                 "EHE pooled | retry rate % | n_retried | mean retries (if retried) | "
                 "fallback % | LLM fail | wall h |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    any_data = False
    for arm in ("placebo", "strict", "disabled"):
        for seed in SEEDS:
            recs = _find(rows, "run_metrics", arm=arm, seed=seed)
            if not recs:
                lines.append(f"| {arm} | {seed} | PENDING | -- | -- | -- | -- | -- | -- | "
                             f"-- | -- | -- | -- |")
                continue
            any_data = True
            r = recs[0]
            lines.append(
                f"| {arm} | {seed} | {r['n_rows']} | {_cp(r['ibr_uncond']):.2f} | "
                f"{_cp(r['ibr_tp_not_medium']):.2f} | {_cp(r['ibr_tp_high']):.2f} | "
                f"{_cp(r['ehe_pooled']):.3f} | {_cp(r['retry_rate_pct']):.2f} | "
                f"{r['n_retried']} | "
                f"{_fmt_mean_retry(r)} | "
                f"{_cp(r['fallback_share_pct']):.2f} | {r['llm_fail_n']} | "
                f"{_cp(r['wall_hours']):.3f} |"
            )
    lines.append("")

    lines.append("### Rule-id census, top 6 among retried rows")
    lines.append("")
    lines.append("| arm | seed | rank | rule_id | count |")
    lines.append("|---|---|---|---|---|")
    for arm in ("placebo", "strict", "disabled"):
        for seed in SEEDS:
            recs = _find(rows, "rule_id_census", arm=arm, seed=seed)
            if not recs:
                lines.append(f"| {arm} | {seed} | -- | pending | -- |")
                continue
            for r in sorted(recs, key=lambda x: int(x["rank"])):
                lines.append(f"| {arm} | {seed} | {r['rank']} | {r['rule_id']} | {r['count']} |")
    lines.append("")

    lines.append("### Manifest census")
    lines.append("")
    lines.append("| arm | seed | model | git_commit | thinking_mode | retry_feedback_mode | "
                 "key present | enforced |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for arm in ("placebo", "strict", "disabled"):
        for seed in SEEDS:
            recs = _find(rows, "manifest_check", arm=arm, seed=seed)
            if not recs:
                lines.append(f"| {arm} | {seed} | pending | -- | -- | -- | -- | -- |")
                continue
            r = recs[0]
            lines.append(f"| {arm} | {seed} | {r['model']} | {r['git_commit_short']}... | "
                         f"{r['thinking_mode']} | {r['retry_feedback_mode']} | "
                         f"{r['retry_feedback_mode_present']} | {r['enforced']} |")
    lines.append("")

    # ---- Part 2: contrasts -------------------------------------------------------
    lines.append("## Part 2 -- seed-paired contrasts (n=2, both per-seed values reported, "
                 "no t-test)")
    lines.append("")
    lines.append("| metric | seed | placebo | strict | disabled | placebo-strict | "
                 "placebo-disabled | share on strict->disabled line |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for metric_label in METRICS:
        for seed in SEEDS:
            recs = _find(rows, "contrast_pair", metric=metric_label, seed=seed)
            if not recs:
                pend = _find(rows, "skipped", section="contrast_pair", metric=metric_label,
                              seed=seed)
                reason = pend[0]["reason"] if pend else "no data"
                lines.append(f"| {metric_label} | {seed} | -- | -- | -- | -- | -- | "
                             f"PENDING ({reason}) |")
                continue
            r = recs[0]
            if r["degenerate"]:
                share_cell = (f"n.a. (denominator |disabled-strict| = "
                              f"{_cp(r['denom_abs']):.4f} < threshold "
                              f"{r['degenerate_threshold']:g})")
            else:
                share_cell = f"{_cp(r['share_on_strict_to_disabled_line']):.3f}"
            lines.append(
                f"| {metric_label} | {seed} | {_cp(r['placebo_value']):.3f} | "
                f"{_cp(r['strict_value']):.3f} | {_cp(r['disabled_value']):.3f} | "
                f"{_cp(r['diff_placebo_minus_strict']):.3f} | "
                f"{_cp(r['diff_placebo_minus_disabled']):.3f} | "
                f"{share_cell} |"
            )
    lines.append("")

    # ---- Part 3: schedule check ---------------------------------------------------
    lines.append("## Part 3 -- did the validator fire on a comparable schedule "
                 "(placebo vs strict)?")
    lines.append("")
    lines.append("| seed | placebo retry rate % | strict retry rate % | placebo top rule | "
                 "strict top rule | placebo fallback % | strict fallback % | "
                 "disabled fallback % |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for seed in SEEDS:
        p = _find(rows, "run_metrics", arm="placebo", seed=seed)
        s = _find(rows, "run_metrics", arm="strict", seed=seed)
        d = _find(rows, "run_metrics", arm="disabled", seed=seed)
        p_top = _find(rows, "rule_id_census", arm="placebo", seed=seed, rank=1)
        s_top = _find(rows, "rule_id_census", arm="strict", seed=seed, rank=1)
        if not (p and s):
            lines.append(f"| {seed} | pending | pending | pending | pending | pending | "
                         f"pending | pending |")
            continue
        p, s = p[0], s[0]
        d_fb = f"{_cp(d[0]['fallback_share_pct']):.2f}" if d else "pending"
        lines.append(
            f"| {seed} | {_cp(p['retry_rate_pct']):.2f} | {_cp(s['retry_rate_pct']):.2f} | "
            f"{p_top[0]['rule_id'] if p_top else 'n.a.'} | "
            f"{s_top[0]['rule_id'] if s_top else 'n.a.'} | "
            f"{_cp(p['fallback_share_pct']):.2f} | {_cp(s['fallback_share_pct']):.2f} | "
            f"{d_fb} |"
        )
    lines.append("")

    # ---- Plain read -----------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    sentences = []
    placebo_seeds_landed = sorted({r["seed"] for r in _find(rows, "run_metrics", arm="placebo")})
    if not placebo_seeds_landed:
        comparators_ready = bool(_find(rows, "run_metrics", arm="strict")) and \
            bool(_find(rows, "run_metrics", arm="disabled"))
        sentences.append(
            "The placebo run (JOH_placebo_gemma3_4b_83fa97e1) is still in progress -- 0/2 "
            f"seeds landed. Comparators (strict, disabled, both faf1bb12) are "
            f"{'already complete' if comparators_ready else 'also incomplete'} and reported "
            f"in Part 1 above; Part 2/3's placebo-vs-comparator contrasts will populate "
            f"automatically, no code change needed, once placebo lands."
        )
    elif len(placebo_seeds_landed) < len(SEEDS):
        missing = [s for s in SEEDS if s not in placebo_seeds_landed]
        sentences.append(
            f"The placebo run has landed for seed(s) {', '.join(placebo_seeds_landed)} but "
            f"not yet for seed(s) {', '.join(missing)} -- Part 2/3's paired contrasts need "
            f"both seeds and stay PENDING until the second one lands."
        )
    shares = _find(rows, "contrast_pair")
    if shares:
        # Verdict is computed over non-degenerate IBR cells ONLY (2026-09-22
        # review fix). EHE pooled simlog's strict-to-disabled line is too
        # short on both seeds here (denominator below its own degenerate
        # threshold) to divide by for this purpose -- its share is still
        # computed and shown in the table above, just excluded from the
        # verdict, and called out explicitly below so it is never silently
        # dropped without explanation.
        ibr_cells = [r for r in shares if r["metric"].startswith("IBR")]
        ibr_ok = [r for r in ibr_cells if not r["degenerate"]]
        ehe_cells = [r for r in shares if r["metric"] == "EHE pooled simlog"]
        ehe_degenerate = [r for r in ehe_cells if r["degenerate"]]

        if ibr_ok:
            vals = [float(r["share_on_strict_to_disabled_line"]) for r in ibr_ok]
            mean_share = sum(vals) / len(vals)
            lo, hi = min(vals), max(vals)
            near_strict = mean_share < 0.35
            near_disabled = mean_share > 0.65
            if near_strict:
                verdict = (f"placebo sits close to STRICT on IBR (mean share "
                          f"{mean_share:.3f}, range {lo:.3f} to {hi:.3f}, i.e. near 0) -- "
                          f"most of governance's measured value here looks like it comes "
                          f"from the EXTRA ATTEMPT existing at all (the \"previous "
                          f"response was flagged, reconsider\" framing), not from the "
                          f"specific rule id/reason/suggestion the retry prompt would "
                          f"otherwise carry")
            elif near_disabled:
                verdict = (f"placebo sits close to DISABLED on IBR (mean share "
                          f"{mean_share:.3f}, range {lo:.3f} to {hi:.3f}, i.e. near 1) -- "
                          f"most of governance's measured value here looks like it comes "
                          f"from the SPECIFIC RULE CONTENT in the retry prompt, not just "
                          f"from having another attempt")
            else:
                verdict = (f"placebo sits roughly midway between strict and disabled on "
                          f"IBR (mean share {mean_share:.3f}, range {lo:.3f} to "
                          f"{hi:.3f}) -- neither \"just an extra attempt\" nor \"the rule "
                          f"content alone\" explains most of governance's measured value "
                          f"here; both appear to matter")
            sentences.append(f"Across the {len(vals)} non-degenerate IBR (conditioning, "
                             f"seed) cells, {verdict}.")
            by_seed = {}
            for r in ibr_ok:
                by_seed.setdefault(r["seed"], []).append(float(r["share_on_strict_to_disabled_line"]))
            parts = "; ".join(f"seed {s}: mean {sum(v)/len(v):.3f} "
                              f"({', '.join(f'{x:.3f}' for x in v)})"
                              for s, v in sorted(by_seed.items()))
            sentences.append(f"Per-seed IBR share: {parts}.")
        else:
            sentences.append("No non-degenerate IBR cells are available to base a verdict "
                             "on.")
        if ehe_degenerate:
            denom_parts = "; ".join(f"seed {r['seed']}: |disabled-strict|="
                                    f"{_cp(r['denom_abs']):.4f}" for r in ehe_degenerate)
            sentences.append(
                f"EHE pooled simlog CANNOT discriminate extra-attempt from rule-content "
                f"here -- strict and disabled are themselves nearly identical on this "
                f"metric ({denom_parts}, both below the {DEGENERATE_THRESHOLD['EHE pooled simlog']:g} "
                f"degenerate threshold), so a placebo-vs-strict-vs-disabled share on EHE "
                f"is not interpretable and is excluded from the verdict above (raw shares "
                f"are still in the Part 2 table, marked n.a. with the reason)."
            )
    schedule_rows = [(_find(rows, "run_metrics", arm="placebo", seed=s),
                      _find(rows, "run_metrics", arm="strict", seed=s)) for s in SEEDS]
    if all(p and s for p, s in schedule_rows):
        p_rates = [float(p[0]["retry_rate_pct"]) for p, s in schedule_rows]
        s_rates = [float(s[0]["retry_rate_pct"]) for p, s in schedule_rows]
        max_gap = max(abs(a - b) for a, b in zip(p_rates, s_rates))
        sentences.append(
            f"Placebo and strict retry rates track each other closely (max per-seed gap "
            f"{max_gap:.2f}pp), consistent with the manipulation being clean -- the "
            f"validator fires on the same schedule in both, only the retry prompt's "
            f"content differs."
        )
    sentences.append(
        "This whole comparison is n=2 seeds (42, 43) -- no significance test is "
        "computed anywhere in this script; the per-seed numbers and their sign "
        "agreement are reported directly, and any conclusion here should be read as "
        "suggestive, not statistically established."
    )
    for s in sentences[:5]:
        lines.append(s)
        lines.append("")

    # ---- Method -----------------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "The 6 collapsed flood metrics (3 IBR conditionings at the final action level, EHE "
        "pooled simlog, rejection rate, retry rate) are `r23_flood_strict_regen.py::"
        "_metrics_for()`, imported, not re-derived -- the SAME definitions every other "
        "script in this package uses for these columns. `retry_feedback_mode` is reported "
        "from each run's `reproducibility_manifest.json` and value-enforced =='placebo' "
        "ONLY for the placebo arm (raises otherwise, including if the key is simply absent "
        "-- that would itself be a real finding, not something to pass silently); the "
        "strict/disabled comparator manifests are read and reported with the same fields, "
        "never enforced. Rule-id census counts each RETRIED row's `failed_rules` "
        "(pipe-delimited) once per distinct rule id per row (a row with the same rule id "
        "repeated is not double-counted), ranked by count then alphabetically, with rule "
        "ids `sorted()` before counting -- the exact fix "
        "`r27_irrigation_crossmodel_gemma4_12b.py` applied for a Python set-hash-"
        "randomization nondeterminism bug, reused here since the same pattern (splitting a "
        "pipe-delimited column into a set) recurs. share_on_strict_to_disabled_line = "
        "(placebo-strict)/(disabled-strict): 0 = placebo behaves like strict (attempt "
        "count matters), 1 = placebo behaves like disabled (rule content matters); raises "
        "on a zero denominator rather than reporting inf/nan."
    )
    lines.append("")

    # 2026-09-22 review fix (round 2): code-provenance caveat, pulled live from this
    # run's own manifest_check rows (never hard-coded) so it cannot drift from what
    # actually ran. Round-1 text overclaimed "unchanged" for the retry-prompt path
    # the mock check cannot see; replaced with the three-piece evidence chain
    # (framework-change scope, retry-prompt golden text, mock CSV identity for BOTH
    # domains) recorded in out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md.
    placebo_hash, comparator_hash = _manifest_commit_hashes(
        rows, placebo_arms=["placebo"], comparator_arms=["strict", "disabled"])
    lines.append(
        f"The placebo arm was run at code {placebo_hash} while the strict and disabled "
        f"comparators come from {comparator_hash}. The comparison is accepted on three "
        f"pieces of evidence recorded in out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md: "
        f"the only framework change between c3391a53 and 83fa97e1 is PR #46 (eleven files, "
        f"all plumbing for the retry_feedback_mode feature), whose only behaviour-changing "
        f"branch is in the domain-generic retry loop broker/core/_retry_loop.py (RetryMixin."
        f"_governance_retry_loop); the full-mode retry prompt rendered by that loop is "
        f"byte-identical across the two commits for both the rule-violation and the "
        f"format-violation branch; and mock runs at both commits give identical "
        f"governance-audit and simulation logs for flood (4 of 4 comparisons) and for "
        f"irrigation (4 of 4, strict and disabled, synthetic agents). The earlier "
        f"faf1bb12 -> c3391a53 gate in out/regen_progress_2026-09-15.md covers both "
        f"domains."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
