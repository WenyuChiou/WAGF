# WAGF metric definitions (canonical implementations)

Every metric used by this skill cites the exact production implementation.
Never reimplement; always import or shell out.

**All reference values below were re-derived from disk on 2026-08-20** on the
v21 irrigation corpus (gemma3:4b, seeds 42-46) and the single-agent flood
corpus (gemma3:4b, `JOH_FINAL/Group_C` vs `JOH_ABLATION_DISABLED/Group_C_disabled`,
Run_1-5). If a number you compute disagrees with a table here, the disagreement
is real and must be resolved before it goes in a paper.

Rates are displayed to 2 decimals; **every delta column is computed on the
unrounded values**, so two of them are 0.01 off the difference of the two
displayed rates (irrigation executed 25.90, flood published 12.61). That is
display rounding, not a disagreement.

---

## Read this first: three choices change the number

The same "IBR" can mean four different things. Whenever you report one, state
all three of these, because every one of them moves the answer:

| Axis | The choices | How much it moves the number |
|---|---|---|
| **Denominator scope** | every row / rows where the agent decided / rows where a rule applies | flood governed 0.76% vs 0.87% vs 1.60% |
| **Action column** | last proposal after retries / what actually executed | irrigation governed 36.05% vs 0.86% (**42x**) |
| **Aggregation** | rate per seed then mean / pool every row then one rate | irrigation EHE 0.6724 vs 0.6765 (illustrated on EHE because no IBR aggregation variant was computed) |

The published Nature Water numbers use **rule-applies denominator + last
proposal + per-seed-then-mean**. That combination, and only that combination,
reproduces the paper.

**The action column is the trap.** `yearly_decision` (simulation log) and
`final_skill` (audit csv) both record the agent's LAST PROPOSAL after the retry
loop, not what executed. On a `status == REJECTED` row the broker executes the
registry default (`maintain_demand` for irrigation) and the proposal never
happens. Measured 2026-08-20 across 5 irrigation seeds: **5,845 rejected
increase-proposals in the governed arm, and the water request rose in 0 of them**
(mean delta +0.0000); the no-validator arm is the same, 4,754 rows, 0 rises.
`proposed_skill == final_skill` on 100% of rows in all three reference domains,
so no column in the shipped corpus records governance changing an action, and
`run_flood.py:460`'s `governance_intervention` flag is always False. The
attempt-0 columns that would close this gap (`initial_skill`, `initial_labels`,
`attempt_skills`, commit `0c6aa60e`) are **default-OFF and postdate every
published run** — computing an attempt-0 metric requires a re-run.

---

## IBR / AAI (appraisal-action inconsistency)

One sentence, both domains: **among the decisions for which a behavioural rule
applies given the agent's own reported appraisal, the fraction whose action
contradicts that rule.** Prose calls it "appraisal-action inconsistency"; tables
call it AAI; the code still calls it IBR.

### Irrigation

```
denominator  agent-years with wsa_label in {H, VH}          <- NOT all rows
numerator    of those, yearly_decision in {increase_large, increase_small}
IBR          100 * numerator / denominator
aggregate    one rate per seed, then the unweighted mean over 5 seeds
```

Canonical: `SUBMISSION_2026/decomposition/_loader.py::ibr()` (12 lines).
Reproduce the whole table with
`python SUBMISSION_2026/decomposition/reproduce_published.py`.

| denominator | action | governed | no-validator | delta |
|---|---|---|---|---|
| **wsa in {H,VH}** | **last proposal** | **36.05** | **59.07** | **23.02** <- PUBLISHED |
| all 3,276 rows | last proposal | 40.90 | 62.52 | 21.62 <- SI companion measure |
| wsa in {H,VH} | executed | 0.86 | 26.77 | 25.90 |
| all 3,276 rows | executed | 3.60 | 33.50 | 29.90 |

The two arms' denominators are different sizes: high-WSA rows per seed are
1,074-1,330 governed against 2,633-2,777 no-validator. Expressed as a share of
all decisions that is **37.1% against 82.8%**, a 45.7 pp gap. The appraisal is
produced by the same LLM call as the action, so this denominator is
post-treatment; see the caveat section.

### Flood

```
denominator  agent-years whose threat_appraisal is in {H, VH, VL, L}
             medium threat triggers no rule and is EXCLUDED
numerator    R1  threat in {H,VH}  and action == do_nothing
             R3  threat in {VL,L}  and action == relocate
             R4  threat in {VL,L}  and action == elevate_house
             R5  already elevated  and action == elevate_house   -> TRACKED, NOT COUNTED
IBR          100 * |R1 u R3 u R4| / denominator
aggregate    one rate per run, then the mean over 5 runs
```
Map `relocated` -> `relocate` before matching. Rows whose `threat_appraisal` is
null made no decision (the agent already relocated) and are not in either side.

| denominator | governed | no-validator | delta |
|---|---|---|---|
| **threat-relevant (M excluded)** | **1.60** | **14.22** | **12.61** <- PUBLISHED |
| rows where a decision was made | 0.87 | 7.41 | 6.54 |
| design-fixed 100 agents x 10 years | 0.76 | 7.10 | 6.34 |
| threat-relevant, **R5 included** | 22.46 | 33.04 | 10.58 |

**The denominator ladder, per run** (governed Run_1 shown; the shape holds for all):

```
1000   design: 100 agents x 10 years
 -147  agents that already relocated make no decision that year (143 of the 147)
 853   decisions actually made
 -342  threat_appraisal == M, which triggers no rule
 511   the published denominator
```

Two things worth knowing about that ladder. The M exclusion is severe in early
years: **year 1 has 79 of 100 agents at M, so the year-1 denominator is 21
decisions.** And relocation is itself an outcome of the treatment — the governed
arm relocates 2.6x more (106 against 41 agent-years out of 1,000) — so the
design-fixed denominator dilutes the arms unequally. That dilution is mild and
runs *against* the paper: moving to the decision-rows denominator widens the gap
from 6.34 to 6.54 pp.

Two facts to state whenever the flood numerator is described: **R3 and R4 are
zero in all five governed runs**, so the governed figure is R1 alone despite
being presented as a three-rule composite; and **excluding R5 carries the
result** — including it moves governed from 1.60% to 22.46%, roughly 93% of the
governed arm's would-be violations.

> **OPEN DEFECT — the drafts disagree with each other on this pair.** The SI has
> moved to the unified conditional definition and reports **1.6 / 14.2**
> (`supplementary_information_v15.md:533`). The main-text Results draft has not:
> `section2_v19_results.md` still carries the pre-unification **0.9 / 8.5** in
> both its prose and Extended Data Table 2, and neither 1.60 nor 14.22 appears
> anywhere under `paper/nature_water/drafts/` outside the SI. Tracked as backlog
> N5. Check which draft is live before quoting either number, and do not write a
> cross-domain sentence calling both domains "AAI" without saying which
> denominator each one used.

### Caveats that belong with any IBR number

- **The denominator is post-treatment.** The appraisal that defines it is
  emitted by the same LLM call as the action, in the arm being treated. A
  contrast conditioned on it does not identify a causal effect. For irrigation
  the two arms' denominators differ by 45.7 pp of appraisal mass; **for flood
  they barely differ at all (51.1% against 52.0%)**, which is why flood is the
  clean testbed and irrigation is where this bites.
- **Do not "fix" it by dropping physically impossible proposals.** Excluding
  agent-years already at the water-right cap moves ΔIBR from 23.02 to 6.59 pp,
  because 42.2% of no-validator high-WSA rows are at the cap against 0.0%
  governed. But being at the cap is downstream of the treatment, so excluding it
  is the same post-treatment conditioning error. Report the concentration; do not
  re-estimate on it.
- **The identified alternative is the unconditional companion**, denominator
  fixed by design, `e1_total_effect.py`: **-21.62 pp**, CI [-26.80, -16.45],
  paired t = -11.608, df = 4, p = 0.000315 — 93.9% of the published magnitude.
- The full six-estimator robustness suite, each with an independent verifier that
  shares no code with it, is `SUBMISSION_2026/decomposition/`; its verdict memo
  is `RESULTS.md` (SURVIVES-WITH-REFRAMING) and the fix list is
  `PAPER_PUNCHLIST.md`.

---

## EHE (Effective Heterogeneity Entropy)

```
EHE = H(action distribution) / log2(k)
      H = -sum p_i log2 p_i over the observed actions
      k = size of the agent's action interface, NOT the number of observed actions
```
- Irrigation **k = 5** (increase_large, increase_small, maintain_demand,
  decrease_small, decrease_large)
- Flood **k = 4** (do_nothing, buy_insurance, elevate_house, relocate)

**Unconditional** — every row, no appraisal filter. This is the one place the two
metrics part company: in flood, IBR uses 511 rows and EHE uses ~996.

**Row set.** Irrigation: all 3,276 rows. Flood: every row with a non-null
`yearly_decision`, which **includes the carried-forward `relocated` rows** (they
map to `relocate` and do count); only the 4 rows with no decision at all are
dropped. Do not use the 853 decision rows or the 511 threat-relevant rows.
Those 4 are the same 4 the IBR ladder leaves over: of the 147 rows with no
appraisal, 143 are carried-forward `relocated`, which EHE keeps and IBR does
not, leaving 4 that neither uses.

**Aggregation: one EHE per seed, then the mean.** Not pooled, and never
yearly-averaged then meaned (yearly-averaging gives ~0.63 and is wrong).

| domain | aggregation | governed | no-validator |
|---|---|---|---|
| irrigation (k=5) | **per-seed then mean** | **0.6724** | **0.8569** <- what Supp Fig 1 plots |
| irrigation (k=5) | all-seed pooled | 0.6765 | 0.8595 |
| flood (k=4) | **per-run then mean** | **0.8614** | **0.7861** |

The flood pair reproduces `gen_fig3_case2_flood.py`'s printed 0.861 / 0.786
exactly. Rule-based PMT is 0.598 for reference.

> **OPEN DEFECT.** The main text and SI report irrigation EHE as
> **0.687 / 0.848** (`section2_v19_results.md:25` and its table at :37, SI:841).
> That pair reproduces under **neither** aggregation. The per-seed standard
> deviations do match (+/- 0.046 and +/- 0.011), which suggests the same
> computation on an earlier data vintage. Supplementary Figure 1 regenerates
> pixel-identical using 0.672 / 0.857, so the figure and the prose currently
> disagree. SI:534's ΔEHE = -0.18 matches 0.857 - 0.672 = 0.185, not
> 0.848 - 0.687 = 0.161, so the statistic sides with the figure.

Direction convention: **ΔEHE = governed - no-validator**, and
**ΔIBR = no-validator - governed** so that positive means validators reduced it.
The paper quotes magnitudes, so signs flip between code and prose.

---

## Where each published number is computed

| Output | Script |
|---|---|
| Fig 2 (irrigation) | `paper/nature_water/scripts/gen_fig2_case1_irrigation.py` |
| Fig 3 (flood) | `paper/nature_water/scripts/gen_fig3_case2_flood.py` |
| Supp Fig 1 (EHE x AAI scatter) | `paper/nature_water/scripts/gen_fig3_crossmodel.py` |
| Supp Fig 2 (trajectories) | `paper/nature_water/scripts/gen_sfig_crossmodel_trajectories.py` |
| Supp Tables 1 & 6 | `paper/nature_water/scripts/analysis_2026-05-31/gen_tableS1_S6_crossmodel_unified.py` |
| Headline reproduction from raw | `SUBMISSION_2026/decomposition/reproduce_published.py` |
| Canonical loader + `ibr()` | `SUBMISSION_2026/decomposition/_loader.py` |

`paper/` is gitignored, so those five figure scripts are not recoverable from
git. `SUBMISSION_2026/decomposition/` is tracked and is the durable copy of the
computation.

## Other metrics

- **BRI (Behavioural Rationality Index)** = 1 − IBR, so it inherits IBR's
  conditional denominator and every caveat above. The SI leans on it:
  governed 63.9% against no-validator 40.9% for irrigation, with a null-model
  baseline of 60% because 3 of the 5 skills are non-increase
  (`supplementary_information_v15.md:534`).
- **Rejection rate**: fraction of decisions with `status != "APPROVED"`.
  Read `household_governance_audit.csv:status`. One row per agent-year — retries
  are collapsed into `retry_count`, never separate rows, so retries can never
  inflate any denominator on this page.
- **Retry rate**: fraction with `retry_count > 0`. **Mean retries**: mean of
  `retry_count`.
- **Retry compliance Pattern A/B/C** — A: TP lowered, proposal retained;
  B: TP held, action more protective; C: both change.
  Canonical: `examples/single_agent/analysis/compute_retry_compliance.py`.
- **Temporal diagnostics M1/M2/M3** — M1 appraisal-history coherence, M2
  behavioural inertia, M3 evidence-grounded irreversibility. Canonical:
  `examples/single_agent/analysis/compute_temporal_diagnostics.py`
  (`--gemma4-pipeline {v1,v2}`).
- **Paired t-test**: `scipy.stats.ttest_rel` on matched seeds, CI via
  `scipy.stats.t.interval(0.95, df=n-1, ...)`. Reference implementation:
  `SUBMISSION_2026/decomposition/e1_total_effect.py` (the old pointer here,
  `gen_sfig_forest.py:paired_stats`, is inside a do-not-run script).
  With n = 5 the exact sign-flip
  permutation floor is 0.0625, so any p below that is parametric-only and must
  be labelled as such. **Check the seeds are actually matched first**: the six
  gemma3/ministral3 flood models pair governed seeds 42/4202/4203/45/46 against
  no-validator 42/43/44/45/46, so `ttest_rel` is pairing seed 4202 with seed 43.
  The three gemma4 models are 42-46 on both arms and are clean.

## Do NOT use

- `examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py` for a
  headline IBR. Its `compute_ibr_components` divides by `len(work)`, and `work`
  is a frame read from `household_governance_audit.csv` — which holds one row
  per decision the broker was actually asked to make (857 / 879 / 946 on
  governed Run_1-3), **not** the 1,000-row design grid. So its denominator is
  the **decision-made** row of the flood table above: it gives 0.87 / 7.41, not
  the published 1.60 / 14.22 and not the design-fixed 0.76 / 7.10.
  `CLAUDE.md` still names it canonical; that pointer is stale. The function is
  fine for R1/R3/R4/R5 component counts.
- `paper/nature_water/scripts/gen_sfig_forest.py` — writes the adopted
  Supplementary Figure 1 filename with a different plot and the old
  unconditional denominator. Its printed Gemma-3 4B ΔIBR of +6.54 is the
  unconditional row above, not the published one.
- `examples/single_agent/analysis/{nw_flood_pmt_crosstab, nw_flood_ibr_decomposition,
  nw_ehe_annual_decision}.py` — all three use `Group_A` as the no-validator arm.
  The baseline is `Group_C_disabled`; `Group_A` is a different experiment
  (no structured prompts). Open as backlog item N10.
- Deleted 2026-08-20 because every data path they referenced was a v20 directory
  that no longer exists: `compute_ibr.py`, `ensemble_analysis.py`,
  `governed_vs_ungoverned.py`, `nw_comprehensive_analysis.py`,
  `ibr_wsa_aca_decomposition.py` (all under
  `examples/irrigation_abm/analysis/`).

## What this skill does NOT compute

- **Cohen's d** and **bootstrap CIs**: only by request.
  `examples/irrigation_abm/analysis/nw_bootstrap_ci.py`.
- **Construct-action coherence rate**: out of scope.
- **WAGF Coherence Index**: does not exist; refuse if asked.
