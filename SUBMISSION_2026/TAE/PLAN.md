# PLAN — TAE submission

> **Entry point is [HANDOVER.md](HANDOVER.md).** This file is a working record and its status
> claims go stale. Anything about whether something passes, is complete or is ready is measured
> by `evidence/corpus_inventory.py`, `evidence/run_all.py` and `paper/submission_gate.py` --
> prefer those three to any sentence here.

> ## The calendar in this file is about two weeks overtaken. Do not follow it day by day.
>
> Written **2026-07-31**, when there was no manuscript. There is now a finished draft, a built PDF
> inside the page limit, and a title — work this file schedules for **16 August** was done on
> **2 August**. §1's "no manuscript file exists yet" and §3's Blocks 0–3 are both obsolete, and §4's
> B/C items are closed.
>
> **Two parts are still live and load-bearing, and exist in no other file:**
> **§2's forbidden-claims table** — eleven rows, each with the incident that earned it — and
> **§5's experiment fences**. Read those. Ignore the dates.
>
> For what to do next, read `STATUS.md`. For anything a script can measure, run the check that
> measures it:
>
> ```
> python SUBMISSION_2026/TAE/evidence/corpus_inventory.py     # is the experimental material enough?
> python SUBMISSION_2026/TAE/evidence/run_all.py              # are all the numbers still right?
> python SUBMISSION_2026/TAE/paper/submission_gate.py         # is this ready to submit?
> ```

Deadline **29 Aug 2026 AoE**.

Supersedes the schedule in `DECISION.md` §11 (which budgets the work but not the calendar) and every
date in `CAMPAIGN_PLAN.md`. `DECISION.md` remains the decision of record for *content*: venue, claim,
mechanism, structure, claims discipline. This file is the decision of record for *sequence*.

Sources it is built from, each named per item below:
**lane A** = `TAE/BACKLOG.md` (backlog sweep) · **lane B** = `TAE/BOUNDARY.md` (folder contract) ·
**lane C** = figure/artefact audit · **lane D** = `TAE/EXPERIMENT_OPTIONS.md` (experiment costing) ·
plus `TAE/DECISION.md`, `TAE/NUMBERS.md`, `audit/MATERIALS_VERDICT.md`.

---

## 1. Status in five lines

1. **Decided:** venue (TAE, 8 pages, 29 Aug, double-blind, non-archival), the claim, the corrected
   mechanism, the 8-page structure, the analysis set, and the claims-discipline list — `DECISION.md`.
2. **Built:** the whole evidence pipeline — zero GPU, an independent second implementation that
   agrees on every headline value (`_verify_pipeline.py`), and 15 structural contamination guards
   that a self-test actively attacks. It has grown since this line was written; **run
   `evidence/run_all.py` for the script count and `evidence/corpus_inventory.py` for the run
   count** rather than trusting the numbers that used to be here.
3. **Left: this item is obsolete. The manuscript exists** — `paper/manuscript.md`, nine numbered
   sections, four figures, two tables, a title, and a built PDF that clears the page limit. The six
   blocking corrections and the four rendered-artefact fixes are applied. Use `STATUS.md` for what
   is actually left.
4. **Not a paper item and ranked above all of it:** human-subjects PII is still live in a PUBLIC
   repo's git history, two days past its own deadline (`CAMPAIGN_PLAN.md` R1, verified today).
5. **The single thing most endangering the deadline:** the recommended GPU run (option 1). It is the
   only item that can consume days without producing prose, and its downside branch forces a rewrite
   of §5, §8 and the abstract at roughly day 15. It is fenced by a hard go/no-go on **6 Aug** and a
   hard freeze on **14 Aug**; if either fence is crossed, the run is abandoned and the paper is
   unchanged. Nothing in §§3–6 may depend on it.

---

## 2. The claim and the discipline — the writer never needs another file for this

**Write this sentence (`DECISION.md` §2):**

> When a governance layer's norm conditions on a state the agent itself reports, the conformance
> statistic has no observation channel independent of the process it governs, so enforcement rewrites
> the distribution of its own conditioning variable and the reported gain cannot be separated into
> behaviour and composition by that statistic.

**The mechanism, established and not to be contradicted (`DECISION.md` §4):** the appraisal moves
mainly because the intervention **changed the world** and the agent **reported the changed world
accurately**. Three independent supports: year-1 null under maximum retry pressure; the never-retried
shift is *larger* (+48.21 vs +40.02 pooled, 5 of 5 cells; +49.1 vs +40.45 before 2026-08-03); the shift tracks the reservoir. Lead with
*"even a perfectly honest agent breaks the statistic; the metric is most misleading exactly when the
intervention is most effective."*

**Concede, in §1, in our own words, before a reviewer does it:** this is **not** a systems
contribution. AgentSpec's DSL constrains nothing about what a predicate may read; SAVeR already
enforces verification over internal belief states. It is an **evaluation** contribution.

**Concede in §8:** the corpus can **bound** but not **separate** honest re-reporting from a residual
gaming component.

**Forbidden — grep for each of these before submission (`DECISION.md` §10):**

| ❌ | why |
|---|---|
| any assertion of **premise revision** | falsified by this corpus, three ways |
| flood as a **"low enforcement pressure control"** | it has no action→environment feedback (`run_flood.py:285-291`); it is a cross-theory portability demonstration |
| **"behavioural feasibility"** unqualified | term collision with arXiv:2603.21435 — relabel or fence in a footnote on first use, and the fence must cover **figure legends**, not only body text (lane C) |
| **"the appraisal mediates the governance effect"** | transmission is unsupportable (Paul et al. 2024) |
| any claim the **first-attempt appraisal is recoverable from this corpus** | it is not — three checks, all negative (`DECISION.md` §5) |
| **endogeneity as the differentiator** | Gao et al. arXiv:2607.24604 already own post-treatment risk-set bias; use the no-independent-channel argument |
| a **corrected effect size** for the conformance gain | the unconditional rate is a decomposition term, not a corrected estimate |
| a **monotone / dose-response** pressure→shift relation | regime is perfectly confounded with testbed; within-irrigation Pearson is the wrong sign |
| **"governed rejections are 100% behavioural theory"** | 100% name *a validator rule*; only 3,840/6,469 = **59.4%** name an appraisal-conditioned one |
| **"no-validator rejections are 100% on increase proposals"** | 99.95% (6,168/6,171). Prefer the structural argument, which is exact |
| **"both arms reject a substantial share"** unscoped | anchor cell only (29.0 / 5.3 / 3.6 / 1.5 / 1.0%) |

**Sign convention, non-negotiable:** `Delta = (no-validator) MINUS (with-validators)`; positive means
the validators lowered the quantity. `decomposition/RESULTS.md` uses the opposite convention — the
same anchor effect is **−23.02** there and **+23.02** here. Never quote across the two in one sentence.

**Cell value = mean of per-seed rates, never pooled.** Inferential unit is the seed; paired t, df=n−1;
`ministral3:8b` excluded from every paired contrast and shown separately.

---

## 3. Day-by-day to 29 August

Working assumption: ~5 productive hours/day. Every day names an output, not an activity.

### BLOCK 0 — corrections and prep · 31 Jul – 4 Aug (5 days)

| date | output | items |
|---|---|---|
| **Thu 31 Jul** (today, remainder) | Repo private. `run_all.py` green. Venue facts locked. | **P0.1 handoff** (Wenyu personally — the agent's global deny blocks the force-push). **B4**: `DECISION.md:97` "+40.4" → "+40.45", re-run `run_all.py`, expect 6/6 PASS. **W1**: read the TAE CFP, record dual-submission clause + page limit + OpenReview id + date-read in `DECISION.md` §1. **Template width**: obtain the TAE/NeurIPS `.sty`, record the text-column width in `BOUNDARY.md`. |
| **Fri 1 Aug** | Flood provenance restated. Experiment prerequisites met or the run is dead. | **B1** (30 m), **B6** (1 h). **P0.2**: revert or justify the `insurance_lapse_rate` edit. **Experiment prereq**: commit or stash the 6 dirty `examples/multi_agent/flood/` paths, `git status --porcelain` empty, tag `tae-firstattempt-2026-08-01`, pause Windows Update for the window. |
| **Sat 2 Aug** | `evidence/e0_year1_exogeneity.py` exists and passes. | **B2** (2 h). Launch the option-1 queue if the go decision is yes (§5 below). |
| **Sun 3 Aug** | `evidence/e1_first_attempt_limits.py` exists; flood instrument decided. | **B3** (2 h), **B5** (2 h). |
| **Mon 4 Aug** | **NUMBER FREEZE.** All artefacts regenerated, no retracted number on any rendered page. | **C1–C4** (§4 below, ~3 h). Re-run `run_all.py` → 6/6 PASS. Re-read every figure PNG at the confirmed column width. Update `NUMBERS.md` §0/§8/§11/§12 and delete the rows the new scripts close. |

**Gate 0 → writing:** do not start §3 until `run_all.py` exits 0 and `NUMBERS.md` §11 ("claims no
script produces") is empty or every remaining row is explicitly marked as prose-only.

### BLOCK 1 — §3 to §6, the paper · 5 – 11 Aug (7 days)

| date | output |
|---|---|
| **Tue 5 Aug** | **§3 drafted** (1.0 pg) — *(done 2 Aug; and the heading "the two rule layers separate" was retired on 3 Aug as an overpromise, replaced by "Which rules read what the agent says")*. Fig 1 placed. The within-stack contrast, 59.4 / 40.6 on the page, layer-level disjointness stated exactly. |
| **Wed 6 Aug** | **§4 drafted** (1.5 pg) — the conditioning variable moves. Per-cell table, both arms' prevalence, the one number nobody reports. **HARD GO/NO-GO on the experiment (§5).** |
| **Thu 7 Aug** | **§5 first half** — year-1 null, retry pressure with its stratum named on every number. |
| **Fri 8 Aug** | **§5 complete** (1.75 pg) — never-retried stratum with its caveat travelling attached, reservoir trajectory, the honest-reporting conclusion. |
| **Sat 9 Aug** | **§6 drafted** (1.0 pg) — conditional vs unconditional, 12B highlighted, LAST-PROPOSED reading named. |
| **Sun 10 Aug** | **§3–§6 number audit**: every printed value traced to a script stdout line in `NUMBERS.md`. Nothing survives that is not there. |
| **Mon 11 Aug** | Slack inside the block. Mid-run check on the queue: integrity assertion per completed seed. |

### BLOCK 2 — §1, §2, §7, §8 · 12 – 15 Aug (4 days)

| date | output |
|---|---|
| **Tue 12 Aug** | **§1 drafted** (1.0 pg). The gap; the systems-novelty concession in one sentence. |
| **Wed 13 Aug** | **§2 drafted** (0.75 pg) + **§7 drafted** (0.5 pg). Flood introduced as a portability demonstration. |
| **Thu 14 Aug** | **§8 drafted** (0.5 pg): acceptance-selection + the first-attempt limitation; provenance (**W8** — mixed-vintage flood arms, irrigation manifest drift, and the standing prohibition on any commit-level reproducibility claim); two open-weight families ≤27B; regime confounded with testbed. **EXPERIMENT FREEZE — analysis is frozen on whatever seeds passed integrity by end of today.** |
| **Fri 15 Aug** | Appendix assembled: the option-1 result **if n ≥ 3**, otherwise the appendix section is deleted and §8 keeps only the limitation sentence. Provenance appendix. |

### BLOCK 3 — abstract and full read · 16 Aug (1 day)

| **Sat 16 Aug** | **Abstract + title written last.** Then one uninterrupted read-through and the trim to 8 pages. |

### BLOCK 4 — red team · 17 – 20 Aug (4 days)

| date | output |
|---|---|
| **Sun 17 Aug** | **Claims red-team.** Grep the manuscript for every ❌ in §2 of this file. Each hit is either removed or defended in writing. Re-argue §12 of `DECISION.md` (the "that's just coupled simulations" attack) against the drafted text. |
| **Mon 18 Aug** | **Citation re-verification.** `verify-references` on all five framing citations — AgentSpec, SAVeR (arXiv:2604.08401), Gao et al. (arXiv:2607.24604), Park (arXiv:2603.21435), Paul et al. (10.18653/v1/2024.findings-emnlp.882) — plus every other reference. Two of the five decide a framing choice; if one fails, §1–§3 change. |
| **Tue 19 Aug** | **Double-blind sweep.** The WRR 2026 predecessor and the Nature Water manuscript in the **third person** throughout. No author names, no institution, no acknowledgements, no funding, no repo URL, no `C:/Users/...` or other identifying path in any figure, caption, appendix or artefact CSV. Anonymised code link only. PDF metadata stripped. |
| **Wed 20 Aug** | **Artefact sweep.** Figures re-rendered at the confirmed column width and read at print size; every caption re-read against `NUMBERS.md`; `run_all.py` green; the `NUMBERS.md` ↔ manuscript cross-check re-run end to end. |

### BUFFER · 21 – 28 Aug (8 days)

Unallocated on purpose. **Do not schedule into it.** Its jobs, in order, only if needed: absorb an
overrun from any block; absorb a red-team finding that requires re-drafting; absorb an incident on the
GPU queue; absorb a CFP surprise from W1.

| **Thu 28 Aug** | **Submit.** OpenReview dry run, PDF page count, anonymity re-check, then submit. |
| **Fri 29 Aug** | Absolute last day (AoE). Reserved for a submission-system failure only. |

**Buffer accounting:** 31 Jul – 29 Aug inclusive is 30 calendar days. Blocks 0–4 commit
**21** (31 Jul – 20 Aug, including the slack day already inside block 1); **8 free** (21 – 28 Aug);
**1** reserved for a submission-system failure (29 Aug). If any block overruns by more than two days,
cut §7 to three sentences and cut the appendix — in that order — before touching the buffer.

---

## 4. The blocking list, ordered

Nothing in Block 1 starts until every row here is done. Total ~12 h, **zero GPU, no new data.**

### Blocks drafting (lane A: `BACKLOG.md` B1–B6)

| # | item | est | definition of done |
|---|---|---|---|
| **B4** | `run_all.py` exits 1. `fig2_mechanism.py` computes +40.45; `DECISION.md:97` writes +40.40. | 1 h | `DECISION.md:97` reads **+40.45**; `python SUBMISSION_2026/TAE/evidence/run_all.py` exits **0**, 6/6 PASS. **Adjudication:** lane A said "decide the pooling basis"; lane C established the computed value is correct and the brief was written to 1 dp against a 2 dp tolerance. **Lane C wins** — correct the prose, never the script. Nothing is tuned. |
| **B1** | `README.md` and `NUMBERS.md` §8 call the flood corpus "known-partial (F1 silent-drop)". It is not damaged. | 30 m | Both files say coverage is <100% because **relocation is a designed absorbing state that ends participation**; the F1 attribution is deleted; the per-run-rate rule is retained. **Adjudication:** `MATERIALS_VERDICT` vs the TAE docs — MATERIALS_VERDICT is right; measured on 5/5 `ministral3_3b/Group_C` runs, `audit rows = 1000 − relocated` **exactly** (764/236, 705/295, 714/286, 735/265, 756/244). |
| **B2** | The cornerstone "at year 1 the two worlds are provably identical" has no script in this folder. | 2 h | `TAE/evidence/e0_year1_exogeneity.py` exists, takes its run directories from `_data.irrigation_run()`, prints the year-1 exact-equality rate and the first divergence year, is added to `run_all.py`, and passes. **Adjudication:** lane A said "port or cite external"; lane B established the source is 739 lines, needs pandas, and discovers runs by `glob` — the exact hazard `_data.py` exists to make unreachable. **Lane B wins: re-derive minimally, do not copy.** `DECISION.md` §4 and `NUMBERS.md` §11 then cite the local script. |
| **B3** | The §5/§8 limitation rests on four unscripted inspections. | 2 h | `TAE/evidence/e1_first_attempt_limits.py` recomputes and prints all four — retry counts, the single-generation `raw_output`, `proposed_skill == final_skill` on 2,007/2,030, and the load-bearing **one JSONL record per (agent, year)** claim — and is added to `run_all.py`. The corresponding rows leave `NUMBERS.md` §11. Note: the retry counts were re-derived by lane A and `DECISION.md` §5 is **correct** (3,276 rows / 2,030 retried / 763 approved after retry = 23.3%); the JSONL claim is the one still unchecked. |
| **B5** | The two flood arms may have measured threat appraisal with different instruments (`RESULTS.md` S5). | 2 h | The producer of `construct_TP_LABEL` is traced in **both** arms. If identical → flood deltas may be printed with the per-run-mean basis. If not → **flood becomes descriptive text with no numbers**, and §2/§6 are written accordingly. Partly closed already: both arms carry the same 5-level scheme, but one stray lowercase `l` in the no-validator arm proves the parse is not identical. |
| **B6** | `JOH_FINAL/gemma3_4b/Group_C/Run_1` ran a different prompt and is disclosed nowhere in `TAE/`. | 1 h | Either the seed is dropped from every flood number (governed n=4) **or** it is the third bullet of `NUMBERS.md` §8 and of the paper's §8. Flood is descriptive-only, so disclosure is the cheap route — take it unless B5 kills flood numbers anyway. |

### Blocks shipping the figures (lane C — rendered artefacts print retracted numbers)

These do not block drafting, but they are the 2026-07-31 retractions reappearing on pages a reviewer
reads. Do them on 4 Aug with the number freeze. **None of them changes a computed value.**

| # | item | est | definition of done |
|---|---|---|---|
| **C1** | `fig1_rule_layers.py` panel c renders `6,168 / 100.0%` against a stated `n = 6,171`. | 20 m | The panel reads **99.95%** (2 dp for that label) and the caption gives the **structural** reason — the precondition exists only on the two increase skills — rather than an empirical near-100%. |
| **C2** | `table1_cells.py` §C prints `theory 6,469 (100.0%)` — verbatim the retracted formulation. | 20 m | The printed column is renamed **`named a validator rule`** (leave `_data.rejection_cause`'s internal key alone), with the **3,840 / 2,629** sub-split beside it. |
| **C3** | `fig1_rule_layers.py` panel A labels the split as 23.4% / 16.1% of *all decisions*; the 59.4% is only in stdout. | 40 m | **59.4% / 40.6% appear on the figure.** The one number the correction was about must be on the page. Optional and worth it if time allows: split panel c's validators-on bar by rule kind, which is the genuine within-stack contrast `DECISION.md` §7 asks Figure 1 to carry. |
| **C4** | Four caption/docstring statements outrun their data. | 1.5 h | (a) `fig2` caption "71% **of them**" → "71% **of all year-1 decisions**" (70.5% is over all year-1 decisions, not over the retried 82.1%; "of them" would be 86%). (b) `fig2` docstring line 26 — delete "and stays there"; the script's own output says the arm does not. (c) `fig2` panel A title — scope it: the shift is absent at year 1 and established from ~year 12; years 2–11 oscillate, with **year 4 = −18.46 pp (p=0.004)** and **year 7 = −6.41 pp (p=0.001)** significantly negative. Do not leave those unremarked inside a panel titled "moves only after". (d) `fig3` caption title "collapses" → "shrinks, and on one model removes entirely" (anchor +23.02 → +21.62 is a 1.39 pp gap), plus one clause saying the unconditional rate is a decomposition term, not a corrected estimate. (e) `fig1` docstring — scope the "both arms reject a substantial share" claim to the anchor cell. (f) `table1` §A — add the `role` column inline so flood is not read as a low-pressure control. |

### Decide before any flood delta is printed — a live lane disagreement

| the two sides | pick, and why |
|---|---|
| Flood `ministral3:3b` ΔHIGH: the brief and `MATERIALS_VERDICT` say **−0.22** (pooled, n_gov=3674); `table1_cells.py` computes **−0.15** (mean of per-run rates). Both reproduce; both are internally correct. | **Take −0.15, the per-run mean.** It is the convention every other number in this folder uses and that `_data.py` enforces in code. Knock-on: the low-regime mean is **+0.58**, not +0.56. The sign is negative either way and no qualitative statement changes. Restate the chosen basis in `DECISION.md` and `NUMBERS.md`. Nothing gates this automatically — `table1_cells.py` checks flood against nothing — so it will not surface again on its own. **Moot if B5 rules flood descriptive-only.** |

### Do while writing (lane A, W-items) — none blocks a section

`W1` CFP + `W4` citations are **pulled forward** (31 Jul and 18 Aug) because each can change a framing
decision. `W2` (drop "1.84 shortage tiers" and the −0.514 Pearson — no script produces either),
`W3` (name the stratum on every retry number: anchor year-1 82.1/70.5 · anchor all-years 63.8/44.4 ·
five cells pooled 74.14/51.09), `W8` (provenance disclosures) fold into the drafting days above.
`W9` (flood IBR reconciliation) is **deferred by decision** — under the current §2 the paper prints no
flood conformance rate, so it is not owed.

**Outside the write boundary — needs the user's explicit go before an agent touches them:** `W5`
(`SUBMISSION_2026/README.md` supersession banner + delete the false "that column now exists"),
`W6` (stale AAMAS2027 `appraisal_composition` pair; `rederive_executed_levels.py:59` glob),
`W7` (`evidence/claude_verified_facts.md` "use as ground truth" + unreproducible counts). None affects
a TAE number; all three mislead the next session that greps them.

---

## 5. Experiment decision — one run, fenced

**RUN OPTION 1, AND NOTHING ELSE** (lane D, `EXPERIMENT_OPTIONS.md` §2):
first-attempt appraisal logging, **governed arm only**, `gemma3:4b` anchor cell, `--real`, 42 years,
strict, seeds 42–46. **52 GPU-h, 2.5 days wall-clock, zero code changes** — one YAML key
(`global_config.audit.initial_proposal_columns: true`, plus `executed_skill_columns` free) in an
isolated complete config copy, `--output` always explicit.

**Why this and not the others.** It is the only candidate that attacks the paper's self-declared
weakest point (`DECISION.md` §5, §8, §12), and lane D established the load-bearing fact: the code at
HEAD **does** persist attempt-0 appraisal labels (`skill_broker_engine.py:364-366` →
`_audit_helpers.py:109-131` → `audit.py:253-256`), verified end to end on a real LLM. `DECISION.md`
§5 is right about the **shipped corpus** and out of date about the **current code**. The statistic is
**within-run and within-decision**, so the new corpus never has to reproduce a published number —
which is what makes it safe to run at a different code state.

Rejected, with reasons, so they are not re-litigated: **rule ablation** — removing the two
appraisal-conditioned rules removes 3,882 of 10,507 rule fires, so demands and therefore the reservoir
diverge between arms, and the appraisal difference is confounded by exactly the channel §5 identifies;
104 GPU-h for a number the paper would have to disclaim. **Reservoir pinning** — needs a new code path
in frozen `examples/`, 1.5–3 d of coding before any GPU, breaks mass balance, and the paper already
owns the control three ways. **More seeds** — every new seed runs at HEAD while existing seeds run at
older dirty states, which *manufactures* the mixed-vintage defect in cells currently clean on that
axis; separation is already complete under six stratifications.

### The fences — these are the decision, not commentary

| fence | date | rule |
|---|---|---|
| **Prerequisite** | **1 Aug** | `git status --porcelain` empty (commit or stash the 6 dirty `examples/multi_agent/flood/` paths), tree tagged, Windows Update paused. Not met → the run does not start. |
| **HARD GO/NO-GO** | **6 Aug** | If the queue has not started by end of 6 Aug, **abandon the run permanently.** It does not get rescheduled into the writing window. |
| **Per-run integrity** | each run | 3,276 audit rows, 3,276 sim rows, zero `(agent, year)` gaps or duplicates, non-empty `reflection_log.jsonl`, `initial_labels` non-empty on >95% of rows, wall-clock within 2× of 10.4 h. **Exit 0 is not evidence** — three documented silent-failure modes (Windows Update reboot, 100% CPU fallback, exit-0 silent death). A run that fails any assertion is not in the analysis. |
| **FREEZE** | **14 Aug** | Analysis freezes on whatever seeds have passed. n ≥ 3 → report with df = 2, matching the paper's own convention on its 3-seed cells. **n < 3 → delete the section.** |
| **Budget the downside** | — | If attempt-0 → accepted drift generalises, §5/§8/abstract need one careful paragraph distinguishing the **cross-arm** shift (world-driven; untouched by this run) from a **within-decision revision channel** on the retried quarter. Different quantities; no falsification. **One extra writing day is pre-authorised for this.** |
| **Invariant** | always | §§3–6 derive entirely from the shipped corpus. If the queue dies, the paper is unchanged. |

The both-arms add-on (+41 GPU-h, +1.7 d) is **conditionally approved**: take it only if all five
governed seeds have passed integrity by **12 Aug**. Otherwise skip it and say in §8 that the bound was
measured on the arm where the selection stratum is largest (governed 24.3% vs no-validator 6.3%).

---

## 6. Boundary contract

1. **Write only inside `SUBMISSION_2026/TAE/`.** Everything the paper needs lives here: `DECISION.md`,
   `NUMBERS.md`, `BOUNDARY.md`, `BACKLOG.md`, `EXPERIMENT_OPTIONS.md`, this file, `evidence/`,
   `figures/`, and (if the run proceeds) `runs/`.
2. **Read anything.** In practice exactly four file kinds under `examples/*/results/` plus the frozen
   configs; 41 run directories; `_verify_pipeline.py` prints `forbidden-token hits: 0`. New scripts
   **must** import `_data` and must not construct a path, a glob, an arm selector, or a rate definition.
3. **Never modify `examples/`, `paper/`, or `broker/`** — frozen experiments and a paused manuscript.
   Two `paper/` findings are **recorded and not acted on**: six Nature Water drafts were edited
   2026-07-30 13:31 (untracked, gitignored, no diff recoverable) and
   `figures/Fig3_cumulative_adaptation.{png,pdf}` were overwritten 2026-07-30 23:16 by a script that
   drops one of three series. Both need the user's eyes when NW is unpaused. Also recorded for NW only:
   `PAPER_PUNCHLIST.md` line 27's "100% behavioural-theory rules" is the pre-correction overstatement
   and may have travelled into the NW SI.

---

## 7. Risk register

| # | risk | trigger | mitigation |
|---|---|---|---|
| R1 | **TAE dual-submission policy is unconfirmed** and a main-track version is planned. An exclusivity clause invalidates the venue choice. | CFP text read on 31 Jul says work under review elsewhere is not permitted. | Read the CFP **today** (W1, 15 min) and record the answer with the date. If exclusive: the fallback venues explicitly welcome work under review elsewhere, but they are 4 pages — the decision then is *this paper at 8 pages elsewhere* vs *main track first*, and it must be made in Block 0, not in the buffer. |
| R2 | **Double-blind slip.** Easy to forget; fatal at desk-reject. | Any first-person reference to the group's WRR 2026 predecessor or the Nature Water manuscript; a repo URL; an identifying path in a figure or artefact CSV; PDF metadata. | Dedicated red-team day (**19 Aug**), not an afterthought. Grep list fixed in §3 Block 4. Re-checked once more on submission day. |
| R3 | **The option-1 run eats the writing window or forces a §5 rewrite.** | Queue not started by 6 Aug; or <3 clean seeds by 14 Aug; or attempt-0 drift generalises. | The three fences in §5. Abandon rather than reschedule; delete the section rather than shrink the buffer; one pre-authorised extra writing day for the downside branch. |
| R4 | **The unbalanced cell is challenged.** `ministral3:8b` is 3 governed vs 2 no-validator and is excluded from every paired contrast. | A reviewer reads the exclusion as post-hoc cherry-picking. | The exclusion is enforced in code (`_data.IRRIGATION_UNBALANCED_PREFIXES`, currently `_data.py:201` — search the name, not the line) on a **design** criterion, predates the analysis, is stated in `README.md`, and the cell is still shown separately and marked. **`evidence/corpus_inventory.py` checks in both directions whether that exclusion is still true, and says so when it has outlived its reason — a run that would balance this cell was being written on 3 August.** Say all of that in §2 in one sentence; do not bury it in §8. Gate 0 also passes without it (48.06 pp mean vs a pre-fixed 30 pp bar). |
| R5 | **The corpus bounds but cannot separate honest re-reporting from residual gaming.** | A reviewer asks for the decomposition. | State it ourselves in §8 before it is found. The never-retried stratum (larger shift, no appraisal ever rewritten) and the year-1 null are the bound. Name the frozen-world arm as "what would settle it" — and do not run it. |
| R6 | ~~**Figure layout is built at 6.8 in and the template width is unverified.**~~ **CLOSED 2026-08-01.** | — | The premise is false twice over: `paper/template/` holds `neurips_2026.sty`, `neurips_2026.tex`, `checklist.tex` and the official author kit, and the text width is **exactly 5.5 in**, read out of `neurips_2026.sty:127-141` (see `BOUNDARY.md`). The good branch is the real one — the figures rescale and survive; no re-layout was needed. |

---

## 8. Definition of submission-ready

Tick every line. Any unticked line means not ready.

**Evidence**
- [ ] `python SUBMISSION_2026/TAE/evidence/run_all.py` exits **0**, all scripts PASS, on a clean checkout.
- [ ] `_verify_pipeline.py` prints `INDEPENDENT VERIFICATION: EVERY VALUE AGREES` and `forbidden-token hits: 0`.
- [ ] `_data.py` self-test prints `SELF-TEST: CLEAN`, 15 guards.
- [ ] `NUMBERS.md` §11 ("claims no script produces") is empty, or every remaining row is marked prose-only and carries no number.
- [ ] Every numeric value in the manuscript traces to a named script and stdout line in `NUMBERS.md`.
- [ ] No figure or table renders `100.0%` where the value is 99.95%, and no artefact prints "theory … 100%".

**Claims**
- [ ] Every ❌ in §2 grepped against the full manuscript, zero hits.
- [ ] Systems novelty conceded in §1, in our own words.
- [ ] "Behavioural feasibility" relabelled or fenced on first use, **including in figure legends**.
- [ ] Every retry number names its stratum; every flood mention names it a portability demonstration.
- [ ] Sign convention stated once and used consistently; nothing quoted across `RESULTS.md`.
- [ ] §8 states the acceptance-selection limitation, the first-attempt limitation, the provenance defects, and that the corpus bounds rather than separates honest re-reporting from gaming.

**Venue**
- [ ] Dual-submission policy read, recorded with the date, and compatible with the main-track plan.
- [ ] ≤ 8 pages excluding references, in the correct template.
- [ ] Double-blind sweep passed: no names, institution, acknowledgements, funding, repo URL, identifying paths in figures/captions/appendix/CSVs, or PDF metadata.
- [ ] Every reference verified by `verify-references`; the five framing citations verified individually.
- [ ] Figures re-rendered at the confirmed template width and read at print size.

**Housekeeping**
- [ ] P0.1 closed — repo private, history purged across all branches **and all 7 tags**, force-push done by Wenyu, IRB number or exemption on file. *(Not a submission dependency. It outranks the submission.)*
- [ ] P0.2 closed — the calibration edit reverted or justified in writing.
- [ ] Appendix present with the option-1 result **or** absent by the 14 Aug freeze rule. Never partially present.

---

## 9. What this plan deliberately does not do

- It does not schedule any Nature Water work. That manuscript is **paused by the user**. Two findings
  caused by this workspace are recorded in `BACKLOG.md` (N11, N12) and in §6 above, and neither is
  acted on from a TAE session.
- It does not schedule the AAMAS campaign. Lane A verified it is **not started** — no `attempt_labels`,
  no per-call seed, no CRN in `broker/`, no `strict` in `run_integrity.py`, no `AAMAS2027/campaign/`,
  no `aamas2027-*` tag. Its Gate 5 on 8 Sep is a no-go by construction and needs re-planning **after**
  29 Aug, not before.
- It does not reopen anything in `BACKLOG.md`'s ALREADY DONE or DROPPED tables. Both carry their
  evidence; several items kept reappearing only because the raising document was never updated.
