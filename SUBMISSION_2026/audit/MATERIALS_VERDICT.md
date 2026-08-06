# MATERIALS VERDICT — SUBMISSION_2026 workshop paper

**Synthesis lane.** Inputs: lane A (data selection), lane B (run integrity), lane C (framework
semantics), lane D (claim traceability), plus independent checks run in this lane.
Repo HEAD `10e190cf`. Written 2026-07-30.

---

## 1. Verdict

> **SOUND AFTER 6 SPECIFIC FIXES — but fix #1 is not a fix, it is a reframe, and it changes the paper.**

**The corpus is fine. The claim is not.** All 131 runs in the 14 cells are row-complete with zero
gaps (lane B), the two good analysis scripts select cleanly (lane A), and the per-cell table
reproduces exactly through three independent code paths (lane D, and again in this lane). Nothing
needs to be re-run on a GPU.

The one fact that decides it: **at simulation year 1 — the only stratum where the two arms provably
face an identical world — the appraisal shift is gone.** High-regime mean **−0.58 pp**
(range −8.97 … +4.36) against a full-run mean of **+38.13 pp**, and the regime separation is
**BROKEN**. This holds even though the governed arm retried **68–88 %** of its year-1 decisions, so
enforcement was at full intensity and the recorded appraisal is the post-retry one.

The +38 pp is not the agent revising its premise under enforcement. It is 42 years of accumulated
divergence in a coupled reservoir. The repo's own `evidence/exogeneity_check.py` already documents
the channel: Lake Mead ends up **102 ft higher** in the governed arm, shortage tier **1.84 tiers
lower**, and every hydrology column is classified `DRIFTS — SAFE ONLY AT YEAR 1` with
`year1_exact_equal_rate = 1.0` and `first_year_with_any_disagreement = 2`.

So the measurement critique **survives and gets stronger** (the conditioning variable is
post-treatment through a fully traceable causal channel, which the paper can now prove rather than
speculate). The mechanism claim in the title and abstract **does not survive**.

---

## 2. Does the headline finding survive?

**The regime separation survives every data-hygiene regime and fails the one causal stratification.**

| stratification | cells | high mean | low mean | min high vs max low | separation |
|---|---|---|---|---|---|
| as published (all 14) | 14 (5/9) | +38.13 | +0.56 | +21.26 vs +6.25 | **COMPLETE** (+15.01) |
| shared seeds only (lane D R1) | 14 | +37.75 | +0.67 | +21.26 vs +6.25 | **COMPLETE** (+15.01) |
| **balanced cells only (lane D R2)** | **7 (4/3)** | **+39.42** | **+3.38** | +21.26 vs +6.25 | **COMPLETE** (+15.01) |
| balanced + attrition-matched (lane D R3) | 7 (4/3) | +39.42 | +3.03 | +21.26 vs +6.26 | **COMPLETE** (+15.00) |
| antecedent-consistent, on \|shift\| (lane D R4) | 14 | 34.01 | 4.30 | 18.65 vs 9.21 | **COMPLETE** (+9.43) |
| never-retried decisions only (this lane) | 14 | +45.56 | +1.51 | +24.34 vs +8.81 | **COMPLETE** (+15.53) |
| **year 1 only (this lane)** | **14** | **−0.58** | **+0.27** | **−8.97 vs +2.20** | **BROKEN** |

**Surviving cell count on the strictest balance rule: 7** — irrigation gemma3:4b, gemma3:12b,
gemma4:e2b, gemma4:e4b, and flood gemma4_e2b, gemma4_e4b, gemma4_26b (lane B seed inventory;
lane D R2). On those 7 the separation is complete and the margin is unchanged at +15.01 pp.

**But the separation is not evidence for what the abstract says it is.** Two independent checks in
this lane:

**(a) Never-retried decisions.** Restrict the governed arm to decisions with `retry_count == 0` —
decisions where the agent was never shown a rule. The shift gets *larger* (+45.56 vs +38.13), and
separation stays complete. Within-decision premise revision cannot produce a shift on decisions
where nothing was said to the agent.

**(b) Year 1.** The clean test. Same seed, same initialisation, no decisions yet taken, world
provably identical. Shift ≈ 0 with mixed signs:

| cell | shift all years | shift year 1 | n gov / n ung (yr 1) | gov yr-1 retried |
|---|---:|---:|---:|---:|
| irrigation gemma3:4b | +45.50 | **+3.33** | 390 / 390 | 82.1 % |
| irrigation gemma3:12b | +21.26 | **−0.85** | 234 / 234 | 67.9 % |
| irrigation gemma4:e2b | +47.53 | **+4.36** | 390 / 390 | 81.5 % |
| irrigation gemma4:e4b | +43.38 | **−0.77** | 390 / 390 | 87.9 % |
| irrigation ministral3:8b | +32.97 | **−8.97** | 234 / 156 | 70.9 % |

Enforcement is at maximum in exactly this stratum and the appraisal does not move. The year-by-year
trace for the gemma3:4b baseline shows the shift growing from +3.3 pp (yr 1) to +80–92 pp
(yrs 17–33) and then collapsing back to ~+5 pp (yrs 38–42, both arms saturated near 95–99 % high
scarcity). It tracks reservoir divergence, not enforcement.

**Conclusion for §2:** the *table* is real and reproducible. The *sentence* "under sustained
enforcement the agent also revises the self-reported state" is not supported, and title candidate 1
("Governed agents revise the premise, not the policy") is contradicted by the repo's own data.
Title candidate 2 ("Conditioning on a post-treatment variable") survives all of it.

---

## 3. Defect register

Severity: **S1** changes a number or falsifies a claim · **S2** changes a number at stated precision
or breaks a comparison · **S3** does not change a number but misdescribes the material.

### Still open

| # | Defect | Where | Changes a number? | Sev | Fix |
|---|---|---|---|---|---|
| 1 | **Mechanism claim falsified.** Abstract/title assert enforcement-driven premise revision; shift is ≈0 at year 1 under 68–88 % retry pressure and ≈0 in the world-identical stratum. Dominant mechanism is world-state divergence in the coupled reservoir. §5 lists only *premise revision* and *selection*; the third mechanism is missing and is the one the evidence supports. | `papers/workshop_skeleton.md` §"finding", title 1, abstract, §5 | **Falsifies a claim** | **S1** | Reframe to title 2. Add world-state divergence as mechanism 3, cite `evidence/exogeneity_check.py`. Report the year-1 null as a result, not a limitation. ~1 day, no GPU. |
| 2 | **Flood "natural control" does not control what the paper says.** `run_flood.py:285-291` sets `flood_event` from `flood_years.csv` or an i.i.d. draw — **no agent action enters**. Flood has zero action→environment feedback; irrigation has a coupled mass balance. The flood null is explained by absence of a coupling channel and a 10-yr horizon, not by loose rule binding. | `examples/single_agent/run_flood.py:285-291`; `evidence/exogeneity_by_column.csv` | **Falsifies the control argument** | **S1** | Restate the control as "uncoupled environment", which is a *better* control for the measurement claim. ~2 h. |
| 3 | **Stale committed artifact carries the retracted contaminated value.** `flood ministral3_3b` row reads `n_governed=4577, shift=+2.0352`; correct is `n=3674, shift=−0.22`. The `.py` was fixed, the `.csv` never regenerated, and `README.md:31` points readers at that pair. | `evidence/appraisal_composition.csv` (lane A B1, lane D B1; re-confirmed here) | **Yes — sign flip** | **S1** | Regenerate or delete the CSV. 5 min. |
| 4 | **Abstract contains three wrong numbers.** "432,083 logged decisions" (real: **216,020**; the figure reproduces from nothing — lanes A, B, D all failed to source it); "mean 0.8 pp" (real **+0.56**); **"9/9 cells"** (only **5 of 9** low cells are positive; largest is +6.25 pp, which is not "vanishing"). The 9/9 error is flagged in no existing document. | `papers/workshop_skeleton.md:35-43` | **Yes ×3** | **S1** | Replace with 216,020 / +0.56 / "5 of 9 positive, all \|shift\| ≤ 6.3 pp". 15 min. |
| 5 | **Unfixed live copy of the Group_A glob bug.** Byte-identical to the pre-fix script; running it today reproduces +2.04 pp. | `AAMAS2027/experiments/appraisal_composition.py` (lane A B2) | Yes, if run | **S2** | Delete or apply the same fix. 10 min. |
| 6 | **Two more scripts carry the same `**` glob**, asymmetrically (only the governed root has a `Group_A` sibling). | `evidence/rederive_executed_levels.py:59`; `evidence/skeleton_claims_check.py:103,428,451` (lane A B3) | Denominator wrong; printed value unchanged at 2 dp | **S2** | Replace `{model}/**` with `{model}/Group_C/Run_*`. 20 min. |
| 7 | **Flood gemma3_4b governed Run_1 ran a different prompt.** 4 response fields, no MULTI-ACTION block, 2,480 chars vs 2,972 in all other 89 flood runs — verified from rendered prompts in `raw/household_traces.jsonl`, not inferred from config. 1 of 5 governed seeds is a different stimulus. | `JOH_FINAL/gemma3_4b/Group_C/Run_1` (lane B, blocking 1) | Unbounded on that cell | **S2** | Drop the seed (governed n=4) or disclose. Flood is a low-regime cell, so impact on the headline is small; do not quote that cell alone. 1 h. |
| 8 | **7 of 14 cells have unbalanced arms.** 6 flood cells pair governed seeds 42/4202/4203/45/46 against 42/43/44/45/46; irrigation ministral3:8b is 3 gov vs 2 ung. Pairing by `Run_N` pairs seed 4202 with seed 43. | lane B §3; lane A §B | Moves 7 of 14 cells; ministral3:8b +32.97→+31.07 | **S2** | Use unpaired tests, or restrict to the 7 balanced cells (separation holds either way). 2 h. |
| 9 | **Arms built at different code states.** In all 6 v1 flood cells, no-validator Run_1/2/3 were re-run 2026-05-30 at commit `5a1d467f` (dirty) during the reflection backfill; governed Run_1/2/3 date from Feb 2026 with no commit recorded. Arms differ in seed AND commit AND run date simultaneously. Not in any existing doc. | lane A B4; lane B §4(b) | Not measurable | **S3** | State it. Restricting to the 3 gemma4 flood cells avoids it entirely. |
| 10 | **`claude_verified_facts.md` is labelled "ground truth" and contains an unreproducible number** — claims single_agent = 117 runs / 156,705 rows; tree holds 109 audit CSVs / 98,305 rows. | `evidence/claude_verified_facts.md` (lane A B5) | Yes | **S2** | Correct or drop the label. 30 min. |
| 11 | **`Group_A` used *as* the no-validator arm in four Nature Water scripts**, contradicting the project rule that the baseline is `Group_C_disabled`. One of them (`gen_si_cumulative_adaptation.py:52`) silently drops a whole series because `Group_B` was archived — it prints an error, **exits 0, and saves the figure anyway**. | `paper/nature_water/scripts/gen_si_cumulative_adaptation.py`; `examples/single_agent/analysis/{nw_flood_pmt_crosstab,nw_flood_ibr_decomposition,nw_ehe_annual_decision}.py` (lane A §D) | Yes, for NW SI | **S1 for NW, out of scope here** | Separate task. Do not let this paper inherit those scripts. |
| 12 | **`Run order = seed order` asserted in a comment, false for 6 flood cells**, feeding `ttest_rel` for NW Supplementary Tables 1 and 6. | `paper/nature_water/scripts/analysis_2026-05-31/gen_tableS1_S6_crossmodel_unified.py:48` (lane A §C) | Yes, for NW SI | **S1 for NW, out of scope** | Separate task. |
| 13 | **"Post-correction on 100 % of rows" is false.** Real: **74.1 %** of governed irrigation decisions were retried (51 % hit the 3-retry cap); flood governed is **4.5 % / 5.8 %**. On the remainder the recorded appraisal *is* the first attempt. | `papers/workshop_skeleton.md` §5; measured this lane | Yes | **S2** | Replace with the real rates. This is *good* for the paper — it is what makes check (a) in §2 possible. 30 min. |
| 14 | **Zero clean provenance, corpus-wide.** Of 131 manifests: 74 `git_dirty=true`, **57 with no `git_commit` field at all**, **0 clean**. The 57 include every one of the 45 governed flood v1 runs. 18 distinct code states. | lane B §5; lane D | No | **S3** | No Data/Code Availability statement may claim commit-level reproducibility. |
| 15 | **`skeleton_claims_check.py` §5 claim unverified by any lane** and now measured: see #13. Lane D listed it UNVERIFIED; settled here. | — | — | — | Closed by #13. |

### Already fixed / already correct — do not spend time here

| item | status |
|---|---|
| Group_A 903-row contamination in `evidence/appraisal_composition.py` | **FIXED and verified complete** by lane A (glob now names `Group_C`/`Group_C_disabled`); only the CSV is stale (#3). Confirmed independently in this lane: my recomputation returns **−0.22** for that cell. |
| `workshop_evidence.py` selection | **Clean.** No `**`, explicit `Group_C`/`Group_C_disabled`, self-reports balance and blank-appraisal counts (lane A #5). Best script in the tree. |
| `decomposition/_loader.py`, `e6_flood_placebo.py` | **Clean**, with a `paired_seeds()` primitive and loud `DataError`s (lane A #6). |
| Executed-vs-proposal action confusion | **Already known and already corrected in this workspace.** `rederive_executed_levels.py` documents it in its docstring, verified it empirically (1,865/1,865 REJECTED rows unchanged), and `workshop_evidence.py:504` implements `_executed()` correctly. Lane C reported this as a new blocking defect; it is not new and it is not open **for this paper**. It remains an open issue for anything reading `final_skill` naively. |
| "First-attempt appraisal not recoverable" (§5) | **Correct as written.** Lane C flagged it, but lane C's own finding is that first-attempt *labels and reasoning* are genuinely gone; only the first-attempt *action* is recoverable (86 % of flood retry rows, via skill names interpolated into `error_messages` at `agent_validator.py:507`). The skeleton says *appraisal*. It stands. |
| "F1 silent-drop → flood is partial data" | **MISDIAGNOSIS, and the material is better than documented.** Lanes B and D independently: sim logs are 1,000 rows in every flood run; 8,283 of 8,296 missing audit rows are `relocated` agents (a designed absorbing state); only **13 rows corpus-wide** (0.006 %) are genuine drops, and they appear both before F1 was introduced and after it was fixed. Any restriction adopted because flood was believed partial can be lifted. |
| 2026-05-30 reflection confound | **Remediated.** All 18 defective runs quarantined (no `reflection_log.jsonl` at all); all 131 live runs have a non-empty one. Side effect is #9. |
| WARNING rules → 0 % behaviour change | **Architecturally forced, verified** at 3 points by lane C. The skeleton already bans this claim. Correct. |
| pytest suite | 3,293 passed, 3 skipped, 2 xfailed, 0 failed (lane C, run twice). |

---

## 4. What is usable, stated positively

- **All 131 runs.** 41 irrigation + 90 flood, every one 100 % row-complete, zero `(agent, year)`
  holes, zero duplicates, zero orphan audit rows, zero byte-identical duplicate files (lane B).
  This is a clean corpus.
- **The 7 balanced cells** — irrigation gemma3:4b / gemma3:12b / gemma4:e2b / gemma4:e4b, flood
  gemma4_e2b / gemma4_e4b / gemma4_26b — have matched seeds, perfect arm config parity (the *only*
  differing key is `governance_profile`), and no code-era split. **A paper resting only on these 7
  is defensible without caveat #8 or #9.** The separation is complete on them.
- **The per-cell appraisal table**, recomputed here through a fourth independent code path, matches
  lane D and `workshop_evidence.py` exactly, including the corrected `flood ministral3_3b = −0.22`.
- **The 216,020-row figure** is confirmed to the row (134,316 irrigation + 81,704 flood).
- **`NUMBERS.md`** is accurate — all 94 CLAIM lines reproduced, `anchor_gate: PASS` (lane D). It is
  the trustworthy document in the set. The *skeleton* is what carries stale numbers.
- **`evidence/exogeneity_check.py` and `exogeneity_by_column.csv`** are the strongest assets in the
  workspace and are currently unused by the skeleton. They give you a per-column, per-year
  treatment-invariance classification with an explicit sign convention and a reconstructed
  exogenous precipitation trace checked against source. **This is the evidence that makes the
  reframed paper work.**
- **The year-1 stratum** is a legitimate conditioning point: every hydrology column has
  `year1_exact_equal_rate = 1.0` and `first_year_with_any_disagreement = 2`. n = 390 per arm per
  cell (234 for the 3-seed cells).
- **The 5 matched model pairs** across testbeds (gemma3:4b, gemma3:12b, gemma4:e2b, gemma4:e4b,
  ministral3:8b appear in both) mean model family and size are *not* confounded with regime.
- **`workshop_evidence.py` and `decomposition/`** are safe to build on as-is.

---

## 5. What is NOT usable, and why

- **`evidence/appraisal_composition.csv`** — stale, carries the retracted value. Do not grep it.
- **`AAMAS2027/experiments/appraisal_composition.py`** — unfixed copy of the contamination bug.
- **`flood ministral3:3b` as a quotable cell** — it has now flipped sign under two different
  selection choices (Group_A removal +2.04 → −0.22; seed pairing −0.22 → +1.18). Report it inside
  the low-regime range, never on its own.
- **`JOH_FINAL/gemma3_4b/Group_C/Run_1`** — different prompt. Drop or disclose.
- **Paired tests on the 6 v1 flood cells** (gemma3_4b, gemma3_12b, gemma3_27b, ministral3_3b,
  ministral3_8b, ministral3_14b) — arms are not seed-matched.
- **Any paired test on irrigation ministral3:8b** — 3 vs 2 seeds;
  `ungoverned_v21_42yr_ministral3_8b_seed44` does not exist.
- **`evidence/claude_verified_facts.md` as ground truth** — contains an unreproducible count.
- **The number 432,083** — sourced by nothing, in any lane.
- **The number 347 runs** — sourced by nothing; three different counts give 215 / 200 / 131.
- **`Group_A` for anything** — it is a different experiment (no structured prompts). The four NW
  scripts that use it as the no-validator arm are wrong.
- **`_QUARANTINE_reflection_missing_2026-05-30/` (15,698 rows)** — reachable by any glob rooted at
  `single_agent/results/**`. Root your globs at `JOH_*` or deeper.
- **Commit-level reproducibility claims** — 0 of 131 runs support one.

---

## 6. Framework verdict — does the code do what the papers say?

Mostly yes, with six documentation/code disagreements. Lane C verified each against both source and
shipped data.

| # | Documentation says | Code does | Impact here |
|---|---|---|---|
| 1 | `REJECTED_FALLBACK` = "retries exhausted, registry default executed" (`broker/INVARIANTS.md` §2, `_audit_helpers.py:318`) | It is set iff **the parser produced nothing** (`skill_broker_engine.py:647`). Plain `REJECTED` rows *also* run the default. Confirmed on data: all 23 such rows have empty `parse_layer`. | Low — this paper's pressure metric uses `status.startswith("REJECTED")`, which covers both. Fix the doc. |
| 2 | `fallback_activated` marks fallback rows | **True on 1 row of 216,020.** Effectively a constant. | Never use it to count fallbacks. |
| 3 | `failed_rules` / `rules_triggered` describe this decision | **Pooled across all attempts**, deduped. Non-empty on 763/2009 APPROVED irrigation rows. | Do not use as a per-decision blocking-rule count. |
| 4 | `final_skill` / `yearly_decision` = the decision taken | **Proposal-stage**, last attempt. On 37,445 of 216,020 rows (17.3 %) the recorded skill provably never executed (Δrequest +0.00 % on all 1,244 REJECTED rows of seed42; `magnitude_pct` empty on 100 % of them). | **Already handled** in this workspace (`_executed()`); open for other consumers. Retires the circular MEMORY.md note that "yearly_decision == final_skill" proves execution. |
| 5 | Retries are a conversation | `prompt` is never reassigned; each retry re-sends attempt-0's prompt plus current reports. No accumulated dialogue. | Describe accurately in §2. |
| 6 | `INVARIANTS.md` test names; Invariant 4 guard | Several named tests do not exist; Invariant 4's dormant-column rule is near-vacuous (3 of 4 tracked keys are skipped). | Housekeeping. |

Two behavioural findings worth knowing, neither blocking for this paper:

- **Blocked proposals advance governance state.** `run_experiment.py:303` feeds the *blocked* skill
  to `update_consecutive_tracker`, and `irrigation_validators.py:612-623` increments the
  consecutive-increase counter for any `increase_*`. A blocked increase counts toward the cap that
  blocks *future* increases. This changes simulated trajectories, not just labels.
- **The "no validator" arm is not unconstrained.** 32.7 % of ungoverned irrigation decisions are
  REJECTED by registry preconditions (`skill_broker_engine.py:833-851`), outside the validator
  stack. The arm still retries up to 3 times. Needs one sentence in Methods.

---

## 7. Limitations any paper on this corpus must state

1. **Enforcement regime is perfectly confounded with testbed identity.** All 5 high-pressure cells
   are irrigation; all 9 low-pressure cells are flood. Within-testbed there is *no* regime contrast
   and *no* dose–response: within-irrigation Pearson(pressure, shift) = **−0.514** (wrong sign),
   within-flood **+0.148**, pooled **+0.848**. The entire pooled correlation is between-testbed.
   **Enforcement pressure cannot be presented as an independent predictor** — at the level of the
   explanatory variable this is n = 2, not n = 14. Testbed bundles: rule tightness, environmental
   coupling, appraisal construct (WSA vs TP), theory, action space (5 vs 4), horizon (42 vs 10 yr),
   agent count (78 vs 100). Model family and size are the one thing *not* confounded (5 matched
   pairs).
2. **The two testbeds differ in whether the environment is coupled at all** (defect #2). Given the
   year-1 null, this is the more likely explanation of the contrast than rule tightness.
3. **Provenance is unrecoverable.** 0 of 131 runs have a clean manifest; 57 record no commit; 18
   distinct code states.
4. **The backend is non-deterministic at fixed seed and commit** (documented for `gemma4:e4b` on
   RTX 4080 SUPER + Ollama 0.23). N-seed aggregates only; and this makes seed *pairing* nominal
   even where seeds match, which independently weakens the case for paired tests.
5. **Unbalanced arms in 7 of 14 cells**, including the highest-pressure cell.
6. **Mixed-vintage arms** in 6 flood cells (defect #9).
7. **Differential relocation attrition in flood.** Arms count different numbers of agent-years
   (capture differs by −6.36 pp on gemma3:4b, +5.28 on gemma4:e2b) because relocation is treated and
   ends participation. Small (≤1.03 pp on the shift) but it is the same class of error the paper is
   about.
8. **The flood conditioning stratum is chosen, not given.** Two of three flood ERROR rules condition
   on TP ∈ {VL, L}, not {H, VH}. On that stratum shifts reach −9.21 pp — an order of magnitude
   larger than the +0.56 reported. Separation still holds on |shift| (margin +9.43) but "the
   difference vanishes" is not supportable.
9. **The irrigation antecedent is a conjunction** (WSA high **AND** ACA high); the metric conditions
   on one conjunct. Measured on the true joint antecedent the effect holds (+18.65 … +43.00), so
   this is a strengthening robustness check the paper should volunteer.
10. **Two open-weight families, ≤27B, one governance implementation.** Already in the skeleton.
11. **The appraisal is recorded post-retry on 74 % of governed irrigation decisions** and 4.5–5.8 %
    of governed flood decisions — not 100 %.

---

## 8. Ordered work list

**Zero GPU hours required for anything below.** Nothing needs a re-run.

| # | Item | Blocking? | Est. | GPU |
|---|---|---|---|---|
| 1 | **Reframe to the post-treatment-conditioning paper.** Adopt title 2. Add world-state divergence as mechanism 3 in §5, sourced to `exogeneity_check.py`. Move the year-1 null and the never-retried check into §5 as *results*. Drop "revise the premise" from title and abstract. | **BLOCKING** | 1 d | no |
| 2 | **Restate the flood control** as an uncoupled-environment control, not a loose-rules control (`run_flood.py:285-291`). | **BLOCKING** | 2 h | no |
| 3 | **Fix the three abstract numbers**: 432,083 → 216,020; 0.8 → +0.56; "9/9" → "5 of 9 positive, all \|shift\| ≤ 6.3 pp". | **BLOCKING** | 15 min | no |
| 4 | **Regenerate or delete `evidence/appraisal_composition.csv`.** | **BLOCKING** | 5 min | no |
| 5 | **Delete `AAMAS2027/experiments/appraisal_composition.py`**; fix the `**` glob in `rederive_executed_levels.py:59` and `skeleton_claims_check.py:103,428,451`. | **BLOCKING** | 30 min | no |
| 6 | **Decide the analysis set**: all 14 with caveats, or the 7 balanced cells. Recommend leading with 14 and reporting the 7-cell restriction as a robustness row — separation is complete in both. | **BLOCKING** | 1 h | no |
| 7 | Replace the "100 % post-correction" sentence with 74.1 % / 4.5–5.8 %. | high | 30 min | no |
| 8 | Drop or disclose `JOH_FINAL/gemma3_4b/Group_C/Run_1` (different prompt). | high | 1 h | no |
| 9 | Add the year-1 table and the within-testbed correlations (−0.514 / +0.148 / +0.848) to the limitations, and state the confound in §2 rather than waiting for a reviewer. | high | 2 h | no |
| 10 | Correct or de-label `evidence/claude_verified_facts.md`; drop the unsourced 432,083 and 347. | high | 30 min | no |
| 11 | Add the joint-antecedent robustness check (#9 in §7) as a footnote — it *strengthens* the result. | medium | 2 h | no |
| 12 | Add the low-TP flood stratum (#8 in §7) so a reviewer does not find it first. | medium | 2 h | no |
| 13 | Fix the six documentation/code disagreements in `broker/INVARIANTS.md` and `_audit_helpers.py:318`. | optional, not this paper | 3 h | no |
| 14 | **Separate task, do not fold in:** the four Nature Water scripts using `Group_A` as the no-validator arm, and `gen_tableS1_S6_crossmodel_unified.py:48`'s false pairing assumption. These affect the NW SI, not this paper. | out of scope | — | no |

**Critical path to a writable paper: items 1–6, roughly 2 working days, no GPU.**

---

## 9. Reproducing this lane

- `SUBMISSION_2026/audit/audit_synthesis_checks.py` — never-retried and full-run shift per cell
  (read-only over `examples/`; writes nothing).
- Year-1 and year-by-year tables, retry distributions, and within-testbed correlations were computed
  inline; the logic is the same as the script above with a `year` filter.
- Lane scripts: `SUBMISSION_2026/audit/audit_data_selection.py` (A),
  `.ai/corpus_audit/audit_run_integrity.py` (B), `SUBMISSION_2026/audit/audit_claim_traceability.py` (D).

### Side effects to be aware of

Lane D re-ran `papers/workshop_evidence.py`, regenerating `per_cell_table.csv` and `fig1_data.csv`
(both byte-consistent with `NUMBERS.md`; `SUBMISSION_2026/` is gitignored).

**Lane A ran `paper/nature_water/scripts/gen_si_cumulative_adaptation.py`, which regenerated
`paper/nature_water/figures/Fig3_cumulative_adaptation.png` and `.pdf` — and that script silently
drops its `Group_B` series (defect #11), so the regenerated figure has two of three series.
`paper/` is gitignored, so the previous version is not recoverable from git. Check the current Fig3
against the SI before doing anything else.**
