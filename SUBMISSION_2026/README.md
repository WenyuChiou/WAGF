# SUBMISSION_2026 — campaign workspace

Gitignored (`.gitignore:291`). This repo is public; nothing here is for the public tree.

## What this is

Getting WAGF into a top venue, on two tracks:

| tier | target | deadline | GPU | odds |
|---|---|---|---|---|
| **1** | NeurIPS 2026 workshop, 4 pp, non-archival | **29 Aug** | **zero** | **~72%** |
| **2** | AAMAS 2027 main track | reg **17 Sep** · paper 8 Oct | 333 h | ~25% |
| **3** | fallback: AAAI-28 AI for Social Impact | ~Jul 2027 | reuse | — |

Tier 1's evidence is **already on disk and verified**. It does not depend on a single new run.

## The finding

> Enforcing a behavioural-theory norm on an LLM agent changes what the agent **says about the
> world**, not only what it does — and the standard conformance metric conditions on exactly that
> self-report, so the reported effect is part behaviour and part composition.

Verified across 14 model×testbed cells, complete regime separation:

| regime | cells | enforcement pressure | appraisal shift |
|---|---:|---|---|
| irrigation (rules bind) | 5 | 28–63% rejected | **+38.13 pp** (all +21…+48) |
| flood (rules loose) | 9 | 0–0.85% rejected | **+0.56 pp** (−3.7…+6.3) |

Lowest high-pressure cell (+21.26) still exceeds the highest low-pressure cell (+6.25).
Reproduce: `python SUBMISSION_2026/evidence/appraisal_composition.py`

**Open question the campaign answers**: is this *premise revision* (the agent restates its appraisal
so the rule stops applying) or *selection* (high-appraisal decisions trip the rule more, so they
retry more)? The shipped corpus cannot tell — the first-attempt appraisal was never persisted. That
column now exists.

## Files

| path | what |
|---|---|
| `CAMPAIGN_PLAN.md` | **the plan of record** — run matrix, schedule, gates, cut list, open decisions |
| `evidence/appraisal_composition.py` | the workshop paper's whole evidence base, one command, zero GPU |
| `evidence/fallback_scenarios.py` | what the conformance number becomes under each fallback semantics |
| `evidence/rederive_executed_levels.py` | executed-vs-proposed correction across the corpus |
| `evidence/claude_verified_facts.md` | everything verified directly against code/data this session |
| `papers/workshop_skeleton.md` | tier-1 paper: section plan, drafted abstract, claims discipline |
| `ops/environment.md` | model availability, costs, hazards, provenance requirements |
| `ops/_lane_*.md` | raw workflow lane outputs, archived verbatim |
| `runs/` | campaign outputs (empty until the queue starts) |

Superseded material lives in `../AAMAS2027/` — keep it for the defect findings, which stand; its
venue recommendation and its "two experiment families" framing do not. See
`../AAMAS2027/00_FRAMING_CORRECTION.md`.

## The two structural corrections the planning produced

**1. The decomposition runs on IRRIGATION, not flood.** My earlier plan had it on flood. That was
wrong and would have been fatal: flood fires a theory rule on 0.00–0.85% of decisions, so a 5-seed
cell yields ~43 fired decisions and a standard error of ~7.7 pp on any arm-to-arm difference — the
arms are statistically indistinguishable *no matter what is true*. Per GPU-hour, irrigation buys
~327 fired decisions against flood's ~6.2, a **53× difference in the currency that matters**. Flood's
job is to be flat (the control), not to be measured precisely.

**2. Pre-registration v1 was self-falsifying.** With flood primary, the maximum attainable primary
contrast is 0.85 pp against a pre-committed ±5 pp equivalence margin — it would have returned
"claim falsified" with probability ≈1 for reasons unrelated to truth. Fixed in v2, with a dated
supersession note committed before any data exists.

## Deliberately under-spending the GPU

Committed line is **333 h of ~630 h available — 47% utilisation, finishing 25 Aug, three weeks
before the freeze.** That slack is the plan, not waste. The binding constraint is eight pages and
one student's attention: 149 runs is 149 integrity reviews landing in the writing window. The scale
axis was cut because the pre-registration already commits to calling any scale interaction
exploratory — so those runs would buy a term we have pre-committed not to claim.

## Non-negotiables

- **Never cut** any of the six anchor ladder arms (A / A′ / A″ / B′ / B / C1). Losing a rung turns a
  clean contrast into a composite and destroys the decomposition. Losing a *model* costs a table row.
- **No interim outcome looks** between 6 Aug and the 15 Sep freeze. Monitoring is restricted to run
  health, manifest conformance, capture rate and call matching.
- **Every run from a clean tagged tree.** Not one of the 347 existing runs has clean provenance; the
  queue must refuse to start otherwise.
- **Nature Water wins** any week where it and the campaign contend.

## Corrections to this file

**2026-07-30 — flood low-regime mean corrected from +0.81 pp to +0.56 pp.** `appraisal_composition.py`'s
flood glob was `JOH_FINAL/<model>/**/*governance_audit.csv`, which recursed into
`ministral3_3b/Group_A/Run_1_bak_broker/` and pooled **903 rows from a different experiment**
(Group_A has no structured prompts and is not a clean ablation of Group_C) into that cell's governed
arm. It flipped that cell's sign, +2.04 pp to **−0.22 pp**. It was the only such file in the flood
corpus, so exactly one of fourteen cells was affected. The glob now names `Group_C` /
`Group_C_disabled` explicitly and skips `_`-prefixed directories. High-regime numbers are unchanged
and the separation is still COMPLETE.

**The "432,083 decisions" figure is being used two different ways.** It is a count over the whole
347-run corpus (`evidence/claude_verified_facts.md`), but the workshop abstract attributes it to the
14 model x testbed cells, which hold **216,020** decision rows. The abstract must say 216,020, or say
347 runs without implying the cells.
