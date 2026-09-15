# Reviewer-prep headline numbers - 2026-09-05

> **DATA STATUS — 2026-09-15.** The irrigation, single-agent flood, and
> vaccination corpora behind this package were lost 2026-09-15 (VSS restore
> zero-filled files at the right name/size/mtime; 0/183 manifest-bearing run
> dirs came back clean — see `r18_restore_verification_2026-09-15.md`).
> Every number below is the **pre-loss value** computed 2026-09-05...09-10,
> **not currently re-verifiable against disk**. Corpora are being
> regenerated at commit `e75e390c` (`.research/experiment_plan_framework_paper_2026-09-06.md`
> §0b); until then this is the **original-corpus record**, not a live reproduction.

Every number here was recomputed 2026-09-05...09-10 from released corpora that were on
disk at that time, using the scripts in `../scripts/`. Those corpora are lost as of
2026-09-15 (see banner above) and the numbers are not currently reproducible. Nothing
is quoted from a draft. Where a published figure and a recomputed one disagree, both
are printed and the disagreement is named.

**Sanity gate (r0): PASS.** Irrigation headline IBR reproduces to 36.05 % governed
(sd 3.60) and 59.07 % no-validator (sd 1.66) on the five seed-matched gemma3:4b v21
runs - delta +0.002 pp and +0.000 pp against the published values, well inside the
0.05 pp tolerance, and identical to `decomposition/reproduce_published.py`.

---

## The fifteen numbers

| # | Number | What it is | Table |
|---|---|---|---|
| 1 | **36.05 / 59.07 %** (gap -23.02 pp, paired t = -16.15, df = 4, t-p = 0.000086) | Irrigation IBR, governed vs no-validator, on the PROPOSAL column - the published headline | r0, r5, r7 |
| 2 | **0.86 / 26.77 %** (gap -25.90 pp) | The same statistic on the EXECUTED action (a REJECTED proposal runs `maintain_demand`). Different number, same sign | r5 |
| 3 | **39.5 % / 29.0 %** of irrigation decisions end REJECTED-to-fallback (governed / no-validator) | So 39.5 % of the governed headline's rows describe an action that never ran | r3, r5 |
| 4 | **989.8 +/- 14.5 ft / 895.0 +/- 0.0 ft** minimum Lake Mead; **14.8 +/- 1.9 / 38.2 +/- 0.8** shortage years | 0 of 5 governed seeds reach dead pool, 5 of 5 no-validator seeds do | r1, r7 |
| 5 | **999.3 +/- 4.7 ft** (FQL with validators) vs **895.0 +/- 0.0 ft** (FQL without) | The FQL baseline's conservatism is the validator stack, not the Q-learning kernel - 10 of 10 no-validator FQL seeds hit dead pool | r1 |
| 6 | **0.87 / 7.41 %** flood IBR (R1+R3+R4, R5 excluded), unconditional, per-run-then-mean | The live flood corpus. Published Extended Data Table 2 says 0.9 / 8.5 | r2, r4, r7 |
| 7 | **8.53 +/- 1.08 %** | The published 8.5 reproduces only from the PRE-QUARANTINE no-validator arm (quarantined Run_1-3 + live Run_4-5). The live corpus gives 7.41 | r4 |
| 8 | **35.4 % of no-validator irrigation rows are ERROR-blocked** by the `not at_allocation_cap` skill precondition | The "no validator" arm is not an unblocked arm | r3 |
| 9 | **3.2 % / 4.1 %** of released irrigation rows were decided by a fallback parsing layer; **16.15 %** on the unreleased TAE seed 42, of which the `enclosure+json+digit` layer alone is the 10.47 % on record | r6 |
| 10 | **Elevation rate 0.986 / 0.996 / 0.887** (governed / no-validator / rule-based) against empirical ranges 0.03-0.12 (table A) and 0.10-0.35 (table B) | Every arm is far outside both. Insurance and buyout land in range for at least one arm | r8 |
| 11 | **Governed IBR bounds 3.35 % (label rules undone) / 1.05 % (world rules undone)**, both far below the 36.05 % published proposal-level figure and both close to the 0.86 % executed figure | An accounting bound, not a re-run: undoing the two label-conditioned rules (`low_threat_no_increase`, `high_threat_high_cope_no_increase`) moves the executed IBR less than 3 points; undoing the world/state rules (`demand_ceiling_stabilizer` and five others) moves it about 1 point. Neither rule family alone explains the proposal-to-executed gap - 56 % of blocked-and-increase-proposed rows are blocked by **both** families on the same row, and those stay blocked in either bound | r10 |
| 12 | **Flood IBR 0.74 / 8.03 %** unconditional (gap -7.29 pp, paired t p = 0.00003), now seed-matched at **n = 7** (df = 6) instead of n = 3, inference settings matched to the published arm | Two 2026-09-07 top-up batches (seeds 43/44 governed, 4202/4203 no-validator, code `e0eee08c`, num_ctx=8192/num_predict=4096/thinking=disabled) give flood the same seven seeds on both arms for the first time. All three IBR conditionings and both governance-process rates (rejection, retry) run the same direction on all 7 seeds - zero sign flips; only EHE flips (2 of 7), as in every other flood table here. A matched-vs-unmatched sensitivity check moves every metric under 1.3 pp / 0.05 entropy units - no conclusion changes | r11 |
| 13 | **Vaccination T0-4b (rerun, `88c21542`): parity 100 % (3000/3000, menu-decoded), integrity clean, 0 HBM rule fires on all three seeds** (gemma3:4b, HBM, 100 agents x 10 years); final cumulative uptake 50.0/56.0/64.0 % (mean 56.7 +/- 7.0 pp) | New domain, DomainPack-plug demonstration (parity/audit/integrity), not a governance effect. The options-text-parity fix now decodes the model's own `raw_output` digit against the menu actually rendered into that row's own prompt at 100 % agreement with `proposed_skill`, every year, all three seeds (the pre-fix `e0eee08c` runs rendered `Available actions: [N/A]` on literally every row of all three seeds - no menu was ever shown, at any year). But the 5 HBM thinking-rules' own (label, action) preconditions never co-occur in this fixed batch, so 0/1000 rows fire any rule on any seed - the "≥1 HBM rule fires" check now FAILS, where it PASSED (WARNING-only) on the pre-fix runs. The validator itself is confirmed live by a direct positive-control test (synthetic precondition-satisfying rows fire correctly through the exact production entry point), not a dead code path. 17 of the pre-fix runs' 20 rule-fire instances occur on rows whose own digit (legend-decoded) disagrees with the recorded `proposed_skill` - likely decode-bug artifacts, not clean governance signal | r12 (pre-fix `e0eee08c`, superseded) / r12b (fix `88c21542`, current) |
| 14 | **Reservoir control T0-6 (TOY): REJECTED 35.7 / 26.2 / 21.4 %** across seeds 42/43/44 (gemma3:4b, 1 agent x 42 years), `dead_pool_violation` fires on every row it is evaluated on (fire==seen: 30/23/19) | New domain, TOY capability demo (synthetic reservoir, not calibrated basin data). Release-target parity is exact in both directions - 0/91 mismatches on APPROVED rows (`world_release_target == magnitude_pct/100*0.75`), 0/35 mismatches on REJECTED rows (target silently reverts to the last APPROVED value). Two instrumentation gaps found, neither visible from `run_integrity.json`: `governance_summary.json` `total_interventions` reads 0 despite 30/23/19 real blocks in the audit CSV, and the CSV's own `fallback_activated` column reads `False` on every REJECTED row even though the parity check proves a fallback happens | r13 |
| 15 | **Irrigation advise arm, FINAL n = 5 (2026-09-10): advised rows 4.16 +/- 0.39 % of rows, uptake 16.12 +/- 2.02 % - one-sample vs 0, t = 17.85, df = 4, p = 0.0001, exact permutation p = 0.0625 (the n=5 floor), consistent positive on 5/5 seeds; IBR(prop) advise 39.63 +/- 4.64 % vs strict 36.05 +/- 3.60 % (paired diff +3.58 pp, 95% CI [+0.94, +6.22], t = 3.76, df = 4, p = 0.020, exact permutation p = 0.125, NOT consistent - seed 44 flips sign); rejected_to_fallback 40.82 +/- 1.74 % (advise) vs 39.49 +/- 4.60 % (strict), diff +1.33 pp, 95% CI [-2.88, +5.54], t = 0.88, p = 0.43, exact permutation p = 0.4375, NOT consistent - seed 46 flips sign because its OWN strict reference is an outlier (rejected_to_fallback 47.59 %, mead_min 964.0 ft, approved_first_attempt 29.67 %, vs 994-998 ft / 36-39 % on the other 4 strict seeds)** (gemma3:4b, code `e0eee08c`) | Tier-1 T1-2, FINAL 5-seed call (seeds 45-46 added 2026-09-10, see `out/r14_advise_final_n5_2026-09-10.md`). **Uptake > 0 (H-a): HOLDS**, direction consistent on 5/5 seeds, exact permutation p at its n=5 floor. **rejected_to_fallback ~= strict (H-b): NOT SETTLED.** The interim's clean "same direction on 3/3" broke at n=5 - not because advise's own numbers moved much (40.26->40.82 %), but because the strict reference's seed 46 is an outlier against its own four seed-mates (a corpus artifact, not evidence advise_mode changed blocking; every strict seed is itself a distinct, non-byte-identical real-LLM run on `d8a5da41`/`db05d3a2`/`708d34f1` for seeds 42/43/44, commit unrecorded in the sparser seed-45/46 manifests). No metric's exact permutation p clears the n=5 floor of 0.0625 except uptake | r14 |

---

## Published numbers that reproduce exactly

| Published | Definition it belongs to | Table |
|---|---|---|
| irrigation 36.05 / 59.07 | conditional high-WSA increase rate, proposal column, per-seed mean | r0 |
| irrigation 0.86 / 26.77 | the same, executed remap | r5 |
| Mead 989.8 +/- 14.5 / 895.0; 1086.3 / 984.0 mean; FQL 999.3 +/- 4.7 / 1140.2 | per-year across-agent mean elevation | r1 |
| flood 0.87 / 7.41 | IBR unconditional, live corpus | r4 |
| flood 1.60 / 14.22 | IBR conditioned on threat appraisal != medium, per-run-then-mean | r4 |
| flood 2.51 / 22.56 | IBR conditioned on threat appraisal high, per-run-then-mean | r4 |
| flood 0.9 / 8.5 and 0.87 / 8.53 | IBR unconditional, **pre-quarantine** no-validator arm (r7 regenerates it as 8.5273 +/- 1.0812) | r4, r7 |
| flood EHE 0.861 +/- 0.045 (governed) | pooled-once H/log2(4) on `simulation_log.yearly_decision`, `relocated` -> `relocate` | r7, r8 |
| flood EHE 0.815 +/- 0.053 (no-validator) | the same, **pre-quarantine** arm — r7 row `noval_arm=prequarantine`, `metric=ehe_flood_pooled_simlog_PUBLISHED`, giving 0.8145 +/- 0.0527. The live arm gives 0.7860 +/- 0.0396 | r7 |
| flood EHE **p = 0.166** | reproduces ONLY as an **unpaired** two-sample t (Student, df 8) of governed against the **pre-quarantine** arm: p = 0.1672 (Welch 0.1683). See the test-family note below | r7 |

## Published numbers that reproduce from NO cell

| Published | Closest computed cells | Table |
|---|---|---|
| irrigation EHE **0.687 / 0.848** | per-seed mean on `simulation_log` 0.672 / 0.857 - pooled across seeds 0.677 / 0.860 - audit proposal column 0.674 / 0.857 - parsed-label-only 0.674 / 0.857. None is within 0.01 of both halves | r7 |
| rule-based flood EHE **0.583 +/- 0.014** | 0.693 +/- 0.012 under the published `normalize_action` fold, 0.698 +/- 0.027 folding "Both" to elevation, **0.598 +/- 0.017** folding "Both" to insurance. 0.583 matches no fold. The only documented statement about a rule-based value is `metrics_definitions.md:195`, "Rule-based PMT is 0.598 for reference" | r8 |
| FQL "84-89 % of actions rejected" | 71.1 % pooled over ten seeds (already flagged in `FQL_BASELINE_NOTE_2026-08-06.md`) | r1 |

## The flood EHE p-value depends on which test you run

The published p = 0.166 for the flood entropy comparison is not a paired test. It
reproduces only as an unpaired two-sample t of the governed arm against the
pre-quarantine no-validator arm. The four cells, all in `r7_seed_robustness.csv` under
`metric = ehe_flood_pooled_simlog_PUBLISHED`:

| no-validator arm | paired (per run index, df 4) | unpaired two-sample (Student, df 8) |
|---|---|---|
| pre-quarantine | p = 0.2947 | **p = 0.1672** (Welch 0.1683) — the published number |
| live | p = 0.0785 | **p = 0.0221** (Welch 0.0224) |

Two things follow, and a reviewer will notice both. The v50 Methods describe
seed-level paired comparisons, so the paired column is the one the stated design
licenses, and the published value is in the unpaired column. And on the live corpus
the verdict itself moves with the test family: paired gives 0.0785 (not significant at
0.05), unpaired gives 0.0221 (significant). Neither is wrong arithmetic; they answer
different questions, and the flood arms are not seed-matched anyway, which is what
makes the choice consequential rather than cosmetic.

## The n = 5 caveat, as a number

An exact two-sided sign-flip permutation test on five paired differences has 2^5 = 32
arrangements, so its smallest attainable p is 2/32 = **0.0625**. No paired n = 5
contrast in this package can be permutation-significant at 0.05, however large the
effect. Every p < 0.05 quoted anywhere is a Student's t p, which buys its extra
resolution with a normality assumption five points cannot test. Both p-values sit
side by side in `r7_seed_robustness.csv`. For the seed-matched flood pairing (n = 3)
the floor is 2/8 = 0.25.

Against that, the effects are unusually clean at the seed level: **every irrigation
metric and every flood IBR variant carries the same sign on every seed** - zero sign
flips. The only sign flip anywhere is flood EHE, which flips on one of five run-index
pairs.

## Proposal vs executed, in one place

| Domain | proposal | executed | do they differ? |
|---|---|---|---|
| irrigation IBR, governed | 36.05 % | 0.86 % | yes, on 39.49 % of rows |
| irrigation IBR, no-validator | 59.07 % | 26.77 % | yes, on 29.04 % of rows |
| irrigation increase rate, governed | 40.90 % | 3.60 % | as above |
| irrigation increase rate, no-validator | 62.52 % | 33.50 % | as above |
| flood IBR, every conditioning | identical | identical | no - flood `proposed_skill` equals `final_skill` on every row, and its rejection rate is 1.07 %, so the remap moves nothing |

`proposed_skill` and `final_skill` are equal on every irrigation row too, except 108
rows across the ten runs where `proposed_skill` is blank. The whole
proposal-vs-executed gap is the REJECTED-to-default remap, not a validator rewriting
a skill name.

## WORLD vs LABEL rules, and the expert-panel rejection-decomposition claim (r10)

Of the six ERROR-level rules the released governed corpus exercises, two condition on
the model's own WSA/ACA label (`low_threat_no_increase`, `high_threat_high_cope_no_increase`
- LABEL) and four condition only on environment state or a skill precondition
(`demand_ceiling_stabilizer`, `demand_floor_stabilizer`, `curtailment_awareness`,
`supply_gap_block_increase` - WORLD); the no-validator arm's sole ERROR id, the literal
`Unknown` precondition text, is the same WORLD family. Restricted to rows whose
`proposed_skill` was an increase and whose `failed_rules` was non-empty (mean 1,274 of
3,276 governed rows/run; 951 of 3,276 no-validator rows/run - **95 %** and **46 %** of
each arm's increase proposals respectively): governed splits WORLD-only 498 / LABEL-only
63 / **both 713** (56 %) / other 0; no-validator is WORLD-only on all 951 (no label rule
can fire without a validator layer).

**The expert-panel rejection decomposition
(`examples/irrigation_abm/analysis/rejection_rate_expert_panel_review.md`,
seed 42, v20 pre-base-fix run) is broadly confirmed on the released v21 seed 42 corpus,
not reproduced exactly** - different code generation, same qualitative picture:

| Rule | Expert-panel doc (v20, seed 42 only) | This package (v21, 5-seed mean, own `failed_rules` on REJECTED rows) |
|---|---|---|
| `demand_ceiling_stabilizer` | 1,420 triggers, ~80 % of rejections | 86.5 % +/- 3.6 (seed 42 alone: 83.3 %) |
| `high_threat_high_cope_no_increase` | 1,180 triggers, ~61 % | 56.7 % +/- 6.4 (seed 42 alone: 56.2 %) |

Both shares are computed the same way here: among rows whose FINAL status starts
`REJECTED`, the % carrying that id anywhere in their OWN `failed_rules` - not `r3`'s
`share_of_rejected_pct`, which divides by the same denominator but also counts rows the
rule blocked on the way to an eventual retry-APPROVED, and so exceeds 100 % for the
busiest rules. **60.7 % +/- 5.7 of governed rejected rows carry more than one distinct
rule id** - this is why the six per-rule shares (86.5 + 56.7 + 26.9 + 10.4 + 9.5 + 3.2 =
193.3 %) do not sum to 100 %, and it is also why the two accounting bounds below are not
additive.

**Bounds, not counterfactual runs** (`out/r10_rule_type_attribution.csv`, `row_type =
block_class`). For a row blocked ONLY by a label rule, bound (a) reads its own
`proposed_skill` as the action instead of the executed remap; bound (b) does the mirror
for a row blocked ONLY by a world rule. A row blocked by both stays at its executed
action in both bounds, because undoing one rule family leaves the other still blocking
it - no retry is re-simulated either way.

| | published (proposal) | executed | bound (a): label rules undone | bound (b): world rules undone |
|---|---|---|---|---|
| governed IBR | 36.05 % | 0.86 % | **3.35 % +/- 0.41** | **1.05 % +/- 0.18** |
| governed increase rate | 40.90 % | 3.60 % | 4.53 % +/- 0.95 | 18.52 % +/- 2.63 |
| no-validator IBR | 59.07 % | 26.77 % | 26.77 % +/- 1.08 (identical - no label rule exists in this arm) | 59.07 % +/- 1.66 (identical - every no-validator block is world-only) |

Both governed bounds land far below the published 36.05 % and close to the 0.86 %
executed figure - removing either rule family alone recovers only a few points of IBR,
because the majority of blocked-and-increase-proposed rows (56 %) are blocked by both
families at once and stay blocked regardless of which single family is undone. The
no-validator row is an internal-consistency check, not a new result: with zero label
rules in that arm, bound (a) collapses to exactly the executed figure and bound (b)
collapses to exactly the published proposal figure, both to 2 decimal places on the
5-seed mean.

**A second, smaller contamination in the same direction:** `failed_rules` unions ids
across every retry ATTEMPT of a decision, and an attempt can change skill TYPE, not
just magnitude - 53-89 of each governed seed's increase-first rows (4-6 %) carry the
decrease-only `demand_floor_stabilizer` id left over from an earlier decrease attempt.
Measured effect on the classification: only 2-5 rows per seed would move from BOTH to
LABEL_ONLY if that alien id were excluded - negligible against the 5-seed means above.

**The first-proposal column.** `initial_skill` (P0-1a,
`broker/tests/test_initial_proposal_columns_p0_1a.py`) is the column that would record
the true first attempt across a governance retry; it is gated OFF by default and
confirmed ABSENT from all ten released audit CSVs. This table falls back to
`proposed_skill`, which is the LAST (post-retry) attempt, not the first - measured
directly on one seed-42 trace (`raw/irrigation_farmer_traces.jsonl`, step 3, agent
"Fort Mohave Ind Res CA", Y1): the row's `proposed_skill` is `increase_small` after one
retry, but `error_messages` shows the blocked FIRST attempt was `increase_large`. Every
count in this table that uses `proposed_skill` as "the first proposal" inherits this
gap; it cannot be closed from the released files (the same absence r9 documents for WSA
labels, here for the skill name).

## Flood, seed-matched at n = 7 for the first time (r11)

Two 2026-09-07 top-up batches, inference settings **matched** to the published
no-validator arm - `JOH_T0-1b_strict_gemma3_4b_e0eee08c_matched/Run_43,44`
(governed) and `JOH_T0-2b_disabled_gemma3_4b_e0eee08c_matched/Run_4202,4203`
(no-validator), both gemma3:4b, code `origin/main e0eee08c` - give flood the same
seven seeds on both arms: `{42, 43, 44, 45, 46, 4202, 4203}`. All four new runs pass
integrity: 1000-row `simulation_log.csv`, `run_integrity.json` `integrity_ok: true`,
manifest seed matches the directory, `config_snapshot.yaml` `governance_profile`
matches the arm (`strict` / `disabled`), and manifest `num_ctx` / `num_predict` /
`thinking_mode` all equal the published no-validator arm's own reference manifest
(`8192` / `4096` / `disabled`, read live, not hardcoded) - the script raises instead
of noting a caveat if any of the three ever drifts. Diffing the new
`config_snapshot.yaml` against a published Group_C snapshot shows the only line ever
REMOVED is `seed: 42`; everything else is a pure ADDITION (`difflib` reports zero
`replace` regions touching the governance-rule text) - three optional response
fields, a disabled `multi_skill` block, a `psychological_framework` field, and two
unused governance profiles `strict_no_etb`/`grounded_v1` with their own nested
`thinking_rules`/`identity_rules`; the active `strict`/`disabled` ruleset itself is
untouched between the two code commits.

| metric (n = 7, seed-matched) | governed | no-validator | gap | p (paired-t) | p (perm, floor 0.0156) | sign flips |
|---|---|---|---|---|---|---|
| IBR unconditional | 0.74 % | 8.03 % | -7.29 pp | 0.00003 | 0.0156 | 0 / 7 |
| IBR, threat != medium | 1.41 % | 15.18 % | -13.77 pp | 0.00001 | 0.0156 | 0 / 7 |
| IBR, threat high | 2.12 % | 22.25 % | -20.13 pp | <0.0001 | 0.0156 | 0 / 7 |
| EHE (simlog, PUBLISHED def.) | 0.861 | 0.801 | +0.060 | 0.084 | 0.0938 | 2 / 7 |
| rejection rate | 0.99 % | 0.00 % | +0.99 pp | 0.024 | 0.0156 | 0 / 7 |
| retry rate | 8.42 % | 0.00 % | +8.42 pp | 0.00039 | 0.0156 | 0 / 7 |

*Unmatched (superseded): the original 2026-09-06 top-up (num_ctx=4096/num_predict=2048/thinking=auto) gave IBR unconditional gap -7.40 pp (p=0.00006), threat-high gap -20.33 pp, EHE +0.043 (p=0.264, not significant) - same signs, same significance pattern, superseded by the matched table above.*

IBR is identical across `proposal` / `final` / `executed` on every one of the 12,728
audit rows checked (14 run instances) - flood's three action levels still coincide
row for row with the matched runs mixed in. The no-validator arm's rejection and
retry rates are exactly 0.00 % on all seven seeds: the validator stack is genuinely
off, not just lenient. Every metric r7 also computed under the old 5-run run-index
pairing moves in the same direction here (e.g. IBR unconditional gap -6.54 pp there
vs -7.29 pp here; IBR threat-high -20.05 pp vs -20.13 pp) - the seed-matched n = 7
pairing sharpens the same picture rather than contradicting it. **No conclusion
changes between the unmatched and matched batches** - every sign, every
significance call (p<0.05 or not) and every ranking is identical; matching the
inference settings moved point estimates by well under 1 pp / 0.02 entropy units.

**Provenance flag, read before trusting the four new seeds as directly comparable to
their pair:** for seeds 43/44 the governed run is on the new commit (`e0eee08c`)
while its no-validator pair is the published run on an older commit (`5a1d467f`) -
the code commit still differs, but `num_ctx` / `num_predict` / `thinking_mode` are
now IDENTICAL on both sides (`8192`/`4096`/`disabled`), closing the inference-setting
gap the unmatched batch left open. Mirrored for seeds 4202/4203, where the
no-validator side is new (same matched settings) and the governed side is the old
published Group_C run, whose manifest schema is old enough that it never recorded
`git_commit`, `num_ctx`, `num_predict` or `thinking_mode` at all -
`ABSENT_FROM_MANIFEST`, unconfirmable from disk, unchanged from before. Model
identity (`gemma3`, `4.3B`, `Q4_K_M`, same weight digest) and `python_version`
(3.14.0) are identical everywhere both sides record them.

**Sensitivity: matched vs unmatched, same seed and same arm.** Comparing each new
seed's matched run against its own unmatched run (same seed, same arm, same code
commit - isolates `num_ctx`/`num_predict`/`thinking_mode` alone):

| seed | arm | IBR uncond | IBR threat != medium | EHE | rejection rate | retry rate |
|---|---|---|---|---|---|---|
| 43 | governed | 0.44 % vs 0.11 % | 0.97 % vs 0.23 % | 0.832 vs 0.806 | 0.66 % vs 0.34 % | 8.11 % vs 5.86 % |
| 44 | governed | 0.40 % vs 0.94 % | 0.86 % vs 1.97 % | 0.887 vs 0.855 | 0.94 % vs 0.94 % | 9.03 % vs 8.70 % |
| 4202 | no-validator | 8.47 % vs 9.56 % | 15.98 % vs 17.26 % | 0.822 vs 0.841 | 0.00 % vs 0.00 % | 0.00 % vs 0.00 % |
| 4203 | no-validator | 10.65 % vs 10.59 % | 19.17 % vs 19.74 % | 0.853 vs 0.898 | 0.00 % vs 0.00 % | 0.00 % vs 0.00 % |

(each cell reads matched vs unmatched). The largest single-seed move is retry rate
on seed 43 (+2.25 pp); every IBR move is under 1.3 pp - an order of magnitude below
the 7-20 pp governed-vs-no-validator gap above, and no seed's sign flips relative to
its own arm.


## Vaccination T0-4: a new domain, and a decision-mapping anomaly (r12)

> **SUPERSEDED 2026-09-09.** This section describes the pre-fix `e0eee08c` runs,
> since REJECTED: the `raw_output` decision digit was mis-decoded because
> `Available actions:` never rendered a menu into the prompt - it prints the
> literal string `[N/A]` on **every row, every year, all three seeds** (not
> just years 2-10, which is as far as this section's own cross-check reached).
> Kept below as the historical record of what that mis-decode looked like from
> inside the run; do not cite these numbers as current. **Current numbers are in
> "Vaccination T0-4b" below** (options-text-parity fix, commit `88c21542`,
> script `r12b`).

First reviewer-prep pass over the new vaccination domain (HBM framework, gemma3:4b,
strict governance profile, 100 agents x 10 years, seeds 42/43/44, code
`origin/main e0eee08c`). These runs live outside this repo, in a sibling checkout
(`wagf-main-runs`); `r12`'s docstring records why. `k = 3` skills
(`get_vaccinated` / `delay` / `refuse`, `skill_registry.yaml`), 5 HBM thinking-rules (2
ERROR, 3 WARNING).

**Pre-registered acceptance (plan Sec 3), all three seeds:**

| criterion | seed 42 | seed 43 | seed 44 |
|---|---|---|---|
| run completes (1000/1000 rows) | PASS | PASS | PASS |
| rejection rate | 0.0 % | 0.0 % | 0.0 % |
| retry rate | 0.0 % | 0.0 % | 0.1 % |
| >= 1 HBM rule fires | PASS (WARNING only) | PASS (WARNING only) | PASS (WARNING + 1 ERROR block) |
| `run_integrity.json` clean | PASS, no flags | PASS, no flags | PASS, no flags |
| traces committed only if clean | N/A_by_design - integrity is clean but nothing is committed anywhere (gitignored in both checkouts); not yet promoted to a released corpus | same | same |

No REJECTED row exists anywhere in the three runs - the `strict` profile never
fell back to the registry default (`delay`) once. `ehe_vaccination` (pooled once,
executed action, k = 3): **0.8247 / 0.7896 / 0.7545** (seeds 42/43/44). Executed action
shares: get_vaccinated 59.6-64.4 %, delay 28.4-29.9 %, refuse 7.1-10.5 %.

**Rule census, 3-seed means.** Two WARNING rules do essentially all the recorded
governance activity: `low_susceptibility_no_get_vaccinated` (seen 4.3 decisions/seed)
and `low_severity_low_benefits_get_vaccinated` (seen 3.3/seed, absent entirely from
seed 44). One ERROR rule, `high_cues_low_barriers_refuse_inconsistent`, blocks exactly
once across all three seeds (seed 44, one decision, retried twice, `fire_count = 2`
in `validator_health.csv` vs `rule_frequency = 3` in that seed's own
`governance_summary.json` - the two counters disagree by one for the same single
decision's retry loop; not reconciled here). `high_susceptibility_high_severity_high_efficacy_no_refuse`
(the second ERROR rule) never fires in any of the three seeds.

**The "DEAD VALIDATOR" log line.** `[Audit] DEAD VALIDATOR: rule
'low_susceptibility_no_get_vaccinated' never fired across 3 decisions` (seed 44's
main run, NOT the 25x3 smoke run - `smoke.log` has zero such lines) is printed by
`broker/components/analytics/audit.py` for any rule with `seen_count > 0` and
`fire_count == 0`. A WARNING-level rule can never set `fire_count` (only ERROR-level
blocking does) - by construction, every WARNING rule that is ever evaluated gets this
line, whether or not it is actually inert. It is measuring "never blocked", worded as
"never fired". Both HBM WARNING rules get this line in all three seeds.

**Anomaly found while building this table (not in the brief):** every row's
`raw_output` parses cleanly as its own JSON object (`parse_layer` = `enclosure+json`
on 100.0 % of rows, all three seeds - zero fallback anywhere in this batch), with an
explicit `"decision"` field. Cross-checking that field against the audited
`proposed_skill`: **0.0 % disagree in year 1**, but **49-88 % disagree per year in
years 2-10** (not a fixed off-by-one - `"decision": "1"` maps to `get_vaccinated`
233 times, `delay` 152 times and `refuse` 9 times within seed 42 alone). Ruled out as
a stale/cached `raw_output`: verified byte-distinct (sha1) and independently timestamped
across all 10 years for a sample agent, and cross-checked against the raw JSONL trace
(not just the CSV) for one case with `retry_count = 0` (single LLM call, no retry-loop
ambiguity). `run_integrity.json` does not see this at all - it only tracks which
parse layer succeeded, never whether the extracted field matches the recorded skill.
Root cause not identified in this pass. Construct labels (the six VL/L/M/H/VH
appraisal columns) are unaffected - 0.0 % unparsed everywhere, all three seeds -
only the decision-to-skill mapping is implicated. **Practical effect: the year 1
action distribution in this batch is trustworthy; the years 2-10 action distribution,
and anything downstream of it (the executed shares and `ehe_vaccination` above),
is not verified against the model's own stated choice.**

One more distributional note: `construct_BENEFITS_LABEL`, `_CUES_TO_ACTION_LABEL`,
`_SELF_EFFICACY_LABEL` and `_SUSCEPTIBILITY_LABEL` never once emit `VH` in any of the
three seeds (`construct_BARRIERS_LABEL` does, rarely) - not a parser truncation (the
regex accepts all five codes and 0.0 % of rows fall outside the alphabet), just an
observed ceiling in what the model actually writes for those four constructs.


## Vaccination T0-4b: options-text-parity fix rerun (r12b, current)

Rerun of the same domain/config on the options-text-parity fix (commit `88c21542`),
same 3 seeds, same 100 agents x 10 years, gemma3:4b, `strict` profile, actual
inference settings `num_ctx=4096 / num_predict=1024` on both this arm and the
superseded arm above (`SETTINGS_NOTE.md` in the run directory - the
`reproducibility_manifest.json` value of 16384/-1 is confirmed wrong/unused on
both arms, so the two are settings-matched). Runs now live in this repo:
`examples/vaccination_demo/results/JOH_T0-4b_gemma3_4b_88c21542/Run_{42,43,44}`.
New, independent script `r12b_vaccination_t04b.py` (does not touch
`r12_vaccination_t04.py`; does not require `validator_health.csv` - see below);
`--old-arm` reruns the identical three tables against the superseded `e0eee08c`
runs for a reproducible side-by-side.

**Parity - the fix verified directly, not by proxy.** For every one of 3000 rows
(3 seeds x 1000), decoded the digit in `raw_output`'s own `"decision"` field
against the literal `Available actions:` menu rendered into *that row's own
prompt* (`raw/individual_traces.jsonl`), joined on `step_id`, and compared to the
audited `proposed_skill`: **3000/3000 match, 100.00 %, every year, every seed**
(seed 42 1000/1000, seed 43 1000/1000, seed 44 1000/1000). Zero rows on this arm
render `[N/A]` for the menu - contrast the superseded arm above, which renders
`[N/A]` on all 3000/3000 rows (not just years 2-10).

**Governance sanity, all three seeds.** `run_integrity.json`: `integrity_ok = true`,
zero anomaly counters, all three seeds. `individual_governance_audit.csv`:
`status = APPROVED` on all 3000 rows (0 REJECTED), `retry_count = 0` on all 3000
rows, `proposed_skill == final_skill` on every row (0 remaps). **`failed_rules`
and `warning_rules` are both empty on all 3000 rows, all three seeds - the
pre-registered "≥1 HBM rule fires" acceptance check now FAILS**, where it PASSED
(WARNING-only) on the superseded arm. Checked directly against the 5 rules' own
preconditions (label AND action together, not label alone): 0/1000 rows on any
seed satisfy any of the 5 preconditions - the labels themselves still occur at
rates comparable to the superseded arm (`VL`/`VH` did not vanish), only the
specific (label, action) combination the rules key on does not co-occur in this
batch.

**The validator is confirmed live, not a dead code path.** A direct
positive-control test (`out/r12_rerun_2026-09-09/validator_liveness_2026-09-09.md`)
constructs the same `AgentValidator` class from the same YAML the run used, feeds
it one real audit row unmodified (0 fires, as expected) and two synthetic
mutations engineered to satisfy a WARNING and an ERROR rule's precondition
respectively - both fire correctly, through both the direct
`validate_thinking()` call and the full `validate(proposal, context, registry)`
engine entry point `skill_broker_engine.py` actually calls in production. No
counter in the audit schema itself can make this distinction (see
`out/r12_rerun_2026-09-09/r12_rerun_zero_fires_2026-09-09.md` sections 2-3 for
why), so the positive-control test is the actual evidence, not the absence of
fires.

**Uptake, 3-seed mean +/- sd (n = 3, sample sd).** Final (year-10) cumulative
uptake: seed 42 = 50.0 %, seed 43 = 56.0 %, seed 44 = 64.0 %, **mean 56.7 +/- 7.0
pp**. Annual (per-year, not cumulative) uptake mean +/- sd: Y1 37.0+/-5.3, Y2
46.7+/-4.2, Y3 21.3+/-6.1 (a real dip, all three seeds), Y4 46.3+/-7.6, Y5
49.3+/-7.1, Y6 50.7+/-8.6, Y7 52.7+/-7.0, Y8 52.3+/-8.1, Y9 52.7+/-7.6, Y10
52.7+/-7.6.

**Superseded arm's rule fires, re-examined.** The pre-fix arm's 20 rule-fire
instances (across the 2 WARNING + 1 ERROR rules that ever fired there) were
cross-checked against the same digit-vs-legend decode: **17/20 fire instances
occur on rows whose own digit (legend-decoded: 1=get_vaccinated / 2=delay /
3=refuse) disagrees with the recorded `proposed_skill`** - i.e. those 17 rule
fires most likely fired against a corrupted action label, not the model's actual
stated choice. Only 3/20 fire instances occur on a row where the digit and the
recorded label agree.

**Framing.** This domain now demonstrates the DomainPack plug working correctly -
parity, audit-trail integrity, and a live, correctly-wired validator - not a
governance effect. Nothing in this batch shows the 5 HBM rules changing an
outcome; zero of them ever had a matching precondition to act on. That is a fact
about this batch's (label, action) distribution, established directly, not a
framework defect.

**Output:** `out/r12b_vaccination_parity.csv`, `out/r12b_vaccination_governance.csv`,
`out/r12b_vaccination_uptake.csv` (`arm` column distinguishes `NEW_88c21542` /
`REJECTED_e0eee08c` - each written by a separate invocation, `--old-arm` for the
latter); `out/r12_rerun_2026-09-09/` (interim parity/governance/outcome recheck,
the zero-fires investigation, and the validator-liveness positive-control test).

---

## Reservoir control T0-6: a TOY capability demo, and two instrumentation gaps (r13)

**TOY, not a paper result.** One OPERATOR agent, one annual release-setting decision,
against a synthetic mass-balance reservoir (`ToyMassBalanceReservoir`, 12 monthly
sub-steps/year, 42 years, gemma3:4b, `strict` governance, seeds 42/43/44, code
`origin/main e0eee08c`). Not a calibrated basin, not USBR/CRSS data, not
multi-agent - built to exercise exactly one hard rule (`dead_pool_violation`) via a
scripted 2-year drought tail wrapped modulo-4 over 42 years. Lives outside this repo
in the sibling `wagf-main-runs` checkout; `r13`'s docstring records why.

| seed | rows | REJECTED | dead_pool_violation fire/seen | retry-then-approved | storage min/max/final (maf) | shortfall total (maf) |
|---|---|---|---|---|---|---|
| 42 | 42/42, integrity clean | 15 (35.7 %) | 30/30 | 0 | 2.474 / 17.276 / 8.094 | 129.15 |
| 43 | 42/42, integrity clean | 11 (26.2 %) | 23/23 | 1 (year 11) | 3.022 / 17.276 / 8.554 | 131.49 |
| 44 | 42/42, integrity clean | 9 (21.4 %) | 19/19 | 1 (year 26) | 4.072 / 17.276 / 8.139 | 133.20 |

Spill is 0.000 maf in all three seeds - the solver never fills toward capacity, so
the second registered rule (`flood_control_overflow`) never once evaluates (storage
tops out at 17.276 maf against a 0.9x24.0=21.6 maf trigger, every seed). `set_release`
is proposed on 42/42 decisions every seed; `maintain_release` is never chosen, not
even after a rejection. Proposed magnitudes cluster at 60/65/67/68/70 %(/75 % once,
seed 44) - the model does not retreat below 60 % even on the retry that fails again.
The "wall -> retry -> resolves" pattern `ops_modules.py`'s design docstring is built
around happens twice in the batch (seed 43 year 11, seed 44 year 26); the other 24 of
26 `retry_count=1` rows stay REJECTED after the retry.

**Release-target parity - does the agent's choice actually drive the solver? Yes,
exactly, in both directions.** All 91 APPROVED rows across the three seeds
(27+31+33): `world_release_target == magnitude_pct/100 * 0.75`, float-exact (1e-9
tolerance), **0 mismatches**. All 35 REJECTED rows (15+11+9): `world_release_target`
equals the last APPROVED (or initial 0.75 maf/month) committed target -
`ReservoirOpsBundle.commit_world_delta` silently reuses `_last_release_target` when
the approved skill carries no `magnitude_pct` - **0 mismatches**. The coupling is
airtight: an approved choice sets the solver input precisely; a rejected one provably
does not touch it.

**Two odd findings, found while building this table, neither visible from
`run_integrity.json` (which reports `integrity_ok=True` for all three seeds):**
1. `governance_summary.json`'s `total_interventions` reads **0** in every seed, while
   `audit_summary.json`'s `validator_health` and the audit CSV itself correctly
   record 30/23/19 `dead_pool_violation` fires. `GovernanceAuditor.log_intervention()`
   (`broker/utils/governance_auditor.py`) is evidently never called on this
   domain-physical-validator dispatch path - the audit trail is right, the legacy
   summary counter is not.
2. The audit CSV's `fallback_activated` column reads `False` on all 126 rows across
   all three seeds, including all 35 REJECTED rows, even though the parity check
   above proves a REJECTED decision demonstrably reverts to the prior committed
   setpoint. The column simply does not track this domain's
   REJECTED-retains-prior-setpoint behaviour - it is a labeling gap in the audit
   schema, not a physics or governance-enforcement error (the enforcement itself,
   per the parity check, is exact).

**Coupling evidence.** The brief asked for `coupling_contract_active` /
`coupling_guard_calls`; neither key exists in `run_integrity.json` schema 2. What
does exist, identical across all three seeds: `run_integrity.json`
`coupling_adapter=True`, `sim_engine_class=EnvironmentCouplingAdapter`;
`reproducibility_manifest.json`'s `coupling_provenance` block
(`adapter_class=EnvironmentCouplingAdapter`, `bundle_class=ReservoirOpsBundle`,
`solver_class=ToyMassBalanceReservoir`, `substeps_per_decision=12`, plus a
`contract_sha256`).


## Irrigation advise arm: does telling the model change the proposal? (r14)

**Tier-1, T1-2, FINAL n = 5 (2026-09-10; supersedes the n = 3 interim look of
2026-09-07/08).** `strict` profile + `governance.advise_mode: feedback`
(gemma3:4b, 78 agents x 42 years, code `e0eee08c`),
`examples/irrigation_abm/results/advise_feedback_42yr_gemma3_4b_e0eee08c_seed{42,43,44,45,46}`.
Per `docs/guides/governance_layers.md` (Section 1, read via
`git show origin/main:docs/guides/governance_layers.md` - this branch's tree does
not carry the doc), `feedback` mode issues one extra, non-blocking LLM call whenever
an otherwise-APPROVED decision triggers a WARNING-level rule, and the decision's
`status` is exactly what it would have been with the channel off. The
`..._seed46_PARTIAL_killed_2026-09-08` directory (the killed-and-restarted first
attempt at seed 46) is excluded entirely - not read, not counted as incomplete -
by the discovery fix described in `out/r14_advise_final_n5_2026-09-10.md`. Full
statistics, exact commands and the interim-vs-final walkthrough live in that file;
this section restates only the numbers a reader of this summary needs.

**Integrity: clean on all 5.** 3276/3276 audit rows on every seed;
`run_integrity.json` `integrity_ok=True`/`audit_rows=3276`;
`reproducibility_manifest.json` `git_commit=e0eee08c141b16cc0c683a0cfc43d36bad451da5`/
`num_ctx=8192`/`num_predict=4096`/`config_hash=62d2eeb2373e` identical on all 5
advise seeds; `soft_advise_mode` reads `"feedback"` on all 3276 rows of every
seed, no exceptions.

**Who got advised, and about what, per seed.** Every finding shown is
WARNING-level on all 5 seeds, matching `governance_layers.md`'s layer-2 table - no
new rule id appears:

| rule id (category:name) | seed 42 | seed 43 | seed 44 | seed 45 | seed 46 |
|---|---|---|---|---|---|
| `thinking:high_threat_no_maintain` | 99 | 65 | 87 | 87 | 108 |
| `institutional:curtailment_awareness` | 37 | 40 | 35 | 38 | 31 |
| `physical:curtailment_awareness` | 14 | 9 | 12 | 13 | 0 |
| `physical:non_negative_diversion` | 1 | 2 | 0 | 2 | 1 |

(A row can carry more than one finding.) Advised rows are 4.61 %, 3.54 %, 4.09 %,
4.27 %, 4.27 % of the 3276-row run - **mean 4.16 % +/- 0.39 % sd** (n=3 interim:
4.08 % +/- 0.53 %).

**Uptake = mean 16.12 % +/- 2.02 % sd across seeds** (25/151 = 16.56 %,
17/116 = 14.66 %, 25/134 = 18.66 %, 19/140 = 13.57 %, 24/140 = 17.14 %),
denominator = advised rows on each seed, per the pre-registration - never the
run's 3276. Treated as a one-sample test against 0 (there is no strict-arm
counterpart): t = 17.85, df = 4, p = 0.0001, exact sign-flip permutation
p = 0.0625 (the n=5 floor). **Uptake > 0 (H-a): HOLDS, consistent positive on
5/5 seeds, no exceptions** (n=3 interim: 16.62 % +/- 2.00 %, also 3/3). Direction
is mixed on every seed, not one-way:

| seed | before -> after (all changes) |
|---|---|
| 42 | `increase_small->maintain_demand` 7, `maintain_demand->increase_large` 7, `increase_small->increase_large` 5, `increase_large->increase_small` 3, `maintain_demand->increase_small` 2, `maintain_demand->decrease_small` 1 |
| 43 | `increase_small->increase_large` 5, `increase_small->maintain_demand` 5, `maintain_demand->increase_large` 3, `maintain_demand->increase_small` 2, `decrease_small->increase_large` 1, `maintain_demand->decrease_small` 1 |
| 44 | `increase_small->increase_large` 8, `maintain_demand->increase_small` 8, `maintain_demand->increase_large` 7, `increase_large->increase_small` 1, `increase_small->maintain_demand` 1 |
| 45 | `increase_small->increase_large` 9, `maintain_demand->increase_large` 6, `maintain_demand->increase_small` 2, `increase_large->increase_small` 1, `maintain_demand->decrease_small` 1 |
| 46 | `maintain_demand->increase_large` 10, `maintain_demand->increase_small` 7, `increase_small->increase_large` 4, `decrease_small->maintain_demand` 1, `increase_small->maintain_demand` 1, `maintain_demand->decrease_small` 1 |

On every seed, changes toward MORE demand and changes toward LESS demand both occur
in comparable numbers. Reading uptake as "the model listened and backed off" does
not survive any of the 5 seeds.

**The post-advice proposal is discarded, not always kept - and this share is
noisy.** `advise_post_validation_invalid` is 13.25 % (seed 42), 15.52 % (seed 43),
21.64 % (seed 44), 22.14 % (seed 45), 17.14 % (seed 46) of advised rows - **mean
17.94 % +/- 3.87 % sd**. Those rows execute the PRE-advice proposal
(`advise_executed_stage=pre`: 24/151, 22/116, 33/134, 34/140, 29/140; `post` on
the rest). `advise_parse_failed` stays low on all 5 (2.65 %, 3.45 %, 2.99 %,
2.14 %, 3.57 % - mean 2.96 % +/- 0.59 %). `soft_findings_unidentified` is 0 on
every row of every seed - no advisory finding ever went un-named.

**Rejection rate: higher on advise than strict on 4/5 seeds - seed 46 breaks the
n = 3 interim's clean run.**

| seed | rejected_to_fallback advise % | rejected_to_fallback strict % | diff pp |
|---|---|---|---|
| 42 | 42.28 | 38.68 | +3.60 |
| 43 | 39.53 | 36.36 | +3.17 |
| 44 | 38.98 | 37.21 | +1.77 |
| 45 | 40.35 | 37.64 | +2.72 |
| 46 | 42.98 | **47.59** | **-4.61** |
| **mean +/- sd** | **40.82 +/- 1.74** | **39.49 +/- 4.60** | **+1.33 +/- 3.39** |

Paired t (df = 4): t = 0.88, p = 0.43. 95 % CI on the diff: [-2.88, +5.54] pp -
includes 0. Exact sign-flip permutation p = 4/32 = 0.4375 (4 of 5 diffs positive,
1 negative - **not** the n=5 floor of 0.0625, because the signs are no longer
unanimous). The seed-46 flip is a **strict-arm** anomaly, not an advise-arm one:
`production_v21_42yr_seed46`'s own numbers are the outlier against its four
seed-mates (mead_min 964.0 ft vs 994-998 ft; approved_first_attempt 29.67 % vs
36-39 %; rejected_to_fallback 47.59 % vs 36-38 %) - see the caveat section of
`out/r14_advise_final_n5_2026-09-10.md` for the manifest evidence that this
strict seed also sits on its own distinct code commit. `approved_first_attempt`
and `approved_after_retry` (not part of the pre-registered metric list, reported
for completeness) show the same seed-46-driven break: `approved_after_retry` is
lower on advise on all 5 seeds (consistent), but `approved_first_attempt` flips
sign on seed 46 for the same reason as rejected_to_fallback.

**Headline metrics, proposal + executed level, FINAL n = 5** (`_loader.ibr` /
`_loader.increase_rate` on `simulation_log.yearly_decision`; EHE pooled once,
H/log2(5)):

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
| strict | mead_min ft | 997.62 | 994.36 | 996.97 | 996.03 | **964.01** | 989.80 +/- 14.47 |
| advise_feedback | shortage years | 15 | 13 | 12 | 13 | 15 | 13.60 +/- 1.34 |
| strict | shortage years | 14 | 17 | 15 | 12 | 16 | 14.80 +/- 1.92 |

All 5 seeds' `first_dead_pool_year` reads "none" on both advise and strict (never
reached, even strict seed 46's 964.0 ft low); no_validator hits dead pool on
every seed it was checked against in the n=3 look (years 17, 17, 18).

Paired t (df = 4), advise-minus-strict, with the exact n = 5 permutation p stated
alongside every t-test p (floor = 2/32 = 0.0625 when all 5 diffs share a sign) and
a 95 % CI on the mean difference (stdlib bisection against the same Student-t CDF
`_loader.py` already uses - see `r14_advise_stats_n5.csv`):

| metric | mean diff | 95% CI | paired t | t-test p (df=4) | exact permutation p | direction |
|---|---|---|---|---|---|---|
| IBR % proposal | +3.58 pp | [+0.94, +6.22] | 3.76 | 0.020 | 0.1250 | seed 44 flips sign |
| IBR % executed | -0.01 pp | [-0.54, +0.53] | -0.03 | 0.976 | 1.0000 | seeds 45/46 flip sign |
| increase_rate % proposal | +0.71 pp | [-3.62, +5.03] | 0.45 | 0.673 | 0.6875 | seeds 44/46 flip sign |
| EHE pooled (proposal) | -0.0153 | [-0.0782, +0.0477] | -0.67 | 0.538 | 0.5625 | seeds 44/46 flip sign |
| mead_min ft | +5.98 ft | [-12.39, +24.36] | 0.90 | 0.417 | 0.7500 | seeds 42/44/45 flip sign |
| shortage years | -1.20 | [-4.03, +1.63] | -1.18 | 0.305 | 0.4375 | seeds 43/44/46 flip sign |

**No metric except uptake clears the n=5 permutation floor.** The interim's
cleanest-looking result (IBR % proposal, floor 0.125 at n=3 with all 3 diffs
positive) stays directionally positive at n=5 (4 of 5 seeds, seed 44 the lone
flip, unchanged from the n=3 reading) and is now the only paired metric with a
t-test p under 0.05 (0.020) and a 95 % CI excluding 0 - but its exact permutation
p (0.125) still cannot certify significance below its own floor.

The per-year increase_rate trajectory (`out/r14_advise_yearly.csv`, 42 years x 5
seeds = 210 rows) keeps the same shape on seeds 42-45 as the n=3 look: advise
above strict more years than below. Seed 46 is the outlier year-by-year too,
tracking its anomalous strict reference rather than the other 4 strict seeds.

**What holds and what doesn't, FINAL n = 5 (pre-registered hypotheses).**
- **Uptake > 0 (H-a): HOLDS.** Consistent positive on 5/5 seeds, 13.57-18.66 %
  (mean 16.12 % +/- 2.02 %), exact permutation p at its n=5 floor (0.0625) -
  the strongest-possible exact-test result this design can produce. Direction of
  the changed proposals still mixes MORE-demand and LESS-demand changes on every
  seed, so "the model backs off when warned" remains not what uptake shows.
- **rejected_to_fallback ~= strict (H-b): NOT SETTLED, and n=5 makes the call
  harder, not easier.** The n=3 interim's "same direction on 3/3" was itself
  sitting on a permutation floor that could not distinguish "true small effect"
  from "3 lucky draws." At n=5 the direction is no longer unanimous - seed 46
  flips it - and the flip traces to the **strict reference arm**, not the advise
  arm: `production_v21_42yr_seed46` is an outlier against its own four
  seed-mates on every metric in the table above (mead_min, approved_first_attempt,
  rejected_to_fallback, increase_rate, IBR-proposal all sit outside the range set
  by seeds 42/43/44/45). Whether that is ordinary gemma3:4b run-to-run
  non-determinism (project memory already documents this class of finding) or a
  genuine outlier run cannot be resolved from analysis alone - it needs either a
  spot-check of seed 46's raw JSONL or a 6th strict seed, neither done here.
  `production_v21_42yr_seed{N}` / `ungoverned_v21_42yr_seed{N}` remain separate
  real-LLM runs on a DIFFERENT git commit than the advise arm's `e0eee08c` for
  every seed (three distinct commits recorded across seeds 42/43/44 alone -
  `d8a5da41`/`db05d3a2`/`708d34f1` - and no commit recorded at all in the sparser
  seed-45/46 manifests) - not a byte-identical rerun with only `advise_mode`
  flipped, at n=3 or at n=5.
- The IBR-proposal gap (advise above strict) is the one paired metric that stays
  directionally strong at n=5 (4/5 seeds positive, only seed 44 flips, unchanged
  from n=3) and is the only metric with t-test p < 0.05 - but the exact
  permutation p (0.125) is still short of what n=5 needs to certify it.
- EHE, increase_rate-proposal, mead_min and shortage_years all show 2-3 sign
  flips out of 5 at final n - none resolves in either direction. This is a
  strictly less certain picture than the n=3 interim implied for
  increase_rate-proposal and mead_min (which had 1 flip each at n=3, matching
  their n=5 pattern) but EHE and shortage_years both go from "small, weak" at
  n=3 to "no consistent direction, 2-3 of 5 flipped" at n=5 - more data changed
  the read, not just tightened it.
- Full manifest cross-check (commit / model digest / num_ctx / num_predict /
  advise_mode, both arms, all 5 seeds each) and exact reproduction commands live
  in `out/r14_advise_final_n5_2026-09-10.md`.

**Output:** `out/r14_advise_arm.csv` (15 rows: one per arm x seed for 5 seeds x 3
arms; advice-only columns are `N/A_by_design` on the two reference arms),
`out/r14_advise_findings.csv` (46 rows: rule ids and before->after directions per
seed), `out/r14_advise_yearly.csv` (210 rows: per-year increase_rate, advise vs
strict, 42 years x 5 seeds), `out/r14_advise_stats_n5.csv` (8 rows: one per
pre-registered metric, with mean +/- sd per arm, the paired/one-sample 95 % CI,
paired-t p, exact permutation p and the direction-consistency call - new in the
2026-09-10 n=5 extension, replacing the 3 `advise_MINUS_strict_paired_t` summary
rows the n=3 script used to smuggle into `r14_advise_arm.csv`'s column union).

## Vintage-of-code prompt/memory length check, and a reflection bug it found (r16)

A reviewer flagged a backfilled irrigation run
(`ungoverned_v21_42yr_ministral3_8b_seed44`, Aug 2026) with a much shorter injected
-memory column than its March arm-mates - a prompt-rendering CODE difference,
invisible to a config-snapshot diff. r16 checks 33 runs (all of flood governed/
no-validator/quarantine/Sept-matched, all of irrigation gemma governed/ungoverned,
all six ministral runs) for the same thing.

**The memory column, named.** No audit CSV carries rendered memory text as its own
column. It lives inside the raw JSONL `input` field, after the literal line `Your
memory includes:` up to the next blank line - matched on 100% of sampled rows across
every vintage.

**Only 1 of 33 runs flagged** (mean memory or prompt more than 30% from its arm's
median): `ungoverned_v21_42yr_ministral3_8b_seed44`, memory mean 194.6 chars vs its
March arm-mates' 575.9 / 628.6 chars (-66% / -69%).

**Root cause, found chasing the number: a reflection-write bug, not a shorter
template.** The `memory_pre` field's own item schema changed across vintages (March:
plain strings; April+ and the Aug backfill: `{"content": ..., ...}` dicts). In the
flagged run, the `"Consolidated Reflection: ..."` memory item is truncated to the
literal 27-character string `"Consolidated Reflection: {"` on 3,106/3,198 rows with
memory (85.5%). The same truncation exists at a low background rate elsewhere (0.1
-0.4% in gemma irrigation, 7.2-9.9% in the OTHER ministral runs) - ministral-3:8b's
own output style turns an occasional bug into a near-universal one in this run,
which plausibly explains the reviewer's number on its own.

**A second, separate artifact: `raw_output` length depends on which file you read.**
The raw jsonl's `raw_output` field is hard-capped at exactly 500 chars + the literal
suffix `"...[truncated]"` (514 total) on 99.8-100% of rows in every Feb-May-vintage
run (flood and irrigation, gemma and ministral alike); the Aug backfill and the Sept
T0-1b/T0-2b top-up do not truncate it. The audit CSV's OWN `raw_output` column is
never truncated in any vintage (spot-check: 775 chars there vs 514 in the jsonl for
the same row). Read from the CSV - the vintage-stable source, and what this table
reports - `raw_output` is flat across vintage within each domain (flood 783-834
chars; irrigation gemma 859-885; irrigation ministral 1,032-1,101): the 514-vs-800+
split visible in the raw jsonl field is a debug-trace truncation policy that
changed, not a real difference in model verbosity.

**Flood live no-validator arm: comparable on everything except memory.**
`JOH_ABLATION_DISABLED/.../Run_1-3` (May 2026 backfill) mean memory 1,068.9 chars
(avg of the three) vs `Run_4-5` (Feb) 889.0 - **+20.2%** - and vs governed `Group_C`
(Feb) 894.8 - **+19.5%**; `Run_4-5` itself sits within 0.6% of governed. Full prompt
length moves much less (`Run_1-3` avg 3,706.0 vs `Run_4-5` avg 3,526.2, +5.1%), and
CSV `raw_output` barely moves (820.6-834.1 across all five runs). Neither sub-group
alone crosses the 30% flag against the arm's own blended median, but the gap is real
and specific to memory content: `Run_1-3` and `Run_4-5` are not interchangeable in
what the model actually read as memory, though `config_snapshot.yaml` shows them as
one arm.

**Today's Sept T0-1b/T0-2b matched top-up is closer to the published corpus than
the May backfill is to its own arm-mates.** Governed `Run_43,44` mean memory 809.1
vs published `Group_C` 894.8 (-9.6%); no-validator `Run_4202,4203` mean memory 788.0
vs published `Run_4-5` 889.0 (-11.4%) - both comfortably under the 30% bar, with
`raw_output` matching closely too (789-797 vs 780-834 published).

**Horizon controlled for.** Memory grows several-fold within a single run's own
years (flood `Group_C Run_1`: year-1 mean 393 chars -> year-10 mean 1,052;
irrigation governed seed42: year-1 mean 16 chars, literally `"No memories yet."`, ->
year-42 mean 444) - larger than any cross-run gap above. Every comparison above
pairs runs of the SAME length (10 years for flood, 42 for irrigation), so none of
the reported gaps can be a horizon artifact in disguise.

**Output:** `out/r16_vintage_prompt_check.csv` (one row per run + one row per arm
summary), `out/r16_vintage_prompt_check_by_year.csv` (one row per run x year).
