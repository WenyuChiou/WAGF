# Submission readiness — NeurIPS 2026 TAE workshop

> **Entry point is [HANDOVER.md](HANDOVER.md).** This file is a working record and its status
> claims go stale. Anything about whether something passes, is complete or is ready is measured
> by `evidence/corpus_inventory.py`, `evidence/run_all.py` and `paper/submission_gate.py` --
> prefer those three to any sentence here.

> ## Read this before anything below it
>
> **The verdict this file used to open with is out of date, and so are its file:line references.**
> It was written against the manuscript as it stood on **1 August 23:36**. The manuscript has been
> revised heavily since — a title was written on 2 August, the appendix was deleted, several
> captions were rewritten, and three references were added. An audit on **3 August** resolved 22 of
> this file's `manuscript.md:NNN` pointers and found that **none of them lands on the line it
> names**. Do not navigate by them; search for the quoted text instead.
>
> **For current status, run the checks — they measure, this file asserts:**
>
> ```
> python SUBMISSION_2026/TAE/evidence/corpus_inventory.py     # is the experimental material enough?
> python SUBMISSION_2026/TAE/evidence/run_all.py              # are all the numbers still right?
> python SUBMISSION_2026/TAE/paper/submission_gate.py         # is this ready to submit?
> ```
>
> `submission_gate.py` covers, and re-measures on the built PDF every run, most of what §2's
> checklist below asserts by hand: the page limit, the figure and table counts, the fonts, the
> anonymity sweep, the reference and citation counts, and the build guards.
>
> **What is still worth reading here, and is in no other file:** §3's weakest-link analysis of the
> argument — that §5 standardises on a variable §7 declares treatment-affected, and that the
> never-retried stratum is filtered on the *outcome* in one arm and on *action* in the other. That
> is the sharpest criticism written of this paper. Risks **R2, R7 and R12** are also still live.
> §6 (internship strategy) is not a submission document.

**Superseded verdict, kept for the record.** As of 1 August this file read: *"NOT READY — the
manuscript has no title, the abstract and §5 assert a monotone dose-response that the
forbidden-claims list bars and that §4 explicitly disclaims two pages earlier, the Figure 2 caption
describes three panels that are not in the figure it is bound to, and the statistic named 'the
rule's antecedent' in Table 1 and §4 is one conjunct of a two-conjunct rule."* **Four of those five
are fixed**: the title is written and renders on page 1, the dose-response sentences are deleted,
the caption is rewritten, and the antecedent is disclosed in §4 as a conjunction. Of the ten
blocking items in §1, items 1, 2, 3, 5, 6, 9 and 10 have been applied.

---

## 1. The shortest path

In this order. Items 1–4 are the ones a reviewer finds in the first minute.

| # | Fix | Where | Cost |
|---|---|---|---|
| 1 | Write the title | `manuscript.md:1`, `manuscript.tex:32` | author decision |
| 2 | Delete the dose-response claim, two sentences | abstract L18, §5 L285–287 | 2 min |
| 3 | Rewrite the Figure 2 caption to describe the figure that exists | §5 L325–337 | 15 min |
| 4 | Fix the antecedent mis-specification (W1) — numbers below, they are cheap | §2 L66, §4 L153, Table 1 caption L203 | 30 min |
| 5 | `70.5% of all year-1 decisions` → `of governed year-1 decisions` | §5 L294 (and the string baked into `fig2_mechanism.py`) | 5 min |
| 6 | Add in-text callouts for Figures 1 and 2 | §3, §5 | 10 min |
| 7 | Reconcile "excluded from every paired contrast" with "5 of 5" and "20 paired seeds" | Table 1 caption, §5 L300–303, §6 L360, §8 L426 | 10 min |
| 8 | Label the two bases for the enforcement range (28.1–62.6 pooled-count vs 28.09–62.63 per-seed-mean; the upper bound was 62.19 until ministral3:8b joined the paired basis 2026-08-03) | §3 L97, §4 L178 | 5 min |
| 9 | Confirm which PolicyGuard `[3]` is, and reword "for twenty-five years" | §1 L28, L31 | author decision |
| 10 | Scope "The agent is a faithful instrument" to the anchor cell | §5 L283 | 2 min |

Then: `python make_bibliography.py && python substitute.py && python build.py && pdflatex ×2`, and
re-check page count with pypdf. I ran exactly that sequence today; it exits 0 and yields 9 pages with
the Appendix first appearing on page 9.

---

## 2. The checklist, item by item

### CONTENT

| Item | Status | Evidence |
|---|---|---|
| Sections written | **PASS** | There are now **nine** numbered sections plus an unnumbered "Artifact availability" — §9 Conclusion was added 2026-08-02 so the paper does not end on its own limitations. §7 reports the falsified repair rather than hiding it. |
| Abstract | **FAIL** | Present and structurally complete, but contains a forbidden claim: "An honest agent is enough to break the statistic, and **it breaks it most where the intervention worked best**" (L18). It also carries the gemma3:12b null — "+11.44 pp conditional falling to +0.16 pp" — without its interval, which is (−13.92, +14.25) on n = 3 (§6 L356). |
| Title | **RESOLVED 2026-08-02** | The placeholder is gone: `grep -c "TITLE PLACEHOLDER"` returns **0** in both `manuscript.md` and `manuscript.tex`, and the real 13-word title renders on page 1 of `manuscript.pdf`. |
| References, every one independently verified | **PARTIAL** | **These counts are stale — three references were added on 3 August, and `make_bibliography.py --check` now reports "14 references, 14 cited in body."** `submission_gate.py`'s citations gate re-measures this every run and cross-checks it against the labels typeset in the built PDF; as of the last check `references.bib` holds 17 entries, 14 of them cited, body numbering [1]..[14] contiguous, and the 3 uncited entries are verified and deliberate. Every entry has a `note` naming the URL fetched and the date. Four items remain open and are recorded in `manuscript.md:457`: (a) three distinct 2026 arXiv papers are called PolicyGuard and the author has not confirmed which `[3]` means; (b) "for twenty-five years" (§1 L31) is supported by nothing cited — [8] is 2002 (24 yr), [6] and [7] are 2004, [5] is 2007; (c) [5] is metadata-verified but closed access, so its regimentation/enforcement wording is unconfirmed; (d) the post-treatment argument rests on one 2026 preprint, with Rosenbaum 1984 verified and sitting uncited in the `.bib`. |
| Appendix | **RESOLVED 2026-08-02** | The `[STUB]` appendix was deleted, not shrunk, per the freeze rule. Re-verified 2026-08-03: the string `[STUB]` does not appear anywhere in `manuscript.pdf`. Its one unique disclosure (no commit-level reproducibility claim is supported) now ships in the "Artifact availability" section. |

### FORMAT

| Item | Status | Evidence |
|---|---|---|
| Compiles under `[dblblindworkshop]{neurips_2026}` | **PASS** | `manuscript.tex:12`. The `final` variant appears only as a commented-out line at :9 with a warning. Both `pdflatex` passes exit 0; `grep -c "^!" manuscript.log` = 0. |
| Body ≤ 8 pages | **PASS (re-established 2026-08-03)** | This row's earlier evidence was VOID: it cited the appendix as the page-9 marker, and the appendix was deleted 2026-08-02, after which the body genuinely overran. **The verdict is right; the particulars written here were measured before the 3 August revisions and no longer hold.** They said page 9 began with the References heading and carried entries [1]–[11]; in fact the heading and entry [1] sit on page 8, page 9 starts with entry [2], and there are 14 entries, not 11. **Stop hand-measuring this row.** `submission_gate.py`'s pages gate finds the page the References heading is typeset on, confirms nothing but references follows it, cross-checks against `manuscript.aux`, and reports the remaining page slack in body lines — every run, on the built PDF. The 14-line overrun was repaid on 2026-08-03; see that day's entry for the itemised cuts. |
| Figures embedded correctly | **PASS (re-verified 2026-08-03)** | There are now FOUR figures, not three; all four `\includegraphics` resolve and render, and `build.py` reports "figures: 4 found, 4 with a caption paragraph attached". Figure 1's caption was rewritten 2026-08-03 (it had described an "upper bar / lower bars" two-tier layout the figure does not have) and Figure 1 is now cited in the body, in §2's worked-example paragraph. Figure 3's panel (b) band is now labelled as the per-seed min–max range rather than left under panel (a)'s "95% CI". |

### ANONYMITY

| Item | Status | Evidence |
|---|---|---|
| Own prior work in the third person | **PASS, by absence** | Neither predecessor is cited. `manuscript.md:455` records that no entry for either is in `references.bib`, and the one sentence that gestures at them — "the studies that produced this corpus did not report it either" (§4 L166) — names neither. The earlier lane's open item (re-check once the bibliography lands) is now closed: the bibliography landed and the rule has nothing to bite on. |
| No repo links | **PASS** | **This is now measured, not asserted.** `submission_gate.py`'s anonymity gate scans `manuscript.pdf` (text, every stream, and metadata), every figure PDF and PNG, and the three source files, against needles it derives at runtime from `build.py`'s camera-ready constants plus the machine account and repository path, plus regexes for any email address and any user path. It reports hits by label and location, never by value. There are **four** figure PDFs and **five** PNGs now, not three of each. |
| No acknowledgements | **PASS** | No acknowledgements or funding section exists in `manuscript.tex`. |
| No identifying paths in figures or their metadata | **PASS** | PDF metadata: `/Author` empty, `/Title` empty, `/Producer` MiKTeX, `/Creator` "LaTeX with hyperref". Figure PDFs carry only generic Matplotlib strings. `manuscript.docx` core properties: `author='python-docx'`, `last_modified_by=''`. |
| Residual fingerprint risk | **OPEN, author's call** | Not a checklist item and not grep-catchable. "78 farm agents over 42 years" + Lake Mead + the 895 ft floor (§2, §5) is the same testbed signature as the group's two predecessor studies. A reviewer who has seen either could trace this paper with zero citation or metadata leak. Deliberately not fixed — genericising it would remove content the reviewer needs. |

### HONESTY

| Item | Status | Evidence |
|---|---|---|
| Every number traceable to a script line | **PARTIAL** | **The two counts formerly quoted here (87 markers, 11/11 scripts) are stale and have been removed — both are printed by the commands themselves, and `submission_gate.py` runs both and reports them.** Three gaps remain, and they are the part of this row worth keeping: (i) the Table 1 body is hand-typed — the manuscript's own handoff note at L232 says so, and `build.py` has no markdown-table renderer, so no guard would catch a stale cell; (ii) §3's `67.87%` / `31.8%` are no longer printed by any live script — `fig1_rule_layers.py` now prints the 80.6% / 48.5% split instead, and I confirmed `67.87` appears nowhere in its output; (iii) five numbers rendered inside Figure 2 (`yr 4 -18.46 pp`, `yr 7 -6.41 pp`, the two significance tallies, `2.0 MAF`) reach the page with no caption and no `NUMBERS.md` row of their own. |
| Forbidden-claims list swept | **FAIL on one, PASS on eleven** | Swept all twelve. Clean: flood is disclaimed as a control in three places; "We report a regime separation and claim no dose-response" (§4 L188); §3 discounts its own headline to 59.4%; the first attempt is called unrecoverable in both §5 and §8; "endogeneity" is explicitly disclaimed as the differentiator (§1 L45); framework novelty is conceded away (§1 L40); "behavioural feasibility", "premise revision", "novel", "first to", "monotone" appear nowhere. **Violated:** monotone dose-response, twice — abstract L18 and §5 L285–287 ("breaks it by roughly the amount the intervention succeeded in moving the world. The metric is most misleading exactly when the intervention is most effective"). No cross-cell estimate in this corpus identifies that, and §4 disclaims it by name. **Borderline:** §8 L432 "a stronger model reports a changed world more accurately, which makes the composition term larger rather than smaller" is an untested directional claim about models the corpus does not contain, in the same sentence that concedes "no frontier models". |
| The falsified repair reported rather than hidden | **PASS** | §7 opens "The obvious repair does not work, and we tested it", gives four world-conditioned antecedents that shift by +64.29, +55.71, +55.71 and +25.71 pp against the self-report's +45.73, and states the reason. The abstract carries it too: "Moving the antecedent to world state is tested here and fails." This is the best-executed thing in the paper. |

### OUTPUT

| Item | Status | Evidence |
|---|---|---|
| `manuscript.pdf` uploadable to OpenReview | **PASS** | Compiles clean, anonymous, correct style option. **The two content blockers named in this row are gone**: the title was written 2026-08-02 and the `[STUB]` appendix was deleted the same day (this file already records both, four rows up — the row you are reading contradicted itself). `submission_gate.py` re-checks the build, the anonymity sweep and the page limit on the built PDF every run. |
| `manuscript.docx` for the author | **PASS** | 955 KB, 101 paragraphs, regenerated by `build.py` in today's run, metadata clean. |
| One command that regenerates every number and figure | **PARTIAL** | `python SUBMISSION_2026/TAE/evidence/run_all.py` regenerates every figure, CSV and evidence artefact from the raw run directories; it prints its own pass count, which is no longer duplicated here. It does **not** rebuild the paper — that is a separate four-command chain — and it does not touch the hand-typed Table 1 body. Two commands, not one, and one table outside both. |
| Version control | **RISK, not on the checklist** | `git check-ignore` confirms `SUBMISSION_2026/` is ignored wholesale. The entire submission bundle — manuscript, evidence scripts, `NUMBERS.md` — is untracked. There is no recovery from an overwrite and no commit hash to bind a number to. |

---

## 3. What the reviewer simulation said

The simulation returned two verdicts, and I think both are right.

**Workshop: accept, 6/10.** On-theme almost to the letter, honest about its confounds, page budget met.
**Main track: reject, 4/10.** Soundness 2, Presentation 2, Contribution 2, Confidence 4.

The strengths it named are real and worth protecting through the edits: the novelty concession is made
in paragraph three and unhedged ("Enforcing over model-authored state is not new and we do not claim
it"); the distinction between a treatment-affected *world* predicate and a treatment-authored
*self-report* predicate is sharper than anything in the cited literature; §3 earns its own distinction
empirically and then discounts it; and the executed-action reading that moves the flagship null to
+27.82 pp is disclosed by the authors rather than found by the reviewer.

### The weakest link

**§5's stratification adjusts on a variable that §7 declares treatment-affected, and the two sections
never meet.** §5: the world state "is written by the simulator, independently of the generation being
governed, so it can be held fixed after the fact". §7: "In a coupled system the world is downstream of
the treatment as well." Independent of the *generation* is not independent of the *treatment*, and it
is the second that direct standardisation needs. The shortage tier is downstream of exactly the
withdrawals the validators changed — §5 says so itself: "What made the worlds differ is the
reservoir." So §5 performs, on its own argument, the post-treatment adjustment §1 diagnoses in others
via Gao et al. Every headline in the abstract flows through that step.

Compounding it: the two arms' supports are close to disjoint (64.8% of governed decisions in tier 0,
76.7% of no-validator decisions in tier 3), Table 2 reports no per-stratum *n*, no weighting scheme,
no effective sample size, and no interval on any residual — while the raw gap it nullifies carries
one, (+40.24, +51.21).

**Does the paper acknowledge it? Partially, and in the wrong place.** §8 names the missing experiment
("The other runs enforcement on with the environment pinned to the untreated trajectory. Neither
exists here") but frames it as completing the picture rather than as the thing that would make §5
identifying. Nowhere does the paper say: this adjustment has the same post-treatment character we
diagnose in others, and here is why it is nonetheless informative. One paragraph in §5 would close
the gap, and would cost the paper nothing it is currently claiming.

**A second weak link is entirely unacknowledged.** The never-retried stratum is used to bound the
paper's largest conceded limitation — "Selection on acceptance is not what produces the effect" (§5),
"The never-retried stratum bounds it" (§8). But in the governed arm "never spoke to" *means* "was not
rejected", and 59.4% of governed rejections are appraisal-conditioned, so that stratum is
definitionally depleted of decisions whose appraisal sat inside the rule. In the no-validator arm the
filter is the water-right precondition, which attaches to the two increase skills — selection on
*action*, not on appraisal. The two arms are filtered on different variables, one of which is the
outcome. A widened gap is the expected consequence of that filter, not evidence against it. The paper
names the imbalance ("36.2% of governed decisions against 64.6% of no-validator ones") and files it as
a caveat rather than as a rival explanation.

### W1 — the one finding I could settle, and the news is good

The reviewer's fatal-to-the-claim finding was that the paper measures one conjunct of a two-conjunct
antecedent and calls it the antecedent. I verified this against the rule as implemented and then
computed the correction.

The rule is `high_threat_high_cope_no_increase` in
`examples/irrigation_abm/config/agent_types.yaml:354`, and its conditions are
`WSA_LABEL ∈ {H, VH}` **and** `ACA_LABEL ∈ {H, VH}`. The manuscript states this correctly at §2 L66.
But the evidence layer's `HIGH` is `wsa_label` alone (`evidence/_data.py:59, 128`), `coping` appears
three times in the manuscript and zero times in `NUMBERS.md`, and Table 1's caption calls the scarcity
marginal "the rule's antecedent". So the reviewer is right on the specification.

The coping label is in the shipped corpus as `aca_label`. Recomputing over the anchor cell, all five
seeds, both arms, 16,380 decisions per arm:

| | with validators | without | Δ |
|---|---:|---:|---:|
| scarcity HIGH (what the paper reports as the antecedent) | 37.08% | 82.80% | **+45.73 pp** |
| coping HIGH (never reported) | 70.66% | 83.06% | +12.40 pp |
| **the actual conjunction** | **25.46%** | **68.61%** | **+43.15 pp** |

Two things follow. The scarcity row reproduces the paper's Table 1 to the second decimal, which
confirms beyond doubt that the published statistic is the marginal. And the conjunction moves +43.15
pp against the reported +45.73 pp — the claim survives the correction almost untouched. Runs are
equal-sized (3,276 decisions per seed) so the pooled rate equals the mean of per-seed rates on the
paper's own basis; I did not compute a paired CI for the conjunction, and one should be added by
`e4_world_fixed_decomposition.py` rather than by hand.

So W1 is a specification error, not a result-threatening one. The cheapest honest repair is to report
the conjunction, add the coping marginal in both arms — which is exactly the reporting discipline §7
demands of everyone else — and keep the scarcity marginal as the published-statistic comparison.

One further wrinkle the author should know: a second appraisal-conditioned rule exists in the same
config, `low_threat_no_increase`, firing on `WSA_LABEL = VL`. Its antecedent is disjoint from HIGH.
So even the corrected conjunction is not "the antecedent" of the governed rejections as a class —
which is another reason §3's careful "59.4% name at least one rule whose antecedent is the reported
appraisal" is the right sentence and the Table 1 caption's "the rule's antecedent" is the wrong one.

### Where I part company with the reviewer

The reviewer scored Presentation 2 partly on the missing bibliography. That is now fixed: ten verified
entries, twelve in-text markers, a generator with guards. The score should move.

---

## 4. Open decisions for the author

Nothing below was decided for you. Each needs a judgement no lane could make.

1. **The title.** Nobody wrote it. It is the single highest-leverage sentence in the submission and it
   is empty.
2. **Which PolicyGuard `[3]` is.** Three distinct June-2026 arXiv papers carry the name (2606.29225
   Kang/Yu/Hwang; 2606.32004 Malik/Singh/Azad; 2606.12896 Guo/Huang). 2606.29225 was selected as the
   only runtime policy-adherence verifier for LLM agents among them, and no TAE document records the
   intended one. A reviewer finds this in one search.
3. **"For twenty-five years."** Supported by nothing now cited. Either reword to "for more than two
   decades" (carried by [8], 2002) or verify Jones & Sergot 1993 and cite it — that source could not
   be retrieved and is deliberately absent from the `.bib`.
4. **W1: report the conjunction, or restate the claim as being about a marginal.** Both are honest.
   The numbers for the first are in §3 above.
5. **The testbed fingerprint.** Lake Mead + 78 agents + 42 years + four-action PMT is traceable to the
   predecessors even with a clean anonymity sweep. Genericise or accept.
6. **Whether the Appendix ships at all**, and if the freeze rule fails, whether the two flood
   provenance defects `NUMBERS.md` §8 requires in §8 — manifest seeds disagreeing across arms in 6 of
   9 flood models, and `gemma3_4b/Group_C/Run_1` running a different prompt from its four siblings —
   move into §8 prose. Right now they live only in the Appendix's conditional content and would ship
   nowhere.
7. **Whether to add the §5 paragraph conceding the post-treatment character of the stratification.**
   It costs about 60 words and roughly one reviewer objection. It also invites the objection into the
   paper, which is a real cost at a workshop and a clear gain at a main track.
8. **Whether to cite Rosenbaum 1984**, verified and sitting uncited in the `.bib`. One bracket in §4
   or §5.

---

## 5. Remaining risks at submission

| # | Risk | Likelihood a reviewer hits it | Mitigation |
|---|---|---|---|
| R1 | Title placeholder ships | Certain | Write it. Nothing else on this list is as cheap. |
| R2 | **Figure 2 caption describes a different figure.** Caption promises (a) the stratification ladder, (b) tier occupancy 64.8/76.7, (c) per-year gap "on the right axis". The figure's actual panels, confirmed from `fig2_mechanism.py:528, 574, 636`, are A "Null at year 1; the shift is not monotone afterwards", B "because the intervention changed the world" (Lake Mead levels, stacked, not a right axis), C "and LARGER where no validator ever spoke (5 of 5)". Caption (a) and (b) are plotted nowhere in the figure; printed panel C, which carries a load-bearing claim, is described nowhere in the caption. `NUMBERS.md`'s own panel labels agree with the script and contradict the manuscript. | Certain, within 30 seconds | Rewrite the caption to the figure. The stratification ladder is already Table 2; it does not need a panel. |
| R3 | Dose-response claim survives the sweep and contradicts §4 | High — §4 disclaims it by name two pages earlier | Delete both sentences. Replace with: the distortion in the anchor cell is the same size as the appraisal shift enforcement induced, and whether it scales with effectiveness is not identified here. |
| R4 | W1 antecedent mis-specification | High at main track, moderate at workshop | Fix with the numbers in §3 above. |
| R5 | Wrong denominator: "70.5% of **all** year-1 decisions ran to the end of the retry budget" (§5 L294). `fig2_mechanism.py:378-387` computes it over the governed arm only, and the no-validator arm has no retry loop. The wrong phrasing is also baked into the figure image ("71% of ALL year-1 decisions") and `NUMBERS.md` §4 offers a third, also-wrong wording. | Moderate | Fix all three together. |
| R6 | "Excluded from every paired contrast" (Table 1 caption, §6, Figure 3 caption) versus "5 of 5 irrigation cells" (§5, §8) and "20 paired seeds" (§5) — 5+3+5+5+2 = 20 only if ministral3:8b is in | Moderate | Either qualify the exclusion or say 4 of 4. Figure 2's panel C draws a ministral bar, so the figure must move with the prose. |
| R7 | Two values for the same-sounding quantity: 28.1–62.6% (§3, pooled) and 28.09–62.19% (§4, mean of per-seed rates). `NUMBERS.md` §8 warns they are different bases; the manuscript prints both a page apart with identical wording | Moderate — reads as an arithmetic error | Label the basis on one or both. |
| R8 | No in-text callout for Figure 1 or Figure 2 anywhere in the body | Moderate | Add panel-level callouts where each number lands. |
| R9 | §3's 67.87% / 31.8% are correct but no live script prints them; `fig1_rule_layers.py` prints 80.6% / 48.5% instead, which is also the split the figure plots and the stronger evidence for the sentence's own claim | Low for a reviewer, high for the next edit | Use 80.6 / 48.5 and drop the aggregate. |
| R10 | The abstract's flagship null rests on n = 3 with a 95% CI of (−13.92, +14.25) and flips to +27.82 pp (p = 0.004) under the executed-action reading — disclosed in §6, not in the abstract | Moderate at main track | Carry the interval into the abstract or demote the claim to the body. |
| R11 | ~~`[STUB]` renders on page 9 of the PDF~~ **CLOSED 2026-08-02** | — | The Appendix was deleted, not shrunk. `[STUB]` appears nowhere in `manuscript.pdf`. |
| R12 | Figure 2 prints "yr 4 −18.46 pp (p = 0.004), yr 7 −6.41 pp (p = 0.001)" — significant reversals running against the composition account — and the body never mentions them | Moderate, and it converts a sympathetic reviewer into a hostile one | Two sentences in §5. The account survives; burying it does not. |
| R13 | The whole bundle is gitignored and untracked | Certain but invisible to reviewers | Tag or archive a copy before the freeze. There is currently no way to prove which code state produced a number. |

---

## 6. What is still missing for the 2027 summer internship application

The paper is one artefact and, at workshop scale, a modest one: non-archival, 8 pages, one domain, one
governance stack. Treat it as evidence of *taste* — the willingness to publish a falsified repair and
to discount your own headline by 40% — rather than as a headline result. Here is what an AI-lab
research-internship packet needs that this repo does not yet contain.

**1. An archival first-author paper in a venue a CS committee recognises.** The Nature Water
manuscript is paused and, more importantly, is illegible to an AI-lab screener: it will be read as
domain science, not as agent evaluation. This TAE workshop paper is non-archival by design. Nothing in
the current portfolio is a NeurIPS/ICLR/ICML/ACL archival entry. The realistic 2027 path is to take
this exact result to a main track after the fixes in §5 plus the two experiments below — that is a
2026-12 to 2027-02 submission, which lands before or during the application window.

**2. The two missing arms, which are also the two strongest additions to the paper.** §8 names them
already: (a) log the first-attempt appraisal before the retry loop rewrites it; (b) run enforcement on
with the environment pinned to the untreated trajectory. (b) converts §5 from a decomposition into an
identification and removes the paper's weakest link. Both are runs, not new machinery, and the repo
already has the retry-exhaustion policy hook and the isolated-config-root support committed in the
last two commits on main.

**3. A validation environment with a known ground-truth composition term.** Build a synthetic setting
where the split between behaviour and composition is known by construction, show the naive conditional
statistic fails there and the reported diagnostic recovers the truth. This is what turns "an
interesting finding about our simulator" into a measurement method, and it is the single cheapest
thing that moves the main-track contribution score.

**4. Evidence that the failure mode occurs outside your own stack.** Right now the support is that a
self-report-conditioned rule "is well formed in [AgentSpec] today" — grammar, not practice. Exhibit
one or two real self-report-conditioned rules from published guardrail rule sets, and generalise the
condition in one paragraph: the norm's antecedent is written by the generation under judgement, which
also covers LLM-judge rubrics, self-consistency filters, refusal-rate metrics conditioned on
model-declared intent, and constitutional-AI critiques. That paragraph costs nothing and is the
largest available reach in the paper.

**5. One result on a non-simulation agent testbed.** A NeurIPS reader will ask whether a finding from
an LLM role-playing an irrigator transfers to code-repair, tool-use or web agents — the settings
AgentSpec and SAVeR actually govern. One coupled tool-use or code agent where an action alters the
state a later norm reads would answer it. This is also the item that makes the work legible to an
industry reviewer with no water background.

**6. A public, runnable artefact.** `run_all.py` is genuinely good — 11 scripts, 11 PASS, raw data to
figures, contamination guards, an independent re-derivation pass at the end. It is also inside a
gitignored directory in a private repo and cannot be shown to anyone. A small standalone public repo
with the evidence layer, synthetic or de-identified inputs, and that one command is worth more to a
screener than a second paper. Nothing about the current design blocks it.

**7. The framework itself is undersold.** WAGF is 3,100+ tests, five invariants with CI guards, a
seven-part DomainPack protocol, five domains, and a scaffolding CLI. That is systems engineering an
AI-lab hiring manager can evaluate directly, and it currently appears in no artefact aimed at one. A
short systems/tooling write-up, or an open-source release, converts three years of infrastructure into
a legible line item.

**8. Non-paper materials, none of which exist in this repo.** A one-page research statement that leads
with the evaluation claim rather than the water domain; a CV framed for an AI lab; a recommender who
can speak to AI research specifically rather than to hydrology; and, if the target is an
alignment/evaluation team, one small piece of public writing on the measurement problem this paper
identifies. The last is the cheapest and most differentiating — the argument in §1 of this manuscript
is already better prose than most blog posts on the subject.

**9. Timing.** 2027 summer applications open roughly 2026-09 to 2026-12. Items 1, 2 and 6 are the only
ones that plausibly complete in that window, and item 6 is the one fully under your control.
