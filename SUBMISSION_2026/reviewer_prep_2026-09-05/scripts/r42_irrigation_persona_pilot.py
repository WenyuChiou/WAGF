"""R42 -- irrigation persona pilot: does the NEW irrigation corpus (main
branch, commit 431adb5e, PR #54 supply-side redesign PLUS PRs #55-#59 --
context contract on, memory-line opt-out, prompt fixes, history-anchored
water right with paper_water_margin 0.4, silent retry mode) reproduce the
OLD corpus's (commit faf1bb12) governance signature, seed by seed -- with
two earlier vintages kept readable as current-rules references: "mid"
(commit fcd74a5f, persona-diversified, pre-redesign physics) and "prev"
(commit 5a8a8dab, this script's OWN former "new" before the 2026-09-27
retarget below -- persona-diversified, PR #54 redesign physics, pre-PR
#55-59)? Pilot read at whatever seed count has landed; the same code
re-run later gives the n=5 read with zero edits. CPU-only (GPU busy with
the live persona-pilot batch -- this script only reads already-written
CSV/JSON/JSONL files, never launches a run).

VINTAGE / ARM TERMINOLOGY (do not confuse with r25's own "old"/"new")
  Four vintages, oldest to newest (was three before the 2026-09-27 VINTAGE
  RETARGET below added "prev"):
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
      Part 2/2b's contrast (nor the Plain Read gated on it), which stays
      old-vs-new only (the pilot's original question), so an extra vintage
      does not quietly change what "the contrast" means partway through
      this script's life.
    "prev" = commit 5a8a8dab -- PR #54's merge commit, the supply-side
      water-balance redesign (Lake Powell storage buffer, 1-January
      Mead/Powell snapshots, Hung & Yang (2021) magnitude sampling)
      layered on the SAME persona corpus as "mid". This script's OWN
      former "new" (every revision before 2026-09-27), demoted to "prev"
      the moment 431adb5e became the vintage worth checking -- the exact
      same demotion fcd74a5f went through when THIS vintage first
      superseded it (see "mid" above). Supersedes the earlier
      fcd74a5f-as-"new" pilot design point in turn, the way that one
      superseded the 732b2b6c pilot before it (killed, run dir deleted, no
      cell ever landed).
    "new" = commit 431adb5e -- PR #54's redesign PLUS PRs #55-#59 (context
      contract on, memory-line opt-out, prompt fixes, history-anchored
      water right with paper_water_margin 0.4, silent retry mode), layered
      on the SAME persona corpus as "mid"/"prev". The CURRENT pilot target
      (VINTAGE RETARGET, below) -- the only vintage carrying "placebo"/
      "silent" retry-feedback-mode arms in addition to strict/comparator.
  Every vintage carries two arms: "strict" (governed) and a comparator arm
  named DIFFERENTLY per vintage on disk -- "ungoverned" for old (faf1bb12),
  "disabled" for mid (fcd74a5f), prev (5a8a8dab) and new (431adb5e) -- but
  plays the identical no-governance role in every contrast below. This
  script's `role` field ("strict" / "comparator" / "placebo" / "silent")
  is what code branches on; the `arm` field always carries the REAL
  on-disk name so nothing is silently relabelled.

VINTAGE RETARGET 2026-09-27 (PR #55-#59 on top of the 5a8a8dab redesign;
commit 431adb5e -- context contract on, memory-line opt-out, prompt fixes,
history-anchored water right with paper_water_margin 0.4, silent retry
mode)
  Exactly the same demotion this script already documents above (fcd74a5f
  demoted from "new" to "mid" when 5a8a8dab landed) repeats one vintage
  later: 5a8a8dab is demoted from "new" to a FOURTH vintage key, "prev" --
  Part 1 + persona-check only, like "mid", NOT part of Part 2/2b/3's
  contrast -- and "new" is repointed at 431adb5e, the vintage this update
  exists to check. "old" (faf1bb12) and "mid" (fcd74a5f) are UNCHANGED.
  Part 2/2b's old-vs-new contrast is therefore now faf1bb12 (old) vs
  431adb5e (new); 5a8a8dab ("prev") and fcd74a5f ("mid") both sit out of
  that contrast, exactly as "mid" always has.
  The "new" (431adb5e) vintage alone carries TWO EXTRA arms beyond
  strict/comparator: "placebo" and "silent", both strict governance with
  `--retry-feedback-mode placebo|silent` (recorded per-run in
  `reproducibility_manifest.json` as `retry_feedback_mode`) -- rendered as
  additional Part 1 rows (PENDING until their directories exist,
  `EXTRA_ROLES_BY_VINTAGE`) and consumed by the new PART 3 (below).

RUN LAYOUT (examples/irrigation_abm/results/)
  old strict:      strict_42yr_gemma3_4b_faf1bb12_seed{S}
  old comparator:  ungoverned_42yr_gemma3_4b_faf1bb12_seed{S}
  mid strict:      strict_42yr_gemma3_4b_fcd74a5f_seed{S}
  mid comparator:  disabled_42yr_gemma3_4b_fcd74a5f_seed{S}
  prev strict:     strict_42yr_gemma3_4b_5a8a8dab_seed{S}
  prev comparator: disabled_42yr_gemma3_4b_5a8a8dab_seed{S}
  new strict:      strict_42yr_gemma3_4b_431adb5e_seed{S}
  new comparator:  disabled_42yr_gemma3_4b_431adb5e_seed{S}
  new placebo:     placebo_42yr_gemma3_4b_431adb5e_seed{S}
  new silent:      silent_42yr_gemma3_4b_431adb5e_seed{S}
  Seeds 42-46 (placebo/silent land only for "new"). Verified on disk at the
  time this update was made: all 10 old dirs (faf1bb12, both arms, seeds
  42-46) are complete; mid (fcd74a5f) and prev (5a8a8dab) each have ONLY
  their seed42 strict+comparator dirs on disk (both Finished, seeds 43-46
  not yet run for either -- unchanged from before this update); no "new"
  (431adb5e) LLM run dir (strict/comparator/placebo/silent) exists yet for
  any seed. The "new" vintage's TWO FQL reference dirs
  (`fql_raw_norebalance_431adb5e`, `fql_nogov_431adb5e`) are, by contrast,
  ALREADY fully landed -- all 10 seeds (42-51) Finished on disk as of this
  update -- so the FQL side of "new" will not be the blocker once its LLM
  runs start landing. This script renders PENDING for every
  incomplete/missing cell rather than guessing; re-running it later with
  431adb5e LLM seeds landed needs no code change.
  SAME-DAY FOLLOW-UP (FQL REGEN 2026-09-27, commit 78d986ed): the two
  "new" FQL dirs named in this paragraph (`fql_raw_norebalance_431adb5e`,
  `fql_nogov_431adb5e`) are now the LEGACY, pre-warm-start references --
  see "FQL REGEN 2026-09-27" below for the two-hash vintage this
  follow-up introduces (LLM stays 431adb5e, unaffected; only the FQL
  runner and its output dirs changed). The LLM run-dir names/seed counts
  in this RUN LAYOUT section are unaffected by that follow-up.

FQL REFERENCE (vintage-aware, TWO KINDS per vintage, added/revised with
the "new" vintage)
  UPDATED 2026-09-27: every "new"/96394b44 reference this section
  describes below now belongs to "prev" (5a8a8dab, demoted -- see VINTAGE
  RETARGET above); "new" (431adb5e) gets its OWN pair, generated under the
  redesigned+PR#55-59 physics: `fql_raw_norebalance_431adb5e` ("wagfrules")
  and `fql_nogov_431adb5e` ("nogov", PRIMARY, same "unruled FQL is the
  traditional-ABM line" decision carried forward unchanged). Both are
  fully landed on disk (seeds 42-51, all ten Finished) as of this update --
  the FQL side of "new" is ready before a single "new" LLM run has landed.
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
  Only the "prev" (5a8a8dab) and "new" (431adb5e, added 2026-09-27)
  physics trees have a "nogov" dir on disk (`fql_nogov_96394b44` and
  `fql_nogov_431adb5e` respectively, seeds 42-51, all ten with a Finished:
  LAUNCH_COMMAND.txt line as of this update); "old"/"mid" physics
  (faf1bb12/fcd74a5f) never had an ungoverned FQL generated, so
  `FQL_DIR_BY_VINTAGE["old"]["nogov"]` / `["mid"]["nogov"]` are `None` and
  every "nogov" column for those two vintages prints a named "n/a" --
  never a guessed or borrowed value. `FQL_PRIMARY_KIND` records which kind
  is the vintage's PRIMARY, cross-run-comparable KGE reference: "nogov"
  for "prev"/"new" (the true traditional-ABM reference exists for both),
  "wagfrules" for "old"/"mid" BY NECESSITY (no unruled FQL was ever run at
  that physics), not by preference -- Part 2's contrast rows name which
  kind was used per vintage rather than silently treating "primary" as
  the same thing on both sides of old-vs-new. `fql_raw_norebalance_96394b44`
  / `fql_raw_norebalance_431adb5e` ("wagfrules" for "prev"/"new"
  respectively) are still read as a SECOND KGE column for those runs,
  labelled "FQL + WAGF rules" -- this makes the governed-FQL ablation
  directly visible next to the unruled-FQL primary, so a reader can see
  how much of the KGE gap (if any) the WAGF governance layer itself was
  contributing under the earlier, published comparison. Both kinds are
  gated by `_fql_completeness(vintage, seed, kind)` on their own
  LAUNCH_COMMAND.txt carrying a `Finished:` line -- confirmed present for
  `fql_raw_norebalance_faf1bb12` (old/mid), `fql_raw_norebalance_96394b44`
  + `fql_nogov_96394b44` (prev), and `fql_raw_norebalance_431adb5e` +
  `fql_nogov_431adb5e` (new) alike (r28's own `_run_completeness` does not
  check this, since its one frozen FQL dir never needed it).
  `lake_mead_level` timing also differs by vintage:
  `examples/irrigation_abm/run_experiment.py`'s own "Supply-side redesign
  columns" comment states `lake_mead_level` is the 1-JANUARY value the
  agents saw from 5a8a8dab on (so "prev" and "new" share this timing);
  `docs/irrigation_physics.md`'s physics-comparison table confirms the
  pre-redesign series was an END-OF-YEAR series ("one year earlier than
  the 1 January series") for "old"/"mid". Every KGE in this script is
  computed WITHIN one vintage against that SAME vintage's FQL reference
  (both series on the same timing convention), so no single KGE number is
  contaminated by the timing change -- but a reader comparing raw
  `final_year_mead_ft` / `min_mead_ft` values SIDE BY SIDE across vintages
  (Part 1's table shows all four in one table) is comparing two different
  points in the water year across the old/mid vs prev/new boundary.
  Flagged again in Method.
  CONSTANT-DEMAND NULL: not computed here. `r29_kge_null_and_demand.py`
  supplies the constant-demand KGE null (its own Part (a)) once its
  replay is re-pointed at 431adb5e; out of this script's scope.

FQL REGEN 2026-09-27 (commit 78d986ed) -- TWO-HASH VINTAGE, LLM UNCHANGED
  The irrigation LLM corpus stays pinned at framework commit 431adb5e --
  completely UNAFFECTED by this update (`EXPECTED_COMMIT_PREFIX["new"]`
  is still `"431adb5e"`, unchanged; every LLM run dir name in RUN LAYOUT
  above is unchanged). Only the FQL runner changed, at commit 78d986ed:
  the same LLM code, a shared log-row builder across FQL/LLM writers, and
  a CALIBRATED WARM START seeded from Hung & Yang's own
  `Initial_Files/All-1109` (the earlier FQL trees this script read were
  ZERO-INIT -- no calibrated starting state -- a materially different
  initial condition, not a cosmetic rerun). From this update on, "the
  new vintage" is therefore a TWO-HASH thing, not one: LLM=431adb5e (the
  agent/governance code + prompts), FQL=78d986ed (the traditional-ABM
  runner + its warm-start data), tracked as two independent commits
  because the redo touched only the FQL side. `FQL_DIR_BY_VINTAGE["new"]`
  is repointed at the 78d986ed trees:
    "nogov"     -> `fql_nogov_78d986ed` (Hung & Yang's FQL, NO WAGF
      rules, warm-started from All-1109) -- PRIMARY, same "raw/unruled
      FQL is the one traditional-ABM baseline" decision this package has
      held since 2026-09-26, now on the calibrated-warm-start runner.
      This is the ONLY baseline; nothing else in this script substitutes
      for it.
    "wagfrules" -> `fql_raw_norebalance_78d986ed` (the SAME FQL policy
      plus WAGF governance rules on top) -- an SI ABLATION column only,
      shown alongside the primary so a reader can see how much of any
      KGE gap the WAGF layer itself contributes; it is never read as a
      baseline in its own right, exactly as "wagfrules" was never
      primary for any vintage before this one.
  `FQL_LEGACY_DIR_BY_VINTAGE["new"]` (added this update) keeps the
  superseded, pre-warm-start, zero-init 431adb5e FQL pair
  (`fql_nogov_431adb5e`, `fql_raw_norebalance_431adb5e`) readable -- kept
  on disk deliberately, never deleted -- but ONLY for Part 4's reference-
  sensitivity check below; nothing in Part 1/2/2b/3 reads this dict.
  Two SI-only calibration-SNAPSHOT sensitivity dirs also land under the
  78d986ed tree, `fql_nogov_78d986ed_snapshot-All-WRR` and
  `fql_nogov_78d986ed_snapshot-All` (`FQL_SNAPSHOT_DIRS["new"]`) --
  probing whether the specific calibration day's snapshot chosen to seed
  the warm start (as opposed to the `All-1109` snapshot backing the
  primary) moves the KGE read. That choice is PROVENANCE-BASED, not a
  judgment call made here: both snapshot dirs' on-disk
  LAUNCH_COMMAND.txt / manifest provenance fields name the same
  calibration day as `cal_1108`, which is why these two (and not some
  other calibration day) were picked to probe -- PENDING the authors'
  own explicit confirmation that `cal_1108` is in fact the snapshot Hung
  & Yang intended for this comparison. Neither snapshot dir is ever
  primary; both are Part 4 only.
  CONSEQUENCE FOR PART 1/2/2b/3 (intentional, not a bug): because
  `FQL_PRIMARY_KIND["new"]` is `"nogov"` and that dir is now
  `fql_nogov_78d986ed`, every "new"-vintage row in Part 1 (and therefore
  every "new" cell Part 2/2b/3 depend on) gates on 78d986ed's own
  completeness, not 431adb5e's. Until `fql_nogov_78d986ed` lands and
  passes `_fql_completeness`, Part 1/2/2b/3's "new" rows render PENDING
  again -- even though the 431adb5e LLM runs and the legacy 431adb5e FQL
  pair are themselves complete on disk. This is by design: the legacy
  zero-init pair is a superseded reference, not a stand-in for the
  current primary, so this script never silently keeps reading it as if
  it were still current. Part 4 below is the one place both the current
  (78d986ed) and legacy (431adb5e) FQL trees are read side by side, on
  purpose.

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
  DISCOVERED 2026-09-27, once the 78d986ed FQL trees fully landed:
  `_fql_dir_completeness()`'s `Finished:` check (above) is specific to the
  PRE-78d986ed FQL runner's LAUNCH_COMMAND.txt template. The 78d986ed
  runner's shared log-row builder dropped the `Started:`/`Finished:`
  timestamp lines entirely -- verified across all 40 seed-dirs of the
  four 78d986ed trees -- and reports completion via `ExitCode: <n>`
  instead. `_fql_dir_completeness()` now accepts EITHER marker: `Finished:`
  present -> ok (old runner, unchanged); no `Finished:` but `ExitCode: 0`
  present -> ok (new runner); a present nonzero ExitCode -> a real
  failure, never read as complete; neither marker -> still in progress.
  This does not touch `_run_completeness()` (the LLM-run gate above),
  whose own LAUNCH_COMMAND.txt template is unaffected by the FQL regen.

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
  prev, `fql_raw_norebalance_431adb5e` for new) and "nogov" (Hung & Yang's
  FQL with no governance rules, `fql_nogov_96394b44` for prev,
  `fql_nogov_431adb5e` for new -- `None`/"n/a" for old/mid). Three
  fields are written per landed run: `mead_kge_vs_fql_wagfrules` /
  `mead_rmse_vs_fql_wagfrules` (always computed when that dir is ready),
  `mead_kge_vs_fql_nogov` / `mead_rmse_vs_fql_nogov` (prev/new only, "n/a"
  by vintage-structure for old/mid), and `mead_kge_vs_fql_primary` /
  `mead_rmse_vs_fql_primary` (whichever kind `FQL_PRIMARY_KIND[vintage]`
  names -- "nogov" for new, "wagfrules" for old/mid) plus
  `mead_kge_primary_kind` naming which kind that was, so no reader has to
  infer it. `mead_kge_vs_fql_primary` is what Part 2/2b's contrast reads
  (Part 3's retry-feedback-mode ablation reads `mead_kge_vs_fql_nogov`
  directly instead, per its own task brief -- the two happen to be the
  same number for the "new" vintage, since "new"'s primary kind IS
  "nogov", but the field name makes the choice explicit rather than
  incidental); it is always a genuine float whenever a run_metrics row
  exists, because the row itself is gated on the PRIMARY kind's
  completeness (a non-primary kind not being ready never blocks the row,
  only its own column).
  Manifest census: model, git_commit (short + value-enforced to start with
  the vintage's expected prefix, RAISES on mismatch -- all four vintages
  are fully pinned commits here, so this is a real enforcement, not a
  soft check), temperature, top_p (both read directly; irrigation's
  gemma3:4b runs carry no explicit sampling params in any vintage's
  manifest -- confirmed by reading old/mid/prev, all `null` -- so `None`
  here is the EXPECTED value, not a missing-field symptom), top_k (checked for
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

PERSONA CHECK (mid + prev + new vintages -- all three carry the
persona-diversified corpus; old predates it. UPDATED 2026-09-27: "prev"
added to this set -- it always carried the persona corpus, it just was
not yet given its own vintage key before this update)
  For every (arm, seed) directory of the "mid", "prev" or "new" vintage
  that exists on disk (independent of the full completeness gate above -- raw
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
  landed; otherwise the row records which combination is missing and the
  Plain Read reports it as PENDING. `sign_match` = whether diff_old and
  diff_new share the same sign -- reported, never smoothed into a single
  score, since a 2-vintage comparison with a possible n=1 new seed has no
  business claiming more precision than a sign-and-magnitude read.
  "old" is always faf1bb12; "new" is 431adb5e as of the 2026-09-27
  VINTAGE RETARGET above (was 5a8a8dab before that update). "mid" and
  "prev" do not appear here (see VINTAGE/ARM TERMINOLOGY above for why).

PART 2b -- per seed: shortage-tier-years / Mead-min ordering, old vs new
  For each vintage: does strict sit on the governance-benefit side of the
  comparator arm -- fewer shortage-tier years, and a HIGHER Mead minimum?
  (`_loader.py`'s convention: governance is expected to raise the physical
  floor, not lower it.) Reported per seed as `ordering_ok_old` /
  `ordering_ok_new`, again only when all four cells for that seed have
  landed. Each ordering check compares strict vs comparator WITHIN one
  vintage only, so the old/mid Mead-level timing difference documented
  above (end-of-year vs 1-January) never crosses into a single comparison
  here. Same old/new remapping as Part 2 above (new=431adb5e as of
  2026-09-27); "mid"/"prev" sit out, same as Part 2.

PART 3 (NEW, 2026-09-27) -- retry-feedback-mode ablation: silent vs
strict (full governance); placebo alongside
  Within the "new" (431adb5e) vintage ONLY (the sole vintage carrying
  placebo/silent arms -- see VINTAGE RETARGET above), per seed: silent
  minus strict for 8 metrics already computed in Part 1's `run_metrics`
  row (imported values, nothing re-derived) -- IBR conditional (%), IBR
  unconditional (%), rejection rate (%), retry rate (%), appraisal WSA-
  drift rate (%), final-year Mead (ft), min Mead (ft), and Mead KGE vs
  FQL (no governance) (the vintage's PRIMARY "nogov" reference). Placebo
  is reported alongside as a second diff column (placebo minus strict),
  never averaged with silent into one number. A cell is reported only
  when strict, silent AND placebo have all landed for that seed; missing
  arms print a named PENDING row instead (`row_type=skipped,
  section=retry_mode_pair`). A metric that is itself an "n/a (...)"
  string for a given run (e.g. appraisal-drift rate before the audit
  column existed) renders its diff as "n/a (non-numeric cell)" rather
  than raising or silently coercing to 0.

PART 4 (NEW, 2026-09-27 FQL REGEN) -- reference sensitivity: does the FQL
regen at 78d986ed move the read?
  "new" (431adb5e LLM) vintage ONLY, strict and comparator ("disabled")
  roles ONLY (no placebo/silent here -- this is about the FQL reference,
  orthogonal to the retry-feedback-mode ablation in Part 3). Per (role,
  seed): Mead-elevation KGE and basin-TOTAL-diversion KGE (`diversion`
  column, agg="sum", same shape as `_basin_totals_maf`'s own diversion
  read, computed here as a KGE via the SAME `R28._kge_and_rmse()` call
  Part 1 uses for Mead) against FOUR reference trees, gated and reported
  independently so a not-yet-landed tree never blocks the other three:
    1. PRIMARY -- `fql_nogov_78d986ed` (Hung & Yang's FQL, warm-started
       from `Initial_Files/All-1109`; see FQL REGEN 2026-09-27 above).
    2. SI sensitivity -- `fql_nogov_78d986ed_snapshot-All-WRR`.
    3. SI sensitivity -- `fql_nogov_78d986ed_snapshot-All`.
    4. LEGACY -- `fql_nogov_431adb5e` (the pre-warm-start, zero-init FQL
       this script read as "new"'s primary before the FQL REGEN above;
       kept on disk, read here and ONLY here).
  Additionally, PRIMARY reference ONLY: the per-agent-median diversion
  KGE -- for every agent present in BOTH the LLM run and the FQL
  reference (agent_id sets are expected identical; a mismatch RAISES,
  not silently intersects), that agent's own 42-year diversion series
  gets its own KGE against the reference's same agent, and the MEDIAN of
  those per-agent KGEs is reported (`statistics.median`, stdlib). This is
  a finer-grained companion to the basin-total diversion KGE above, which
  can look fine even when individual agents' trajectories diverge and the
  basin sum still lines up -- computed for the primary reference only
  (the task brief scopes it there; the three sensitivity trees get the
  two basin-level KGEs only, not a second per-agent read).
  This block answers "does the regenerated FQL runner (shared log-row
  builder + calibrated warm start, vs. the old zero-init trees) move the
  KGE read at all" -- an SI robustness check, never a second primary
  alongside Part 1's. A (role, seed) whose LLM run itself is not
  complete renders ONE `row_type=skipped` row (no `reference_kind` --
  nothing about any reference tree is checked without a run to check it
  against). A complete LLM run still renders PENDING, per reference tree,
  independently, for whichever of the four trees is not yet Finished on
  disk -- exactly the "reads_pending_not_absent" pattern this script uses
  everywhere else, applied here across four references instead of one.

PLAIN READ (per seed, gated on landing -- this block was labelled "PART 3"
in this docstring before the 2026-09-27 update above claimed that number
for the retry-feedback-mode ablation; the rendered .md heading has always
been "## Plain read", never "## Part 3", so there is no output collision,
only a docstring-numbering one, now fixed)
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
    ordering_pair, retry_mode_pair, reference_sensitivity}. The new
    (2026-09-26) columns described in Part 1 above are additional FIELDS
    on the existing `run_metrics` row_type, not a new row_type;
    `retry_mode_pair` (2026-09-27, Part 3 above) IS a new row_type, since
    it holds a strict/silent/placebo triple per seed rather than one
    arm's numbers. `reference_sensitivity` (2026-09-27, Part 4 above, FQL
    REGEN) is also a new row_type, one row per (arm, seed, reference_kind)
    -- see PART 4 above.
  out/r42_irrigation_persona_pilot.md -- GENERATED by render_md() directly
    from that same `rows` list (no number typed by hand).

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r42_irrigation_persona_pilot.py
"""
from __future__ import annotations

import json
import os
import re
import statistics
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

# VINTAGE_ARM_DIRS keys double as the `role` field on every row this
# script writes for that vintage (see _arm_name_for). "old"/"mid"/"prev"
# carry exactly two roles (strict/comparator); "new" (431adb5e) carries
# two MORE -- "placebo"/"silent", the retry-feedback-mode arms named in
# the 2026-09-27 VINTAGE RETARGET above -- so its dict has 4 entries, not
# 2. Dict order is also render order (Part 1's tables iterate vintages via
# `VINTAGES_ORDERED` and roles via `_iter_vintage_roles()`, both consistent
# with insertion order here).
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
    "prev": {
        "strict": lambda seed: os.path.join(
            IRR_RESULTS, f"strict_42yr_gemma3_4b_5a8a8dab_seed{seed}"),
        "comparator": lambda seed: os.path.join(
            IRR_RESULTS, f"disabled_42yr_gemma3_4b_5a8a8dab_seed{seed}"),
    },
    "new": {
        "strict": lambda seed: os.path.join(
            IRR_RESULTS, f"strict_42yr_gemma3_4b_431adb5e_seed{seed}"),
        "comparator": lambda seed: os.path.join(
            IRR_RESULTS, f"disabled_42yr_gemma3_4b_431adb5e_seed{seed}"),
        "placebo": lambda seed: os.path.join(
            IRR_RESULTS, f"placebo_42yr_gemma3_4b_431adb5e_seed{seed}"),
        "silent": lambda seed: os.path.join(
            IRR_RESULTS, f"silent_42yr_gemma3_4b_431adb5e_seed{seed}"),
    },
}
# Fixed rendering order for Part 1's per-vintage tables (see
# _iter_vintage_roles). Contrast-relevant order (Part 2/2b) is separately
# fixed as ("old", "new") inside _four_cells -- unaffected by this list.
VINTAGES_ORDERED = ("old", "mid", "prev", "new")
# Vintages carrying the persona-diversified corpus (see PERSONA CHECK doc).
PERSONA_VINTAGES = ("mid", "prev", "new")
# Roles beyond strict/comparator, by vintage -- only "new" (431adb5e) has
# any (placebo/silent, the retry-feedback-mode arms). Empty for every other
# vintage via .get(vintage, ()).
EXTRA_ROLES_BY_VINTAGE = {"new": ("placebo", "silent")}
COMPARATOR_ARM_NAME = {"old": "ungoverned", "mid": "disabled", "prev": "disabled",
                        "new": "disabled"}
EXPECTED_COMMIT_PREFIX = {"old": "faf1bb12", "mid": "fcd74a5f", "prev": "5a8a8dab",
                           "new": "431adb5e"}
TOP_N_RULES = 3


def _arm_name_for(vintage: str, role: str) -> str:
    """The REAL on-disk arm name for (vintage, role). Only "comparator" is
    remapped per vintage (COMPARATOR_ARM_NAME -- "ungoverned" for old,
    "disabled" everywhere else); "strict"/"placebo"/"silent" are already
    their own on-disk name in every vintage that carries them. Single
    source of truth for both `_part1` (which needs the mapping to look up
    `_find()` rows by arm=) and `_iter_vintage_roles()` (render_md)."""
    return COMPARATOR_ARM_NAME[vintage] if role == "comparator" else role


def _iter_vintage_roles():
    """Yields (vintage, role, arm_name) across VINTAGES_ORDERED x each
    vintage's own roles (strict/comparator plus EXTRA_ROLES_BY_VINTAGE) --
    the single grid every Part 1 render_md table iterates, so adding a
    vintage or an extra role (as this 2026-09-27 update did for "prev" and
    "placebo"/"silent") only has to be taught to this one function, not
    re-typed into 6 separate table loops."""
    for vintage in VINTAGES_ORDERED:
        roles = ("strict", "comparator") + EXTRA_ROLES_BY_VINTAGE.get(vintage, ())
        for role in roles:
            yield vintage, role, _arm_name_for(vintage, role)


# Vintage-aware, TWO-KIND FQL reference dirs (see module docstring "FQL
# REFERENCE"). "wagfrules" = run_fql_baseline.py WITH the 12 governance
# validators (every LAUNCH_COMMAND.txt below lacks --no-governance) -- the
# governed FQL ablation this package has always used. "nogov" =
# run_fql_baseline.py --no-governance -- Hung & Yang's FQL with NO WAGF
# rules, confirmed via fql_nogov_96394b44/seed*/LAUNCH_COMMAND.txt (prev)
# and fql_nogov_431adb5e/seed*/LAUNCH_COMMAND.txt (new). "old"/"mid" share
# pre-redesign physics (fcd74a5f predates fe72e43f) and so share the SAME
# frozen "wagfrules" reference every other reviewer-prep script already
# reads; neither ever had an unruled FQL run generated, so their "nogov"
# entry is None (n/a downstream, never guessed). "prev" (5a8a8dab) and
# "new" (431adb5e, added 2026-09-27) each have their OWN both-kind pair,
# generated under their own physics tree -- "prev"'s pair is the same
# 96394b44 dirs this table has always carried under the "new" key before
# the retarget; "new"'s pair (fql_raw_norebalance_431adb5e,
# fql_nogov_431adb5e) is generated fresh under 431adb5e, already fully
# landed (seeds 42-51, all Finished) as of this update.
# "new"'s pair REPOINTED 2026-09-27 (FQL REGEN, commit 78d986ed -- see
# module docstring) from the zero-init 431adb5e trees to the
# calibrated-warm-start 78d986ed trees. The LLM side of "new" is still
# 431adb5e, unaffected -- see EXPECTED_COMMIT_PREFIX below, unchanged.
# The superseded 431adb5e FQL pair is NOT deleted from this dict by
# accident-proofing it out of existence; it moves to
# FQL_LEGACY_DIR_BY_VINTAGE (below), read only by Part 4.
FQL_DIR_BY_VINTAGE = {
    "old": {"wagfrules": "fql_raw_norebalance_faf1bb12", "nogov": None},
    "mid": {"wagfrules": "fql_raw_norebalance_faf1bb12", "nogov": None},
    "prev": {"wagfrules": "fql_raw_norebalance_96394b44", "nogov": "fql_nogov_96394b44"},
    "new": {"wagfrules": "fql_raw_norebalance_78d986ed", "nogov": "fql_nogov_78d986ed"},
}
# The superseded, pre-warm-start, zero-init "new" FQL pair (431adb5e),
# added 2026-09-27 alongside the FQL_DIR_BY_VINTAGE repoint above. Read
# ONLY by Part 4's reference-sensitivity check -- never by Part 1/2/2b/3,
# so a stale reference can never quietly stand in for the current
# primary. Only "new" has ever had a superseded pair (no other vintage's
# FQL dir has been regenerated), so this dict has exactly one key.
FQL_LEGACY_DIR_BY_VINTAGE = {
    "new": {"wagfrules": "fql_raw_norebalance_431adb5e", "nogov": "fql_nogov_431adb5e"},
}
# SI-only calibration-snapshot sensitivity trees, both under the 78d986ed
# runner (added 2026-09-27, FQL REGEN) -- see module docstring for why
# "cal_1108" was the provenance-based pick. Read ONLY by Part 4, and only
# for the two basin-level KGEs (never the per-agent-median metric, which
# is scoped to the primary reference). Neither key is a "kind" in the
# FQL_DIR_BY_VINTAGE / FQL_PRIMARY_KIND sense (wagfrules/nogov) --
# both snapshot dirs are themselves "nogov"-shaped (no WAGF rules), just
# seeded from a different calibration day's snapshot than the primary.
FQL_SNAPSHOT_DIRS = {
    "new": {
        "snapshot-All-WRR": "fql_nogov_78d986ed_snapshot-All-WRR",
        "snapshot-All": "fql_nogov_78d986ed_snapshot-All",
    },
}
# The PRIMARY, cross-run-comparable KGE reference per vintage. "prev" and
# "new" both have a true unruled FQL, so Wenyu's 2026-09-26 decision (kept
# unchanged by the 2026-09-27 retarget) makes THAT primary for both;
# "old"/"mid" never had one generated, so their existing governed
# reference remains primary BY NECESSITY, not by preference -- Part 2's
# contrast rows name which kind was used per vintage rather than silently
# treating "primary" as the same thing on both sides.
FQL_PRIMARY_KIND = {"old": "wagfrules", "mid": "wagfrules", "prev": "nogov", "new": "nogov"}
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
# Part 3 (NEW, 2026-09-27) -- retry-feedback-mode ablation constants
# =============================================================================
# The one vintage carrying placebo/silent arms (see EXTRA_ROLES_BY_VINTAGE).
RETRY_MODE_VINTAGE = "new"
# "strict" here means FULL governance (the task brief's "full"), i.e. the
# SAME strict arm Part 1/2/2b already read for this vintage -- not a
# separate run.
RETRY_MODE_ROLES = ("strict", "silent", "placebo")
# label -> `run_metrics` field name, all already computed by _part1 (Part 3
# reuses per_run, never re-derives). Order is render order.
RETRY_MODE_METRIC_KEYS = {
    "IBR conditional (%)": "ibr_conditional",
    "IBR unconditional (%)": "ibr_unconditional",
    "Rejection rate (%)": "rejection_rate_pct",
    "Retry rate (%)": "retry_rate_pct",
    "Appraisal WSA-drift rate (%)": "appraisal_wsa_drift_rate_pct",
    "Final-year Mead (ft)": "final_year_mead_ft",
    "Min Mead (ft)": "min_mead_ft",
    "Mead KGE vs FQL (no governance)": "mead_kge_vs_fql_nogov",
}


# =============================================================================
# Part 4 (NEW, 2026-09-27 FQL REGEN, commit 78d986ed) -- reference
# sensitivity constants
# =============================================================================
# The vintage whose FQL reference was regenerated at 78d986ed. Happens to
# equal RETRY_MODE_VINTAGE today, but for an unrelated reason (that
# constant names the one vintage carrying placebo/silent arms; this one
# names the one vintage whose FQL runner changed) -- kept as its own name
# so the two concepts are never silently conflated if a future update
# ever makes them diverge.
FQL_REGEN_VINTAGE = "new"
FQL_REGEN_ROLES = ("strict", "comparator")
# kind -> dir name, resolved from the three dicts above so this is the
# ONE place Part 4 decides which physical directory backs each of its
# four reference trees. Order is render order; "primary" is listed first
# on purpose (it is the only kind carrying the per-agent-median metric).
PART4_REFERENCE_DIRS = {
    "primary": FQL_DIR_BY_VINTAGE[FQL_REGEN_VINTAGE]["nogov"],
    "snapshot_all_wrr": FQL_SNAPSHOT_DIRS[FQL_REGEN_VINTAGE]["snapshot-All-WRR"],
    "snapshot_all": FQL_SNAPSHOT_DIRS[FQL_REGEN_VINTAGE]["snapshot-All"],
    "legacy_zeroinit": FQL_LEGACY_DIR_BY_VINTAGE[FQL_REGEN_VINTAGE]["nogov"],
}
PART4_REFERENCE_ORDER = ("primary", "snapshot_all_wrr", "snapshot_all", "legacy_zeroinit")
PART4_REFERENCE_LABEL = {
    "primary": "FQL nogov 78d986ed, All-1109 warm start (PRIMARY)",
    "snapshot_all_wrr": "FQL nogov 78d986ed, calibration snapshot All-WRR (SI)",
    "snapshot_all": "FQL nogov 78d986ed, calibration snapshot All (SI)",
    "legacy_zeroinit": "FQL nogov 431adb5e, pre-warm-start zero-init (legacy)",
}
# Only "primary" carries the per-agent-median diversion KGE (task brief
# scope); the other three kinds print a named "n/a" for that column.
PART4_PER_AGENT_MEDIAN_KIND = "primary"


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


def _fql_dir_completeness(fql_root: str, seed: str) -> tuple:
    """(status, reason) with status in {"ok", "skipped", "fail"}, for an
    arbitrary FQL results-dir ROOT (`fql_root/seed{seed}/...`) -- the
    (vintage, kind)-independent half of `_fql_completeness`'s gate,
    factored out (2026-09-27, FQL REGEN) so Part 4's four reference trees
    can share exactly one completeness check. Only "primary" among Part
    4's four kinds is also indexed in FQL_DIR_BY_VINTAGE; the other three
    (two calibration-snapshot sensitivity dirs, one legacy zero-init dir)
    are not, so a check keyed on an absolute root rather than
    (vintage, kind) is what lets all four share this one function.
    `r28_trajectory_vs_traditional.py::_run_completeness` only checks
    dir+simulation_log.csv -- fine for a frozen FQL dir that finished
    months ago, but this package's task brief asked for an explicit
    completion check because newly generated FQL dirs can land out of
    order with the LLM/FQL runs that reference them.
    "fail" vs "skipped" (2026-09-27 REVIEW FIX, P1-a): a genuine run
    failure (a present, nonzero `ExitCode:`) must never be reported the
    same way as "still running" -- callers render "fail" as an explicit
    FAIL, never folded into a PENDING label.
    TWO completion-marker formats, by FQL-runner vintage (discovered
    2026-09-27, verified across all 40 seed-dirs of the four 78d986ed
    trees before adding this branch -- not assumed from one sample):
    old-runner dirs (pre-78d986ed) carry `Started:`/`Finished:` timestamp
    lines AND an `ExitCode:` line (e.g. `fql_nogov_431adb5e`); the
    78d986ed runner's shared log-row builder DROPPED the Started:/
    Finished: pair entirely and reports completion via `ExitCode: <n>`
    alone (confirmed present-and-absent respectively on every one of
    those 40 dirs, not an occasional formatting quirk).
    Decision order:
      1. Whenever an `ExitCode:` line exists at all (old-runner dirs
         carry one alongside `Finished:`; new-runner dirs carry only
         this), it MUST be 0 -- a present nonzero ExitCode is "fail",
         regardless of whether `Finished:` is also present.
      2. `Finished:` present (with no ExitCode line, or an ExitCode: 0
         already cleared by step 1) -- the LEGACY-OK case: accepted
         directly, no further check. This path exists ONLY for dirs with
         no ExitCode line at all (the oldest, pre-ExitCode-field format);
         a Finished:+ExitCode:0 dir also lands here since step 1 already
         cleared it.
      3. No `Finished:` line (new-runner format) but a cleared
         `ExitCode: 0` from step 1 -- ALSO require
         `reproducibility_manifest.json` to exist (the new runner's own
         completeness signature Part 1/Part 4 both expect); missing ->
         still "skipped" (in progress), not "fail" (a lagging manifest
         write is not itself evidence of failure).
      4. Neither marker present -> "skipped", still in progress."""
    fql_dir = os.path.join(fql_root, f"seed{seed}")
    status, reason = R28._run_completeness(fql_dir)
    if status == "skipped":
        return status, reason
    lc_path = os.path.join(fql_dir, "LAUNCH_COMMAND.txt")
    if not os.path.isfile(lc_path):
        return "skipped", "LAUNCH_COMMAND.txt missing (FQL run in progress)"
    lc_text = open(lc_path, encoding="utf-8", errors="replace").read()
    has_finished = "Finished:" in lc_text
    m = re.search(r"^ExitCode:\s*(-?\d+)\s*$", lc_text, re.MULTILINE)
    if m is not None:
        exit_code = int(m.group(1))
        if exit_code != 0:
            return "fail", f"LAUNCH_COMMAND.txt reports ExitCode: {exit_code} (FQL run failed)"
    if has_finished:
        return "ok", None
    if m is None:
        return "skipped", ("LAUNCH_COMMAND.txt has no Finished: or ExitCode: line "
                            "(FQL run in progress)")
    manifest_path = os.path.join(fql_dir, "reproducibility_manifest.json")
    if not os.path.isfile(manifest_path):
        return "skipped", ("reproducibility_manifest.json missing (FQL run in progress, "
                            "new-runner format)")
    return "ok", None


def _fql_completeness(vintage: str, seed: str, kind: str) -> tuple:
    """FQL reference dir completeness for `vintage`'s `kind` ("wagfrules"
    or "nogov") Mead-KGE baseline -- `FQL_DIR_BY_VINTAGE[vintage][kind] is
    None` (no unruled FQL exists for old/mid physics) short-circuits to
    "skipped" without touching disk -- a structural absence, not an
    in-progress run, but the same tuple shape lets every caller handle
    both the same way. Delegates the actual dir/file gate to
    `_fql_dir_completeness` (2026-09-27, FQL REGEN -- factored out so
    Part 4's non-(vintage,kind)-indexed reference trees share it too).
    Verified present for `fql_raw_norebalance_faf1bb12` (old/mid
    "wagfrules"), `fql_raw_norebalance_96394b44` (prev "wagfrules") and
    `fql_nogov_96394b44` (prev "nogov"), seeds 42-46 alike; "new" now
    resolves to the 78d986ed trees (see FQL REGEN 2026-09-27)."""
    dir_name = FQL_DIR_BY_VINTAGE[vintage][kind]
    if dir_name is None:
        return "skipped", f"no {kind!r} FQL reference exists for vintage {vintage!r} (structural)"
    return _fql_dir_completeness(os.path.join(IRR_RESULTS, dir_name), seed)


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
    if fql_status != "ok":
        raise PrepError(f"FQL {kind!r} reference ({fql_dir_name!r}) seed {seed} for vintage "
                         f"{vintage!r} not available ({fql_status}): {fql_reason} (caller "
                         f"should have pre-checked)")
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
    confirmed present at this same call site across all four vintages
    (faf1bb12, fcd74a5f, 5a8a8dab, and 431adb5e -- `git show
    431adb5e:examples/irrigation_abm/run_experiment.py` still carries the
    literal `_REFLECTION_MEMORY_PREFIX = "Consolidated Reflection: "`,
    checked 2026-09-27 since PR #55-59's "memory-line opt-out" could
    plausibly have touched this exact string). Computed for every vintage.
    Raw traces file missing (run in progress, or none written) -> "n/a"."""
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
            # _arm_name_for, not a bare "strict"/COMPARATOR_ARM_NAME check:
            # "new" (431adb5e) also carries "placebo"/"silent" roles, whose
            # arm_name IS the role itself (their on-disk dir already names
            # them placebo_.../silent_...), not the comparator's name.
            arm_name = _arm_name_for(vintage, role)
            for seed in SEEDS:
                run_dir = dir_fn(seed)
                status, reason = _run_completeness(run_dir)
                if status == "ok":
                    primary_kind = FQL_PRIMARY_KIND[vintage]
                    fql_status, fql_reason = _fql_completeness(vintage, seed, primary_kind)
                    if fql_status != "ok":
                        status = fql_status  # "skipped" (in progress) or "fail" (real failure)
                        tag = "FAILED" if fql_status == "fail" else "not ready"
                        reason = (f"primary FQL reference ({primary_kind}, "
                                  f"{FQL_DIR_BY_VINTAGE[vintage][primary_kind]})/seed{seed} "
                                  f"{tag}: {fql_reason}")
                if status != "ok":
                    label = "FAILED" if status == "fail" else "SKIPPED"
                    print(f"  {label} {vintage}/{arm_name} seed {seed}: {reason}")
                    rows.append({"row_type": "skipped", "status": status, "vintage": vintage,
                                 "arm": arm_name, "role": role, "seed": seed, "reason": reason})
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
                    # attempted (all four vintages have a dir); "nogov"
                    # only exists for "prev"/"new" (FQL_DIR_BY_VINTAGE[...]
                    # ["nogov"] is None for old/mid, per the FQL REFERENCE
                    # docstring).
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
                        if fql_status != "ok":
                            tag = "FAILED" if fql_status == "fail" else "not ready"
                            na = f"n/a (FQL {dir_name}/seed{seed} {tag}: {fql_reason})"
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

                if vintage in PERSONA_VINTAGES:
                    rows.append(_persona_check(vintage, arm_name, seed, run_dir))
    return per_run


def _four_cells_retry_mode(per_run: dict, seed: str) -> tuple:
    """({role: run_metrics_row}, [missing role names]) for RETRY_MODE_VINTAGE
    ("new"/431adb5e) at one seed, over RETRY_MODE_ROLES (strict/silent/
    placebo). Returns the whole `run_metrics` row per role (not one field)
    since Part 3 reads 8 different fields off the same three rows."""
    cells, missing = {}, []
    for role in RETRY_MODE_ROLES:
        v = per_run.get((RETRY_MODE_VINTAGE, role, seed))
        if v is None:
            missing.append(role)
        else:
            cells[role] = v
    return cells, missing


def _part3_retry_mode(rows: list, per_run: dict) -> None:
    """Silent vs strict (full governance), placebo alongside, within
    RETRY_MODE_VINTAGE ("new"/431adb5e) only -- see module docstring PART 3
    (NEW, 2026-09-27). A metric/seed cell is emitted only when strict,
    silent AND placebo have all landed for that seed; otherwise a named
    PENDING row (row_type=skipped, section=retry_mode_pair) is appended
    instead, listing exactly which role(s) are missing."""
    for seed in SEEDS:
        cells, missing = _four_cells_retry_mode(per_run, seed)
        if missing:
            missing_labels = [f"{RETRY_MODE_VINTAGE}/{r}" for r in missing]
            print(f"  Part 3 PENDING: retry-feedback-mode ablation seed {seed} -- "
                  f"missing {missing_labels}")
            rows.append({"row_type": "skipped", "section": "retry_mode_pair", "seed": seed,
                         "reason": f"missing: {', '.join(missing_labels)}"})
            continue
        strict_row = cells["strict"]
        for metric_label, key in RETRY_MODE_METRIC_KEYS.items():
            strict_v = strict_row[key]
            silent_v = cells["silent"][key]
            placebo_v = cells["placebo"][key]

            def _diff(other_v):
                if isinstance(other_v, str) or isinstance(strict_v, str):
                    return "n/a (non-numeric cell)"
                return other_v - strict_v

            rows.append({
                "row_type": "retry_mode_pair", "metric": metric_label, "seed": seed,
                "strict_value": strict_v, "silent_value": silent_v,
                "diff_silent": _diff(silent_v),
                "placebo_value": placebo_v, "diff_placebo": _diff(placebo_v),
            })


# =============================================================================
# Part 4 (NEW, 2026-09-27 FQL REGEN, commit 78d986ed) -- reference
# sensitivity: does the regenerated FQL runner move the KGE read?
# =============================================================================
def _series_kge_vs_dir(sim_path: str, fql_root: str, seed: str, col: str, agg: str) -> dict:
    """KGE/RMSE of `col` (aggregated across agents per year via `agg`)
    between the LLM run's own simulation_log.csv (`sim_path`) and an
    ARBITRARY FQL reference root (`fql_root/seed{seed}/simulation_log.csv`)
    -- byte-identical call sequence to `_mead_kge_vs_fql` above
    (`R28._yearly_series` + `R28._kge_and_rmse`), generalised to take a
    results-dir root directly rather than a (vintage, kind) pair, since
    Part 4 checks FOUR reference trees per (role, seed), only one of
    which (primary) is indexed in FQL_DIR_BY_VINTAGE. Raises if the year
    sets differ -- a real data bug, not a completeness gap; callers are
    expected to have already gated the reference tree via
    `_fql_dir_completeness`."""
    years, sim_vals = R28._yearly_series(sim_path, col, agg)
    ref_path = os.path.join(fql_root, f"seed{seed}", C.L.SIM_LOG)
    ref_years, ref_vals = R28._yearly_series(ref_path, col, agg)
    if ref_years != years:
        raise PrepError(f"{sim_path} vs {ref_path}: year sets differ for column {col!r} "
                         f"({years[:3]}..{years[-3:]} vs {ref_years[:3]}..{ref_years[-3:]})")
    return R28._kge_and_rmse(sim_vals, ref_vals)


def _diversion_kge_per_agent_median(sim_path: str, fql_root: str, seed: str) -> dict:
    """Median, across agents present in BOTH runs, of the per-agent KGE of
    that agent's OWN 42-year diversion series (LLM run vs the FQL
    reference) -- a finer-grained companion to `_series_kge_vs_dir`'s
    basin-TOTAL diversion KGE, which can look fine even when individual
    agents' trajectories diverge and the basin sum still lines up.
    `agent_id` sets are expected IDENTICAL between an LLM run and its FQL
    reference (same persona roster, same environment) -- a mismatch
    RAISES rather than silently comparing whatever intersects. Reads via
    `C.read_csv` (plain dict rows, matching this script's non-pandas
    style elsewhere) rather than r28's pandas-based `_yearly_series`,
    since this needs a per-agent grouping `_yearly_series` does not do.
    2026-09-27 REVIEW FIX (Should-fix): two corrections from the first
    version of this function --
      (1) ALIGN BY YEAR SET, not by list length: each agent's series is
          now a {year: value} dict; the two dicts' KEY SETS (not just
          their lengths) must match before pairing values, so two
          equal-length series over DIFFERENT year sets can never be
          silently zipped at the wrong years.
      (2) SKIP CONSTANT/ZERO-MEAN SERIES EXPLICITLY: an agent whose
          diversion never changes across the run (sd==0, either side) or
          whose reference series has mean 0 -- the EXACT conditions
          `R28._kge_and_rmse` itself raises PrepError on -- is a real,
          expected edge case (an agent that never diverts, or a
          constant-`maintain_demand` agent under one arm), not a data
          bug, so it is SKIPPED here rather than aborting the whole
          per-agent-median computation for the seed. The skipped count is
          returned as `n_skipped_constant`, never silently absorbed into
          `n_agents` (which counts only agents that actually contributed
          a KGE to the median)."""
    sim_rows = C.read_csv(sim_path)
    ref_path = os.path.join(fql_root, f"seed{seed}", C.L.SIM_LOG)
    ref_rows = C.read_csv(ref_path)

    def _by_agent(csv_rows):
        out: dict = {}
        for r in csv_rows:
            aid = r["agent_id"]
            out.setdefault(aid, {})[int(r["year"])] = float(r["diversion"])
        return out

    sim_by_agent = _by_agent(sim_rows)
    ref_by_agent = _by_agent(ref_rows)
    sim_agents, ref_agents = set(sim_by_agent), set(ref_by_agent)
    if sim_agents != ref_agents:
        raise PrepError(f"{sim_path} vs {ref_path}: agent_id sets differ (sim has "
                         f"{len(sim_agents)}, ref has {len(ref_agents)}, symmetric "
                         f"difference {len(sim_agents ^ ref_agents)})")
    kges = []
    n_skipped_constant = 0
    for agent_id in sorted(sim_agents):
        sim_by_year, ref_by_year = sim_by_agent[agent_id], ref_by_agent[agent_id]
        if set(sim_by_year) != set(ref_by_year):
            sim_years, ref_years = sorted(sim_by_year), sorted(ref_by_year)
            raise PrepError(f"{sim_path} vs {ref_path}: agent {agent_id!r} year sets differ "
                             f"(sim {sim_years[:3]}..{sim_years[-3:]} vs "
                             f"ref {ref_years[:3]}..{ref_years[-3:]})")
        common_years = sorted(sim_by_year)
        s = [sim_by_year[y] for y in common_years]
        r = [ref_by_year[y] for y in common_years]
        if C.sd(s) == 0 or C.sd(r) == 0 or C.mean(r) == 0:
            n_skipped_constant += 1
            continue
        stats = R28._kge_and_rmse(s, r)
        kges.append(stats["kge"])
    if not kges:
        raise PrepError(f"{sim_path} vs {ref_path}: every agent's diversion series was "
                         f"constant/zero-mean ({n_skipped_constant} of {len(sim_agents)} "
                         f"skipped) -- no per-agent KGE could be computed")
    return {"median_kge": statistics.median(kges), "n_agents": len(kges),
            "n_skipped_constant": n_skipped_constant}


def _part4_reference_sensitivity(rows: list) -> None:
    """SI reference-sensitivity check for FQL_REGEN_VINTAGE ("new"/431adb5e
    LLM) ONLY -- see module docstring PART 4. For strict and comparator
    ("disabled"), per seed: Mead-elevation KGE and basin-total-diversion
    KGE against each of PART4_REFERENCE_ORDER's four reference trees,
    gated and reported INDEPENDENTLY per tree (a not-yet-landed
    calibration-snapshot or legacy dir never blocks the other three).
    The primary reference ALSO gets the per-agent-median diversion KGE
    (task-brief scope); the other three kinds print a named "n/a" for
    that column, never a borrowed or duplicated number. A (role, seed)
    whose LLM run itself is not complete renders ONE `row_type=skipped`
    row (no `reference_kind` -- nothing about any reference tree is
    checked without a run to check it against). 2026-09-27 REVIEW FIX
    (P1-a): a reference tree whose `_fql_dir_completeness` status is
    "fail" (a genuine nonzero ExitCode, never a mid-run state) renders a
    `status="fail"` skipped row and an explicit FAIL print/label, never
    folded into the ordinary "PENDING" (still-running) case."""
    for role in FQL_REGEN_ROLES:
        arm_name = _arm_name_for(FQL_REGEN_VINTAGE, role)
        run_dir_fn = VINTAGE_ARM_DIRS[FQL_REGEN_VINTAGE][role]
        for seed in SEEDS:
            run_dir = run_dir_fn(seed)
            status, reason = _run_completeness(run_dir)
            if status == "skipped":
                print(f"  Part 4 PENDING: {FQL_REGEN_VINTAGE}/{arm_name} seed {seed} -- "
                      f"LLM run not ready: {reason}")
                rows.append({"row_type": "skipped", "section": "reference_sensitivity",
                             "status": "skipped", "vintage": FQL_REGEN_VINTAGE,
                             "arm": arm_name, "seed": seed,
                             "reason": f"LLM run not ready: {reason}"})
                continue
            sim_path = os.path.join(run_dir, C.L.SIM_LOG)
            for kind in PART4_REFERENCE_ORDER:
                dir_name = PART4_REFERENCE_DIRS[kind]
                fql_root = os.path.join(IRR_RESULTS, dir_name)
                ref_status, ref_reason = _fql_dir_completeness(fql_root, seed)
                if ref_status != "ok":
                    label = "FAIL" if ref_status == "fail" else "PENDING"
                    print(f"  Part 4 {label}: {arm_name} seed {seed} ref={kind} "
                          f"({dir_name}) -- {ref_reason}")
                    rows.append({"row_type": "skipped", "section": "reference_sensitivity",
                                 "status": ref_status, "vintage": FQL_REGEN_VINTAGE,
                                 "arm": arm_name, "seed": seed, "reference_kind": kind,
                                 "reference_dir": dir_name, "reason": ref_reason})
                    continue
                mead_stats = _series_kge_vs_dir(sim_path, fql_root, seed, "lake_mead_level",
                                                 "first")
                div_stats = _series_kge_vs_dir(sim_path, fql_root, seed, "diversion", "sum")
                row = {
                    "row_type": "reference_sensitivity", "vintage": FQL_REGEN_VINTAGE,
                    "arm": arm_name, "seed": seed, "reference_kind": kind,
                    "reference_dir": dir_name,
                    "mead_kge_vs_reference": mead_stats["kge"],
                    "mead_rmse_vs_reference": mead_stats["rmse"],
                    "diversion_kge_vs_reference": div_stats["kge"],
                    "diversion_rmse_vs_reference": div_stats["rmse"],
                }
                na = "n/a (per-agent median computed for the primary reference only)"
                if kind == PART4_PER_AGENT_MEDIAN_KIND:
                    med = _diversion_kge_per_agent_median(sim_path, fql_root, seed)
                    row["diversion_kge_per_agent_median"] = med["median_kge"]
                    row["diversion_kge_per_agent_n"] = med["n_agents"]
                    row["diversion_kge_per_agent_n_skipped_constant"] = med["n_skipped_constant"]
                else:
                    row["diversion_kge_per_agent_median"] = na
                    row["diversion_kge_per_agent_n"] = na
                    row["diversion_kge_per_agent_n_skipped_constant"] = na
                rows.append(row)
                print(f"  OK Part 4 {arm_name} seed {seed} ref={kind}: "
                      f"mead_kge={mead_stats['kge']:.3f} "
                      f"diversion_kge={div_stats['kge']:.3f}")


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
    "strict_value", "silent_value", "diff_silent", "placebo_value", "diff_placebo",
    "reference_kind", "reference_dir",
    "mead_kge_vs_reference", "mead_rmse_vs_reference",
    "diversion_kge_vs_reference", "diversion_rmse_vs_reference",
    "diversion_kge_per_agent_median", "diversion_kge_per_agent_n",
    "diversion_kge_per_agent_n_skipped_constant",
]


def main() -> int:
    C.banner("R42  Irrigation persona pilot: new corpus (431adb5e) vs old corpus "
             "(faf1bb12); mid (fcd74a5f) + prev (5a8a8dab) kept as earlier references")
    rows: list = []

    print("\n-- Part 1: per (vintage, arm, seed) metrics, rule census, manifest census, "
          "persona check --")
    per_run = _part1(rows)

    print("\n-- Part 2: seed-paired strict-minus-comparator contrast, old vs new --")
    _part2(rows, per_run)

    print("\n-- Part 2b: shortage-tier-years / Mead-min ordering, old vs new --")
    _part2b(rows, per_run)

    print("\n-- Part 3: retry-feedback-mode ablation, silent vs strict (placebo alongside), "
          "new vintage only --")
    _part3_retry_mode(rows, per_run)

    print("\n-- Part 4: FQL reference sensitivity (78d986ed regen), new vintage strict/"
          "disabled only --")
    _part4_reference_sensitivity(rows)

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


def _pending_or_fail_label(rows, **kw):
    """"FAIL (reason)" / "PENDING (reason)" / bare "PENDING" for the
    `row_type=skipped` row matching `kw` -- 2026-09-27 REVIEW FIX (P1-a):
    a genuine failure (status="fail", a nonzero ExitCode) must render
    visibly differently from an ordinary still-running PENDING, not be
    folded into the same label. No matching skipped row at all (e.g. an
    older row written before "reason" was tracked for this table) falls
    back to a bare "PENDING", never a fabricated reason."""
    recs = _find(rows, "skipped", **kw)
    if not recs:
        return "PENDING"
    r = recs[0]
    status = r.get("status") or "skipped"
    reason = r.get("reason")
    tag = "FAIL" if status == "fail" else "PENDING"
    return f"{tag} ({reason})" if reason else tag


def render_md(rows: list) -> str:
    lines = []
    lines.append("# R42 -- irrigation persona pilot: new corpus (431adb5e) vs old corpus "
                 "(faf1bb12); mid (fcd74a5f) + prev (5a8a8dab) kept as earlier references")
    lines.append("")
    lines.append("Source: `r42_irrigation_persona_pilot.py`. Every number below is read live "
                 "from the `rows` list this script writes to the paired CSV. \"old\" = commit "
                 "faf1bb12 (5 seeds landed, 42-46, pre-redesign physics). \"mid\" = commit "
                 "fcd74a5f (the persona-diversified corpus, pre-redesign physics; only seed 42 "
                 "landed). \"prev\" = commit 5a8a8dab (PR #54's supply-side redesign; this "
                 "script's OWN former \"new\" before the 2026-09-27 retarget; only seed 42 "
                 "landed). \"mid\"/\"prev\" are both current-rules-or-earlier references kept "
                 "readable in Part 1 only. \"new\" = commit 431adb5e (PR #54's redesign plus "
                 "PRs #55-#59; the corpus this pilot exists to check now; landed cells only "
                 "where they exist on disk and pass the completeness gate -- see Method; also "
                 "the only vintage carrying \"placebo\"/\"silent\" retry-feedback-mode arms). "
                 "Part 2/2b's contrast is old-vs-new only (faf1bb12 vs 431adb5e); Part 3 (new, "
                 "2026-09-27) is silent-vs-strict within \"new\" only, placebo alongside.")
    lines.append("")

    # ---- Part 1: per-run metrics -----------------------------------------------
    lines.append("## Part 1 -- per (vintage, arm, seed) metrics")
    lines.append("")
    lines.append("| vintage | arm | seed | n_rows | IBR cond. % | IBR uncond. % | EHE exec | "
                 "EHE prop | rejected n | rejection % | retried n | retry % | final-yr Mead ft | "
                 "min Mead ft | shortage-tier yrs | Mead KGE vs FQL (primary) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for vintage in VINTAGES_ORDERED:
        for role in ("strict", "comparator") + EXTRA_ROLES_BY_VINTAGE.get(vintage, ()):
            arm_name = _arm_name_for(vintage, role)
            for seed in SEEDS:
                recs = _find(rows, "run_metrics", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    label = _pending_or_fail_label(rows, vintage=vintage, arm=arm_name, seed=seed)
                    lines.append(f"| {vintage} | {arm_name} | {seed} | {label} | -- | "
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
                 "Yang's traditional ABM with NO WAGF rules, generated only for the prev "
                 "(5a8a8dab, `fql_nogov_96394b44`) and new (431adb5e LLM, `fql_nogov_78d986ed` "
                 "-- FQL commit 78d986ed as of the 2026-09-27 FQL REGEN, not 431adb5e; see "
                 "Method) physics trees; old/mid never had one generated, so that column reads "
                 "`n/a` there by construction, not because a run is incomplete. \"primary\" "
                 "(also shown in the main Part 1 table) is whichever kind `FQL_PRIMARY_KIND` "
                 "names per vintage.")
    lines.append("")
    lines.append("| vintage | arm | seed | KGE FQL+WAGF rules | KGE FQL (no governance) | "
                 "primary kind |")
    lines.append("|---|---|---|---|---|---|")
    for vintage in VINTAGES_ORDERED:
        for role in ("strict", "comparator") + EXTRA_ROLES_BY_VINTAGE.get(vintage, ()):
            arm_name = _arm_name_for(vintage, role)
            for seed in SEEDS:
                recs = _find(rows, "run_metrics", vintage=vintage, arm=arm_name, seed=seed)
                if not recs:
                    label = _pending_or_fail_label(rows, vintage=vintage, arm=arm_name, seed=seed)
                    lines.append(f"| {vintage} | {arm_name} | {seed} | {label} | -- | -- |")
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
    for vintage in VINTAGES_ORDERED:
        for role in ("strict", "comparator") + EXTRA_ROLES_BY_VINTAGE.get(vintage, ()):
            arm_name = _arm_name_for(vintage, role)
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
    for vintage in VINTAGES_ORDERED:
        for role in ("strict", "comparator") + EXTRA_ROLES_BY_VINTAGE.get(vintage, ()):
            arm_name = _arm_name_for(vintage, role)
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
    for vintage in VINTAGES_ORDERED:
        for role in ("strict", "comparator") + EXTRA_ROLES_BY_VINTAGE.get(vintage, ()):
            arm_name = _arm_name_for(vintage, role)
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
    for vintage in VINTAGES_ORDERED:
        for role in ("strict", "comparator") + EXTRA_ROLES_BY_VINTAGE.get(vintage, ()):
            arm_name = _arm_name_for(vintage, role)
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

    lines.append("### Persona check (mid + prev + new vintages) -- year-1 PVIDDiversionAG "
                 "prompt")
    lines.append("")
    lines.append("| vintage | arm | seed | status | starts with expected persona lead-in | "
                 "first 120 chars |")
    lines.append("|---|---|---|---|---|---|")
    for vintage in PERSONA_VINTAGES:
        for role in ("strict", "comparator") + EXTRA_ROLES_BY_VINTAGE.get(vintage, ()):
            arm_name = _arm_name_for(vintage, role)
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

    # ---- Part 3 (NEW, 2026-09-27): retry-feedback-mode ablation ------------------
    lines.append(f"## Part 3 -- retry-feedback-mode ablation: silent vs strict (full "
                 f"governance), placebo alongside ({RETRY_MODE_VINTAGE}=431adb5e only)")
    lines.append("")
    lines.append("Within the \"new\" (431adb5e) vintage only -- the sole vintage carrying "
                 "\"placebo\"/\"silent\" arms (`--retry-feedback-mode placebo|silent`). "
                 "diff_silent/diff_placebo = that arm's value minus strict's (same "
                 "governance-minus-comparator sign direction Part 2 uses, with \"strict\" "
                 "here meaning FULL governance, the same strict arm Part 1/2/2b already "
                 "read). A cell renders PENDING when strict, silent OR placebo has not landed "
                 "for that seed; a metric that is itself an \"n/a (...)\" string for a given "
                 "run renders its diff as \"n/a (non-numeric cell)\", never a fabricated "
                 "number.")
    lines.append("")
    lines.append("| metric | seed | strict (full) | silent | diff (silent-strict) | placebo | "
                 "diff (placebo-strict) |")
    lines.append("|---|---|---|---|---|---|---|")
    for metric_label in RETRY_MODE_METRIC_KEYS:
        for seed in SEEDS:
            recs = _find(rows, "retry_mode_pair", metric=metric_label, seed=seed)
            if not recs:
                pend = _find(rows, "skipped", section="retry_mode_pair", seed=seed)
                reason = pend[0]["reason"] if pend else "no data"
                lines.append(f"| {metric_label} | {seed} | -- | -- | PENDING ({reason}) | -- | "
                             f"-- |")
                continue
            r = recs[0]
            lines.append(
                f"| {metric_label} | {seed} | {_valfmt(r['strict_value'])} | "
                f"{_valfmt(r['silent_value'])} | {_valfmt(r['diff_silent'])} | "
                f"{_valfmt(r['placebo_value'])} | {_valfmt(r['diff_placebo'])} |"
            )
    lines.append("")

    # ---- Part 4 (NEW, 2026-09-27 FQL REGEN): reference sensitivity ----------------
    lines.append(f"## Part 4 -- FQL reference sensitivity (regen at commit 78d986ed), "
                 f"{FQL_REGEN_VINTAGE}=431adb5e LLM only")
    lines.append("")
    lines.append("Same strict/disabled LLM runs as Part 1 (431adb5e, unaffected by this "
                 "regen), scored against FOUR FQL reference trees instead of one -- the "
                 "PRIMARY (`fql_nogov_78d986ed`, warm-started from Hung & Yang's own "
                 "`Initial_Files/All-1109`), two SI calibration-snapshot sensitivity trees "
                 "(`...snapshot-All-WRR`, `...snapshot-All`), and the LEGACY, pre-warm-start "
                 "zero-init reference (`fql_nogov_431adb5e`, this vintage's primary before "
                 "this regen). Each reference tree is gated independently, so one tree still "
                 "landing never blocks another. Per-agent-median diversion KGE is computed "
                 "for the PRIMARY reference only (task-brief scope); the other three rows "
                 "read `n/a` for that column by construction, not because anything failed.")
    lines.append("")
    lines.append("| arm | seed | reference | Mead KGE | Mead RMSE (ft) | diversion KGE "
                 "(basin total) | diversion RMSE (basin total, ac-ft) | diversion KGE "
                 "(per-agent median) | n agents | n skipped (constant/zero-mean) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for role in FQL_REGEN_ROLES:
        arm_name = _arm_name_for(FQL_REGEN_VINTAGE, role)
        for seed in SEEDS:
            for kind in PART4_REFERENCE_ORDER:
                label = PART4_REFERENCE_LABEL[kind]
                recs = _find(rows, "reference_sensitivity", arm=arm_name, seed=seed,
                             reference_kind=kind)
                if not recs:
                    kind_pend = _find(rows, "skipped", section="reference_sensitivity",
                                       arm=arm_name, seed=seed, reference_kind=kind)
                    if kind_pend:
                        status = kind_pend[0].get("status") or "skipped"
                        reason = kind_pend[0]["reason"]
                    else:
                        llm_pend = [r for r in _find(rows, "skipped",
                                                      section="reference_sensitivity",
                                                      arm=arm_name, seed=seed)
                                    if "reference_kind" not in r]
                        status = (llm_pend[0].get("status") or "skipped") if llm_pend else "skipped"
                        reason = llm_pend[0]["reason"] if llm_pend else "no data"
                    tag = "FAIL" if status == "fail" else "PENDING"
                    lines.append(f"| {arm_name} | {seed} | {label} | {tag} ({reason}) | "
                                 f"-- | -- | -- | -- | -- | -- |")
                    continue
                r = recs[0]
                lines.append(
                    f"| {arm_name} | {seed} | {label} | "
                    f"{_valfmt(r['mead_kge_vs_reference'], nd=4)} | "
                    f"{_valfmt(r['mead_rmse_vs_reference'], nd=2)} | "
                    f"{_valfmt(r['diversion_kge_vs_reference'], nd=4)} | "
                    f"{_valfmt(r['diversion_rmse_vs_reference'], nd=1)} | "
                    f"{_valfmt(r['diversion_kge_per_agent_median'], nd=4)} | "
                    f"{r['diversion_kge_per_agent_n']} | "
                    f"{r['diversion_kge_per_agent_n_skipped_constant']} |"
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
        "\"prev\"/\"new\" (5a8a8dab on), end-of-year for \"old\"/\"mid\" (`examples/"
        "irrigation_abm/docs/irrigation_physics.md`'s physics-comparison table) -- so "
        "`final_year_mead_ft` / `min_mead_ft` / `years_mead_le_900ft` are each internally "
        "consistent within a vintage but not directly comparable across the old/mid vs "
        "prev/new boundary without accounting for the roughly one-year offset. Mead-elevation "
        "KGE vs the FQL reference: "
        "`r28_trajectory_vs_traditional.py::_yearly_series()` + `_kge_and_rmse()` (Gupta et "
        "al. 2009 original formulation). 2026-09-27 REVIEW FIX (P1-b) -- WHAT THIS KGE IS: an "
        "AGREEMENT INDEX BETWEEN TWO MODELS (the governed or ungoverned LLM-ABM and the "
        "calibrated RL-ABM/FQL, run under IDENTICAL hydrology), never a validation against "
        "observed data -- FQL is itself only a model, and Hung and Yang (2021) report their "
        "own RL-ABM's fit to OBSERVED diversions ranging KGE 0.27 to 0.90 across their "
        "calibrated agents/reaches, so an LLM-vs-FQL KGE in this table sits inside the spread "
        "the RL-ABM's own fit to reality already carries. REVISED 2026-09-26 (Wenyu's "
        "decision): the earlier "
        "published irrigation KGE comparison in this package, and every FQL dir this script "
        "read before this revision, used `run_fql_baseline.py` WITH its 12 governance "
        "validators on by default (\"FQL + WAGF rules\" -- confirmed via each dir's own "
        "LAUNCH_COMMAND.txt lacking `--no-governance`; \"raw\" in those dir names describes "
        "the Q-learning policy, not an absence of governance) -- a governed FQL ablation, not "
        "Hung & Yang's traditional ABM unmodified. The PRIMARY reference is the unruled FQL "
        "(`--no-governance`, i.e. NO WAGF rules): `fql_nogov_96394b44` for \"prev\" (5a8a8dab) "
        "and, for \"new\", `fql_nogov_78d986ed` (REPOINTED 2026-09-27, FQL REGEN -- see "
        "below; was `fql_nogov_431adb5e` before this same-day follow-up). Old/mid physics "
        "(faf1bb12) never had an unruled FQL run, so their primary reference stays \"FQL + "
        "WAGF rules\" (`fql_raw_norebalance_faf1bb12`) by necessity, and their unruled-FQL "
        "column reads `n/a`. \"Prev\"/\"new\" rows additionally report their own governed-FQL "
        "ablation (`fql_raw_norebalance_96394b44` / `fql_raw_norebalance_78d986ed` "
        "respectively) as a SECOND, explicitly labelled KGE column -- an SI ablation, never a "
        "second baseline -- so the governed-vs-unruled gap stays visible rather than silently "
        "dropped when the primary reference changed. FQL REGEN 2026-09-27 (commit 78d986ed): "
        "the \"new\" vintage is now a TWO-HASH thing -- LLM stays 431adb5e (agent/governance "
        "code + prompts, completely unaffected: the same LLM run dirs, the same "
        "`EXPECTED_COMMIT_PREFIX[\"new\"]==\"431adb5e\"` manifest check, still apply), while "
        "FQL moves to 78d986ed (same LLM code; only the FQL runner changed -- a shared "
        "log-row builder plus a calibrated warm start seeded from Hung & Yang's own "
        "`Initial_Files/All-1109`, replacing the earlier ZERO-INIT FQL trees). Because the "
        "FQL side changed but the LLM side did not, the two are tracked as independent "
        "commits rather than folded into one vintage hash. Part 4 (new, 2026-09-27) is the "
        "SI reference-sensitivity check this regen motivated: strict/disabled (431adb5e LLM) "
        "scored against the new primary (`fql_nogov_78d986ed`), two calibration-snapshot "
        "sensitivity trees (`fql_nogov_78d986ed_snapshot-All-WRR`, "
        "`fql_nogov_78d986ed_snapshot-All`), and the superseded LEGACY zero-init reference "
        "(`fql_nogov_431adb5e`, kept on disk, read ONLY here) -- Mead-elevation KGE and "
        "basin-total-diversion KGE against all four, plus a per-agent-median diversion KGE "
        "against the primary only. The snapshot choice is PROVENANCE-based, not asserted: "
        "both snapshot dirs' own LAUNCH_COMMAND.txt / manifest provenance fields name the "
        "same calibration day as `cal_1108`, which is why these two were picked to probe -- "
        "PENDING the authors' own explicit confirmation that `cal_1108` is the calibration "
        "run Hung & Yang intended here. Every FQL dir is gated by "
        "`_fql_completeness(vintage, seed, kind)`, which delegates to `_fql_dir_completeness()` "
        "-- 2026-09-27 REVIEW FIX (P1-a): NOT a bare `Finished:` check any more, since the "
        "78d986ed FQL runner's LAUNCH_COMMAND.txt carries no `Finished:` line at all. A "
        "present `ExitCode:` line (either runner) must be 0 or the dir is FAIL, never silently "
        "read; `Finished:` present is the legacy-ok case; no `Finished:` but a cleared "
        "`ExitCode: 0` (the 78d986ed runner's own format) additionally requires "
        "`reproducibility_manifest.json` to exist. A FAIL renders as an explicit FAIL with its "
        "reason in Part 1's and Part 4's tables, never folded into an ordinary PENDING -- "
        "every KGE is computed WITHIN one vintage, against that vintage's own "
        "reference (of whichever kind), so the Mead-level timing difference above never "
        "enters a single KGE number. `_four_cells`/Part 2's contrast reads "
        "`mead_kge_vs_fql_primary` (whichever kind is primary per vintage) and names the kind "
        "used on each side via `old_reference`/`new_reference` -- old (wagfrules) and new "
        "(nogov) use DIFFERENT primary kinds, so that contrast is a same-vintage "
        "strict-vs-comparator read, not an apples-to-apples cross-vintage reference "
        "comparison. This script does NOT compute a constant-demand KGE null; "
        "`r29_kge_null_and_demand.py`'s own Part (a) supplies that once its replay is "
        "re-pointed at 431adb5e. Top-3 rule-id census: "
        "`r35_placebo_retry_irrigation.py::_rule_id_census()`, imported, rule ids `sorted()` "
        "before counting (the Python set-hash-randomization fix r27/r34/r35 all apply). "
        "Manifest census: `git_commit_short` is value-enforced to start with the vintage's "
        "expected commit prefix (raises otherwise -- all four vintages are pinned commits "
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
        "magnitude directly. Part 3 (retry-feedback-mode ablation, 2026-09-27): every metric "
        "is read off the SAME `run_metrics` row Part 1 already built for the \"new\" "
        "vintage's strict/silent/placebo arms -- no new metric definition, only a new diff "
        "(silent-strict, placebo-strict) at matched seeds within one vintage. `diff_silent`/"
        "`diff_placebo` render \"n/a (non-numeric cell)\" rather than raising or coercing to 0 "
        "when either side of the subtraction is itself an \"n/a (...)\" string (e.g. the "
        "appraisal-drift or Mead-KGE-nogov columns before their underlying data exists). "
        "Part 4 (FQL reference sensitivity, 2026-09-27 FQL REGEN): basin-level Mead/diversion "
        "KGE use the SAME `R28._yearly_series()` + `R28._kge_and_rmse()` call Part 1 uses "
        "(`_series_kge_vs_dir`, a (vintage,kind)-independent generalisation of "
        "`_mead_kge_vs_fql` that takes any results-dir root, since three of Part 4's four "
        "reference trees are not indexed in `FQL_DIR_BY_VINTAGE`); diversion is aggregated "
        "with agg=\"sum\" (the same aggregation `_basin_totals_maf` uses for its own diversion "
        "read), Mead with agg=\"first\" (unchanged from Part 1). Per-agent-median diversion "
        "KGE (`_diversion_kge_per_agent_median`, primary reference only): agent_id sets are "
        "expected identical between the two runs (same persona roster, same environment) and "
        "a mismatch RAISES; each agent's own diversion series is then aligned by its YEAR SET "
        "(a {year: value} dict per agent, intersected on keys, not paired by list position) "
        "before scoring -- 2026-09-27 REVIEW FIX (Should-fix): pairing by length alone could "
        "silently mismatch two equal-length series over different year sets. An agent whose "
        "series is CONSTANT or ZERO-MEAN on either side (sd==0 or mean(ref)==0 -- the exact "
        "conditions `R28._kge_and_rmse` itself raises on) is SKIPPED explicitly rather than "
        "aborting the seed; `statistics.median()` (stdlib) is then taken over the remaining "
        "agents' KGEs, and the skipped count is reported as its own field, "
        "`diversion_kge_per_agent_n_skipped_constant`, never silently absorbed into "
        "`diversion_kge_per_agent_n`. Every reference tree is gated by "
        "`_fql_dir_completeness()` (the two-completion-marker-format gate `_fql_completeness()` "
        "also delegates to, see above) independently per (arm, seed, reference_kind) -- a "
        "not-yet-landed calibration-snapshot or legacy dir never blocks the primary or any "
        "other tree, and a genuine FAIL (nonzero ExitCode) renders as an explicit FAIL, never "
        "folded into PENDING. This is an SI robustness check on the FQL regen itself, never a "
        "replacement for Part 1's own primary-reference read."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
