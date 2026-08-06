## Verdict

The instrument is genuinely good — `initial_proposal_columns` plus `executed_skill` plus an advise/placebo pair is the right hardware for this question, and it is more than the published literature has. But as specified, **the matrix does not answer the question**, for five reasons, three of which I can demonstrate as arithmetic or as code rather than as opinion.

Ranked by how badly each one breaks the paper:

| # | Flaw | Class | Fatal? |
|---|---|---|---|
| 1 | Flood-primary makes the primary contrast mathematically bounded at ≤0.85 pp against a ±5 pp equivalence margin — the prereg guarantees its own falsification | design | **fatal** |
| 2 | The placebo arm is not content-free: it names the blocked skill and renders the real `suggested_correction` | code | **fatal to G_content** |
| 3 | Four unacknowledged trajectory confounds (absorbing attrition, cross-agent interference, shared-RNG desync, filler rows) — year 2–10 is not merely "trajectory-confounded", it is a different experiment | design + code | **fatal to V_pooled** |
| 4 | Premise revision has no noise floor: A′ exists but no label-movement outcome is defined on it | estimand | recoverable, cheap |
| 5 | Held-out rule shares its consequent with two of the three enforced rules | estimand | recoverable, cheap |

Plus: no LLM seed is passed to Ollama at all, so "paired on seed" pairs the environment and not the generation; and the two documents disagree about the primary testbed.

---

## 1. The flood-primary decision is self-falsifying. This is the kill shot.

Verified in code, not inferred from the corpus:

- `broker/core/_advise_pass.py:80` — the advisory pass returns a blank info dict and makes **zero** extra calls unless `advised` is non-empty, i.e. unless an advised rule actually fired on this decision.
- The enforcement loop opens only on `not all_valid` (`_retry_loop.py:218`), i.e. only when a rule fires.

Therefore **arms A, A′, A″, B′, B, C1 are byte-identical on every decision where no E-rule fires.** The arms are not different treatments applied to 1,000 decisions; they are different treatments applied to the fired subset and the identity map elsewhere.

Flood E-rule fire rate: 0.00–0.85 %.

| quantity | flood (prereg primary) | irrigation |
|---|---:|---:|
| decisions per run | 1,000 | 3,276 |
| fire rate | 0.00–0.85 % | 28.1–62.6 % |
| **treated decisions per run** | **0 – 8.5** | ~920 – 2,050 |
| treated decisions per 5-seed arm cell | **0 – 42.5** | ~4,600 – 10,200 |
| **theoretical max \|V(A) − V(C1)\|** | **≤ 0.85 pp** | ≤ ~45 pp |
| ladder has 5 terms → mean term | **≤ 0.17 pp** | ~9 pp |
| prereg equivalence margin | ±5 pp | ±5 pp |
| margin ÷ theoretical ceiling | **5.9×** | 0.11× |

Read the last row again. The pre-registered equivalence margin is **six times larger than the largest value the primary contrast can take even if enforcement flips 100 % of treated decisions**. TOST at ±5 pp on a quantity bounded by 0.85 pp passes with probability ≈ 1 regardless of the truth.

Now trace that through §12 as written:

- **F1** fires: `Γ(C1)` within ±5 pp — guaranteed, since Γ is also bounded by the fire rate.
- **F4** fires: `G_content` and `G_enforce` both within ±5 pp — guaranteed.

So the pre-registration, executed exactly as written, **obliges the paper to report its own central claim as falsified**, on evidence that consists of a power failure. That is worse than a null result: a reviewer who does this arithmetic (it takes ten minutes) will conclude either that you did not do it, or that you did and chose the testbed anyway.

The year-1 identified window is worse still: 100 agents × 5 seeds = 500 decisions per arm × 0.85 % ≈ **4 treated decisions per arm cell**. The identified estimate of the paper's headline rests on about four decisions.

§3.1's justification — "if the motivating case were used a reviewer would say the result was selected on the outcome" — is a real concern answered with the wrong instrument. Selecting the testbed where you expect the null is outcome-selection too, just conservative, and conservative selection combined with a margin above the physical ceiling is not conservatism, it is a guaranteed answer.

**Fixes, pick one:**

- **(A, recommended) Swap primary to irrigation, as the run matrix says.** Flood becomes a pre-registered *regime prediction* ("the ladder is flat where rules do not fire"), and its null is reported as consistent-with-prediction, never as falsification. Rewrite F1/F4 so they can only be evaluated in a cell where the fire rate exceeds a pre-stated floor — I would set that floor at **10 %**, which flood fails and irrigation passes by 3–6×.
- **(B) Keep flood primary and pay for it.** To detect δ = 0.3 pp on a base rate of ~1.5 % at 80 % power, α = .05: n ≈ 2(1.96+0.84)²·p(1−p)/δ² ≈ **25,800 decisions per arm** ≈ 26 runs per arm ≈ 155 runs for the six-arm ladder ≈ 190 GPU-h for one model. And that is the decision-level number, which flaw 3 invalidates anyway.
- **(C) Regardless of A or B: make the equivalence margin scale-relative.** Margin = max(1 pp, 0.25 × V(A) in that cell), pre-registered per cell, and it must be strictly smaller than the smallest effect that would change a sentence in the paper. A fixed ±5 pp applied to both a 0.85 pp regime and a 38 pp regime is not one decision rule, it is two different ones wearing the same number.

---

## 2. The placebo arm leaks the rule. G_content is currently not identified.

`broker/core/_advise_pass.py:107-112` builds the placebo by overwriting **only** `r.violation_summary`. But `InterventionReport.to_prompt_string` (`broker/interfaces/skill_types.py:177-181`) renders:

```
- [{severity}] Your proposed action '{blocked_skill}' {verb}.
  - Reason: {violation_summary}
  - Suggestion: {suggested_correction}
```

So the placebo prompt still carries **`blocked_skill`** and, if the advised rule defines one, **the real `suggested_correction` verbatim**.

Why this is fatal rather than untidy. With a four-action space, telling the agent "your action `do_nothing` triggered a rule" removes one of four options. For `extreme_threat_block` (TP ∈ {H,VH} blocks `do_nothing`), naming `do_nothing` as the offender pushes the agent into {insure, elevate, relocate} — which **is** conformance with that rule. A placebo that mechanically delivers most of the enforcement effect makes `G_content = V(B′) − V(B) ≈ 0`, and §12's F4 branch reads that as "the effect is resampling, the claim is false." You would publish a false negative caused by your own control arm.

The existing reassurance is also false: `test_placebo_mode_strips_rule_content_from_the_prompt` (cited in the G1 doc) evidently checks that the rule *text* is absent. It does not check that the skill name and suggestion are absent.

**Fix (about 15 LOC, zero GPU):**

1. In placebo mode, render with `show_suggestion=False` **and** a report string that names no skill:
   `- [{severity}] One of your proposed actions triggered a governance rule.`
2. Fix report count. B′ currently shows N reports where N = number of rules fired, which leaks *how many* rules were broken and makes the block length outcome-correlated. Set `max_reports_per_retry: 1` in **both** B and B′ so the block is one item in both arms.
3. Add the assertion that actually defines "content-free": **the placebo advisory prompt, minus the base prompt, must be byte-identical across every decision in the run.** Hash it and assert a single distinct value per run. That is a unit test and a post-run linter check, and it is the only version of this property that a reviewer cannot argue with.
4. Re-word the paper's claim: with (1)–(3), `G_content` means "rule identity plus justification versus a generic corrective signal of identical shape." Without them it means nothing.

---

## 3. "Is any contrast after year 1 clean?" — No, and for four reasons, only one of which is in the documents.

The prereg names state divergence. Three more mechanisms are live in `examples/single_agent/run_flood.py`:

**(a) Absorbing attrition with pool removal.** `run_flood.py:364` — `active_agents = [a for a in agents if not relocated]`; `:369-371` relocated agents `continue`. Relocation is absorbing and removes the agent from the decision pool. `relocation_threat_low` blocks `relocate` at low TP, so **C1 retains more agents in the pool than A**. The arms differ not only in state but in *who is still being measured*. This is competing risks / differential censoring, and it appears nowhere in the prereg, the matrix, or the risk register.

**(b) Cross-agent interference.** `run_flood.py:398-401` writes into every agent's memory: `"Year {y}: I observe {elev_pct}% of neighbors elevated and {reloc_pct}% relocated."` The "single-agent" flood testbed is not single-agent from year 2. Every agent's prompt contains a population aggregate that the treatment moved. Consequences:
- SUTVA fails from year 2. The arm effect on agent *i* depends on the arm's effect on all other agents.
- The prereg's GLMM `violation ~ arm + (1|seed) + (1|seed:agent_id)` treats agents as conditionally independent. They are not — they share one aggregate channel per run. **The correct cluster is the run.** Effective n for any post-year-1 claim is **5, not 5,000.** The G1 gate's claim that "the mixed-effects MDE is far smaller" is therefore wrong for exactly the window it is invoked to defend.

**(c) Shared-RNG desynchronisation — the arms do not even face the same weather.** `run_flood.py:1366` sets one global `random.seed(actual_seed)`. Every stochastic element then draws from that single stream: the per-agent damage draw (`:374`, `:381`), the memory-recall draw (`:404`), and the flood event itself when `flood_probability` mode is used (`:288`). Relocated agents `continue` before their draws. So **the moment one agent's decision differs between arms, the RNG stream desynchronises and every subsequent exogenous shock differs across arms.** Different damage realisations, different recalled memories, potentially different flood years. Arms are not paired on the environment after the first divergence; they are independent runs with a shared initialisation.

**(d) Filler rows.** `run_flood.py:1276-1287` backfills relocated agents with synthetic rows carrying `yearly_decision: "relocated"` and no LLM call. Under §4.1 these have no `initial_labels` → `UNPARSABLE_0`. Their frequency is arm-dependent (relocation rate is arm-dependent), so §9.4's ">2 pp differential" trigger fires and the primary outcome degrades to a Manski bound — by construction, in every configuration. Separately, the risk register's proposed strict assertion "row count == agents × years exactly (flood 1,000)" is satisfied only *because* of these filler rows; without them it would fail on every governed run. Neither document notices.

**Fixes, ranked by value per hour of work:**

1. **Common random numbers (~30 LOC, 0 GPU, do this first).** Pre-draw all exogenous shocks into an `(agent, year)` array from a dedicated `random.Random(seed)` before the run: flood events, per-agent damage draws, memory-recall draws. Index into the array rather than consuming a shared stream. Every arm then faces a byte-identical exogenous history, and paired differencing does what the prereg claims it does. Without this, "paired on seed" is a slogan.
2. **Restructure the identified estimand: N agents × 1 year, not 100 agents × 10 years.** 1,000 agents × 1 year costs the *same* GPU as 100 × 10 (identical call count) and makes **100 % of the corpus identified instead of 10 %**. No attrition, no interference (the neighbour aggregate in year 1 comes from initial conditions, identical across arms), no state divergence, no RNG desync, no filler rows. Every pathology above is a year-2+ pathology. For irrigation the panel is fixed at 78 agents, so the equivalent is 42 independent 1-year replicates at staggered start-years rather than one 42-year trajectory — same cost, all identified.
3. **Make V_y1 the unconditional primary now.** §4.3's "if the two windows disagree in sign, V_y1 leads" is an outcome-contingent choice of primary window (see §4 below).
4. **If you keep the multi-year window at all:** state is low-dimensional and fully logged (`elevated`, `has_insurance`, `relocated`, wealth), so report a marginal structural model with stabilised IPW over the observed state history, or at minimum V within state strata. Report per-arm survival curves. Cluster at the run.

---

## 4. Premise revision: identified in principle, not identified as specified

You asked me to walk the arithmetic. Here it is, one property per rung:

| contrast | differs in exactly one property? | isolates what is claimed? |
|---|---|---|
| A → A′ | yes: one extra draw, zero added text | yes — free stochastic drift |
| A′ → A″ | yes: wrapper scaffolding + position | yes |
| A″ → B′ | **no — two properties**: report block present/absent, *and* its content and item count | conflates "there is a correction" with "how many rules and which action" |
| B′ → B | only after fix #2 above; today B′ already carries `blocked_skill` + suggestion | **not identified as shipped** |
| B → C1 | yes: blocking versus not, call-matched at C1 `max_retries: 1` | yes |

And now the substantive point about premise revision specifically.

**Selection is solved.** With `TP0` observed on every row, the latent problem is gone: which decisions are high-appraisal is directly measured pre-treatment, so the selection component is the difference between the TP0 marginal and the TP_final marginal, and between the TP0 marginal among retried and non-retried rows. That is a real advance and it is what the instrument bought.

**Premise revision is not.** `PREMISE_REV_PURE` as defined in S3 is a within-arm description with no counterfactual: it counts label movement, but nothing tells you how much of that label movement would have happened under a second draw with no rule text. On a 4B model at Ollama's default temperature (~0.8 — `broker/utils/llm_utils.py:271-277` only sets sampling params if explicitly configured), spontaneous ordinal-label instability between two independent draws could plausibly be 20–40 %. If the headline is "premise revision accounted for X pp", and the free-resample floor is 0.6X, the paper is wrong by that factor.

**A′ is exactly the right control and the prereg wastes it.** Fix, in three parts:

1. **Define a label-movement outcome, in every arm:**
   `M+ = P(TP moves out of the rule's antecedent band between attempt 0 and the final proposal | at-risk ∧ attempt-0 violated)`.
2. **Report the attributable quantities, not the raw one:**
   - free drift = `M+(A′)`
   - content-attributable premise revision = `M+(B) − M+(B′)`
   - enforcement-attributable premise revision = `M+(C1) − M+(B)`
   Each is a one-property, call-matched contrast. Report raw `M+(C1)` too, but never as the headline.
3. **Add an `attempt_labels` column** alongside `attempt_skills`, at the same emission site. Today intermediate labels are lost for anything past one retry, so C3 is unanalysable for premise revision and the C1-versus-C3 comparison cannot be made on the mechanism.

Also decompose Γ, which currently conflates the two things the paper is about:
`Γ = V − V_final = [movement of the antecedent within retained rows] + [rows entering/leaving the at-risk set]`. Both terms are computable from TP0 and TP_final. Reporting Γ as one number reproduces, in the paper's own headline statistic, the exact conflation the paper indicts.

---

## 5. Held-out rules: yes, the design leaks, and in a way that is cheap to fix

**(a) Shared consequent — mechanical, not behavioural.** `low_coping_block` blocks `{elevate_house, relocate}` on low CP. Two of the three *enforced* rules (`relocation_threat_low`, `elevation_threat_low`) block the same two actions. So enforcement mechanically reduces the elevate/relocate share, which mechanically reduces the held-out violation rate with zero change in the agent's coping reasoning. If enforcement cuts the {elevate, relocate} share from *s* to *s′*, the held-out rate falls by roughly `(s − s′) · P(CP0 low | elevate/relocate chosen)` for free.

Fix, two lines of analysis code: report the **conditional** held-out rate `P(CP0 ∈ {VL,L} | a_exec ∈ {elevate, relocate})`, which is invariant to the action-composition shift, alongside the marginal. If the conditional does not move, there is no induction, whatever the marginal does. Better still, add a held-out rule with a **disjoint consequent** — one blocking `buy_insurance` or `do_nothing` — so no algebraic path exists at all.

**(b) Can the agent tell which rules are enforced?** Within a decision, unambiguously yes: `to_prompt_string` names the blocked skill and the reason. Across years, the leak is behavioural rather than textual — `run_flood.py:407` feeds last year's action context into memory, and enforced-rule pressure persists in the agent's own state. So any cross-year "induction" claim is contaminated by the agent having learned the enforced set.

Fixes:
- Confine held-out inference to **first-violation events** per agent, or to year 1.
- Add a **generic-feedback contrast** (rule named versus "a rule was triggered") to bound rule-identity leakage. Note this is the same machinery as the placebo fix in §2 and costs no extra arm.
- **Split within-run, not across runs.** Assign split S1 to a random half of agents and S2 to the other half in the same run. Halves the cost of B6a/B6b (~50 GPU-h saved), removes run-level nuisance from the enforced-versus-held-out comparison, and each agent only ever observes its own enforced set. Honest caveat: the neighbour-aggregate memory channel still couples the halves at the *action* level, though not at the rule level — state it.

**(c)** The prereg's framing that `low_coping_block` is "a free held-out rule because WARNING is inert" is correct but should be stated precisely: a WARNING rule never enters any prompt in any arm, so the agent cannot know it exists. That makes it a clean spillover/induction probe — which is exactly why (a) is the binding problem, not (b).

---

## 6. Escape hatches in the pre-registration

The document is far above field norm. It still has eight.

| # | Hatch | Fix |
|---|---|---|
| 1 | §4.3: V_y1 leads *only if* the windows disagree in sign. Sign-agreement is weak — both windows can agree in sign with 5× different magnitudes, and the paper will quote the pooled magnitude | Name one primary window unconditionally. V_y1 is the identified one |
| 2 | ±5 pp equivalence margin applied identically to a regime with a 0.85 pp ceiling and one with a 45 pp range | Scale-relative margin, §1(C) |
| 3 | Asymmetric burden: falsification (F1) is a **three-way conjunction**; confirmation (§8 row 1) is a two-way conjunction. Conjunctions make falsification strictly harder than confirmation | Make the primary falsifier a single pre-stated quantity with a single threshold |
| 4 | §6 permits halting analysis for a "bug" whenever identity 3 fails to sum. "Classification disagreement" can always be called a bug | Freeze the analysis script hash at §9.6; any post-freeze change logged with a diff, and **both versions' results reported** |
| 5 | §11 spends headroom on "re-runs of runs excluded by §10", with no cap and no requirement to retain the excluded run | Cap re-runs; permit only for crash / reboot / CPU-fallback / dirty-tree; retain and report every replaced run |
| 6 | §9.4 triggers Manski bounds only if parse loss differs by >2 pp. Parse loss is plausibly outcome-correlated even when balanced (a confused row is likelier to violate) | Report bounds always |
| 7 | **The G1 gate contradicts §13.** G1 Property 3 pre-authorises "downscope: split the paper accordingly"; G1 Property 1 pre-authorises moving (C1 − B) "from the headline decomposition to a secondary result". §13 forbids moving an outcome between primary and secondary. Two governing documents, opposite rules | Resolve explicitly: either the G1 downscopes are legitimate pre-registered adaptations (then say so in §13 and enumerate them), or they are struck |
| 8 | **G1 Property 3's conditional-divergence check is an interim outcome look.** `initial_skill != final_skill` on retried rows is precisely `ACTION_REV + JOINT` from S3 — computed on the primary model, before the freeze, and used to reallocate the campaign. §11's "no interim looks" is violated by the gate that §11 depends on | Run the divergence check on a non-primary model or on the §9.6 synthetic fixture; or declare it a peek, state its alpha cost, and pre-register that it cannot alter the primary analysis |

**And a ninth, structural:** the run matrix says irrigation-primary and the pre-registration says flood-primary. Both are dated 2026-07-29. A reviewer will ask which was written second and why. There must be **one** document of record, one commit, and an explicit supersession statement — before any tag is cut.

---

## 7. Is the primary outcome robust to the two known measurement defects?

**Executed-versus-proposed: half fixed.** Using `executed_skill` is right. But V then counts a `REJECTED_FALLBACK` `do_nothing` as an agent violation of `extreme_threat_block`, and §4.1 pre-registers exactly that. So V is a hybrid of agent behaviour and registry-default behaviour, and the sign of the enforcement effect on V is partly determined by whether the default happens to satisfy each rule — which for this rule set it does for the low-TP rules and does not for the high-TP rule.

Report three quantities, not one:

| outcome | definition | property |
|---|---|---|
| **V_world** | executed action (= current V) | what the world got; mixes agent and default |
| **V_intent** | antecedent TP0, consequent = **last agent-proposed skill** from `attempt_skills` | defined on every row, no fallback artifact, premise-invariant, fully identified |
| **V_choice** | V restricted to `executed_via_fallback == False` | agent choice, but a post-treatment-selected sample — must be bounded, never point-estimated |

I would make **V_intent primary**. It is the only one of the three that is defined on the full sample *and* free of the default-execution artifact, and `attempt_skills` already makes it computable. V_world is the deployment-relevant secondary. V_choice is a bounded sensitivity.

**Post-treatment conditioning: not fixed, and the paper cannot afford this.** TP0 is pre-treatment within a decision, and post-treatment at the trajectory level from year 2 onward — via state, via attrition, via the neighbour aggregate, and via the RNG stream. So 90 % of the flood corpus conditions the at-risk denominator on a post-treatment variable. A paper whose thesis is "the standard statistic conditions on a post-treatment variable" cannot present a main table where its own preferred statistic does the same thing for nine years out of ten, with the acknowledgement in a subclause. That is the single most quotable objection a reviewer will raise, and §4.3 as written hands it to them.

The fix is §3's item 2: **restructure the run so the identified window is the whole run.** It costs zero GPU-hours.

---

## 8. Two smaller things worth naming before the tag

**No LLM seed is passed anywhere.** `broker/utils/llm_utils.py:270-295` builds `options` with temperature/top_p/top_k only, and only if explicitly configured; there is no `seed` key, and `grep` finds `"seed"` in the provider path only at `broker/utils/replay.py:54`. Consequences: (i) "paired on seed" pairs agent initialisation, not generation; (ii) attempt-0 is an independent draw in every arm even though the attempt-0 prompt is byte-identical; (iii) the G1-E non-determinism result is currently measuring an unnecessary quantity. **Add `options["seed"]` derived deterministically from `(run_seed, agent_id, year, attempt_index)`, record it per row, then re-run G1-E.** If Ollama's seed gives reproducibility on this build, attempt-0 becomes *identical* across arms and §9.1 upgrades from a noisy proportion test to a 100 %-threshold assertion. That is worth more than any single arm in the matrix.

**§9.1's balance check is mis-calibrated for the year-1 window.** Six arms → 15 pairwise differences, threshold "max pairwise < 5 pp", n = 5 seeds.

| window | decisions/run | per-run SD at p≈0.3 | SE over 5 seeds | SD of a pairwise diff | expected max of 15 | 5 pp threshold |
|---|---:|---:|---:|---:|---:|---|
| pooled | 1,000 | 1.45 pp | 0.65 pp | 0.92 pp | ~2.5 pp | fine |
| year 1 | 100 | 4.58 pp | 2.05 pp | 2.90 pp | **~7.8 pp** | **fails under the true null most of the time** |

Since §12's F2 voids the whole design when this check fails in ≥2 of 4 configurations, the pre-registration currently contains a validity gate that, applied to the identified window, voids the study by chance. Fix: specify the window; use TOST with a stated margin rather than a max-difference rule; and after the seed fix above, replace it with the exact-match assertion.

**One prompt observation for Methods.** `examples/single_agent/config/prompts/household.txt` contains, in every arm: *"Note: If no flood occurred this year, since no immediate threat, most people would choose 'Do Nothing.'"* This is a fixed nudge toward the action `extreme_threat_block` forbids. It is arm-invariant so it does not confound the contrasts, but it does mean V(A) partly measures compliance with the prompt rather than with PMT, and it caps how much enforcement can move. One sentence in Methods; a reviewer who reads the prompt will find it.

---

## 9. What I would actually change, in order

| # | Change | Cost | Buys |
|---|---|---|---|
| 1 | Swap primary to irrigation; flood becomes a pre-registered flat-regime prediction with a ≥10 % fire-rate floor gating F1/F4 | 0 GPU, rewrite §3.1/§12 | removes the guaranteed self-falsification |
| 2 | Fix the placebo: no skill name, no suggestion, fixed 1 report in both B and B′, plus a byte-identity assertion across decisions | ~15 LOC + 1 test | makes G_content identified |
| 3 | Common random numbers: pre-draw all exogenous shocks per (agent, year) | ~30 LOC | arms actually share an environment |
| 4 | Restructure the identified estimand to N agents × 1 year (flood) / staggered 1-year replicates (irrigation) | 0 GPU | 100 % identified instead of 10 % |
| 5 | Pass a deterministic per-call LLM seed; re-run G1-E | ~5 LOC | real pairing; §9.1 becomes an assertion |
| 6 | Add `attempt_labels`; define M+ and report it against A′; decompose Γ into within-row and set-membership terms | ~20 LOC + analysis | premise revision gets a noise floor |
| 7 | Held-out: conditional rate + disjoint-consequent rule + within-run split | 0 GPU, −50 GPU-h on B6a/B6b | kills the algebraic-spillover objection |
| 8 | Make V_intent primary; V_world and bounded V_choice secondary | analysis only | removes the registry-default artifact |
| 9 | Reconcile the two documents into one of record; close the eight hatches; resolve the G1/§13 contradiction | 0 GPU | the timestamp defence survives contact |

Items 1–8 together cost roughly **100 lines of code, zero GPU-hours, and about two days** — and they are the difference between a decomposition a hostile reviewer can dismantle in one paragraph and one they cannot. All of them must land **before** the tag, because every one of them changes what the runs mean, not how they are analysed.

**Files referenced:**
`C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\core\_advise_pass.py` (lines 80, 94-118 — advisory fires only on fired rules; placebo overwrites only `violation_summary`)
`C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\interfaces\skill_types.py` (lines 158-181 — `InterventionReport` fields and `to_prompt_string`; the leak)
`C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\core\_advise.py` (`ADVISE_DENY`, `render_intervention_prompt`)
`C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\utils\llm_utils.py` (lines 270-295 — no seed in `options`)
`C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\run_flood.py` (lines 288, 364-371, 374-404, 1276-1287, 1366 — RNG stream, attrition, neighbour aggregates, filler rows, single global seed)
`C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\config\prompts\household.txt` (no rule text at attempt 0; the `do_nothing` nudge)

## Advisor memo — cut the campaign to ~180 GPU-hours, and fix the testbed choice before you commit the pre-registration

### Bottom line

Three things, in order of how much they change your next ten weeks.

1. **The pre-registration names flood as the primary testbed. Your own data says flood cannot produce a result there.** This is arithmetic, not judgment, and it is checkable in the file the pre-registration cites as its evidence base.
2. **Neither document estimates the effect size of the primary outcome.** You have a careful power analysis for *noise* (G1 Property 5) and none for *signal*. That is the hole that turns 556 GPU-hours into a table of confidence intervals straddling zero.
3. **You have a Nature Water manuscript at v29 that has not been sent to your advisor since 11 May.** That is eleven weeks. It is the most expensive object in this portfolio and it is blocked on decisions, not on compute.

---

### 1. Flood-primary is unpowered by construction — from your own CSV

`AAMAS2027/experiments/appraisal_composition.csv`, governed rejection rate, flood column:

| model | % rejected |
|---|---:|
| gemma3_4b | 0.85 |
| gemma4_e4b | 0.47 |
| gemma4_26b | 0.12 |
| ministral3_3b | 0.087 |
| ministral3_8b | 0.024 |
| gemma3_12b | 0.021 |
| gemma3_27b, ministral3_14b, gemma4_e2b | **0.000** |

The pre-registration's primary outcome V is the first-attempt-conditioned violation rate on the executed action. Attempt 0 is pre-treatment by design (§9.1 asserts byte-identical base prompts), so the first-attempt violation rate is the same in every arm, and it is what the governed rejection rate measures. Therefore **V(A) ≈ 0.85 pp at the very best flood cell, and V(A) − V(C1) ≤ 0.85 pp.**

The pre-registered equivalence margin is **±5 pp**. The maximum attainable effect is six times smaller than the margin you have pre-committed to calling "no effect." Under §12 that returns **F1 — claim falsified** with probability approaching one, for reasons that have nothing to do with whether the claim is true.

Worse: the pre-registered model queue is gemma3:4b → ministral3:3b → ministral3:8b → gemma3:12b. Three of those four reject **0.087%, 0.024%, 0.021%** of flood decisions. A 1,000-decision run yields **zero to one** violating row. You would spend roughly 240 GPU-hours on cells that cannot contain a single observation of the phenomenon, and then report a pre-registered falsification.

The run matrix reaches the right conclusion (irrigation primary, flood as a cheap flatness control) by a slightly wrong route — it uses "fired decisions" where V's denominator is the broader at-risk set. The conclusion survives the correction; the numbers above are the cleaner version of the argument. **Take the run matrix's structural recommendation and rewrite §3.1 of the pre-registration before you commit it.**

Do this now, not after. The pre-registration's entire value is that it is timestamped ahead of data. It is not committed (§13 log empty, tag uncut), so this is a free correction today and a permanent credibility cost on 6 August.

There is a second, subtler prize here. Flood governed IBR 0.87% vs no-validator 8.53% is a 7.7 pp gap in the published statistic, while only 0.85% of decisions were ever rejected. Those two numbers do not obviously reconcile. Resolving that — zero GPU, one afternoon on existing traces — may be the single strongest result in the whole program, and it is a defensive note you want in hand before a reviewer finds it.

### 2. Estimate the signal before you buy the GPU

Before any run: compute a V-proxy on the **existing disabled-arm irrigation corpus** (final labels, executed action — an upper bound, but a real one) and on the flood corpus. You already have `rederive_executed_levels.py` and `appraisal_composition.py`; this is a variant of both.

That number decides the campaign. If V(A) on irrigation is 30–60 pp, decomposing it into five terms with 5 seeds is comfortable. If it is 4 pp, the ladder is not estimable at any seed count you can afford and you should not start. **One day of analyst time gates 500 GPU-hours.** Neither document contains it.

### 3. What I would actually run — ~180 GPU-hours, not 556

Irrigation primary, gemma3:4b anchor, ministral3:3b replication, flood as control.

| block | testbed / model | arms | seeds | GPU-h |
|---|---|---|---:|---:|
| B0 clean-tree bridge + instrument smoke | irr / gemma3:4b | C3, disabled (legacy framing) | 3 | 26 |
| Anchor full ladder | irr / gemma3:4b | A, A′, A″, B′, B, C1 | 5 | **126** |
| Replication, core ladder | irr / ministral3:3b | A, B′, B, C1 | 5 | 74 |
| Regime control | flood / gemma3:4b | A, B, C1 | 5 | 19 |
| | | | | **~245** |

Trim further if the calendar bites: drop B0's disabled arm (−11 h), drop the flood control to 3 seeds (−8 h). The floor that still answers the question is **anchor ladder + replication ≈ 200 h, ~12 days of queue.**

Note what this preserves: the full six-rung ladder on the anchor, which the risk register correctly calls the methodological contribution, and a second lineage. Note what it drops.

### 4. What I would cut, and why each cut is safe

**The scale axis — ministral3:8b + gemma3:12b, −170 GPU-h, −24 runs.** Your own pre-registration says the scale interaction is "EXPLORATORY... labelled exploratory in the paper regardless of the p-value obtained, including if p < 0.001." You are proposing 170 GPU-hours and 24 integrity reviews to purchase a term you have already committed to not claiming. Cut it. Report the decomposition on two models in two lineages and say so.

**gemma3:27b and ministral3:14b — already cut in the run matrix, agreed, for the arithmetic given there.** Add one more reason: 35 h unresumable atomic units on a machine with two recorded silent-failure incidents is a coin-flip you re-toss on every crash.

**The held-out-rule blocks (B6a + B6b, −99 h) become free, not cut.** `examples/irrigation_abm/config/agent_types.yaml` ships `high_threat_no_maintain` at `level: WARNING`, and your own project memory records that WARNING has no channel to the model — inert by construction. That is exactly the structure the pre-registration exploits in flood (§S4, `low_coping_block`). Score it in every arm, enforce it in none, inside runs you are already doing. Same design, zero marginal GPU, and *stronger* — no arm confound, because it is the identical run. `water_right_cap` appearing as ERROR for one agent type and WARNING for another is a second natural contrast worth a look, with the caveat that agent type is confounded.

**Sham theory (−43 h), non-determinism block (−36 h).** The placebo arm already strips rule content, which covers most of the "your validator is arbitrary" objection. Non-determinism: run 4 repetitions inside the G1 gate, state a bound in Methods, move on. Both are limitation paragraphs, not blocks.

**Never cut:** arms A′ and B′, and seeds below 5 on the anchor. Losing a model costs a table row. Losing a rung destroys the decomposition; losing seeds destroys the only inference the design supports.

### 5. On proportionality — a freed GPU is not a reason to use it

The marginal cost of a run is not the GPU-hour. It is one manifest review, one integrity decision, one more cell you must explain in an eight-page paper, and — this is the one that actually bites — one more thing to think about during the three weeks you are drafting the workshop paper. 149 runs and a five-term decomposition across four models is a *writing* problem you cannot solve in the 23 days between the 15 September freeze and the 8 October deadline. 40 runs and a five-term decomposition on two models is a figure you can draw and a paragraph you can write.

Against a 22% acceptance probability, 245 hours is proportionate because the artifact is useful on rejection (see below). 556 hours is not, at any GPU price, because the binding resource is the eight pages and the ten weeks.

### 6. The rejection case — and why irrigation makes it non-lossy

Modal outcome is rejection on 21 December, with the fallback venue in July 2027. Seven months of dead time is not an acceptable plan for the 78% branch.

Run on **irrigation**, the deliverable survives regardless: *the conformance statistic used in your own water manuscripts conditions on a post-treatment variable and overstates behaviour change by Γ; here is the premise-invariant replacement, and here is the mechanism.* That goes into NW Paper 1b's SI, or a short methods companion in Environmental Modelling & Software / JASSS / WRR, and — more importantly — it **pre-empts a reviewer who spots the conditioning problem in the journal paper.** A Nature Water reviewer who notices that the IBR denominator is itself treated could sink the submission. You would be building your own defence.

Run on **flood single-agent**, you get a pre-registered null in the low-enforcement regime, and it strengthens nothing.

This is a stronger argument for the testbed switch than the statistics are.

### 7. The opportunity cost, stated plainly

NW Paper 1b is at docx v29, SI v21, with a locked title, a verified asset map, and re-derived headline numbers. It has been unsent to Yang since 11 May. Its open items are: the flood-testbed provenance contradiction (Data Availability claims ACS+FEMA; the default path is synthetic), the SI Methods stitch, and Yang's review round. **Those are decisions and days, not months, and none of them need a GPU.**

Ten weeks is exactly enough to close that submission. It is also exactly the ten weeks the AAMAS campaign wants. If I have to choose for you: **the journal submission goes first, and the campaign runs in the background of it, unattended, at a size that does not require your attention.** That is the real argument for 245 hours over 556 — not the GPU, the fact that a 40-run queue can be babysat in ten minutes a day and a 149-run queue cannot.

Keep the workshop paper. It is four pages, non-archival, zero GPU, ~70%, and it forces the framing you need for both the AAMAS paper and the NW SI note. Budget **one week**, not three, and take the 29 August deadline over 22 August.

### 8. Three things that are not about AAMAS at all and outrank everything above

- **The PII.** Re-identifiable human-subjects records (lat/long + zipcode + income + household size + Qualtrics response ID) reachable from six of seven tags on a public repository, live since June. Repo private today; `filter-repo` across all branches and tags; you run the force-push personally because the global deny blocks the agent. This is not on the critical path of any paper and it should be done this week regardless.
- **The calibration band.** `insurance_lapse_rate` widened 0.05–0.15 → 0.15–0.30 with the Gallagher / Michel-Kerjan attribution untouched, uncommitted, in the tree right now. Revert it or re-source it in writing. This is the same failure mode as the EPI demotion your own pre-registration opens by confessing; do not add a second instance while writing a document whose credibility rests on the first one being an isolated lapse.
- **The strict integrity gate and the GPU/throughput assertions, before any queue starts.** `run_integrity.py` flags and never aborts, and checks only reflection-log non-emptiness. Add a strict mode for the new campaign path; leave the legacy flag-only path alone for byte-identity. This is the difference between 41 unattended days and 41 days of hand-watching, and hand-watching is what will cost you the workshop paper.

### 9. The calendar I would approve

| dates | queue | you |
|---|---|---|
| 29 Jul – 2 Aug | idle | PII purge · calibration revert · V-proxy on existing corpus · rewrite pre-reg §3.1 to irrigation-primary · commit + tag |
| 3–4 Aug | G1 gate (~5 h) | strict integrity gate + GPU/throughput asserts |
| 5–6 Aug | B0 bridge (26 h) | re-fit cost multipliers; **NW: send v29 + SI to Yang** |
| 6–13 Aug | anchor ladder (126 h) | analysis + figure code against B0 output |
| 13–18 Aug | replication + flood control (93 h) | workshop draft |
| 18–29 Aug | queue idle or re-runs | workshop paper → **29 Aug** · NW revisions on Yang's return |
| 29 Aug – 8 Sep | headroom: re-runs, third model only if NW is out the door | decomposition figure |
| **8 Sep** | — | **go / no-go on AAMAS**, nine days before the mandatory registration fee |
| 15 Sep | freeze | |

The queue finishes 18 August with three weeks of slack. That slack is the plan. A schedule that lands on 10 September against a 15 September freeze is not a schedule, it is a hope, and this project has two recorded multi-hour incidents arguing against hope.

**Files:** `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\AAMAS2027\experiments\appraisal_composition.csv` (the rejection-rate table that decides the testbed), `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\config\agent_types.yaml` (line 341, `high_threat_no_maintain` at `level: WARNING` — the free held-out rule), `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\AAMAS2027\experiments\rederive_executed_levels.py` (starting point for the V-proxy), `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\paper\nature_water\PAPER_ASSETS.md`.