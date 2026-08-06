# Robustness memo: the conditional appraisal-action inconsistency estimand

Phase 4a deliverable. Audience: the author deciding what to change before submitting, and through
them a hostile reviewer. Anchor cell throughout is the published pair, irrigation gemma3:4b, 5
paired seeds (42-46).

**Sign convention, stated once and used everywhere below: every gap is governed minus ungoverned.
Negative means governance LOWERED the rate.** The paper reports the same magnitudes with the sign
flipped ("a 23.0 pp reduction"); this memo never uses that convention.

---

## 1. Verdict

**SURVIVES-WITH-REFRAMING** — for the anchor irrigation contrast only, and only as a total effect
on behaviour, not as a causal claim about appraisal-action consistency.

The single number: removing the post-treatment conditioning entirely, the governance effect on the
unconditional demand-increase rate is **−21.62 pp** (governed 40.90%, no-validator 62.52%; 95% CI
−26.80 to −16.45; paired t = −11.608, df = 4, p = 0.000315), which is **93.9% of the published
−23.02 pp magnitude** (`e1_total_effect.py`).

Three things do not survive and must be fixed before submission: (a) the published quantity is not
identified as a causal effect and the Methods definition currently hides that it is conditional at
all; (b) the R2 high-scarcity/high-capacity quadrant paragraph is a within-cell comparison across
two arms whose cell populations differ by 45.7 pp of appraisal mass, and cannot be repaired by
rewording; (c) the action variable is the agent's last *proposed* action, not the executed one, so
the paper's "executed action" wording is wrong — recomputed on what actually moved the water
request the same statistic is 0.86% governed vs 26.77% no-validator (`linkage_check.py`).

---

## 2. The problem as a reviewer would state it

The reported inconsistency rate is conditioned on the agent's own self-reported high-scarcity
label, and that label is produced by the same language-model call that produces the action, in the
arm being treated. Governance moves it enormously: 37.08% of governed decisions report high
scarcity against 82.80% without validators, a 45.73 pp shift (`reproduce_published.py`). The two
arms' denominators are therefore different populations of decisions, so the reported difference
mixes a change in behaviour with a change in who is counted, and a contrast conditioned on a
post-treatment variable does not identify a causal effect.

---

## 3. Results table

Six estimators, each independently re-derived by a separate verifier script that shares no code
with it. **All six verifiers returned CONFIRMED-WITH-CORRECTIONS: every headline number reproduced
exactly, and every estimator's own summary label needed correction.** Where the estimator and its
verifier disagree, the verifier's judgement governs and the disagreement is shown.

| # | Estimand | Headline number (script) | Estimator's own label | Verifier verdict and the correction that matters |
|---|---|---|---|---|
| e1 | Total effect on the unconditional increase rate; denominator fixed by design at 78 agents x 42 years | **−21.62 pp**, CI [−26.80, −16.45], t = −11.608, df 4, p = 0.000315 (`e1_total_effect.py`) | SURVIVES | CONFIRMED-WITH-CORRECTIONS. The number is right and stable to leave-one-seed-out (−20.83 to −23.39, all p < 0.01). The **label is over-claimed twice**: the "85% survival" decision threshold sits inside the survival statistic's own CI [77.9%, 109.6%], and what survives is a *different estimand* of similar size, not the published one (`_verify_e1_total_effect.py`) |
| e2 | Same rate, standardized on exogenous CRSS winter precipitation terciles x static water-right terciles, years 1-41 | **−21.21 pp**, CI [−26.23, −16.18], t = −11.71, df 4, p = 0.000304 (`e2_stratified.py`) | SURVIVES | CONFIRMED-WITH-CORRECTIONS. **This is not an independent estimator.** Standardization is an identity on this data; e2's own 42-year variant returns e1's headline bit-for-bit (−21.62, t = −11.608, p = 0.000315). The campaign has one identified estimator across e1+e2, not two (`_verify_e2_stratified.py`) |
| e3 | Kitagawa/Oaxaca split of the design-fixed gap into composition (who is in which appraisal stratum) and behaviour (rate within stratum) | composition **+6.34 pp**, CI [+4.69, +7.99], t = 10.677, p = 0.0004; behaviour **−27.97 pp**; composition share of the design-fixed gap **−29.3%** (`e3_decomposition.py`) | SURVIVES; "the reviewer's worry has the sign backwards" | CONFIRMED-WITH-CORRECTIONS, and **the sign claim is REFUTED**. The direct quantity — how much bigger the headline looks because it conditions — is positive in 4 of 4 balanced cells and 16 of 18 seed-cells: +1.39 pp (anchor, p = 0.316), +7.11 (12b), +3.69 (e2b, p = 0.035), +8.89 (e4b, p = 2.9e-05) (`_verify_e3_decomposition.py`) |
| e4 | Worst-case bounds on the conditional estimand for a fixed population (agents who would report high scarcity absent validators) | sharp identified set **[−30.49, −9.68] pp**; Imbens-Manski 95% [−35.53, −4.84]; upper bound vs zero t = −4.265, p = 0.013 (`e4_bounds.py`) | WEAKENED | CONFIRMED-WITH-CORRECTIONS. Bounds arithmetic verified by brute force, but the **non-identification premise is wrong**: both arms ran the same agents/years/seeds, so the matched-cell estimate is available and is **−20.38 pp**, CI [−25.39, −15.37], p = 0.00035 (88.5% of the headline). Separately, a **coding defect flips a reported result**: monotonicity-violating cells get a zero-width point instead of [0,1]; widening them consistently moves the year-stratified Lee interval from [−42.29, −5.82] (excludes zero) to [−45.86, +1.90] (includes zero) (`_verify_e4_bounds.py`) |
| e5 | The same contrasts restricted to year 1, where Phase 1 proved the two arms' worlds are bit-identical | year-1 conditional gap **+1.15 pp**, CI [−4.71, +7.00], p = 0.616; unconditional **−1.28 pp**, CI [−2.87, +0.31], p = 0.089; appraisal-share **−3.33 pp**, p = 0.261 (`e5_year1.py`) | OVERTURNED | CONFIRMED-WITH-CORRECTIONS, **label rejected**. A null at 1 of 42 time points does not overturn a cumulative total effect, and the estimator's own caveats say so. Also: its headline +1.15 pp is itself mediator-conditioned; the clean version is the **matched-denominator year-1 gap −4.37 pp**, CI [−15.75, +7.00], p = 0.346 on the 61 agents rated high in both arms (`_verify_e5_year1.py`) |
| e6 | Flood placebo: the same composition machinery on a testbed where the theory rules rarely bind | flood composition **+1.39 pp**, CI [−1.48, +4.27], includes zero (n = 3 balanced cells) vs irrigation **+6.44 pp**, CI [+4.77, +8.11], excludes zero; appraisal shift flood **−3.37 pp** vs irrigation **−45.50 pp** (`e6_flood_placebo.py`) | SURVIVES | CONFIRMED-WITH-CORRECTIONS. Numbers exact, but the **mechanism story is wrong in one factual particular and understated in another**: the flood config has three ERROR-level appraisal-conditioned rules, not one, and two of them target the low stratum; and enforcement dose is 6x to 75x the reported terminal-rejection figure. The verifier then found a **dose-response**: Spearman(rule-firing rate, |appraisal shift|) = 0.867, p = 0.0025 across 9 flood cells. Flood is a low-dose control, not a structurally clean zero (`_verify_e6_flood_placebo.py`) |

One cross-campaign inconsistency to note before anyone quotes two of these side by side: e6 reports
the irrigation unconditional gap as −21.37 pp (parsed rows only) while e1/e2/e3 report −21.62 pp
(all rows). The 0.25 pp difference is the 105 governed `N/A` appraisal rows, which are exactly the
rows where the retry budget was exhausted.

---

## 4. What is identified and what is not

**Identified: the total effect of the governance regime on the unconditional demand-increase rate.**
The denominator is 78 agents x 42 years = 3,276 rows in every one of the 41 runs, fixed by the
experiment design before any model call. Nothing in it can move with treatment. The only assumption
is that the two arms differ solely by the validator toggle, and that assumption is checkable and
checks out: `diff` of the two arms' `config_snapshot.yaml` returns exactly one changed line on all
five anchor seeds, `governance_profile: strict` vs `disabled` (`_verify_e1_total_effect.py`). The
estimate is −21.62 pp with CI [−26.80, −16.45].

Read this precisely: it is a **whole-run regime effect that includes the reservoir feedback**, not
"the effect of validators holding the environment fixed". Phase 1 measured the arms' worlds
diverging completely from year 2 — Lake Mead sits 102.25 ft higher under governance, shortage tier
1.84 lower, drought index 0.157 lower, all at 2.2-3.0 pooled standard deviations. Part of the
measured effect is agents responding to a river that governance made less scarce. That is a
legitimate estimand for a policy question ("what happens if we impose these rules") and the wrong
estimand for a cognition question ("do the rules make agents reason more consistently").

**Not identified: the published within-appraisal contrast.** The conditioning variable `wsa_label`
is emitted by the treated language-model call. Its distribution moves 45.73 pp between arms. There
is no covariate on Phase 1's SAFE list that can fix this — the four treatment-invariant logged
columns (`water_right`, `cluster`, `basin`, `has_efficient_system`, the last of which has one
distinct value and adjusts nothing) are static agent attributes; they absorb between-agent
composition and cannot rebalance a denominator that moved because the self-report moved. The
exogenous CRSS precipitation trace is genuinely treatment-invariant at every year but varies only
by year, so it cannot substitute either — which is exactly why e2's standardization turned out to
be an arithmetic identity.

**Also not identified, and worth saying plainly: nothing here is identified beyond the anchor.**
The magnitude that survives de-conditioning collapses across cells: 93.9% (gemma3:4b), 80.5%
(gemma4:e2b), 48.9% (gemma4:e4b), **1.4%** (gemma3:12b, where −11.44 pp becomes −0.16 pp), and on
the excluded unbalanced ministral-3:8b cell the sign flips to +21.12 pp (`e1_total_effect.py`). On
the population-matched conditional estimate the sign reverses outright in 2 of 5 cells: +8.57 pp
(12b) and +30.87/+38.93 pp (ministral) (`_verify_e4_bounds.py`). **The anchor is the single most
favourable cell in the corpus**, and it is the cell the paper publishes.

**Two identification caveats a careful reader will apply to our own rescue numbers.** First, e4's
matched-cell Δ_S = −20.38 pp treats the ungoverned arm's realised high-scarcity label at
(seed, agent, year) as the governed unit's counterfactual appraisal. That holds at year 1, where
the worlds are bit-identical; from year 2 the ungoverned agent is standing in a different river, so
Δ_S is a matched-cell descriptive quantity, not a point-identified potential-outcome contrast. The
verifier is right that it is far more informative than the near-vacuous bounds and right that the
estimator should not have declined to compute it; it is not right to call it identified. Second,
seed-level inference here generalises over language-model sampling only. The 78-agent attribute
table is identical across all five seeds, and precipitation is a fixed exogenous trace identical
across seeds and arms, so the CIs are resample-the-model intervals, not population intervals
(`_verify_e3_decomposition.py`, `_verify_e5_year1.py`).

---

## 5. How much of the −23.0 pp is composition

The reviewer will ask for one number. There are three defensible answers to that question and they
are not the same number, so give all three or the reviewer will find the two you left out.

**(a) The direct answer — how much bigger the headline looks because it conditions: +1.39 pp on the
anchor, about 6% of the reported magnitude.** |published −23.02| minus |design-fixed −21.62|. Not
significant at n = 5 (t = 1.144, df = 4, p = 0.316), but **positive in 4 of 4 balanced cells and 16
of 18 seed-cells**, and much larger elsewhere: +3.69 pp on gemma4:e2b (p = 0.035), +7.11 pp on
gemma3:12b (62% of that cell's headline), +8.89 pp on gemma4:e4b (p = 2.9e-05, 51% of that cell's
headline). Source: `_verify_e3_decomposition.py`. **Conditioning on the self-report inflates the
apparent governance benefit in every balanced model. The anchor is where it inflates least.**

**(b) The formal decomposition term: +6.34 pp, CI [+4.69, +7.99], t = 10.677, df = 4, p = 0.0004
(`e3_decomposition.py`).** This is the composition component of the *design-fixed* gap: what the
unconditional gap would have been if only the appraisal mix had moved and within-stratum rates had
not. It is **positive against a negative total**, i.e. −29.3% of the gap, so on this accounting the
composition shift works *against* the measured benefit and the pure within-stratum behaviour term
is −27.97 pp, larger in magnitude than the published headline. This is the campaign's most
counter-intuitive result and it is real and reproduced twice. It is also the number most likely to
be misused: it is a term in the internal accounting of a *different* estimand, so it does not
license "the reviewer's concern has the sign backwards" — see (a), which is the version of the
question the reviewer actually asked.

**(c) The population-matched version of the published statistic itself: −20.38 pp, CI [−25.39,
−15.37], p = 0.00035 (`_verify_e4_bounds.py`).** Holding the denominator fixed at the set of
decisions that reported high scarcity in the no-validator arm, the gap is 11.5% smaller than the
published −23.02 pp. Read with the caveat in §4: this is matched-cell, not identified.

**Uncertainty on the "93.9% survives" statistic.** Per-seed survival ratios are 97.6, 113.3, 84.8,
92.4, 80.6 percent; mean 93.75%, sd 12.79, 95% CI **[77.9%, 109.6%]** (`_verify_e1_total_effect.py`).
One seed exceeds 100%. Do not report 93.9% to three significant figures without that interval, and
do not report the corpus-wide ordering (93.9 > 80.5 > 48.9 > 1.4) as an established ranking — the
anchor-vs-e2b difference is roughly 2.4 standard errors.

**Two caveats attached to all three numbers.** Composition and behaviour are not cleanly separable
here because the appraisal shift is partly *veridical*: governance made the river less scarce
(Lake Mead +102 ft), so a lower high-scarcity share is partly agents correctly reporting a better
world. And the outcome is binary throughout — `increase_large` and `increase_small` count the same,
and `magnitude_pct` / `request` / `diversion` are never used — so none of these numbers says
anything about how much water moved.

---

## 6. Mechanism: premise revision or selection?

**The evidence does not distinguish them, and it cannot on this corpus. That is the honest answer,
and it is the strongest available motivation for the planned experiment.**

Both channels are demonstrably present:

- *Selection is present by construction.* 94.6% of governed rejections are on `increase_small` /
  `increase_large` proposals, and the rules are named `high_threat_high_cope_no_increase`,
  `low_threat_no_increase`, `supply_gap_block_increase`, `demand_ceiling_stabilizer`
  (`_verify_e2_stratified.py`). High-appraisal increase proposals are exactly what trips the stack.
- *Premise revision is consistent with the aggregate.* The high-scarcity share falls from 82.80% to
  37.08% (`reproduce_published.py`), and in the flood testbed the appraisal shift scales with how
  often the rules actually fire (Spearman ρ = 0.867, p = 0.0025 across 9 cells; ρ = 0.783,
  p = 0.013 after normalising the dose by the high-appraisal base rate — `_verify_e6_flood_placebo.py`).
  Flood has no shared-resource feedback of the irrigation kind, so that dose-response is hard to
  explain by world divergence.

**The key evidence is the year-1 trajectory, and it points away from premise revision at the moment
of enforcement.** At year 1 the two worlds are bit-identical (Phase 1: all nine pre-decision columns
equal on all 390 matched pairs). There, the appraisal-share gap is **−3.33 pp, CI [−10.42, +3.75],
p = 0.261** — no shift — and this is *despite* 320 of 390 governed rows having taken at least one
validator rejection with the retry budget exhausted at 3 (`e5_year1.py`, `_verify_e5_year1.py`).
Agents under direct, repeated rejection pressure do not restate their scarcity appraisal downward
on the first decision. The paired within-seed test confirms year 1 genuinely differs from the rest
of the run: the appraisal-share gap is +43.43 pp larger at year 1 than over years 2-42
(p = 0.000012).

From year 2 onward the two candidate explanations become perfectly confounded, because that is
exactly when the worlds diverge (0% agreement on `lake_mead_level`, `drought_index`,
`mead_storage_maf` from year 2, never recovering). A governed agent reporting lower scarcity in
year 10 may be revising its premise to dodge a rule, or may be accurately describing a reservoir
that is 102 ft fuller *because* the rules worked. No estimator in this campaign can separate those,
and no reweighting can, because the confounder is a consequence of the treatment.

Two further facts a reviewer will want, both of which complicate any simple story:

- **The mechanism is not persuasion at the reasoning level, but it is not pure blocking either.**
  52 of the 320 feedback-exposed year-1 rows were eventually approved after rejection, 11 of them
  on a non-increase action. And the year-1 *stated* action distribution moves enormously — 
  `increase_large` −22.56 pp, `increase_small` +21.28 pp, chi² = 46.2 on 4 df, p = 2.2e-09 — while
  the published binary (increase vs not) barely moves, because the two shifts cancel inside the
  increase family (`_verify_e5_year1.py`). The published statistic is blind to the largest year-1
  effect in the data.
- **Late in the run, composition equalises and the conditional gap does not.** In years 38-42 the
  appraisal-share gaps are −4.62, +1.03, −5.13, −7.44, −4.87 pp while the conditional gaps are
  −32.91, −27.18, −32.65, −42.96, −39.15 pp (`e5_year1_trajectory.csv` via
  `_verify_e5_year1.py`). Those years are a near-matched-denominator contrast in which the published
  gap survives intact. It is not identified (the worlds have diverged), but it is direct evidence
  that the gap is not purely compositional, and it belongs in the record.

**What would separate them.** An arm with validators enforced but the reservoir trajectory pinned to
the no-validator path (feedback off), or an arm where validator feedback is shown to the agent but
never enforced. Either isolates premise revision from veridical re-appraisal. Nothing in the current
corpus does.

---

## 7. Recommended actions for the paper

Paths are relative to the repo root. Line numbers are from the exposure map.

### Blocking, before anything else

**M0 — MUST: decide which main text is live.** `paper/nature_water/PAPER_ASSETS.md` (2026-06-02)
declares the markdown drafts current and locks the 36.1 / 59.1 headline; but
`paper/nature_water/WAGF_NatureWater_maintext_governance_v50.docx` (2026-06-13, eleven days newer,
unmentioned in PAPER_ASSETS) contains **no AAI number anywhere** — no 36.1, no 59.1, no 23.0. If
v50 is live, most of the exposure below has already been removed by accident and the work collapses
to the Methods definition, one figure panel, and the SI. If the markdown drafts are live, nine
load-bearing claims need rewriting. **The rest of this list assumes the markdown drafts (Track A);
skip the ones that no longer exist if v50 is authoritative.**

### MUST

**M1 — Rewrite the Methods AAI definition. It currently hides the conditioning and describes a
different metric.** `paper/nature_water/drafts/methods_v7.md:101` says "the fraction of decisions in
which an agent's stated cognitive appraisal contradicts the proposed action" and "the percentage of
executed decisions that violate..." — both read as unconditional rates over all decisions, and the
paragraph then describes an A+B+C three-rule-set metric (`examples/irrigation_abm/analysis/compute_ibr.py`)
that is *not* what 36.1 / 59.1 measures. Replace the irrigation definition with:

> Appraisal-action inconsistency (AAI) is a conditional rate. In the irrigation testbed it is the
> share of agent-years in which the agent's self-reported water-scarcity appraisal was high or very
> high (WSA in {H, VH}) and the action it recorded for that year was a demand increase
> (`increase_small` or `increase_large`). The denominator is not all decisions: agent-years labelled
> VL, L or M are excluded. Both the numerator and the denominator are produced by the same
> language-model call, so the appraisal label is an outcome of the intervention rather than a fixed
> covariate, and the two arms' denominators are different sets of decisions (high-scarcity share
> 37.1% with validators, 82.8% without). AAI is therefore reported as a descriptive property of each
> arm's decision record, not as a causal estimate of the effect of validation on appraisal-action
> consistency. The contrast that conditions on nothing produced by the model — the share of all
> agent-years, denominator fixed at 78 agents x 42 years, in which the recorded action was a demand
> increase — is 40.9% with validators and 62.5% without (difference −21.6 percentage points, 95% CI
> −26.8 to −16.5; paired t = −11.61, df = 4, p = 0.0003).

**M2 — Correct "executed" to "proposed" wherever the irrigation action variable is described.**
`simulation_log.yearly_decision` is byte-identical to the audit's `final_skill` in 100.00% of all 41
runs, but a rejected proposal never moved the water request: **6,096 of 6,096 governed rejected rows
and 4,754 of 4,754 ungoverned rejected rows show zero movement in `request`** (`linkage_check.py`).
On the executed action the same statistic is **0.86% governed vs 26.77% no-validator, gap −25.90 pp**,
and the unconditional executed rate is 3.60% vs 33.50% (`e3_decomposition.py` Part E). This affects
`drafts/methods_v7.md:101`, the v50 docx Methods P60/P65 ("executed action"), and
`PAPER_ASSETS.md:17-19`. Either relabel the reported quantity as a proposal-stage measure, or
recompute on the executed action — but the current wording says one and reports the other, and this
also violates the project's own EXECUTED-ONLY rule. Add the sentence:

> The action recorded for each agent-year is the last action the agent proposed that year. Where a
> proposal was rejected and the retry budget was exhausted, the agent's request did not move and the
> domain default executed, so AAI as defined here is a property of proposed actions.

**M3 — Reword the abstract and intro claims from causal to descriptive, and add the identified
companion number.** `drafts/abstract_v16.md:18` ("institutional rules reduced appraisal-action
inconsistency from 59.1% to 36.1%") and `drafts/introduction_v16.md:37`. The rates themselves
reproduce exactly and may stand as descriptions of each arm's record; "reduced" is a causal verb
attached to a non-identified contrast. Recommended: keep the two rates, attach the unconditional
−21.6 pp as the effect claim.

**M4 — Cut or fully rebuild the R2 quadrant paragraph.** `drafts/section2_v19_results.md:46` — seven
numbers (49.7 / 69.3 / 53.5 / 70.5 / 31.7 / 7.9 / 28.9), every one a rate inside a cell of a
*doubly* post-treatment grid (WSA x ACA, both model outputs). Cell membership is treatment-determined,
so "the governance effect was largest at moderate scarcity (31.7 pp)" is a statement about a cell
whose population governance chose. This cannot be repaired by hedging. Same for the two claims that
carry it forward: `drafts/section3_v17_discussion.md:29` (the "non-compliance signature" observable)
and `drafts/section3_v17_discussion.md:39` (the CRSS / compact-negotiation policy prescription).
**The policy prescription is the most damaging item to leave unqualified** — it recommends monitoring
a quantity computed inside a composition-contaminated contrast.

**M5 — Drop or reframe the 40% null comparison.** `drafts/section2_v19_results.md:21` compares the
no-validator rate to "a 40% null expectation under uniform random action selection". A within-
denominator null is only interpretable if the denominator is the same population in both arms, which
is precisely what is in dispute. The same paragraph's "arbitrary vs adaptive diversity" argument at
`:25` rests entirely on the conditional rate; EHE itself is denominator-free and survives, its
*interpretation* does not.

**M6 — Fix the SI's internal contradiction and add the composition caveat there.**
`drafts/supplementary_information_v15.md:524` (Note 5) states the conditional definition correctly
and is the only place in the paper that does; `:721` (Note 8) still states an *unconditional*
denominator ("divided by the number of active agent-year observations") and contradicts it in the
same document. Fix Note 8. Then add to Note 5 or Note 6 the fact that the conditioning variable is
an intervention outcome, with the 37.1 / 82.8 shift and the unconditional companion. The existing
hook is at `:805`, where the SI already uses a composition argument to explain away the Gemma-4 e2b
null — it should be generalised into a stated limitation rather than used only where it is convenient.

**M7 — Report the unconditional rate alongside AAI in Extended Data Table 1.**
`drafts/section2_v19_results.md:35` and its footnote at `:38`. One extra row: unconditional increase
rate 40.9 / 62.5, difference −21.6 pp. This is the cheapest single change that pre-empts the whole
critique, and it is the number a reviewer will otherwise compute themselves.

### SHOULD

**S1 — State the cross-model collapse.** The magnitude that survives de-conditioning is 93.9% on the
anchor, 80.5% (e2b), 48.9% (e4b), **1.4%** (12b), and the sign flips on ministral-3:8b
(`e1_total_effect.py`). Any sentence claiming the irrigation mechanism generalises across models must
carry this. Note also that gemma3:12b has only 3 seeds in both arms (df = 2) and ministral-3:8b is
unbalanced (3 governed vs 2 ungoverned) — `seed_inventory.csv`.

**S2 — Report the governed arm's collapse onto the default action, in both directions.** Executed
`maintain_demand` is 94.42% governed vs 45.88% no-validator, and executed *decreases* fall from
20.21% to 1.89% (`_verify_e2_stratified.py`). The paper currently reports the favourable half of a
two-sided collapse to inaction. A reviewer who finds this unaided will ask whether a rule stack that
suppresses voluntary demand reduction by 18 pp is a governance benefit.

**S3 — Add the year-1 null as a Supplementary Note.** It is a genuinely good result and it is the
paper's honest answer to "is this an instantaneous reasoning effect or a cumulative system effect":
at the one decision where the two worlds are bit-identical, the conditional gap is +1.15 pp
(p = 0.616), the unconditional gap −1.28 pp (p = 0.089), the matched-denominator gap −4.37 pp
(p = 0.346), and the appraisal shift −3.33 pp (p = 0.261). The 42-year effect is cumulative, and
saying so is more defensible than implying it is immediate.

**S4 — Regenerate the affected display items and fix three known inconsistencies.**
`paper/nature_water/scripts/gen_fig3_crossmodel.py` (Supplementary Figure 1, irrigation panel is the
conditional rate at lines 159-167); Figure 3 panel b cell colour (`gen_fig3_case2_flood.py`, and the
v50 Fig 3 caption P33). Then: (i) `paper/nature_water/scripts/compile_paper.py:520-527` hardcodes a
Fig 2 caption quoting **51.2%** where `section2_v19_results.md:46` says **49.7%** and the live figure
plots neither (panel b is the demand ratio); (ii) `methods_v7.md:105` says eight of nine flood
reductions are significant, SI v22 says nine of nine; (iii) EDT2 at `section2_v19_results.md:72-78`
still carries flood 0.9 / 8.5 while the SI has moved to the conditional 1.6 / 14.2. **Do not run
`paper/nature_water/scripts/gen_sfig_forest.py`** — PAPER_ASSETS.md:61 records that it writes the
same output filename as the adopted SuppFig 1 using the old unconditional denominator.

**S5 — Disclose the flood arms' asymmetric appraisal instrument.**
`drafts/supplementary_information_v15.md:742`: the no-validator flood arm's threat appraisal is
inferred by a keyword classifier with a *relaxed* low-threat threshold {L, VL, M} while the
with-validators arm uses the strict {L, VL}. In flood the conditioning variable is not merely
treatment-affected, it is **measured with a different instrument in the two arms**. The SI presents
this as a robustness accommodation; it is a validity threat and must be labelled as one. (This does
not appear to apply to irrigation, where `wsa_label` is a first-class logged column in both arms —
confirmed empirically: `simulation_log.wsa_label` and audit `construct_WSA_LABEL` agree on 100.00%
of 32,760 anchor row-pairs, `linkage_check.py`.)

**S6 — Fix the provenance record for the anchor runs.** `git_dirty = True` on every anchor run that
records it; seeds 45 and 46 carry a degraded 5-key manifest with no `git_commit`, `config_hash` or
`model_digest`; seeds 43 and 44 record *different* commits for the two arms (the committed diffs over
`broker/` and `examples/irrigation_abm/` are empty, so this is a documentation defect, not a
confound); and `psychological_framework: cognitive_appraisal` is present in the seed 42/43/44 config
snapshots and absent from 45/46, where the code silently defaults to PMT
(`broker/config/agent_types/base.py:269`). The drift is symmetric across arms so the paired contrast
is unaffected, and the headline is *stronger* on the three fully-provenanced seeds (−23.60 pp,
t = −22.618, df = 2, p = 0.00195) — but a Data Availability statement should not claim more than
this. Source: `_verify_e1_total_effect.py`.

### OPTIONAL

**O1** — Report the matched-denominator estimates as a robustness footnote: −20.38 pp full-run,
−4.37 pp at year 1, both with the "matched-cell, not identified" caveat from §4.

**O2** — Run the frozen-world arm described in §6. It is the only thing that separates premise
revision from veridical re-appraisal, and it would convert this memo's honest "cannot distinguish"
into a result.

**O3** — Fix the two verifier-identified code defects before anyone reuses these scripts:
`e4_bounds.py` `lee_stratified` assigns a zero-width point to monotonicity-violating cells (should be
[0,1] like the empty cells two lines above), and `e2_stratified.py` `invert_precip` tests a float
clip by exact equality with 0.0, one ULP away from fabricating an exogeneity failure.

---

## 8. What a reviewer could still attack after all of this

Assume every action above is taken. These remain, and they are not small.

1. **The identified estimand is not the one the paper is about.** −21.6 pp is a total regime effect
   that includes the reservoir feedback: part of it is agents reacting to a river governance made
   fuller. A reviewer can say, correctly, that the paper's contribution claim is about the cognitive
   layer and the only identified number is about the water.
2. **The anchor is the best cell in the corpus and the paper publishes the anchor.** 1.4% survival on
   gemma3:12b and a sign flip on ministral-3:8b are on the record now. "The effect generalises across
   model scales" is not supportable for the irrigation mechanism.
3. **n = 5 is five language-model resamples, not five worlds.** The agent population is identical
   across seeds and precipitation is a fixed exogenous trace identical across seeds and arms. Every
   CI in this memo is a resample interval. A reviewer can ask what happens with a different 78-agent
   draw or a different hydrology, and we have no answer.
4. **The treatment is partly defined as blocking the outcome.** The rules are literally named
   `high_threat_high_cope_no_increase`, `low_threat_no_increase`, `supply_gap_block_increase`, and
   94.6% of governed rejections land on increase proposals. "Validators reduce increase propensity"
   is close to "the rule named no-increase was enforced". The paper needs to be explicit about what
   is a finding and what is a tautology.
5. **The governed arm may be degenerate rather than well-behaved.** 94.4% executed
   `maintain_demand`, executed decreases down from 20.21% to 1.89%.
6. **The two arms' rejection mechanisms are not comparable.** Governed rejections are validator
   rejections with retries exhausted; the no-validator arm's 29.04% "REJECTED" rows are skill
   *precondition* failures (`not at_allocation_cap`), a world affordance, and that rate is 29.04% on
   the anchor against 1.46-5.33% in the other balanced cells (`linkage_check.py`). The anchor's
   asymmetry is a property of the published pair specifically.
7. **The flood placebo is low-dose, not zero-dose, and the defect scales with dose.** Spearman
   ρ = 0.867 (p = 0.0025) between rule-firing rate and appraisal shift across 9 flood cells implies
   the composition problem is not absent in flood, only small because enforcement is light — and
   therefore that it is large in irrigation *because* enforcement is heavy. Six of those nine cells
   are the degraded unbalanced ones, so this is suggestive, not confirmatory.
8. **The bounds are uninformative once the coding defect is fixed.** The year-stratified Lee interval
   includes zero after violating cells are widened correctly ([−45.86, +1.90]).
9. **Multiplicity.** `e5_year1.py` runs 126 paired t-tests across the trajectory and stars 92 of them
   with no correction; anything quoted from the trajectory must be labelled descriptive.
10. **The published flood AAI has a third definition problem of its own.** Three different flood
    statistics exist in the record — 0.87 / 7.41 (unconditional), 1.60 / 14.22 (conditioned on
    TP not medium, the SI v21/v22 numbers), 2.51 / 22.56 (conditioned on TP high) — and the flood
    conditioning set is "not medium", which is a looser and different post-treatment conditioning
    than the irrigation one (`_verify_e6_flood_placebo.py`). Any cross-domain sentence that calls
    both "AAI" needs to say which denominator each uses.

---

## 9. Reproduction

From the repo root, `C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework`. All scripts are
read-only with respect to `examples/` and exit 0. Estimators write their CSVs into
`SUBMISSION_2026/decomposition/`; verifiers write nothing but stdout.

```bash
# Phase 2/3 -- corpus inventory, reproduction of the published pair, file linkage
python SUBMISSION_2026/decomposition/_loader.py            # self-test: 41 runs, 3276 rows each
python SUBMISSION_2026/decomposition/reproduce_published.py
python SUBMISSION_2026/decomposition/linkage_check.py --model ALL
python SUBMISSION_2026/decomposition/seed_inventory.py

# Phase 1 -- what may be conditioned on
python SUBMISSION_2026/evidence/exogeneity_check.py

# The six estimators
python SUBMISSION_2026/decomposition/e1_total_effect.py
python SUBMISSION_2026/decomposition/e2_stratified.py
python SUBMISSION_2026/decomposition/e3_decomposition.py
python SUBMISSION_2026/decomposition/e4_bounds.py
python SUBMISSION_2026/decomposition/e5_year1.py
python SUBMISSION_2026/decomposition/e6_flood_placebo.py

# The six independent verifiers (pandas/numpy/scipy; none imports _loader)
python SUBMISSION_2026/decomposition/_verify_e1_total_effect.py
python SUBMISSION_2026/decomposition/_verify_e2_stratified.py
python SUBMISSION_2026/decomposition/_verify_e3_decomposition.py
python SUBMISSION_2026/decomposition/_verify_e4_bounds.py
python SUBMISSION_2026/decomposition/_verify_e5_year1.py
python SUBMISSION_2026/decomposition/_verify_e6_flood_placebo.py
```

Headline lines to check on re-run:

| Command | Line to grep | Expected |
|---|---|---|
| `e1_total_effect.py` | `E1 TOTAL EFFECT` | `-21.62 pp (95% CI -26.80 .. -16.45; paired t = -11.608, df = 4, p = 0.000315)` |
| `e2_stratified.py` | `standardized difference` | `-21.21 pp (95% CI -26.23 .. -16.18), paired t = -11.71, df = 4, p = 0.000304` |
| `e3_decomposition.py` | `COMPOSITION component (symmetric)` | `6.343 pp 95% CI [4.694, 7.993] t=10.677 df=4 p=0.0004` |
| `e4_bounds.py` | `identified set for the MEAN effect` | `[-30.49, -9.68] pp` (sharp, under monotonicity) |
| `e5_year1.py` | `MEAN GAP` under `CONDITIONAL IBR` | `1.15 pp 95% CI [-4.71, 7.00] t = 0.543 df = 4 p = 0.615680` |
| `e6_flood_placebo.py` | `flood COMPOSITION (PRIMARY)` | `n=3 +1.39 pp 95% CI [-1.48, +4.27]` |

All six were re-run for this memo and all six matched.

---

*Every number in this memo comes from one of the scripts named beside it. No number was carried over
from the task brief, estimated, or interpolated. Where an estimator's own summary label disagrees
with its verifier, the verifier's judgement is reported and the disagreement is left visible.*
