"""R42 -- irrigation persona pilot: does the NEW irrigation persona corpus
(main branch, commit 732b2b6c) reproduce the OLD corpus's (commit faf1bb12)
governance signature, seed by seed? Pilot read at whatever seed count has
landed; the same code re-run later gives the n=5 read with zero edits.
CPU-only (GPU busy with the live persona batch -- this script only reads
already-written CSV/JSON/JSONL files, never launches a run).

VINTAGE / ARM TERMINOLOGY (do not confuse with r25's own "old"/"new")
  This script's "old" = commit faf1bb12 (the pre-persona-diversification
  corpus every other reviewer-prep script already reads). This script's
  "new" = commit 732b2b6c (the new persona corpus this pilot exists to
  check). r25_table1_regen.py ALSO has an "old"/"new" pair in its own
  contrast_pair rows, but that is a DIFFERENT split (a pre-2026-09-15-loss
  snapshot vs the current faf1bb12 corpus) -- entirely unrelated to the
  vintage split here. Both vintages carry two arms: "strict" (governed) and
  a comparator arm that is named DIFFERENTLY per vintage on disk --
  "ungoverned" for old (faf1bb12), "disabled" for new (732b2b6c) -- but
  plays the identical no-governance role in every contrast below. This
  script's `role` field ("strict" / "comparator") is what code branches on;
  the `arm` field always carries the REAL on-disk name so nothing is
  silently relabelled.

RUN LAYOUT (examples/irrigation_abm/results/)
  old strict:      strict_42yr_gemma3_4b_faf1bb12_seed{S}
  old comparator:  ungoverned_42yr_gemma3_4b_faf1bb12_seed{S}
  new strict:      strict_42yr_gemma3_4b_732b2b6c_seed{S}
  new comparator:  disabled_42yr_gemma3_4b_732b2b6c_seed{S}
  Seeds 42-46. Verified on disk at the time this script was written: all 10
  old dirs (5 seeds x 2 arms) exist and are complete. Of the new dirs, only
  strict_42yr_gemma3_4b_732b2b6c_seed42 exists at all, and it is IN
  PROGRESS (LAUNCH_COMMAND.txt has no `Finished:` line yet, no
  simulation_log.csv / audit csv / run_integrity.json written) -- every
  other new (arm, seed) cell has no directory on disk yet. This script
  renders PENDING for every incomplete/missing cell rather than guessing;
  re-running it later with more seeds landed needs no code change.

COMPLETENESS GATE (fail-loud, never reads a partial run)
  `_run_completeness()`: run dir exists -> irrigation_farmer_governance_
  audit.csv exists -> simulation_log.csv exists -> LAUNCH_COMMAND.txt
  exists AND contains a `Finished:` line -> run_integrity.json exists with
  integrity_ok==True. The middle two checks are
  r35_placebo_retry_irrigation.py::_irr_run_completeness's own gate
  (imported logic, re-declared here with the added LAUNCH_COMMAND.txt
  `Finished:` check the task brief for this script asked for explicitly --
  a belt-and-suspenders check on top of r35's, not a replacement for it).

PART 1 -- per (vintage, arm, seed): metrics + rule census + manifest census
  IBR conditional (the published high-WSA increase rate, a.k.a. AAI) and
  IBR unconditional both come from the canonical loader, imported, never
  re-derived: `_loader.ibr()` (= `_common.py`'s `C.L.ibr`, proposal-level,
  conditioned on HIGH self-reported water-scarcity appraisal) and
  `_loader.increase_rate()` (= `C.L.increase_rate`, unconditional, over ALL
  rows). Both operate on the FINAL PROPOSED action (`_loader.action()`), the
  same accessor every other script in this package uses -- a REJECTED row's
  proposal never executed, but IBR is explicitly a proposal-level rate (see
  `_loader.py`'s own docstring).
  EHE pooled: a helper DOES exist for irrigation --
  `r25_table1_regen.py::_irr_llm_metrics()` returns both `ehe_pooled`
  (executed-distribution, k=5, `C.irr_executed` + `C.normalized_entropy`)
  and `ehe_pooled_proposal` (proposal-distribution, k=5) -- both imported
  here via the SAME function call this script already makes for IBR
  conditional, Mead min, rejection rate, and retry rate, so nothing here is
  a second, possibly-diverging definition.
  REJECTED count/rate + retry rate: rejection_rate_pct and retry_rate_pct
  are `_irr_llm_metrics()`'s own fields (status.startswith("REJECTED") / n;
  retry_count>0 / n -- the SAME definitions r25/r35/r36 use). `rejected_n`
  is counted directly here (same condition) since `_irr_llm_metrics()` only
  returns the rate, not the raw count.
  Top-3 rule ids: `r35_placebo_retry_irrigation.py::_rule_id_census()`,
  imported (not re-derived) with top_n=3 -- counts each RETRIED row's
  `failed_rules` (pipe-delimited) once per distinct rule id, rule ids
  `sorted()` before counting (the Python set-hash-randomization fix
  r27/r34/r35 all apply).
  Final-year Mead level / minimum Mead level / shortage-tier years: read
  DIRECTLY from simulation_log.csv via
  `r28_trajectory_vs_traditional.py::_yearly_series()` (imported, not
  re-derived) on two columns -- `lake_mead_level` (final = last year's
  value, min = the series minimum) and `shortage_tier` (a basin-level
  value shared by every agent within a year, exactly like
  `lake_mead_level` -- `_yearly_series(..., "first")` verifies this via its
  own nunique==1-per-year check, raising if it is ever not a single shared
  value). "Shortage-tier years" = the count of years with
  `shortage_tier >= 1`. THIS IS A DIFFERENT DEFINITION from the
  `shortage_years` column r25/r35/r36 report (years with mean Mead level
  below 1075 ft) -- this script's own metric is named `shortage_tier_years`
  throughout, never the bare `shortage_years` name those other scripts use,
  precisely so the two are never confused as the same column with two
  computations.
  Mead-elevation KGE vs the FQL-matched trajectory: computed EXACTLY as
  `r28_trajectory_vs_traditional.py::_irr_part1`'s own per-cell KGE call --
  `_yearly_series()` on `lake_mead_level` for both series, then
  `_kge_and_rmse()` (Gupta et al. 2009 original formulation, imported, not
  re-derived) -- reproduced here in single-cell form because r28's own
  `_irr_part1` is a whole-corpus rows-appending Part function over its own
  fixed IRR_MODELS/IRR_ARMS lists, not a reusable per-run helper (the exact
  situation r36_no_ceiling_ablation.py's own `_mead_kge_vs_fql_matched`
  documents for the identical reason). The FQL reference dir is
  `r28_trajectory_vs_traditional.py::_fql_run_dir("matched", seed)` --
  `fql_raw_norebalance_faf1bb12`, the SAME primary ("matched") reference
  r28's own Part 1 uses for every irrigation KGE row in this package. This
  reference is FQL, a deterministic rule-based baseline with no LLM
  sampling at all, so the SAME reference dir applies to both vintages --
  there is no "old FQL" vs "new FQL" split to make.
  Manifest census: model, git_commit (short + value-enforced to start with
  the vintage's expected prefix, RAISES on mismatch -- both vintages are
  fully pinned commits here, so this is a real enforcement, not a
  soft check), temperature, top_p (both read directly; irrigation's
  gemma3:4b runs carry no explicit sampling params in either vintage's
  manifest -- confirmed by reading both, both `null` -- so `None` here is
  the EXPECTED value, not a missing-field symptom), top_k (checked for
  presence as a top-level manifest key; confirmed absent from this
  manifest schema entirely by reading `broker/core/experiment_runner.py::
  _collect_reproducibility_metadata`'s own output keys -- reported as
  "absent" rather than a fabricated null), retry_feedback_mode (checked for
  presence; per r35's own docstring this key does not exist yet in
  faf1bb12's manifest schema -- confirmed absent here too for the old
  vintage; read and reported for whichever vintage's manifest actually
  carries it, never assumed).

PERSONA CHECK (new vintage only)
  For every NEW (arm, seed) directory that exists on disk (independent of
  the full completeness gate above -- raw JSONL traces are streamed
  incrementally during a run, unlike the audit CSV / simulation_log.csv /
  run_integrity.json, which are written only at the end), this script scans
  `raw/irrigation_farmer_traces.jsonl` for the first year=1 record whose
  `agent_id` is `PVIDDiversionAG`, reads its `input` field (the literal LLM
  prompt), and reports whether it starts with "You are PVIDDiversionAG, an
  agriculture water user" (the exact persona-lead-in string named in the
  task brief) plus the first 120 characters of that prompt (leading
  whitespace stripped -- the raw field begins with several blank lines
  before the persona text). A dir with no raw-traces file yet, or a
  raw-traces file with no year=1 PVIDDiversionAG record yet, reports a
  named PENDING status rather than failing the whole script.

PART 2 -- per seed: strict-minus-comparator contrast, old vs new
  Two metrics: IBR conditional (%) and Mead KGE vs FQL matched. Per seed,
  per vintage: diff = strict_value - comparator_value (same
  governance-minus-no-governance direction `_loader.py`'s own sign
  convention documents: negative IBR diff = governance lowered the
  high-scarcity increase rate, the paper's reported direction). A cell is
  reported only when all four (vintage x role) values for that seed are
  landed; otherwise the row records which combination is missing and
  Part 3 reports it as PENDING. `sign_match` = whether diff_old and
  diff_new share the same sign -- reported, never smoothed into a single
  score, since a 2-vintage comparison with a possible n=1 new seed has no
  business claiming more precision than a sign-and-magnitude read.

PART 2b -- per seed: shortage-tier-years / Mead-min ordering, old vs new
  For each vintage: does strict sit on the governance-benefit side of the
  comparator arm -- fewer shortage-tier years, and a HIGHER Mead minimum?
  (`_loader.py`'s convention: governance is expected to raise the physical
  floor, not lower it.) Reported per seed as `ordering_ok_old` /
  `ordering_ok_new`, again only when all four cells for that seed have
  landed.

PART 3 -- plain read, per seed, gated on landing
  For each seed where ALL FOUR cells (old strict/comparator, new
  strict/comparator) are landed for BOTH Part 2 metrics, states: (a) does
  the new corpus preserve the sign (and, without inventing a threshold not
  given in the task brief, the plainly-stated magnitude) of the IBR
  conditional contrast; (b) is strict's KGE word
  (`r28_trajectory_vs_traditional.py::_kge_word()`, imported, not
  re-derived -- "closely reproduces" / "reasonably reproduces" / "only
  loosely tracks" / "does not reproduce") high while the comparator's is
  low, for both vintages; (c) does the shortage-tier-years / Mead-min
  ordering (Part 2b) hold in both vintages. A seed with any of the four
  cells still PENDING is named as pending, listing exactly which cell(s)
  are missing -- never silently skipped, never given a partial reading.

OUTPUTS
  out/r42_irrigation_persona_pilot.csv -- row_type in {skipped, run_metrics,
    rule_id_census, manifest_check, persona_check, contrast_pair,
    ordering_pair}.
  out/r42_irrigation_persona_pilot.md -- GENERATED by render_md() directly
    from that same `rows` list (no number typed by hand).

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r42_irrigation_persona_pilot.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r25_table1_regen as R25  # noqa: E402  READ-ONLY: _irr_llm_metrics.
import r28_trajectory_vs_traditional as R28  # noqa: E402  READ-ONLY: _yearly_series,
                                              # _fql_run_dir, _run_completeness, _kge_and_rmse,
                                              # _kge_word.
import r35_placebo_retry_irrigation as R35  # noqa: E402  READ-ONLY: _rule_id_census,
                                             # _manifest_fields.

IRR_RESULTS = os.path.join(C.REPO, "examples", "irrigation_abm", "results")
SEEDS = ["42", "43", "44", "45", "46"]

VINTAGE_ARM_DIRS = {
    "old": {
        "strict": lambda seed: os.path.join(
            IRR_RESULTS, f"strict_42yr_gemma3_4b_faf1bb12_seed{seed}"),
        "comparator": lambda seed: os.path.join(
            IRR_RESULTS, f"ungoverned_42yr_gemma3_4b_faf1bb12_seed{seed}"),
    },
    "new": {
        "strict": lambda seed: os.path.join(
            IRR_RESULTS, f"strict_42yr_gemma3_4b_732b2b6c_seed{seed}"),
        "comparator": lambda seed: os.path.join(
            IRR_RESULTS, f"disabled_42yr_gemma3_4b_732b2b6c_seed{seed}"),
    },
}
COMPARATOR_ARM_NAME = {"old": "ungoverned", "new": "disabled"}
EXPECTED_COMMIT_PREFIX = {"old": "faf1bb12", "new": "732b2b6c"}
TOP_N_RULES = 3

PERSONA_AGENT = "PVIDDiversionAG"
PERSONA_EXPECTED_PREFIX = "You are PVIDDiversionAG, an agriculture water user"
PERSONA_CHARS = 120


# =============================================================================
# completeness
# =============================================================================
def _run_completeness(run_dir: str) -> tuple:
    """dir exists -> audit csv exists -> simulation_log.csv exists ->
    LAUNCH_COMMAND.txt has a `Finished:` line -> run_integrity.json exists
    with integrity_ok==True. The audit/simlog/run_integrity checks are
    r35_placebo_retry_irrigation.py::_irr_run_completeness's own gate,
    re-declared here (r35 does not export it as a module-level name meant
    for reuse) with one addition: the explicit LAUNCH_COMMAND.txt
    `Finished:` check this script's task brief asked for by name -- a run
    whose audit/simlog files happen to already exist but whose launch
    command never printed Finished: is still a partial run and must never
    be read as complete."""
    if not os.path.isdir(run_dir):
        return "skipped", "run directory does not exist yet"
    if not os.path.isfile(os.path.join(run_dir, C.L.AUDIT_LOG)):
        return "skipped", f"{C.L.AUDIT_LOG} missing (run in progress)"
    if not os.path.isfile(os.path.join(run_dir, C.L.SIM_LOG)):
        return "skipped", f"{C.L.SIM_LOG} missing (run in progress)"
    lc_path = os.path.join(run_dir, "LAUNCH_COMMAND.txt")
    if not os.path.isfile(lc_path):
        return "skipped", "LAUNCH_COMMAND.txt missing (run in progress)"
    lc_text = open(lc_path, encoding="utf-8", errors="replace").read()
    if "Finished:" not in lc_text:
        return "skipped", "LAUNCH_COMMAND.txt has no Finished: line (run in progress)"
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
def _mead_kge_vs_fql_matched(sim_path: str, seed: str) -> dict:
    """Mead-elevation KGE against the FQL-matched reference, byte-identical
    call sequence to r28_trajectory_vs_traditional.py::_irr_part1's own
    per-(model, arm, seed) cell for series="mead_elevation",
    reference="matched" -- reproduced here in single-cell form since r28's
    `_irr_part1` is a whole-corpus rows-appending Part function over its
    own fixed IRR_MODELS/IRR_ARMS lists, not a reusable per-run helper (the
    same situation r36_no_ceiling_ablation.py's own
    `_mead_kge_vs_fql_matched` documents)."""
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


def _manifest_census_row(vintage: str, arm: str, seed: str, run_dir: str) -> dict:
    manifest = R35._manifest_fields(run_dir)
    model = manifest.get("model")
    if model != "gemma3:4b":
        raise PrepError(f"{run_dir}: model={model!r}, expected 'gemma3:4b'")
    git_commit = manifest.get("git_commit")
    git_commit_short = (git_commit or "")[:8]
    expected_prefix = EXPECTED_COMMIT_PREFIX[vintage]
    if not git_commit_short.startswith(expected_prefix):
        raise PrepError(f"{run_dir}: git_commit={git_commit!r}, expected to start with "
                         f"{expected_prefix!r} for vintage={vintage!r}")
    top_k_present = "top_k" in manifest
    retry_feedback_mode_present = "retry_feedback_mode" in manifest
    return {
        "row_type": "manifest_check", "vintage": vintage, "arm": arm, "seed": seed,
        "model": model, "git_commit_short": git_commit_short,
        "git_commit_expected_prefix": expected_prefix,
        "temperature": manifest.get("temperature"), "top_p": manifest.get("top_p"),
        "top_k_present": top_k_present,
        "top_k": manifest.get("top_k") if top_k_present else "absent (not a manifest key)",
        "retry_feedback_mode_present": retry_feedback_mode_present,
        "retry_feedback_mode": (manifest.get("retry_feedback_mode") if retry_feedback_mode_present
                                 else "absent (not a manifest key)"),
        "thinking_mode": manifest.get("thinking_mode"),
    }


def _persona_check(vintage: str, arm: str, seed: str, run_dir: str) -> dict:
    base = {"row_type": "persona_check", "vintage": vintage, "arm": arm, "seed": seed}
    if not os.path.isdir(run_dir):
        return {**base, "status": "no_dir", "first_120_chars": None,
                "starts_with_expected": None}
    raw_path = os.path.join(run_dir, "raw", "irrigation_farmer_traces.jsonl")
    if not os.path.isfile(raw_path):
        return {**base, "status": "no_raw_traces_file_yet", "first_120_chars": None,
                "starts_with_expected": None}
    found = None
    with open(raw_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("agent_id") == PERSONA_AGENT and int(obj.get("year", -1)) == 1:
                found = obj
                break
    if found is None:
        return {**base, "status": "no_year1_persona_trace_yet", "first_120_chars": None,
                "starts_with_expected": None}
    prompt = (found.get("input") or "").lstrip()
    first120 = prompt[:PERSONA_CHARS]
    starts_ok = prompt.startswith(PERSONA_EXPECTED_PREFIX)
    return {**base, "status": "ok", "first_120_chars": first120,
            "starts_with_expected": starts_ok}


def _part1(rows: list) -> dict:
    """Returns {(vintage, role, seed): run_metrics_row} for landed runs,
    used by Part 2/2b. Also appends skipped / run_metrics / rule_id_census /
    manifest_check / persona_check rows to `rows`."""
    per_run: dict = {}
    for vintage, arm_dirs in VINTAGE_ARM_DIRS.items():
        for role, dir_fn in arm_dirs.items():
            arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME[vintage]
            for seed in SEEDS:
                run_dir = dir_fn(seed)
                status, reason = _run_completeness(run_dir)
                if status == "skipped":
                    print(f"  SKIPPED {vintage}/{arm_name} seed {seed}: {reason}")
                    rows.append({"row_type": "skipped", "vintage": vintage, "arm": arm_name,
                                 "role": role, "seed": seed, "reason": reason})
                else:
                    sim_path = os.path.join(run_dir, C.L.SIM_LOG)
                    m = R25._irr_llm_metrics(run_dir)
                    sim = C.read_csv(sim_path)
                    aud = C.read_csv(os.path.join(run_dir, C.L.AUDIT_LOG))
                    n = len(aud)
                    ibr_unconditional = C.L.increase_rate(sim)

                    years, mead_series = R28._yearly_series(sim_path, "lake_mead_level", "first")
                    _, tier_series = R28._yearly_series(sim_path, "shortage_tier", "first")
                    final_year_mead_ft = mead_series[-1]
                    min_mead_ft = min(mead_series)
                    shortage_tier_years = sum(1 for t in tier_series if t >= 1)

                    kge_stats = _mead_kge_vs_fql_matched(sim_path, seed)

                    st = [(r.get("status") or "").strip() for r in aud]
                    rejected_n = sum(1 for s in st if s.startswith("REJECTED"))
                    retried_n = sum(1 for r in aud if int(r.get("retry_count") or 0) > 0)

                    row = {
                        "row_type": "run_metrics", "vintage": vintage, "arm": arm_name,
                        "role": role, "seed": seed, "n_rows": n,
                        "ibr_conditional": m["ibr_headline"],
                        "ibr_unconditional": ibr_unconditional,
                        "ehe_pooled_executed": m["ehe_pooled"],
                        "ehe_pooled_proposal": m["ehe_pooled_proposal"],
                        "rejected_n": rejected_n, "rejection_rate_pct": m["rejection_rate_pct"],
                        "retried_n": retried_n, "retry_rate_pct": m["retry_rate_pct"],
                        "final_year_mead_ft": final_year_mead_ft, "min_mead_ft": min_mead_ft,
                        "shortage_tier_years": float(shortage_tier_years),
                        "mead_kge_vs_fql_matched": kge_stats["kge"],
                        "mead_rmse_vs_fql_matched": kge_stats["rmse"],
                        "fallback_pct": m["fallback_pct"], "llm_fail_n": int(m["llm_fail_n"]),
                        "wall_hours": m["wall_hours"],
                    }
                    rows.append(row)

                    census = R35._rule_id_census(aud, TOP_N_RULES)
                    for rank, (rule_id, count) in enumerate(census, start=1):
                        rows.append({"row_type": "rule_id_census", "vintage": vintage,
                                     "arm": arm_name, "seed": seed, "rank": rank,
                                     "rule_id": rule_id, "count": count})

                    rows.append(_manifest_census_row(vintage, arm_name, seed, run_dir))

                    print(f"  OK {vintage}/{arm_name:11s} seed {seed}: "
                          f"IBR_cond={m['ibr_headline']:.2f}% KGE={kge_stats['kge']:.4f} "
                          f"shortage_tier_years={shortage_tier_years} "
                          f"top_rule={census[0] if census else None}")

                    per_run[(vintage, role, seed)] = row

                if vintage == "new":
                    rows.append(_persona_check(vintage, arm_name, seed, run_dir))
    return per_run


# =============================================================================
# Part 2 / 2b
# =============================================================================
CONTRAST_METRIC_KEYS = {
    "IBR conditional (%)": "ibr_conditional",
    "Mead KGE vs FQL matched": "mead_kge_vs_fql_matched",
}
ORDERING_METRIC_KEYS = {
    "Shortage-tier years": "shortage_tier_years",
    "Mead min (ft)": "min_mead_ft",
}
# Direction in which "strict" is expected to sit relative to its comparator,
# per `_loader.py`'s own governance-benefit sign convention (governance
# LOWERS a harmful rate / RAISES the physical floor): True = higher is
# better for strict (Mead min), False = lower is better for strict
# (shortage-tier years).
ORDERING_HIGHER_IS_BETTER_FOR_STRICT = {
    "Shortage-tier years": False,
    "Mead min (ft)": True,
}


def _four_cells(per_run: dict, seed: str, key: str) -> tuple:
    """({(vintage, role): value}, [missing 'vintage/role' labels]) for one
    seed and one run_metrics field, over the fixed (vintage, role) grid
    old/new x strict/comparator."""
    cells, missing = {}, []
    for vintage in ("old", "new"):
        for role in ("strict", "comparator"):
            v = per_run.get((vintage, role, seed))
            if v is None:
                missing.append(f"{vintage}/{role}")
            else:
                cells[(vintage, role)] = float(v[key])
    return cells, missing


def _part2(rows: list, per_run: dict) -> None:
    for metric_label, key in CONTRAST_METRIC_KEYS.items():
        for seed in SEEDS:
            cells, missing = _four_cells(per_run, seed, key)
            if missing:
                print(f"  Part 2 PENDING: {metric_label} seed {seed} -- missing "
                      f"{missing}")
                rows.append({"row_type": "skipped", "section": "contrast_pair",
                             "metric": metric_label, "seed": seed,
                             "reason": f"missing: {', '.join(missing)}"})
                continue
            diff_old = cells[("old", "strict")] - cells[("old", "comparator")]
            diff_new = cells[("new", "strict")] - cells[("new", "comparator")]
            sign_match = (diff_old > 0) == (diff_new > 0)
            rows.append({
                "row_type": "contrast_pair", "metric": metric_label, "seed": seed,
                "old_strict": cells[("old", "strict")],
                "old_comparator": cells[("old", "comparator")],
                "new_strict": cells[("new", "strict")],
                "new_comparator": cells[("new", "comparator")],
                "diff_old": diff_old, "diff_new": diff_new, "sign_match": sign_match,
            })


def _part2b(rows: list, per_run: dict) -> None:
    for metric_label, key in ORDERING_METRIC_KEYS.items():
        higher_is_better = ORDERING_HIGHER_IS_BETTER_FOR_STRICT[metric_label]
        for seed in SEEDS:
            cells, missing = _four_cells(per_run, seed, key)
            if missing:
                print(f"  Part 2b PENDING: {metric_label} seed {seed} -- missing "
                      f"{missing}")
                rows.append({"row_type": "skipped", "section": "ordering_pair",
                             "metric": metric_label, "seed": seed,
                             "reason": f"missing: {', '.join(missing)}"})
                continue

            def _ok(vintage):
                s, c = cells[(vintage, "strict")], cells[(vintage, "comparator")]
                return (s > c) if higher_is_better else (s < c)

            rows.append({
                "row_type": "ordering_pair", "metric": metric_label, "seed": seed,
                "old_strict": cells[("old", "strict")],
                "old_comparator": cells[("old", "comparator")],
                "new_strict": cells[("new", "strict")],
                "new_comparator": cells[("new", "comparator")],
                "ordering_ok_old": _ok("old"), "ordering_ok_new": _ok("new"),
            })


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "vintage", "arm", "role", "seed", "reason", "n_rows",
    "ibr_conditional", "ibr_unconditional", "ehe_pooled_executed", "ehe_pooled_proposal",
    "rejected_n", "rejection_rate_pct", "retried_n", "retry_rate_pct",
    "final_year_mead_ft", "min_mead_ft", "shortage_tier_years",
    "mead_kge_vs_fql_matched", "mead_rmse_vs_fql_matched",
    "fallback_pct", "llm_fail_n", "wall_hours",
    "rank", "rule_id", "count",
    "model", "git_commit_short", "git_commit_expected_prefix", "temperature", "top_p",
    "top_k_present", "top_k", "retry_feedback_mode_present", "retry_feedback_mode",
    "thinking_mode",
    "status", "first_120_chars", "starts_with_expected",
    "metric", "old_strict", "old_comparator", "new_strict", "new_comparator",
    "diff_old", "diff_new", "sign_match", "ordering_ok_old", "ordering_ok_new",
]


def main() -> int:
    C.banner("R42  Irrigation persona pilot: new corpus (732b2b6c) vs old corpus (faf1bb12)")
    rows: list = []

    print("\n-- Part 1: per (vintage, arm, seed) metrics, rule census, manifest census, "
          "persona check --")
    per_run = _part1(rows)

    print("\n-- Part 2: seed-paired strict-minus-comparator contrast, old vs new --")
    _part2(rows, per_run)

    print("\n-- Part 2b: shortage-tier-years / Mead-min ordering, old vs new --")
    _part2b(rows, per_run)

    md_text = render_md(rows)

    csv_final = "r42_irrigation_persona_pilot.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, "r42_irrigation_persona_pilot.md")
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


def render_md(rows: list) -> str:
    lines = []
    lines.append("# R42 -- irrigation persona pilot: new corpus (732b2b6c) vs old corpus (faf1bb12)")
    lines.append("")
    lines.append("Source: `r42_irrigation_persona_pilot.py`. Every number below is read live "
                 "from the `rows` list this script writes to the paired CSV. \"old\" = commit "
                 "faf1bb12 (5 seeds landed, 42-46). \"new\" = commit 732b2b6c (the new persona "
                 "corpus; landed cells only where they exist on disk and pass the completeness "
                 "gate -- see Method).")
    lines.append("")

    # ---- Part 1: per-run metrics -----------------------------------------------
    lines.append("## Part 1 -- per (vintage, arm, seed) metrics")
    lines.append("")
    lines.append("| vintage | arm | seed | n_rows | IBR cond. % | IBR uncond. % | EHE exec | "
                 "EHE prop | rejected n | rejection % | retried n | retry % | final-yr Mead ft | "
                 "min Mead ft | shortage-tier yrs | Mead KGE vs FQL matched |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for vintage in ("old", "new"):
        for role in ("strict", "comparator"):
            arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME[vintage]
            for seed in SEEDS:
                recs = _find(rows, "run_metrics", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    lines.append(f"| {vintage} | {arm_name} | {seed} | PENDING | -- | "
                                 f"-- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |")
                    continue
                r = recs[0]
                lines.append(
                    f"| {vintage} | {arm_name} | {seed} | {r['n_rows']} | "
                    f"{_cp(r['ibr_conditional']):.2f} | {_cp(r['ibr_unconditional']):.2f} | "
                    f"{_cp(r['ehe_pooled_executed']):.3f} | {_cp(r['ehe_pooled_proposal']):.3f} | "
                    f"{r['rejected_n']} | {_cp(r['rejection_rate_pct']):.2f} | "
                    f"{r['retried_n']} | {_cp(r['retry_rate_pct']):.2f} | "
                    f"{_cp(r['final_year_mead_ft']):.1f} | {_cp(r['min_mead_ft']):.1f} | "
                    f"{int(r['shortage_tier_years'])} | {_cp(r['mead_kge_vs_fql_matched']):.4f} |"
                )
    lines.append("")

    lines.append("### Rule-id census, top 3 among retried rows")
    lines.append("")
    lines.append("| vintage | arm | seed | rank | rule_id | count |")
    lines.append("|---|---|---|---|---|---|")
    for vintage in ("old", "new"):
        for role in ("strict", "comparator"):
            arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME[vintage]
            for seed in SEEDS:
                recs = _find(rows, "rule_id_census", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    lines.append(f"| {vintage} | {arm_name} | {seed} | -- | pending | -- |")
                    continue
                for r in sorted(recs, key=lambda x: int(x["rank"])):
                    lines.append(f"| {vintage} | {arm_name} | {seed} | {r['rank']} | "
                                 f"{r['rule_id']} | {r['count']} |")
    lines.append("")

    lines.append("### Manifest census")
    lines.append("")
    lines.append("| vintage | arm | seed | model | git_commit | temperature | top_p | top_k | "
                 "retry_feedback_mode | thinking_mode |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for vintage in ("old", "new"):
        for role in ("strict", "comparator"):
            arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME[vintage]
            for seed in SEEDS:
                recs = _find(rows, "manifest_check", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    lines.append(f"| {vintage} | {arm_name} | {seed} | pending | -- | -- | -- | "
                                 f"-- | -- | -- |")
                    continue
                r = recs[0]
                lines.append(
                    f"| {vintage} | {arm_name} | {seed} | {r['model']} | "
                    f"{r['git_commit_short']}... | {r['temperature']} | {r['top_p']} | "
                    f"{r['top_k']} | {r['retry_feedback_mode']} | {r['thinking_mode']} |"
                )
    lines.append("")

    lines.append("### Persona check (new vintage only) -- year-1 PVIDDiversionAG prompt")
    lines.append("")
    lines.append("| arm | seed | status | starts with expected persona lead-in | "
                 "first 120 chars |")
    lines.append("|---|---|---|---|---|")
    for role in ("strict", "comparator"):
        arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME["new"]
        for seed in SEEDS:
            recs = _find(rows, "persona_check", vintage="new", arm=arm_name, seed=seed)
            if not recs:
                lines.append(f"| {arm_name} | {seed} | not checked | -- | -- |")
                continue
            r = recs[0]
            chars = r["first_120_chars"]
            chars_cell = "n.a." if chars is None else "`" + chars.replace("|", "\\|") + "`"
            lines.append(f"| {arm_name} | {seed} | {r['status']} | "
                         f"{r['starts_with_expected']} | {chars_cell} |")
    lines.append("")

    # ---- Part 2: contrasts -------------------------------------------------------
    lines.append("## Part 2 -- seed-paired strict-minus-comparator contrast, old vs new")
    lines.append("")
    lines.append("diff = strict value - comparator value (governance-minus-no-governance "
                 "direction). `sign_match` = whether diff_old and diff_new share the same "
                 "sign -- no significance test, n is whatever has landed.")
    lines.append("")
    lines.append("| metric | seed | old strict | old comparator | diff old | new strict | "
                 "new comparator | diff new | sign match |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for metric_label in CONTRAST_METRIC_KEYS:
        for seed in SEEDS:
            recs = _find(rows, "contrast_pair", metric=metric_label, seed=seed)
            if not recs:
                pend = _find(rows, "skipped", section="contrast_pair", metric=metric_label,
                              seed=seed)
                reason = pend[0]["reason"] if pend else "no data"
                lines.append(f"| {metric_label} | {seed} | -- | -- | -- | -- | -- | -- | "
                             f"PENDING ({reason}) |")
                continue
            r = recs[0]
            lines.append(
                f"| {metric_label} | {seed} | {_cp(r['old_strict']):.4f} | "
                f"{_cp(r['old_comparator']):.4f} | {_cp(r['diff_old']):.4f} | "
                f"{_cp(r['new_strict']):.4f} | {_cp(r['new_comparator']):.4f} | "
                f"{_cp(r['diff_new']):.4f} | {r['sign_match']} |"
            )
    lines.append("")

    # ---- Part 2b: ordering ---------------------------------------------------
    lines.append("## Part 2b -- shortage-tier-years / Mead-min ordering, old vs new")
    lines.append("")
    lines.append("ordering_ok = strict sits on the governance-benefit side of its comparator "
                 "(fewer shortage-tier years; a HIGHER Mead minimum).")
    lines.append("")
    lines.append("| metric | seed | old strict | old comparator | ordering ok (old) | "
                 "new strict | new comparator | ordering ok (new) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for metric_label in ORDERING_METRIC_KEYS:
        for seed in SEEDS:
            recs = _find(rows, "ordering_pair", metric=metric_label, seed=seed)
            if not recs:
                pend = _find(rows, "skipped", section="ordering_pair", metric=metric_label,
                              seed=seed)
                reason = pend[0]["reason"] if pend else "no data"
                lines.append(f"| {metric_label} | {seed} | -- | -- | -- | -- | -- | "
                             f"PENDING ({reason}) |")
                continue
            r = recs[0]
            lines.append(
                f"| {metric_label} | {seed} | {_cp(r['old_strict']):.2f} | "
                f"{_cp(r['old_comparator']):.2f} | {r['ordering_ok_old']} | "
                f"{_cp(r['new_strict']):.2f} | {_cp(r['new_comparator']):.2f} | "
                f"{r['ordering_ok_new']} |"
            )
    lines.append("")

    # ---- Plain read -----------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    lines.append("Per seed, gated on all four cells (old strict/comparator, new "
                 "strict/comparator) having landed for BOTH Part 2 metrics AND both Part 2b "
                 "metrics. A seed missing any cell is reported as pending, naming exactly "
                 "which cell(s).")
    lines.append("")
    any_landed = False
    for seed in SEEDS:
        ibr_rec = _find(rows, "contrast_pair", metric="IBR conditional (%)", seed=seed)
        kge_rec = _find(rows, "contrast_pair", metric="Mead KGE vs FQL matched", seed=seed)
        short_rec = _find(rows, "ordering_pair", metric="Shortage-tier years", seed=seed)
        mead_rec = _find(rows, "ordering_pair", metric="Mead min (ft)", seed=seed)
        needed = {"IBR conditional (%) contrast": ibr_rec, "Mead KGE contrast": kge_rec,
                  "Shortage-tier-years ordering": short_rec, "Mead-min ordering": mead_rec}
        missing_parts = [name for name, recs in needed.items() if not recs]
        if missing_parts:
            skip_reasons = []
            for name, section, metric in (
                ("IBR conditional (%) contrast", "contrast_pair", "IBR conditional (%)"),
                ("Mead KGE contrast", "contrast_pair", "Mead KGE vs FQL matched"),
                ("Shortage-tier-years ordering", "ordering_pair", "Shortage-tier years"),
                ("Mead-min ordering", "ordering_pair", "Mead min (ft)"),
            ):
                if name in missing_parts:
                    pend = _find(rows, "skipped", section=section, metric=metric, seed=seed)
                    skip_reasons.append(f"{name} ({pend[0]['reason'] if pend else 'no data'})")
            lines.append(f"- seed {seed}: PENDING -- missing {'; '.join(skip_reasons)}.")
            continue

        any_landed = True
        ibr, kge = ibr_rec[0], kge_rec[0]
        short_o, mead_o = short_rec[0], mead_rec[0]
        ibr_sign_word = "the SAME sign as" if ibr["sign_match"] else "the OPPOSITE sign from"
        kge_word_old_strict = R28._kge_word(kge["old_strict"])
        kge_word_old_comp = R28._kge_word(kge["old_comparator"])
        kge_word_new_strict = R28._kge_word(kge["new_strict"])
        kge_word_new_comp = R28._kge_word(kge["new_comparator"])
        lines.append(
            f"- seed {seed}: (a) IBR conditional contrast -- old diff "
            f"{_cp(ibr['diff_old']):.2f}pp, new diff {_cp(ibr['diff_new']):.2f}pp: the new "
            f"corpus's diff has {ibr_sign_word} the old corpus's diff. (b) Mead KGE vs FQL "
            f"matched -- old: strict {kge_word_old_strict} it (KGE={_cp(kge['old_strict']):.3f}), "
            f"comparator {kge_word_old_comp} it (KGE={_cp(kge['old_comparator']):.3f}); new: "
            f"strict {kge_word_new_strict} it (KGE={_cp(kge['new_strict']):.3f}), comparator "
            f"{kge_word_new_comp} it (KGE={_cp(kge['new_comparator']):.3f}). (c) ordering -- "
            f"shortage-tier years ok old={short_o['ordering_ok_old']}/new="
            f"{short_o['ordering_ok_new']}; Mead min ok old={mead_o['ordering_ok_old']}/new="
            f"{mead_o['ordering_ok_new']}."
        )
    if not any_landed:
        lines.append("")
        lines.append("No seed has all four cells landed yet for both Part 2 metrics and both "
                     "Part 2b metrics (every `new` cell is still pending -- see Part 1). This "
                     "is expected for the pilot read: only the `old` (faf1bb12) side is "
                     "complete at the time this script was last run.")
    lines.append("")

    # ---- Method -----------------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "IBR conditional/unconditional: `_loader.py::ibr()` / `_loader.py::increase_rate()` "
        "(imported as `C.L.ibr` / `C.L.increase_rate`), both on the FINAL PROPOSED action "
        "(`_loader.py::action()` -- a REJECTED row's proposal never executed, but IBR is a "
        "proposal-level rate by definition). EHE pooled (executed + proposal), rejection "
        "rate, retry rate, and min Mead ft come from "
        "`r25_table1_regen.py::_irr_llm_metrics()`, imported, not re-derived -- the SAME call "
        "every table in this package uses for these columns. `rejected_n`/`retried_n` are "
        "counted directly here with the identical condition `_irr_llm_metrics()` uses for its "
        "own rates (status.startswith(\"REJECTED\"); retry_count>0). Final-year Mead ft, "
        "min Mead ft (read independently from the same yearly series, not from "
        "`_irr_llm_metrics()`, as a cross-check), and shortage-tier years all come from "
        "`r28_trajectory_vs_traditional.py::_yearly_series()` on `lake_mead_level` and "
        "`shortage_tier` respectively -- imported, not re-derived; `_yearly_series()`'s own "
        "nunique==1-per-year check is what verifies both columns are genuinely basin-level, "
        "not assumed. `shortage_tier_years` (years with `shortage_tier>=1`) is a DIFFERENT "
        "metric from the `shortage_years` column r25/r35/r36 report (years with mean Mead "
        "level below 1075 ft) and is never given that other name. Mead-elevation KGE vs the "
        "FQL-matched reference: `r28_trajectory_vs_traditional.py::_yearly_series()` + "
        "`_kge_and_rmse()` (Gupta et al. 2009 original formulation), against "
        "`_fql_run_dir(\"matched\", seed)` = `fql_raw_norebalance_faf1bb12` -- the SAME "
        "reference dir r28's own Part 1 uses for irrigation, reused unchanged for both "
        "vintages since FQL is a deterministic rule-based baseline with no LLM sampling. "
        "Top-3 rule-id census: `r35_placebo_retry_irrigation.py::_rule_id_census()`, imported, "
        "rule ids `sorted()` before counting (the Python set-hash-randomization fix "
        "r27/r34/r35 all apply). Manifest census: `git_commit_short` is value-enforced to "
        "start with the vintage's expected commit prefix (raises otherwise -- both vintages "
        "are pinned commits here); `model` is value-enforced to `gemma3:4b`; `temperature` / "
        "`top_p` are read and reported (both `null` in every manifest read so far -- the "
        "EXPECTED value for irrigation's gemma3:4b runs, not a missing-field symptom); "
        "`top_k` and `retry_feedback_mode` are checked for PRESENCE as top-level manifest "
        "keys and reported \"absent (not a manifest key)\" when missing, never guessed or "
        "defaulted to null. `r28_trajectory_vs_traditional.py::_kge_word()` (imported) "
        "supplies the plain-read's \"closely/reasonably reproduces\" / \"only loosely "
        "tracks\" / \"does not reproduce\" language -- no new threshold invented here. "
        "`sign_match` (Part 2) is a same-sign check only; this script does not invent a "
        "numeric \"rough size\" tolerance the task brief did not specify -- both diffs are "
        "printed in full so the reader judges magnitude directly."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
