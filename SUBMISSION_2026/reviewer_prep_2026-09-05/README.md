# reviewer_prep_2026-09-05

> **DATA STATUS — 2026-09-15.** The irrigation, single-agent flood, and
> vaccination corpora behind this package were lost 2026-09-15 (VSS restore
> zero-filled files at the right name/size/mtime; 0/183 manifest-bearing run
> dirs came back clean — see `out/r18_restore_verification_2026-09-15.md`).
> Every number below is the **pre-loss value** computed 2026-09-05...09-10,
> **not currently re-verifiable against disk**. Corpora are being
> regenerated at commit `e75e390c` (`.research/experiment_plan_framework_paper_2026-09-06.md`
> §0b); until then this is the **original-corpus record**, not a live reproduction.

Pre-computed answers to the questions a water-journal reviewer will ask about the
framework paper. **Analysis only.** Nothing here runs a simulation, calls a model, or
writes anywhere outside this directory. Every table was built 2026-09-05...09-10 from
corpora that were on disk at that time; those corpora are lost as of 2026-09-15 (see
banner above).

    scripts/   one runnable script per table, plus _common.py
    out/       one CSV per table, plus SUMMARY.md with the headline numbers

**Verified independently 2026-09-06 (opus review).** Six claims confirmed against the
corpora to four decimal places: the r0 sanity gate (36.05 / 59.07); the executed remap
(0.86 / 26.77); the flood IBR grid and which published pair lands on which cell
(0.87/7.41, 1.60/14.22, 2.51/22.56, and 8.53 only from the pre-quarantine arm); the
`not at_allocation_cap` precondition firing on 35.4 % of no-validator irrigation rows;
the six dead audit columns including `fallback_activated` contradicting `status`; and
the six-versus-seven benchmark-table disagreement count. The review returned four
provenance defects, all fixed on 2026-09-06: r7 now regenerates the pre-quarantine
flood arm itself, r7 now reports both test families, the rule-based EHE row now cites
`metrics_definitions.md:195` instead of an undocumented ledger claim, and r8's
elevation rows now carry the population-mismatch note.

## How to regenerate everything

From the repository root, in this order (r0 first - the rest are independent):

    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r0_sanity_gate.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r1_irrigation_trajectories.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r2_flood_trajectories.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r3_rule_firing_census.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r4_flood_headline_variants.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r5_irrigation_executed_vs_proposal.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r6_parser_layer_share.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r7_seed_robustness.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r8_flood_vs_benchmarks.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r9_appraisal_drift.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r10_rule_type_attribution.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r11_flood_seed_matched.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12_vaccination_t04.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12b_vaccination_t04b.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12b_vaccination_t04b.py --old-arm
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r14_advise_arm.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r16_vintage_prompt_check.py
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r17_strict_arm_vintage_check.py  # strict irrigation arm vintage and seed-46 outlier check
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r21_compute_cost.py  # compute cost and runtime metrics across experimental arms
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r23_flood_strict_regen.py  # flood governed arm: regen at faf1bb12 vs old published
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r24_flood_contrast_regen.py  # flood no-validator arm regen vs old, plus contrast
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r25_table1_regen.py  # paper Table 1, old vs new, across all arms
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r26_flood_crossmodel_gemma4_12b.py  # flood gemma4:12b cross-model arms vs gemma3:4b comparison
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r27_irrigation_crossmodel_gemma4_12b.py  # irrigation gemma4:12b cross-model arms vs gemma3:4b comparison
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r28_trajectory_vs_traditional.py  # do LLM arms reproduce the traditional model's trajectory
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r29_kge_null_and_demand.py  # constant-demand KGE null plus basin-demand descriptive stats
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r30_grounded_coherence.py  # irrigation increase rate conditioned on environment, not self-report
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r31_flood_relocation_sensitivity.py  # flood IBR and JS distance excluding relocated agent-years
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r33_first_vs_last_proposal.py  # first vs last irrigation proposal, using initial_proposal_columns
    python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r34_placebo_retry_flood.py  # placebo-retry flood: rule content value vs extra attempt

None of r17-r34 takes a command-line argument (checked: no `argparse` /
`add_argument` in any of them); all are run from the repository root like
r0-r16 above. r18, r19, r22 and r32 are memos under `out/` with no
corresponding runnable file; the numbers r15 and r20 were never assigned.

r13 is not in this list: its data lives only in the sibling `wagf-main-runs`
checkout (see its own entry in "Corpora read" below).

## Pending, runs still in the GPU queue (2026-09-22)

Queue state per `out/paper_readiness_audit_2026-09-22.md`: step [1] running,
steps [2] through [5] pending. These four scripts exist and are run-ready,
but the runs their tables depend on have not landed; their `out/*.md` and
`out/*.csv` write-ups are pre-landing placeholders and live in
`out/_pending/` until the runs land.

- **[1]** `r35_placebo_retry_irrigation.py` - irrigation placebo retry-feedback arm,
  seeds 42-43 (seed 42 running as of this pass, seed 43 not yet started).
- **[2]** `r36_no_ceiling_ablation.py` - no-demand-ceiling ablation.
- **[3a]/[3b]** flood initprop seeds 42-46 and irrigation initprop seeds 43-44 -
  extends `r33_first_vs_last_proposal.py` (currently single-seed, commit
  c3391a53) to five seeds; no separate r-numbered script exists for this step.
- **[4]** `r37_flood_n10_update.py` - flood seeds 47-51 (n=10 update).
- **[5]** `r38_paraphrase_robustness.py` - paraphrase-prompt robustness check.

Standard library only. No pandas, no scipy, no pytest. Each script raises on a
missing file, a missing column or an empty denominator; none of them fills a gap with
0 or NaN, and a NaN that is genuinely computed (an empty stratum) is written to the
CSV as the literal string `NA` so it can never be read as a zero. A cell that does
not apply to its row at all - a paired p-value on an unpaired test row, a
permutation floor on a two-sample t - carries the distinct sentinel `N/A_by_design`,
so "undefined for this row" is never confused with "computed and came out empty".

## Where the definitions come from

Nothing in this package invents a metric.

- **Irrigation** imports `SUBMISSION_2026/decomposition/_loader.py` directly:
  `run_dirs`, `paired_seeds`, `load_run`, `load_audit`, `action`, `wsa`, `is_high`,
  `is_increase`, `ibr` (conditional high-WSA increase rate), `increase_rate`
  (unconditional), `mean`, `sd`, `paired_t`, `t_two_sided_p`.
- **The executed remap** is transcribed from `reproduce_published.py:51-53`: a row
  whose `status` starts with `REJECTED` executes the registry default
  `maintain_demand` (`_loader.py:59-60`); every other row executes `final_skill`.
- **Flood** is transcribed from the canonical published implementation
  `examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py`: IBR = (R1 + R3 +
  R4) / total, R5 tracked and excluded per Extended Data Table 2; the action
  normalisation map with `relocated` to `relocate`; EHE = H/log2(4). Corpus discovery
  and the seed-from-manifest rule follow
  `SUBMISSION_2026/decomposition/e6_flood_placebo.py`.
- **EHE is pooled once.** Every headline EHE in this package pools a whole run's
  decisions and takes entropy once. The per-year entropy in r1 and r2 is labelled
  `ehe_yearly` and is explicitly not the headline; averaging per-year entropies gives
  a materially smaller number.

## Proposal and executed, everywhere

Every table that can carry both carries both, labelled `proposal` (what the agent
asked for: `proposed_skill`) and `executed` (what ran, after the REJECTED-to-default
remap). Where a third column helps, `final` (`final_skill`, post-validator,
pre-fallback) sits between them. In irrigation the published headline is the
`proposal` figure; in flood the three columns are identical row for row.

## The n = 5 caveat

An exact two-sided sign-flip permutation test on five paired differences has 2^5 = 32
arrangements, so the smallest p it can return is 2/32 = **0.0625**. No paired n = 5
contrast can be permutation-significant at 0.05, however large the effect. Every
p < 0.05 in this package is a Student's t p on the per-seed differences (df = 4),
which buys its resolution with a normality assumption five points cannot test. Both
p-values are printed side by side in `out/r7_seed_robustness.csv`, together with the
per-seed differences, their min and max, and a count of sign flips - which is the
evidence that does not depend on a distributional assumption. For the seed-matched
flood pairing (n = 3) the permutation floor is 2/8 = 0.25.

---

## The tables

### r0 - sanity gate
**Answers:** is this package computing the same thing the paper computed?
**Definition:** `_loader.ibr` on `simulation_log.yearly_decision`, five seed-matched
gemma3:4b v21 runs, per-seed then unweighted mean.
**Result:** 36.05 / 59.07, matching the published values to +0.002 pp and +0.000 pp.
**Caveat:** the gate is the precondition for trusting anything else here. It raises if
it fails; it never tunes a definition to make the target appear.

### r1 - irrigation per-year trajectories and Lake Mead bands
**Answers:** the 42-year series behind a single averaged headline, per seed, per arm.
**Definition:** per year, `ibr_pct`, `increase_rate_pct`, `ehe_yearly` (H/log2(5)
within the year) and the share of each of the five skills, at four action levels
(`sim`, `proposal`, `final`, `executed`). Reservoir elevation is the across-agent mean
of `lake_mead_level` per year; the band is the mean and sample sd across seeds.
**Caveats:** `ehe_yearly` is not the headline EHE. The FQL arms write a different
three-action vocabulary (`increase_demand` / `maintain_demand` / `decrease_demand`)
and their `wsa_label` is a fuzzy-state label rather than an agent self-report, so
their rows are labelled level `sim_fql3`, scored with k = 3, and must not be read
against the LLM entropies. `fql_nogov` is explicitly not paper data. A skill outside a
run's vocabulary is written `NA`, never 0.

### r2 - flood per-year trajectories
**Answers:** the flood twin of r1, ten years, five runs per arm.
**Definition:** per year, IBR = (R1 + R3 + R4) / all audit rows of the year, R5
excluded; `ehe_yearly` = H/log2(4); four action shares. Levels `proposal`, `final`,
`executed`.
**Caveats:** the v1 flood cells are **not seed-matched**. Governed carries seeds
42, 4202, 4203, 45, 46; no-validator carries 42, 43, 44, 45, 46; only three seeds
exist in both. The published analysis pairs by run index, which pairs governed seed
4202 with no-validator 43. `simulation_log.csv` is 1000 rows in every run;
`household_governance_audit.csv` is shorter because an agent that has relocated makes
no further decision.

### r3 - rule-firing census
**Answers:** which validator rule fired, how often, and with what outcome.
**Columns used:** `failed_rules` (ERROR-level blocking ids, pipe-delimited),
`warning_rules` (WARNING-level, recorded but not blocking), `status`, `retry_count`,
`error_messages`. **Columns deliberately not used, and measured dead on every run:**
`rules_triggered` (empty on 100 % of rows), `rules_personal_hit` /
`rules_social_hit` / `rules_thinking_hit` / `rules_physical_hit` /
`rules_semantic_hit` (all "0"), and `fallback_activated` ("False" on 100 % of rows
even where `status` is `REJECTED_FALLBACK`, so it contradicts the status column).
**Caveat:** `failed_rules` records the literal id `Unknown` for a block raised by a
skill **precondition** rather than a named theory rule, so the modal error message is
carried alongside every id. That matters: the no-validator irrigation arm's `Unknown`
is `Precondition failed: 'not at_allocation_cap'`, a hard world affordance, firing on
35.4 % of its rows.

### r4 - flood headline variants
**Answers:** five different flood IBR pairs circulate; which definition does each
belong to?
**Definition:** a grid of 3 conditionings (unconditional, threat appraisal not medium,
threat appraisal high) x 3 action levels x 2 aggregations (per-run-then-mean, pooled),
for the governed arm, the live no-validator arm, and a reconstruction of the
no-validator arm as it stood before the 2026-05-30 quarantine.
**Caveat:** conditioning on high threat appraisal collapses the numerator to R1 alone,
because R3 and R4 require a low appraisal and cannot occur in that denominator. The
pre-quarantine arm is built from `_QUARANTINE_reflection_missing_2026-05-30/gemma3_4b`
Run_1 to Run_3 plus live Run_4 and Run_5; it is reconstructed only to explain a
published number, not offered as current data.

### r5 - irrigation executed vs proposal
**Answers:** the single most load-bearing disclosure. The published headline is
computed on what the agent proposed, not on what the simulation ran.
**Definition:** IBR and unconditional increase rate on `proposed_skill`, `final_skill`
and the executed remap, per seed, plus row-level disagreement counts.
**Caveat:** the whole proposal-executed gap is the REJECTED-to-default remap. The
validators do not rewrite a skill name: `proposed_skill` equals `final_skill` on every
row except 108 across the ten runs where `proposed_skill` is blank (105 governed,
3 no-validator) - a parse gap, counted and never folded into another bucket.

### r6 - parser layer share
**Answers:** how much of the corpus was decided by a fallback parsing layer rather
than by a clean structured answer.
**Definition:** `parse_layer` classified as `clean_structured` (contains json, no
digit, no keyword), `digit_fallback`, `keyword_fallback` or `blank`;
`fallback_share_pct` is the last three combined. `parse_confidence` is carried.
`base_layer` does not exist in either corpus and is reported absent.
**Caveat:** the TAE `firstattempt_gov_seed42..46` runs are **unreleased, provenance
RED, disclosure only** and are never pooled with the released corpora. The 10.47 %
figure on record for TAE seed 42 is the `enclosure+json+digit` layer alone; every
non-clean layer together is 16.15 %.

### r7 - seed robustness
**Answers:** every headline metric, every seed, both arms, the paired difference, the
range, sign flips, and two p-values.
**Definition:** irrigation metrics are seed-matched (n = 5, df = 4). Flood is reported
twice: the published run-index pairing (n = 5) and the seed-matched pairing (n = 3).
`p_paired_t` is Student's t on the per-seed differences; `p_exact_permutation` is the
exact two-sided sign-flip test with its floor printed alongside.
**Two no-validator arms** (`noval_arm` column): `live` is the current corpus and the
default; `prequarantine` is that arm as it stood before 2026-05-30 (quarantined
Run_1-3 plus live Run_4-5), reconstructed only because flood IBR 8.5273 +/- 1.0812 and
flood EHE 0.8145 +/- 0.0527 reproduce from it and from nothing else.
**Two test families** (`test_family` column): the paired one-sample t on differences,
which is what a per-seed design licenses, and an unpaired two-sample t (Student
df = n1 + n2 - 2, plus Welch in its own columns), which is the only way the published
flood EHE p = 0.166 reproduces. `p_paired_t` is left empty on an unpaired row; the
unpaired values live in `p_unpaired_student_t` and `p_unpaired_welch_t`.
**Caveat:** `ehe_flood_pooled_simlog_PUBLISHED` is the Extended Data Table 2
definition (`simulation_log.yearly_decision` over all 1000 agent-years, `relocated`
mapped to `relocate`), not the audit-csv one; the two differ because the audit drops
post-relocation rows.

### r8 - flood action shares against both benchmark tables
**Answers:** how the three arms distribute their actions, and which of the two shipped
benchmark tables disagree with each other.
**Definition:** action shares from `simulation_log.yearly_decision`. Benchmark ranges
are parsed from the source of both tables (`python -m broker.calibration.benchmark_diff`
does not exist on this branch) and diffed here.
**Caveats:** the rule-based PMT arm writes six cumulative state labels, not four yearly
actions, so its four-way share depends on how "Both Flood Insurance and House
Elevation" is folded in. Three folds are reported side by side and none is chosen
silently - note that the published `normalize_action` would send that label to
`do_nothing`, because it is absent from the mapping and the function's tail defaults
there. Only `insurance_rate_all`, `elevation_rate` and `buyout_rate` are computable
from the single-agent corpus; every other benchmark is written NOT AVAILABLE with the
missing column named. Every elevation row carries a population-mismatch note: the
corpus denominator is all agents, because there is no tenure column, while benchmark A
is homeowners over roughly ten years and benchmark B is `tenure == Owner`. Same
cumulative construct, different population - so an out-of-range elevation figure is a
denominator mismatch first and a model verdict only after that is accounted for.
**The six-versus-seven count is settled:** six metrics share a name across the two
tables (after mapping table A's `insurance_rate` to table B's `insurance_rate_sfha`)
and carry different ranges - `buyout_rate`, `elevation_rate`, `insurance_lapse_rate`,
`insurance_rate_all`, `insurance_rate_sfha`, `mg_adaptation_gap`. Adding table A's
`rl_uninsured_rate` (repetitive-loss properties), which exists in table B only as
`renter_uninsured_rate` (renters) - same range, different population - makes seven.
Both figures are defensible; they count different things.

### r9 - appraisal change across retries
**Answers:** does the retry loop let an agent restate the appraisal the headline
conditions on?
**Verdict: NOT AVAILABLE on the released corpora**, and the script proves the absence
rather than asserting it. It checks the audit columns (no `initial_labels` /
`attempt_labels` / `first_attempt_wsa` on any released run), the raw JSONL under each
`raw/` (one object per decision, not per attempt - `skill_proposal.reasoning.WSA_LABEL`
is the accepted attempt's label and no earlier one) and the reflection log.
**What it reports instead:** the size of the hole. 63.8 % of governed irrigation
decisions were retried, 35.4 % of no-validator ones, 8.4 % of governed flood ones -
and none of that can be checked for appraisal drift from the shipped files. The only
measurement that exists (45.3 % of retried decisions changed their appraisal) is
`SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py` on TAE seed 42, which is
unreleased and provenance RED.

### r10 - rule-type attribution: WORLD vs LABEL, and two accounting bounds
**Answers:** of the increase proposals that got blocked, how many were blocked by a
rule that reads only environment state (WORLD), how many by a rule that reads the
model's own WSA/ACA label (LABEL), and what would the headline IBR read if one family
were switched off?
**Columns used:** `proposed_skill` (first-proposal proxy - see caveat), `failed_rules`
(ERROR-level blocking ids, the same column r3 uses), `status`, `construct_WSA_LABEL`.
**Definition:** restricted to rows whose `proposed_skill` is `increase_large` /
`increase_small` and whose `failed_rules` is non-empty (blocked at least once during
that decision's retry loop). WORLD = `demand_ceiling_stabilizer`,
`demand_floor_stabilizer`, `water_right_cap`, `minimum_utilisation_floor`,
`curtailment_awareness`, `supply_gap_block_increase`, plus `non_negative_diversion` /
`compact_allocation` / `drought_severity` / `magnitude_cap` /
`consecutive_increase_cap` / `zero_escape_floor` (defined in
`examples/irrigation_abm/validators/irrigation_validators.py`, never observed firing
at ERROR level in these ten runs) and the literal id `Unknown` (the no-validator arm's
`at_allocation_cap` skill precondition - same physical constraint as `water_right_cap`,
raised at a different layer). LABEL = `low_threat_no_increase`,
`high_threat_high_cope_no_increase`, `high_threat_no_maintain` (all three carry an
explicit `construct:` key in `examples/irrigation_abm/config/agent_types.yaml`'s
`strict.thinking_rules`; the third is WARNING-only and never observed at ERROR level).
A row's `failed_rules` classifies as WORLD_ONLY / LABEL_ONLY / BOTH / OTHER by set
membership across all ids on that row; none of the six ids actually observed at ERROR
level in these ten runs fell to OTHER. Two accounting bounds recompute `_loader.ibr`
and `_loader.increase_rate` with `proposed_skill` substituted for the executed action
on LABEL_ONLY rows (bound a) or WORLD_ONLY rows (bound b); a BOTH row keeps its
executed action in either bound, because undoing one rule family leaves the other
still blocking it. Neither bound re-simulates a retry.
**No first-proposal column exists in the released corpora.** `initial_skill` (P0-1a,
`broker/tests/test_initial_proposal_columns_p0_1a.py`) would record the true first
attempt across a governance retry; it is gated off by default and confirmed absent
from all ten released audit CSVs (checked directly against the header of every run).
`proposed_skill` is the fallback the brief specifies, and it is the LAST (post-retry)
attempt, not the first - `skill_proposal` is reassigned by
`_retry_loop._governance_retry_loop` on every retry. Spot-checked on seed 42, step 3,
agent "Fort Mohave Ind Res CA", Y1: `proposed_skill` reads `increase_small` after one
retry, while `error_messages` shows the blocked FIRST attempt was `increase_large`.
**Caveat:** `failed_rules` accumulates ids across EVERY attempt of a decision's retry
loop, and a retry can change which skill TYPE is proposed, not just its magnitude - so
a row whose FINAL `proposed_skill` is an increase can carry a decrease-only rule id
(`demand_floor_stabilizer` blocks `DECREASE_SKILLS` only in
`irrigation_validators.py`) left over from an earlier decrease attempt in the same
decision. Measured directly: 53-89 of each governed seed's ~1,250-1,600 increase-first
rows (4-6 %) carry `demand_floor_stabilizer` this way; re-classifying those rows with
that id excluded flips only 2-5 rows per seed from BOTH to LABEL_ONLY (every other
contaminated row already carries a second, non-alien WORLD id), a change the 5-seed
means in this table absorb without materially moving.
**Caveat:** the rule-share-of-rejections table (60.7 % of governed rejected rows carry
more than one rule id) broadly confirms, without exactly reproducing, the seed-42
expert-panel doc's decomposition
(`examples/irrigation_abm/analysis/rejection_rate_expert_panel_review.md`: demand
ceiling ~80 %, `high_threat_high_cope_no_increase` ~61 %) - that doc's numbers come
from a v20 run predating the base-asymmetry fix, not the released v21 corpus; this
table's own five-seed means are 86.5 % and 56.7 %.

**Output:** `out/r10_rule_type_attribution.csv` (`row_type` in `block_class` /
`rule_share`, per-seed rows plus MEAN/SD).

### r11 - flood seed-matched 7-pair table (2026-09-07 inference-matched top-up)
**Answers:** r2/r4/r7 all flag that flood governed and no-validator share only THREE
seeds (42, 45, 46), so the published flood pairing is by RUN INDEX, not by seed. Two
small top-up batches close that gap: `JOH_T0-1b_strict_gemma3_4b_e0eee08c_matched/Run_43,44`
(governed, seeds 43/44) and `JOH_T0-2b_disabled_gemma3_4b_e0eee08c_matched/Run_4202,4203`
(no-validator, seeds 4202/4203), both gemma3:4b, 100 agents x 10 years, code
`origin/main e0eee08c`, inference settings **matched** to the published no-validator
arm (`num_ctx=8192`, `num_predict=4096`, `thinking_mode=disabled`). Combined with the
five already-published runs per arm, BOTH arms now carry the same seven seeds
`{42, 43, 44, 45, 46, 4202, 4203}` - the first flood table paired by seed at n = 7
(df = 6) instead of n = 3 (df = 2). The script defaults to this matched batch;
`--variant unmatched` reproduces the original 2026-09-06 top-up (`num_ctx=4096`,
`num_predict=2048`, `thinking_mode=auto` - not matched to the published arm), kept
runnable as a sensitivity check rather than as the headline table.

**Integrity of the four new (matched) runs, checked before any metric, raises
otherwise:** `simulation_log.csv` is 1000 rows in all four (100 x 10, as required);
audit rows are 912 / 742 / 909 / 911 (seeds 43 / 44 / 4202 / 4203) - lower than 1000
because an agent that has relocated makes no further decision, same convention as
every other flood table here. `run_integrity.json` reports `integrity_ok: true` on
all four, manifest seed matches the run-directory seed on all four, and
`config_snapshot.yaml`'s `governance_profile` reads `strict` for both T0-1b runs and
`disabled` for both T0-2b runs, matching the arm. **New in this pass:** each
manifest's `num_ctx` / `num_predict` / `thinking_mode` is checked against the
published no-validator arm's own reference manifest (read live from
`JOH_ABLATION_DISABLED/.../Group_C_disabled` seed 42, not hardcoded) - all four new
runs report `8192 / 4096 / disabled`, an exact match; the script raises instead of
printing a caveat if any of the three ever drifts.

**Config snapshot diff (stdlib `difflib`, no third-party YAML parser):** against a
published Group_C run's snapshot, the governed diff is `+133 / -1` lines and the
no-validator diff is `+68 / -1` lines - larger than the old unmatched-run diff
(the different `thinking_mode` setting changes which optional profile blocks get
serialized). In BOTH diffs the only line removed is `seed: 42` (the run's own seed
value); `difflib.SequenceMatcher` reports zero `replace` regions overlapping the
governance-rule text, so every line of the published snapshot reappears
byte-for-byte in the new one - what changes is a pure ADDITION (three optional
response-schema fields, a `psychological_framework` field, a `multi_skill` block,
two unused named governance profiles `strict_no_etb` and `grounded_v1`, and their own
nested `thinking_rules` / `identity_rules` sub-blocks), never a rewrite of the
`strict` or `disabled` profile these runs actually run under. That is a stronger,
machine-checked version of the old manual eyeball claim, not merely a repeat of it.

**Provenance, the two arms of a mixed-commit seed pair:** for seeds 43/44 the
governed side is the new commit (`e0eee08c...`) and the no-validator side is the
published run on the OLDER commit (`5a1d467f...`) - the code commit still differs,
but for the first time `num_ctx` / `num_predict` / `thinking_mode` are IDENTICAL on
both sides (`8192` / `4096` / `disabled`), closing the inference-settings gap that
the unmatched top-up left open. For seeds 4202/4203 the no-validator side is the new
commit (same `8192`/`4096`/`disabled`) but the governed side is the published
Group_C run, whose manifest schema is old enough that it records neither
`git_commit` nor `num_ctx`/`num_predict`/`thinking_mode` at all -
`ABSENT_FROM_MANIFEST`, not inferred, unchanged from before. `model_family`,
`model_parameter_size`, `model_quantization` and `model_digest` (gemma3, 4.3B,
Q4_K_M, same digest) are identical everywhere they are recorded. `python_version`
(3.14.0) is identical on every manifest that records it.

**Proposal vs final vs executed:** counted directly (not asserted) across all 14
(arm, seed) run instances, 12,728 audit rows total: `proposed_skill` != `final_skill`
on 0 rows, `final_skill` != executed on 0 rows, `proposed_skill` != executed on 0
rows. Flood's three action levels coincide row for row in the matched runs too.

**Metrics, n = 7, mean (governed / no-validator), paired-t p / exact-permutation p
(floor 2/128 = 0.015625), sign flips out of 7:**

| metric | governed | no-validator | p (paired-t) | p (perm) | flips |
|---|---|---|---|---|---|
| IBR unconditional | 0.74 % | 8.03 % | 0.00003 | 0.0156 | 0 |
| IBR, threat != medium | 1.41 % | 15.18 % | 0.00001 | 0.0156 | 0 |
| IBR, threat high | 2.12 % | 22.25 % | <0.0001 | 0.0156 | 0 |
| EHE (simlog, PUBLISHED) | 0.861 | 0.801 | 0.084 | 0.0938 | 2 |
| rejection rate | 0.99 % | 0.00 % | 0.024 | 0.0156 | 0 |
| retry rate | 8.42 % | 0.00 % | 0.00039 | 0.0156 | 0 |

IBR is identical across proposal/final/executed (see above). The no-validator arm's
rejection and retry rates are exactly 0.00 % on all seven seeds - the validators are
in fact off, not merely permissive. EHE is the only metric with any sign flip (2 of
7) and the only one that stays non-significant (p = 0.084), consistent with every
other table in this package that touches flood EHE. The 7-seed contrasts run in the
same direction as r7's old 5-run run-index pairing on every metric r7 also computed
(e.g. IBR unconditional gap -7.29 pp here vs -6.54 pp in r7; IBR threat-high gap
-20.13 pp vs -20.05 pp in r7); rejection rate, retry rate and the three
proposal-level IBR cells are new to this table and carry `N/A_by_design` in the
`r7_n5_*` columns rather than a value r7 never computed. Matching the inference
settings moved every metric by well under 1 percentage point / 0.02 entropy units
from the old unmatched-run n = 7 table (e.g. IBR unconditional -7.40 -> -7.29 pp,
EHE +0.043 -> +0.060) - no sign, no significance threshold and no ranking changes.

**Sensitivity: matched vs unmatched, same seed and same arm (`row_type=sensitivity`),
isolating `num_ctx`/`num_predict`/`thinking_mode` alone with code commit, seed and
arm held fixed:**

| seed | arm | IBR uncond (matched vs unmatched) | IBR threat != medium | EHE | rejection rate | retry rate |
|---|---|---|---|---|---|---|
| 43 | governed | 0.44 % vs 0.11 % (+0.33 pp) | 0.97 % vs 0.23 % (+0.73 pp) | 0.832 vs 0.806 (+0.026) | 0.66 % vs 0.34 % (+0.32 pp) | 8.11 % vs 5.86 % (+2.25 pp) |
| 44 | governed | 0.40 % vs 0.94 % (-0.54 pp) | 0.86 % vs 1.97 % (-1.10 pp) | 0.887 vs 0.855 (+0.032) | 0.94 % vs 0.94 % (+0.00 pp) | 9.03 % vs 8.70 % (+0.33 pp) |
| 4202 | no-validator | 8.47 % vs 9.56 % (-1.08 pp) | 15.98 % vs 17.26 % (-1.28 pp) | 0.822 vs 0.841 (-0.019) | 0.00 % vs 0.00 % | 0.00 % vs 0.00 % |
| 4203 | no-validator | 10.65 % vs 10.59 % (+0.05 pp) | 19.17 % vs 19.74 % (-0.57 pp) | 0.853 vs 0.898 (-0.045) | 0.00 % vs 0.00 % | 0.00 % vs 0.00 % |

The within-seed matched-vs-unmatched movement (up to ~1.3 pp on IBR, ~0.05 on EHE, up
to 2.3 pp on retry rate for the one seed - 43 - whose retry behaviour changed most)
is an order of magnitude smaller than the ~7-20 pp governed-vs-no-validator gap in
every IBR cell above, and never flips a seed's sign relative to its own arm's other
seeds. Inference-setting drift moves these four runs' numbers a little; it does not
manufacture the treatment effect.

**Output:** `out/r11_flood_seed_matched.csv` (`--variant matched`, default) /
`out/r11_flood_seed_matched_unmatched.csv` (`--variant unmatched`); `row_type` in
`integrity` / `config_diff` / `provenance` / `level_disagreement` / `pair` / `stat` /
`sensitivity`.


### r12 - vaccination T0-4 (2026-09-06 new-domain first pass)
**SUPERSEDED 2026-09-09** by `r12b` below (options-text-parity fix, commit
`88c21542`). `r12` itself is untouched and still targets the pre-fix `e0eee08c`
runs - kept runnable as the historical record of what the mis-decode looked like
from inside the run. One correction to this section's own finding: the `[N/A]`
menu placeholder it describes below as a years-2-10 anomaly actually prints on
**every row, every year, all three seeds** of the `e0eee08c` runs - `r12`'s own
digit-vs-`proposed_skill` cross-check (against a fixed alias table, not the
rendered menu) is what showed 0 % disagreement in year 1; it does not mean a
menu was rendered in year 1.
**Answers:** the pre-registered T0-4 acceptance checks (plan Sec 3) for the first
governance-trace analysis of the vaccination / HBM domain, plus the rule census,
action distribution and parser-layer share this package runs for every other domain.
**Data location - not in this repo.** `examples/vaccination_demo/results/` does not
exist under `governed_broker_framework`. These runs live in a sibling checkout,
`wagf-main-runs` (both checkouts gitignore `examples/*/results/`, so the data is
committed nowhere). `r12.py`'s `VACC_ROOT` tries this repo first, then that sibling
checkout, and raises if neither has the directory.
**Runs read:** `JOH_T0-4_gemma3_4b_e0eee08c/Run_42,43,44` (100 agents x 10 years each,
gemma3:4b, `strict` governance profile, code `origin/main e0eee08c`); the 25x3 smoke
run (`JOH_T0-4_smoke_gemma3_4b_e0eee08c`) is checked only to confirm the "DEAD
VALIDATOR" log line is not about it (it has none).
**Definition:** integrity (audit rows vs agents x years, every `run_integrity.json`
field that can be non-OK, manifest seed vs directory seed), a rule census identical in
method to `r3` (same `failed_rules` / `warning_rules` / `status` / `retry_count`
columns, same per-rule and run-level-status math) over the 5 HBM thinking-rules,
`validator_health.csv`'s own seen/fire/warn counts per rule, action shares at
`proposal` / `final` / `executed` (`k = 3`: `get_vaccinated` / `delay` / `refuse`,
`skill_registry.yaml`, `default_skill = delay`), `ehe_vaccination` = pooled-once
H/log2(3) on the executed distribution, the six construct-label columns' observed
VL/L/M/H/VH alphabet and unparsed share, and `parse_layer` / `parse_confidence`
(reusing `r6`'s `clean_structured` / `digit_fallback` / `keyword_fallback` / `blank`
classification).
**The "DEAD VALIDATOR" log line, explained.** `broker/components/analytics/audit.py`
prints it for any rule with `seen_count > 0` and `fire_count == 0` summed over the
whole run. `fire_count` only increments on an ERROR-level block; a WARNING-level rule
structurally can never set it (WARNING rules record and do not block - project
memory: "WARNING rules = 0 % behaviour change"), so every WARNING rule that is ever
evaluated prints this line regardless of whether it is actually inert. Seed 44's
quoted line is about `low_susceptibility_no_get_vaccinated` (WARNING) in the MAIN
100x10 run, not the smoke run - confirmed both from the log grep and independently
from `validator_health.csv` (`seen=3, fire=0`).
**Caveat, found while building this table, not asked for by the brief:** every row's
`raw_output` parses as clean JSON (`parse_layer = enclosure+json` on 100.0 % of rows,
all three seeds) with its own `"decision"` field, and that field disagrees with the
audited `proposed_skill` on 0.0 % of year-1 rows but 49-88 % of rows in years 2-10
(not a fixed remap - `"decision": "1"` resolves to all three skills across different
rows of the same seed). Ruled out as a stale-`raw_output` artifact (byte-distinct,
plausibly-timestamped per year for a sampled agent) and cross-checked against the raw
JSONL trace directly, not just the CSV. `run_integrity.json` cannot see this - it
tracks which parse layer succeeded, not whether the extracted field matches the
recorded skill. Root cause not identified in this pass; flagged so the years 2-10
action distribution (and `ehe_vaccination`, which is computed on it) is not read as
verified against the model's own stated choice the way year 1 is.
**Output:** `out/r12_vaccination_t04.csv` (`row_type` in `integrity` / `config` /
`rule_census` / `validator_health` / `action_distribution` / `ehe_vaccination` /
`construct_label` / `parser_layer` / `decision_field_check` / `acceptance_verdict`).

---

### r12b - vaccination T0-4b, options-text-parity fix rerun (2026-09-09, current)
**Answers:** the same T0-4 acceptance checks as `r12`, on the fixed arm, plus
parity between the model's own `raw_output` decision digit and the menu actually
rendered into that row's own prompt (`r12` decoded against a fixed alias table;
`r12b` decodes against the live per-row menu - the direct test of whether the
fix holds). New, independent script; does not import or modify `r12_vaccination_t04.py`.
**Data location - in this repo.** `examples/vaccination_demo/results/JOH_T0-4b_gemma3_4b_88c21542/Run_{42,43,44}`
(100 agents x 10 years each, gemma3:4b, `strict` profile, code `fix/options-text-parity 88c21542`).
`--old-arm` points the same three tables at the superseded `e0eee08c` runs in the
sibling `wagf-main-runs` checkout instead, for a reproducible side-by-side (writes
the same three output filenames - run once per arm, or diff the two invocations'
console output).
**Does not require `validator_health.csv`.** That file does not exist in the new
arm's run directories (`broker/components/analytics/audit.py` only writes it when
its in-memory summary is non-empty, which itself only happens on a rule
precondition match - see `out/r12_rerun_2026-09-09/r12_rerun_zero_fires_2026-09-09.md`
section 3). Governance sanity is read straight off `individual_governance_audit.csv`'s
own `status` / `failed_rules` / `warning_rules` / `retry_count` columns instead,
which every run writes unconditionally either way.
**Result, new arm:** parity 3000/3000 (100.00 %), all years, all three seeds;
`integrity_ok = true`, zero anomaly counters, all three seeds; 0 REJECTED, 0
retries, 0 remaps; **0 HBM rule fires on all 3000 rows, all three seeds** (the
"≥1 HBM rule fires" acceptance check now FAILS, where it PASSED on the pre-fix
arm) - confirmed this is a fact about the batch's (label, action) distribution
(0/1000 rows on any seed satisfy any of the 5 rules' own preconditions), not a
dead validator (direct positive-control test, `out/r12_rerun_2026-09-09/validator_liveness_2026-09-09.md` -
a synthetic row engineered to satisfy a rule's precondition fires correctly
through the exact production entry point). Final cumulative uptake 50.0 / 56.0 /
64.0 % (mean 56.7 +/- 7.0 pp, n = 3).
**Result, old arm (`--old-arm`), re-examined:** the `Available actions:` menu
renders the literal string `[N/A]` on all 3000/3000 rows, every year, all three
seeds - not just years 2-10 as `r12`'s own fixed-alias check first read it (see
the correction note on `r12` above). Of that arm's 20 rule-fire instances, 17
occur on a row whose own digit (legend-decoded) disagrees with the recorded
`proposed_skill` - likely decode-bug artifacts, not clean governance signal.
**Framing.** This domain demonstrates the DomainPack plug working correctly
(parity, audit-trail integrity, a live and correctly-wired validator), not a
governance effect - nothing here shows the 5 HBM rules changing an outcome, only
that this batch never gave them a matching precondition to act on.
**Output:** `out/r12b_vaccination_parity.csv` (per run per year: `n`, `n_match`,
`n_no_menu_rendered`, `parity_pct_of_decodable`), `out/r12b_vaccination_governance.csv`
(long format: `metric` in `status` / `retry_count` / `failed_rule_ERROR` /
`warning_rule_WARNING` / `integrity` / `integrity_anomaly`), `out/r12b_vaccination_uptake.csv`
(per run per year: `annual_share_pct`, `cumulative_share_pct`); all three carry
an `arm` column (`NEW_88c21542` / `REJECTED_e0eee08c`). Supporting write-ups:
`out/r12_rerun_2026-09-09/r12_rerun_interim_2026-09-09.md` (parity/governance/
outcome recheck), `r12_rerun_zero_fires_2026-09-09.md` (why zero fires - label
distributions, config diff, prompt diff, label provenance), `validator_liveness_2026-09-09.md`
(the positive-control test).

---

### r13 - reservoir control T0-6 (2026-09-07 TOY capability demo, not a paper result)
**TOY, labelled as such throughout.** Plan Sec 1 Tier-0 row T0-6: ONE OPERATOR agent,
ONE annual release-setting decision, against a synthetic mass-balance reservoir
(`ToyMassBalanceReservoir`, 12 monthly sub-steps/year, 42 years, gemma3:4b, `strict`
governance, seeds 42/43/44). Not a calibrated basin, not USBR/CRSS data, not
multi-agent - a scripted 2-year drought tail wrapped modulo-4 over 42 years, built to
exercise exactly one hard rule.
**Data location - not in this repo.** `examples/reservoir_control/results/` in
`governed_broker_framework` only has 4-year smoke dirs (`results_ops`,
`results_ops_e4b`). The 42-year T0-6 batch lives in the sibling `wagf-main-runs`
checkout (both gitignore `examples/*/results/` - committed nowhere). `r13.py`'s
`RES_ROOT` tries this repo first, then the sibling checkout, and raises if neither
has the directory.
**Runs read:** `T0-6_gemma3_4b_e0eee08c/Run_42,43,44` (1 agent x 42 years each,
gemma3:4b, `strict` profile, `num_ctx=8192`/`num_predict=1024`, code
`origin/main e0eee08c`). Source read via `git show origin/main:...` for the output
contract: `run_reservoir_ops.py` (hindcast-then-set annual cadence), `ops_validators.py`
(`dead_pool_violation` linear projection), `ops_modules.py` (`ReservoirOpsBundle`
setpoint mapping + designed drought-tail arithmetic in its module docstring).
**Per-seed table (audit CSV + `raw/operator_traces.jsonl` environment_context, since
storage/spill/shortfall are NOT audit-CSV columns):**

| seed | rows | REJECTED | dead_pool_violation fire/seen | storage min/max/final (maf) | spill total | shortfall total (maf) |
|---|---|---|---|---|---|---|
| 42 | 42/42 | 15 (35.7 %) | 30/30 | 2.474 / 17.276 / 8.094 | 0.000 | 129.15 |
| 43 | 42/42 | 11 (26.2 %) | 23/23 | 3.022 / 17.276 / 8.554 | 0.000 | 131.49 |
| 44 | 42/42 | 9 (21.4 %) | 19/19 | 4.072 / 17.276 / 8.139 | 0.000 | 133.20 |

All three `run_integrity.json` clean (`integrity_ok=True`, `audit_rows==audit_years==
42`, `manifest.seed==dir_seed`, `reflection_expected=False` matching this domain's
config). `flood_control_overflow` (the second registered physical rule) never
evaluates in this batch - storage never exceeds 90 % of the 24.0 maf capacity in any
seed (max observed 17.276 maf, all three). `set_release` is proposed on 42/42
decisions every seed (`maintain_release` never once chosen by the model, proposed or
final). Magnitude choices cluster at 60/65/67/68/70(/75 seed 44 once) - the model
never proposes below 60 % even into the retry that gets REJECTED again.
**Release-target parity (does the agent's choice actually drive the solver?).**
Checked exactly, all 91 APPROVED rows across the 3 seeds (27+31+33):
`world_release_target == magnitude_pct/100 * 0.75` to float precision (1e-9), **0
mismatches**. On all 35 REJECTED rows (15+11+9): `world_release_target` exactly equals
the last APPROVED (or initial 0.75 maf/month) committed target - `ReservoirOpsBundle.
commit_world_delta` silently reuses `_last_release_target` when the approved skill
carries no `magnitude_pct` - **0 mismatches**. So the coupling is exact in both
directions: an approved choice sets the solver input precisely, and a rejected choice
provably does not touch it.
**Wall -> retry -> resolves, the pattern `ops_modules.py`'s docstring is designed
around:** observed twice across the batch (seed 43 year 11, seed 44 year 26) - first
attempt blocked by `dead_pool_violation`, retry at the same or lower magnitude
projects above the dead pool and is APPROVED. The other 24 retries (of 26 total
`retry_count=1` rows) stayed REJECTED after the retry.
**Two odd findings, neither visible from `run_integrity.json`:**
1. `governance_summary.json`'s `total_interventions` reads **0** in all three seeds,
   while `audit_summary.json`'s `validator_health` (and the audit CSV itself)
   correctly show 30/23/19 `dead_pool_violation` fires. `GovernanceAuditor.
   log_intervention()` (`broker/utils/governance_auditor.py`) is evidently not called
   on this domain-physical-validator path - the audit trail is right, the legacy
   summary counter is not.
2. The audit CSV's own `fallback_activated` column reads `False` on every one of the
   126 rows across all three seeds, including all 35 REJECTED rows - even though the
   release-target parity check above proves a REJECTED decision demonstrably falls
   back to the prior committed setpoint. The flag simply does not track this domain's
   REJECTED-retains-prior-setpoint behaviour.
**Coupling evidence.** The brief's field names `coupling_contract_active` /
`coupling_guard_calls` do not exist in `run_integrity.json` schema 2. What is there,
consistent across all three seeds: `run_integrity.json` `coupling_adapter=True`,
`sim_engine_class=EnvironmentCouplingAdapter`; `reproducibility_manifest.json`
`coupling_provenance` (`adapter_class=EnvironmentCouplingAdapter`,
`bundle_class=ReservoirOpsBundle`, `solver_class=ToyMassBalanceReservoir`,
`substeps_per_decision=12`, plus a `contract_sha256`).
**Output:** `out/r13_reservoir_t06.csv` (`row_type` in `integrity` / `config` /
`action_distribution` / `magnitude_distribution` / `rule_firing` /
`storage_trajectory` / `coupling_evidence` / `release_target_parity` /
`odd_finding`).

### r14 - irrigation advise arm (2026-09-10, Tier-1 T1-2, FINAL n = 5)

**Pre-registered question (plan Sec 3, T1-2):** does a WARNING-level finding shown to
the model as advice, without changing whether the decision is blocked, change what
the model proposes? `strict` profile + `governance.advise_mode: feedback`
(`docs/guides/governance_layers.md`, read via `git show origin/main:...` since this
branch's tree does not carry the doc), gemma3:4b, 78 agents x 42 years, code
`e0eee08c`. Directory:
`examples/irrigation_abm/results/advise_feedback_42yr_gemma3_4b_e0eee08c_seed{N}`.

**All five seeds (42-46) are complete; the killed-and-restarted seed-46 attempt is
excluded.** `..._seed46_PARTIAL_killed_2026-09-08/` (raw/ + an empty
`reflection_log.jsonl`, no audit csv - the remnant of a killed first attempt at seed
46) is skipped entirely by a 2026-09-10 discovery-code fix, not read, not counted as
incomplete. Numbers below are the **FINAL n = 5** (mean +/- sample sd, ddof=1) -
this supersedes the n = 3 interim look (seeds 42-44 only) reported here through
2026-09-08. Full statistics, exact commands and the interim-vs-final walkthrough:
`out/r14_advise_final_n5_2026-09-10.md`.

**Integrity: clean on all 5 seeds.** Audit 3276/3276 rows each, `run_integrity.json`
`integrity_ok=True`/`audit_rows=3276`; manifest `git_commit=e0eee08c141b16cc0c683a0cfc43d36bad451da5`/
`num_ctx=8192`/`num_predict=4096`/`config_hash=62d2eeb2373e` identical on all 5;
`soft_advise_mode` is `"feedback"` on all 3276 rows of every seed.

**Advice reached the model on 4.16 % +/- 0.39 % of rows (mean across seeds)** -
151/3276 (4.61 %, seed 42), 116/3276 (3.54 %, seed 43), 134/3276 (4.09 %, seed 44),
140/3276 (4.27 %, seed 45), 140/3276 (4.27 %, seed 46). All carry
`advise_shown=True`. Findings shown, by rule id (a row can carry more than one), all
WARNING-level and matching `governance_layers.md`'s layer-2 table on every seed - no
new rule id appears:

| rule id | seed 42 | seed 43 | seed 44 | seed 45 | seed 46 |
|---|---|---|---|---|---|
| `thinking:high_threat_no_maintain` | 99 | 65 | 87 | 87 | 108 |
| `institutional:curtailment_awareness` | 37 | 40 | 35 | 38 | 31 |
| `physical:curtailment_awareness` | 14 | 9 | 12 | 13 | 0 |
| `physical:non_negative_diversion` | 1 | 2 | 0 | 2 | 1 |

**Uptake = mean 16.12 % +/- 2.02 % sd** (25/151 = 16.56 %, 17/116 = 14.66 %,
25/134 = 18.66 %, 19/140 = 13.57 %, 24/140 = 17.14 %), denominator = advised rows on
each seed, per the pre-registration. Treated as a one-sample test against 0
(no strict-arm counterpart exists): t = 17.85, df = 4, p = 0.0001, exact sign-flip
permutation p = 0.0625 (the n=5 floor). **HOLDS on 5/5 seeds, no exceptions -
uptake > 0 pre-registered hypothesis (H-a) CONFIRMED at final n = 5.** Direction of
the changed proposals mixes MORE-demand and LESS-demand changes on every seed (e.g.
seed 42: `increase_small->maintain_demand` 7 vs `maintain_demand->increase_large` 7;
seed 46: `maintain_demand->increase_large` 10 vs `maintain_demand->increase_small`
7) - "the model backs off when warned" is not what uptake shows on any seed. Of the
advised rows, `advise_post_validation_invalid` is 13.25 % / 15.52 % / 21.64 % /
22.14 % / 17.14 % (mean 17.94 % +/- 3.87 %); those revert to the pre-advice
proposal (`advise_executed_stage=pre`: 24/151, 22/116, 33/134, 34/140, 29/140).
`advise_parse_failed` stays low (2.65 % / 3.45 % / 2.99 % / 2.14 % / 3.57 %, mean
2.96 % +/- 0.59 %). `soft_findings_unidentified` is 0 on every row of every seed.

**Blocking is higher on advise than strict on 4/5 seeds - seed 46 breaks the n = 3
interim's clean run.** `rejected_to_fallback`: 42.28 % vs 38.68 % (seed 42,
+3.60 pp), 39.53 % vs 36.36 % (seed 43, +3.17 pp), 38.98 % vs 37.21 % (seed 44,
+1.77 pp), 40.35 % vs 37.64 % (seed 45, +2.72 pp), 42.98 % vs **47.59 %** (seed 46,
**-4.61 pp**) - **mean 40.82 % +/- 1.74 % (advise) vs 39.49 % +/- 4.60 % (strict),
diff +1.33 pp +/- 3.39 pp, 95 % CI [-2.88, +5.54] pp (includes 0).** Paired t
(df=4): t = 0.88, p = 0.43. Exact sign-flip permutation p = 4/32 = 0.4375 - **not**
the n=5 floor of 0.0625, because the sign is no longer unanimous. This is a
**strict-arm** anomaly, not an advise-arm one: `production_v21_42yr_seed46`'s own
numbers (mead_min 964.0 ft, approved_first_attempt 29.67 %, increase_rate 48.57 %)
are outliers against its own four seed-mates, all of which sit in a much tighter
band (994-998 ft / 36-39 % / 37-40 %). `approved_first_attempt` and
`approved_after_retry` (not part of the pre-registered metric list, reported for
completeness) show the same seed-46-driven break: `approved_after_retry` is lower
on advise on all 5 seeds (consistent), but `approved_first_attempt` flips sign on
seed 46 for the same reason as `rejected_to_fallback`.

**Headline metrics, proposal + executed level, per seed and mean +/- sd**
(`_loader.ibr` / `_loader.increase_rate` on `simulation_log.yearly_decision`; EHE
pooled once, H/log2(5)):

| arm | metric | seed 42 | seed 43 | seed 44 | seed 45 | seed 46 | mean +/- sd |
|---|---|---|---|---|---|---|---|
| advise_feedback | IBR % (proposal) | 40.61 | 41.52 | 33.30 | 37.16 | 45.56 | 39.63 +/- 4.64 |
| strict | IBR % (proposal) | 36.05 | 36.69 | 33.47 | 32.40 | 41.65 | 36.05 +/- 3.60 |
| no_validator | IBR % (proposal) | 61.47 | 58.26 | 58.86 | 57.04 | 59.72 | 59.07 +/- 1.66 |
| advise_feedback | IBR % (executed) | 1.23 | 0.95 | 1.14 | 0.78 | 0.18 | 0.86 +/- 0.42 |
| strict | IBR % (executed) | 0.96 | 0.76 | 0.75 | 1.02 | 0.83 | 0.86 +/- 0.12 |
| advise_feedback | increase_rate % (proposal) | 43.25 | 40.54 | 39.74 | 40.72 | 43.77 | 41.61 +/- 1.79 |
| strict | increase_rate % (proposal) | 39.38 | 37.85 | 40.32 | 38.37 | 48.57 | 40.90 +/- 4.39 |
| advise_feedback | EHE pooled (proposal) | 0.6761 | 0.6464 | 0.6152 | 0.6778 | 0.6703 | 0.6572 +/- 0.0266 |
| strict | EHE pooled (proposal) | 0.6338 | 0.6375 | 0.6731 | 0.6691 | 0.7487 | 0.6724 +/- 0.0462 |
| advise_feedback | mead_min ft | 994.67 | 995.94 | 996.45 | 995.55 | 996.31 | 995.78 +/- 0.72 |
| strict | mead_min ft | 997.62 | 994.36 | 996.97 | 996.03 | 964.01 | 989.80 +/- 14.47 |
| advise_feedback | shortage years | 15 | 13 | 12 | 13 | 15 | 13.60 +/- 1.34 |
| strict | shortage years | 14 | 17 | 15 | 12 | 16 | 14.80 +/- 1.92 |

`first_dead_pool_year` reads "none" on advise and strict on all 5 seeds (never
reached, even strict seed 46's 964.0 ft low); no_validator hit dead pool on every
seed checked in the n=3 look (years 17/17/18).

**Paired t (df=4), advise minus strict, with the exact n = 5 permutation floor and a
95 % CI stated alongside every t-test p** (floor = 2/32 = 0.0625 when all 5 diffs
share a sign - never read a t-test p past what n = 5 can resolve):

| metric | mean diff | 95% CI | paired t | t-test p | exact permutation p |
|---|---|---|---|---|---|
| IBR % proposal | +3.58 pp | [+0.94, +6.22] | 3.76 | 0.020 | 0.1250 (seed 44 flips sign) |
| IBR % executed | -0.01 pp | [-0.54, +0.53] | -0.03 | 0.976 | 1.0000 (seeds 45/46 flip sign) |
| increase_rate % proposal | +0.71 pp | [-3.62, +5.03] | 0.45 | 0.673 | 0.6875 (seeds 44/46 flip sign) |
| EHE pooled (proposal) | -0.0153 | [-0.0782, +0.0477] | -0.67 | 0.538 | 0.5625 (seeds 44/46 flip sign) |
| mead_min ft | +5.98 ft | [-12.39, +24.36] | 0.90 | 0.417 | 0.7500 (seeds 42/44/45 flip sign) |
| shortage years | -1.20 | [-4.03, +1.63] | -1.18 | 0.305 | 0.4375 (seeds 43/44/46 flip sign) |

No metric except uptake clears the n=5 permutation floor. IBR-proposal is the
strongest of the rest (t-test p = 0.020, 95 % CI excludes 0) but its exact
permutation p (0.125) is still short of the floor - one sign flip (seed 44,
unchanged from n=3) keeps it there.

Per-year increase_rate, advise minus strict (`out/r14_advise_yearly.csv`, 42 years
x 5 seeds = 210 rows), keeps the same shape on seeds 42-45 as the n=3 look: advise
above strict more years than below. Seed 46 is the outlier year-by-year too,
tracking its anomalous strict reference rather than the other 4 strict seeds.

**Pre-registered hypotheses, FINAL n = 5.** Uptake > 0 (H-a): **HOLDS**, consistent
positive on 5/5 seeds, exact permutation p at its n=5 floor (0.0625).
`rejected_to_fallback ~= strict` (H-b): **NOT SETTLED** - the n=3 interim's clean
"same direction on 3/3" broke at n=5 because the strict reference's seed 46 is an
outlier against its own four seed-mates, not because the advise arm's own numbers
moved much (40.26 % -> 40.82 %).

**Reference-arm caveat, stated plainly.** `production_v21_42yr_seed{N}` (strict) and
`ungoverned_v21_42yr_seed{N}` (no-validator) remain separate real-LLM runs on a
DIFFERENT git commit than the advise arm's `e0eee08c` for every seed - three
distinct commits recorded across seeds 42/43/44 alone (`d8a5da41`/`db05d3a2`/
`708d34f1`), and no commit recorded at all in the sparser seed-45/46 manifests -
not a byte-identical rerun with only `advise_mode` flipped, at n=3 or at n=5.
Project memory already documents gemma3/gemma4-class Ollama runs as
non-deterministic run-to-run at fixed seed and fixed code. So the rejection-rate
gap flipping sign on exactly the strict seed (46) whose OWN corpus-internal numbers
are already an outlier is consistent with either (a) ordinary real-LLM /
cross-commit sampling variance concentrated in one strict-arm run, or (b) the
advisory call's effect genuinely varying by seed - **this table cannot distinguish
the two even at final n = 5**, and does not claim to. Full manifest evidence:
`out/r14_advise_final_n5_2026-09-10.md` Sec 5.

**Output:** `out/r14_advise_arm.csv` (15 rows: one row per arm x seed for 5 seeds x
3 arms; advice-only columns carry `N/A_by_design` on the reference rows),
`out/r14_advise_findings.csv` (46 rows: rule ids and before->after directions, per
seed), `out/r14_advise_yearly.csv` (210 rows: per-year increase_rate, advise vs
strict, 42 years x 5 seeds), `out/r14_advise_stats_n5.csv` (8 rows: one per
pre-registered metric, mean +/- sd per arm, 95 % CI, paired-t p, exact permutation
p and direction-consistency call - new in the 2026-09-10 n=5 extension, replacing
the 3 `advise_MINUS_strict_paired_t` summary rows the n=3 script smuggled into
`r14_advise_arm.csv`'s column union).

### r16 - vintage-of-code prompt/memory length check (2026-09-07)

**Question.** A reviewer found a backfilled irrigation run
(`ungoverned_v21_42yr_ministral3_8b_seed44`, 2026-08 real-LLM backfill) with a much
shorter injected-memory column than its March arm-mates - a difference in the code
that renders the prompt, invisible to a `config_snapshot.yaml` diff. Does the same
thing affect the flood no-validator "live" arm (`JOH_ABLATION_DISABLED/.../Run_1-3`
backfilled 2026-05-30, `Run_4-5` and the whole governed `Group_C` arm from 2026-02),
or today's Sept T0-1b/T0-2b matched top-up (r11)?

**What "the memory column" is.** Neither audit CSV carries the rendered memory text
as a column of its own (checked: their `mem_*` columns are counts/mode/engine-name).
It exists, verbatim, inside the raw JSONL's `input` field, introduced by the literal
line `Your memory includes:` and closed by the next blank line - matched on 100% of
sampled rows across every vintage read (Feb/May/Aug backfills, Sept matched top-up).
That substring is what the table calls `memory_mean`/`memory_median`.

**33 runs, 1 flagged.** Within each arm (a fixed grouping, e.g. all 5 flood
no-validator "live" runs count as ONE arm so an internal vintage split shows up
rather than being defined away), a run is flagged if its mean memory or mean prompt
length is more than 30% from the arm's median-of-means. Only
`ungoverned_v21_42yr_ministral3_8b_seed44` (Aug backfill) is flagged: memory mean
194.6 chars vs its two March arm-mates' 575.9 / 628.6 (-66% / -69%), while its
governed ministral arm-mates (42/43/44, all March-vintage `plain_string` memory
schema) sit at 633.7-681.4 unaffected.

**Root cause, found while chasing the number: a reflection-write bug, not just a
shorter template.** `memory_pre` (the retrieved-memory list upstream of the
rendered prompt) changed item SCHEMA across vintages - March runs store plain
strings, April+ gemma runs and the Aug ministral backfill store `{"content": ...,
"emotion": ..., ...}` dicts. In the flagged run, the `"Consolidated Reflection: ..."`
memory item is truncated to the literal 27-character string
`"Consolidated Reflection: {"` on 3106/3198 rows with memory (85.5% of all reflection
items in the run; `reflection_len_mean`/`pct_reflection_truncated_le60chars` in the
CSV). The SAME truncation pattern exists at a low background rate in gemma
irrigation runs (11/9,590 reflection items, 0.1-0.4%) and a higher one in the OTHER
ministral runs (7.2-9.9%) - so this is a real bug that ministral-3:8b's own output
style turns from occasional into near-universal in this one run, not something that
appears from nothing. It plausibly explains most of the reviewer's number on its
own; a shorter rendering template is not required to explain it.

**A second, unrelated vintage artifact found in the same pass: `raw_output` length
depends on WHICH FILE you read it from.** The raw JSONL's own `raw_output` field is
hard-capped at exactly 500 chars + the literal suffix `"...[truncated]"` (514 chars
total) on 99.8-100% of rows in every Feb-May-vintage run checked - flood AND
irrigation, gemma AND ministral alike (`rawout_jsonl_mean`/`rawout_jsonl_truncated_pct`
in the CSV). The Aug ministral backfill and the Sept T0-1b/T0-2b top-up do not
truncate the jsonl copy at all. The audit CSV's OWN `raw_output` column, spot-checked
against the same rows, is never truncated in any vintage (JOH_FINAL Run_1 row 1:
CSV 775 chars vs jsonl 514). This table's `rawout_mean`/`rawout_median` columns read
the CSV, the vintage-stable source; once read that way, raw_output is flat across
vintage within each domain (flood 783-834 chars regardless of Feb/May/Sept; irrigation
gemma 859-885; irrigation ministral 1032-1101) - the 514-vs-800+ split visible in the
raw jsonl field is a debug-trace truncation policy that changed, not a real
difference in how verbose the model's answers were.

**Is the flood live no-validator arm comparable in prompt input? Mostly not on
memory, yes on everything else.** `Run_1-3` (May backfill; manifest carries
`git_commit`/`timestamp`/`memory_engine_class=DecisionFilteredMemoryEngine`, absent
from `Run_4-5`'s manifest) mean memory 1,085.1 / 1,085.4 / 1,036.2 chars (avg 1,068.9)
vs `Run_4-5` (Feb) 875.7 / 902.4 (avg 889.0) - **+20.2%**, and vs the governed
`Group_C` arm (Feb, avg 894.8) - **+19.5%**; `Run_4-5` itself sits within 0.6% of
governed. Full prompt length moves much less over the same split (`Run_1-3` avg
3,706.0 vs `Run_4-5` avg 3,526.2, **+5.1%**), and CSV-sourced `raw_output` barely
moves at all (820.6-834.1 chars across all 5 runs, no split). Neither sub-group
individually crosses the 30% flag on the arm's own blended median, but the split is
real and specific to the memory column: the May backfill's arm-mates are NOT
interchangeable with `Run_4-5` in what the model actually read as memory, even
though the two "look like" one arm from `config_snapshot.yaml`.

**Is today's Sept T0-1b/T0-2b matched top-up comparable to the corpus it extends?**
Yes, well inside tolerance. Governed `Run_43,44` mean memory 809.1 vs published
`Group_C` 894.8 (-9.6%); no-validator `Run_4202,4203` mean memory 788.0 vs published
`Run_4-5` 889.0 (-11.4%) - both under the 30% bar, and CSV `raw_output` matches
closely too (789-797 vs 780-834 published). The Sept batch is measurably closer to
the published Feb corpus in prompt input than the May no-validator backfill is to
its OWN Feb arm-mates.

**Year vs vintage, so growth is not mistaken for a code change.** Memory grows
several-fold across a run's own years (flood `Group_C Run_1`: year-1 mean 393 chars
-> year-10 mean 1,052; irrigation governed seed42: year-1 mean 16 chars (`"No
memories yet."`) -> year-42 mean 444), dwarfing every cross-run gap reported above.
Every comparison above is between runs of the SAME length (10 years for all flood
runs, 42 for all irrigation runs), so horizon cannot be the explanation for any of
the flagged or near-flagged gaps; `out/r16_vintage_prompt_check_by_year.csv` (one row
per run x year) is there to check any other comparison the same way.

**A third observation, not flagged because it stays under 30%:** within the
nominal `irr_governed`/`irr_ungoverned` arms, seeds 42-44 carry the dict
`memory_pre` schema and a rich manifest (git_commit/timestamp), while seeds 45-46
carry the plain-string schema and a manifest with none of those fields - a vintage
split inside an arm the paper treats as one 5-seed batch. It moves `memory_mean` by
+19.5% (governed: 45-46 avg 542.5 vs 42-44 avg 454.0) but -8.7% in the opposite
direction on the no-validator side (45-46 avg 393.3 vs 42-44 avg 430.9), so unlike
the flood live-arm split this one does not have a consistent sign - reported as a
fact about the corpus, not a claim about which direction memory content changed.

**Output:** `out/r16_vintage_prompt_check.csv` (one row per run + one row per arm
summary: medians, spread, flagged runs), `out/r16_vintage_prompt_check_by_year.csv`
(one row per run x year, for the horizon check above).

---

## Corpora read

| Path | What |
|---|---|
| `examples/irrigation_abm/results/production_v21_42yr_seed42..46` | governed irrigation, gemma3:4b |
| `examples/irrigation_abm/results/ungoverned_v21_42yr_seed42..46` | no-validator irrigation |
| `examples/irrigation_abm/results/fql_raw/seed42..seed51` | FQL baseline, validators ON |
| `examples/irrigation_abm/results/fql_nogov/seed42..seed51` | FQL, validators OFF - **not paper data** |
| `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_C/Run_1..5` | governed flood |
| `examples/single_agent/results/JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_1..5` | no-validator flood |
| `examples/single_agent/results/JOH_T0-1_strict_gemma3_4b_e0eee08c/Run_43,44` | **2026-09-06 top-up**: governed flood, seeds 43/44, code `origin/main e0eee08c` - r11 only |
| `examples/single_agent/results/JOH_T0-2_disabled_gemma3_4b_e0eee08c/Run_4202,4203` | **2026-09-06 top-up**: no-validator flood, seeds 4202/4203, code `origin/main e0eee08c` - r11 only |
| `examples/single_agent/results/_QUARANTINE_reflection_missing_2026-05-30/gemma3_4b/Run_1..3` | pre-quarantine no-validator flood, **r4 published-number reconciliation only** |
| `examples/single_agent/results/rulebased/Run_1..3` | rule-based PMT flood baseline |
| `SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42..46` | **unreleased, provenance RED, disclosure only** (r6, r9) |
| `<repo>/../wagf-main-runs/examples/vaccination_demo/results/JOH_T0-4_gemma3_4b_e0eee08c/Run_42,43,44` | **2026-09-06 new domain, SUPERSEDED**: vaccination/HBM, gemma3:4b, `strict` profile, code `origin/main e0eee08c` - r12 only (kept as historical record; see r12's superseded note). **Not in this repo** - sibling checkout, gitignored in both, committed nowhere |
| `<repo>/../wagf-main-runs/examples/vaccination_demo/results/JOH_T0-4_smoke_gemma3_4b_e0eee08c` | vaccination smoke run (25 agents x 3 years) - r12 checks its log only, to confirm the DEAD VALIDATOR line is not about it |
| `examples/vaccination_demo/results/JOH_T0-4b_gemma3_4b_88c21542/Run_42,43,44` | **2026-09-09 options-text-parity fix, current**: vaccination/HBM, gemma3:4b, `strict` profile, code `fix/options-text-parity 88c21542` - r12b default arm. **In this repo** (`examples/*/results/` gitignored as usual, but present on this checkout) |
| `<repo>/../wagf-main-runs/examples/reservoir_control/results/T0-6_gemma3_4b_e0eee08c/Run_42,43,44` | **2026-09-07 new domain, TOY**: reservoir control, 1 OPERATOR agent x 42 years, gemma3:4b, `strict` profile, code `origin/main e0eee08c` - r13 only. **Not in this repo** - sibling checkout, gitignored in both, committed nowhere |
| `examples/irrigation_abm/results/advise_feedback_42yr_gemma3_4b_e0eee08c_seed{42,43,44,45,46}` | **2026-09-07/10 Tier-1 T1-2, FINAL n=5**: irrigation, `strict` + `governance.advise_mode: feedback`, gemma3:4b, code `e0eee08c` - r14 only. The `..._seed46_PARTIAL_killed_2026-09-08` remnant of a killed-and-restarted first attempt is excluded entirely (not read, not counted) |

No file outside `SUBMISSION_2026/reviewer_prep_2026-09-05/` is written. Nothing is
committed.
