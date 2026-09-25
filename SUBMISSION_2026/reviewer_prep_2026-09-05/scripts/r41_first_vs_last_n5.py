"""R41 -- first-attempt vs last-proposal IBR at n=5 (flood) / n=3 (irrigation),
extending r33's single-seed irrigation result to the landed multi-seed initprop
corpora. Answers the audit's queue steps [3a] (flood) and [3b] (irrigation).
CPU-only, existing runs only, no LLM calls made by this script.

BACKGROUND -- what this script extends and why
  `r33_first_vs_last_proposal.py` computed the first-vs-last-proposal IBR
  contrast for exactly ONE irrigation run (`strict_42yr_gemma3_4b_c3391a53_
  initprop_seed42`), citing `initial_skill`/`initial_labels`/`attempt_skills`
  (the `global_config.audit.initial_proposal_columns` opt-in columns,
  default OFF) as closing the `docs/AUDIT_SCHEMA.md` "Per-attempt retry
  sequence" gap. `out/paper_readiness_audit_2026-09-22.md`'s "What the
  pending queue steps can change" section (quoted verbatim, not
  paraphrased): "**Step [3a] flood initprop seeds 42-46 and [3b] irrigation
  initprop seeds 43-44.** Touch M6. Decision rule: if the five-seed
  first-attempt IBR mean exceeds the last-proposal mean by more than the
  pooled standard deviation, 'negotiation, not relabelling' holds at n = 5
  on one corpus and can be printed as a headline. If the gap falls inside
  one standard deviation, drop the claim and keep only the walk-back rate
  (41.21 percent of high-WSA first attempts ended as maintain or decrease),
  which is descriptive and does not need the contrast." That 41.21% figure
  is IRRIGATION's own single-seed walk-back rate from r33 -- this script
  computes each domain's OWN walk-back rate at its own landed n, never
  reuses that one number across domains.

  "the pooled standard deviation" is not defined further in the audit text.
  This script uses the standard two-sample pooled-SD formula (the Cohen's-d
  denominator convention): pooled_sd = sqrt((sd_first^2 + sd_last^2) / 2)
  for n_first == n_last (equal-n case, which always holds here since every
  seed contributes exactly one first-attempt value and one last-proposal
  value) -- distinct from the SD of the PAIRED per-seed differences, which
  is also reported separately (see PART A/B below) because the task
  separately asked for "sd (ddof=1)" of the differences alongside the
  permutation test. This is a judgment call, flagged as such, not something
  verified against a second source in the audit text -- see the final
  report for this flag.

RUN LAYOUT
  All eight target runs landed before this fix round, confirmed by
  directory + manifest, not assumed: flood
  `JOH_strict_initprop_gemma3_4b_83fa97e1/Run_{42..46}` (5 seeds, all at
  83fa97e1); irrigation seed 42 (`strict_42yr_gemma3_4b_c3391a53_
  initprop_seed42`, at c3391a53) plus seeds 43 and 44
  (`strict_42yr_gemma3_4b_83fa97e1_initprop_seed{43,44}`, both at
  83fa97e1). Seed 44 was the last of the eight to land -- its own
  `LAUNCH_COMMAND.txt` records `Finished: 2026/09/23 11:43:30.09` local
  wall-clock (read directly from the file's own "Finished:" line; the
  locale prints a weekday abbreviation before the 24-hour time, not an
  AM/PM marker; cross-checked against `run_integrity.json`'s own 11:43:28
  mtime, not assumed from the mtime alone). With all eight runs
  landed, Part B now populates at n=3 with zero PENDING rows -- the same
  script, unmodified in its completeness-gate logic, that first ran
  against n=2 while seed 44 was still on the GPU.

PART A -- flood, n = 5 (JOH_strict_initprop_gemma3_4b_83fa97e1, seeds 42-46)
  Flood's `initial_labels` carries `TP_LABEL=X|CP_LABEL=Y` (verified live
  against seed 42's own audit rows before writing this script, the flood
  analogue of irrigation's `WSA_LABEL`/`ACA_LABEL`). The published flood
  IBR formula (CLAUDE.md: "IBR formula = R1 + R3 + R4 (R5 excluded per
  EDT2)", canonical at `examples/single_agent/analysis/
  gemma4_nw_crossmodel_analysis.py (compute_ibr_components)`, transcribed
  into `_common.py::flood_ibr_components`) is restated here as
  `_flood_rate()` because
  `flood_ibr_components` is hard-wired to read TP from `construct_TP_LABEL`
  (the FINAL label) and cannot be pointed at `initial_labels`' TP_LABEL --
  the exact same reason r33 restated `_loader.py::ibr()` as its own
  `_rate()` for irrigation. `_flood_rate()`'s own self-test cross-checks it
  against `_common.py::flood_ibr_components` directly (action=proposed_
  skill, label=final, on the SAME audit rows) and raises on disagreement --
  this is checking this script's OWN reimplementation against the
  canonical library function, not two independently-designed computations.
  Three action sources reported per seed: initial_skill (first attempt,
  paired with its own first-attempt TP_LABEL -- the "first impulse"
  framing r33's own Plain-read section uses), proposed_skill (last
  recorded proposal, paired with `construct_TP_LABEL` -- the published
  headline framing), and `C.flood_executed` (REJECTED -> `do_nothing`,
  else final_skill, paired with `construct_TP_LABEL`).

  Walk-back rate: "share of first-attempt rule-violating proposals whose
  last proposal is compliant" (task brief's own words). Defined here by
  direct analogy to r33's own irrigation walk-back block (initial_skill/
  initial_labels/attempt_skills, r33_first_vs_last_proposal.py lines
  308-315): base = rows whose FIRST attempt (initial_skill, normalized)
  is an IBR violation under that SAME row's FIRST-attempt TP_LABEL;
  walked_back = base rows whose LAST attempt (attempt_skills[-1],
  normalized) is NOT a violation under the SAME (unchanged) first-attempt
  TP_LABEL -- i.e. only the action is re-checked, the label is held fixed
  at its first-attempt value, exactly as r33 does for irrigation. This is
  a judgment call (the task brief does not specify whether "compliant"
  re-evaluates the label too), made by direct precedent, not guessed cold.

  Band check: this arm's own `IBR headline` / `EHE pooled` / `final_year_
  protection_pct` (`r25_table1_regen.py::_flood_llm_metrics()`, imported,
  not re-derived -- the same function r35/r36 already reuse for flood)
  against the faf1bb12 strict 5-seed band (`JOH_strict_gemma3_4b_faf1bb12/
  Run_{42..46}`, ALREADY COMPLETE, mean +/- 2*sd across its own 5 seeds,
  same function). Purpose: show the initprop flag (opt-in, key-gated,
  `global_config.audit.initial_proposal_columns`) did not itself change
  governed behaviour -- the initprop arm should sit inside the pre-
  initprop strict band on all three metrics.

  NOTE: `_flood_llm_metrics()`'s own `ibr_headline` uses action=final_skill
  (r23's `LEVELS["final"] = C.flood_final`, not `proposed_skill`) -- a
  DIFFERENT action-column choice from this script's own "last-proposal"
  cell (action=proposed_skill, mirroring r33's naming for irrigation). Both
  are reported; this script does not assert they are numerically identical
  (unlike r33's irrigation crosscheck, which explicitly verifies proposed_
  skill==final_skill on all but a small unparsed share) -- see the Method
  section for the live-computed size of any discrepancy on this corpus.

PART B -- irrigation, n = 3 (seed 42 c3391a53 initprop; seeds 43, 44 at
  83fa97e1)
  Reuses r33's OWN functions directly (`r33_first_vs_last_proposal.py`,
  imported READ-ONLY): `_rate()`, `_initial_wsa()`, `_final_wsa()`,
  `_crosscheck_published_ibr()`, `TARGET_DIR` (== the seed-42 c3391a53
  run). Completeness gate reused from `r35_placebo_retry_irrigation.py::
  _irr_run_completeness` (dir -> audit -> simlog -> run_integrity.json
  integrity_ok==True), the stricter gate r35/r36 established after r33 was
  written. Walk-back rate re-declared here (byte-identical to r33's own
  inline block, r33 does not export it as a reusable function) as
  `_irr_walkback()`.

  Commit mix: seed 42 ran at c3391a53, seeds 43/44 at 83fa97e1 -- reported
  from each run's own manifest (never assumed), with a one-line pointer to
  `out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md` (the three-piece
  evidence chain r35's own Method section already cites for why pooling
  across these two commits is accepted for this feature) and the earlier
  `out/regen_progress_2026-09-15.md` faf1bb12 -> c3391a53 gate.

  No band check in Part B -- the task brief did not ask for one here (the
  faf1bb12 -> c3391a53 gate already covers the commit-mix concern; a fresh
  band check would need a faf1bb12 5-seed irrigation initprop corpus that
  does not exist, since faf1bb12 predates the initprop columns entirely).

PART C -- provenance census
  Per target run (5 flood + 3 irrigation, 8 total; the faf1bb12 comparators
  used only for Part A's band check are NOT included here -- they are
  already established by r33 Part 3 to categorically lack `initial_skill`):
  manifest git_commit / model / thinking_mode; whether
  `initial_proposal_columns` is on, read from BOTH `reproducibility_
  manifest.json` (checked directly per run, does not carry this key on any
  run in this package, per r33's own finding) and `config_snapshot.yaml`'s
  `global_config.audit.initial_proposal_columns` (where it DOES appear);
  and the count of rows with an empty `initial_skill` cell. NOTE: the audit
  CSVs never contain a true null -- `initial_skill` is either a real skill
  name or the empty string "" (never a blank/NULL cell type), so "rows
  where initial_skill is null" is read here as "rows where initial_skill is
  an empty string after stripping" -- the same quantity r33 calls
  `n_initial_unparsed`. Flagged as an interpretation, not silently assumed.

COMPLETENESS GATE
  Flood: per seed, run dir exists -> household_governance_audit.csv exists
  -> reproducibility_manifest.json exists -> run_integrity.json exists with
  integrity_ok==True. Irrigation: `r35_placebo_retry_irrigation.py::
  _irr_run_completeness`, imported, same four checks with irrigation's own
  file names. Missing any -> row_type=skipped with a printed pending
  reason; that seed is EXCLUDED from pooled/mean/diff/gate/band
  computations, which recompute honestly at whatever n remains (never
  silently padded to n=5 or n=3).

OUTPUTS
  out/r41_first_vs_last_n5.csv -- row_type in {skipped, flood_ibr,
    flood_ibr_summary, flood_walkback, flood_walkback_summary, flood_diff,
    flood_diff_summary, flood_gate, flood_band, irr_ibr, irr_ibr_summary,
    irr_walkback, irr_walkback_summary, irr_diff, irr_diff_summary,
    irr_gate, manifest_census}.
  out/r41_first_vs_last_n5.md -- GENERATED by render_md() directly from
    that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r41_first_vs_last_n5.py
        python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r41_first_vs_last_n5.py --corpus defaults

--corpus (added 2026-09-23, see _common.py::flood_corpus_dirs) -- PART A
(flood) ONLY; Part B (irrigation) is always the v08 corpus, unaffected.
v08 (default): EXACTLY the behaviour documented above, byte-identical
output. defaults: the initprop target reads `JOH_strict_initprop_defaults_
gemma3_4b_83fa97e1`; the band comparator becomes the DEFAULTS baseline
strict corpus (not faf1bb12) -- comparing the initprop flag's effect
within the same sampling regime, the same convention r23/r24/r25/r26 use.
This script's existing completeness gate already tolerates 0/5 seeds
landed (true today for the defaults initprop dir) via its early return in
`_part_a_flood`, so no new PENDING branch was needed for the target side;
the band comparator itself is expected complete whenever any target seed
lands (raises with a clear message otherwise, never a bare
FileNotFoundError). Writes out/r41_first_vs_last_n5_defaults.{md,csv}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r25_table1_regen as R25  # noqa: E402  READ-ONLY: _flood_llm_metrics.
import r33_first_vs_last_proposal as R33  # noqa: E402  READ-ONLY: _rate,
                                           # _initial_wsa, _final_wsa,
                                           # _crosscheck_published_ibr,
                                           # _parse_labels, TARGET_DIR.
import r35_placebo_retry_irrigation as R35  # noqa: E402  READ-ONLY:
                                             # _irr_run_completeness.

L = C.L  # SUBMISSION_2026/decomposition/_loader.py: HIGH, INCREASE, mean, sd

# =============================================================================
# constants
# =============================================================================
FLOOD_INITPROP_ROOT = C.flood_corpus_dirs("v08")["strict_initprop"][0]
FLOOD_BAND_ROOT = C.flood_corpus_dirs("v08")["strict"][0]
FLOOD_SEEDS = ["42", "43", "44", "45", "46"]


def _flood_initprop_root(corpus: str) -> str:
    """FLOOD_INITPROP_ROOT above, verbatim, for corpus=='v08'; the
    no-sampling-params re-run's strict_initprop dir otherwise."""
    if corpus == "v08":
        return FLOOD_INITPROP_ROOT
    return C.flood_corpus_dirs(corpus)["strict_initprop"][0]


def _flood_band_root(corpus: str) -> str:
    """FLOOD_BAND_ROOT above (faf1bb12), verbatim, for corpus=='v08'. For
    --corpus defaults, the band comparator is the DEFAULTS baseline strict
    corpus (not faf1bb12) -- comparing the initprop flag's effect within
    the same sampling regime, the same convention r23/r24/r25/r26 use for
    their own defaults-mode comparators."""
    if corpus == "v08":
        return FLOOD_BAND_ROOT
    return C.flood_corpus_dirs(corpus)["strict"][0]
FLOOD_MODEL = "gemma3:4b"
FLOOD_COMMIT_PREFIX = "83fa97e1"

IRR_RESULTS = os.path.join(C.REPO, "examples", "irrigation_abm", "results")
IRR_SEEDS = ["42", "43", "44"]
IRR_MODEL = "gemma3:4b"
IRR_SEED_DIRS = {
    "42": (R33.TARGET_DIR, "c3391a53"),
    "43": (os.path.join(IRR_RESULTS, "strict_42yr_gemma3_4b_83fa97e1_initprop_seed43"), "83fa97e1"),
    "44": (os.path.join(IRR_RESULTS, "strict_42yr_gemma3_4b_83fa97e1_initprop_seed44"), "83fa97e1"),
}
MOCK_EQUIV_NOTE = "out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md"
REGEN_GATE_NOTE = "out/regen_progress_2026-09-15.md"

AUDIT_ATTEMPT_COLS = ["initial_skill", "initial_labels", "attempt_skills",
                       "proposed_skill", "final_skill", "status", "retry_count"]


# =============================================================================
# shared helpers (both domains)
# =============================================================================
def _check_attempt_invariants(aud: list, where: str) -> None:
    """Byte-identical checks to r33's own two invariant blocks, factored
    out here since both domains' audit schemas carry the same
    initial_skill/attempt_skills/proposed_skill/retry_count columns
    (confirmed by reading both headers directly before writing this
    function)."""
    n_fail = 0
    for r in aud:
        n_att = len((r.get("attempt_skills") or "").split("|")) if r.get("attempt_skills") else 0
        rc = int(r["retry_count"])
        if n_att != rc + 1:
            n_fail += 1
    if n_fail:
        raise PrepError(f"{where}: {n_fail}/{len(aud)} rows violate "
                         f"len(attempt_skills.split('|')) == retry_count+1")
    n_mismatch = 0
    for r in aud:
        last = (r.get("attempt_skills") or "").split("|")[-1]
        if last != (r.get("proposed_skill") or "").strip():
            n_mismatch += 1
    if n_mismatch:
        raise PrepError(f"{where}: {n_mismatch}/{len(aud)} rows have "
                         f"attempt_skills[-1] != proposed_skill")


def _manifest_census(run_dir: str, domain: str, seed: str, expected_model: str,
                      expected_commit_prefix: str, n_initial_null: int, rows: list,
                      arm: str) -> None:
    """Byte-identical logic to r33's own manifest-census block, generalised
    over (domain, seed, expected_model, expected_commit_prefix). `arm`
    tags this row for `_manifest_commit_hashes()` (e.g. "flood_initprop"/
    "irr_initprop") -- needed because the faf1bb12 band comparator (Part
    A's band check) reuses the SAME seed strings 42-46 as the flood
    initprop target rows, so seed alone cannot disambiguate them."""
    manifest_path = os.path.join(run_dir, "reproducibility_manifest.json")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    model = manifest.get("model")
    git_commit = manifest.get("git_commit")
    thinking_mode = manifest.get("thinking_mode")
    if model != expected_model:
        raise PrepError(f"{manifest_path}: model={model!r}, expected {expected_model!r}")
    if not str(git_commit or "").startswith(expected_commit_prefix):
        raise PrepError(f"{manifest_path}: git_commit={git_commit!r}, expected to start "
                         f"with {expected_commit_prefix!r}")
    manifest_has_flag = "initial_proposal_columns" in json.dumps(manifest)
    config_snapshot_path = os.path.join(run_dir, "config_snapshot.yaml")
    config_flag = None
    if os.path.isfile(config_snapshot_path):
        import yaml
        with open(config_snapshot_path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        config_flag = (cfg.get("global_config", {}) or {}).get("audit", {}).get(
            "initial_proposal_columns")
    rows.append({"row_type": "manifest_census", "domain": domain, "arm": arm, "seed": seed,
                 "model": model, "git_commit_short": git_commit[:8] if git_commit else "",
                 "thinking_mode": thinking_mode,
                 "manifest_has_initial_proposal_key": manifest_has_flag,
                 "config_snapshot_initial_proposal_columns": config_flag,
                 "n_initial_null": n_initial_null})


def _flood_band_manifest_rows(rows: list, corpus: str = "v08") -> None:
    """`manifest_census` rows for the band comparator (faf1bb12 for --corpus
    v08, the defaults baseline strict corpus for --corpus defaults), tagged
    `arm="flood_band_faf1bb12"` (row-schema name kept as-is across corpora
    for CSV-column stability; the `note` field states the actual corpus) --
    kept separate from the initprop target's own `arm="flood_initprop"`
    rows (added via `_manifest_census` above) since both use the same seed
    strings 42-46. Not run through `_manifest_census` itself: this
    comparator predates the initprop flag entirely (r33 Part 3 already
    established it lacks `initial_skill`), so there is nothing to
    value-enforce or count nulls on here, only git_commit/model/
    thinking_mode to report. Only called once at least one initprop target
    seed has landed (see `_part_a_flood`'s early return), so the band
    comparator dir existing is a real regression, not incompleteness, if
    this ever raises."""
    band_root = _flood_band_root(corpus)
    for seed in FLOOD_SEEDS:
        band_dir = os.path.join(C.FLOOD_RESULTS, band_root, f"Run_{seed}")
        manifest_path = os.path.join(band_dir, "reproducibility_manifest.json")
        if not os.path.isfile(manifest_path):
            raise PrepError(f"missing {manifest_path} -- the band comparator "
                             f"({band_root}) is expected to already be complete whenever "
                             f"an initprop target seed has landed")
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        git_commit = manifest.get("git_commit")
        row = {"row_type": "manifest_census", "domain": "flood",
               "arm": "flood_band_faf1bb12", "seed": seed,
               "model": manifest.get("model"),
               "git_commit_short": git_commit[:8] if git_commit else "",
               "thinking_mode": manifest.get("thinking_mode")}
        if corpus != "v08":
            # byte-identity contract: v08 rows carry no "note" field, exactly
            # as before this switch existed.
            row["note"] = f"band comparator root: {band_root}"
        rows.append(row)


def _pooled_sd(sd_first: float, sd_last: float) -> float:
    """Two-sample pooled SD for equal n (Cohen's-d denominator convention):
    sqrt((sd_first^2 + sd_last^2) / 2). See module docstring BACKGROUND for
    why this, not the SD of the paired differences, is used for the audit's
    gate -- flagged there as a judgment call."""
    return ((sd_first ** 2 + sd_last ** 2) / 2.0) ** 0.5


def _diff_and_gate(domain: str, first_vals: dict, last_vals: dict, rows: list,
                    row_prefix: str) -> None:
    """first_vals/last_vals: {seed: rate}. Writes <prefix>_diff (per seed),
    <prefix>_diff_summary, and <prefix>_gate rows. n = number of seeds with
    BOTH a first and a last value (intersection, never padded)."""
    seeds = sorted(set(first_vals) & set(last_vals), key=lambda s: int(s))
    if not seeds:
        return
    diffs = []
    for seed in seeds:
        fv, lv = first_vals[seed], last_vals[seed]
        diff = fv - lv
        diffs.append(diff)
        rows.append({"row_type": f"{row_prefix}_diff", "domain": domain, "seed": seed,
                     "first_ibr": fv, "last_ibr": lv, "diff": diff})
    n = len(diffs)
    mean_diff = C.mean(diffs)
    sd_diff = C.sd(diffs) if n >= 2 else float("nan")
    sd_first_group = C.sd([first_vals[s] for s in seeds]) if n >= 2 else float("nan")
    sd_last_group = C.sd([last_vals[s] for s in seeds]) if n >= 2 else float("nan")
    pooled_sd = (_pooled_sd(sd_first_group, sd_last_group)
                 if n >= 2 else float("nan"))
    perm_p = C.exact_perm_p(diffs)
    rows.append({"row_type": f"{row_prefix}_diff_summary", "domain": domain, "n": n,
                 "mean": mean_diff, "sd": sd_diff, "sd_first_group": sd_first_group,
                 "sd_last_group": sd_last_group, "pooled_sd": pooled_sd,
                 "exact_perm_p": perm_p})
    holds = (n >= 2) and (mean_diff == mean_diff) and (pooled_sd == pooled_sd) and \
            (mean_diff > pooled_sd)
    rows.append({"row_type": f"{row_prefix}_gate", "domain": domain, "n": n,
                 "mean": mean_diff, "pooled_sd": pooled_sd, "holds": holds})


# =============================================================================
# PART A -- flood
# =============================================================================
def _flood_is_violation(tp: str, action: str) -> bool:
    """Per-row IBR-violation predicate, pulled out of `_common.py::
    flood_ibr_components`'s inner loop verbatim (R1: tp HIGH & do_nothing;
    R3: tp LOW & relocate; R4: tp LOW & elevate_house; R5 excluded per
    EDT2, never evaluated here) so it can be evaluated against an
    arbitrary (tp, action) pair -- flood_ibr_components itself always
    reads tp from `construct_TP_LABEL` (final) and cannot be pointed at
    `initial_labels`' TP_LABEL."""
    return ((tp in C.HIGH and action == "do_nothing")
            or (tp in C.LOW and action == "relocate")
            or (tp in C.LOW and action == "elevate_house"))


def _flood_rate(rows_: list, action_fn, tp_fn) -> dict:
    """R1+R3+R4 conditional rate for an arbitrary (action_fn, tp_fn) pair.
    Same formula and same denominator convention (ALL rows, not a HIGH-only
    subset -- R3/R4 are the LOW-conditioned components) as `_common.py::
    flood_ibr_components`, restated here because that function cannot
    source TP from `initial_labels`. Self-tested against the canonical
    function in `_part_a_flood()` below (action=proposed_skill, tp=final)."""
    total = len(rows_)
    if total == 0:
        raise PrepError("_flood_rate called with zero rows")
    num = sum(1 for r in rows_ if _flood_is_violation(tp_fn(r), action_fn(r)))
    return {"numerator": num, "denominator": total, "rate": 100.0 * num / total}


def _flood_initial_tp(row: dict) -> str:
    return R33._parse_labels(row.get("initial_labels") or "").get("TP_LABEL", "").strip().upper()


def _flood_final_tp(row: dict) -> str:
    return C.flood_normalize_tp(row.get("construct_TP_LABEL"))


def _flood_initial_action(row: dict) -> str:
    return C.flood_normalize_action(row.get("initial_skill"))


def _flood_last_attempt_action(row: dict) -> str:
    raw = (row.get("attempt_skills") or "").split("|")[-1]
    return C.flood_normalize_action(raw)


def _flood_walkback_stat(aud: list) -> dict:
    """"Share of first-attempt rule-violating proposals whose last proposal
    is compliant" -- base fixed by the FIRST attempt's own (action, TP);
    walked_back re-checks only the LAST attempt's action against that SAME
    (unchanged) first-attempt TP. Direct analogy to r33's irrigation
    walk-back block (its base = initial_skill in INCREASE & initial WSA
    HIGH; its walked_back = last attempt escapes INCREASE, same fixed
    label) -- see module docstring PART A for the full citation."""
    base = [r for r in aud if _flood_is_violation(_flood_initial_tp(r), _flood_initial_action(r))]
    walked_back = [r for r in base
                   if not _flood_is_violation(_flood_initial_tp(r), _flood_last_attempt_action(r))]
    den = len(base)
    num = len(walked_back)
    return {"numerator": num, "denominator": den,
            "rate": (100.0 * num / den) if den > 0 else float("nan")}


def _flood_target_completeness(run_dir: str) -> tuple:
    """Same four-gate structure as `r35_placebo_retry_irrigation.py::
    _irr_run_completeness`, restated with flood's own audit/sim filenames
    (that function hardcodes irrigation's `C.L.AUDIT_LOG`/`C.L.SIM_LOG`,
    not reusable for flood directly)."""
    if not os.path.isdir(run_dir):
        return "skipped", f"run directory does not exist yet: {run_dir}"
    if not os.path.isfile(os.path.join(run_dir, C.FLOOD_AUDIT)):
        return "skipped", f"{C.FLOOD_AUDIT} not yet written (run in progress)"
    if not os.path.isfile(os.path.join(run_dir, "reproducibility_manifest.json")):
        return "skipped", "reproducibility_manifest.json not yet written (run in progress)"
    ri_path = os.path.join(run_dir, "run_integrity.json")
    if not os.path.isfile(ri_path):
        return "skipped", "run_integrity.json not yet written (run in progress)"
    with open(ri_path, encoding="utf-8") as fh:
        ri = json.load(fh)
    if ri.get("integrity_ok") is not True:
        return "skipped", f"integrity_ok is {ri.get('integrity_ok')!r}, not True"
    return "ok", None


def _part_a_flood(rows: list, corpus: str = "v08") -> None:
    landed_aud: dict = {}          # seed -> audit rows (for pooled_rows concat)
    first_vals: dict = {}          # seed -> first-attempt IBR rate
    last_vals: dict = {}           # seed -> last-proposal IBR rate
    r25_metrics: dict = {}         # seed -> _flood_llm_metrics() dict
    initprop_root = _flood_initprop_root(corpus)

    for seed in FLOOD_SEEDS:
        run_dir = os.path.join(C.FLOOD_RESULTS, initprop_root, f"Run_{seed}")
        status, reason = _flood_target_completeness(run_dir)
        if status == "skipped":
            print(f"  SKIPPED flood seed {seed}: {reason}")
            rows.append({"row_type": "skipped", "domain": "flood", "section": "target",
                         "seed": seed, "reason": reason})
            continue

        aud_path = os.path.join(run_dir, C.FLOOD_AUDIT)
        aud = C.read_csv(aud_path)
        C.require_cols(aud, AUDIT_ATTEMPT_COLS + ["construct_TP_LABEL"], aud_path)
        _check_attempt_invariants(aud, aud_path)
        n_initial_null = sum(1 for r in aud if not (r.get("initial_skill") or "").strip())

        first = _flood_rate(aud, _flood_initial_action, _flood_initial_tp)
        last = _flood_rate(aud, C.flood_proposal, _flood_final_tp)
        executed = _flood_rate(aud, C.flood_executed, _flood_final_tp)

        # self-test: my own _flood_rate(proposed_skill, final) must equal the
        # canonical library function computed on the SAME audit rows.
        canonical_last = C.flood_ibr_components(aud, C.flood_proposal)["ibr_pct"]
        if abs(canonical_last - last["rate"]) > 1e-9:
            raise PrepError(f"{aud_path}: _flood_rate self-test failed -- "
                             f"{last['rate']:.6f}% vs canonical "
                             f"flood_ibr_components={canonical_last:.6f}%")

        for action_name, r in (("initial_skill", first), ("proposed_skill", last),
                               ("executed", executed)):
            rows.append({"row_type": "flood_ibr", "domain": "flood", "seed": seed,
                         "action": action_name, "numerator": r["numerator"],
                         "denominator": r["denominator"], "rate": r["rate"]})
        first_vals[seed] = first["rate"]
        last_vals[seed] = last["rate"]
        landed_aud[seed] = aud

        wb = _flood_walkback_stat(aud)
        rows.append({"row_type": "flood_walkback", "domain": "flood", "seed": seed,
                     "numerator": wb["numerator"], "denominator": wb["denominator"],
                     "rate": wb["rate"]})

        m = R25._flood_llm_metrics(run_dir)
        r25_metrics[seed] = m
        print(f"  OK flood seed {seed}: first={first['rate']:.2f}% last={last['rate']:.2f}% "
              f"executed={executed['rate']:.2f}% walkback={wb['rate']:.2f}% "
              f"r25_ibr_headline={m['ibr_headline']:.2f}%")

        _manifest_census(run_dir, "flood", seed, FLOOD_MODEL, FLOOD_COMMIT_PREFIX,
                          n_initial_null, rows, arm="flood_initprop")

    landed_seeds = sorted(landed_aud, key=lambda s: int(s))
    if not landed_seeds:
        print("  no flood seeds landed -- Part A produces no pooled/summary/gate/band rows")
        return

    # ---- pooled (rows combined) ------------------------------------------------
    all_rows = [r for seed in landed_seeds for r in landed_aud[seed]]
    first_pooled = _flood_rate(all_rows, _flood_initial_action, _flood_initial_tp)
    last_pooled = _flood_rate(all_rows, C.flood_proposal, _flood_final_tp)
    exec_pooled = _flood_rate(all_rows, C.flood_executed, _flood_final_tp)
    for action_name, r in (("initial_skill", first_pooled), ("proposed_skill", last_pooled),
                           ("executed", exec_pooled)):
        rows.append({"row_type": "flood_ibr", "domain": "flood", "seed": "pooled_rows",
                     "action": action_name, "numerator": r["numerator"],
                     "denominator": r["denominator"], "rate": r["rate"]})
    wb_pooled = _flood_walkback_stat(all_rows)
    rows.append({"row_type": "flood_walkback", "domain": "flood", "seed": "pooled_rows",
                 "numerator": wb_pooled["numerator"], "denominator": wb_pooled["denominator"],
                 "rate": wb_pooled["rate"]})

    # ---- mean +/- sd across landed seeds ----------------------------------------
    for action_name, val_map in (("initial_skill", first_vals), ("proposed_skill", last_vals)):
        vals = [val_map[s] for s in landed_seeds]
        n = len(vals)
        rows.append({"row_type": "flood_ibr_summary", "domain": "flood",
                     "action": action_name, "n": n, "mean": C.mean(vals),
                     "sd": C.sd(vals) if n >= 2 else float("nan")})
    exec_vals = [r["rate"] for seed in landed_seeds
                 for r in [_flood_rate(landed_aud[seed], C.flood_executed, _flood_final_tp)]]
    rows.append({"row_type": "flood_ibr_summary", "domain": "flood", "action": "executed",
                 "n": len(exec_vals), "mean": C.mean(exec_vals),
                 "sd": C.sd(exec_vals) if len(exec_vals) >= 2 else float("nan")})
    wb_vals = [_flood_walkback_stat(landed_aud[s])["rate"] for s in landed_seeds]
    wb_vals = [v for v in wb_vals if v == v]  # drop nan (empty-base seeds, none expected)
    rows.append({"row_type": "flood_walkback_summary", "domain": "flood", "n": len(wb_vals),
                 "mean": C.mean(wb_vals) if wb_vals else float("nan"),
                 "sd": C.sd(wb_vals) if len(wb_vals) >= 2 else float("nan")})

    # ---- diff + gate --------------------------------------------------------------
    _diff_and_gate("flood", first_vals, last_vals, rows, "flood")

    # ---- band check vs strict 5-seed band (faf1bb12 for v08, the defaults
    # baseline strict corpus for --corpus defaults) --------------------------------
    band_root = _flood_band_root(corpus)
    _flood_band_manifest_rows(rows, corpus)
    band_seed_vals = {"ibr_headline": [], "ehe_pooled": [], "final_year_protection_pct": []}
    for seed in FLOOD_SEEDS:
        band_dir = os.path.join(C.FLOOD_RESULTS, band_root, f"Run_{seed}")
        bm = R25._flood_llm_metrics(band_dir)
        for k in band_seed_vals:
            band_seed_vals[k].append(bm[k])
    band_stats = {k: {"mean": C.mean(v), "sd": C.sd(v)} for k, v in band_seed_vals.items()}
    metric_labels = {"ibr_headline": "IBR headline", "ehe_pooled": "EHE pooled",
                     "final_year_protection_pct": "Final-year protection %"}
    for metric_key, label in metric_labels.items():
        b = band_stats[metric_key]
        lo, hi = b["mean"] - 2 * b["sd"], b["mean"] + 2 * b["sd"]
        vals = []
        for seed in landed_seeds:
            v = r25_metrics[seed][metric_key]
            vals.append(v)
            inside = lo <= v <= hi
            rows.append({"row_type": "flood_band", "domain": "flood", "metric": label,
                         "seed": seed, "arm_value": v, "band_mean": b["mean"],
                         "band_sd": b["sd"], "band_lo": lo, "band_hi": hi,
                         "inside_band": inside})
        pooled_mean_val = C.mean(vals)
        inside_pooled = lo <= pooled_mean_val <= hi
        rows.append({"row_type": "flood_band", "domain": "flood", "metric": label,
                     "seed": f"mean(n={len(vals)})", "arm_value": pooled_mean_val,
                     "band_mean": b["mean"], "band_sd": b["sd"], "band_lo": lo,
                     "band_hi": hi, "inside_band": inside_pooled})
        print(f"  band {label}: initprop mean(n={len(vals)})={pooled_mean_val:.4f} vs "
              f"{band_root} band [{lo:.4f}, {hi:.4f}] -> "
              f"{'INSIDE' if inside_pooled else 'OUTSIDE'}")


# =============================================================================
# PART B -- irrigation
# =============================================================================
def _irr_walkback(aud: list) -> dict:
    """Byte-identical to r33's own inline walk-back block
    (r33_first_vs_last_proposal.py lines 308-315), re-declared here since
    r33 does not export it as a reusable function."""
    base = [r for r in aud if (r.get("initial_skill") or "").strip() in L.INCREASE
            and R33._initial_wsa(r) in L.HIGH]
    walked_back = [r for r in base
                   if (r.get("attempt_skills") or "").split("|")[-1] not in L.INCREASE]
    den = len(base)
    num = len(walked_back)
    return {"numerator": num, "denominator": den,
            "rate": (100.0 * num / den) if den > 0 else float("nan")}


def _part_b_irrigation(rows: list) -> None:
    landed_aud: dict = {}
    first_vals: dict = {}
    last_vals: dict = {}
    commit_seen: dict = {}

    for seed in IRR_SEEDS:
        run_dir, expected_commit = IRR_SEED_DIRS[seed]
        status, reason = R35._irr_run_completeness(run_dir)
        if status == "skipped":
            print(f"  SKIPPED irrigation seed {seed}: {reason}")
            rows.append({"row_type": "skipped", "domain": "irrigation", "section": "target",
                         "seed": seed, "reason": reason})
            continue

        aud_path = os.path.join(run_dir, C.L.AUDIT_LOG)
        aud = C.read_csv(aud_path)
        C.require_cols(aud, AUDIT_ATTEMPT_COLS + ["construct_WSA_LABEL"], aud_path)
        _check_attempt_invariants(aud, aud_path)
        n_initial_null = sum(1 for r in aud if not (r.get("initial_skill") or "").strip())

        first = R33._rate(aud, lambda r: (r.get("initial_skill") or "").strip(), R33._initial_wsa)
        last = R33._rate(aud, lambda r: (r.get("proposed_skill") or "").strip(), R33._final_wsa)
        executed = R33._rate(aud, C.irr_executed, R33._final_wsa)
        R33._crosscheck_published_ibr(run_dir, aud, f"irrigation seed {seed}")

        for action_name, r in (("initial_skill", first), ("proposed_skill", last),
                               ("executed", executed)):
            rows.append({"row_type": "irr_ibr", "domain": "irrigation", "seed": seed,
                         "action": action_name, "numerator": r["numerator"],
                         "denominator": r["denominator"], "rate": r["rate"]})
        first_vals[seed] = first["rate"]
        last_vals[seed] = last["rate"]
        landed_aud[seed] = aud

        wb = _irr_walkback(aud)
        rows.append({"row_type": "irr_walkback", "domain": "irrigation", "seed": seed,
                     "numerator": wb["numerator"], "denominator": wb["denominator"],
                     "rate": wb["rate"]})
        print(f"  OK irrigation seed {seed} ({expected_commit}): first={first['rate']:.2f}% "
              f"last={last['rate']:.2f}% executed={executed['rate']:.2f}% "
              f"walkback={wb['rate']:.2f}%")

        _manifest_census(run_dir, "irrigation", seed, IRR_MODEL, expected_commit,
                          n_initial_null, rows, arm="irr_initprop")
        commit_seen[seed] = expected_commit

    landed_seeds = sorted(landed_aud, key=lambda s: int(s))
    if not landed_seeds:
        print("  no irrigation seeds landed -- Part B produces no pooled/summary/gate rows")
        return

    all_rows = [r for seed in landed_seeds for r in landed_aud[seed]]
    first_pooled = R33._rate(all_rows, lambda r: (r.get("initial_skill") or "").strip(),
                             R33._initial_wsa)
    last_pooled = R33._rate(all_rows, lambda r: (r.get("proposed_skill") or "").strip(),
                            R33._final_wsa)
    exec_pooled = R33._rate(all_rows, C.irr_executed, R33._final_wsa)
    for action_name, r in (("initial_skill", first_pooled), ("proposed_skill", last_pooled),
                           ("executed", exec_pooled)):
        rows.append({"row_type": "irr_ibr", "domain": "irrigation", "seed": "pooled_rows",
                     "action": action_name, "numerator": r["numerator"],
                     "denominator": r["denominator"], "rate": r["rate"]})
    wb_pooled = _irr_walkback(all_rows)
    rows.append({"row_type": "irr_walkback", "domain": "irrigation", "seed": "pooled_rows",
                 "numerator": wb_pooled["numerator"], "denominator": wb_pooled["denominator"],
                 "rate": wb_pooled["rate"]})

    for action_name, val_map in (("initial_skill", first_vals), ("proposed_skill", last_vals)):
        vals = [val_map[s] for s in landed_seeds]
        n = len(vals)
        rows.append({"row_type": "irr_ibr_summary", "domain": "irrigation",
                     "action": action_name, "n": n, "mean": C.mean(vals),
                     "sd": C.sd(vals) if n >= 2 else float("nan")})
    exec_vals = [R33._rate(landed_aud[s], C.irr_executed, R33._final_wsa)["rate"]
                 for s in landed_seeds]
    rows.append({"row_type": "irr_ibr_summary", "domain": "irrigation", "action": "executed",
                 "n": len(exec_vals), "mean": C.mean(exec_vals),
                 "sd": C.sd(exec_vals) if len(exec_vals) >= 2 else float("nan")})
    wb_vals = [_irr_walkback(landed_aud[s])["rate"] for s in landed_seeds]
    wb_vals = [v for v in wb_vals if v == v]
    rows.append({"row_type": "irr_walkback_summary", "domain": "irrigation", "n": len(wb_vals),
                 "mean": C.mean(wb_vals) if wb_vals else float("nan"),
                 "sd": C.sd(wb_vals) if len(wb_vals) >= 2 else float("nan")})

    _diff_and_gate("irrigation", first_vals, last_vals, rows, "irr")

    commits = sorted(set(commit_seen.values()))
    rows.append({"row_type": "irr_commit_mix", "domain": "irrigation",
                 "note": "; ".join(f"seed {s}: {c}" for s, c in sorted(commit_seen.items(),
                                                                        key=lambda kv: int(kv[0])))})


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "domain", "arm", "section", "seed", "action", "metric", "numerator",
    "denominator", "rate", "first_ibr", "last_ibr", "diff", "n", "mean", "sd",
    "sd_first_group", "sd_last_group", "pooled_sd", "exact_perm_p", "holds", "arm_value",
    "band_mean", "band_sd", "band_lo", "band_hi", "inside_band", "model", "git_commit_short",
    "thinking_mode", "manifest_has_initial_proposal_key",
    "config_snapshot_initial_proposal_columns", "n_initial_null", "note", "reason",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="R41 -- first-attempt vs last-proposal IBR (Part A/flood is "
                     "--corpus-aware; Part B/irrigation is not)")
    C.add_corpus_arg(parser)
    args = parser.parse_args()
    corpus = args.corpus
    suffix = C.corpus_suffix(corpus)

    C.banner(f"R41  First-attempt vs last-proposal IBR: flood n=5 (corpus={corpus}), "
             f"irrigation n=3")
    rows: list = []

    print(f"\n-- Part A: flood ({_flood_initprop_root(corpus)}, n=5) --")
    _part_a_flood(rows, corpus)

    print("\n-- Part B: irrigation (seed 42 c3391a53 + seeds 43-44 83fa97e1, n=3, "
          "always v08 -- unaffected by --corpus) --")
    _part_b_irrigation(rows)

    md_text = render_md(rows, corpus)

    csv_final = f"r41_first_vs_last_n5{suffix}.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, f"r41_first_vs_last_n5{suffix}.md")
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


def _is_nan(x) -> bool:
    return isinstance(x, float) and x != x


def _find(rows, row_type, **kw):
    out = []
    for r in rows:
        if r.get("row_type") != row_type:
            continue
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


def _manifest_commit_hashes(rows: list, target_arms: list, comparator_arms: list) -> tuple:
    """(target_hash, comparator_hash), pulled from `manifest_census` rows'
    `git_commit_short` -- never hard-coded, so the Method-section
    provenance caveat cannot drift from the actual run. Byte-identical
    logic to r35_placebo_retry_irrigation.py's and
    r36_no_ceiling_ablation.py's own `_manifest_commit_hashes` (re-declared
    here, not imported, since neither exports it as a reusable
    module-level name), param name `target_arms` generalised from r35's
    `placebo_arms` / r36's `treatment_arms` since r41's manipulated arm is
    the initprop flood corpus, not a placebo or an ablation. Raises if the
    arm(s) have no manifest rows yet, or if git_commit_short disagrees
    within an arm (across seeds) or between arms -- a disagreement there
    would mean the provenance claim itself is false, never something to
    paper over."""
    def _one(arms: list) -> str:
        vals = {r["git_commit_short"] for r in _find(rows, "manifest_census")
                if r.get("arm") in arms}
        if not vals:
            raise PrepError(f"no manifest_census rows yet for arm(s) {arms} -- cannot render "
                             f"the code-provenance caveat")
        if len(vals) > 1:
            raise PrepError(f"manifest_census git_commit_short disagrees within/between "
                             f"arm(s) {arms}: {sorted(vals)} -- the code-provenance caveat "
                             f"cannot be rendered as a single hash")
        return next(iter(vals))
    return _one(target_arms), _one(comparator_arms)


def _render_ibr_table(lines: list, rows: list, domain: str, seeds: list) -> None:
    lines.append("| seed | first-attempt (initial_skill) | last-proposal (proposed_skill) | "
                 "executed |")
    lines.append("|---|---|---|---|")
    row_order = seeds + ["pooled_rows"]
    for seed in row_order:
        cells = []
        for action in ("initial_skill", "proposed_skill", "executed"):
            recs = _find(rows, f"{domain}_ibr", seed=seed, action=action)
            if not recs:
                cells.append("PENDING")
            else:
                r = recs[0]
                cells.append(f"{_cp(r['rate']):.2f}% ({r['numerator']}/{r['denominator']})")
        label = "pooled (rows combined)" if seed == "pooled_rows" else seed
        lines.append(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines.append("")
    lines.append("Mean +/- sd across landed seeds:")
    lines.append("")
    lines.append("| action | n | mean (%) | sd |")
    lines.append("|---|---|---|---|")
    for action in ("initial_skill", "proposed_skill", "executed"):
        recs = _find(rows, f"{domain}_ibr_summary", action=action)
        if not recs:
            lines.append(f"| {action} | -- | PENDING | -- |")
            continue
        r = recs[0]
        sd_cell = "n.a. (n<2)" if _is_nan(r["sd"]) else f"{_cp(r['sd']):.3f}"
        lines.append(f"| {action} | {r['n']} | {_cp(r['mean']):.2f} | {sd_cell} |")
    lines.append("")


def _render_walkback_table(lines: list, rows: list, domain: str, seeds: list) -> None:
    lines.append("| seed | numerator | denominator | rate (%) |")
    lines.append("|---|---|---|---|")
    for seed in seeds + ["pooled_rows"]:
        recs = _find(rows, f"{domain}_walkback", seed=seed)
        label = "pooled (rows combined)" if seed == "pooled_rows" else seed
        if not recs:
            lines.append(f"| {label} | -- | -- | PENDING |")
            continue
        r = recs[0]
        rate_cell = "n.a. (empty base)" if _is_nan(r["rate"]) else f"{_cp(r['rate']):.2f}"
        lines.append(f"| {label} | {r['numerator']} | {r['denominator']} | {rate_cell} |")
    lines.append("")
    summ = _find(rows, f"{domain}_walkback_summary")
    if summ:
        s = summ[0]
        sd_cell = "n.a. (n<2)" if _is_nan(s["sd"]) else f"{_cp(s['sd']):.3f}"
        lines.append(f"Mean walk-back rate across landed seeds (n={s['n']}): "
                     f"{_cp(s['mean']):.2f}% (sd {sd_cell}).")
        lines.append("")


def _render_diff_gate(lines: list, rows: list, prefix: str, domain_label: str,
                      audit_quote_floor: str) -> tuple:
    """Returns (mean_diff, pooled_sd, holds, n) or (None,)*4 if no data."""
    diffs = _find(rows, f"{prefix}_diff")
    lines.append("| seed | first-attempt IBR (%) | last-proposal IBR (%) | diff (first-last) |")
    lines.append("|---|---|---|---|")
    for r in diffs:
        lines.append(f"| {r['seed']} | {_cp(r['first_ibr']):.2f} | {_cp(r['last_ibr']):.2f} | "
                     f"{_cp(r['diff']):.2f} |")
    lines.append("")
    summ = _find(rows, f"{prefix}_diff_summary")
    gate = _find(rows, f"{prefix}_gate")
    if not summ:
        lines.append("PENDING -- fewer than 1 landed seed pair, no diff statistics yet.")
        lines.append("")
        return None, None, None, 0
    s = summ[0]
    n = s["n"]
    if n < 2:
        lines.append(f"n={n} landed seed(s) -- sd/permutation test/gate need at least 2 "
                     f"paired seeds, not yet computed.")
        lines.append("")
        return None, None, None, n
    lines.append(f"n={n}: mean diff = {_cp(s['mean']):.3f} pp, sd of diffs (ddof=1) = "
                 f"{_cp(s['sd']):.3f} pp, sd(first group) = {_cp(s['sd_first_group']):.3f}, "
                 f"sd(last group) = {_cp(s['sd_last_group']):.3f}, pooled sd = "
                 f"{_cp(s['pooled_sd']):.3f} pp, exact permutation p (paired sign, floor "
                 f"{audit_quote_floor}) = {_cp(s['exact_perm_p']):.4f}.")
    lines.append("")
    g = gate[0] if gate else None
    holds = g["holds"] if g else None
    if g is not None:
        if holds:
            lines.append(
                f"**Decision rule (audit, verbatim): \"if the five-seed first-attempt IBR "
                f"mean exceeds the last-proposal mean by more than the pooled standard "
                f"deviation, 'negotiation, not relabelling' holds ... and can be printed as "
                f"a headline.\"** At n={n} on {domain_label}, mean diff "
                f"({_cp(s['mean']):.3f} pp) EXCEEDS the pooled sd ({_cp(s['pooled_sd']):.3f} "
                f"pp): the gate is MET -- \"negotiation, not relabelling\" holds and may be "
                f"printed as a headline on this corpus."
            )
        else:
            lines.append(
                f"**Decision rule (audit, verbatim): \"if the gap falls inside one standard "
                f"deviation, drop the claim and keep only the walk-back rate ... which is "
                f"descriptive and does not need the contrast.\"** At n={n} on {domain_label}, "
                f"mean diff ({_cp(s['mean']):.3f} pp) does NOT exceed the pooled sd "
                f"({_cp(s['pooled_sd']):.3f} pp): the gate is NOT met -- drop the first-vs-"
                f"last IBR contrast as a headline and report only this domain's own "
                f"walk-back rate (see the table above)."
            )
        lines.append("")
    return s["mean"], s["pooled_sd"], holds, n


def render_md(rows: list, corpus: str = "v08") -> str:
    lines = []
    lines.append("# R41 -- first-attempt vs last-proposal IBR (flood n=5, irrigation n=3)")
    lines.append("")
    lines.append("Source: `r41_first_vs_last_n5.py`. Every number below is read live from the "
                 "`rows` list this script writes to the paired CSV. Extends r33's single-seed "
                 "irrigation result; see that script and `out/r33_first_vs_last_proposal.md` "
                 "for the single-seed baseline this corpus builds on.")
    lines.append("")
    if corpus != "v08":
        lines.append(f"> **Flood corpus: {corpus}.** {C.flood_sampling_method_text(corpus)}. "
                     f"Part B (irrigation) is UNCHANGED (always v08). Part A's band "
                     f"comparator is the {corpus} baseline strict corpus, NOT faf1bb12.")
        lines.append("")

    # ---- Part A: flood ----------------------------------------------------------
    lines.append(f"## Part A -- flood (`{_flood_initprop_root(corpus)}`, seeds 42-46, "
                 f"n=5)")
    lines.append("")
    flood_landed = sorted({r["seed"] for r in _find(rows, "flood_ibr")
                          if r["seed"] != "pooled_rows" and r.get("action") == "initial_skill"},
                         key=lambda s: int(s))
    flood_pending = [s for s in FLOOD_SEEDS if s not in flood_landed]
    if flood_pending:
        lines.append(f"Landed seeds: {', '.join(flood_landed) or 'none'}. PENDING: "
                     f"{', '.join(flood_pending)}.")
        lines.append("")

    lines.append("### IBR: first-attempt vs last-proposal vs executed")
    lines.append("")
    _render_ibr_table(lines, rows, "flood", FLOOD_SEEDS)

    lines.append("### Walk-back rate (first-attempt rule-violating proposals whose last "
                 "proposal is compliant)")
    lines.append("")
    _render_walkback_table(lines, rows, "flood", FLOOD_SEEDS)

    lines.append("### First-minus-last difference, sd, exact permutation p, and the audit's "
                 "gate")
    lines.append("")
    flood_mean_diff, flood_pooled_sd, flood_holds, flood_n = _render_diff_gate(
        lines, rows, "flood", "flood (this corpus)", "2/2^5 = 0.0625 at n=5")

    band_root = _flood_band_root(corpus)
    lines.append(f"### Band check vs `{band_root}` 5-seed band (mean +/- 2 sd)")
    lines.append("")
    band_metrics = ["IBR headline", "EHE pooled", "Final-year protection %"]
    band_rows = _find(rows, "flood_band")
    if not band_rows:
        lines.append("PENDING -- no landed initprop seeds yet.")
        lines.append("")
    else:
        lines.append("| metric | seed | arm value | band (mean +/- 2 sd) | inside band? |")
        lines.append("|---|---|---|---|---|")
        for metric in band_metrics:
            for r in _find(rows, "flood_band", metric=metric):
                lines.append(f"| {metric} | {r['seed']} | {_cp(r['arm_value']):.4f} | "
                             f"[{_cp(r['band_lo']):.4f}, {_cp(r['band_hi']):.4f}] "
                             f"(mean {_cp(r['band_mean']):.4f}, sd {_cp(r['band_sd']):.4f}) | "
                             f"{'YES' if r['inside_band'] else 'NO'} |")
        lines.append("")
        all_inside = all(r["inside_band"] for r in band_rows if r["seed"].startswith("mean("))
        outliers = [r for r in band_rows if not r["inside_band"]
                   and not str(r["seed"]).startswith("mean(")]
        if not outliers:
            outlier_clause = "no individual seed falls outside any metric's band"
        elif len(outliers) == 1:
            o = outliers[0]
            outlier_clause = (f"one seed ({o['seed']}) falls outside on {o['metric']} alone "
                              f"({_cp(o['arm_value']):.4f} against [{_cp(o['band_lo']):.4f}, "
                              f"{_cp(o['band_hi']):.4f}])")
        else:
            outlier_clause = "; ".join(
                f"seed {o['seed']} falls outside on {o['metric']} alone "
                f"({_cp(o['arm_value']):.4f} against [{_cp(o['band_lo']):.4f}, "
                f"{_cp(o['band_hi']):.4f}])" for o in outliers)
        # band_label: v08 keeps its original hand-written wording verbatim
        # ("faf1bb12 strict 5-seed") -- byte-identity contract for that
        # corpus. Any other corpus derives its label from band_root itself
        # (never the v08-specific "faf1bb12" literal) and states the seed
        # count/seeds forming the band explicitly, since the comparator
        # directory name alone does not say how many seeds were pooled.
        band_label = ("faf1bb12 strict 5-seed" if corpus == "v08"
                      else f"{corpus} strict 5-seed (`{band_root}`, seeds "
                           f"{'-'.join([FLOOD_SEEDS[0], FLOOD_SEEDS[-1]])}, n={len(FLOOD_SEEDS)})")
        lines.append(f"All three pooled (mean-of-landed-seeds) metrics fall "
                     f"{'INSIDE' if all_inside else 'OUTSIDE (at least one metric)'} the "
                     f"{band_label} band -- the initprop flag "
                     f"{'did not' if all_inside else 'DID'} visibly shift governed behaviour "
                     f"relative to the pre-initprop strict corpus, except {outlier_clause}.")
        lines.append("")

        initprop_hash, band_hash = _manifest_commit_hashes(
            rows, target_arms=["flood_initprop"], comparator_arms=["flood_band_faf1bb12"])
        if corpus == "v08":
            lines.append(
                f"The initprop arm was run at code {initprop_hash} while the strict 5-seed "
                f"comparator band comes from {band_hash}. The comparison is accepted on three "
                f"pieces of evidence recorded in out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md: "
                f"the only framework change between c3391a53 and 83fa97e1 is PR #46 (eleven "
                f"files, all plumbing for the retry_feedback_mode feature), whose only "
                f"behaviour-changing branch is in the domain-generic retry loop "
                f"broker/core/_retry_loop.py (RetryMixin._governance_retry_loop); the full-mode "
                f"retry prompt rendered by that loop is byte-identical across the two commits "
                f"for both the rule-violation and the format-violation branch; and mock runs at "
                f"both commits give identical governance-audit and simulation logs for flood (4 "
                f"of 4 comparisons) and for irrigation (4 of 4, strict and disabled, synthetic "
                f"agents). The earlier faf1bb12 -> c3391a53 gate in "
                f"out/regen_progress_2026-09-15.md covers both domains."
            )
        elif initprop_hash == band_hash:
            lines.append(
                f"The initprop arm and the {corpus} strict 5-seed comparator band were both "
                f"run at code {initprop_hash} -- the SAME commit, so this comparison carries "
                f"none of the v08 corpus's c3391a53/83fa97e1 code-provenance question (there "
                f"is no commit difference to justify here); any gap between the two arms is "
                f"attributable to the initprop flag alone."
            )
        else:
            lines.append(
                f"The initprop arm was run at code {initprop_hash} while the {corpus} strict "
                f"5-seed comparator band comes from {band_hash} -- these differ, and unlike "
                f"the v08 corpus this script has no recorded mock-equivalence chain "
                f"justifying pooling across them for the {corpus} corpus; treat this band "
                f"check as provisional until one is recorded."
            )
        lines.append("")

    # ---- Part B: irrigation -------------------------------------------------------
    lines.append("## Part B -- irrigation (seed 42 c3391a53 + seeds 43-44 83fa97e1, n=3)")
    lines.append("")
    irr_landed = sorted({r["seed"] for r in _find(rows, "irr_ibr")
                        if r["seed"] != "pooled_rows" and r.get("action") == "initial_skill"},
                       key=lambda s: int(s))
    irr_pending = [s for s in IRR_SEEDS if s not in irr_landed]
    if irr_pending:
        lines.append(f"Landed seeds: {', '.join(irr_landed) or 'none'}. PENDING: "
                     f"{', '.join(irr_pending)} (still running).")
        lines.append("")

    commit_mix = _find(rows, "irr_commit_mix")
    if commit_mix:
        lines.append(f"Commit mix (from each run's own manifest, never assumed): "
                     f"{commit_mix[0]['note']}. Pooling across c3391a53 and 83fa97e1 for this "
                     f"feature is accepted on the three-piece evidence chain in "
                     f"`{MOCK_EQUIV_NOTE}`; the earlier faf1bb12 -> c3391a53 gate is recorded "
                     f"in `{REGEN_GATE_NOTE}`.")
        lines.append("")

    lines.append("### IBR: first-attempt vs last-proposal vs executed")
    lines.append("")
    _render_ibr_table(lines, rows, "irr", IRR_SEEDS)

    lines.append("### Walk-back rate (first-attempt increase under high first-attempt WSA "
                 "whose last attempt is maintain/decrease)")
    lines.append("")
    _render_walkback_table(lines, rows, "irr", IRR_SEEDS)

    lines.append("### First-minus-last difference, sd, exact permutation p, and the audit's "
                 "gate")
    lines.append("")
    irr_mean_diff, irr_pooled_sd, irr_holds, irr_n = _render_diff_gate(
        lines, rows, "irr", "irrigation (this corpus)",
        "2/2^n (n=2 -> 0.5, n=3 -> 0.25; the audit's 0.0625 floor is stated for n=5, which "
        "irrigation does not reach in this step)")

    # ---- Part C: provenance census -------------------------------------------------
    lines.append("## Part C -- provenance census")
    lines.append("")
    lines.append("`initial_proposal_columns` never appears in `reproducibility_manifest.json` "
                 "on any run in this package (confirmed per run below, consistent with r33's "
                 "own finding) -- it is recorded only in `config_snapshot.yaml`'s "
                 "`global_config.audit.initial_proposal_columns`. \"rows where initial_skill "
                 "is null\" is read as \"rows where initial_skill is the empty string after "
                 "stripping\" -- the audit CSVs carry no distinct NULL cell type (see Method).")
    lines.append("")
    lines.append("| domain | seed | model | git_commit | thinking_mode | manifest has key? | "
                 "config_snapshot flag | empty initial_skill rows |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for domain, seeds, target_arm in (("flood", FLOOD_SEEDS, "flood_initprop"),
                                       ("irrigation", IRR_SEEDS, "irr_initprop")):
        for seed in seeds:
            # arm=target_arm excludes Part A's faf1bb12 band-comparator rows,
            # which share these same seed strings (42-46) on domain=flood.
            recs = _find(rows, "manifest_census", domain=domain, seed=seed, arm=target_arm)
            if not recs:
                lines.append(f"| {domain} | {seed} | PENDING | -- | -- | -- | -- | -- |")
                continue
            r = recs[0]
            lines.append(f"| {domain} | {seed} | {r['model']} | {r['git_commit_short']}... | "
                         f"{r['thinking_mode']} | {r['manifest_has_initial_proposal_key']} | "
                         f"{r['config_snapshot_initial_proposal_columns']} | "
                         f"{r['n_initial_null']} |")
    lines.append("")

    # ---- Plain read ---------------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    if flood_n and flood_n >= 2:
        lines.append(
            f"Flood, n={flood_n}: pooled first-attempt IBR "
            f"{_cp(_find(rows, 'flood_ibr', seed='pooled_rows', action='initial_skill')[0]['rate']):.2f}%"
            f" vs pooled last-proposal IBR "
            f"{_cp(_find(rows, 'flood_ibr', seed='pooled_rows', action='proposed_skill')[0]['rate']):.2f}%"
            f" (rows combined across the {flood_n} landed seed(s)); mean per-seed diff "
            f"{_cp(flood_mean_diff):.3f} pp against a pooled sd of {_cp(flood_pooled_sd):.3f} "
            f"pp -- gate {'MET' if flood_holds else 'NOT MET'}."
        )
        lines.append("")
    if irr_n and irr_n >= 2:
        lines.append(
            f"Irrigation, n={irr_n} (of 3 target seeds; seed 44 {'PENDING' if irr_pending else 'landed'}): "
            f"pooled first-attempt IBR "
            f"{_cp(_find(rows, 'irr_ibr', seed='pooled_rows', action='initial_skill')[0]['rate']):.2f}%"
            f" vs pooled last-proposal IBR "
            f"{_cp(_find(rows, 'irr_ibr', seed='pooled_rows', action='proposed_skill')[0]['rate']):.2f}%"
            f"; mean per-seed diff {_cp(irr_mean_diff):.3f} pp against a pooled sd of "
            f"{_cp(irr_pooled_sd):.3f} pp -- gate {'MET' if irr_holds else 'NOT MET'}. This "
            f"is n={irr_n}, not the five-seed n the audit's decision rule was framed for -- "
            f"reported at the n this corpus actually has, not extrapolated."
        )
        lines.append("")
    irr_floor_desc = (f"2/2^{irr_n} = {_cp(2.0 / (2 ** irr_n)):.4f}" if irr_n
                      else "not yet computable (fewer than 2 landed seeds)")
    lines.append(
        f"This whole script computes exact permutation tests, not asymptotic ones, and at "
        f"n=5 (flood) the floor is 2/32 = 0.0625; at irrigation's landed n ({irr_n or 0}) "
        f"the floor is {irr_floor_desc} -- none of these p-values should be read as passing "
        f"a conventional 0.05 significance bar just because a number is printed."
    )
    lines.append("")

    # ---- Method ---------------------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "Flood IBR formula = R1+R3+R4 (R5 excluded per EDT2), canonical at "
        "`examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py "
        "(compute_ibr_components)`, transcribed as `_common.py (flood_ibr_components)`; "
        "this script's own `_flood_rate()` restates "
        "the same per-row predicate (`_flood_is_violation`) so it can be evaluated against "
        "`initial_labels`' first-attempt TP_LABEL as well as `construct_TP_LABEL` (final) -- "
        "self-tested against `_common.py (flood_ibr_components)` directly on "
        "action=proposed_skill/label=final (raises on disagreement, verified live on every "
        "landed seed, never assumed). Irrigation IBR formula = "
        "`SUBMISSION_2026/decomposition/_loader.py (ibr)`'s own conditional-high-WSA-"
        "increase-rate formula, reused via `r33_first_vs_last_proposal.py (_rate, "
        "_initial_wsa, _final_wsa, _crosscheck_published_ibr)` unmodified -- this script adds "
        "no new irrigation IBR logic, only iterates it over 3 seeds instead of r33's 1 and "
        "adds the pooled/diff/gate layer. Executed action = `_common.py (irr_executed)` for "
        "irrigation, `_common.py (flood_executed)` for flood -- both remap a REJECTED "
        "proposal to the domain's registry default (`maintain_demand` / `do_nothing`) and "
        "otherwise use `final_skill`. The exact permutation test is `_common.py "
        "(exact_perm_p)`, reused unmodified (all 2^n sign-flip assignments on the paired "
        "per-seed differences); \"pooled standard deviation\" for the audit's gate is this "
        "script's own `_pooled_sd()` = sqrt((sd_first^2 + sd_last^2)/2), the standard "
        "two-sample equal-n pooled-SD (Cohen's-d denominator) convention -- the audit text "
        "does not define this term itself, so this is a flagged judgment call, distinct from "
        "the SD of the paired differences (also reported, separately). Flood's band-check "
        "metrics (`IBR headline`, `EHE pooled`, `final_year_protection_pct`) are "
        "`r25_table1_regen.py (_flood_llm_metrics)`, imported unmodified -- note its own "
        "`ibr_headline` uses action=final_skill (`r23_flood_strict_regen.py`'s "
        "`LEVELS[\"final\"]`), a different action-column choice from this script's own "
        "\"last-proposal\" cell (action=proposed_skill, matching r33's irrigation naming); "
        "both are reported side by side, never asserted identical. Walk-back rate for both "
        "domains holds the FIRST-attempt label fixed and re-checks only the terminal action "
        "-- flood's `_flood_walkback_stat()` and irrigation's `_irr_walkback()` -- a judgment "
        "call made by direct analogy to r33's own inline irrigation walk-back block, not an "
        "independently-invented rule. \"rows where initial_skill is null\" (Part C) is read "
        "as \"rows where the stripped `initial_skill` cell is the empty string\", the same "
        "quantity r33 calls `n_initial_unparsed` -- the audit CSVs never carry a distinct "
        "NULL cell type."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
