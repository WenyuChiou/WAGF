# G1 — Instrument Validation Gate

**Purpose.** Decide, for roughly six GPU-hours, whether the 700-hour campaign starts. Everything in the instrument was proven under a mock. A mock never fails to parse, never times out, never returns an empty string, and never varies at fixed seed. The five properties the decomposition rests on are all properties of *behaviour under those failure modes*, so none of them is actually established yet.

The gate is deliberately small and deliberately pre-committed: thresholds below are fixed before any run, and I have written the FAIL consequence for each so that a marginal result cannot be re-argued into a pass at 2 a.m. on 4 August.

---

## G0 — Preconditions (zero GPU, must clear before any GPU is spent)

Three things must be true before the gate is worth running.

**The tree must be tagged and clean.** The working tree is dirty right now — six modified files (`examples/multi_agent/flood/orchestration/lifecycle_hooks.py`, `run_unified_experiment.py`, three paper3 analysis files, `configs/calibration.yaml`) and ten untracked paths including four whole prompt directories (`config/prompts_v2/`, `prompts_v3/`, `prompts_institutional_v2/`, `prompts_institutional_v3/`) and `examples/multi_agent/flood/parametric/`. Untracked prompt directories are precisely the class of thing that changes a run's behaviour while the commit hash looks respectable. Each must be committed or gitignored — explicitly, with a decision recorded — and then a release tag cut (`aamas2027-instrument-v1`). Every gate run and every campaign run executes from a clean checkout of that tag.

**The ADVISED_SET must be frozen.** `AAMAS2027/experiments/ARM_CONFIGS.md` still ends with `<ADVISED_SET>` unresolved for flood: the four custom validators in `examples/multi_agent/flood/run_unified_experiment.py` (`validate_flood_zone_appropriateness`, `validate_buyout_repetitive_loss`, `validate_elevation_justification`, `validate_insurance_access_barriers`) mix behavioural theory with world affordance, and the arm definitions cannot be frozen until each is classified. The gate cannot validate arms that do not exist. This is a domain-science ruling, not an engineering task, and it is on the critical path.

**The mock evidence must be re-run at the tag, not inherited.** Two commands: `pytest tests/ broker/ -k "not real_llm"` green, and the flags-OFF byte-identity check via `broker.tools.compare_audit_csv` against the frozen baseline (this was IDENTICAL at `c701d01a`, sha256 `034b4117…`; re-confirm at the tag). Then one mock run with *all* flags ON — `executed_skill_columns`, `initial_proposal_columns`, `advise_columns`, `intervention_framing: neutral`, `require_profile: true` — purely to confirm the columns physically appear in the CSV before spending GPU on discovering they do not.

---

## The gate's run set

All flood runs use `examples/single_agent/run_flood.py` at `--agents 20 --years 5` = 100 decisions per run. All irrigation runs use `examples/irrigation_abm/run_experiment.py` at `--agents 20 --years 10` = 200 decisions per run. These are small on purpose: the gate tests *mechanism properties*, which are per-row invariants, not effect sizes. A per-row invariant that holds on 100 decisions and breaks on 1,000 is a fantastically unlikely failure mode compared with the ones actually being tested.

- **G1-A · arm sweep.** gemma3:4b, flood, seed 42, one run of each of the seven arms (A, A′, A″, B′, B, C1, C3). ~825 decision-equivalents after arm multipliers ≈ **0.9 h**.
- **G1-B · cross-lineage repeat.** ministral3:3b, flood, arms B′, B, C1 only. Parse behaviour is model-family-specific and Ministral is the other lineage in the ladder. ≈ **0.4 h**.
- **G1-C · irrigation smoke.** gemma3:4b, arms B and C1. Irrigation is the high-enforcement regime where the anchoring finding lives, and `--governance-mode` on the irrigation runner was only exposed last week (`b9efe6ec`) and has never been exercised against a real model. ≈ **0.6 h**.
- **G1-D · parity pair.** gemma3:4b, flood, arms B and B′ at `--temperature 0`, with prompt capture on. ≈ **0.3 h**.
- **G1-E · noise floor.** gemma4:e4b arm C1 × 10 repetitions, plus gemma3:4b arm C1 × 5 repetitions, all at fixed seed and fixed commit. ≈ **2.6 h** (the e4b figure is extrapolated — e4b is *not* in the measured cost table, so treat 2.6 h as ±40%).

**Total ≈ 4.8 GPU-hours, budget 6 h with contingency for one re-run after a fix.** That is 0.7 % of the campaign and one evening of machine time. Two gate cycles (fail → fix → re-gate) fit inside two calendar days, which is why the gate must start no later than 2 August against a 5 August queue start.

One tooling item the gate needs and does not yet have: a **prompt-capture shim**. Prompts are not persisted anywhere reliable — `docs/AUDIT_SCHEMA.md` line 188 records full prompts as CSV: no, JSONL: "if the trace writer includes them". `broker/utils/llm_utils.py::create_llm_invoke` is the single seam through which every call passes, so a ~20-line gate-only wrapper that monkeypatches it and tees `(agent_id, year, call_index, sha256, text)` to a JSONL file is sufficient. It lives in the gate harness, not in `broker/`, so it cannot disturb byte-identity.

---

## Property 1 — Call matching

**What to run:** arms B and B′ from G1-A (and again from G1-B, since parse failure is the dominant mismatch cause and it is model-specific).

**What to measure,** all per row from the audit CSV: `llm_calls`, `advisory_llm_calls`, `advisory_fired`, `advisory_parse_failed`, `retry_count`, and separately `llm_retries` (the provider-level counter, which is *not* the same thing and is not included in `llm_calls`).

**Thresholds, in descending severity:**

The hard invariant is that `advisory_llm_calls == 1` on 100 % of rows where `advisory_fired == True`. Not 99.9 %. This is a code property, not a statistical one — `broker/core/_advise_pass.py` sets the counter unconditionally at line 127 before the call and takes no path that increments it twice — so a single violation means the control flow is not what the code review believed, and everything downstream is suspect.

The distributional check is `|mean(llm_calls)_B − mean(llm_calls)_B′| ≤ 0.02` calls per decision, with the share of rows carrying `llm_calls > 2` at or below 2 % in each arm and the *difference* in that share between arms at or below 1 pp.

The attrition check is `advisory_parse_failed` at or below 5 % per arm, with a between-arm difference at or below 3 pp.

**What causes mismatch in practice,** and why each threshold is where it is. There are three distinct mechanisms and they have different consequences.

A parse failure on the advisory call does *not* break call matching — `_advise_pass.py` records the failure, keeps attempt 0, and explicitly does not retry, so the call count stays at exactly one extra. What it breaks is *content* matching: that row received a call but no advice. If the advise prompt (longer, carries rule text) fails to parse more often than the placebo prompt (shorter, one sentinel sentence), the arms suffer *differential attrition* and (B − B′) is confounded with prompt length. That is why the between-arm differential (3 pp) is tighter than the level (5 pp): a symmetric 4 % failure rate is a filterable nuisance, a 1 %-vs-6 % split is a confound.

A Tier-0 block on the post-advisory proposal *does* break call matching, and by design — the module docstring says so plainly: the one-call guarantee is scoped to the mechanism, not the decision. A post-advisory proposal that hallucinates a skill name still gets caught, still opens the governance retry loop, and that decision costs three or four calls. This is the right trade (suppressing the floor to protect a call budget would let impossible actions mutate world state in one arm only), but it means the matched contrast must be computed on a filtered subset, and the filter must be pre-registered: `llm_calls == 2 AND advisory_parse_failed == False`.

Provider-level retries inside `llm_invoke` are invisible to `llm_calls`. They are real GPU cost and real extra sampling. Report `llm_retries` per arm; a large arm asymmetry here is a genuine (if second-order) violation of sample matching even when `llm_calls` looks perfect.

**On FAIL.** The `advisory_llm_calls == 1` invariant is **fatal** — stop, debug, re-gate. Mean drift in the 0.02–0.05 range, or an extra-call row share between 2 % and 10 %, is a **downscope**: keep the decomposition, apply the pre-registered filter, and report the filtered-out share in the paper. Above 10 % filtered out, the (C1 − B) term drops from the headline decomposition to a secondary result, because a decomposition computed on 88 % of a sample selected on a post-treatment variable is exactly the methodological sin this whole paper is about. A symmetric parse-failure rate under 5 % is a **limitation** — report it, filter, move on.

---

## Property 2 — Prompt parity

Inspection is not verification, and this property cannot be checked from the shipped artefacts at all, because prompts are not persisted. So it is checked on captured prompts from G1-D.

**Two separate checks, because they have different failure meanings.**

The *base prompt* check: for every (agent_id, year) pair, the attempt-0 prompt in arm B must be byte-identical to the attempt-0 prompt in arm B′. Threshold: 100 %, zero exceptions. The advise configuration touches only the validator return point and the advisory pass; if it reaches the task prompt, then A, A′ and A″ are no longer nested controls and the whole ladder collapses. This check is cheap, exhaustive and unambiguous.

The *advisory prompt* check is subtler and this is where the honest procedure matters. You cannot simply hash the two advisory prompts and compare, because the reports block is built from the pre-advisory proposal, and under a real LLM at temperature > 0 the pre-advisory proposals differ across arms. So: (i) run the parity pair at `--temperature 0` to maximise attempt-0 agreement; (ii) match rows across arms on `(agent_id, year, initial_skill, advisory_rules)`; (iii) on matched rows, rewrite every report's `violation_summary` line to a fixed sentinel in *both* arms and hash the result. Masked hashes must be equal, and `advisory_reports_shown` must be equal.

Threshold: masked-hash equality on ≥ 99 % of matched rows, with a matched fraction of ≥ 40 % of advisory rows. Below 40 % matched, the check is not powered and the result is "parity under-tested", not "parity verified".

**On FAIL.** Base-prompt mismatch is **fatal**. Masked-hash mismatch on matched rows is **fatal** too, but almost certainly a fixable rendering bug rather than a design flaw — fix and re-gate. A matched fraction below 40 % is a **downscope to a stated-limitation posture**: fall back to the mock-based parity proof (which is exhaustive and free, and which already exists as `test_placebo_mode_strips_rule_content_from_the_prompt` and the neutral-framing tests in `broker/tests/test_advise_disposition_p0_1c.py`), keep the real-LLM base-prompt result, and write in Methods that parity is mock-verified with a partial real-LLM confirmation. That is a weaker claim, honestly stated, not a dead paper.

---

## Property 3 — First-attempt capture

This is the column that did not exist before this month and without which premise-revision and selection cannot be told apart. It is also the property most likely to look fine and be quietly wrong.

**Measure,** from every arm in G1-A and G1-C: the non-empty rate of `initial_skill` and `initial_labels`; the length of `attempt_skills` against `1 + retry_count + advisory_llm_calls`; the distribution of `initial_labels`; and the divergence rate `initial_skill != executed_skill`.

**Thresholds.** Population: `initial_skill` non-empty on ≥ 99 % of rows in every arm, with the residual corroborated by an attempt-0 parse failure on the same row. Structure: the length invariant `len(attempt_skills) == 1 + retry_count + advisory_llm_calls` holds on ≥ 99 % of rows.

The strongest check costs nothing and I would run it first: **on rows with `retry_count == 0` and no advisory fired, `initial_skill == final_skill` must hold on 100 % of rows.** Nothing in the pipeline could have changed the proposal, so any divergence means the column is being written at the wrong point in the control flow — and that is exactly the bug class that produced `proposed_skill == final_skill` on 100 % of the shipped corpus.

Divergence, which is the "often enough to be measurable" question: express it conditionally, not marginally, because the marginal rate is just a restatement of the rejection rate. Among rows with `retry_count ≥ 1`, require `initial_skill != final_skill` on ≥ 20 % in irrigation C3 and ≥ 10 % in flood C3. The irrigation number is the load-bearing one — irrigation rejects 28–62 % of decisions, so if a fifth of blocked decisions do not change their proposal after being told they violated a rule, either the retry mechanism does nothing (a finding in itself, but one that dissolves the premise-revision hypothesis) or the column is stale.

Label variation matters as much as skill variation, because the appraisal-composition finding conditions on the labels: require `initial_labels` to carry ≥ 2 distinct values with the modal value below 95 %.

**On FAIL.** Population below 99 %, or a `retry_count == 0` divergence, is **fatal** — the new corpus would inherit exactly the blind spot that motivates the Tier-2 paper, and there is no point spending 700 hours to reproduce it. Conditional divergence below threshold is a **downscope with a real scientific reading**: it means the mechanism is filtering rather than revising, the premise-revision arm of the question is answered in the negative on a small sample, and the campaign should reallocate hours from the decomposition toward P0-3 held-out rules, which is the test that survives that answer. Label degeneracy is **fatal to the mechanism question** but not to the enforcement decomposition — split the paper accordingly.

---

## Property 4 — Non-blocking

**Measure,** on arms B and B′: whether any rule id in ADVISED_SET ever appears as a blocking rule with a REJECTED outcome or a fallback execution; the fallback / registry-default execution rate; `post_advice_rules`; and `retry_count`.

**Thresholds.** Zero rows — exactly zero — in which an advised rule id blocks or triggers fallback. The fallback rate in B and B′ must sit within 1 pp of the arm-A rate, since non-blocking means a persistent violator executes its own choice, so the advise arms must not carry the enforcement signature. `retry_count == 0` on ≥ 98 % of rows, the residual being Tier-0 blocks.

There is also a **positive control**, which matters because "nothing blocked" is also what a broken advisory pass looks like: `post_advice_rules` must be non-empty on ≥ 10 % of rows where advice fired. That field records rules the *post-advisory* proposal still trips. If it is empty on 100 % of rows, then either advice is perfectly persuasive (not credible on a 4B model) or the re-validation at `_advise_pass.py:207` is not running and the field is vacuous. Do not accept a clean sheet as evidence of a clean mechanism.

**On FAIL.** Any advised rule blocking is **fatal**: the advise arm is partially an enforce arm, (C1 − B) is contaminated, and the decomposition is not the decomposition. Fallback-rate drift of 1–3 pp is a **downscope**: report the arms as "advise, with residual Tier-0 enforcement at X %" and bound the contamination. An empty `post_advice_rules` is **fatal to the arm's interpretation** until diagnosed — it is a five-minute check with a large consequence.

---

## Property 5 — Non-determinism budget

**What to run:** G1-E — gemma4:e4b arm C1 at fixed seed and fixed commit, ten repetitions; gemma3:4b arm C1, five repetitions. Ten is not chosen for precision; it is the smallest number that distinguishes "a few percent of decisions flip" from "a quarter of them do", which is the decision the gate actually has to make. Precise characterisation is P1-D (~30 h, in queue gaps) and should not be smuggled into the gate.

gemma3:4b gets repetitions too, and this is not optional. Non-determinism is documented for e4b only; gemma3:4b carries the published headline and has never been tested this way. Discovering after the campaign that the primary model also drifts would be worse than discovering it now.

**What to measure.** Three things, and the third is the one that decides the campaign shape. First, decision-level disagreement: for each (agent_id, year), the modal executed skill across repetitions and the share of decisions departing from it. Second, the run-level rate of the primary outcome across repetitions, and its variance. Third — the decisive one — **the excess of that variance over the binomial expectation** `p(1−p)/n`. Diffuse per-decision noise averages away across the ~1,000 decisions in a campaign run. A common-mode run-level shift (server state, KV-cache residency, thermal drift) does not average away at all and can only be beaten with more seeds.

**Thresholds.** Decision-level disagreement ≤ 10 % *and* run-level variance ≤ 2× binomial on gemma3:4b: **PASS**, campaign proceeds at 5 seeds. Disagreement 10–25 % or variance 2–4× binomial: **PASS WITH DOWNSCOPE** — go to 7 seeds on the two primary models and pay for it by cutting the model ladder, per the existing "never cut arms" ordering. Above 25 % disagreement or above 4× binomial: the five-term additive decomposition is not estimable at any seed count you can afford; collapse to a three-arm contrast (A, B, C1) with 7–9 seeds and report the intermediate terms as not separately identified.

**Minimum detectable effect, stated honestly.** At the run level with five seeds and a paired t-test on 4 df, the MDE at 80 % power is roughly `1.93 × σ_diff`. If the seed-to-seed SD of the primary rate is 3 pp, `σ_diff ≈ 4.2 pp` and the MDE is about **8 pp**. That is a large effect. The pre-registered analysis is a mixed-effects model with agent random effects over ~1,000 decisions per run, whose MDE is far smaller — but *only* if the excess run-level variance is small, because a common-mode shift enters the mixed model as an irreducible run-level random effect and the agent-level n buys nothing against it. So threshold three is not a hygiene check; it is the condition under which the campaign's power claim is true at all. Report the actual observed σ from the gate and recompute the MDE before the queue starts, and pre-register that any decomposition term falling below it is reported as "not separately identified, CI [a, b]" — never as zero.

---

## Property 6 — Clean provenance

Every one of the 347 existing runs records `git_dirty=true` or no commit at all. The reason is structural: `broker/core/experiment_runner.py:517-518` *records* dirtiness and does nothing about it. Recording has now been empirically demonstrated, 347 times, to be insufficient.

**The enforcement.** Add a pre-run refusal in the launcher: read `git status --porcelain`; if non-empty, exit non-zero before a single LLM call, with the offending paths printed. Provide exactly one override, `WAGF_ALLOW_DIRTY=1`, which stamps `dirty_override: true` into the manifest so an overridden run is permanently and visibly marked. A refusal, not a warning — and note that `--porcelain` includes untracked files, which is what catches the four untracked prompt directories currently sitting in the tree.

**The verification.** A manifest linter (zero GPU, runs over the gate's own output) asserting, for every run: `git_dirty == false`; `git_commit` equal to the sha of `aamas2027-instrument-v1`; `advise_spec_resolved.mode` equal to the arm's intended mode; `max_retries_resolved` equal to the intended value; `intervention_framing_resolved == "neutral"`; `governance_profile_resolved` equal to the intended profile; `model_digest` not `"unavailable"`. The `max_retries_resolved` assertion is the load-bearing one — `skill_broker_engine.py:129` resolves `max_retries if max_retries != 3 else config.get_governance_retries(...)`, so a constructor argument silently beats the YAML and an arm intended as C1 can run as C3, which would break call matching in the one place the whole decomposition depends on it. Verify arms from the manifest, never from the config file. Set `require_profile: true` in every arm config so a typo'd `GOVERNANCE_PROFILE` raises instead of falling back to `default` and quietly running the wrong rule set.

The linter also asserts **seed-set equality across arms**: the exact same seed values in every arm of every model. The existing 42/4202/4203/45/46-versus-42/43/44/45/46 mismatch invalidated paired statistics on six of nine flood configurations, and it is invisible unless something checks it.

Threshold: 100 % of gate runs pass the linter, and the linter runs as a mandatory post-run step on every campaign run thereafter, not once at the start.

**On FAIL.** Fatal-until-fixed rather than fatal-to-campaign — every provenance failure is a cheap fix, and the only unacceptable outcome is starting the queue with the linter unwritten. But treat "we'll add it after the first few runs" as a fail: the first few runs are the ones you will most want to trust in October.

---

## One thing to add while you are already measuring

The gate is the only moment when you will have clean per-model, per-arm timing on this machine. Record seconds-per-decision for every model in the gate and hard-wire those numbers as a **wall-clock tripwire** in the campaign launcher: abort and alert if a run's rolling seconds-per-decision exceeds 2× the gate baseline. This directly addresses the recorded four-hour silent CPU fallback, which produced no error and no log line and was only found by noticing the clock. Pair it with a pre-run `ollama ps` assertion that the model shows 100 % GPU, and with Windows Update paused for the full campaign window, per the incident that killed a run at year 10.

---

## Summary of the decision rule

The campaign starts if and only if: the one-call invariant holds absolutely; no advised rule ever blocks; base prompts are identical across arms; `initial_skill` populates on ≥ 99 % of rows and is exactly equal to the final skill whenever nothing could have changed it; and the manifest linter passes on 100 % of gate runs. Those five are the fatal set, and every one of them is a code property that either holds or does not — no judgement calls.

Everything else — parity match rate, parse-failure attrition, conditional divergence, non-determinism magnitude — moves the campaign's *size and shape*, and each has a pre-written smaller version of the campaign attached to it. That is the point of writing the thresholds down now: the failure modes that would otherwise be discovered in week four, when the only remaining options are bad ones, are instead discovered on 2 August, when the option is simply "run a smaller thing".

**Cost: ~4.8 GPU-hours, budget 6. Wall clock: one evening, two days if a re-gate is needed. Deadline: PASS by 4 August; if not passed by 8 August, invoke the existing hard gate and cut gemma3:27b and ministral3:14b immediately rather than compressing the analysis window.**