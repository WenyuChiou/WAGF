# Supplementary experiment plan — for a main-track submission

Written 2026-08-05. Costs are measured from this corpus's own run history, not estimated from
model size.

**Premise:** the TAE route is closed and the target is a main-track venue (ICLR 2027, deadline
25 September 2026, pending confirmation). That is seven weeks. This plan says what those weeks
can buy, what they cannot, and in what order.

---

## 0. The enabling fact: the apparatus is already written

Seven commits sit unpushed on `p0-1-governance-instrumentation`. Two of them are the experiments.

| commit | what it gives us |
|---|---|
| `0c6aa60e` | **P0-1a: first-attempt proposal columns**, opt-in, default-OFF. `skill_broker_engine.py:365` computes `initial_labels = _extract_construct_labels(skill_proposal)` — the appraisal from attempt 0, snapshotted *before* the retry loop reassigns it. |
| `c701d01a` | **P0-1c: ADVISE disposition** — intervene without blocking, exactly one extra LLM call. A third enforcement mode. |
| `b9efe6ec` | `--governance-mode` exposed on the irrigation runner (was hardcoded `strict`). |
| `5dc063c5` | Arm identity pinned in the manifest; an undeclared governance profile now fails loudly. |
| `10e190cf` | Isolated config roots, so a new arm cannot contaminate a frozen one. |

**This is not "build then run". It is "turn the flag on and run".** The default-OFF design means
flag-OFF runs stay byte-identical to the frozen corpus, so the existing results are not at risk.

## 1. Measured cost basis

From consecutive finish times in `examples/irrigation_abm/results`, excluding idle gaps:

| cell | per run |
|---|---|
| gemma3:4b (anchor) | **9–16 h**, call it 11 h |
| gemma3:12b | governed 16–21 h, no-validator 7–8 h |
| ministral3:8b | governed ~16 h, no-validator ~5.5 h |

One anchor paired seed ≈ **22 h**.

---

## 2. E1 — Log the first attempt. Highest value by a wide margin.

**What it closes.** §8 opens with the paper's largest admission:

> "An accepted report after a retry is selected by the rule that judged it. This stratum is **24.3%**
> of governed decisions, and **its first attempt is absent from the shipped corpus**."

That absence is why §5 has to *infer* the mechanism by stratification. With `initial_labels` on, the
first attempt is no longer absent, and the mechanism becomes **directly observable**.

**The measurement.** For every governed decision that was blocked and then accepted, compare the
appraisal at attempt 0 with the appraisal on record. Then:

- if the appraisal **changes** between attempts, the paper's central claim moves from inferred to
  measured — enforcement demonstrably rewrites its own conditioning variable;
- if it **does not change**, then Figure 1's feedback edge describes something the data does not
  support, §5's world-composition story becomes the *whole* explanation, and the paper must say so.

**Both outcomes are publishable and one of them falsifies the current figure.** That is what makes
this an experiment rather than a confirmation, and it is the reason to run it first: everything
downstream — the figure, §5's framing, §8's wording — depends on the answer.

**Cost.** Anchor cell, 5 seeds × 2 arms = 10 runs ≈ **110 h ≈ 4.6 days**.

**Note on the no-validator arm.** Determine before launching whether its precondition rejections
also trigger a re-prompt. If they do not, that arm has no attempt-0/attempt-n distinction and only
the governed arm needs re-running, halving the cost. Check the retry-count column in an existing
no-validator run rather than assuming.

## 3. E2 — The ADVISE arm. A new result, not more of an old one.

**The question the paper cannot currently answer:** does the appraisal shift require *blocking*, or
is *being told* enough?

Every arm in the corpus is either full enforcement or none. `c701d01a` adds a middle: the agent is
given the rule feedback but the action is not blocked. If the shift appears under ADVISE, the
mechanism is about the message. If it needs blocking, the mechanism is about the retry.

This is a genuinely new finding and it is cheap, because it reuses the anchor's existing two arms as
its comparison.

**Cost.** Anchor, 5 seeds, 1 arm ≈ **60 h ≈ 2.5 days** (ADVISE adds one LLM call per decision).

## 4. E3 — Thicken the two thin cells

Both currently carry headline results on 3 seeds.

| cell | why it is thin | cost |
|---|---|---|
| **gemma3:12b** | the "whole apparent gain is composition" cell. 95% CI (−13.92, +14.25), p = 0.96 — an interval wider than the effect | +2 paired seeds ≈ **51 h** |
| **ministral3:8b** | the sign-reversal cell, the paper's strongest single result. Its unconditional delta is robust (p = 0.005) but the conditional clears zero by 0.02 pp at p = 0.049 | +2 paired seeds ≈ **43 h** |

These firm up existing claims rather than producing new ones. Lower priority than E1 and E2, but
cheap, and a reviewer will look straight at the n column.

## 5. Total

| | GPU hours | days |
|---|---|---|
| E1 first-attempt | 110 | 4.6 |
| E2 ADVISE | 60 | 2.5 |
| E3a gemma3:12b | 51 | 2.1 |
| E3b ministral3:8b | 43 | 1.8 |
| **subtotal** | **264** | **11** |
| failure buffer (+50%) | 132 | 5.5 |
| **total** | **~396** | **~16.5** |

Sixteen days of GPU inside a seven-week window. It fits, with room for the analysis and the writing
that must follow. The buffer is not padding: this corpus has a documented history of silent deaths
(anchor seed 44 and seed 46 both died mid-run and had to be relaunched).

## 6. Order, and why

1. **E1 first**, because the figure, §5's framing and §8's wording all depend on its answer. Running
   anything else first risks writing prose that E1 then contradicts.
2. **E3 in parallel where the GPU allows**, since it needs no code change and no decision.
3. **E2 after E1 reports**, because if E1 shows the appraisal does not move under blocking, the
   ADVISE comparison changes meaning.

## 7. Risks, named

- **Provenance.** Flag-ON runs are a different code state from the frozen corpus. `5dc063c5` pins arm
  identity and fails loudly on an undeclared profile, which is the guard. The precedent for getting
  this wrong is on record: the ministral seed-44 run was produced on a different broker commit and
  silently changed a string in `failed_rules`, which falsified a §3 claim until it was caught.
- **New runs change published numbers.** Every added seed forces a full re-derivation. The pipeline
  is automated (`run_all.py`), but every CLAIM marker must be re-verified, and the frozen brief in
  `table1_cells.py` and `fig3_consequence.py` must be updated deliberately, not tuned.
- **The reproducibility audit is RED.** It was narrowly waived for a non-archival PDF-only workshop.
  **That waiver does not transfer to an archival venue.** New runs should be produced with clean
  manifests so that at least the new arms are reproducible, even if the historic ones are not.
- **Hardware.** Verify `100% GPU` in `ollama ps` before every launch. On 2026-05-13 a driver update
  silently moved inference to CPU and cost four hours. Pause Windows Update for the duration; an
  auto-reboot has killed a run at year 10 before.

---

# ADDENDUM — pre-flight checks, and reuse for the Nature Water paper

Added 2026-08-05 after running the checks §2 asked for. **One assumption was wrong and one
opportunity was missed.**

## A1. The no-validator arm retries too. E1 needs both arms.

§2 suggested the no-validator arm might have no attempt-0/attempt-n distinction, which would halve
E1. Measured from the existing audit CSVs:

| run | rows | retried | max retry |
|---|---|---|---|
| governed seed 42 | 3,276 | 2,030 (**62.0%**) | 3 |
| no-validator seed 42 | 3,276 | 1,281 (**39.1%**) | 3 |
| no-validator seed 43 | 3,276 | 1,159 (**35.4%**) | 3 |

The water-right precondition blocks and re-prompts exactly as the validators do. **Both arms rewrite
their appraisal.** E1 must re-run both, and the cost stays at 110 h.

**This makes E1 a better experiment than it was framed as.** The question is not "does enforcement
rewrite the appraisal" — both arms do. It is **whether the governed arm rewrites it differently**.
Three outcomes, all informative:

- governed rewrites *more* → the mechanism is the validator layer, as §5 argues;
- both rewrite *equally* → the rewriting is generic to the retry loop, and the between-arm difference
  must come from somewhere else, which is §5's world-composition story doing all the work;
- governed rewrites *less* → the current framing is wrong and the paper needs rethinking.

The design already has its own control. That is worth more than the halved cost would have been.

## A2. Nature Water has the identical gap, and closing it costs ~12 hours

`examples/single_agent/analysis/compute_retry_compliance.py` — the NW paper's retry analysis — reads
`final_act`, `final_skill`, `final_tp`, `n_retries`. **It can count retries but cannot see what the
first attempt said.** `final_tp` is the flood domain's self-reported appraisal, so the missing
quantity is exactly the one P0-1a captures, in the paper Yang cares about.

**Cost.** Flood runs are far cheaper than irrigation: 1,000 decisions per run against 3,276. The one
consecutive back-to-back pair in the corpus (`JOH_FINAL/gemma3_4b/Group_C` Run_4 → Run_5) took
**1.2 h**. Five runs × two arms ≈ **12 h**, against E1's 110 h on irrigation.

Treat 1.2 h as indicative — it is a single observation. Even at three times that it is cheap.

**Recommendation: add a flood arm to E1.** For roughly a tenth of E1's cost, the same instrumentation
closes the same hole in a second paper. Do not substitute it for the irrigation arm — irrigation
carries the identification for the ICLR paper and flood has no action-to-environment feedback.

## A3. Four conditions the runs must meet to be reusable for NW

Producing data that a workshop paper can use is a lower bar than producing data a journal can use.
If NW reuse is intended, these are not optional.

1. **Use an isolated config root.** `10e190cf` exists for exactly this. The frozen v21 irrigation
   corpus and the `JOH_FINAL/Group_C` flood corpus are the current NW headline data and **must not
   be contaminated**. A new arm writes to a new root or it is not worth running.
2. **Match NW's model.** NW paper 1b's headline is **gemma3:4b**. A first-attempt arm on a different
   model tells NW nothing about its own numbers. Run gemma3:4b for the NW-facing arm even if the
   ICLR paper later wants others.
3. **Clean manifests, from the first run.** The reproducibility audit is RED for historic runs and
   was waived only for a non-archival workshop PDF. **A journal will not accept that waiver.** Every
   new run should carry a clean manifest so that at minimum the new arms are reproducible.
4. **Record the code state deliberately.** `5dc063c5` pins arm identity and fails loudly on an
   undeclared profile. The precedent for skipping this is on record: the ministral seed-44 run was
   produced on a different broker commit and silently changed a string in `failed_rules`, which
   falsified a §3 claim until it was caught by a figure's own gate.

## A4. Revised totals

| | GPU hours |
|---|---|
| E1 irrigation, both arms, 5 seeds | 110 |
| **E1-flood, both arms, 5 runs (NW reuse)** | **~12** |
| E2 ADVISE, irrigation anchor | 60 |
| E3a gemma3:12b +2 paired seeds | 51 |
| E3b ministral3:8b +2 paired seeds | 43 |
| **subtotal** | **276** |
| failure buffer (+50%) | 138 |
| **total** | **~414 h ≈ 17 days** |

The flood arm adds 4% to the budget and serves a second paper.

## 8. What seven weeks cannot buy, stated plainly

- **A second governance stack.** The most likely reviewer objection, and it is months of work.
- **A second measurement domain.** Flood is a portability demonstration with no action-to-environment
  feedback; it cannot carry identification.
- **Frontier models.** Possible only via API, at a cost nobody has scoped. If this matters, price one
  cell — 3,276 decisions × 5 seeds × 2 arms — before assuming it is out of reach.
- **gemma4:e2b's non-replication.** More seeds will not help; it already has five. Understanding why
  its fine-strata residual grows instead of collapsing is an analysis question, not a run.

Anyone planning this should say these four out loud at the start rather than discover them in week
six.
