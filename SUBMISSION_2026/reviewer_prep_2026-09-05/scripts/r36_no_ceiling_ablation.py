"""R36 -- no-ceiling ablation: how much of the governed arm's basin-demand
envelope and Mead-elevation agreement with the traditional model comes
specifically from the `demand_ceiling_stabilizer` validator rule, as opposed
to the rest of strict governance? CPU-only (GPU busy -- this script stays
light; all data read from existing/landing CSVs, no LLM calls, no
`IrrigationEnvironment` replay).

BACKGROUND -- what "no_demand_ceiling" ablation means here, verified from
source (unlike r34/r35's placebo feature, this mechanism IS present in this
worktree, confirmed by reading it directly, not assumed):
  `examples/irrigation_abm/run_experiment.py` takes `--ablation-mode
  no_demand_ceiling` (argparse choices=["no_demand_ceiling"], symbol
  `examples/irrigation_abm/run_experiment.py (--ablation-mode)`). When
  set, it flips a module-level flag,
  `irr_validators.ENABLE_DEMAND_CEILING = False`, symbol
  `examples/irrigation_abm/validators/irrigation_validators.py
  (ENABLE_DEMAND_CEILING)`, which
  `examples/irrigation_abm/validators/irrigation_validators.py`'s
  `demand_ceiling_stabilizer` function, symbol
  `examples/irrigation_abm/validators/irrigation_validators.py
  (demand_ceiling_stabilizer)`, reads to decide whether
  to fire at all. This flag is NEVER written to
  `reproducibility_manifest.json` or `config_snapshot.yaml` by name --
  confirmed by reading `broker/core/experiment_runner.py::
  _collect_reproducibility_metadata` end to end, no `ablation` key anywhere
  in it. So there is no named manifest/config_snapshot field this script
  could "enforce" the way r33/r34/r35 enforce e.g. `retry_feedback_mode` --
  the task brief's "report what it is called" is answered here: it isn't
  called anything in either artifact. The two facts this script CAN and
  DOES verify instead: (1) the run's own `LAUNCH_COMMAND.txt` literally
  contains the substring `--ablation-mode no_demand_ceiling` (raises if
  missing once the run lands); (2) BEHAVIOURALLY, `demand_ceiling_
  stabilizer` never appears in the ablated run's `failed_rules` OR
  `rules_triggered` columns across every audit row (raises otherwise) --
  the stronger of the two checks, since it verifies the validator actually
  never fired, not just that the right flag was requested.

RUN LAYOUT
  Ablated -- LANDED both seeds: `examples/irrigation_abm/results/
  strict_noceiling_42yr_gemma3_4b_83fa97e1_seed{42,43}`. Seed 42 finished
  2026-09-22 21:30, seed 43 finished 2026-09-23 00:37 (each run dir's own
  `LAUNCH_COMMAND.txt` "Finished:" line); both `run_integrity.json` files
  read `integrity_ok: true`; a current run of this script reports zero
  `skipped` rows for the ablated arm. Reported via r35's own completeness
  gate (`r35_placebo_retry_irrigation.py::_irr_run_completeness`, imported
  not re-derived -- identical directory-existence / audit / simlog /
  run_integrity.json(integrity_ok==True) check).
  Comparators, ALREADY COMPLETE, same 2 seeds: `strict_42yr_gemma3_4b_
  faf1bb12_seed{42,43}` and `ungoverned_42yr_gemma3_4b_faf1bb12_seed{42,43}`
  (`R28._irr_run_dir`). Mead-KGE reference: `fql_raw_norebalance_faf1bb12`
  ("matched"), same seed, `R28._fql_run_dir("matched", seed)`.

PART 1 -- per (arm, seed): metrics + demand/ceiling stats + Mead KGE + rule census
  `_irr_llm_metrics()` (r25, imported) gives IBR headline, both EHE
  definitions, Mead min ft, shortage years, retry/rejection rate, fallback,
  wall hours -- same reused definitions r35 uses. Basin-demand mean and
  share of years above the ceiling: `R28._yearly_series(sim, "request",
  "sum")` (r28) + `DEMAND_CEILING_AF` (r29's own import, from
  `examples/irrigation_abm/validators/irrigation_validators.py`, = 6,000,000
  acre-ft) -- the exact pattern r29's `_part_b` uses, reproduced here per
  (arm, seed) rather than imported wholesale (r29's `_part_b` is a
  rows-appending Part function over ITS OWN fixed arm list, not a reusable
  per-run helper). Mead KGE vs FQL matched: `R28._yearly_series(sim,
  "lake_mead_level", "first")` for both the run and the same-seed FQL
  matched reference, `R28._kge_and_rmse()` -- byte-identical call sequence
  to `r28_trajectory_vs_traditional.py::_irr_part1`'s own per-(model, arm,
  seed) cell, just reproduced here in single-cell form (r28's `_irr_part1`
  is a whole-corpus rows-appending Part function over its own fixed
  IRR_MODELS/IRR_ARMS lists, likewise not a reusable per-run helper -- same
  situation as r29's `_part_b`). Rule census: r35's `_rule_id_census` (top
  6, retried rows). For the ablated arm specifically, an ADDITIONAL
  behavioural assertion scans EVERY row (not just retried ones) for
  `demand_ceiling_stabilizer` in `failed_rules` or `rules_triggered` --
  raises if found even once (see BACKGROUND). 2026-09-22 review fix: Part
  1 now also renders one plain sentence per seed, "IBR headline: ablated
  X, strict Y, ungoverned Z", straight from these same `run_metrics` rows
  -- no interpretation beyond stating the three values -- so a reader
  sees directly that coherence (IBR) did not collapse in the ablated arm
  even where Part 2/3's envelope verdict below says the physical Mead
  floor did.

PART 2 -- where the ablated arm sits between strict and ungoverned
  2026-09-22 review fix: the original two-metric version of this Part
  (Mead KGE vs FQL matched, basin-demand mean) answered a TRAJECTORY
  question -- does the ablated arm's water-level path still agree with the
  traditional model? -- but the audit's actual decision rule for this step
  (`out/paper_readiness_audit_2026-09-22.md`, "What the pending queue
  steps can change", step [2]) is an ENVELOPE question: does removing the
  demand-ceiling rule send the governed basin to the same Mead floor
  ("dead pool") as the ungoverned arm? That question is answered by Mead
  min (ft) and shortage years, not by Mead KGE. Averaging all four metrics
  into one number hid this: seed 42 alone prints "roughly midway (0.479)"
  from KGE (0.599) and demand mean (0.360) even though Mead min's own
  share is 1.000 -- the ablated arm's Mead min (895.0 ft) is IDENTICAL to
  ungoverned's (895.0 ft), not "midway" at all. Four metrics now, each
  tagged with a `level` column: level="envelope" for Mead min (ft),
  shortage years, and basin-demand mean (all describe the physical state
  of the governed water system); level="trajectory" for Mead KGE vs FQL
  matched (describes agreement with the traditional model's time path,
  a different question). share = (ablated-strict)/(ungoverned-strict) per
  seed, r34/r35's degenerate-denominator rule applied from the start.
  Thresholds set from the two ALREADY-COMPLETE comparators' own observed
  numbers (computed empirically below, not guessed -- the same faf1bb12
  strict/ungoverned runs r35 uses for irrigation, so the Mead-min and
  shortage-years numbers below are identical to r35's own docstring):
    Mead KGE vs FQL matched: strict 0.9484/0.9461, ungoverned 0.1224/0.4517
      (seed 42/43) -- line ~0.50-0.83 -- threshold 0.05
    Basin demand mean (acre-ft): strict 6,019,226/6,069,173, ungoverned
      11,909,071/11,957,962 -- line ~5.84M-5.94M -- threshold 100,000
      acre-ft (order of r29's own reported cross-seed SD for this arm,
      65,646 -- a difference smaller than one seed's own noise floor is
      not a meaningful "where it sits" signal)
    Mead min (ft): strict 997.0/995.7, ungoverned 895.0/895.0 -- line
      ~100-102 ft -- threshold 5.0 ft (r35's own threshold for the
      identical quantity)
    Shortage years: strict 13/15, ungoverned 39/37 -- line ~22-26 years --
      threshold 1.0 year (a count metric; sub-year differences are not
      meaningful -- r35's own threshold for the identical quantity)
  IBR headline and both EHE are reported descriptively in Part 1 only (see
  the new IBR-by-seed sentence there) -- they measure proposal-level
  coherence, not the physical envelope, so Part 2 does not fold them into
  the envelope/trajectory contrast.

PART 3 -- plain read
  2026-09-22 review fix, same root cause as the Part 2 fix above: replaced
  the single share averaged across all four heterogeneous metrics (which
  printed "roughly midway (0.479)" on seed 42 alone) with one templated
  sentence per metric -- share per seed, its own non-degenerate mean, and
  a label from r35's shared `_track_label()` (0.35/0.65 thresholds,
  "tracks STRICT" / "midway" / "tracks UNGOVERNED") -- envelope metrics
  first (Mead min, shortage years, basin-demand mean), trajectory metric
  (Mead KGE vs FQL matched) last. Then ONE gated closing sentence keyed on
  Mead min specifically, because that is exactly the audit's step [2]
  decision rule ("if removing the demand ceiling rule sends governed seeds
  to dead pool, the envelope is one institutional ceiling rule ... If the
  envelope survives without the ceiling, the claim generalises"): if Mead
  min's label is "tracks UNGOVERNED" (mean share > 0.65), a fixed sentence
  naming the dead-pool reading and pointing to Part 1 for coherence
  metrics; otherwise a fixed sentence naming the envelope-survives reading,
  followed by the bare label list for all four metrics. Nothing in this
  section is hard-coded -- every value is read from the same
  `contrast_pair` rows Part 2 wrote.

COMPLETENESS GATE
  Per (arm, seed): r35's `_irr_run_completeness` (dir exists -> audit
  exists -> simlog exists -> run_integrity.json integrity_ok==True).

OUTPUTS
  out/r36_no_ceiling_ablation.csv -- row_type in {skipped, run_metrics,
    rule_id_census, manifest_check, contrast_pair}.
  out/r36_no_ceiling_ablation.md -- GENERATED by render_md() directly from
    that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r36_no_ceiling_ablation.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r25_table1_regen as R25  # noqa: E402  READ-ONLY: _irr_llm_metrics.
import r28_trajectory_vs_traditional as R28  # noqa: E402  READ-ONLY: _irr_run_dir,
                                              # _fql_run_dir, _yearly_series, _kge_and_rmse.
import r29_kge_null_and_demand as R29  # noqa: E402  READ-ONLY: DEMAND_CEILING_AF.
import r35_placebo_retry_irrigation as R35  # noqa: E402  READ-ONLY: _irr_run_completeness,
                                             # _manifest_fields, _rule_id_census.

IRR_RESULTS = os.path.join(C.REPO, "examples", "irrigation_abm", "results")
SEEDS = ["42", "43"]
ARM_DIRS = {
    "ablated": lambda seed: R28._irr_run_dir("strict_noceiling", "gemma3_4b", "83fa97e1", seed),
    "strict": lambda seed: R28._irr_run_dir("strict", "gemma3_4b", "faf1bb12", seed),
    "ungoverned": lambda seed: R28._irr_run_dir("ungoverned", "gemma3_4b", "faf1bb12", seed),
}
ABLATED_RULE = "demand_ceiling_stabilizer"
TOP_N_RULES = 6


# =============================================================================
# Part 1
# =============================================================================
def _demand_stats(sim_path: str) -> dict:
    years, demand = R28._yearly_series(sim_path, "request", "sum")
    n = len(demand)
    n_over = sum(1 for v in demand if v > R29.DEMAND_CEILING_AF)
    return {"demand_mean": C.mean(demand), "demand_sd": C.sd(demand),
            "share_years_over_ceiling_pct": 100.0 * n_over / n}


def _mead_kge_vs_fql_matched(sim_path: str, seed: str) -> dict:
    years, mead = R28._yearly_series(sim_path, "lake_mead_level", "first")
    fql_dir = R28._fql_run_dir("matched", seed)
    fql_status, fql_reason = R28._run_completeness(fql_dir)
    if fql_status == "skipped":
        raise PrepError(f"FQL matched reference seed {seed} not available: {fql_reason}")
    fql_path = os.path.join(fql_dir, "simulation_log.csv")
    fyears, fmead = R28._yearly_series(fql_path, "lake_mead_level", "first")
    if fyears != years:
        raise PrepError(f"{sim_path} vs {fql_path}: year sets differ "
                         f"({years[:3]}..{years[-3:]} vs {fyears[:3]}..{fyears[-3:]})")
    return R28._kge_and_rmse(mead, fmead)


def _assert_ablated_rule_absent(aud: list, run_dir: str) -> int:
    """Scans EVERY audit row (not just retried ones) for ABLATED_RULE in
    either `failed_rules` or `rules_triggered`. Raises on the first hit --
    a disabled validator rule must never appear as having fired, in either
    column, not just 'usually' or 'in the retried subset'."""
    hits = 0
    for r in aud:
        for col in ("failed_rules", "rules_triggered"):
            raw = (r.get(col) or "").strip()
            if not raw:
                continue
            ids = set(x.strip() for x in raw.split("|") if x.strip())
            if ABLATED_RULE in ids:
                hits += 1
    if hits > 0:
        raise PrepError(f"{run_dir}: {ABLATED_RULE!r} appears {hits} time(s) in "
                         f"failed_rules/rules_triggered of the ABLATED arm -- the "
                         f"validator should never fire with ENABLE_DEMAND_CEILING=False")
    return hits


def _check_launch_command(run_dir: str) -> str:
    p = os.path.join(run_dir, "LAUNCH_COMMAND.txt")
    if not os.path.isfile(p):
        raise PrepError(f"missing LAUNCH_COMMAND.txt in {run_dir}")
    text = open(p, encoding="utf-8", errors="replace").read()
    needle = "--ablation-mode no_demand_ceiling"
    if needle not in text:
        raise PrepError(f"{run_dir}/LAUNCH_COMMAND.txt does not contain {needle!r} -- "
                         f"cannot confirm this run was actually launched with the ablation "
                         f"flag (the flag is not recorded anywhere else -- see BACKGROUND)")
    return needle


def _part1(rows: list) -> dict:
    per_run: dict = {}
    for arm, dir_fn in ARM_DIRS.items():
        for seed in SEEDS:
            run_dir = dir_fn(seed)
            status, reason = R35._irr_run_completeness(run_dir)
            if status == "skipped":
                print(f"  SKIPPED {arm} seed {seed}: {reason}")
                rows.append({"row_type": "skipped", "arm": arm, "seed": seed, "reason": reason})
                continue
            m = R25._irr_llm_metrics(run_dir)
            sim_path = os.path.join(run_dir, "simulation_log.csv")
            demand = _demand_stats(sim_path)
            kge_stats = _mead_kge_vs_fql_matched(sim_path, seed)
            aud = C.read_csv(os.path.join(run_dir, C.L.AUDIT_LOG))
            n = len(aud)
            retried = [r for r in aud if int(r.get("retry_count") or 0) > 0]

            ablated_rule_hits = None
            if arm == "ablated":
                ablated_rule_hits = _assert_ablated_rule_absent(aud, run_dir)
                launch_cmd_check = _check_launch_command(run_dir)
                print(f"  ABLATION CHECK {arm} seed {seed}: {ABLATED_RULE!r} hits=0 (verified "
                      f"over all {n} rows); LAUNCH_COMMAND.txt contains "
                      f"'--ablation-mode no_demand_ceiling'")

            row = {"row_type": "run_metrics", "arm": arm, "seed": seed, "n_rows": n,
                   "ibr_headline": m["ibr_headline"], "ehe_pooled": m["ehe_pooled"],
                   "ehe_pooled_proposal": m["ehe_pooled_proposal"],
                   "mead_min_ft": m["mead_min_ft"], "shortage_years": m["shortage_years"],
                   "rejection_rate_pct": m["rejection_rate_pct"],
                   "retry_rate_pct": m["retry_rate_pct"], "n_retried": len(retried),
                   "fallback_pct": m["fallback_pct"], "llm_fail_n": int(m["llm_fail_n"]),
                   "wall_hours": m["wall_hours"],
                   "demand_mean": demand["demand_mean"], "demand_sd": demand["demand_sd"],
                   "share_years_over_ceiling_pct": demand["share_years_over_ceiling_pct"],
                   "mead_kge_vs_fql_matched": kge_stats["kge"],
                   "mead_rmse_vs_fql_matched": kge_stats["rmse"],
                   "ablated_rule_hits": ablated_rule_hits}
            rows.append(row)

            census = R35._rule_id_census(aud, TOP_N_RULES)
            for rank, (rule_id, count) in enumerate(census, start=1):
                rows.append({"row_type": "rule_id_census", "arm": arm, "seed": seed,
                             "rank": rank, "rule_id": rule_id, "count": count})
            print(f"  OK {arm:10s} seed {seed}: rows={n} IBR={m['ibr_headline']:.2f}% "
                  f"demand_mean={demand['demand_mean']:,.0f} "
                  f"KGE_vs_fql_matched={kge_stats['kge']:.4f} "
                  f"top_rule={census[0] if census else None}")

            manifest = R35._manifest_fields(run_dir)
            model = manifest.get("model")
            git_commit = manifest.get("git_commit")
            thinking_mode = manifest.get("thinking_mode")
            enforced = arm == "ablated"
            if enforced:
                if model != "gemma3:4b":
                    raise PrepError(f"{run_dir}: model={model!r}, expected 'gemma3:4b'")
                if not str(git_commit or "").startswith("83fa97e1"):
                    raise PrepError(f"{run_dir}: git_commit={git_commit!r}, expected to "
                                     f"start with '83fa97e1'")
            rows.append({"row_type": "manifest_check", "arm": arm, "seed": seed, "model": model,
                         "git_commit_short": (git_commit or "")[:8],
                         "thinking_mode": thinking_mode,
                         "launch_command_ablation_flag_present": (arm == "ablated"),
                         "ablated_rule_hits": ablated_rule_hits, "enforced": enforced})

            per_run[(arm, seed)] = row
    return per_run


# =============================================================================
# Part 2
# =============================================================================
# 2026-09-22 review fix: envelope metrics (does the basin physically reach
# dead pool without the ceiling rule -- the audit's actual step [2] decision
# rule) listed first, trajectory metric (agreement with the traditional
# model's Mead path -- a different question) last. METRIC_LEVEL below labels
# each for Part 2's table and Part 3's per-metric sentence order.
METRIC_KEYS = {
    "Mead min (ft)": "mead_min_ft",
    "Shortage years": "shortage_years",
    "Basin demand mean (acre-ft)": "demand_mean",
    "Mead KGE vs FQL matched": "mead_kge_vs_fql_matched",
}
# Empirically set from the two already-complete comparators (exact per-seed
# numbers in the docstring above, computed via the same _mead_kge_vs_fql_
# matched / _demand_stats calls this script uses everywhere else, or --
# for Mead min / shortage years -- identical to r35's own thresholds for
# the same faf1bb12 strict/ungoverned comparators).
DEGENERATE_THRESHOLD = {
    "Mead min (ft)": 5.0,                       # feet -- r35's own threshold, same quantity
    "Shortage years": 1.0,                      # a count metric; sub-year differences are
                                                 # not meaningful -- r35's own threshold
    "Basin demand mean (acre-ft)": 100_000.0,   # acre-ft; ~ r29's own cross-seed SD for
                                                 # this arm (65,646) -- a difference below
                                                 # one seed's own noise floor is not a
                                                 # meaningful "where it sits" signal
    "Mead KGE vs FQL matched": 0.05,
}
METRIC_LEVEL = {
    "Mead min (ft)": "envelope",
    "Shortage years": "envelope",
    "Basin demand mean (acre-ft)": "envelope",
    "Mead KGE vs FQL matched": "trajectory",
}


def _part2(rows: list, per_run: dict) -> None:
    for metric_label, key in METRIC_KEYS.items():
        threshold = DEGENERATE_THRESHOLD[metric_label]
        level = METRIC_LEVEL[metric_label]
        for seed in SEEDS:
            a = per_run.get(("ablated", seed))
            s = per_run.get(("strict", seed))
            u = per_run.get(("ungoverned", seed))
            if a is None or s is None or u is None:
                missing = [n for n, v in (("ablated", a), ("strict", s), ("ungoverned", u))
                           if v is None]
                print(f"  Part 2 PENDING: {metric_label} seed {seed} -- missing arm(s) "
                      f"{missing}")
                rows.append({"row_type": "skipped", "section": "contrast_pair",
                             "metric": metric_label, "seed": seed,
                             "reason": f"missing arm(s): {missing}"})
                continue
            av, sv, uv = float(a[key]), float(s[key]), float(u[key])
            diff_a_minus_s = av - sv
            diff_a_minus_u = av - uv
            denom = uv - sv
            denom_abs = abs(denom)
            degenerate = denom_abs < threshold
            share = (av - sv) / denom if denom != 0 else float("nan")
            rows.append({"row_type": "contrast_pair", "metric": metric_label, "seed": seed,
                         "level": level,
                         "ablated_value": av, "strict_value": sv, "ungoverned_value": uv,
                         "diff_ablated_minus_strict": diff_a_minus_s,
                         "diff_ablated_minus_ungoverned": diff_a_minus_u,
                         "share_on_strict_to_ungoverned_line": share,
                         "denom_abs": denom_abs, "degenerate_threshold": threshold,
                         "degenerate": degenerate})
            if degenerate:
                print(f"  DEGENERATE share: {metric_label} seed {seed} -- "
                      f"|ungoverned-strict|={denom_abs:.4f} < threshold {threshold} -- "
                      f"share={share:.4f} computed and stored, excluded from the verdict")


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "arm", "seed", "n_rows", "ibr_headline", "ehe_pooled",
    "ehe_pooled_proposal", "mead_min_ft", "shortage_years", "rejection_rate_pct",
    "retry_rate_pct", "n_retried", "fallback_pct", "llm_fail_n", "wall_hours", "demand_mean",
    "demand_sd", "share_years_over_ceiling_pct", "mead_kge_vs_fql_matched",
    "mead_rmse_vs_fql_matched", "ablated_rule_hits", "rank", "rule_id", "count", "model",
    "git_commit_short", "thinking_mode", "launch_command_ablation_flag_present", "enforced",
    "metric", "level", "ablated_value", "strict_value", "ungoverned_value",
    "diff_ablated_minus_strict", "diff_ablated_minus_ungoverned",
    "share_on_strict_to_ungoverned_line", "denom_abs", "degenerate_threshold", "degenerate",
    "reason",
]


def main() -> int:
    C.banner("R36  No-ceiling ablation: is the Mead/demand envelope bought by one rule?")
    rows: list = []

    print("\n-- Part 1: per (arm, seed) metrics, demand/ceiling stats, Mead KGE, rule census --")
    per_run = _part1(rows)

    print("\n-- Part 2: where the ablated arm sits between strict and ungoverned --")
    _part2(rows, per_run)

    md_text = render_md(rows)

    csv_final = "r36_no_ceiling_ablation.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, "r36_no_ceiling_ablation.md")
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
def _cp(x) -> float:
    return float(C.fmt(x))


def _find(rows, row_type, **kw):
    out = []
    for r in rows:
        if r.get("row_type") != row_type:
            continue
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


def _is_nan(x) -> bool:
    return isinstance(x, float) and x != x


# 2026-09-22: same 0.35/0.65 classification r35_placebo_retry_irrigation.py's
# `_track_label` uses -- re-declared here (r35 does not export it as a
# module-level name meant for reuse), byte-identical thresholds so the two
# scripts' "tracks STRICT" / "midway" / "tracks UNGOVERNED" language cannot
# disagree.
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
    recomputed."""
    recs = _find(rows, "contrast_pair", metric=metric_label)
    ok = [r for r in recs if not r["degenerate"]]
    mean_share = (sum(float(r["share_on_strict_to_ungoverned_line"]) for r in ok) / len(ok)
                  if ok else float("nan"))
    return mean_share, _track_label(mean_share)


def _share_cells(rows: list, metric_label: str) -> list:
    """[cell_str_per_seed] for one metric -- 'PENDING' if that seed's
    contrast_pair row does not exist yet, 'degenerate' if it does but is
    excluded, else the formatted share. Factored out of
    `_metric_plain_sentence` so the Method section's saturation-explanation
    sentences (2026-09-23) can reuse the identical per-seed lookup rather
    than re-deriving it."""
    cells = []
    for seed in SEEDS:
        recs = _find(rows, "contrast_pair", metric=metric_label, seed=seed)
        if not recs:
            cells.append("PENDING")
        elif recs[0]["degenerate"]:
            cells.append("degenerate")
        else:
            cells.append(f"{_cp(recs[0]['share_on_strict_to_ungoverned_line']):.3f}")
    return cells


def _metric_plain_sentence(rows: list, metric_label: str) -> tuple:
    """One templated sentence for a metric: share per seed (or 'degenerate'
    / 'PENDING'), its own non-degenerate mean, and its `_track_label`.
    Returns (sentence, label) -- the label feeds the gated closing sentence
    below."""
    seed_cells = _share_cells(rows, metric_label)
    mean_share, label = _metric_mean_and_label(rows, metric_label)
    mean_cell = "n.a." if _is_nan(mean_share) else f"{_cp(mean_share):.3f}"
    level = METRIC_LEVEL[metric_label]
    sentence = (f"{metric_label} ({level} level): share {seed_cells[0]} / {seed_cells[1]} "
                f"(seed 42 / seed 43), mean {mean_cell}: {label}.")
    return sentence, label


def _dead_pool_floor_ft(rows: list) -> str:
    """The dead-pool floor Mead min saturates at, read from the ungoverned
    arm's own `mead_min_ft` run_metrics rows -- never hard-coded. Renders
    a single value when both seeds agree (as observed), else both values
    separated by ' / '."""
    vals = sorted({_cp(r["mead_min_ft"]) for r in _find(rows, "run_metrics", arm="ungoverned")})
    if not vals:
        return "n.a. (no ungoverned run_metrics rows yet)"
    if len(vals) == 1:
        return f"{vals[0]:.1f}"
    return " / ".join(f"{v:.1f}" for v in vals)


# 2026-09-23 review fix: re-declared from r35_placebo_retry_irrigation.py's
# `_manifest_commit_hashes` (r35 does not export it as a module-level name
# meant for reuse), byte-identical logic, param names generalised from
# r35's `placebo_arms` to `treatment_arms` since r36's manipulated arm is
# called "ablated", not "placebo".
def _manifest_commit_hashes(rows: list, treatment_arms: list, comparator_arms: list) -> tuple:
    """(treatment_hash, comparator_hash), pulled from `manifest_check`
    rows' `git_commit_short` -- never hard-coded, so the Method-section
    provenance caveat cannot drift from the actual run. Raises if the
    arm(s) have no manifest rows yet, or if git_commit_short disagrees
    within an arm (across seeds) or between the comparator arms -- a
    disagreement there would mean the provenance claim itself is false,
    never something to paper over."""
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
    return _one(treatment_arms), _one(comparator_arms)


def render_md(rows: list) -> str:
    lines = []
    lines.append("# R36 -- no-ceiling ablation: is the Mead/demand envelope bought by one rule?")
    lines.append("")
    lines.append("Source: `r36_no_ceiling_ablation.py`. Every number below is read live from "
                 "the `rows` list this script writes to the paired CSV. n=2 seeds (42, 43) "
                 "throughout -- no t-test anywhere in this file.")
    lines.append("")

    lines.append("## Part 1 -- per (arm, seed) metrics")
    lines.append("")
    lines.append("| arm | seed | n_rows | IBR headline | EHE exec | EHE prop | Mead min ft | "
                 "shortage yrs | demand mean (acre-ft) | % yrs over ceiling | "
                 "Mead KGE vs FQL matched | retry rate % | fallback % |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for arm in ("ablated", "strict", "ungoverned"):
        for seed in SEEDS:
            recs = _find(rows, "run_metrics", arm=arm, seed=seed)
            if not recs:
                lines.append(f"| {arm} | {seed} | PENDING | -- | -- | -- | -- | -- | -- | -- | "
                             f"-- | -- | -- |")
                continue
            r = recs[0]
            lines.append(
                f"| {arm} | {seed} | {r['n_rows']} | {_cp(r['ibr_headline']):.2f} | "
                f"{_cp(r['ehe_pooled']):.3f} | {_cp(r['ehe_pooled_proposal']):.3f} | "
                f"{_cp(r['mead_min_ft']):.1f} | {int(r['shortage_years'])} | "
                f"{_cp(r['demand_mean']):,.0f} | {_cp(r['share_years_over_ceiling_pct']):.2f} | "
                f"{_cp(r['mead_kge_vs_fql_matched']):.4f} | {_cp(r['retry_rate_pct']):.2f} | "
                f"{_cp(r['fallback_pct']):.2f} |"
            )
    lines.append("")

    lines.append("IBR headline by seed (ablated vs strict vs ungoverned, no interpretation "
                 "beyond stating the three values):")
    lines.append("")
    for seed in SEEDS:
        a = _find(rows, "run_metrics", arm="ablated", seed=seed)
        s = _find(rows, "run_metrics", arm="strict", seed=seed)
        u = _find(rows, "run_metrics", arm="ungoverned", seed=seed)
        a_v = f"{_cp(a[0]['ibr_headline']):.2f}" if a else "PENDING"
        s_v = f"{_cp(s[0]['ibr_headline']):.2f}" if s else "PENDING"
        u_v = f"{_cp(u[0]['ibr_headline']):.2f}" if u else "PENDING"
        lines.append(f"- seed {seed}: IBR headline: ablated {a_v}, strict {s_v}, "
                     f"ungoverned {u_v}.")
    lines.append("")

    lines.append("### Ablation check (ablated arm only): does `demand_ceiling_stabilizer` "
                 "ever fire?")
    lines.append("")
    lines.append("| arm | seed | rule hits (failed_rules or rules_triggered, all rows) | "
                 "LAUNCH_COMMAND.txt has `--ablation-mode no_demand_ceiling` |")
    lines.append("|---|---|---|---|")
    for seed in SEEDS:
        recs = _find(rows, "manifest_check", arm="ablated", seed=seed)
        if not recs:
            lines.append(f"| ablated | {seed} | pending | pending |")
            continue
        r = recs[0]
        lines.append(f"| ablated | {seed} | {r['ablated_rule_hits']} | "
                     f"{r['launch_command_ablation_flag_present']} |")
    lines.append("")

    lines.append("### Rule-id census, top 6 among retried rows")
    lines.append("")
    lines.append("| arm | seed | rank | rule_id | count |")
    lines.append("|---|---|---|---|---|")
    for arm in ("ablated", "strict", "ungoverned"):
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
                 "enforced (model/commit) |")
    lines.append("|---|---|---|---|---|---|")
    for arm in ("ablated", "strict", "ungoverned"):
        for seed in SEEDS:
            recs = _find(rows, "manifest_check", arm=arm, seed=seed)
            if not recs:
                lines.append(f"| {arm} | {seed} | pending | -- | -- | -- |")
                continue
            r = recs[0]
            lines.append(f"| {arm} | {seed} | {r['model']} | {r['git_commit_short']}... | "
                         f"{r['thinking_mode']} | {r['enforced']} |")
    lines.append("")

    lines.append("## Part 2 -- where the ablated arm sits between strict and ungoverned")
    lines.append("")
    lines.append("level=envelope (Mead min, shortage years, basin-demand mean) asks whether "
                 "the governed basin physically reaches the same state as ungoverned without "
                 "the ceiling rule; level=trajectory (Mead KGE vs FQL matched) asks whether "
                 "the ablated arm's water-level path still agrees with the traditional model "
                 "-- a different question. Envelope metrics listed first.")
    lines.append("")
    lines.append("| metric | level | seed | ablated | strict | ungoverned | ablated-strict | "
                 "ablated-ungoverned | share on strict->ungoverned line |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for metric_label in METRIC_KEYS:
        level = METRIC_LEVEL[metric_label]
        for seed in SEEDS:
            recs = _find(rows, "contrast_pair", metric=metric_label, seed=seed)
            if not recs:
                pend = _find(rows, "skipped", section="contrast_pair", metric=metric_label,
                              seed=seed)
                reason = pend[0]["reason"] if pend else "no data"
                lines.append(f"| {metric_label} | {level} | {seed} | -- | -- | -- | -- | -- | "
                             f"PENDING ({reason}) |")
                continue
            r = recs[0]
            if r["degenerate"]:
                share_cell = (f"n.a. (denominator |ungoverned-strict| = "
                              f"{_cp(r['denom_abs']):,.4f} < threshold "
                              f"{r['degenerate_threshold']:g})")
            else:
                share_cell = f"{_cp(r['share_on_strict_to_ungoverned_line']):.3f}"
            lines.append(
                f"| {metric_label} | {level} | {seed} | {_cp(r['ablated_value']):,.4f} | "
                f"{_cp(r['strict_value']):,.4f} | {_cp(r['ungoverned_value']):,.4f} | "
                f"{_cp(r['diff_ablated_minus_strict']):,.4f} | "
                f"{_cp(r['diff_ablated_minus_ungoverned']):,.4f} | "
                f"{share_cell} |"
            )
    lines.append("")

    lines.append("## Plain read")
    lines.append("")
    sentences = []
    ablated_seeds_landed = sorted({r["seed"] for r in _find(rows, "run_metrics", arm="ablated")})
    if not ablated_seeds_landed:
        comparators_ready = bool(_find(rows, "run_metrics", arm="strict")) and \
            bool(_find(rows, "run_metrics", arm="ungoverned"))
        sentences.append(
            "The no-ceiling ablation run (strict_noceiling_42yr_gemma3_4b_83fa97e1) has not "
            "landed yet -- 0/2 seeds, and neither seed's run directory exists on disk yet. "
            "Comparators (strict, ungoverned, both faf1bb12) are "
            f"{'already complete' if comparators_ready else 'also incomplete'} and reported "
            f"in Part 1 above; Part 2's ablated-vs-comparator contrasts will populate "
            f"automatically, no code change needed, once the ablation run lands."
        )
    elif len(ablated_seeds_landed) < len(SEEDS):
        missing = [s for s in SEEDS if s not in ablated_seeds_landed]
        sentences.append(
            f"The ablation run has landed for seed(s) {', '.join(ablated_seeds_landed)} but "
            f"not yet for seed(s) {', '.join(missing)} -- Part 2's paired contrasts need both "
            f"seeds and stay PENDING until the second one lands."
        )
    ablated_metrics_rows = _find(rows, "run_metrics", arm="ablated")
    if ablated_metrics_rows:
        hits_total = sum(int(r["ablated_rule_hits"] or 0) for r in ablated_metrics_rows)
        sentences.append(
            f"`demand_ceiling_stabilizer` fired 0 times across all landed seeds of the "
            f"ablated run (verified over every audit row's `failed_rules` and "
            f"`rules_triggered`, total hits={hits_total}), and every landed seed's "
            f"LAUNCH_COMMAND.txt confirms `--ablation-mode no_demand_ceiling` was passed -- "
            f"the manipulation is behaviourally clean even though neither field is recorded "
            f"in the manifest by name."
        )
    # 2026-09-22 review fix: one templated sentence per metric (envelope
    # metrics first, trajectory last) instead of a single share averaged
    # across all four heterogeneous metrics -- the averaged version printed
    # "roughly midway (0.479)" on seed 42 alone even though Mead min's own
    # share is 1.000 (895.0 ft ablated == 895.0 ft ungoverned). Each
    # sentence is self-contained (share per seed, its own non-degenerate
    # mean, `_track_label`) -- no share value is recomputed here, only the
    # same contrast_pair rows Part 2 wrote are read back.
    shares = _find(rows, "contrast_pair")
    metric_order = [m for m in METRIC_KEYS if METRIC_LEVEL[m] == "envelope"] + \
                   [m for m in METRIC_KEYS if METRIC_LEVEL[m] == "trajectory"]
    metric_labels = {}
    if shares:
        for metric_label in metric_order:
            sentence, label = _metric_plain_sentence(rows, metric_label)
            metric_labels[metric_label] = label
            sentences.append(sentence)

        # Gated closing sentence, keyed on Mead min specifically -- this IS
        # the audit's step [2] decision rule ("if removing the demand
        # ceiling rule sends governed seeds to dead pool, the envelope is
        # one institutional ceiling rule ... If the envelope survives
        # without the ceiling, the claim generalises",
        # out/paper_readiness_audit_2026-09-22.md).
        mead_min_label = metric_labels.get("Mead min (ft)")
        if mead_min_label == "tracks UNGOVERNED":
            sentences.append(
                "Removing only the demand-ceiling rule lets the governed basin fall to the "
                "same Mead floor as the ungoverned arm: the water-system envelope in the "
                "strict arm is this one institutional rule, not governance in general. "
                "Coherence metrics (IBR headline) are reported in Part 1 and are not part "
                "of this verdict."
            )
        else:
            sentences.append(
                "Removing the demand-ceiling rule does not send the governed basin to the "
                "ungoverned Mead floor: the envelope survives without the ceiling rule."
            )
            label_list = "; ".join(f"{m}: {metric_labels[m]}" for m in metric_order)
            sentences.append(label_list + ".")
    else:
        sentences.append(
            "No contrast_pair rows are available yet to report the envelope/trajectory "
            "verdict."
        )
    sentences.append(
        "This whole comparison is n=2 seeds (42, 43) -- no significance test is computed "
        "anywhere in this script; the per-seed numbers are reported directly, and any "
        "conclusion here should be read as suggestive, not statistically established."
    )
    for s in sentences:
        lines.append(s)
        lines.append("")

    lines.append("## Method")
    lines.append("")
    lines.append(
        "IBR headline and both EHE definitions are `r25_table1_regen.py::_irr_llm_metrics()`; "
        "Mead min ft and shortage years come from the same call. Basin-demand mean/share-"
        "over-ceiling use `r28_trajectory_vs_traditional.py::_yearly_series()` on the "
        "`request` column plus `DEMAND_CEILING_AF` imported (via r29) from `examples/"
        "irrigation_abm/validators/irrigation_validators.py` (6,000,000 acre-ft). Mead KGE "
        "vs FQL matched uses the same `_yearly_series()` on `lake_mead_level` for both the "
        "run and the same-seed `fql_raw_norebalance_faf1bb12` reference, then "
        "`_kge_and_rmse()` -- the identical Gupta et al. (2009) original-formulation KGE "
        "every other script in this package uses. The ablation itself (`--ablation-mode "
        "no_demand_ceiling`, `examples/irrigation_abm/run_experiment.py`) flips a "
        "module-level flag in `irr_validators` and is NOT recorded in either "
        "`reproducibility_manifest.json` or `config_snapshot.yaml` by name (verified by "
        "reading `broker/core/experiment_runner.py::_collect_reproducibility_metadata` end "
        "to end) -- this script instead verifies the ablation behaviourally, asserting "
        "`demand_ceiling_stabilizer` appears zero times in `failed_rules`/`rules_triggered` "
        "across every row of the ablated run, and textually, checking LAUNCH_COMMAND.txt for "
        "the literal flag string; either check failing raises rather than silently reporting "
        "unverified numbers. share_on_strict_to_ungoverned_line = (ablated-strict)/"
        "(ungoverned-strict): 0 = ablated behaves like strict, 1 = ablated behaves like "
        "ungoverned; a cell is marked degenerate (excluded from the Part 3 verdict, never "
        "hidden from the Part 2 table) when |ungoverned-strict| falls below a per-metric "
        "threshold set from the comparators' own observed line length -- the same rule "
        "r34/r35 established for flood/irrigation placebo, applied here from the start. "
        "2026-09-22: METRIC_LEVEL labels Mead min (ft), shortage years, and basin-demand "
        "mean as level=envelope (the physical state of the governed water system -- the "
        "audit's own step [2] decision rule is stated in these terms, "
        "`out/paper_readiness_audit_2026-09-22.md`) and Mead KGE vs FQL matched as "
        "level=trajectory (agreement with the traditional model's time path, a different "
        "question); Mead min ft and shortage years reuse r35_placebo_retry_irrigation.py's "
        "own thresholds (5.0 ft, 1.0 year) for the identical quantity on the identical "
        "faf1bb12 strict/ungoverned comparator runs. Part 3's per-metric sentences and "
        "gated closing sentence use `_track_label()`, the same 0.35/0.65 thresholds "
        "r35_placebo_retry_irrigation.py's own `_track_label` uses -- re-declared here, "
        "not imported, since r35 does not export it as a module-level name meant for "
        "reuse, but byte-identical, so the two scripts' STRICT/midway/UNGOVERNED language "
        "cannot disagree."
    )
    lines.append("")

    # 2026-09-23 review fix: two sentences explaining why the envelope metrics
    # disagree with each other (Mead min tracks UNGOVERNED while basin-demand
    # mean sits midway) -- every number rendered from the same rows the
    # tables above use, none hard-coded, including the 895 ft floor itself
    # (read from the ungoverned arm's own Mead min, not assumed).
    floor_ft = _dead_pool_floor_ft(rows)
    mead_min_cells = _share_cells(rows, "Mead min (ft)")
    demand_cells = _share_cells(rows, "Basin demand mean (acre-ft)")
    shortage_cells = _share_cells(rows, "Shortage years")
    mead_min_mean, _ = _metric_mean_and_label(rows, "Mead min (ft)")
    demand_mean, _ = _metric_mean_and_label(rows, "Basin demand mean (acre-ft)")
    shortage_mean, _ = _metric_mean_and_label(rows, "Shortage years")
    mead_min_mean_cell = "n.a." if _is_nan(mead_min_mean) else f"{_cp(mead_min_mean):.3f}"
    demand_mean_cell = "n.a." if _is_nan(demand_mean) else f"{_cp(demand_mean):.3f}"
    shortage_mean_cell = "n.a." if _is_nan(shortage_mean) else f"{_cp(shortage_mean):.3f}"
    lines.append(
        f"Mead min saturates at the {floor_ft} ft dead-pool floor (read from the "
        f"ungoverned arm's own Mead min above, not assumed): once sustained basin demand "
        f"exceeds available supply for long enough, elevation cannot fall further, so any "
        f"arm whose demand overshoots supply for long enough settles at that identical "
        f"floor regardless of how far demand overshoots it -- this is why the ablated "
        f"arm's Mead-min share is {mead_min_cells[0]} / {mead_min_cells[1]} (seed 42 / "
        f"seed 43, mean {mead_min_mean_cell}) even though its own basin-demand mean sits "
        f"only {demand_cells[0]} / {demand_cells[1]} (mean {demand_mean_cell}) of the way "
        f"from strict to ungoverned; basin-demand mean does not saturate the same way."
    )
    lines.append("")
    lines.append(
        f"Shortage years saturate less than Mead min but still track UNGOVERNED (share "
        f"{shortage_cells[0]} / {shortage_cells[1]}, mean {shortage_mean_cell}), so the "
        f"dead-pool reading in the Plain read section above does not rest on Mead min "
        f"alone."
    )
    lines.append("")

    # 2026-09-23 review fix: same code-provenance caveat r34/r35 render, at the end
    # of Method, pulled live from this run's own manifest_check rows (never
    # hard-coded) so it cannot drift from what actually ran.
    ablated_hash, comparator_hash = _manifest_commit_hashes(
        rows, treatment_arms=["ablated"], comparator_arms=["strict", "ungoverned"])
    lines.append(
        f"The ablated arm was run at code {ablated_hash} while the strict and ungoverned "
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
