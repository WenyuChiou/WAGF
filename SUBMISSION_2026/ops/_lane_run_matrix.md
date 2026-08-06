# Run Matrix — AAMAS 2027 mechanism decomposition

## 0. The one structural change I would make before anything else

`AAMAS2027/04_EXPERIMENT_PLAN.md` puts the 7-arm decomposition (P0-2, ~236 h) on the **flood** testbed. I think that is the wrong way round, and it is the single highest-leverage decision in this memo.

The decomposition needs decisions **where a theory rule actually fires**. Flood fires on 0.00–0.85 % of decisions; irrigation fires on 28.1–62.6 %. Cost per *fired* decision, using the measured numbers:

| testbed | model | arm C1, 5 seeds | GPU-h | decisions | fire rate | fired decisions | **fired / GPU-h** |
|---|---|---|---:|---:|---:|---:|---:|
| irrigation | gemma3:4b | 5 runs × 3.60 h × 1.25 | 22.5 | 16,380 | ~0.45 | ~7,371 | **327** |
| flood | gemma3:4b | 5 runs × 1.10 h × 1.25 | 6.9 | 5,000 | ~0.0085 | ~43 | **6.2** |

A ~53× difference in the currency that matters. Concretely: a 5-seed flood cell yields ~43 fired decisions, so the standard error on an arm-to-arm difference in that subsample is √(0.25/43) ≈ **7.7 pp**. The flood arms will be statistically indistinguishable from each other no matter what is true. Spending 236 GPU-h there buys a table of null cells.

**Recommendation: irrigation is the primary testbed for the decomposition; flood is retained as a cheap pre-registered falsification control at ~48 GPU-h instead of ~236.** This is also the framing that matches the anchor finding — the composition effect *is* the high-enforcement/low-enforcement contrast, so flood's job in this paper is to be flat, not to be measured precisely.

---

## 1. Cost model (stated explicitly so it can be checked and re-fit)

Base hours per 1,000 decisions, disabled arm (given, measured):

| model | h / 1,000 dec | ×3.276 → irrigation run (3,276 dec) | flood run (1,000 dec) |
|---|---:|---:|---:|
| ministral3:3b | 1.0 | **3.28 h** | 1.00 h |
| gemma3:4b | 1.1 | **3.60 h** | 1.10 h |
| ministral3:8b | 1.9 | **6.22 h** | 1.90 h |
| gemma3:12b | 1.9 | **6.22 h** | 1.90 h |
| ministral3:14b | 2.4 | 7.86 h | 2.40 h |
| gemma3:27b | 10.6 | **34.73 h** | 10.60 h |

Arm multipliers (given: advise/placebo ≈ 1.15×, enforce ≈ 1.40×; C1 interpolated since it makes strictly fewer calls than C3):

| arm | code | multiplier |
|---|---|---:|
| no-theory-rules | A | 1.00 |
| resample (extra draw, no text) | A′ | 1.15 |
| wrapper-only (scaffolding, no rule text) | A″ | 1.15 |
| placebo (report shape, content stripped) | B′ | 1.15 |
| advise (full rule text, never blocks) | B | 1.15 |
| enforce, max_retries = 1 | C1 | 1.25 |
| enforce, max_retries = 3 | C3 | 1.40 |
| sham-theory advise / enforce | S-adv / S-enf | 1.15 / 1.25 |
| held-out-rule scoring | — | +0.00 (scoring adds no LLM call) |

**Known weakness in this model, and the gate it implies.** The 1.15/1.40 multipliers were presumably fitted where fire rates are low. On irrigation, an extra-call arm should cost 1 + *f* ≈ **1.45×**, and enforce-3 could reach ~1.7–1.8× if agents commonly consume all three retries (the retry-stratified appraisal data shows they do reach 3). If the true irrigation multipliers are ~20 % higher on the non-A arms, total cost rises ~12–14 %, which consumes all headroom. **Gate: measure the realised multipliers on Block 0 and the first five runs of Block 1, then re-cost before committing Blocks 3 and 4.** This is a real risk, not boilerplate.

Budget assumption: 41 days (5 Aug → 15 Sep), 18 h/day nominal = 738 h, discounted ~15 % for the two known hazard classes and general slop → **~630 h realistically available**.

---

## 2. Which arms are load-bearing, and why each one is not a luxury

With `initial_proposal_columns` we now observe per decision: first-attempt appraisal *s*₁ and action *a*₁, final *s*_f / *a*_f, the executed action, and `llm_calls`. That makes the decomposition identifiable — but only against the right ladder, because the terms split into a **within-decision** part (visible inside one arm) and a **between-arm** part (not visible inside any single arm).

| term | how it is identified | arms required |
|---|---|---|
| **Action revision** | within C1: *s*_f = *s*₁ and *a*_f ≠ *a*₁, final conforms | C1 alone |
| **Premise revision (post-block)** | within C1: *a*₁ survives but *s*_f ≠ *s*₁ toward rule-inapplicability | C1 alone |
| **Premise shift (pre-block, text effect)** | shift in the marginal of *s*₁ between arms — the rules block sits in the prompt *before* the first call in B and C1 | **A vs B vs C1** |
| **Framing/report-shape nuisance** | shift in *s*₁ from being re-queried in a corrective-looking frame with no rule content | **B′** |
| **Prompt-restructuring / position nuisance** | shift from the wrapper alone (header, closer, task prompt moving head→tail, token count) | **A″** |
| **Free stochastic drift** | how much *s*₁ → *s*₂ moves under a second draw with zero added text | **A′** |
| **Composition / selection** | change in the conditioning-set prevalence, net of all of the above | the full ladder |

So the six-arm ladder **A → A′ → A″ → B′ → B → C1** adds exactly one ingredient per rung, and dropping any rung turns a clean contrast into a composite. That is the answer to "which are luxuries": none of these six. In particular, without A″ the term (B′ − A′) silently absorbs prompt restructuring, and without A′ every framing effect is contaminated by ordinary LLM resampling noise — which the retry-stratified non-monotonicity already suggests is non-trivial.

The genuinely optional arms:

- **C3 (enforce-3)** — not call-matched to a one-call advise arm, so it cannot enter the decomposition. Its job is external validity ("the deployed system") and continuity with the published corpus. Keep on the anchor model only. Run it in `intervention_framing: neutral` so that (C3 − C1) is a clean retry-budget contrast; the legacy-framing bridge is handled separately in Block 0.
- **Held-out rules** — answers a *different* question (induction vs filtering), not the decomposition. But it is the only design that kills the circularity objection, and after the P0-1e correction (governed conformance 0.00–0.86 % on every gemma model) that objection is the sharpest one in the file. Priority 1.5, not optional.
- **Sham theory (paired S-adv/S-enf)** — answers "is it *this* theory or rules-in-general". Strong reviewer defence, second-order for the decomposition. Tier 2.
- **`resample` as a standalone question** — already covered as A′.

---

## 3. The matrix

All blocks: seeds drawn from the identical set {42, 43, 44, 45, 46} across every arm within a block (the existing 42/4202/4203/45/46 vs 42/43/44/45/46 mismatch is what invalidated pairing on 6 of 9 flood configs — do not repeat it). Every run from a clean, tagged tree. `initial_proposal_columns`, `executed_skill_columns`, `llm_calls`, `require_profile` ON everywhere. `intervention_framing: neutral` on A′/A″/B′/B/C1/C3. No `gemma4:e4b` anywhere — it is non-deterministic at fixed seed on this stack.

| # | Block | Testbed | Model(s) | Arms | Seeds | Runs | Run-equiv (Σ mult × seeds) | Base h/run | **GPU-h** | Running total |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| **B0** | Corpus bridge + instrument smoke | irrigation | gemma3:4b | C3-legacy, disabled-legacy | 3 | 6 | 1.40×3 + 1.00×3 = 7.20 | 3.60 | **25.9** | 25.9 |
| **B1** | Anchor full ladder | irrigation | gemma3:4b | A, A′, A″, B′, B, C1, C3 | 5 | 35 | 8.25 × 5 = 41.25 | 3.60 | **148.6** | 174.5 |
| **B7** | Regime control (falsification) | flood | gemma3:4b + ministral3:3b | A, A′, B, C1 | 5 | 40 | 4.55 × 5 = 22.75 each | 1.10 / 1.00 | **47.8** | 222.3 |
| **B2** | Second-lineage ladder (core arms) | irrigation | ministral3:3b | A, A′, B, C1 | 5 | 20 | 4.55 × 5 = 22.75 | 3.28 | **74.5** | 296.9 |
| **B6a** | Held-out rules, anchor | irrigation | gemma3:4b | B, C1 × 2 reciprocal splits | 3 | 12 | 2.40 × 2 × 3 = 14.40 | 3.60 | **51.9** | 348.8 |
| **B5** | Complete 2nd ladder | irrigation | ministral3:3b | A″, B′ | 5 | 10 | 2.30 × 5 = 11.50 | 3.28 | **37.7** | 386.5 |
| **B3** | Scale rung 3 | irrigation | ministral3:8b | A, A′, B, C1 | 3 | 12 | 4.55 × 3 = 13.65 | 6.22 | **85.0** | 471.5 |
| **B4** | Scale rung 4 | irrigation | gemma3:12b | A, A′, B, C1 | 3 | 12 | 4.55 × 3 = 13.65 | 6.22 | **85.0** | 556.4 |
| — | **COMMITTED LINE** | | | | | **149** | | | **556.4** | |
| **B6b** | Held-out rules, 2nd model | irrigation | ministral3:3b | B, C1 × 2 splits | 3 | 12 | 14.40 | 3.28 | **47.2** | 603.6 |
| **B8** | Sham theory, paired | irrigation | gemma3:4b | S-adv, S-enf | 5 | 10 | 2.40 × 5 = 12.00 | 3.60 | **43.2** | 646.8 |
| **B9** | Non-determinism protocol | irrigation | gemma3:4b | C1, fixed seed × 8 reps | — | 8 | 1.25 × 8 = 10.00 | 3.60 | **36.0** | 682.8 |
| — | **STRETCH LINE** | | | | | **179** | | | **682.8** | |

Committed line = **556.4 GPU-h / 149 runs**, ~31 days at 18 h/day. Stretch = **682.8 h / 179 runs**, ~38 days. New decisions generated: 139 irrigation runs × 3,276 + 40 flood runs × 1,000 ≈ **495,000** — larger than the entire existing 432,083-decision corpus, on a clean tree, with first-attempt columns.

### Notes on specific design choices

**B0 first, always.** Six runs, 26 h, and it earns its place three times over: it is the first clean-tree run in the project's history, it is the end-to-end smoke test of every new column against a real LLM (the whole instrument has only ever seen a mock), and it is the only way to attribute any old-vs-new difference to the instrument rather than to the arm design. It also produces the realised cost multipliers that gate Blocks 3 and 4.

**B7 early, not late.** The flood control is a pre-registered *prediction* that the ladder is flat. If it is not flat — if appraisal shifts under advise on a testbed where rules fire on <1 % of decisions — then the shift is a text-priming effect, not enforcement, and every downstream block needs reinterpreting. You want that answer in mid-August, not mid-September. 48 h is cheap insurance and it is the correct size: flood cannot support precision, only a sign check.

**Held-out split design.** Two reciprocal splits so every rule appears on both sides — one split invites "you held out the easy rule." A useful economy: **arm A needs no held-out variant**, because when no theory rules are enforced the split is irrelevant and both rule subsets can be scored post-hoc on the B1/B2 arm-A runs. That drops the held-out block from 3 arms to 2 and saves ~42 h. Contrast reported: violation rate on the held-out subset under C1 vs B vs A. Improvement on never-enforced rules = induced behaviour; no improvement = the mechanism filters and the headline number is definitional. Both outcomes publishable; the second is more interesting and should be pre-registered as such.

**Seeds: 5 on the two cheap anchors, 3 on the two expensive rungs.** The per-cell N is enormous (78 agents × 42 yr), so within-cell precision is never the constraint — between-*run* variance is, which is exactly what seeds buy. Five seeds gives paired-t at df = 4 and matches the existing corpus convention. Going 5 → 3 on ministral3:8b and gemma3:12b saves 113 h and costs only the per-cell significance claim on those two rungs, where the claim being made is the *interaction* (does the decomposition change with scale), not the per-cell effect.

---

## 4. Models I would not run, with the arithmetic

**gemma3:27b — cut.** On irrigation it is 34.73 h *per run*.

| 27b option | runs | GPU-h | what it buys |
|---|---:|---:|---|
| Full 6-arm ladder × 3 seeds | 18 | 354 | a 4th scale point, at half the total budget |
| {A, B, C1} × 3 seeds | 9 | 354 → 354×(3.40/6.85)=176 | 3 arms, no framing controls |
| {A, C1} × 2 seeds | 4 | 156 | one contrast, no error bar |

The cheapest defensible 27b block is 156 h. The same 156 h buys **both** ministral3:8b *and* gemma3:12b at 3 seeds (170 h) — two scale points with real error bars instead of one without. 27b is dominated on every margin. The top of the capability axis should be covered by the frontier-API tier (P0-4 in the existing plan), which costs 0 GPU-h, spans more than one lineage, and reaches far beyond 27b. That tier belongs in this plan and should have its smoke test in week 1, since the audit found the cloud provider path has never appeared in a run manifest.

**ministral3:14b — cut.** 7.86 h/run on irrigation; a 4-arm × 3-seed block is 107 h. It sits between 8b and 12b on the ladder and adds a fourth point in an already-crowded region. 107 h is better spent on B6b + B8.

Resulting scale ladder: **3B → 4B → 8B → 12B, two lineages, 4× parameter range.** That is honestly a modest scale claim. It should be written as one — "across a 4× open-weight range plus two frontier API models", not "across model scale".

---

## 5. Priority order for execution

Run strictly in this order. Each row is a stopping point where the paper is still a paper.

| P | Block | GPU-h | Cum. | What exists if the calendar stops here |
|---:|---|---:|---:|---|
| 0 | B0 bridge/smoke | 25.9 | 25.9 | Clean-tree replication of the published corpus + verified instrument. Not a paper. |
| 1 | B1 anchor ladder | 148.6 | 174.5 | **The decomposition exists**, one cell, 5 seeds, all six controls. This is the paper's core figure. |
| 2 | B7 flood control | 47.8 | 222.3 | + the regime falsification test. Core claim is now defended against "it's a text effect." |
| 3 | B2 second lineage | 74.5 | 296.9 | + replication in a different model family. "Not a Gemma artifact." |
| 4 | B6a held-out (g4b) | 51.9 | 348.8 | + induction-vs-filter answered. **This is the minimum viable submission.** |
| 5 | B5 complete m3b ladder | 37.7 | 386.5 | + two *complete* six-arm ladders, so the framing-constancy assumption is tested, not assumed. |
| 6 | B3 ministral3:8b | 85.0 | 471.5 | + a third scale point; a scale claim becomes possible. |
| 7 | B4 gemma3:12b | 85.0 | 556.4 | + fourth point, 4× range, 2 lineages. **Committed line.** |
| 8 | B6b held-out (m3b) | 47.2 | 603.6 | + generalization result holds in two families. |
| 9 | B8 sham theory | 43.2 | 646.8 | + "it's the theory, not rules-in-general." |
| 10 | B9 non-determinism | 36.0 | 682.8 | + an N-seed protocol; converts a reproducibility embarrassment into a Methods finding. |

**Minimum viable = P0–P4 = 348.8 h ≈ 19–20 days at 18 h/day.** That fits in *half* the window. If everything slips, the submission still stands.

**What I would cut, in order:**

1. **B9 non-determinism (−36 h).** Replace with a 4-repetition flood version at 5.5 h, which is enough to state a bound in Methods. Cut this first because it is the only block whose entire output is a caveat.
2. **B8 sham theory (−43 h).** Demote to a limitation paragraph plus related work. Painful — it is the best single answer to "your validator is arbitrary" — but the placebo arm already strips rule *content*, which covers most of that ground.
3. **B6b held-out on ministral3:3b (−47 h).** The induction-vs-filter result then rests on one model; write the one-model caveat explicitly rather than hiding it.
4. **B4 gemma3:12b (−85 h).** Scale ladder tops out at 8B: 3B/4B/8B, still three points and two lineages.
5. **B3 ministral3:8b (−85 h).** The scale claim dies entirely and the paper becomes a single-scale decomposition plus the flood regime control. This is the floor at which I would consider redirecting to the AAAI-28 fallback rather than submitting a weakened AAMAS paper.

Note the cut order deliberately protects breadth over depth *below* the committed line and depth over breadth *above* it: seeds 5 → 3 on the anchor would save 59 h but destroys the headline cell's error bars, so it is not on the list at all.

---

## 6. Calendar, and the writing collision

| dates | queue | student |
|---|---|---|
| 29 Jul – 4 Aug | idle | finish instrument, clean tag, **pre-register** (primary outcome, arms, mixed-effects spec, arm×scale interaction test), pilot |
| 5–6 Aug | B0 (26 h) | **GATE: re-fit cost multipliers.** If irrigation non-A arms exceed ~1.5×, cut B4 now, not in September. |
| 6–15 Aug | B1 (149 h, 8.3 d) | analysis code against B0 output |
| 15–18 Aug | B7 (48 h, 2.7 d) | **GATE: is the flood ladder flat?** |
| 18–23 Aug | B2 (75 h, 4.2 d) | workshop paper drafting |
| 20–29 Aug | B2 tail + B6a (52 h) run **unattended** | **workshop deadline 29 Aug** — hands off the queue |
| 29 Aug – 1 Sep | B5 (38 h) | first pass on the decomposition figure |
| 1–6 Sep | B3 (85 h) | writing |
| 6–11 Sep | B4 (85 h) | writing |
| 11–15 Sep | B6b / B8 / B9 as time allows | **freeze 15 Sep** |
| 17 Sep | — | **AAMAS author registration (mandatory)** |

The 20–29 Aug workshop-writing window is the real scheduling constraint, not the GPU. Blocks needing supervision (B0, B1, B7) are placed before it; the long unattended blocks straddle it.

**Operational hardening, given the two recorded incidents:**
- Pause Windows Update for the full window and renew weekly (the pause caps at 35 days, which is shorter than this queue). The recorded reboot killed a run at year 10.
- A GPU-utilisation watchdog that aborts and alerts if Ollama drops to CPU. The recorded silent-CPU fallback ran 4 hours at 12× slow with no error — at 12× that incident alone would burn ~48 h of this budget.
- Per-year JSONL checkpointing on, so a kill costs one year not one run; `broker.tools.recover_csv_from_jsonl` is the recovery path.
- Pre-flight check that the F1 silent-drop fix covers the ministral3:3b flood path before B7 — the existing ministral3:3b flood data is 65–73 % capture and B7's whole value is that it is clean.
- Assert `git_dirty == false` and a non-null commit in every manifest as a **run precondition**, not a post-hoc audit. 94 of 171 existing manifests record no commit at all; that must not recur in a corpus this size.

---

## 7. Honest summary

The committed plan is **556 GPU-h across 149 runs**, against ~630 h realistically available — about 12 % headroom, which is thin. The plan survives that thinness only because the cut order is declared in advance and the minimum viable submission (349 h) fits in half the window. The two things most likely to break it are the cost-multiplier assumption on irrigation enforce arms (gated at 6 Aug) and the machine losing days to the two known hazard classes (mitigated above, not eliminated).

The largest single judgement call is moving the decomposition from flood to irrigation. If that call is wrong, the entire matrix is wrong. It rests on one number: rules fire on 28.1–62.6 % of irrigation decisions and 0.00–0.85 % of flood decisions, so flood cannot support a decomposition at any budget — 236 GPU-h there would produce ~43 fired decisions per cell and standard errors near 8 pp.

Relevant files: `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\AAMAS2027\04_EXPERIMENT_PLAN.md` (the plan this supersedes on the testbed question), `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\AAMAS2027\experiments\appraisal_composition.py` (the anchor finding), `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\core\_advise.py` and `_advise_pass.py` and `_retry_loop.py` (the instrument, mock-tested only).