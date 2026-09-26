"""R42 -- irrigation persona pilot: does the NEW irrigation corpus (main
branch, commit 5a8a8dab, PR #54 supply-side redesign) reproduce the OLD
corpus's (commit faf1bb12) governance signature, seed by seed -- with the
persona-diversified, pre-redesign corpus (commit fcd74a5f) kept readable
as a THIRD, "mid" vintage (a current-rules reference: same persona corpus
as "new", pre-redesign physics like "old")? Pilot read at whatever seed
count has landed; the same code re-run later gives the n=5 read with zero
edits. CPU-only (GPU busy with the live persona-pilot batch -- this
script only reads already-written CSV/JSON/JSONL files, never launches a
run).

VINTAGE / ARM TERMINOLOGY (do not confuse with r25's own "old"/"new")
  Three vintages, oldest to newest:
    "old" = commit faf1bb12 -- the pre-persona-diversification corpus
      every other reviewer-prep script already reads. Pre-redesign
      physics (single-reservoir, end-of-year Mead balance).
    "mid" = commit fcd74a5f -- the persona-diversified corpus this pilot
      was ORIGINALLY built to check (this script's former "new", before
      the supply-side redesign retargeted the pilot). Still pre-redesign
      physics: fcd74a5f predates fe72e43f (the first supply-side-redesign
      commit) on the same branch, verified via `git merge-base
      --is-ancestor fcd74a5f fe72e43f`. Kept readable as a "current
      persona corpus, old physics" reference now that "new" means
      something else -- cheap to keep, since Part 1's per-vintage loops
      are already dict-driven over `VINTAGE_ARM_DIRS`. NOT part of
      Part 2/2b/3's contrast, which stays old-vs-new only (the pilot's
      original question), so a third vintage does not quietly change what
      "the contrast" means partway through this script's life.
    "new" = commit 5a8a8dab -- PR #54's merge commit, the supply-side
      water-balance redesign (Lake Powell storage buffer, 1-January
      Mead/Powell snapshots, Hung & Yang (2021) magnitude sampling)
      layered on the SAME persona corpus as "mid". Supersedes the earlier
      fcd74a5f-as-"new" pilot design point (this script's prior revision)
      the way that one superseded the 732b2b6c pilot before it (killed,
      run dir deleted, no cell ever landed).
  Every vintage carries two arms: "strict" (governed) and a comparator arm
  named DIFFERENTLY per vintage on disk -- "ungoverned" for old (faf1bb12),
  "disabled" for mid (fcd74a5f) and new (5a8a8dab) -- but plays the
  identical no-governance role in every contrast below. This script's
  `role` field ("strict" / "comparator") is what code branches on; the
  `arm` field always carries the REAL on-disk name so nothing is silently
  relabelled.

RUN LAYOUT (examples/irrigation_abm/results/)
  old strict:      strict_42yr_gemma3_4b_faf1bb12_seed{S}
  old comparator:  ungoverned_42yr_gemma3_4b_faf1bb12_seed{S}
  mid strict:      strict_42yr_gemma3_4b_fcd74a5f_seed{S}
  mid comparator:  disabled_42yr_gemma3_4b_fcd74a5f_seed{S}
  new strict:      strict_42yr_gemma3_4b_5a8a8dab_seed{S}
  new comparator:  disabled_42yr_gemma3_4b_5a8a8dab_seed{S}
  Seeds 42-46. Verified on disk at the time this update was made: all 10
  old dirs are complete; only seed42's mid strict/comparator dirs exist
  (both complete, seeds 43-46 not yet run); no complete 5a8a8dab run has
  landed yet (as of this update) -- the persona pilot re-targeted at the
  redesigned corpus is running separately. This script renders PENDING
  for every incomplete/missing cell rather than guessing; re-running it
  later with 5a8a8dab seeds landed needs no code change.

FQL REFERENCE (vintage-aware, TWO KINDS per vintage, added/revised with
the "new" vintage)
  The Mead-elevation KGE (Part 1) needs a deterministic FQL baseline on
  the SAME physics as the LLM run it is scored against --
  `run_fql_baseline.py` (Hung & Yang 2021), never an LLM. Reading its own
  docstring plus every on-disk LAUNCH_COMMAND.txt surfaced a distinction
  this script did not previously carry: `run_fql_baseline.py` runs WITH
  irrigation's 12 governance validators BY DEFAULT ("same 12 governance
  validators" as the LLM arms, per its own module docstring) unless
  `--no-governance` is passed. So every FQL dir this script read before
  this revision (`fql_raw_norebalance_faf1bb12`, `fql_raw_norebalance_
  96394b44` -- "raw" here refers to the Q-learning policy being used
  as-is, NOT to an absence of governance) is actually a GOVERNED FQL
  ablation, not Hung & Yang's traditional ABM unmodified. Two "kinds" of
  FQL reference are therefore tracked per vintage, in `FQL_DIR_BY_
  VINTAGE[vintage]`:
    "wagfrules" = the governed FQL ablation this package has always used
      (no `--no-governance` in its LAUNCH_COMMAND.txt, confirmed by
      reading each one) -- labelled "FQL + WAGF rules" throughout.
    "nogov"     = Hung & Yang's FQL with NO WAGF rules at all
      (`--no-governance`, confirmed in `fql_nogov_96394b44/seed*/
      LAUNCH_COMMAND.txt`) -- the traditional-ABM reference Wenyu
      designated PRIMARY for the Mead KGE (2026-09-26 decision, this
      revision).
  Only the "new" (5a8a8dab) physics tree has a "nogov" dir on disk
  (`fql_nogov_96394b44`, seeds 42-51, all ten with a Finished:
  LAUNCH_COMMAND.txt line as of this update); "old"/"mid" physics
  (faf1bb12) never had an ungoverned FQL generated, so `FQL_DIR_BY_
  VINTAGE["old"]["nogov"]` / `["mid"]["nogov"]` are `None` and every
  "nogov" column for those two vintages prints a named "n/a" -- never a
  guessed or borrowed value. `FQL_PRIMARY_KIND` records which kind is the
  vintage's PRIMARY, cross-run-comparable KGE reference: "nogov" for
  "new" (the true traditional-ABM reference now exists there), "wagfrules"
  for "old"/"mid" BY NECESSITY (no unruled FQL was ever run at that
  physics), not by preference -- Part 2's contrast rows name which kind
  was used per vintage rather than silently treating "primary" as the
  same thing on both sides of old-vs-new. `fql_raw_norebalance_96394b44`
  ("wagfrules" for "new") is still read as a SECOND KGE column for "new"
  runs, labelled "FQL + WAGF rules" -- this makes the governed-FQL
  ablation directly visible next to the new unruled-FQL primary, so a
  reader can see how much of the KGE gap (if any) the WAGF governance
  layer itself was contributing under the earlier, published comparison.
  Both kinds are gated by `_fql_completeness(vintage, seed, kind)` on
  their own LAUNCH_COMMAND.txt carrying a `Finished:` line -- confirmed
  present for `fql_raw_norebalance_faf1bb12` (old/mid), `fql_raw_
  norebalance_96394b44` and `fql_nogov_96394b44` (new) alike, seeds
  42-46 (r28's own `_run_completeness` does not check this, since its one
  frozen FQL dir never needed it). `lake_mead_level` timing also differs
  by vintage: `examples/irrigation_abm/run_experiment.py`'s own
  "Supply-side redesign columns" comment states `lake_mead_level` is the
  1-JANUARY value the agents saw from 5a8a8dab on; `docs/
  irrigation_physics.md`'s physics-comparison table confirms the
  pre-redesign series was an END-OF-YEAR series ("one year earlier than
  the 1 January series"). Every KGE in this script is computed WITHIN one
  vintage against that SAME vintage's FQL reference (both series on the
  same timing convention), so no single KGE number is contaminated by the
  timing change -- but a reader comparing raw `final_year_mead_ft` /
  `min_mead_ft` values SIDE BY SIDE across vintages (Part 1's table shows
  old/mid/new in one table) is comparing two different points in the
  water year. Flagged again in Method.
  CONSTANT-DEMAND NULL: not computed here. `r29_kge_null_and_demand.py`
  supplies the constant-demand KGE null (its own Part (a)) once its
  replay is re-pointed at 5a8a8dab; out of this script's scope.

COMPLETENESS GATE (fail-loud, never reads a partial run)
  `_run_completeness()`: run dir exists -> irrigation_farmer_governance_
  audit.csv exists -> simulation_log.csv exists -> LAUNCH_COMMAND.txt
  exists AND contains a `Finished:` line -> run_integrity.json exists with
  integrity_ok==True. The middle two checks are
  r35_placebo_retry_irrigation.py::_irr_run_completeness's own gate
  (imported logic, re-declared here with the added LAUNCH_COMMAND.txt
  `Finished:` check the task brief for this script asked for explicitly --
  a belt-and-suspenders check on top of r35's, not a replacement for it).
  `_fql_completeness(vintage, seed, kind)` applies the SAME dir /
  simulation_log.csv / Finished: shape to whichever FQL reference dir the
  (vintage, kind) pair names (see FQL REFERENCE above; `kind is None`
  short-circuits to "skipped" without touching disk). An LLM run that is
  itself complete but whose vintage's PRIMARY FQL reference is not yet
  Finished renders that (vintage, arm, seed) cell PENDING too, not a
  crash -- the previous revision of this script raised hard on a missing
  FQL dir, which was safe only because its one FQL dir was already
  months-frozen; a newly generated FQL dir can land out of order with the
  LLM runs it references. A non-primary kind that is not ready (e.g. the
  new vintage's "wagfrules" second column) does not block the row -- it
  prints its own "n/a" without gating anything else.

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
  Mead-elevation KGE vs the FQL reference(s): computed EXACTLY as
  `r28_trajectory_vs_traditional.py::_irr_part1`'s own per-cell KGE call --
  `_yearly_series()` on `lake_mead_level` for both series, then
  `_kge_and_rmse()` (Gupta et al. 2009 original formulation, imported, not
  re-derived) -- reproduced here in single-cell form because r28's own
  `_irr_part1` is a whole-corpus rows-appending Part function over its own
  fixed IRR_MODELS/IRR_ARMS lists, not a reusable per-run helper (the exact
  situation r36_no_ceiling_ablation.py's own `_mead_kge_vs_fql_matched`
  documents for the identical reason). The FQL reference is now TWO KINDS
  per vintage (see FQL REFERENCE above): "wagfrules" (governed FQL
  ablation, the SAME reference this script always used, `fql_raw_
  norebalance_faf1bb12` for old/mid, `fql_raw_norebalance_96394b44` for
  new) and "nogov" (Hung & Yang's FQL with no governance rules,
  `fql_nogov_96394b44`, "new" only -- `None`/"n/a" for old/mid). Three
  fields are written per landed run: `mead_kge_vs_fql_wagfrules` /
  `mead_rmse_vs_fql_wagfrules` (always computed when that dir is ready),
  `mead_kge_vs_fql_nogov` / `mead_rmse_vs_fql_nogov` ("new" only, "n/a" by
  vintage-structure for old/mid), and `mead_kge_vs_fql_primary` /
  `mead_rmse_vs_fql_primary` (whichever kind `FQL_PRIMARY_KIND[vintage]`
  names -- "nogov" for new, "wagfrules" for old/mid) plus
  `mead_kge_primary_kind` naming which kind that was, so no reader has to
  infer it. `mead_kge_vs_fql_primary` is what Part 2/2b/3's contrast
  reads; it is always a genuine float whenever a run_metrics row exists,
  because the row itself is gated on the PRIMARY kind's completeness (a
  non-primary kind not being ready never blocks the row, only its own
  column).
  Manifest census: model, git_commit (short + value-enforced to start with
  the vintage's expected prefix, RAISES on mismatch -- all three vintages
  are fully pinned commits here, so this is a real enforcement, not a
  soft check), temperature, top_p (both read directly; irrigation's
  gemma3:4b runs carry no explicit sampling params in any vintage's
  manifest -- confirmed by reading all three, all `null` -- so `None` here
  is the EXPECTED value, not a missing-field symptom), top_k (checked for
  presence as a top-level manifest key; confirmed absent from this
  manifest schema entirely by reading `broker/core/experiment_runner.py::
  _collect_reproducibility_metadata`'s own output keys -- reported as
  "absent" rather than a fabricated null), retry_feedback_mode (checked for
  presence; per r35's own docstring this key does not exist yet in
  faf1bb12's manifest schema -- confirmed absent here too for old/mid; read
  and reported for whichever vintage's manifest actually carries it, never
  assumed).
  NEW COLUMNS (added with this update, read from docs/AUDIT_SCHEMA.md on
  main 5a8a8dab): appraisal-drift rate, feasible-set retry share,
  magnitude_class shares and mean magnitude_af among executed increases,
  basin-total request/diversion at years 1/10/20/42, Consolidated-
  Reflection prompt share, and years at Mead<=900ft. Five of these
  (appraisal drift, feasible-set share, both magnitude shares, mean
  magnitude_af) are gated on audit/sim-log columns that do not exist
  before commits 9908ddd8 (appraisal-drift/feasible-set) and fe72e43f's
  F07 follow-up (magnitude_af/magnitude_class) -- both landed AFTER
  fcd74a5f, so "old" and "mid" alike print a named "n/a (...)" string for
  these five, never a fabricated zero. The other three (basin totals,
  Consolidated-Reflection share, years at Mead<=900ft) are computable in
  every vintage (the underlying columns/traces exist in all three) and are
  reported for old/mid/new alike. See `_appraisal_wsa_drift_rate_pct`,
  `_feasible_line_retry_share_pct`, `_magnitude_increase_stats`,
  `_basin_totals_maf`, `_consolidated_reflection_share_pct` for the exact
  definitions and gating.

PERSONA CHECK (mid + new vintages -- both carry the persona-diversified
corpus; old predates it)
  For every (arm, seed) directory of the "mid" or "new" vintage that
  exists on disk (independent of the full completeness gate above -- raw
  JSONL traces are streamed incrementally during a run, unlike the audit
  CSV / simulation_log.csv / run_integrity.json, which are written only at
  the end), this script scans `raw/irrigation_farmer_traces.jsonl` for the
  first year=1 record whose `agent_id` is `PVIDDiversionAG`, reads its
  `input` field (the literal LLM prompt), and reports whether it starts
  with "You are PVIDDiversionAG, an agriculture water user" (the exact
  persona-lead-in string named in the task brief) plus the first 120
  characters of that prompt (leading whitespace stripped -- the raw field
  begins with several blank lines before the persona text). A dir with no
  raw-traces file yet, or a raw-traces file with no year=1 PVIDDiversionAG
  record yet, reports a named PENDING status rather than failing the whole
  script.

PART 2 -- per seed: strict-minus-comparator contrast, old vs new
  Two metrics: IBR conditional (%) and Mead KGE vs FQL (PRIMARY reference
  per vintage -- "nogov"/Hung & Yang's unruled FQL for new,
  "wagfrules"/governed FQL for old, since old physics has no unruled FQL
  run; each contrast_pair row for the KGE metric names `old_reference` /
  `new_reference` so which kind+dir backed each side is never left
  implicit). Per seed, per vintage: diff = strict_value - comparator_value (same
  governance-minus-no-governance direction `_loader.py`'s own sign
  convention documents: negative IBR diff = governance lowered the
  high-scarcity increase rate, the paper's reported direction). A cell is
  reported only when all four (vintage x role) values for that seed are
  landed; otherwise the row records which combination is missing and
  Part 3 reports it as PENDING. `sign_match` = whether diff_old and
  diff_new share the same sign -- reported, never smoothed into a single
  score, since a 2-vintage comparison with a possible n=1 new seed has no
  business claiming more precision than a sign-and-magnitude read.
  UNCHANGED BY THIS UPDATE: this Part is old-vs-new only; "mid" does not
  appear here (see VINTAGE/ARM TERMINOLOGY above for why).

PART 2b -- per seed: shortage-tier-years / Mead-min ordering, old vs new
  For each vintage: does strict sit on the governance-benefit side of the
  comparator arm -- fewer shortage-tier years, and a HIGHER Mead minimum?
  (`_loader.py`'s convention: governance is expected to raise the physical
  floor, not lower it.) Reported per seed as `ordering_ok_old` /
  `ordering_ok_new`, again only when all four cells for that seed have
  landed. Each ordering check compares strict vs comparator WITHIN one
  vintage only, so the old/mid Mead-level timing difference documented
  above (end-of-year vs 1-January) never crosses into a single comparison
  here. UNCHANGED BY THIS UPDATE: old-vs-new only, same as Part 2.

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
    ordering_pair}. The new columns described above are additional FIELDS
    on the existing `run_metrics` row_type, not a new row_type.
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
                                              # _run_completeness, _kge_and_rmse, _kge_word.
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
    "mid": {
        "strict": lambda seed: os.path.join(
            IRR_RESULTS, f"strict_42yr_gemma3_4b_fcd74a5f_seed{seed}"),
        "comparator": lambda seed: os.path.join(
            IRR_RESULTS, f"disabled_42yr_gemma3_4b_fcd74a5f_seed{seed}"),
    },
    "new": {
        "strict": lambda seed: os.path.join(
            IRR_RESULTS, f"strict_42yr_gemma3_4b_5a8a8dab_seed{seed}"),
        "comparator": lambda seed: os.path.join(
            IRR_RESULTS, f"disabled_42yr_gemma3_4b_5a8a8dab_seed{seed}"),
    },
}
COMPARATOR_ARM_NAME = {"old": "ungoverned", "mid": "disabled", "new": "disabled"}
EXPECTED_COMMIT_PREFIX = {"old": "faf1bb12", "mid": "fcd74a5f", "new": "5a8a8dab"}
TOP_N_RULES = 3

# Vintage-aware, TWO-KIND FQL reference dirs (see module docstring "FQL
# REFERENCE"). "wagfrules" = run_fql_baseline.py WITH the 12 governance
# validators (every LAUNCH_COMMAND.txt below lacks --no-governance) -- the
# governed FQL ablation this package has always used. "nogov" =
# run_fql_baseline.py --no-governance -- Hung & Yang's FQL with NO WAGF
# rules, confirmed via fql_nogov_96394b44/seed*/LAUNCH_COMMAND.txt. "old"/
# "mid" share pre-redesign physics (fcd74a5f predates fe72e43f) and so
# share the SAME frozen "wagfrules" reference every other reviewer-prep
# script already reads; neither ever had an unruled FQL run generated, so
# their "nogov" entry is None (n/a downstream, never guessed). "new"
# (5a8a8dab, the redesigned physics tree) has both, generated under that
# SAME tree.
FQL_DIR_BY_VINTAGE = {
    "old": {"wagfrules": "fql_raw_norebalance_faf1bb12", "nogov": None},
    "mid": {"wagfrules": "fql_raw_norebalance_faf1bb12", "nogov": None},
    "new": {"wagfrules": "fql_raw_norebalance_96394b44", "nogov": "fql_nogov_96394b44"},
}
# The PRIMARY, cross-run-comparable KGE reference per vintage. "new" now
# has a true unruled FQL, so Wenyu's 2026-09-26 decision makes THAT
# primary there; "old"/"mid" never had one generated, so their existing
# governed reference remains primary BY NECESSITY, not by preference --
# Part 2's contrast rows name which kind was used per vintage rather than
# silently treating "primary" as the same thing on both sides.
FQL_PRIMARY_KIND = {"old": "wagfrules", "mid": "wagfrules", "new": "nogov"}
# Human-readable label per kind, used in contrast-row reference fields and
# markdown headers -- one spelling, never retyped ad hoc.
FQL_KIND_LABEL = {"wagfrules": "FQL + WAGF rules", "nogov": "FQL (no governance)"}

PERSONA_AGENT = "PVIDDiversionAG"
PERSONA_EXPECTED_PREFIX = "You are PVIDDiversionAG, an agriculture water user"
PERSONA_CHARS = 120

# executed skills that count as an "increase" for the magnitude-class /
# magnitude_af metrics (_magnitude_increase_stats).
INCREASE_SKILLS = ("increase_large", "increase_small")
# Years at which basin-total request/diversion are reported (_basin_totals_maf).
BASIN_TOTAL_YEARS = (1, 10, 20, 42)
MEAD_LOW_THRESHOLD_FT = 900.0


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


def _fql_completeness(vintage: str, seed: str, kind: str) -> tuple:
    """FQL reference dir completeness for `vintage`'s `kind` ("wagfrules"
    or "nogov") Mead-KGE baseline, gated the same way as the LLM run dirs
    above (dir -> simulation_log.csv -> LAUNCH_COMMAND.txt has a
    `Finished:` line). `FQL_DIR_BY_VINTAGE[vintage][kind] is None` (no
    unruled FQL exists for old/mid physics) short-circuits to "skipped"
    without touching disk -- a structural absence, not an in-progress run,
    but the same tuple shape lets every caller handle both the same way.
    `r28_trajectory_vs_traditional.py::_run_completeness` only checks
    dir+simulation_log.csv -- fine for a frozen FQL dir that finished
    months ago, but this update's task brief asked for the explicit
    Finished: check because the "new" vintage's FQL dirs were still being
    generated at the time. Applied uniformly, not gated to "new" only,
    since it costs nothing on an already-finished dir -- verified present
    for `fql_raw_norebalance_faf1bb12` (old/mid "wagfrules"), `fql_raw_
    norebalance_96394b44` (new "wagfrules") and `fql_nogov_96394b44` (new
    "nogov"), seeds 42-46 alike."""
    dir_name = FQL_DIR_BY_VINTAGE[vintage][kind]
    if dir_name is None:
        return "skipped", f"no {kind!r} FQL reference exists for vintage {vintage!r} (structural)"
    fql_dir = os.path.join(IRR_RESULTS, dir_name, f"seed{seed}")
    status, reason = R28._run_completeness(fql_dir)
    if status == "skipped":
        return status, reason
    lc_path = os.path.join(fql_dir, "LAUNCH_COMMAND.txt")
    if not os.path.isfile(lc_path):
        return "skipped", "LAUNCH_COMMAND.txt missing (FQL run in progress)"
    lc_text = open(lc_path, encoding="utf-8", errors="replace").read()
    if "Finished:" not in lc_text:
        return "skipped", "LAUNCH_COMMAND.txt has no Finished: line (FQL run in progress)"
    return "ok", None


# =============================================================================
# Part 1
# =============================================================================
def _mead_kge_vs_fql(sim_path: str, seed: str, vintage: str, kind: str) -> dict:
    """Mead-elevation KGE against the FQL reference of the given `kind`
    ("wagfrules" or "nogov"), byte-identical call sequence to
    r28_trajectory_vs_traditional.py::_irr_part1's own per-(model, arm,
    seed) cell for series="mead_elevation" -- reproduced here in
    single-cell form since r28's `_irr_part1` is a whole-corpus
    rows-appending Part function over its own fixed IRR_MODELS/IRR_ARMS
    lists, not a reusable per-run helper (the same situation
    r36_no_ceiling_ablation.py's own `_mead_kge_vs_fql_matched`
    documents). The FQL reference dir is vintage- AND kind-aware
    (`FQL_DIR_BY_VINTAGE[vintage][kind]`); callers are expected to have
    already checked `_fql_completeness(vintage, seed, kind)` before
    calling this (Part 1 does, for whichever kinds it needs per row), so
    the raise below is a defensive re-check, not the primary gate."""
    years, mead = R28._yearly_series(sim_path, "lake_mead_level", "first")
    fql_dir_name = FQL_DIR_BY_VINTAGE[vintage][kind]
    fql_status, fql_reason = _fql_completeness(vintage, seed, kind)
    if fql_status == "skipped":
        raise PrepError(f"FQL {kind!r} reference ({fql_dir_name!r}) seed {seed} for vintage "
                         f"{vintage!r} not available: {fql_reason} (caller should have "
                         f"pre-checked)")
    fql_dir = os.path.join(IRR_RESULTS, fql_dir_name, f"seed{seed}")
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


# =============================================================================
# Part 1 -- new columns (P0-1 audit columns, supply-side redesign columns)
# =============================================================================
def _appraisal_wsa_drift_rate_pct(aud: list):
    """Share of ALL rows where the first-attempt WSA_LABEL differs from the
    final attempt's, filtered out of the generic (any-construct)
    `appraisal_drift` string (docs/AUDIT_SCHEMA.md: e.g.
    "WSA_LABEL:H>M|ACA_LABEL:M>H", key-gated on
    `global_config.audit.initial_proposal_columns`) -- a row's entry counts
    here only when it names WSA_LABEL specifically; `appraisal_drifted`
    (bool) is NOT used directly because it fires on ANY construct's drift,
    and the task brief asks for the WSA label alone. Column absent (true
    for every run predating commit 9908ddd8, i.e. every "old"/"mid" run on
    disk today) -> a named "n/a" string, never a fabricated 0."""
    if not aud or "appraisal_drift" not in aud[0]:
        return "n/a (column absent -- audit.initial_proposal_columns was OFF for this run)"
    n = len(aud)
    hits = sum(1 for r in aud if "WSA_LABEL:" in (r.get("appraisal_drift") or ""))
    return 100.0 * hits / n


def _feasible_line_retry_share_pct(aud: list):
    """Among RETRIED rows (retry_count>0), the share whose `feasible_by_
    attempt` column (docs/AUDIT_SCHEMA.md, key-gated on
    `governance.feasible_set_feedback`) is non-empty -- i.e. at least one
    governance-retry prompt in that row logged a feasible-set line with
    recorded content. CAVEAT (documented, not smoothed over): a row whose
    only retry produced a single EMPTY group (no skill passed) joins to
    the same empty string as a row with no groups at all, so this is a
    slight undercount of "carried the line" in that one edge case, not an
    overcount. Column absent (true for every "old"/"mid" run, predating
    commit 9908ddd8) -> "n/a"; a run with the column but zero retried rows
    -> "n/a (0 retried rows)", never a division by zero."""
    if not aud or "feasible_by_attempt" not in aud[0]:
        return "n/a (column absent -- governance.feasible_set_feedback was OFF for this run)"
    retried = [r for r in aud if int(r.get("retry_count") or 0) > 0]
    if not retried:
        return "n/a (0 retried rows this run)"
    hits = sum(1 for r in retried if (r.get("feasible_by_attempt") or "") != "")
    return 100.0 * hits / len(retried)


def _magnitude_increase_stats(sim: list) -> dict:
    """magnitude_class shares (small/large) and mean magnitude_af among
    EXECUTED increases. Row selection mirrors the increase-skill rows of
    examples/irrigation_abm/validate_smoke.py::check_j_magnitude_bounds:
    `yearly_decision` in {increase_large, increase_small} AND
    `magnitude_class` non-empty. `yearly_decision` alone is proposal /
    final-attempt level, not executed (see this repo's own
    d93ce386 correction, and `_common.py`'s irr_final/irr_executed split):
    a REJECTED row whose blocked proposal was an increase runs the
    registry default instead (`skill_broker_engine.py`'s REJECTED-branch
    fallback execution), and that row's `magnitude_class`/`magnitude_af`
    (sourced from the EXECUTED skill's own state_changes, not the blocked
    proposal's) is empty in that case -- validate_smoke.py's own docstring
    states "magnitude_class is set from the executed skill name".
    Requiring `magnitude_class` non-empty is therefore what makes this
    selection executed-level without a second join against the audit
    CSV's status column. Column absent (every pre-2026-09-26 corpus, i.e.
    "old"/"mid" here, predating the F07 follow-up on fe72e43f) -> a named
    "n/a" for all three fields; column present but zero qualifying rows ->
    a distinct "n/a (0 executed increases)"."""
    na_absent = "n/a (column absent -- pre-2026-09-26 corpus, before the F07 magnitude "
    na_absent += "follow-up)"
    if not sim or "magnitude_class" not in sim[0]:
        return {"small_pct": na_absent, "large_pct": na_absent, "mean_af": na_absent}
    rows = [r for r in sim
            if (r.get("yearly_decision") or "").strip() in INCREASE_SKILLS
            and (r.get("magnitude_class") or "").strip() != ""]
    if not rows:
        na_empty = "n/a (0 executed increases this run)"
        return {"small_pct": na_empty, "large_pct": na_empty, "mean_af": na_empty}
    n = len(rows)
    small_n = sum(1 for r in rows if r["magnitude_class"].strip() == "small")
    large_n = sum(1 for r in rows if r["magnitude_class"].strip() == "large")
    afs = [float(r["magnitude_af"]) for r in rows]
    return {"small_pct": 100.0 * small_n / n, "large_pct": 100.0 * large_n / n,
            "mean_af": sum(afs) / len(afs)}


def _basin_totals_maf(sim_path: str) -> dict:
    """Basin-total request/diversion (sum over all agents that year,
    acre-ft -> MAF) at years 1/10/20/42, via
    r28_trajectory_vs_traditional.py::_yearly_series (imported, not
    re-derived) with agg="sum" -- the SAME column/agg r28's own
    basin_demand series uses for `request`; `diversion` is the settled
    counterpart, read with the identical agg. Computed for every vintage
    (both columns exist in old/mid/new alike); raises if a 42-year run is
    somehow missing one of the four target years (would mean the
    completeness gate's EXPECTED_ROWS check upstream was wrong, a data
    bug, not an incompleteness)."""
    out = {}
    for col in ("request", "diversion"):
        years, vals = R28._yearly_series(sim_path, col, "sum")
        by_year = dict(zip(years, vals))
        for y in BASIN_TOTAL_YEARS:
            if y not in by_year:
                raise PrepError(f"{sim_path}: year {y} missing from what should be a "
                                 f"42-year run (years present: {years[:3]}..{years[-3:]})")
            out[f"basin_{col}_maf_y{y}"] = by_year[y] / 1_000_000.0
    return out


def _consolidated_reflection_share_pct(run_dir: str):
    """Share of raw JSONL trace records whose `input` field (the literal
    LLM prompt, including its rendered memory block) contains the literal
    substring "Consolidated Reflection" -- the exact prefix
    `examples/irrigation_abm/run_experiment.py` writes at memory-
    consolidation time (`f"Consolidated Reflection: {insight.summary}"`),
    confirmed present at this same call site across all three vintages
    (faf1bb12, fcd74a5f, 5a8a8dab). Computed for every vintage. Raw traces
    file missing (run in progress, or none written) -> "n/a"."""
    raw_path = os.path.join(run_dir, "raw", "irrigation_farmer_traces.jsonl")
    if not os.path.isfile(raw_path):
        return "n/a (raw traces file missing)"
    total = 0
    hits = 0
    with open(raw_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "input" not in obj:
                continue
            total += 1
            if "Consolidated Reflection" in (obj.get("input") or ""):
                hits += 1
    if total == 0:
        return "n/a (0 records with an input field in raw traces)"
    return 100.0 * hits / total


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
                if status == "ok":
                    primary_kind = FQL_PRIMARY_KIND[vintage]
                    fql_status, fql_reason = _fql_completeness(vintage, seed, primary_kind)
                    if fql_status == "skipped":
                        status = "skipped"
                        reason = (f"primary FQL reference ({primary_kind}, "
                                  f"{FQL_DIR_BY_VINTAGE[vintage][primary_kind]})/seed{seed} "
                                  f"not ready: {fql_reason}")
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
                    years_mead_le_900ft = sum(1 for v in mead_series if v <= MEAD_LOW_THRESHOLD_FT)

                    # Both FQL kinds, per vintage: "wagfrules" is always
                    # attempted (all three vintages have a dir); "nogov"
                    # only exists for "new" (FQL_DIR_BY_VINTAGE[...]["nogov"]
                    # is None for old/mid, per the FQL REFERENCE docstring).
                    # A non-primary kind that is not ready never blocks this
                    # row -- only its own column reads "n/a"; the row itself
                    # was already gated on the PRIMARY kind above.
                    kge_by_kind = {}
                    for kind in ("wagfrules", "nogov"):
                        dir_name = FQL_DIR_BY_VINTAGE[vintage][kind]
                        if dir_name is None:
                            na = "n/a (no unruled FQL exists for this vintage's physics)"
                            kge_by_kind[kind] = {"kge": na, "rmse": na}
                            continue
                        fql_status, fql_reason = _fql_completeness(vintage, seed, kind)
                        if fql_status == "skipped":
                            na = f"n/a (FQL {dir_name}/seed{seed} not ready: {fql_reason})"
                            kge_by_kind[kind] = {"kge": na, "rmse": na}
                            continue
                        stats = _mead_kge_vs_fql(sim_path, seed, vintage, kind)
                        kge_by_kind[kind] = {"kge": stats["kge"], "rmse": stats["rmse"]}
                    primary_kind = FQL_PRIMARY_KIND[vintage]
                    kge_primary = kge_by_kind[primary_kind]

                    st = [(r.get("status") or "").strip() for r in aud]
                    rejected_n = sum(1 for s in st if s.startswith("REJECTED"))
                    retried_n = sum(1 for r in aud if int(r.get("retry_count") or 0) > 0)

                    appraisal_wsa_drift_rate_pct = _appraisal_wsa_drift_rate_pct(aud)
                    feasible_line_retry_share_pct = _feasible_line_retry_share_pct(aud)
                    mag_stats = _magnitude_increase_stats(sim)
                    basin_totals = _basin_totals_maf(sim_path)
                    consolidated_reflection_prompt_share_pct = \
                        _consolidated_reflection_share_pct(run_dir)

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
                        "mead_kge_vs_fql_wagfrules": kge_by_kind["wagfrules"]["kge"],
                        "mead_rmse_vs_fql_wagfrules": kge_by_kind["wagfrules"]["rmse"],
                        "mead_kge_vs_fql_nogov": kge_by_kind["nogov"]["kge"],
                        "mead_rmse_vs_fql_nogov": kge_by_kind["nogov"]["rmse"],
                        "mead_kge_vs_fql_primary": kge_primary["kge"],
                        "mead_rmse_vs_fql_primary": kge_primary["rmse"],
                        "mead_kge_primary_kind": primary_kind,
                        "fallback_pct": m["fallback_pct"], "llm_fail_n": int(m["llm_fail_n"]),
                        "wall_hours": m["wall_hours"],
                        "appraisal_wsa_drift_rate_pct": appraisal_wsa_drift_rate_pct,
                        "feasible_line_retry_share_pct": feasible_line_retry_share_pct,
                        "magnitude_increase_small_share_pct": mag_stats["small_pct"],
                        "magnitude_increase_large_share_pct": mag_stats["large_pct"],
                        "magnitude_af_mean_increases": mag_stats["mean_af"],
                        "years_mead_le_900ft": years_mead_le_900ft,
                        "consolidated_reflection_prompt_share_pct":
                            consolidated_reflection_prompt_share_pct,
                        **basin_totals,
                    }
                    rows.append(row)

                    census = R35._rule_id_census(aud, TOP_N_RULES)
                    for rank, (rule_id, count) in enumerate(census, start=1):
                        rows.append({"row_type": "rule_id_census", "vintage": vintage,
                                     "arm": arm_name, "seed": seed, "rank": rank,
                                     "rule_id": rule_id, "count": count})

                    rows.append(_manifest_census_row(vintage, arm_name, seed, run_dir))

                    print(f"  OK {vintage}/{arm_name:11s} seed {seed}: "
                          f"IBR_cond={m['ibr_headline']:.2f}% "
                          f"KGE({primary_kind})={_valfmt(kge_primary['kge'])} "
                          f"shortage_tier_years={shortage_tier_years} "
                          f"top_rule={census[0] if census else None}")

                    per_run[(vintage, role, seed)] = row

                if vintage in ("mid", "new"):
                    rows.append(_persona_check(vintage, arm_name, seed, run_dir))
    return per_run


# =============================================================================
# Part 2 / 2b
# =============================================================================
CONTRAST_METRIC_KEYS = {
    "IBR conditional (%)": "ibr_conditional",
    "Mead KGE vs FQL (primary ref. per vintage)": "mead_kge_vs_fql_primary",
}
# The one metric label above whose contrast_pair rows also carry
# old_reference/new_reference fields (see _part2) -- old/new use DIFFERENT
# FQL kinds as primary (see FQL_PRIMARY_KIND), so the reference actually
# backing each side of the diff is never left implicit.
KGE_METRIC_LABEL = "Mead KGE vs FQL (primary ref. per vintage)"
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
    old/new x strict/comparator. "mid" is deliberately not part of this
    grid -- Part 2/2b/3 contrast old-vs-new only (see module docstring)."""
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
            contrast_row = {
                "row_type": "contrast_pair", "metric": metric_label, "seed": seed,
                "old_strict": cells[("old", "strict")],
                "old_comparator": cells[("old", "comparator")],
                "new_strict": cells[("new", "strict")],
                "new_comparator": cells[("new", "comparator")],
                "diff_old": diff_old, "diff_new": diff_new, "sign_match": sign_match,
            }
            if metric_label == KGE_METRIC_LABEL:
                # old/new use DIFFERENT FQL kinds as primary (FQL_PRIMARY_
                # KIND) -- name which one backed each side so the diff is
                # never read as an apples-to-apples reference by accident.
                for v in ("old", "new"):
                    kind = FQL_PRIMARY_KIND[v]
                    contrast_row[f"{v}_reference"] = (
                        f"{FQL_KIND_LABEL[kind]} ({FQL_DIR_BY_VINTAGE[v][kind]})")
            rows.append(contrast_row)


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
    "mead_kge_vs_fql_wagfrules", "mead_rmse_vs_fql_wagfrules",
    "mead_kge_vs_fql_nogov", "mead_rmse_vs_fql_nogov",
    "mead_kge_vs_fql_primary", "mead_rmse_vs_fql_primary", "mead_kge_primary_kind",
    "fallback_pct", "llm_fail_n", "wall_hours",
    "appraisal_wsa_drift_rate_pct", "feasible_line_retry_share_pct",
    "magnitude_increase_small_share_pct", "magnitude_increase_large_share_pct",
    "magnitude_af_mean_increases", "years_mead_le_900ft",
    "consolidated_reflection_prompt_share_pct",
    "basin_request_maf_y1", "basin_request_maf_y10", "basin_request_maf_y20",
    "basin_request_maf_y42",
    "basin_diversion_maf_y1", "basin_diversion_maf_y10", "basin_diversion_maf_y20",
    "basin_diversion_maf_y42",
    "rank", "rule_id", "count",
    "model", "git_commit_short", "git_commit_expected_prefix", "temperature", "top_p",
    "top_k_present", "top_k", "retry_feedback_mode_present", "retry_feedback_mode",
    "thinking_mode",
    "status", "first_120_chars", "starts_with_expected",
    "metric", "old_strict", "old_comparator", "new_strict", "new_comparator",
    "diff_old", "diff_new", "sign_match", "ordering_ok_old", "ordering_ok_new",
    "old_reference", "new_reference",
]


def main() -> int:
    C.banner("R42  Irrigation persona pilot: new corpus (5a8a8dab) vs old corpus "
             "(faf1bb12); mid reference (fcd74a5f)")
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


def _valfmt(x, nd=2) -> str:
    """Render a numeric OR a 'n/a (...)'-string cell for the new diagnostic
    columns without routing through `_cp()` (which assumes every value is
    numeric and would raise trying to float() an intentional 'n/a'
    string)."""
    if isinstance(x, str):
        return x
    return f"{x:.{nd}f}"


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
    lines.append("# R42 -- irrigation persona pilot: new corpus (5a8a8dab) vs old corpus "
                 "(faf1bb12); mid reference (fcd74a5f)")
    lines.append("")
    lines.append("Source: `r42_irrigation_persona_pilot.py`. Every number below is read live "
                 "from the `rows` list this script writes to the paired CSV. \"old\" = commit "
                 "faf1bb12 (5 seeds landed, 42-46, pre-redesign physics). \"mid\" = commit "
                 "fcd74a5f (the persona-diversified corpus, pre-redesign physics -- a "
                 "current-rules reference kept readable alongside \"new\"; only seed 42 landed "
                 "as of this read). \"new\" = commit 5a8a8dab (PR #54's supply-side redesign, "
                 "the corpus this pilot exists to check; landed cells only where they exist on "
                 "disk and pass the completeness gate -- see Method). Part 2/2b/3's contrast is "
                 "old-vs-new only; \"mid\" appears in Part 1 only.")
    lines.append("")

    # ---- Part 1: per-run metrics -----------------------------------------------
    lines.append("## Part 1 -- per (vintage, arm, seed) metrics")
    lines.append("")
    lines.append("| vintage | arm | seed | n_rows | IBR cond. % | IBR uncond. % | EHE exec | "
                 "EHE prop | rejected n | rejection % | retried n | retry % | final-yr Mead ft | "
                 "min Mead ft | shortage-tier yrs | Mead KGE vs FQL (primary) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for vintage in ("old", "mid", "new"):
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
                    f"{int(r['shortage_tier_years'])} | "
                    f"{_valfmt(r['mead_kge_vs_fql_primary'], nd=4)} ({r['mead_kge_primary_kind']}) |"
                )
    lines.append("")
    lines.append("\"Mead KGE vs FQL (primary)\" uses each vintage's PRIMARY reference "
                 "(named in parentheses) -- see the dedicated FQL-reference table below for "
                 "both kinds (\"FQL + WAGF rules\" and, new-vintage only, unruled \"FQL (no "
                 "governance)\") side by side.")
    lines.append("")

    lines.append("### Mead KGE vs FQL reference -- both kinds")
    lines.append("")
    lines.append("\"FQL + WAGF rules\" = `run_fql_baseline.py` WITH the 12 governance "
                 "validators (this package's long-standing reference; \"raw\" in its dir name "
                 "refers to the Q-learning policy, not to an absence of governance). "
                 "\"FQL (no governance)\" = `run_fql_baseline.py --no-governance` -- Hung & "
                 "Yang's traditional ABM with NO WAGF rules, generated only for the new "
                 "(5a8a8dab) physics tree (`fql_nogov_96394b44`); old/mid never had one "
                 "generated, so that column reads `n/a` there by construction, not because a "
                 "run is incomplete. \"primary\" (also shown in the main Part 1 table) is "
                 "whichever kind `FQL_PRIMARY_KIND` names per vintage.")
    lines.append("")
    lines.append("| vintage | arm | seed | KGE FQL+WAGF rules | KGE FQL (no governance) | "
                 "primary kind |")
    lines.append("|---|---|---|---|---|---|")
    for vintage in ("old", "mid", "new"):
        for role in ("strict", "comparator"):
            arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME[vintage]
            for seed in SEEDS:
                recs = _find(rows, "run_metrics", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    lines.append(f"| {vintage} | {arm_name} | {seed} | PENDING | -- | -- |")
                    continue
                r = recs[0]
                lines.append(
                    f"| {vintage} | {arm_name} | {seed} | "
                    f"{_valfmt(r['mead_kge_vs_fql_wagfrules'], nd=4)} | "
                    f"{_valfmt(r['mead_kge_vs_fql_nogov'], nd=4)} | "
                    f"{r['mead_kge_primary_kind']} |"
                )
    lines.append("")

    lines.append("### Rule-id census, top 3 among retried rows")
    lines.append("")
    lines.append("| vintage | arm | seed | rank | rule_id | count |")
    lines.append("|---|---|---|---|---|---|")
    for vintage in ("old", "mid", "new"):
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
    for vintage in ("old", "mid", "new"):
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

    lines.append("### Governance/audit + magnitude diagnostics (new columns)")
    lines.append("")
    lines.append("`n/a` with a reason in parentheses means the underlying column does not "
                 "exist for this run (pre-9908ddd8 for the two appraisal/feasible columns, "
                 "pre-fe72e43f-F07 for the three magnitude columns) or, for the magnitude "
                 "columns, that zero rows qualified as an executed increase this run -- never "
                 "a fabricated zero.")
    lines.append("")
    lines.append("| vintage | arm | seed | WSA drift % | feasible-line retry share % | "
                 "magnitude small % (incr.) | magnitude large % (incr.) | mean magnitude_af "
                 "(incr., ac-ft) | years Mead<=900ft | Consolidated-Reflection prompt share % |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for vintage in ("old", "mid", "new"):
        for role in ("strict", "comparator"):
            arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME[vintage]
            for seed in SEEDS:
                recs = _find(rows, "run_metrics", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    lines.append(f"| {vintage} | {arm_name} | {seed} | PENDING | -- | -- | -- | "
                                 f"-- | -- | -- |")
                    continue
                r = recs[0]
                lines.append(
                    f"| {vintage} | {arm_name} | {seed} | "
                    f"{_valfmt(r['appraisal_wsa_drift_rate_pct'])} | "
                    f"{_valfmt(r['feasible_line_retry_share_pct'])} | "
                    f"{_valfmt(r['magnitude_increase_small_share_pct'])} | "
                    f"{_valfmt(r['magnitude_increase_large_share_pct'])} | "
                    f"{_valfmt(r['magnitude_af_mean_increases'])} | "
                    f"{r['years_mead_le_900ft']} | "
                    f"{_valfmt(r['consolidated_reflection_prompt_share_pct'])} |"
                )
    lines.append("")

    lines.append("### Basin totals at years 1 / 10 / 20 / 42 (MAF)")
    lines.append("")
    lines.append("| vintage | arm | seed | request y1 | y10 | y20 | y42 | diversion y1 | y10 | "
                 "y20 | y42 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for vintage in ("old", "mid", "new"):
        for role in ("strict", "comparator"):
            arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME[vintage]
            for seed in SEEDS:
                recs = _find(rows, "run_metrics", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    lines.append(f"| {vintage} | {arm_name} | {seed} | PENDING | -- | -- | -- | "
                                 f"-- | -- | -- | -- |")
                    continue
                r = recs[0]
                lines.append(
                    f"| {vintage} | {arm_name} | {seed} | "
                    f"{_cp(r['basin_request_maf_y1']):.3f} | "
                    f"{_cp(r['basin_request_maf_y10']):.3f} | "
                    f"{_cp(r['basin_request_maf_y20']):.3f} | "
                    f"{_cp(r['basin_request_maf_y42']):.3f} | "
                    f"{_cp(r['basin_diversion_maf_y1']):.3f} | "
                    f"{_cp(r['basin_diversion_maf_y10']):.3f} | "
                    f"{_cp(r['basin_diversion_maf_y20']):.3f} | "
                    f"{_cp(r['basin_diversion_maf_y42']):.3f} |"
                )
    lines.append("")

    lines.append("### Persona check (mid + new vintages) -- year-1 PVIDDiversionAG prompt")
    lines.append("")
    lines.append("| vintage | arm | seed | status | starts with expected persona lead-in | "
                 "first 120 chars |")
    lines.append("|---|---|---|---|---|---|")
    for vintage in ("mid", "new"):
        for role in ("strict", "comparator"):
            arm_name = "strict" if role == "strict" else COMPARATOR_ARM_NAME[vintage]
            for seed in SEEDS:
                recs = _find(rows, "persona_check", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    lines.append(f"| {vintage} | {arm_name} | {seed} | not checked | -- | -- |")
                    continue
                r = recs[0]
                chars = r["first_120_chars"]
                chars_cell = "n.a." if chars is None else "`" + chars.replace("|", "\\|") + "`"
                lines.append(f"| {vintage} | {arm_name} | {seed} | {r['status']} | "
                             f"{r['starts_with_expected']} | {chars_cell} |")
    lines.append("")

    # ---- Part 2: contrasts -------------------------------------------------------
    lines.append("## Part 2 -- seed-paired strict-minus-comparator contrast, old vs new")
    lines.append("")
    lines.append("diff = strict value - comparator value (governance-minus-no-governance "
                 "direction). `sign_match` = whether diff_old and diff_new share the same "
                 "sign -- no significance test, n is whatever has landed. \"mid\" is not part "
                 "of this contrast (see Part 1 for its own numbers). For the KGE row, \"old "
                 "reference\"/\"new reference\" name which FQL kind actually backed each side "
                 "-- old and new use DIFFERENT primary kinds (see Method), so the diff is NOT "
                 "an apples-to-apples reference comparison, only a same-vintage strict-vs-"
                 "comparator one.")
    lines.append("")
    lines.append("| metric | seed | old strict | old comparator | diff old | new strict | "
                 "new comparator | diff new | sign match | old reference | new reference |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for metric_label in CONTRAST_METRIC_KEYS:
        for seed in SEEDS:
            recs = _find(rows, "contrast_pair", metric=metric_label, seed=seed)
            if not recs:
                pend = _find(rows, "skipped", section="contrast_pair", metric=metric_label,
                              seed=seed)
                reason = pend[0]["reason"] if pend else "no data"
                lines.append(f"| {metric_label} | {seed} | -- | -- | -- | -- | -- | -- | "
                             f"PENDING ({reason}) | -- | -- |")
                continue
            r = recs[0]
            old_ref = r.get("old_reference") or "--"
            new_ref = r.get("new_reference") or "--"
            lines.append(
                f"| {metric_label} | {seed} | {_cp(r['old_strict']):.4f} | "
                f"{_cp(r['old_comparator']):.4f} | {_cp(r['diff_old']):.4f} | "
                f"{_cp(r['new_strict']):.4f} | {_cp(r['new_comparator']):.4f} | "
                f"{_cp(r['diff_new']):.4f} | {r['sign_match']} | {old_ref} | {new_ref} |"
            )
    lines.append("")

    # ---- Part 2b: ordering ---------------------------------------------------
    lines.append("## Part 2b -- shortage-tier-years / Mead-min ordering, old vs new")
    lines.append("")
    lines.append("ordering_ok = strict sits on the governance-benefit side of its comparator "
                 "(fewer shortage-tier years; a HIGHER Mead minimum). Each check compares "
                 "strict vs comparator WITHIN one vintage only, so the old/new Mead-level "
                 "timing difference (see Method) never enters a single comparison here.")
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
                 "which cell(s). \"mid\" is not part of this read.")
    lines.append("")
    any_landed = False
    for seed in SEEDS:
        ibr_rec = _find(rows, "contrast_pair", metric="IBR conditional (%)", seed=seed)
        kge_rec = _find(rows, "contrast_pair", metric=KGE_METRIC_LABEL, seed=seed)
        short_rec = _find(rows, "ordering_pair", metric="Shortage-tier years", seed=seed)
        mead_rec = _find(rows, "ordering_pair", metric="Mead min (ft)", seed=seed)
        needed = {"IBR conditional (%) contrast": ibr_rec, "Mead KGE contrast": kge_rec,
                  "Shortage-tier-years ordering": short_rec, "Mead-min ordering": mead_rec}
        missing_parts = [name for name, recs in needed.items() if not recs]
        if missing_parts:
            skip_reasons = []
            for name, section, metric in (
                ("IBR conditional (%) contrast", "contrast_pair", "IBR conditional (%)"),
                ("Mead KGE contrast", "contrast_pair", KGE_METRIC_LABEL),
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
            f"corpus's diff has {ibr_sign_word} the old corpus's diff. (b) Mead KGE vs FQL -- "
            f"old ref. {kge.get('old_reference', '?')}: strict {kge_word_old_strict} it "
            f"(KGE={_cp(kge['old_strict']):.3f}), comparator {kge_word_old_comp} it "
            f"(KGE={_cp(kge['old_comparator']):.3f}); new ref. "
            f"{kge.get('new_reference', '?')}: strict {kge_word_new_strict} it "
            f"(KGE={_cp(kge['new_strict']):.3f}), comparator "
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
        "`_irr_llm_metrics()`, as a cross-check), shortage-tier years, and years at "
        "Mead<=900ft all come from `r28_trajectory_vs_traditional.py::_yearly_series()` on "
        "`lake_mead_level` (and `shortage_tier`) -- imported, not re-derived; "
        "`_yearly_series()`'s own nunique==1-per-year check is what verifies both columns are "
        "genuinely basin-level, not assumed. `shortage_tier_years` (years with "
        "`shortage_tier>=1`) is a DIFFERENT metric from the `shortage_years` column "
        "r25/r35/r36 report (years with mean Mead level below 1075 ft) and is never given "
        "that other name. `lake_mead_level`'s TIMING differs by vintage -- 1 January for "
        "\"new\" (5a8a8dab on), end-of-year for \"old\"/\"mid\" (`examples/irrigation_abm/"
        "docs/irrigation_physics.md`'s physics-comparison table) -- so `final_year_mead_ft` / "
        "`min_mead_ft` / `years_mead_le_900ft` are each internally consistent within a vintage "
        "but not directly comparable across the old/mid vs new boundary without accounting "
        "for the roughly one-year offset. Mead-elevation KGE vs the FQL reference: "
        "`r28_trajectory_vs_traditional.py::_yearly_series()` + `_kge_and_rmse()` (Gupta et "
        "al. 2009 original formulation). REVISED 2026-09-26 (Wenyu's decision): the earlier "
        "published irrigation KGE comparison in this package, and every FQL dir this script "
        "read before this revision, used `run_fql_baseline.py` WITH its 12 governance "
        "validators on by default (\"FQL + WAGF rules\" -- confirmed via each dir's own "
        "LAUNCH_COMMAND.txt lacking `--no-governance`; \"raw\" in those dir names describes "
        "the Q-learning policy, not an absence of governance) -- a governed FQL ablation, not "
        "Hung & Yang's traditional ABM unmodified. The PRIMARY reference is now the unruled "
        "FQL (`--no-governance`, i.e. NO WAGF rules): `fql_nogov_96394b44`, generated only "
        "for the new (5a8a8dab) physics tree, seeds 42-51. Old/mid physics (faf1bb12) never "
        "had an unruled FQL run, so their primary reference stays \"FQL + WAGF rules\" "
        "(`fql_raw_norebalance_faf1bb12`) by necessity, and their unruled-FQL column reads "
        "`n/a`. \"New\" rows additionally report the governed-FQL ablation "
        "(`fql_raw_norebalance_96394b44`) as a SECOND, explicitly labelled KGE column, so the "
        "governed-vs-unruled gap stays visible rather than silently dropped when the primary "
        "reference changed. Every FQL dir is gated by `_fql_completeness(vintage, seed, kind)` "
        "on its own LAUNCH_COMMAND.txt `Finished:` line -- every KGE is computed WITHIN one "
        "vintage, against that vintage's own reference (of whichever kind), so the Mead-level "
        "timing difference above never enters a single KGE number. `_four_cells`/Part 2's "
        "contrast reads `mead_kge_vs_fql_primary` (whichever kind is primary per vintage) and "
        "names the kind used on each side via `old_reference`/`new_reference` -- old and new "
        "use DIFFERENT primary kinds, so that contrast is a same-vintage strict-vs-comparator "
        "read, not an apples-to-apples cross-vintage reference comparison. This script does "
        "NOT compute a constant-demand KGE null; `r29_kge_null_and_demand.py`'s own Part (a) "
        "supplies that once its replay is re-pointed at 5a8a8dab. Top-3 rule-id census: "
        "`r35_placebo_retry_irrigation.py::_rule_id_census()`, imported, rule ids `sorted()` "
        "before counting (the Python set-hash-randomization fix r27/r34/r35 all apply). "
        "Manifest census: `git_commit_short` is value-enforced to start with the vintage's "
        "expected commit prefix (raises otherwise -- all three vintages are pinned commits "
        "here); `model` is value-enforced to `gemma3:4b`; `temperature` / `top_p` are read "
        "and reported (`null` in every manifest read so far -- the EXPECTED value for "
        "irrigation's gemma3:4b runs, not a missing-field symptom); `top_k` and "
        "`retry_feedback_mode` are checked for PRESENCE as top-level manifest keys and "
        "reported \"absent (not a manifest key)\" when missing, never guessed or defaulted to "
        "null. Appraisal-drift rate: `docs/AUDIT_SCHEMA.md`'s `appraisal_drift` / "
        "`appraisal_drifted` columns (key-gated on `audit.initial_proposal_columns`, added "
        "commit 9908ddd8), filtered to rows naming WSA_LABEL specifically -- absent on every "
        "\"old\"/\"mid\" run (both predate that commit), reported \"n/a\", never 0. "
        "Feasible-line retry share: `feasible_by_attempt` (key-gated on "
        "`governance.feasible_set_feedback`, same commit), share of RETRIED rows with a "
        "non-empty value -- same absence caveat. Magnitude-class shares / mean magnitude_af "
        "among executed increases: row selection copied verbatim from "
        "`examples/irrigation_abm/validate_smoke.py::check_j_magnitude_bounds` "
        "(`yearly_decision` in {increase_large, increase_small} AND `magnitude_class` "
        "non-empty -- the non-empty check is what makes the selection EXECUTED-level, per "
        "that function's own \"magnitude_class is set from the executed skill name\" "
        "docstring), absent before the F07 follow-up on commit fe72e43f (every \"old\"/\"mid\" "
        "run). Basin-total request/diversion at years 1/10/20/42 (MAF): "
        "`r28_trajectory_vs_traditional.py::_yearly_series()` with agg=\"sum\", present in "
        "every vintage. Consolidated-Reflection prompt share: a literal substring check for "
        "\"Consolidated Reflection\" (the exact prefix "
        "`examples/irrigation_abm/run_experiment.py` writes at memory-consolidation time) "
        "against every raw JSONL trace record's `input` field, present in every vintage. "
        "`r28_trajectory_vs_traditional.py::_kge_word()` (imported) supplies the plain-read's "
        "\"closely/reasonably reproduces\" / \"only loosely tracks\" / \"does not reproduce\" "
        "language -- no new threshold invented here. `sign_match` (Part 2) is a same-sign "
        "check only; this script does not invent a numeric \"rough size\" tolerance the task "
        "brief did not specify -- both diffs are printed in full so the reader judges "
        "magnitude directly."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
