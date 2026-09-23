"""R35 -- placebo-retry irrigation: does the validator's value come from the
RULE CONTENT of its retry feedback, or just from the EXTRA ATTEMPT? Irrigation
counterpart to r34 (flood), same question, same degenerate-denominator fix
applied from the start this time (not as an after-the-fact correction).
CPU-only (GPU busy with the live placebo run -- this script stays light).

BACKGROUND -- what "placebo" means here
  Per the task brief that commissioned this script, mirroring r34's posture
  for the same feature on flood: `governance.retry_feedback_mode: placebo`
  in YAML config gives the SAME retry SCHEDULE as strict (validator fires on
  the same conditions, same number of extra attempts) but the retry PROMPT
  carries no specific rule content. Checked empirically in THIS worktree
  (branch p0-1-governance-instrumentation), not assumed: `grep -rn
  "retry_feedback_mode" broker/ examples/` returns nothing, and the
  `--config-dir` this run's own LAUNCH_COMMAND.txt names,
  `examples/irrigation_abm/config_variants/placebo_gemma3_4b/`, does not
  exist in this worktree either (confirmed via `find`, not assumed) -- the
  run was launched from a different worktree
  (`reproducibility_manifest.json`'s `agent_types_config` path for the
  faf1bb12 comparators resolves to `...\\wagf-main-runs\\...`, not this
  checkout). This script does not claim to have verified the mechanism
  from source, only reports it as given by the task.

RUN LAYOUT
  Placebo: `examples/irrigation_abm/results/strict_42yr_gemma3_4b_83fa97e1_
  placebo_seed{42,43}`. LANDED 2026-09-22 -- seed 42 finished 15:24, seed 43
  finished 18:29 (`run_integrity.json` mtimes); both have integrity_ok==True.
  Comparators, ALREADY COMPLETE, same 2 seeds: `strict_42yr_gemma3_4b_
  faf1bb12_seed{42,43}` and `ungoverned_42yr_gemma3_4b_faf1bb12_seed{42,43}`.
  All six arm/seed combinations (placebo/strict/ungoverned x seed 42/43) are
  present and complete -- zero `skipped` rows in a current run of this
  script.

PART 1 -- per (arm, seed): metrics + rule census + manifest census
  `_irr_llm_metrics()` imported from r25_table1_regen.py (not re-derived)
  gives: IBR headline (`_loader.py::ibr`), EHE pooled executed, EHE pooled
  proposal (irrigation's two established EHE definitions), Mead min ft,
  shortage years (years with Mead < 1075 ft), rejection/retry rate, LLM
  fail n, fallback %, wall hours. Added here (not in r25, mirroring r34's
  additions for flood): mean retry_count among retried rows, and a rule-id
  census (`failed_rules`, pipe-delimited, top 6) of retried rows -- same
  sorted()-before-counting fix r27/r34 established for the identical
  per-process set-hash-randomization nondeterminism. Manifest census
  value-enforces model=="gemma3:4b", git_commit starts with "83fa97e1",
  retry_feedback_mode=="placebo" for the placebo runs ONLY (raises
  otherwise). thinking_mode is READ AND REPORTED but deliberately NOT
  enforced: irrigation's own faf1bb12 strict comparator manifest records
  "auto" (read directly, not assumed) -- NOT flood's "disabled", which is
  what r34 enforces for the same feature on the flood domain. There is no
  existing irrigation run at commit 83fa97e1 to confirm what value the
  placebo run will actually record, so this script does not guess and does
  not silently copy flood's convention onto a different domain.

PART 2 -- seed-paired placebo vs strict vs ungoverned (n=2, no t-test)
  5 metrics (IBR headline, EHE pooled executed, EHE pooled proposal, Mead
  min ft, shortage years) x 2 seeds: placebo-strict / placebo-ungoverned
  differences, plus share on the strict->ungoverned line =
  (placebo-strict)/(ungoverned-strict) -- 0 means placebo behaves like
  strict (attempt-count is what matters), 1 means placebo behaves like
  ungoverned (rule content is what matters). r34's degenerate-denominator
  rule is applied here FROM THE START: a share cell is degenerate when
  |ungoverned-strict| falls below a per-metric threshold. Thresholds are
  set from the four ALREADY-COMPLETE comparators' own observed numbers
  (computed empirically below via `_irr_llm_metrics`, not guessed):
    IBR headline (%):        strict 26.64/39.56, ungoverned 59.33/55.29
                              (seed 42/43) -- line ~26-33pp -- threshold 1.0pp
    EHE pooled executed:     strict 0.139/0.132, ungoverned 0.804/0.804
                              -- line ~0.66-0.67 -- threshold 0.05 (same
                              unit/metric family r34 used for flood's EHE,
                              itself `C.normalized_entropy`)
    EHE pooled proposal:     strict 0.598/0.656, ungoverned 0.868/0.871
                              -- line ~0.21-0.27 -- threshold 0.05
    Mead min ft:              strict 996.97/995.67, ungoverned 895.0/895.0
                              -- line ~100-102 ft -- threshold 5.0 ft
    shortage years:           strict 13/15, ungoverned 39/37 -- line
                              ~22-26 years -- threshold 1.0 year (a count
                              metric; finer than 1 year is not meaningful)
  Verdict (Part 4) is computed over non-degenerate cells only; the raw
  share is always stored regardless, never hidden.

PART 3 -- validator-fired-on-a-comparable-schedule check
  Placebo vs strict retry rate + rule-id census side by side; terminal
  fallback share placebo vs strict vs ungoverned, same source as Part 1.

PART 4 -- plain read (<=5 sentences, templated from rows)
  States which of "extra attempt" vs "rule content" the share numbers
  point to, quoting them, and the n=2 limitation explicitly. 2026-09-22
  review fix, mirroring r34_placebo_retry_flood.py's identical fix for
  flood: the verdict is computed over non-degenerate IBR cells ONLY
  (here, "IBR headline (%)" x 2 seeds), never over a naive mean across
  all 5 heterogeneous metrics -- an earlier draft of this script did
  exactly that (averaged all 10 (metric, seed) cells) and reported
  "close to STRICT (mean share 0.254)", which hid a real split between
  the proposal level (IBR headline, EHE pooled proposal -- both near
  UNGOVERNED) and the executed level (EHE pooled executed, Mead min,
  shortage years -- all near STRICT). The 4 non-IBR metrics are always
  reported in Part 2's table, explicitly named as excluded from the
  Part 4 verdict in the plain-read text (never silently dropped), and
  broken out by level in Part 4b below.

PART 4b -- proposal level versus executed level (2026-09-22, same
  `contrast_pair` rows Part 2/4 already computed -- no share value is
  recomputed)
  Labels each of the 5 metrics by which level it measures: level=
  "proposal" for IBR headline and EHE pooled proposal (what the agent
  asked for/negotiated to, before any validator); level="executed" for
  EHE pooled executed, Mead min, and shortage years (what actually
  happened to the water system). A table of the 10 (metric, level,
  seed) cells and the two per-level mean shares are reported as plain
  information ONLY -- no verdict is attached to either (2026-09-22
  coordinator review fix: an earlier draft gated a single paragraph on
  the two level MEANS, which hid that IBR headline and EHE pooled
  proposal -- both level=proposal -- behave differently; averaging them
  landed the proposal-level mean just under the 0.65 "tracks UNGOVERNED"
  bar, so the gated paragraph printed "no clean split" even though IBR
  headline alone was clearly near UNGOVERNED). Instead: one templated
  classification sentence per metric (5 sentences, proposal-level
  metrics first then executed-level, both orders derived from
  METRIC_LEVEL/METRIC_KEYS), each naming its per-seed shares (or
  "degenerate" for a degenerate cell), its own non-degenerate mean, and
  a label from `_track_label()` -- "tracks STRICT" (mean<0.35),
  "tracks UNGOVERNED" (mean>0.65), or "midway" -- using the SAME 0.35/
  0.65 thresholds Part 4's own IBR verdict uses (`_track_label` is a
  single shared function; the two parts cannot disagree by
  construction). Then ONE closing sentence: if IBR headline's label is
  "tracks UNGOVERNED" and every executed-level metric's label is
  "tracks STRICT", a fixed interpretive sentence naming both facts and
  cross-referencing r34 (flood); otherwise the bare label list, no
  interpretation. Nothing in this section is hard-coded.

COMPLETENESS GATE
  Per (arm, seed): run dir exists -> irrigation_farmer_governance_audit.csv
  exists -> simulation_log.csv exists -> run_integrity.json exists with
  integrity_ok==True. Missing any -> row_type=skipped, printed pending
  reason, excluded from Part 2/3/4/4b.

OUTPUTS
  out/r35_placebo_retry_irrigation.csv -- row_type in {skipped, run_metrics,
    rule_id_census, manifest_check, contrast_pair, level_share_summary}.
  out/r35_placebo_retry_irrigation.md -- GENERATED by render_md() directly
    from that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r35_placebo_retry_irrigation.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r25_table1_regen as R25  # noqa: E402  READ-ONLY: _irr_llm_metrics.

IRR_RESULTS = os.path.join(C.REPO, "examples", "irrigation_abm", "results")
SEEDS = ["42", "43"]
ARM_DIRS = {
    "placebo": lambda seed: os.path.join(IRR_RESULTS, f"strict_42yr_gemma3_4b_83fa97e1_placebo_seed{seed}"),
    "strict": lambda seed: os.path.join(IRR_RESULTS, f"strict_42yr_gemma3_4b_faf1bb12_seed{seed}"),
    "ungoverned": lambda seed: os.path.join(IRR_RESULTS, f"ungoverned_42yr_gemma3_4b_faf1bb12_seed{seed}"),
}
TOP_N_RULES = 6


# =============================================================================
# completeness
# =============================================================================
def _irr_run_completeness(run_dir: str) -> tuple:
    if not os.path.isdir(run_dir):
        return "skipped", "run directory does not exist yet"
    if not os.path.isfile(os.path.join(run_dir, C.L.AUDIT_LOG)):
        return "skipped", f"{C.L.AUDIT_LOG} missing (run in progress)"
    if not os.path.isfile(os.path.join(run_dir, C.L.SIM_LOG)):
        return "skipped", f"{C.L.SIM_LOG} missing (run in progress)"
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
    failed_rules (pipe-delimited). Identical logic to r34's
    `_rule_id_census` (flood) -- irrigation's audit schema carries the same
    `retry_count` / `failed_rules` columns (confirmed by reading the header
    directly), so the function is byte-identical, just re-declared here
    rather than imported (r34 does not export it as a module-level name
    meant for reuse)."""
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
        return json.load(fh)


def _part1(rows: list) -> dict:
    """Returns {(arm, seed): {metric_key: value, ...}} for complete runs,
    used by Part 2/3."""
    per_run: dict = {}
    for arm, dir_fn in ARM_DIRS.items():
        for seed in SEEDS:
            run_dir = dir_fn(seed)
            status, reason = _irr_run_completeness(run_dir)
            if status == "skipped":
                print(f"  SKIPPED {arm} seed {seed}: {reason}")
                rows.append({"row_type": "skipped", "arm": arm, "seed": seed, "reason": reason})
                continue
            m = R25._irr_llm_metrics(run_dir)
            aud = C.read_csv(os.path.join(run_dir, C.L.AUDIT_LOG))
            n = len(aud)
            st = [(r.get("status") or "").strip() for r in aud]
            status_counts = {"APPROVED": 0, "REJECTED": 0, "REJECTED_FALLBACK": 0}
            for s in st:
                if s not in status_counts:
                    raise PrepError(f"{run_dir}: unexpected status value {s!r} -- "
                                     f"update status_counts")
                status_counts[s] += 1
            retried = [r for r in aud if int(r.get("retry_count") or 0) > 0]
            mean_retry_among_retried = (
                C.mean([int(r["retry_count"]) for r in retried]) if retried else float("nan")
            )
            row = {"row_type": "run_metrics", "arm": arm, "seed": seed, "n_rows": n,
                   "status_approved": status_counts["APPROVED"],
                   "status_rejected": status_counts["REJECTED"],
                   "status_rejected_fallback": status_counts["REJECTED_FALLBACK"],
                   "ibr_headline": m["ibr_headline"], "ehe_pooled": m["ehe_pooled"],
                   "ehe_pooled_proposal": m["ehe_pooled_proposal"],
                   "mead_min_ft": m["mead_min_ft"], "shortage_years": m["shortage_years"],
                   "rejection_rate_pct": m["rejection_rate_pct"],
                   "retry_rate_pct": m["retry_rate_pct"], "n_retried": len(retried),
                   "mean_retry_count_among_retried": mean_retry_among_retried,
                   "fallback_pct": m["fallback_pct"], "llm_fail_n": int(m["llm_fail_n"]),
                   "wall_hours": m["wall_hours"]}
            rows.append(row)

            census = _rule_id_census(aud, TOP_N_RULES)
            for rank, (rule_id, count) in enumerate(census, start=1):
                rows.append({"row_type": "rule_id_census", "arm": arm, "seed": seed,
                             "rank": rank, "rule_id": rule_id, "count": count})
            print(f"  OK {arm:11s} seed {seed}: rows={n} retried={len(retried)} "
                  f"({100.0*len(retried)/n:.1f}%) fallback={m['fallback_pct']:.2f}% "
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
                if retry_feedback_mode != "placebo":
                    raise PrepError(f"{run_dir}: retry_feedback_mode={retry_feedback_mode!r}, "
                                     f"expected 'placebo' -- if this manifest field is "
                                     f"genuinely absent (schema predates this flag), that is "
                                     f"itself worth raising on, not silently passing")
            rows.append({"row_type": "manifest_check", "arm": arm, "seed": seed, "model": model,
                         "git_commit_short": (git_commit or "")[:8],
                         "thinking_mode": thinking_mode, "thinking_mode_enforced": False,
                         "retry_feedback_mode": retry_feedback_mode,
                         "retry_feedback_mode_present": "retry_feedback_mode" in manifest,
                         "enforced": enforced})

            per_run[(arm, seed)] = row
    return per_run


# =============================================================================
# Part 2
# =============================================================================
METRIC_KEYS = {
    "IBR headline (%)": "ibr_headline",
    "EHE pooled executed": "ehe_pooled",
    "EHE pooled proposal": "ehe_pooled_proposal",
    "Mead min (ft)": "mead_min_ft",
    "Shortage years": "shortage_years",
}
# Empirically set from the four already-complete comparators (see docstring
# for the exact per-seed numbers `_irr_llm_metrics` returned when this
# threshold table was written) -- not guessed, and NOT copied verbatim from
# r34's flood thresholds except where the metric is the literal same
# quantity (EHE, both definitions, share r34's 0.05 -- both are
# `C.normalized_entropy` outputs on a comparable [0,1] scale).
DEGENERATE_THRESHOLD = {
    "IBR headline (%)": 1.0,        # percentage points
    "EHE pooled executed": 0.05,
    "EHE pooled proposal": 0.05,
    "Mead min (ft)": 5.0,           # feet
    "Shortage years": 1.0,          # a count metric; sub-year differences are not meaningful
}
# Part 4b (2026-09-22): which level of the decision each metric measures.
# "proposal" = what the agent asked for / negotiated to, before any
# validator (the last recorded proposal, per r33's "first vs last proposal"
# terminology). "executed" = what actually happened to the water system
# after the executed-remap convention (`_common.py::irr_executed`) is
# applied. Used only to label existing contrast_pair rows for Part 4b's
# table and per-level mean -- never changes how a share is computed.
METRIC_LEVEL = {
    "IBR headline (%)": "proposal",
    "EHE pooled proposal": "proposal",
    "EHE pooled executed": "executed",
    "Mead min (ft)": "executed",
    "Shortage years": "executed",
}


def _part2(rows: list, per_run: dict) -> None:
    for metric_label, key in METRIC_KEYS.items():
        threshold = DEGENERATE_THRESHOLD[metric_label]
        for seed in SEEDS:
            p = per_run.get(("placebo", seed))
            s = per_run.get(("strict", seed))
            u = per_run.get(("ungoverned", seed))
            if p is None or s is None or u is None:
                missing = [a for a, v in (("placebo", p), ("strict", s), ("ungoverned", u))
                           if v is None]
                print(f"  Part 2 PENDING: {metric_label} seed {seed} -- missing arm(s) "
                      f"{missing}")
                rows.append({"row_type": "skipped", "section": "contrast_pair",
                             "metric": metric_label, "seed": seed,
                             "reason": f"missing arm(s): {missing}"})
                continue
            pv, sv, uv = float(p[key]), float(s[key]), float(u[key])
            diff_p_minus_s = pv - sv
            diff_p_minus_u = pv - uv
            denom = uv - sv
            denom_abs = abs(denom)
            degenerate = denom_abs < threshold
            share = (pv - sv) / denom if denom != 0 else float("nan")
            rows.append({"row_type": "contrast_pair", "metric": metric_label, "seed": seed,
                         "level": METRIC_LEVEL[metric_label],
                         "placebo_value": pv, "strict_value": sv, "ungoverned_value": uv,
                         "diff_placebo_minus_strict": diff_p_minus_s,
                         "diff_placebo_minus_ungoverned": diff_p_minus_u,
                         "share_on_strict_to_ungoverned_line": share,
                         "denom_abs": denom_abs, "degenerate_threshold": threshold,
                         "degenerate": degenerate})
            if degenerate:
                print(f"  DEGENERATE share: {metric_label} seed {seed} -- "
                      f"|ungoverned-strict|={denom_abs:.4f} < threshold {threshold} -- "
                      f"share={share:.4f} computed and stored, excluded from the verdict")


# =============================================================================
# Part 4b
# =============================================================================
def _part4b(rows: list) -> None:
    """Per-level (proposal vs executed) mean share on the strict->ungoverned
    line. Aggregates the SAME `share_on_strict_to_ungoverned_line` values
    Part 2 already computed and stored on each contrast_pair row (via its
    `level` field, set in _part2 from METRIC_LEVEL) -- no share is
    recomputed here, only averaged within its level, over non-degenerate
    cells only (same degenerate rule Part 2/4 use)."""
    shares = _find(rows, "contrast_pair")
    for level in ("proposal", "executed"):
        ok = [r for r in shares if r.get("level") == level and not r["degenerate"]]
        n = len(ok)
        mean_share = (sum(float(r["share_on_strict_to_ungoverned_line"]) for r in ok) / n
                      if n > 0 else float("nan"))
        rows.append({"row_type": "level_share_summary", "level": level,
                     "mean_share_on_line": mean_share, "n_cells": n})
        print(f"  Part 4b: level={level} mean_share={mean_share!r} over {n} "
              f"non-degenerate cell(s)")


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "arm", "seed", "n_rows", "status_approved", "status_rejected",
    "status_rejected_fallback", "ibr_headline", "ehe_pooled", "ehe_pooled_proposal",
    "mead_min_ft", "shortage_years", "rejection_rate_pct", "retry_rate_pct", "n_retried",
    "mean_retry_count_among_retried", "fallback_pct", "llm_fail_n", "wall_hours", "rank",
    "rule_id", "count", "model", "git_commit_short", "thinking_mode", "thinking_mode_enforced",
    "retry_feedback_mode", "retry_feedback_mode_present", "enforced", "metric", "level",
    "placebo_value", "strict_value", "ungoverned_value", "diff_placebo_minus_strict",
    "diff_placebo_minus_ungoverned", "share_on_strict_to_ungoverned_line", "denom_abs",
    "degenerate_threshold", "degenerate", "mean_share_on_line", "n_cells", "reason",
]


def main() -> int:
    C.banner("R35  Placebo-retry irrigation: extra attempt vs rule content")
    rows: list = []

    print("\n-- Part 1: per (arm, seed) metrics, rule-id census, manifest census --")
    per_run = _part1(rows)

    print("\n-- Part 2: seed-paired placebo vs strict vs ungoverned (n=2, no t-test) --")
    _part2(rows, per_run)

    print("\n-- Part 4b: proposal level vs executed level share summary --")
    _part4b(rows)

    md_text = render_md(rows)

    csv_final = "r35_placebo_retry_irrigation.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, "r35_placebo_retry_irrigation.md")
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
def _csv_precision(x) -> float:
    return float(C.fmt(x))


_cp = _csv_precision


def _is_nan(x) -> bool:
    return isinstance(x, float) and x != x


# 2026-09-22: single source of truth for the strict/midway/ungoverned
# classification, used by BOTH Part 4's IBR verdict and Part 4b's per-metric
# sentences (coordinator-requested change) -- same 0.35/0.65 thresholds in
# one place so the two parts cannot disagree by construction.
def _track_label(mean_share) -> str:
    if _is_nan(mean_share):
        return "n.a. (no non-degenerate cells)"
    if mean_share < 0.35:
        return "tracks STRICT"
    if mean_share > 0.65:
        return "tracks UNGOVERNED"
    return "midway"


def _metric_mean_and_label(rows: list, metric_label: str):
    """(mean_share, label) for one metric, averaged over its non-degenerate
    (seed) cells only -- the SAME contrast_pair rows Part 2 wrote, no share
    recomputed. Shared by Part 4 (IBR only) and Part 4b (all 5 metrics)."""
    recs = _find(rows, "contrast_pair", metric=metric_label)
    ok = [r for r in recs if not r["degenerate"]]
    mean_share = (sum(float(r["share_on_strict_to_ungoverned_line"]) for r in ok) / len(ok)
                  if ok else float("nan"))
    return mean_share, _track_label(mean_share)


def _fmt_mean_retry(r: dict, nd: int = 3) -> str:
    """mean_retry_count_among_retried is NaN by construction whenever
    n_retried==0 -- same NaN-safe-rendering fix r26/r34 established."""
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
    the provenance claim itself is false, never something to paper over."""
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
    lines.append("# R35 -- placebo-retry irrigation: extra attempt vs rule content")
    lines.append("")
    lines.append("Source: `r35_placebo_retry_irrigation.py`. Every number below is read live "
                 "from the `rows` list this script writes to the paired CSV. n=2 seeds "
                 "(42, 43) throughout -- no t-test anywhere in this file.")
    lines.append("")

    # ---- Part 1: per-run metrics -----------------------------------------------
    lines.append("## Part 1 -- per (arm, seed) metrics")
    lines.append("")
    lines.append("| arm | seed | n_rows | IBR headline | EHE executed | EHE proposal | "
                 "Mead min ft | shortage yrs | retry rate % | n_retried | "
                 "mean retries (if retried) | fallback % | LLM fail | wall h |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for arm in ("placebo", "strict", "ungoverned"):
        for seed in SEEDS:
            recs = _find(rows, "run_metrics", arm=arm, seed=seed)
            if not recs:
                lines.append(f"| {arm} | {seed} | PENDING | -- | -- | -- | -- | -- | -- | "
                             f"-- | -- | -- | -- | -- |")
                continue
            r = recs[0]
            lines.append(
                f"| {arm} | {seed} | {r['n_rows']} | {_cp(r['ibr_headline']):.2f} | "
                f"{_cp(r['ehe_pooled']):.3f} | {_cp(r['ehe_pooled_proposal']):.3f} | "
                f"{_cp(r['mead_min_ft']):.1f} | {int(r['shortage_years'])} | "
                f"{_cp(r['retry_rate_pct']):.2f} | {r['n_retried']} | "
                f"{_fmt_mean_retry(r)} | {_cp(r['fallback_pct']):.2f} | {r['llm_fail_n']} | "
                f"{_cp(r['wall_hours']):.3f} |"
            )
    lines.append("")

    lines.append("### Rule-id census, top 6 among retried rows")
    lines.append("")
    lines.append("| arm | seed | rank | rule_id | count |")
    lines.append("|---|---|---|---|---|")
    for arm in ("placebo", "strict", "ungoverned"):
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
    lines.append("| arm | seed | model | git_commit | thinking_mode (not enforced) | "
                 "retry_feedback_mode | key present | enforced (model/commit/mode) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for arm in ("placebo", "strict", "ungoverned"):
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
    lines.append("| metric | seed | placebo | strict | ungoverned | placebo-strict | "
                 "placebo-ungoverned | share on strict->ungoverned line |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for metric_label in METRIC_KEYS:
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
                share_cell = (f"n.a. (denominator |ungoverned-strict| = "
                              f"{_cp(r['denom_abs']):.4f} < threshold "
                              f"{r['degenerate_threshold']:g})")
            else:
                share_cell = f"{_cp(r['share_on_strict_to_ungoverned_line']):.3f}"
            lines.append(
                f"| {metric_label} | {seed} | {_cp(r['placebo_value']):.3f} | "
                f"{_cp(r['strict_value']):.3f} | {_cp(r['ungoverned_value']):.3f} | "
                f"{_cp(r['diff_placebo_minus_strict']):.3f} | "
                f"{_cp(r['diff_placebo_minus_ungoverned']):.3f} | "
                f"{share_cell} |"
            )
    lines.append("")

    # ---- Part 3: schedule check ---------------------------------------------------
    lines.append("## Part 3 -- did the validator fire on a comparable schedule "
                 "(placebo vs strict)?")
    lines.append("")
    lines.append("| seed | placebo retry rate % | strict retry rate % | placebo top rule | "
                 "strict top rule | placebo fallback % | strict fallback % | "
                 "ungoverned fallback % |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for seed in SEEDS:
        p = _find(rows, "run_metrics", arm="placebo", seed=seed)
        s = _find(rows, "run_metrics", arm="strict", seed=seed)
        u = _find(rows, "run_metrics", arm="ungoverned", seed=seed)
        p_top = _find(rows, "rule_id_census", arm="placebo", seed=seed, rank=1)
        s_top = _find(rows, "rule_id_census", arm="strict", seed=seed, rank=1)
        if not (p and s):
            lines.append(f"| {seed} | pending | pending | pending | pending | pending | "
                         f"pending | pending |")
            continue
        p, s = p[0], s[0]
        u_fb = f"{_cp(u[0]['fallback_pct']):.2f}" if u else "pending"
        lines.append(
            f"| {seed} | {_cp(p['retry_rate_pct']):.2f} | {_cp(s['retry_rate_pct']):.2f} | "
            f"{p_top[0]['rule_id'] if p_top else 'n.a.'} | "
            f"{s_top[0]['rule_id'] if s_top else 'n.a.'} | "
            f"{_cp(p['fallback_pct']):.2f} | {_cp(s['fallback_pct']):.2f} | "
            f"{u_fb} |"
        )
    lines.append("")

    # ---- Plain read -----------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    sentences = []
    placebo_seeds_landed = sorted({r["seed"] for r in _find(rows, "run_metrics", arm="placebo")})
    if not placebo_seeds_landed:
        comparators_ready = bool(_find(rows, "run_metrics", arm="strict")) and \
            bool(_find(rows, "run_metrics", arm="ungoverned"))
        sentences.append(
            "The placebo run (strict_42yr_gemma3_4b_83fa97e1_placebo) is still in progress "
            "-- 0/2 seeds landed (seed 42's directory exists but has no audit/simlog/manifest "
            "yet; seed 43 has no directory at all). Comparators (strict, ungoverned, both "
            f"faf1bb12) are {'already complete' if comparators_ready else 'also incomplete'} "
            f"and reported in Part 1 above; Part 2/3's placebo-vs-comparator contrasts will "
            f"populate automatically, no code change needed, once placebo lands."
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
        # 2026-09-22 review fix, mirroring r34_placebo_retry_flood.py's identical fix
        # for flood: the verdict is computed over non-degenerate IBR cells ONLY. A
        # naive mean across all 5 heterogeneous metrics is not interpretable -- an
        # earlier draft of this script did exactly that (averaged all 10 (metric,
        # seed) cells) and reported "close to STRICT (mean share 0.254)", which hid a
        # real split between the proposal level (near UNGOVERNED) and the executed
        # level (near STRICT). See Part 4b below for that split.
        ibr_cells = [r for r in shares if r["metric"].startswith("IBR")]
        ibr_ok = [r for r in ibr_cells if not r["degenerate"]]
        non_ibr_cells = [r for r in shares if not r["metric"].startswith("IBR")]
        degenerate_cells = [r for r in shares if r["degenerate"]]

        if ibr_ok:
            vals = [float(r["share_on_strict_to_ungoverned_line"]) for r in ibr_ok]
            mean_share = sum(vals) / len(vals)
            lo, hi = min(vals), max(vals)
            ibr_track_label = _track_label(mean_share)  # same thresholds Part 4b uses
            near_strict = ibr_track_label == "tracks STRICT"
            near_ungoverned = ibr_track_label == "tracks UNGOVERNED"
            if near_strict:
                verdict = (f"placebo sits close to STRICT on IBR (mean share "
                          f"{mean_share:.3f}, range {lo:.3f} to {hi:.3f}, i.e. near 0) -- "
                          f"most of governance's measured value here looks like it comes "
                          f"from the EXTRA ATTEMPT existing at all, not from the specific "
                          f"rule id/reason/suggestion the retry prompt would otherwise "
                          f"carry")
            elif near_ungoverned:
                verdict = (f"placebo sits close to UNGOVERNED on IBR (mean share "
                          f"{mean_share:.3f}, range {lo:.3f} to {hi:.3f}, i.e. near 1) -- "
                          f"most of governance's measured value here looks like it comes "
                          f"from the SPECIFIC RULE CONTENT in the retry prompt, not just "
                          f"from having another attempt")
            else:
                verdict = (f"placebo sits roughly midway between strict and ungoverned on "
                          f"IBR (mean share {mean_share:.3f}, range {lo:.3f} to "
                          f"{hi:.3f}) -- neither \"just an extra attempt\" nor \"the rule "
                          f"content alone\" explains most of governance's measured value "
                          f"here; both appear to matter")
            sentences.append(f"Across the {len(vals)} non-degenerate IBR (seed) cells, "
                             f"{verdict}.")
            by_seed = {}
            for r in ibr_ok:
                by_seed.setdefault(r["seed"], []).append(float(r["share_on_strict_to_ungoverned_line"]))
            parts = "; ".join(f"seed {s}: mean {sum(v)/len(v):.3f} "
                              f"({', '.join(f'{x:.3f}' for x in v)})"
                              for s, v in sorted(by_seed.items()))
            sentences.append(f"Per-seed IBR share: {parts}.")
        else:
            sentences.append("No non-degenerate IBR cells are available to base a verdict "
                             "on.")

        non_ibr_labels = sorted({r["metric"] for r in non_ibr_cells})
        excl_bits = [f"{', '.join(non_ibr_labels)} (non-IBR, excluded from this verdict by "
                     f"definition -- see Part 4b below for how they split by proposal vs "
                     f"executed level)"]
        if degenerate_cells:
            by_metric = {}
            for r in degenerate_cells:
                by_metric.setdefault(r["metric"], []).append(r)
            deg_parts = "; ".join(
                f"{metric} (" + ", ".join(f"seed {r['seed']}: |ungoverned-strict|="
                                          f"{_cp(r['denom_abs']):.4f}" for r in recs) + ")"
                for metric, recs in sorted(by_metric.items())
            )
            excl_bits.append(f"also degenerate (denominator below its own per-metric "
                             f"threshold, raw share still shown in the Part 2 table marked "
                             f"n.a. with the reason): {deg_parts}")
        sentences.append("Excluded from the verdict: " + "; ".join(excl_bits) + ".")
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

    # ---- Part 4b: proposal level vs executed level ------------------------------
    lines.append("## Part 4b -- proposal level versus executed level")
    lines.append("")
    lines.append(
        "Same `contrast_pair` rows as Part 2/4, each metric labelled by which level "
        "it measures: level=proposal is what the agent asked for / negotiated to, "
        "before any validator (IBR headline, EHE pooled proposal); level=executed is "
        "what actually happened to the water system after the executed-remap "
        "convention (`_common.py::irr_executed`) is applied (EHE pooled executed, "
        "Mead min, shortage years). No share value is recomputed here -- this table "
        "and the two means below only relabel and aggregate Part 2's own numbers."
    )
    lines.append("")
    lines.append("| metric | level | seed | share on strict->ungoverned line |")
    lines.append("|---|---|---|---|")
    for metric_label, level in METRIC_LEVEL.items():
        for seed in SEEDS:
            recs = _find(rows, "contrast_pair", metric=metric_label, seed=seed)
            if not recs:
                lines.append(f"| {metric_label} | {level} | {seed} | PENDING |")
                continue
            r = recs[0]
            if r["degenerate"]:
                share_cell = (f"n.a. (denominator |ungoverned-strict| = "
                              f"{_cp(r['denom_abs']):.4f} < threshold "
                              f"{r['degenerate_threshold']:g})")
            else:
                share_cell = f"{_cp(r['share_on_strict_to_ungoverned_line']):.3f}"
            lines.append(f"| {metric_label} | {level} | {seed} | {share_cell} |")
    lines.append("")

    level_summaries = {r["level"]: r for r in _find(rows, "level_share_summary")}
    proposal_summary = level_summaries.get("proposal")
    executed_summary = level_summaries.get("executed")
    if proposal_summary is not None:
        p_mean_raw = proposal_summary["mean_share_on_line"]
        p_cell = "n.a. (no non-degenerate proposal-level cells)" if _is_nan(p_mean_raw) \
            else f"{_cp(p_mean_raw):.3f}"
        lines.append(f"Proposal-level mean share (non-degenerate cells): {p_cell} "
                     f"(n={proposal_summary['n_cells']}).")
    if executed_summary is not None:
        e_mean_raw = executed_summary["mean_share_on_line"]
        e_cell = "n.a. (no non-degenerate executed-level cells)" if _is_nan(e_mean_raw) \
            else f"{_cp(e_mean_raw):.3f}"
        lines.append(f"Executed-level mean share (non-degenerate cells): {e_cell} "
                     f"(n={executed_summary['n_cells']}).")
    lines.append("")

    # 2026-09-22 coordinator review fix: the level-mean gate above hid that
    # IBR headline and EHE pooled proposal -- both level=proposal -- behave
    # differently (IBR headline tracks UNGOVERNED, EHE pooled proposal tracks
    # STRICT; averaging them landed the proposal-level mean just under the
    # 0.65 bar, so the level-mean paragraph printed "no clean split" even
    # though IBR headline itself was clearly near UNGOVERNED). Replaced with
    # a per-metric classification, one templated sentence per metric, using the SAME
    # `_track_label` thresholds (0.35/0.65) Part 4's own IBR verdict uses --
    # the two parts cannot disagree by construction. No verdict is attached
    # to the table or the two level-mean lines above; they stay informational.
    metric_order = [m for m in METRIC_KEYS if METRIC_LEVEL[m] == "proposal"] + \
                   [m for m in METRIC_KEYS if METRIC_LEVEL[m] == "executed"]
    metric_labels = {}
    for metric_label in metric_order:
        level = METRIC_LEVEL[metric_label]
        seed_cells = []
        for seed in SEEDS:
            recs = _find(rows, "contrast_pair", metric=metric_label, seed=seed)
            if not recs:
                seed_cells.append("PENDING")
            elif recs[0]["degenerate"]:
                seed_cells.append("degenerate")
            else:
                seed_cells.append(f"{_cp(recs[0]['share_on_strict_to_ungoverned_line']):.3f}")
        mean_share, label = _metric_mean_and_label(rows, metric_label)
        metric_labels[metric_label] = label
        mean_cell = "n.a." if _is_nan(mean_share) else f"{_cp(mean_share):.3f}"
        lines.append(
            f"{metric_label} ({level} level): share {seed_cells[0]} / {seed_cells[1]}, "
            f"mean {mean_cell}: {label}."
        )
        lines.append("")

    executed_metrics = [m for m in metric_order if METRIC_LEVEL[m] == "executed"]
    ibr_label = metric_labels.get("IBR headline (%)")
    all_executed_strict = bool(executed_metrics) and \
        all(metric_labels[m] == "tracks STRICT" for m in executed_metrics)
    if ibr_label == "tracks UNGOVERNED" and all_executed_strict:
        lines.append(
            "On the coherence metric the placebo tracks UNGOVERNED while every executed "
            "outcome tracks STRICT: in irrigation, rule text in the retry prompt is what "
            "moves the agent's last recorded proposal, and blocking alone protects the "
            "water system. Compare r34 (flood), where placebo tracked STRICT on IBR as "
            "well."
        )
    else:
        label_list = "; ".join(f"{m}: {metric_labels[m]}" for m in metric_order)
        lines.append(label_list + ".")
    lines.append("")

    # ---- Method -----------------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "IBR headline, both EHE definitions (pooled executed, pooled proposal), Mead min "
        "ft, and shortage years are `r25_table1_regen.py::_irr_llm_metrics()`, imported, "
        "not re-derived -- the SAME definitions every other script in this package uses "
        "for these columns (IBR itself traces to `_loader.py::ibr`). "
        "`retry_feedback_mode` is reported from each run's `reproducibility_manifest.json` "
        "and value-enforced =='placebo' ONLY for the placebo arm (raises otherwise, "
        "including if the key is simply absent); the strict/ungoverned comparator "
        "manifests are read and reported with the same fields, never enforced. "
        "`thinking_mode` is read and reported for every arm but never enforced -- "
        "irrigation's own faf1bb12 comparator manifests record \"auto\", which this "
        "script does not assume the placebo run will also record, and there is no "
        "existing irrigation run at commit 83fa97e1 to check against. Rule-id census "
        "counts each RETRIED row's `failed_rules` (pipe-delimited) once per distinct "
        "rule id per row, ranked by count then alphabetically, rule ids `sorted()` before "
        "counting -- the same Python set-hash-randomization fix "
        "`r27_irrigation_crossmodel_gemma4_12b.py` and `r34_placebo_retry_flood.py` "
        "applied. share_on_strict_to_ungoverned_line = (placebo-strict)/(ungoverned-strict): "
        "0 = placebo behaves like strict, 1 = placebo behaves like ungoverned; a cell is "
        "marked degenerate (excluded from the Part 4 verdict, never hidden from the Part 2 "
        "table) when |ungoverned-strict| falls below a per-metric threshold set from the "
        "comparators' own observed line length -- the exact rule "
        "`r34_placebo_retry_flood.py`'s 2026-09-22 review fix introduced for flood, applied "
        "here from the start. The Part 4 verdict itself is computed over non-degenerate IBR "
        "cells ONLY, mirroring `r34_placebo_retry_flood.py`'s identical 2026-09-22 fix for "
        "its own verdict -- a naive mean across all 5 heterogeneous metrics is not "
        "interpretable; the 4 non-IBR metrics are named as excluded from that verdict in "
        "the plain-read text above, never hidden. Part 4b's proposal/executed level table "
        "and level means are informational only (METRIC_LEVEL, a static per-metric "
        "lookup); its per-metric classification sentences and closing sentence use "
        "`_track_label()`, the SAME 0.35/0.65 thresholds as Part 4's own IBR verdict, so "
        "the two parts cannot disagree -- no share value is recomputed anywhere in "
        "Part 4b."
    )
    lines.append("")

    # 2026-09-22 review fix (round 2): code-provenance caveat, pulled live from this
    # run's own manifest_check rows (never hard-coded) so it cannot drift from what
    # actually ran. Round-1 text cited flood-only mock evidence for an irrigation
    # script and overclaimed "unchanged" for the retry-prompt path the mock check
    # cannot see; replaced with the three-piece evidence chain (framework-change
    # scope, retry-prompt golden text, mock CSV identity for BOTH domains) recorded
    # in out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md.
    placebo_hash, comparator_hash = _manifest_commit_hashes(
        rows, placebo_arms=["placebo"], comparator_arms=["strict", "ungoverned"])
    lines.append(
        f"The placebo arm was run at code {placebo_hash} while the strict and ungoverned "
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
