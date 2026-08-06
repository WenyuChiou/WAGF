# Pre-registration — Decomposing a governance conformance gain

**Document version 1.0 · written 2026-07-29 · Lehigh University**
**Status at time of writing: ZERO runs of the instrument against a real LLM have been executed. All data described below does not yet exist.**

This document is committed before the queue starts. Its git commit hash and commit timestamp are the timestamp of record. The release tag from which every run in this study executes is created *after* this commit and its message references this commit's hash; the tag hash is recorded in §13 by amendment, which is the only entry §13 may contain that is not a deviation.

The reason this document exists is specific and unflattering. This group has a recorded incident in which a validation index (EPI) was demoted from a pass/fail gate to a "descriptive fingerprint" after both candidate models failed it. A reviewer who finds that pattern is entitled to discount every subsequent claim. The defence is not a promise; it is a timestamp. Accordingly: **no outcome, threshold, exclusion, or interpretation defined below may be redefined, re-scoped, softened, or demoted after any data exists. An outcome that fails is reported as failed, in the paper, in the position it was pre-registered to occupy.**

---

## 1. What is already established, and what is not

Two things are already on disk and were verified against code and data before this document was written. They are the premise of the experiment, not part of it.

**Established (14 model × testbed cells, zero GPU, reproducible via `AAMAS2027/experiments/appraisal_composition.py`).** Enforcing a behavioural-theory norm changes the agent's self-reported appraisal — the same variable the conditional conformance statistic conditions on. In the high-enforcement regime (irrigation, 5 cells, 28.1–62.6 % of decisions rejected) the prevalence of the conditioning appraisal shifts by +38.13 pp on average (range +21.26 to +47.53, 5/5 positive). In the low-enforcement regime (flood, 9 cells, 0.00–0.85 % rejected) it shifts +0.81 pp on average (range −3.69 to +6.25). The separation is complete: the minimum high-regime shift (+21.26) exceeds the maximum low-regime shift (+6.25). Flood is a natural control — same harness, same governance code, same audit path, loose rules — so the null there rules out an artifact of the instrument.

The consequence is that the standard conditional conformance statistic conditions on a **post-treatment** variable. For irrigation gemma3:4b the published pair is governed 36.05 % versus ungoverned 59.07 % (Δ +23.02 pp, 5 seeds), while the prevalence of the denominator differs across those same two arms by 45.50 pp. Separately, re-deriving the same metric on the *executed* rather than the *labelled* action moves those levels to 0.86 % and 26.77 % (Δ +25.90 pp): the direction survives, the levels do not.

**Not established, and the reason for this study.** Two mechanisms produce that table and the shipped corpus cannot separate them.

- **(a) Premise revision.** Told that its action violates a rule predicated on a high appraisal, the agent restates the appraisal as lower; the same action then passes.
- **(b) Selection.** Agents reporting a high appraisal trip the rule more often, retry more, and are therefore a non-random subsample of decisions.

Retry-stratified appraisal is non-monotone (0 retries: 23.88 % high; 1: 57.58 %; 2: 58.08 %; 3: 39.38 %), which is consistent with both. The first-attempt appraisal is unrecoverable from the shipped corpus because the proposal object is overwritten on every governance retry — `proposed_skill == final_skill` on 100 % of rows in all three domains.

**The instrument built this week makes the separation possible and has never been run against a real LLM.** It is committed, tested against a mock LLM only, default-OFF, and byte-identity-verified: an ADVISE disposition (a rule surfaced to the model without blocking, at exactly one extra LLM call, so the advise arm is sample-matched against a content-free placebo); `initial_proposal_columns` (first-attempt skill, first-attempt construct labels, and the per-attempt skill list); `executed_skill_columns`; a per-decision `llm_calls` counter; `intervention_framing: neutral`; `on_retry_exhausted`; `require_profile`; and manifest recording of `advise_spec_resolved` / `intervention_framing_resolved` / `max_retries_resolved`.

---

## 2. The claim under test

> **Central claim.** The conformance gain reported by the standard conditional statistic when a behavioural-theory norm is enforced on an LLM agent is a **composite**. It contains (i) genuine action revision, (ii) premise revision — movement in the self-reported state the metric conditions on, and (iii) filtering — decisions whose executed action is a system default rather than an agent choice. In the tested cells, components (ii) and (iii) are large enough that the standard statistic materially overstates behaviour change; and the arm ladder below separates them.

This is falsifiable. §12 states exactly how, with numeric thresholds fixed here.

---

## 3. Testbed, arms, and frozen configuration

### 3.1 Testbed

Primary testbed: **`examples/single_agent` flood, 100 agents × 10 years = 1,000 decisions per run.** (The README's "13 yr" for this case study is wrong and is corrected in the paper.) Action space: `buy_insurance`, `elevate_house`, `relocate`, `do_nothing`. Registry default skill: `do_nothing`. Appraisal constructs: `TP_LABEL` (threat), `CP_LABEL` (coping), on the ordinal scale {VL, L, M, H, VH}.

Flood, not irrigation, is primary. It is the low-enforcement regime, which means the decomposition is measured where the standard statistic looks *cleanest*. If the composite structure appears there it appears anywhere; if the paper's motivating case (irrigation) were used as the primary testbed a reviewer would correctly say the result was selected on the outcome.

### 3.2 Rule sets — fixed now, not later

From the shipped `strict` profile in `examples/single_agent/agent_types.yaml`:

| set | rule ids | role |
|---|---|---|
| **E — enforced / advised** | `extreme_threat_block` (TP ∈ {H,VH} blocks `do_nothing`), `relocation_threat_low` (TP ∈ {VL,L} blocks `relocate`), `elevation_threat_low` (TP ∈ {VL,L} blocks `elevate_house`) | the three ERROR thinking rules; the primary outcome is defined on these |
| **H — held out, scored in every arm, enforced in none** | `low_coping_block` (CP ∈ {VL,L} blocks `elevate_house`, `relocate`) | shipped at level WARNING, and a WARNING has no channel to the model in this implementation; therefore it is inert by construction and is a free held-out rule inside the same runs |
| **HARD — never scored, always enforced** | `elevation_block` (identity rule: cannot elevate an already-elevated house), plus the framework Tier-0 floor (output schema, skill membership, precondition, affordability) | world affordance, not behavioural theory; `affordability`, `precondition_violation` and `output_schema_violation` are in `ADVISE_DENY` and cannot be advised even if listed |

Rules classified AMBIGUOUS in `AAMAS2027/experiments/RULE_CLASSIFICATION.md` are excluded from every scored set. The unclassified custom validators (`validate_flood_zone_appropriateness`, `validate_buyout_repetitive_loss`, `validate_elevation_justification`, `validate_insurance_access_barriers`) live in the **multi-agent** flood runner, which is out of scope for this paper. The primary testbed is therefore fully classified and the arm definitions are frozen.

`low_coping_block` is **not** promoted to ERROR. Promoting it would raise enforcement pressure and change the testbed away from the published system. Its inertness is reported as a finding, not repaired.

### 3.3 The arm ladder

Each consecutive pair differs in exactly one thing. That is the only reason any term is identified.

| arm | one-line definition | config |
|---|---|---|
| **A** | no theory rules; HARD rules and Tier-0 stay on | new profile `no_theory`: `thinking_rules: []`, `identity_rules: [elevation_block]`. **Not** the shipped `disabled` profile, which also drops `elevation_block` and would let the ungoverned arm re-elevate an elevated house |
| **A′** | + one extra call, zero added text | `advise: {mode: resample, rule_ids: E}` |
| **A″** | + wrapper and position | `advise: {mode: wrapper, rule_ids: E}` |
| **B′** | + generic corrective pressure | `advise: {mode: placebo, rule_ids: E, placebo_text: "A governance rule was triggered by this decision."}` |
| **B** | + rule content | `advise: {mode: advise, rule_ids: E}` |
| **C1** | + enforcement | no `advise:` block; `max_retries: 1`; `on_retry_exhausted: default` |
| **C3** | the deployed system | as C1 with `max_retries: 3`; **reported separately, never inside the additive decomposition** |
| **S-enf / S-adv** | sham theory, paired | profile `sham`: the three E rules with their construct bands inverted (TP ∈ {VL,L} blocks `do_nothing`; TP ∈ {H,VH} blocks `relocate` and `elevate_house`). Syntactically identical, coherent, anti-theoretical, and definable without looking at any data |

Shared by every arm: `audit.executed_skill_columns: true`, `audit.initial_proposal_columns: true`, `audit.advise_columns: true`, `governance.max_reports_per_retry: 20`, `governance.intervention_framing: neutral`, `require_profile: true`. Seeds 42, 43, 44, 45, 46 for every arm and every model. Models, in fixed queue order: gemma3:4b, ministral3:3b, ministral3:8b, gemma3:12b.

C1 rather than C3 carries the decomposition because at `max_retries: 3` the enforce arm makes up to three extra calls where advise makes one, so (C−B) would confound enforcement with extra sampling — the exact confound the placebo arms exist to remove.

`on_retry_exhausted: keep_proposal` is **not** used anywhere in this study. What the agent would have done had it not been overwritten is recovered from `attempt_skills`, so no additional arm is needed and no additional confound is introduced.

---

## 4. Primary outcome

**V — the executed-action theory-violation rate on set E, with the rule antecedent evaluated on the first-attempt appraisal.**

The design turn is here. The antecedent is read from **attempt 0**, which is drawn before any rule text exists in the prompt in *every* arm (the base prompt is identical across arms; governance profiles configure validators, not prompt templates). Attempt 0 is therefore pre-treatment. The consequent is read from the **executed** action. V is by construction immune to premise revision: an agent that restates its appraisal so the rule no longer applies still counts as violating under V. That is what makes V, and not the standard statistic, the outcome a decomposition can be built on.

### 4.1 Computation, per run

Two analysts implementing the following independently must obtain the same number.

1. Read the run's single `*governance_audit.csv` with `encoding="utf-8-sig"`.
2. Assert these columns exist, else the **run is excluded** (§10): `agent_id, year, seed, status, retry_count, initial_skill, initial_labels, attempt_skills, executed_skill, executed_via_fallback, llm_calls, construct_TP_LABEL, construct_CP_LABEL, advise_mode, advisory_fired, advisory_llm_calls, advisory_parse_failed, advisory_reports_shown`.
3. `TP0` := the value of key `TP_LABEL` parsed from `initial_labels`, which is a pipe-joined list of `KEY=VALUE` pairs. Strip, uppercase. If the key is absent or the value is not in {VL, L, M, H, VH}, the row is `UNPARSABLE_0` — excluded from the denominator, counted, and carried into the bounds analysis of §9.4.
4. `at_risk` := `TP0 ∈ {VL, L, H, VH}`. Rows with `TP0 = M` are at risk of no rule in E; they are excluded from the primary denominator and reported separately as a descriptive.
5. `a_exec` := `executed_skill`, stripped and lowercased. Must be one of {`buy_insurance`, `elevate_house`, `relocate`, `do_nothing`}; otherwise the row is `UNPARSABLE_EXEC`, handled as in step 3. **Do not use `final_skill`.** On a REJECTED decision `final_skill` records the blocked proposal while the registry default actually executed; that discrepancy is worth up to 35 pp of level and is the reason `executed_skill_columns` exists.
6. `violation(TP, a)` := 1 if (`TP ∈ {H,VH}` and `a = do_nothing`) or (`TP ∈ {VL,L}` and `a ∈ {relocate, elevate_house}`); else 0.
7. **V(run) = Σ violation(TP0, a_exec) / Σ at_risk**, over rows surviving steps 3 and 5.

Rejected rows are **not** dropped, and they are **not** counted by their blocked proposal. They enter the denominator and their executed action is the registry default `do_nothing`. Note the consequence, which is pre-registered as an expectation rather than discovered later: on a `TP0 ∈ {H,VH}` row, retry exhaustion executes `do_nothing`, which is *still a violation of `extreme_threat_block`*. Filtering in this testbed does not automatically manufacture conformance; its sign is rule-dependent. On a `TP0 ∈ {VL,L}` row, exhaustion executes `do_nothing`, which conforms.

### 4.2 Primary contrast

**V(A) − V(C1)**, per model configuration, paired on seed. Positive = enforcement reduced the premise-invariant violation rate.

### 4.3 Two windows, both always reported

Agent trajectories diverge across arms after year 1, because the arm changes the action which changes the state which changes the next decision. The at-risk denominator is therefore itself arm-dependent from year 2 onward — a trajectory-level version of the same post-treatment problem the paper is about. It would be dishonest to pre-register only the convenient window.

- **V_pooled** — all 10 years. Well powered, confounded by trajectory divergence.
- **V_y1** — year 1 only, the single year whose state distribution is arm-independent by construction. Identified, and thinly powered (≈100 decisions per run, ≈500 per arm-cell before the at-risk filter).

Both appear in the main table, side by side, in every cell. **If V_pooled and V_y1 disagree in sign for the primary contrast, V_y1 is the identified estimate and leads the paper; V_pooled is reported as the biased one.** This rule is fixed now precisely because it is the one that will be tempting to invert later.

---

## 5. Secondary outcomes

**S1 — V_final, the standard statistic.** Identical to V except the antecedent is read from `construct_TP_LABEL` (the final, post-treatment proposal's label). This is the number the literature reports. Reporting V and V_final together is the paper's central table.

**S2 — Γ, composition inflation.** `Γ(X) = V(X) − V_final(X)`, in pp. `Γ(A) = 0` exactly by construction, because arm A makes one call and no revision is possible.

**S3 — the mechanism partition.** Over at-risk rows on which attempt 0 violated (`violation(TP0, initial_skill) = 1`), with `a0 = initial_skill`:

| class | definition | reading |
|---|---|---|
| **FILTER** | `executed_via_fallback = True` (equivalently `status = REJECTED_FALLBACK`) | not an agent choice at all |
| **ACTION_REV** | `a_exec ≠ a0` and `violation(TP0, a_exec) = 0` | genuine behaviour change, robust to premise movement |
| **PREMISE_REV_PURE** | `a_exec = a0` and `violation(TP_final, a_exec) = 0` | same action; only the reported premise moved, and the move is exactly what makes it pass |
| **JOINT** | `a_exec ≠ a0`, `violation(TP0, a_exec) = 1`, `violation(TP_final, a_exec) = 0` | action and premise both moved; passes only under the new premise |
| **PERSIST** | `violation(TP0, a_exec) = 1` and `violation(TP_final, a_exec) = 1` | unmoved |

These five are mutually exclusive and exhaustive over that row set. §6, identity 3.

**S4 — held-out conformance.** Violation rate on rule set H (`low_coping_block`: `CP0 ∈ {VL,L}` and `a_exec ∈ {elevate_house, relocate}`), with `CP0` read from `initial_labels`, denominator `CP0 ∈ {VL,L}`. Reported for arms A, B, C1. This rule is scored in every arm and enforced in none, so improvement on it cannot be definitional. It also generalises across a *different construct* (coping, not threat), which is a stronger test than a within-construct split.

**S5 — reciprocal enforced/held-out splits over E** (secondary confirmation of S4). Split S1: enforced {`extreme_threat_block`, `relocation_threat_low`}, held out {`elevation_threat_low`}. Split S2: the reciprocal. Both splits run, because one split invites "you held out the easy rule." Arms A, B, C1 only, two models, three seeds.

**S6 — enforcement pressure and regime placement.** Per arm: share retried, share REJECTED, share REJECTED_FALLBACK, mean `retry_count`. Descriptive, reported whatever it is, never a gate.

**S7 — sham contrast.** Conformance gain achieved on whichever set is enforced, real (E, arms B/C1) versus sham (arms S-adv/S-enf, scored on the sham set). Realised trigger-rate difference between real and sham reported as a caveat.

**S8 — call accounting.** Per-decision `llm_calls` distribution by arm; `advisory_llm_calls`; `advisory_reports_shown` (to prove truncation never bound); `advisory_parse_failed` rate.

**S9 — the executed-versus-labelled artifact size** across the existing corpus, per model, as motivating evidence only (already computed: 1.30 pp for ministral3:8b to 22.54 pp for gemma4:e4b). Legacy data, descriptive, no inferential claim.

---

## 6. The three identities

**Identity 1 — the arm ladder.** In pp of V, per model configuration:

```
V(A) − V(C1)  =  [V(A) −V(A′)]   G_sample     one extra draw, no added text        A → A′
               + [V(A′)−V(A″)]   G_wrapper    scaffolding and prompt position      A′ → A″
               + [V(A″)−V(B′)]   G_pressure   generic corrective pressure          A″ → B′
               + [V(B′)−V(B) ]   G_content    RULE CONTENT                         B′ → B
               + [V(B) −V(C1)]   G_enforce    ENFORCEMENT                          B → C1
```

**Identity 2 — composition.** Since `Γ(A) = 0`:

```
standard-statistic gain   V_final(A) − V_final(C1)  =  [V(A) − V(C1)]  +  Γ(C1)
                                                       premise-invariant   composition
                                                       gain                inflation
```

**Identity 3 — the mechanism partition.** Within each arm, over at-risk rows on which attempt 0 violated:

```
1 = p_FILTER + p_ACTION_REV + p_PREMISE_REV_PURE + p_JOINT + p_PERSIST
```

and the components attributable to rule content and to enforcement are `p_k(B) − p_k(B′)` and `p_k(C1) − p_k(B)` respectively, for each class k.

**On summation, stated in advance because the question was asked.** Identities 1 and 2 are **exact by construction** — 1 telescopes, 2 is definitional. They cannot fail to sum, and a paper that presents their summation as a result would be presenting arithmetic as evidence. Identity 3 is a partition of a finite row set and must sum to 1.0000; **if it does not, that is a bug in the analysis code or the audit writer, not a finding. Analysis halts, the bug is fixed, and the fix is logged in §13 before any interpretation resumes.**

What *can* fail in identities 1 and 2 is not summation but **identification**, and it fails in exactly three ways, each with a pre-registered test in §9: unmatched sampling between B and B′ (voids `G_content`); a non-neutral framing resolved in any of A″/B′/B/C1 (voids `G_content` and `G_enforce`); and order dependence. The ladder is a single-order, path-dependent attribution, not a set of orthogonal causal effects, and the paper says so in those words. The pre-registered order-sensitivity guard is `|G_wrapper| = |V(A′) − V(A″)|`: if it is below 2 pp in at least 3 of 4 configurations, the placement of the wrapper step relative to the content step cannot materially change the attribution, and the single-order presentation stands. If `|G_wrapper| ≥ 2 pp` in two or more configurations, the ladder terms are reported as **order-dependent attributions with the order named in the caption**, and the paper states that a different order would yield different term sizes. Under no circumstance is the ladder re-ordered after seeing which order gives a cleaner story.

---

## 7. Statistical model

**Unit of analysis is the SEED for a per-cell claim and the model CONFIGURATION for a scale claim.** These are not interchangeable and are never pooled into a single test.

**Per-cell claims** (one model × one testbed: "in this cell, enforcement reduced V by x pp"). Unit = seed, n = 5. Arms are paired within seed: the same seed produces the same agent initialisation across arms, so seed-level differencing removes initialisation variance. Test: paired *t* on the seed-level arm difference, df = 4, two-sided, with Wilcoxon signed-rank as a robustness check. **Stated up front, not in a footnote: with n = 5 the exact sign-flip permutation floor is 2⁻⁵ × 2 = 0.0625, so no single 5-seed cell can reach p < 0.05 by permutation.** The paper reports seed-level means with their 95 % *t* CIs and the permutation floor, and does not hide behind the parametric p-value. Multiplicity: within a configuration the five ladder terms are one family, Holm-corrected; the primary contrast V(A) − V(C1) is outside that family and uncorrected.

**Decision-level precision** (not for the scale claim). Logistic GLMM on at-risk rows: `violation ~ arm + (1 | seed) + (1 | seed:agent_id)`, fitted per configuration. Used for interval width on the arm terms. Because trajectory divergence makes post-year-1 rows arm-dependent, the GLMM is fitted separately on the pooled and year-1 windows and both are reported.

**Scale claim** (does the *composition* of the gain change with model size). Unit = configuration, n = 4. `V ~ arm × log(parameters) + (1 | config) + (1 | seed)`. **With four configurations this is under-powered for an interaction and is pre-registered as EXPLORATORY. It is labelled exploratory in the paper regardless of the p-value obtained, including if p < 0.001.** What is reported is the point estimates, their CIs, and the sign pattern across the four configurations. A monotone sign pattern across 4/4 configurations is reported as suggestive and nothing stronger.

**Equivalence.** Where the pre-registered interpretation depends on a term being *absent* rather than merely non-significant, absence is established by two one-sided tests at the seed level with an equivalence margin of **±5 pp**, chosen because observed seed-level standard deviations in this corpus run 1.7–3.6 pp, so 5 pp is 1.4–2.9 SD. "Not significant" is never reported as "no effect."

---

## 8. Pre-stated interpretation of every branch

Written before the data exists. Each row is what the paper says if that branch occurs, in the position where the headline would otherwise go.

| branch | pre-stated reading |
|---|---|
| **Premise revision dominant** — `Γ(C1) ≥ 10 pp` and `p_PREMISE_REV_PURE + p_JOINT > p_ACTION_REV` in ≥3/4 configs | The central claim holds in its strongest form. A conformance number computed on the standard conditional statistic is substantially an artifact of movement in the conditioning variable. The recommendation is concrete: report the premise-invariant statistic V, and report `Γ` alongside it. The published irrigation levels, and any comparable literature number, are overstated by roughly `Γ`. |
| **Action revision dominant** — `p_ACTION_REV` is the largest class and `Γ(C1)` is within ±5 pp of zero by TOST in ≥3/4 configs | Enforcement induces genuine behaviour change and the standard statistic is approximately clean *in this regime*. The central claim as written is **false** and is reported as falsified. The paper becomes: a measurement design that could have found contamination, applied honestly, finding little — with the workshop paper's high-enforcement regime as the boundary condition where the same instrument must be re-applied. This is a smaller paper. It is still an honest one, and it is submitted. |
| **Filtering dominant** — `p_FILTER` is the largest class in ≥3/4 configs | Most of the "governed behaviour" was never chosen by the agent. The reported gain is an artifact of what executes when retries are exhausted, and its sign depends on whether the registry default happens to satisfy the rule — which in this testbed it does for the low-threat rules and does **not** for `extreme_threat_block`. The paper reports the executed-action correction as the headline and states that any conformance number computed without an executed-action column is uninterpretable. |
| **Null** — `V(A) − V(C1)` within ±5 pp of zero by TOST in ≥3/4 configs | Enforcement did not change the premise-invariant violation rate at all, and every reported gain in this testbed was composition plus filtering. This is a strong and publishable negative result and is written as the headline, not the limitations section. |
| **Direction reversal** — any ladder term negative beyond −5 pp | Named explicitly and interpreted, not smoothed. `G_sample < 0`: a second draw makes conformance worse, i.e. resampling degrades the decision. `G_pressure < 0`: content-free corrective pressure makes conformance worse — the model responds to being challenged by moving away from the norm. `G_content < 0`: showing the rule makes violation more likely, which would be the most interesting single result in the study and would be reported as the headline. `G_enforce < 0`: blocking makes the executed action worse than advising, which given the `do_nothing` default is a mechanism the paper can name concretely. |
| **Terms do not sum** | Impossible for identities 1 and 2 (see §6). For identity 3 it is a bug: halt, fix, log, resume. Never reported as a finding. |
| **Order sensitivity** — `\|G_wrapper\| ≥ 2 pp` in ≥2 configs | Ladder terms are reported as order-dependent attributions with the order stated in the caption, and the paper says a different order would give different sizes. The ladder is not re-ordered. |
| **Held-out improves** — S4 violation rate lower under C1 than under A beyond the 5 pp margin | The mechanism induces behaviour that generalises to a rule it was never enforced on, across a different construct. This is the answer to the circularity objection and is reported as such. |
| **Held-out does not improve** | The mechanism is a filter, not an inducer, and the headline conformance number is definitional over the enforced set. This is the more interesting of the two outcomes and is written as the headline if it occurs. |
| **Sham matches real** — gain on the sham's own set within 5 pp of gain on E | What is being measured is compliance with *any* enforced coherent rule, not with behavioural theory. Every "theory" framing is struck from the paper and replaced with "enforced constraint." |
| **V_pooled and V_y1 disagree in sign** | V_y1 leads; V_pooled is reported as trajectory-confounded. Fixed here (§4.3). |
| **Balance check fails** (§9.1) | The design is void. No decomposition claim is made from the affected configuration. See §12, F2. |

---

## 9. Validity checks, run before any outcome is computed

These are computed first, on operational columns only, and their results are reported in the paper whether or not they pass.

**9.1 Attempt-0 balance (the randomisation check).** Attempt 0 is pre-treatment, so the prevalence of `TP0 ∈ {H,VH}` must not differ across arms within a configuration beyond seed noise. Test: one-way analysis on seed-level prevalences across the six ladder arms. **Threshold: max pairwise arm difference < 5 pp.** If it exceeds 5 pp, either the base prompt is not identical across arms or treatment has leaked into attempt 0; the configuration is void for the decomposition. Additionally, a byte-comparison assertion that the attempt-0 prompt string is identical across arms for a matched (seed, agent, year=1) triple is run once per configuration as a hard gate.

**9.2 Call matching between B and B′.** `llm_calls` per decision must match. **Threshold: median difference ≤ 0.05 calls/decision and a two-sample KS test on the per-decision distributions not rejecting at p < 0.01.** Failure voids `G_content`, which is then reported as "not identified" rather than as a number.

**9.3 Manifest conformance.** For every run: `git_dirty = false`; commit hash equals the study tag; `governance_profile` resolved equals the arm's declared profile (a misspelled `GOVERNANCE_PROFILE` falls back silently to `default` and then to agent-type rules — the run would look healthy and be the wrong experiment); `max_retries_resolved` equals the arm's declared value (a constructor argument silently beats YAML at `skill_broker_engine.py:129`, so a run intended as C1 can execute as C3); `intervention_framing_resolved = neutral` for A″/B′/B/C1/C3; `advise_spec_resolved` matches the arm; `seed` in the manifest equals the seed in the directory name.

**9.4 Parse-loss bounds.** Report the `UNPARSABLE_0` and `UNPARSABLE_EXEC` share per arm. **If the `UNPARSABLE_0` share differs across arms by more than 2 pp, the exclusion is itself post-treatment**, and the primary outcome is reported as a Manski-style bound: recompute V with all excluded rows counted first as violations, then as conforming. If the sign of the primary contrast flips under either bound, the bound is reported and the point estimate is not.

**9.5 Truncation.** `advisory_reports_shown` must never equal `max_reports_per_retry` (20); if it does anywhere, truncation bound and the report shape differed across arms.

**9.6 Analysis-code dry run.** The full analysis script is written, committed, and run end-to-end on a **synthetic dataset with known injected ground truth** (mock LLM, scripted proposals with pre-set premise revisions, action revisions, and fallbacks) **before any real run is analysed.** The script must recover the injected shares of each mechanism class to within 1 pp. This is the only permitted look at the analysis pipeline before the freeze.

---

## 10. Exclusion rules

Decided now. A run or row excluded by these rules is excluded whatever it would have shown.

**Run-level, new data:**
1. Manifest reports `git_dirty: true`, or no commit hash, or a commit hash other than the study tag. *(Zero clean-tree runs exist in the entire 347-run legacy corpus; every manifest that records a commit records `git_dirty=true` and 94 of 171 record no commit at all. This rule is the reason the tag exists.)*
2. Any §9.3 manifest field disagrees with the arm's declaration.
3. Audit capture below 99 % of expected decisions (expected = agents × years = 1,000). Runs are excluded, never truncated to their captured portion. *(This rule exists because `ministral3:3b` flood data in the legacy corpus is 65–73 % captured; a partial run analysed as if complete is a silent selection on the outcome.)*
4. Any required column of §4.1 step 2 missing.
5. Crash, host reboot, or a detected GPU-to-CPU fallback during the run. Both hazards have recorded incidents in this project — a Windows Update auto-reboot killed a run at year 10, and an Ollama/driver combination silently fell back to 100 % CPU for four hours without erroring. A run interrupted by either is re-run from scratch, not resumed.

**Model-level:**
6. `gemma4:e4b` is excluded from every per-seed paired claim, because it is non-deterministic at fixed seed and fixed commit on this stack. It may appear only in pooled descriptives, explicitly flagged.

**Legacy corpus (the existing 432,083 decisions / 347 runs):**
7. Legacy data supports **no decomposition claim**. It is used only for the composition/regime motivation figure (§1) and the executed-versus-labelled artifact table (S9).
8. The six flood configurations carrying the seed-labelling mismatch (governed 42/4202/4203/45/46 versus disabled 42/43/44/45/46) are excluded from every paired statistic, legacy or new. They may appear only in unpaired pooled descriptives, labelled as such in the caption.

**Row-level, within an included run:**
9. `advisory_parse_failed = True` — excluded from the matched B/B′ contrast (kept in all other outcomes, and its rate reported per arm).
10. `llm_calls` exceeding the arm's declared maximum — excluded from the matched contrast. The Tier-0 floor blocks in every arm, so an advised decision whose post-advisory proposal hallucinates a skill name is still caught and costs more than one extra call; the one-call guarantee is scoped to the mechanism, not the decision.
11. `UNPARSABLE_0` or `UNPARSABLE_EXEC` — excluded from the denominator, counted, and bounded per §9.4.

---

## 11. Stopping rule and queue

**Queue order, fixed:** gemma3:4b → ministral3:3b → ministral3:8b → gemma3:12b. **Seeds in the outer loop, arms in the inner loop.** This ordering is deliberate: a model truncated mid-way then yields *fewer seeds with all arms*, which is analysable, rather than *all seeds with missing arms*, which is not.

**Budget.** Measured per-1000-decision costs at the disabled arm are gemma3:4b 1.1 h, ministral3:3b 1.0 h, ministral3:8b 1.9 h, gemma3:12b 1.9 h. With arm multipliers (A 1.0; A′/A″/B′/B ≈1.15; C1 ≈1.2; C3 ≈1.4) the seven-arm set is ≈8.2 run-equivalents per model-seed, giving ≈242 h for the main ladder, ≈15 h for sham (2 models × 3 seeds), ≈60 h for the S5 reciprocal splits. **Total ≈317 GPU-hours** against ≈700–800 available in the 5 Aug – 15 Sep window. The GPU is not the binding constraint; the analysis-and-writing calendar is.

**How the headroom is spent, decided now:** re-runs of runs excluded by §10; the non-determinism characterisation (one config, 2 models, fixed commit and seed, 10 repetitions); and `gemma3:27b` **only if** the four-model ladder is complete by 1 Sep. **Headroom is not spent on adding arms, adding outcomes, or adding models outside the fixed order after the queue starts.**

**No interim looks at any outcome.** Monitoring between 5 Aug and the freeze is restricted to §9.3 manifest conformance, capture rate, `llm_calls` matching, and run completion — operational health only. V, V_final, Γ, and the mechanism partition are not computed on any subset before the freeze. This is a hard rule and it is the direct remedy for the incident named at the top of this document.

**Freeze: 00:00 on 15 September 2026.** Any run not complete at that moment is discarded, not partially analysed. Analysis begins on the frozen set and the analysis script has been frozen since §9.6.

**Inclusion floor for a configuration:** ≥3 complete seeds × all six ladder arms. A configuration below that floor is dropped entirely; it does not contribute a partial ladder.

**Minimum publishable:** 2 model configurations × 6 arms × 3 seeds. **Below that floor the AAMAS submission is withdrawn** and the material goes to the workshop (29 Aug, non-archival) plus the AAAI-28 AI for Social Impact fallback (~Jul 2027). This is stated now so that "we'll just report what we have" is not an option available in September.

**If the queue slips:** models are cut from the tail of the fixed order (gemma3:12b first, then ministral3:8b). **Arms are never cut. Seeds are never cut below 3.** Losing a model costs a point on the capability axis; losing an arm destroys the decomposition, and losing seeds destroys the only inference the design supports.

---

## 12. What would falsify the central claim

The claim (§2) is that the standard conformance gain is a composite in which the non-behavioural components are material. It is falsified — not weakened, not nuanced — by any of the following.

**F1 — the composite is negligible.** At arm C1, in ≥3 of 4 configurations: `Γ(C1)` within ±5 pp of zero by TOST at the seed level, **and** `p_FILTER` ≤ 5 % of at-risk violating rows, **and** `p_ACTION_REV` ≥ 80 % of the classified conformance gain. Then enforcement produces genuine behaviour change with negligible measurement artifact, the central claim is false, and the paper reports it as falsified in the abstract.

**F2 — the instrument is void.** The attempt-0 balance check (§9.1) fails in ≥2 of 4 configurations, or the byte-identity prompt assertion fails anywhere. Then attempt 0 is not pre-treatment, V is not premise-invariant, and no decomposition claim can be made from this design. The paper is not submitted on this data; the instrument is repaired and the study is re-run.

**F3 — the content term is not identified.** B/B′ call matching (§9.2) fails in ≥2 of 4 configurations. `G_content` is reported as not identified. The composition claim (identity 2) can survive this, because it does not depend on the ladder; the ladder claim does not.

**F4 — the effect is resampling.** `G_sample` is the largest ladder term in ≥3 of 4 configurations while `G_content` and `G_enforce` are both within ±5 pp of zero by TOST. Then what the field calls governance is, in this regime, a second draw from the same distribution. The claim as written is false; the finding is reported and is arguably more useful than the claim would have been.

**F5 — mechanism ordering reverses.** `p_ACTION_REV > p_PREMISE_REV_PURE + p_JOINT` in ≥3 of 4 configurations at arm C1. The premise-revision mechanism is not the dominant one, and every sentence in the paper that says or implies otherwise is removed.

I have checked this list against the standard evasion: *is there a result the claim cannot survive?* Yes — F1 and F5 are both reachable, both plausible given that the flood testbed is the low-enforcement regime where the appraisal shift was +0.81 pp on average, and both would require rewriting the paper's headline rather than its discussion. That is what makes the claim falsifiable rather than decorative. **The honest prior is that F1 or F5 is a live possibility in the flood testbed specifically, and that is exactly why flood is the primary testbed and irrigation is not.**

---

## 13. Amendment policy

Any deviation from this document is recorded as an **appended, dated entry below this line, with the reason and the date it was decided**. Nothing above this line is edited after the commit. The document lives in version control; the history is checkable by anyone, and it is expected that a reviewer will check it.

An amendment may record a deviation, a bug fix under §6, or the study tag hash. **An amendment may not redefine an outcome, change a threshold, change an exclusion, or move an outcome between primary and secondary.** If a change of that kind becomes genuinely necessary, the correct action is to stop, state in the paper that the pre-registration was violated and how, and report both the pre-registered and the revised analysis side by side with the pre-registered one first.

---

### Amendment log

*(empty at commit time)*

- **A0 — study tag hash.** To be filled when the release tag is created, after this document is committed. Tag name: `aamas2027-prereg-v1`. Every run in this study must report this commit hash and `git_dirty: false`.

---

**Files this document depends on, for the reader who wants to check it:**
`C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\AAMAS2027\experiments\appraisal_composition.py` (the established finding),
`...\AAMAS2027\experiments\ARM_CONFIGS.md` (arm YAML and the four traps),
`...\AAMAS2027\experiments\RULE_CLASSIFICATION.md` (hard-versus-soft rule calls),
`...\AAMAS2027\experiments\P0-1e_RESULT_executed_level_correction.md` (the executed-action correction),
`...\examples\single_agent\agent_types.yaml` (rule ids, levels, skills, `default_skill: do_nothing`),
`...\broker\core\_advise_pass.py` and `...\broker\core\_advise.py` (advise modes, `ADVISE_DENY`),
`...\broker\core\_audit_helpers.py` and `...\broker\components\analytics\audit.py` (column emission, all three flags key-gated),
`...\broker\core\_retry_loop.py` and `...\broker\core\skill_broker_engine.py` (attempt capture, status taxonomy, retry-exhaustion policy).