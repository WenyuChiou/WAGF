# HANDOVER — everything about this submission, in one file

**This is the only file you need.** You do not need the conversation that produced it.

**Read the VENUE CHANGE section first.** Everything below it — every status line, every gate result,
every deadline, and the whole of the older "why this venue" reasoning — was written while this paper
was going to the TAE workshop. **It is not.** The work is sound; the destination moved.

---

# VENUE CHANGE — 2026-08-05, read before anything else

## The TAE route is closed, and it is not negotiable

The organisers confirmed by email on 2026-08-05, in reply to a direct question:

> "The workshop will be held in **Sydney only**. At the moment, we are **not planning to offer a
> virtual presentation option**."

And in their earlier reply, on 2026-08-04:

> "Please submit to the TAE workshop **only if you intend to attend and present** your work there,
> should it be accepted."

The author is committed to the **AGU Annual Meeting, 7–11 December 2026, San Francisco**, and their
advisor expects full attendance. The TAE workshop is **11 or 12 December in Sydney**. A flight
leaving San Francisco after AGU closes on the 11th crosses the date line and arrives on the 13th.
There is no satellite option, no virtual option, no co-author to present — the paper is single-author.

**So TAE is out.** Not deferred, not pending. Do not prepare anything further against TAE's
requirements.

## What the organisers DID grant, in writing, and it matters

From the 2026-08-04 reply:

> "It is **perfectly acceptable** to submit work that you intend to further develop into a full paper
> for a future main conference submission."

The main-conference route is explicitly cleared. Nothing about the work done for TAE is wasted.

## Where it is going — decision in progress

**Leading candidate: ICLR 2027 main track.** Verified from `iclr.cc` on 2026-08-05:

| | |
|---|---|
| deadline | **25 September 2026, AoE** |
| decision | **16 December 2026** |
| conference | 26–30 April 2027, California |
| length | **9 pages** excluding references, 10 at rebuttal, **unlimited appendix** |
| review | double-blind |
| arXiv | explicitly permitted, including during review |

**This is not yet confirmed.** A venue assessment was commissioned on 2026-08-05 and its conclusion
is not recorded in this repository yet. **Whoever confirms the destination must write it into
`DECISION.md`**, because until then no file in this project records where the paper is going.

Also on the table, both with decisions early enough to matter: an **AAAI-27 workshop** (AAAI-27 runs
16–23 February 2027 in Montréal; workshop dates were not published at the time of writing — the
AAAI-25 pattern was submissions late November, notification early December), and an **arXiv preprint
now**, which every venue under consideration permits and which is the only thing that can be visible
before the autumn.

## What this invalidates — do not trust these until they are re-pointed

The paper is in good shape. These are all venue-specific and now check the wrong thing.

| what | current state | why it is now wrong |
|---|---|---|
| `paper/submission_gate.py`, `venue` gate | reports **PASS** | It validates the **TAE** CFP contract and title option. **A passing check that validates the wrong specification** — the exact defect this paper is about. |
| `paper/submission_gate.py`, `pages` gate | enforces **8 pages** | ICLR allows **9**, plus an unlimited appendix. The paper is currently squeezed to a limit that no longer applies. |
| `paper/build.py` | emits `neurips_2026.sty` with TAE's blind option | ICLR requires its own style file. |
| `manuscript_state.json` | `READY_TO_SUBMIT` | True of TAE. Not yet true of anything else. |
| every deadline in `PLAN.md`, `STATUS.md`, `SUBMISSION_READINESS.md` | 29 August | The live deadline is **25 September**, if ICLR is confirmed. |
| `HANDOVER.md` section 2, "Why this venue, and why now" | argues for TAE on timing | Superseded. Its reasoning was sound and the premise changed. |

## The checklist

Ordered. Nothing below the line marked BLOCKED should start before the item above it is settled.

### A — must happen regardless of destination

| # | item | owner | state |
|---|---|---|---|
| A1 | Record the venue change and its evidence in `DECISION.md` — the two organiser quotes, the AGU conflict, and the date-line arithmetic | agent | **open** |
| A2 | Confirm the destination and write it into `DECISION.md`. Until this is done, A3 onward have no target | **author** | **open** |
| A3 | Figure 1: close the retry loop. See `analysis/figure1_loop_defect_2026-08-05.md` and the independent audit `analysis/figure1_mechanism_audit_2026-08-05.md`, which reached the same conclusion from the figure alone before reading either the paper or the argument | agent | in progress |
| A4 | Decide whether to post an arXiv preprint now, and get the advisor's agreement — it is their group's work | **author** | **open** |

### B — BLOCKED until A2 confirms the destination

| # | item | note |
|---|---|---|
| B1 | Re-point the `venue` gate at the confirmed venue's requirements, or delete it rather than let it pass on the wrong contract | it currently reports PASS against TAE |
| B2 | Change the `pages` gate to the confirmed limit | 9 for ICLR |
| B3 | Swap the style file in `build.py` and rebuild | |
| B4 | Update every deadline in the tracking documents | |
| B5 | Move TAE-specific artefacts to `_archive/tae_2026/` — `CODEX_REVIEW.md`, `SUBMISSION_READINESS.md`, and this file's section 2 | keep them; they are the record |

### C — the expansion, if ICLR is confirmed

Seven weeks. The paper is written; this is strengthening, not drafting.

| # | item | note |
|---|---|---|
| C1 | Restore what the 8-page limit forced out | §1's roadmap paragraph, §2's worked-example walkthrough, §6's "different estimand" paragraph. These were cut for space and are the passages that carry a reader. |
| C2 | Build the appendix | the full stratification ladder, per-cell numbers, and the gemma4 replication that never entered the workshop version |
| C3 | Address the reviewer simulation's findings | recorded in the earlier review pass |
| C4 | gemma3:12b from 3 seeds to 5 | ~2 days GPU; it is the thinnest cell carrying a headline result |
| C5 | Decide what to say about the RED reproducibility audit | narrowly waived for a non-archival PDF-only workshop. **That waiver does not transfer to an archival venue.** This needs a real answer, not the same sentence. |

---

## OPERATIONAL — read before running any git command or launching any run

Added 2026-08-05. Two things changed underfoot today and neither is obvious from the file tree.

### 1. The git index has a stale lock, and two agents are working in this repository

`.git/index.lock` exists and is **60 hours old** (created ~2026-08-03 03:00, almost certainly a git
command killed mid-operation during the survey-data purge work). No git operation runs for 2.5 days,
so it is stale — **but five `git.exe` processes are live right now**, which means anything either
agent has tried to stage or commit in the last 2.5 days has been failing.

**If your git commands are failing with `Unable to create '.git/index.lock': File exists`, that is
why, and it is not your fault.**

**The rule, until one agent has the repository to itself:** do not remove the lock unilaterally.
Two agents writing one git index is how a staging area gets silently clobbered — and this project
already has one incident of that class on record (the ministral seed-44 run was produced on a
different broker commit and silently rewrote a string in `failed_rules`, falsifying a §3 claim until
a figure's own gate caught it). Say in your report that you are blocked on the lock, and let the
author sequence the two agents.

### 2. `SUBMISSION_2026/` and `ICLR2027/` are now tracked by git

They were ignored wholesale while the repository was PUBLIC. It went PRIVATE on 2026-08-04 and stays
private until GitHub confirm the server-side GC for the survey-data purge, so the source of two paper
submissions is now under version control instead of living unversioned on one disk.

`.gitignore` was updated with targeted exclusions rather than a blanket rule. Still ignored:
`**/runs/`, `**/__pycache__/`, `ICLR2027/experiments/_smoke_*/`, and the three ~3.5 MB rejected
image-generation candidate PDFs under `_archive/**/candidates/` — the README beside them carries the
reasoning, which is the part worth versioning.

That leaves **163 files, 17.5 MB** to be committed once the lock clears. A PII scan was run over both
directories before staging: three apparent coordinate pairs were checked against their CSV headers
and are false positives — adjacent statistic columns (`pct_high_governed,pct_high_ungoverned`,
`rate_ung,diff_pp`, `comp_sym_pp,behv_sym_pp`), not locations.

**If the repository is ever made public again, revisit that `.gitignore` block BEFORE flipping
visibility.**

---

## THE EXPERIMENTS — planned, verified, and ready to launch

Full plan and costings: `analysis/experiment_plan_2026-08-05.md`. Summary of state:

## CODEX FOLLOW-UP TO CLAUDE -- decision requested, 2026-08-05

I read the updated handover and verified `evidence/e7_appraisal_drift.py --self-test`: **PASS**.
The E7 analysis is the right measurement for the first-attempt question, but the run decision needs
to be explicit before any GPU work starts. This section records Codex's current interpretation and
asks Claude/the next agent to settle the remaining choice.

### The control we mean

For E1, the treatment is an instrumented **strict/governed** arm. The control is an instrumented
**no-validator** arm: the same model, prompt, 78 real agents, 42-year horizon, seed set, memory
settings, and audit columns, but with governance disabled and no custom irrigation validators.
Both arms may retry for non-governance reasons; the control is not a zero-retry null condition.
The comparison asks whether appraisal revision differs between the two configurations. It does not
identify a causal effect of a validation message by itself.

`run_experiment.py --governance-mode disabled` is **not** sufficient for this control, because that
runner still attaches the custom irrigation validators. `run_ungoverned_experiment.py` does disable
both YAML governance and custom validators, but it currently hard-codes the default config directory
and does not expose `--config-dir`; therefore it cannot yet produce a provenance-matched,
first-attempt-instrumented control without a small runner/config change. Do not launch a command that
silently produces an uninstrumented control.

### Codex's proposed ICLR-safe choice

If the goal is to strengthen the active ICLR manuscript, the minimum useful experiment is one paired
E1 matrix on irrigation:

```
gemma3:4b x {strict, no-validator} x seeds {42,43,44,45,46}
```

with `initial_proposal_columns: true` in both arms, separate output roots, and E7 analysis frozen
before the runs. ADVISE, new models, and additional seeds should wait until E1 has answered whether
the governed arm rewrites the appraisal more, equally, or less. Flood can be run separately for
Nature Water reuse, but it should not be mixed into the ICLR identification claim: this handover
itself says flood lacks the action-to-environment feedback that carries the irrigation mechanism.

### Decision requested from Claude/the next agent

Please resolve these points in `DECISION.md` or in a dated follow-up below this section:

1. Is the formal target still the TAE historical package, or is this experiment being adopted for the
   active ICLR package? The current ICLR handoff still says that no formal new experiment has run.
2. Is the launch order intentionally **flood first, then irrigation**, or should the ICLR-critical
   irrigation matrix take priority over the Nature Water add-on?
3. Is the two-arm E1 matrix approved, or does the older `RUN_DECISION.md` instruction remain in force:
   governed-only first, with the no-validator arm conditional on the five governed seeds passing?
4. Who will make the small no-validator runner/config change needed to preserve
   `initial_proposal_columns: true` without modifying the frozen corpus or silently weakening the
   provenance gate?

This is a decision request, not authorization to launch. No paper claim should be broadened and no
formal result should be written until the target venue, arm matrix, runner path, and stop rule are
settled.

**The apparatus already exists.** Seven commits sit unpushed on `p0-1-governance-instrumentation`.
`0c6aa60e` adds first-attempt proposal columns (opt-in, default-OFF) and `c701d01a` adds an ADVISE
disposition. This is not "build then run"; it is "turn the flag on and run".

**The smoke test passed on 2026-08-05.** An isolated config copy at
`ICLR2027/experiments/config_firstattempt/` with `global_config.audit.initial_proposal_columns: true`
was run at 5 agents × 3 years on `gemma3:1b`. All three columns appeared and are populated in the
expected format:

```
initial_labels = 'WSA_LABEL=M|ACA_LABEL=M'
retry_count    = 2
construct_WSA_LABEL = 'M'
```

The frozen config in `examples/irrigation_abm/config/` was **not touched** — `git status` on it is
clean. `--config-dir` (from `10e190cf`) is what makes that true, and every new arm must use it.

**The analysis is written and tested before the data exists.**
`evidence/e7_appraisal_drift.py` reads the new columns and reports, per arm and seed, how often a
retried decision's appraisal ended up different from the one the agent first wrote — and, separately,
how many decisions **entered** or **left** the HIGH set that the conformance rate divides by. That
directional count is the paper's claim expressed as a number.

Run `python SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py --self-test`. It passes four checks,
three of which are mutation tests proving the checker can fail:

- a flag-OFF run is **refused**, not scored as 0% drift — those two states are numerically identical
  and confusing them is exactly the failure this paper is about;
- a zero-retry corpus is refused, because both arms retry (62.0% governed / 39.1% no-validator,
  measured) so a zero means the run is not what it claims;
- planted drift is detected and counted in the right direction.

**What it must not assume.** Three outcomes are possible and all are reportable: the governed arm
rewrites more (§5's mechanism confirmed and no longer inferred), both rewrite equally (§5's
world-composition account is doing all the work), or the governed arm rewrites less (the framing is
wrong). Whoever runs this must not write the conclusion before the data.

**Order.** Flood first — 12 GPU-hours, and it doubles as a check on the Nature Water paper, whose IBR
is `R1+R3+R4` with every component conditioned on `TP`, the agent's own reported threat perception.
That is the same structure this paper criticises, and nobody has checked whether it survives. Then
irrigation (110 h), because Figure 1, §5's framing and §8's wording all depend on its answer.

### What seven weeks cannot do

A second governance stack. A second measurement domain. Frontier models. These are the limitations
§8 discloses, they will be pressed at a main track, and no amount of scheduling changes that. Anyone
planning the expansion should say so out loud rather than discover it in week six.

---

# CURRENT HANDOFF — Codex completion, 2026-08-05

**Read this section first.** It supersedes the dated status and task instructions below where
they conflict. The original sections remain as project history and rationale; they are not a
request to restart the review or to undo the completed revision.

## Current result

The WAGF manuscript has been revised into a plain-language CS/AI-agent workshop submission
candidate for TAE. The introduction now leads with why the metric can fail, gives the irrigation
example early, defines technical terms at first use, and makes the section-to-figure logic
explicit. The paper still makes only descriptive claims and retains its causal, provenance,
coverage, and testbed limitations.

## Files to trust

- **Master manuscript:** `paper/manuscript.md`
- **Submission PDF:** `paper/manuscript.pdf`
- **Generated companion:** `paper/manuscript.docx`
- **Readability and four-perspective review:** `analysis/readability_review_2026-08-05.md`
- **Release hashes and gate record:** `analysis/release_manifest_2026-08-05.json`
- **Current project state and issue ledger:** `manuscript_state.json`
- **Recoverable pre-revision snapshot:** `_archive/readability_revision_2026-08-05/`

`manuscript.md` is the only editable manuscript source. The `.tex`, `.docx`, and `.pdf` are
generated artifacts and must not be hand-edited.

## What Codex completed

1. Reworked the abstract and Introduction into a why → example → method → evidence → reporting
   recommendation chain.
2. Defined LLM, validator, conformance rate, agent-reported condition, world state, full
   conjunction, marginal proxy, and estimand in reader-facing prose.
3. Rewrote Sections 2–9 and the figure/table captions for shorter sentences, explicit
   denominators, standalone captions, and narrower noncausal claims.
4. Preserved the evidence boundary: all 98 `CLAIM` markers remain sourced and used; the four
   figure markers, table blocks, bibliography, numerical values, and stated limitations were
   retained. No new experiment, model, result, or literature claim was added.
5. Added the review memo listed above, including the argument map, terminology audit, citation
   map, four reviewer lenses, readability diagnostics, and remaining risks.
6. Repaired the release metadata so the manifest and state file match the current source/PDF
   SHA-256 hashes. The state audit now reports zero blockers and zero findings.

## Measured release status

The latest gate rebuilt the artifacts from the master source and reported:

```text
evidence    PASS   15 scripts, 15 PASS
figures     PASS   4 referenced, 4 on disk, current
build       PASS   0 LaTeX errors, 0 overfull boxes
venue       PASS   TAE workshop option/title and CFP contract
pages       PASS   9 pages; body ends p8; References from p9
fonts       PASS   8 Type 1 + 3 embedded TrueType; 0 Type 3
anonymity   PASS
citations   PASS   17 entries, 14 cited, body uses [1]..[14]
VERDICT     READY  all 8 gates passed
```

The corpus inventory separately confirms 42 irrigation run directories and 90 flood run
directories; every listed cell is complete, paired, and balanced. The generated DOCX audit also
reports 0 tracked changes, 0 comments, 0 placeholders, and 0 field instructions.

The strict prose-pattern tool still reports 21 diagnostic findings. They are repeated technical
definitions/caption phrases, bibliography repetition, and its known inability to inspect the
PDF; the text-consistency tool reports only the same unsupported-PDF limitation. These are not
new manuscript contradictions and are documented in the review memo.

## Figure handoff

The current Figure 1 is `figures/fig0_problem_schematic.pdf` (and its PNG preview): a reviewed,
flat-icon conceptual schematic showing one answer record, the validator gate, the measurement
lens, the shared agent-reported condition, and the retry path. It is not a data figure and does
not supply quantitative values. Figures 2–4 remain deterministic evidence figures generated by
the evidence pipeline.

The older Figure 1 discussion below says that the figure is TikZ-generated from data. That is
historical and is superseded by the current `manuscript_state.json`, release manifest, and review
memo: the shipped Figure 1 is the reviewed image-generated flat-icon concept figure. Do not
image-generate or redraw the three quantitative figures. If Figure 1 is changed, inspect the
standalone file and the PDF at print size and rerun the full gate.

## Limitations that must not be weakened

- The reproducibility audit remains **RED**: 27 enriched manifests are dirty and 15 identifying
  runs are minimal. Current tables and figures regenerate, but clean source-run reproduction is
  not available for every historic run. This is disclosed and narrowly waived for the PDF-only,
  non-archival TAE submission; do not call the work bitwise reproducible.
- Recorded-world reweighting is descriptive, not a causal adjustment; world state is downstream
  of enforcement.
- The paper does not claim that agents deceive or game the rule, that the unconditional rate is
  the true/corrected effect, or that the pattern applies to every model or governance stack.
- First attempts and untreated trajectories are not fully available; fine strata lose coverage;
  rule regime is confounded with testbed; and the strongest decomposition is scoped to the anchor
  irrigation cell.

## Instructions for the next agent

1. Treat the latest artifacts and the three commands in Section 8 as authoritative; do not trust
   stale prose summaries or the old 2026-08-04 gate block below.
2. If further manuscript work is requested, edit only `paper/manuscript.md`, regenerate all
   artifacts, and update the release hashes/state only after the gate passes.
3. Keep citations as individual `[n]` tokens because the local gate checks the contiguous numeric
   sequence directly.
4. The highest-value optional future additions are first-attempt logging, an untreated-trajectory
   or frozen-world branch, and repair of the dirty/minimal manifests. None is required for the
   current PDF-only workshop gate.
5. The original venue follow-up remains open: the CFP does not state a dual-submission policy. If
   a concurrent main-track version is considered, obtain organizer or venue-policy confirmation
   before relying on the absence of a rule as permission.

**Handoff conclusion:** the current PDF is ready for submission, subject to the author's final
venue decision and human sign-off. Any future agent should improve the artifact only in response
to a new user decision or reviewer feedback, not by restarting the completed readability pass.

---

# 0. YOUR TASKS

You are analysing a paper that is 25 days from its deadline and is already building clean. **This is an
analysis job, not a rewrite job.** Read everything, change almost nothing, and report.

## What you may and may not change

**You MAY edit** — only these, and only where a defect is unambiguous and factual:
- a typo, a broken cross-reference, a number that contradicts `NUMBERS.md`, a caption that describes
  something the figure does not show.

**You MUST NOT change** — no exceptions:
- anything that alters **what the paper claims**. Narrowing an over-broad claim is not "adding" and is
  allowed; adding a claim, strengthening one, or removing a caveat is not.
- any **disclosure, limitation, confidence interval, coverage figure, or seed count**. If something
  only fits by cutting one of those, it does not fit — say so instead.
- any file outside `SUBMISSION_2026/TAE/`. `examples/` is the frozen run corpus, `broker/` is the
  framework, `paper/nature_water/` is a separate paused manuscript. All three are read-only to you.
- the three build guards. `substitute.py` fails on an unmatched **or unused** `{{CLAIM:...}}` marker,
  `build.py` raises on unmapped non-ASCII, `pdflatex` must exit 0. Never weaken one to make something
  pass.
- `manuscript.tex` or `manuscript.docx`. Both are generated. `manuscript.md` is the master.

**Where to put your output:** write everything to `SUBMISSION_2026/TAE/CODEX_REVIEW.md`, one section
per task below. Do not scatter findings across other files.

## Task 1 — Review it as a TAE reviewer would

Read `paper/manuscript.pdf` the way a reviewer actually reads: once, at speed, possibly outside your
exact specialty. Then write the review you would submit.

- **Summary** — what the paper claims, in your own words. If you cannot state it crisply after one
  read, that is the finding.
- **The single strongest reason to accept.** Concrete.
- **The single strongest reason to reject.** Concrete, and be the reviewer trying to reduce their
  load — what is the sentence someone would quote in the box that sinks it?
- **Every place you were confused, in reading order**, with the line quoted. Confusion is rejection.
- **Where you would push back on the claim.** Is the evidence sufficient for what is asserted? Is
  anything over-claimed? Does §8 give away more than it needs to, or less than it should?
- **The questions you would put to the authors.**

A prior review pass returned **weak reject**. Its two blocking findings have since been fixed — the
abstract no longer reads as contradicting itself, and the gemma3:12b result is no longer stated as
stronger than its interval supports. **Do not assume those were the only ones.**

Propose no new experiments. The data is frozen and there is no time.

## Task 2 — Analyse the figures

Four figures. Read §6 below first, and read `_archive/cleanup_2026-08-05/figure-history/_rejected_imagegen/README.md`, before you form a
view. **Figure 1 has been rejected five times**, three of those image-generation attempts that each
got the text right and the structure wrong while reporting their own checks as passing.

For each of the four:

1. **The one-second test.** What does a reader see first, and is it the thing the figure exists to
   say? Quote the caption's claim and say whether the picture delivers it before any number is read.
2. **Does the figure agree with the text?** Read the passage that cites it and check every number,
   direction and label against the figure and its CSV. Report any disagreement.
3. **Can a non-specialist read every label?** The author — who wrote this research — could not read
   the previous labels, so they were all replaced on 2026-08-04. Judge whether the replacements
   landed, and name any word that still requires the reader to already know the answer.
4. **Legibility at print size.** Figures print at 4.40 in wide. Judge the smallest type at that size.
5. **Consistency across the four.** Same colour meaning the same thing, same size hierarchy, same
   convention for marking an exclusion.

Then: **rank the four, and for the worst one name the single change that would help most.**

**Figure 1 specifically.** Two designs exist, side by side in `_archive/cleanup_2026-08-05/figure-history/root-comparisons/FIG1_COMPARISON.png`:
`fig0_problem_schematic` (three regions, two of which share a yellow tint) and `_archive/cleanup_2026-08-05/figure-history/root-comparisons/fig0_variant_strip`
(one continuous yellow strip running through the whole figure). **Say which you would ship and why**,
in terms of what a reader understands faster. Whichever you choose, the change the author is
considering is adding the two concrete examples — `"increase water"` and `"scarcity is high"` — to the
strip version, which currently has none. Judge whether that helps or crowds.

**Do not image-generate anything.** The three data figures render statistics from 16,380 decisions per
arm; a generated picture of a chart would carry invented values. Figure 1 is drawn in TikZ from the
data with a guard that exits non-zero if the corpus contradicts it.

## Task 3 — Check the logic flow

Read `paper/manuscript.md` section by section and judge whether the argument actually carries.

- **Does each section do the job §3 of this file says it does?** That table is the intended chain.
  Where the paper departs from it, say so.
- **Does each section hand the next one what it needs?** §3 exists to isolate the appraisal-conditioned
  layer so §5 can reason about it; §4 establishes the movement so §5 can explain it; §5 explains it so
  §6 can price it. Test each seam.
- **Where does a reader most likely lose the thread?** Quote the exact spot.
- **Is anything load-bearing asserted without support, or supported without being asserted?** §3 is
  a full page of setup that the introduction does not list as a result — deliberately. Check that the
  reader is told why it is there.
- **Paragraph level**: does each section open by telling the reader what it is for? Does each
  paragraph hand off to the next?

## Task 4 — Say what has to come back to a human

Separate what you fixed from what you cannot decide. For each item you did **not** act on, give:
the finding, why it needs a human, and the two or three options with what each costs.

Anything that changes what the paper claims belongs here, not in your edits.

## When you are done

Run all three checkers and paste their real output into your report:

```
python SUBMISSION_2026/TAE/evidence/corpus_inventory.py     # expect exit 0
python SUBMISSION_2026/TAE/evidence/run_all.py              # expect 13/13
python SUBMISSION_2026/TAE/paper/submission_gate.py         # expect 6 of 7; fonts fails by design
```

If you changed anything, rebuild first (§9) and confirm the page count, that the body still ends by
page 8, and that no author name appears in the PDF metadata. **This is a double-blind submission: the
author's name in the PDF is an immediate desk reject.**

---

---

## 1. What this is, in five sentences

A paper for the **TAE workshop at NeurIPS 2026** — "Can We Trust AI Evaluation?".

Runtime governance layers for language-model agents are proliferating. They all work the same way: a
rule fires on a proposed action, the agent is told which rule it broke, and it tries again. The field
scores them with a **conformance rate** — violations under enforcement against violations without it.

**This paper shows that rate is least trustworthy on exactly the runs where the governance worked,
and that no deceptive agent is needed to make it so.**

The reason: some of these rules read a state the *agent itself reports* in the same generation being
judged. Enforcement then rewrites the distribution of the rule's own antecedent — so the rate's
denominator is written by the thing being governed.

## 2. Why this venue, and why now

Decided by the author 2026-08-03. Recorded in `DECISION.md`.

- **Timing decided it.** The goal is a 2027 summer internship; those applications are read in autumn
  2026. A workshop notification arrives in time to appear on the application. A main-track paper
  submitted in October is not decided until early 2027, after the applications are gone. An accepted
  workshop paper beats a submission under review.
- **It costs nothing.** TAE is non-archival, so the work is not spent and a fuller main-track version
  stays available.
- **The paper is workshop-strong, not yet main-track-strong.** The limitations in §8 — one governance
  stack, one simulator, all models at or under 27B open weights — are acceptable disclosures at a
  workshop and would be pressed hard at a main track. Closing them needs a second governance stack or
  a second measurement domain: months, not weeks.
- **Fit.** The workshop's question is whether AI evaluation can be trusted. This paper argues a
  governance metric can fail to measure what it claims. At a main track it would compete with method
  papers for attention.

**Hard facts.** Deadline **30 Aug 2026 07:59 US Eastern** = 29 Aug AoE (read off the OpenReview
submission form, which is more authoritative than the CFP prose). Submission opened 29 Jul. **8 pages
excluding references and appendices. Double-blind.** Submitted through OpenReview at
`NeurIPS.cc/2026/Workshop/TAE`. The author's OpenReview account exists and reaches the submission
button.

**One open item the author owns:** the CFP states accepted papers are non-archival but states **no
dual-submission policy at all**. Absence of a rule is not permission. The author emailed
`aiteval2026@gmail.com` on 2026-08-03 16:55 UTC asking whether a later main-track version is
permitted. No reply yet. If no reply by 2026-08-10, follow up to `hanxun@unimelb.edu.au` (Hanxun
Huang, first-listed organiser, the contact on the OpenReview venue page).

## 3. What the paper actually argues — the chain

Nine sections. Each hands something specific to the next.

| § | job | the move |
|---|---|---|
| 1 Introduction | frame | Guardrails all share one shape and are scored with a conformance number. What that number measures depends on what the rule reads. Rules that read *agent-reported* state have never been evaluated. **The distinguishing property is not endogeneity** — Gao et al. [9] have a treatment-affected conditioning variable too, but theirs is external to the generation, so they can branch from frozen common states. A self-reported predicate has only the generation being governed: freezing the appraisal destroys the thing being measured. |
| 2 Setup | the instrument | Same governed loop, two testbeds. The rule under study forbids an increase in demand when reported scarcity is high **and** reported coping is high — both halves written by the agent. A worked example ends the section and Figure 1 sits there. |
| 3 Which rules read what the agent says | **setup, not a result** | The stack holds two rule kinds. This section isolates the appraisal-conditioned part and proves it is separable and measurable, then **narrows every later claim to it** — only 59.4% of governed rejections are appraisal-conditioned. Without this section §5 does not stand. |
| 4 The conditioning variable moves | result 1 | The antecedent moves further than the rate it supports: **+45.73 pp against +23.02 pp** in the anchor cell. Without the larger number you cannot tell a lower violation rate from a smaller, differently-composed set. Explicitly refuses a dose-response claim. |
| 5 Why it moves | **the core** | The movement is **composition of world states**, not the agent gaming the rule. Hold the simulator-recorded world fixed and +45.73 collapses to **−2.53** at 100% coverage. Two of four intervals exclude zero, both *below* — the governed arm reports *more* scarcity for the same world, the opposite of premise revision. What made the worlds differ is the reservoir. **A perfectly honest agent breaks the statistic on its own.** Two corroborations from opposite directions: year 1 (identical worlds, maximum retry pressure, null shift) and the never-blocked stratum (no pressure at all, *larger* shift, 5 of 5 cells). |
| 6 What it does to the statistic | result 3 | Recomputed over a design-fixed denominator the effect shrinks in every cell. On gemma3:12b it **vanishes**. On ministral3:8b the two statistics **disagree in sign** (+2.80 conditional against −22.17 unconditional). A fixed denominator also admits an external reference the conditional rate cannot use: a uniform-random agent would ask for more on 40% of decisions; without validators the unconditional rate is far above that, with validators it cannot be distinguished from it. |
| 7 What to do instead | prescription | **The obvious repair fails and we tested it.** Conditioning on world state instead moves *more* (+64.29 pp against +45.73). The world is not written by the generation — which is what let §5 hold it fixed — but it is still downstream of the treatment. Three prescriptions survive, the first being: report the conditioning variable's prevalence in both arms beside every conformance rate. One extra number, almost never reported, **including by the studies that produced this corpus**. |
| 8 Limitations | — | Acceptance-selection and the unrecoverable first attempt; coverage falls as strata get finer; regime perfectly confounded with testbed; one run produced on a different broker commit. |
| 9 Conclusion | close | The point outlasts this testbed. |

## 4. The selling points, in the order a reviewer meets them

1. **The prescription is one extra number and costs nothing.** Print the conditioning variable's
   prevalence in both arms beside every conformance rate. It is almost never reported. Figure 1 makes
   the need legible in five seconds without statistics.
2. **The existence proof.** On gemma3:12b the whole apparent governance gain is composition. On
   ministral3:8b the two statistics disagree in sign. Existence proofs are cheap to state and
   expensive to dismiss.
3. **It needs no deceptive agent.** The mechanism is composition of world states, demonstrated by
   direct stratification, not inferred from indirect signs. That is stronger and stranger than "the
   agent games the rule".
4. **The falsified repair is reported, not hidden.** The obvious fix was tested and fails. This
   pre-empts the first thing a reviewer would propose.

## 5. What we have, empirically

**Everything below is regenerated from raw run directories by 13 scripts. `evidence/run_all.py` is
13/13 PASS. No number in the paper is hand-typed without a marker traced to a script line.**

### The corpus

| testbed | cells | arms | seeds | rows per run |
|---|---|---|---|---|
| irrigation | 5 models | with-validators / no-validator | 5, 5, 5, 3, 3 — **all balanced** | 3,276 (78 agents × 42 years) |
| flood | 9 models | same | 5 runs each | 1,000 |

Irrigation cells: `gemma3:4b` (the anchor, 5 seeds), `gemma3:12b` (3), `gemma4:e2b` (5),
`gemma4:e4b` (5), `ministral3:8b` (3). Flood adds `gemma3:27b`, `gemma4:26b`, `ministral3:3b`,
`ministral3:14b`. **Nine model configurations, fourteen model × testbed cells.**

`evidence/corpus_inventory.py` reports the truth off disk and exits 0. Run it rather than trusting
this table.

### The load-bearing numbers

| what | value |
|---|---|
| anchor: HIGH-appraisal prevalence, on vs off | 37.08% / 82.80% → **+45.73 pp** |
| anchor: the conformance rate it supports | 36.05% / 59.07% → **+23.02 pp** |
| world-fixed residual, shortage tier, 100% coverage | **−2.53 pp** |
| world-fixed residual, finest stratification, 43.4% coverage | +0.21 pp |
| reservoir final gap / mean over 42 years | +106.57 ft / +102.25 ft |
| gemma3:12b, conditional → unconditional | +11.44 → **+0.16** (95% CI −13.92, +14.25; p = 0.96) |
| ministral3:8b, conditional vs unconditional | **+2.80 vs −22.17** — opposite signs |
| the falsified repair: world antecedent shift | **+64.29 pp** against the self-report's +45.73 |

### Replication of the mechanism, recorded but NOT in the paper

The world-fixed decomposition was run on four cells. Coarse-rung residual against raw shift:

| cell | raw | coarse residual | verdict |
|---|---|---|---|
| gemma3:4b (anchor) | +45.73 | −2.53 | holds |
| gemma3:12b | +21.27 | −4.94 | holds |
| gemma4:e4b | +43.38 | −3.33 | holds |
| **gemma4:e2b** | +47.53 | **+5.18** | **fails the script's own gate at finer rungs (+13.52)** |

**This is in `NUMBERS.md` and deliberately not in the manuscript.** The author's standing instruction
is that nothing may be added that changes what the paper claims. §5's claim is scoped to the anchor
cell — the sentence reads "leaves *on this cell* a residual near zero at every resolution", narrowed
on 2026-08-03 precisely because the unscoped form is false for e2b.

## 6. The figures — and the part that keeps failing

Four figures. Three are data plots regenerated from the corpus; Figure 1 is a concept diagram.

| # | file | what it shows |
|---|---|---|
| 1 | `fig0_problem_schematic` | **Concept diagram, no numbers.** One output holds both the action and the self-reported appraisal; the rule reads the appraisal; blocked, the agent rewrites it; that same field is the score's denominator. |
| 2 | `fig1_rule_layers` | Why decisions were blocked, by arm and rule kind, and what the blocked decisions were trying to do. Proves the two arms' rejections have disjoint causes. |
| 3 | `fig2_mechanism` | (a) the per-year gap, with year 1 null and the reversals; (b) the reservoir, which is what made the worlds differ; (c) the gap is *bigger* where nothing was blocked. |
| 4 | `fig3_consequence` | The consequence: recomputed over a design-fixed denominator the effect shrinks, vanishes on one cell, reverses sign on another. |

### What has repeatedly gone wrong, and it is worth knowing before touching them

**Figure 1 has been rejected five times.** Three of those were image-generation attempts, archived
with a written post-mortem at `_archive/cleanup_2026-08-05/figure-history/_rejected_imagegen/README.md`. The pattern:

> In every attempt the model got the **text** right and something **structural** wrong — a bar drawn
> at 57% where the data said 36%; a feedback arrow that did not originate where it claimed; a label
> attached to the wrong arrow. In two of three the model reported all its own checks as passing.

**That is this paper's own thesis happening to this paper's own figure.** Every defect was caught by a
measurement made *outside* the tool that produced it. So:

- The three data figures **must never be image-generated.** They render statistics from 16,380
  decisions per arm.
- Figure 1 is drawn in **TikZ from the data**, with a guard that exits non-zero if the corpus ever
  contradicts what the diagram shows (`gov_high < nov_high`), and a collision check that is
  **mutation-tested** — a label is deliberately pushed into a box to prove the check can fail.
- **A reported "0 collisions" from a checker living inside the figure's own script is not evidence.**
  Three rounds reported it and the author rejected the figures each time. Verify from the shipped PDF,
  at true print size, with a checker that has been made to fail on purpose.

### Vocabulary — changed 2026-08-04 because the author could not read the figures

Every technical label was replaced with plain wording. `approved` → `passed`; `precondition` →
`water-right cap`; `appraisal rule` → `rule reading what it said`; `unparsed` → `could not be read`;
`never retried` → `never blocked`; and the two most important, on Figure 4:
`conditional (HIGH-appraisal denominator)` → **`out of decisions where it said scarcity was high`**,
`unconditional (all decisions)` → **`out of every decision`**.

**The body text keeps its technical terms** — that is correct for the venue — **so each caption
bridges the two.** If you change a figure label, check its caption still bridges.

## 7. State as of 2026-08-04, measured

```
evidence    PASS   13 scripts, 13 PASS
figures     PASS   4 referenced, 4 on disk, none stale
build       PASS   0 LaTeX errors, 0 overfull, 0 underfull
pages       PASS   9 pp; body ends p8, References from p8; 12 body lines spare
fonts       FAIL   9 Type 1, 3 TrueType, 0 Type 3
anonymity   PASS   9 artefacts, 8 needles, 0 leaks
citations   PASS   17 entries, 14 cited, 0 unverified
```

**The fonts failure is a project standard, not a venue standard.** The template blocks *Type 3 fonts
or non-embedded TrueType*. Ours are embedded TrueType, and Type 3 is at zero. It does not block
submission. It is open only because figure text is Times New Roman and three DejaVu faces remain.

## 8. The three commands that answer the three recurring questions

| question | command |
|---|---|
| is the experimental material enough? | `python SUBMISSION_2026/TAE/evidence/corpus_inventory.py` |
| are all the numbers still right? | `python SUBMISSION_2026/TAE/evidence/run_all.py` |
| is this ready to submit? | `python SUBMISSION_2026/TAE/paper/submission_gate.py` |

**Prefer these to any prose in this repository, including this file.** Ten tracking documents in this
directory have each gone stale at least once; the scripts read the truth off disk.

## 9. Build

```
cd SUBMISSION_2026/TAE/paper
PYTHONIOENCODING=utf-8 python make_bibliography.py && python substitute.py && python build.py \
  && "/c/Users/wenyu/AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe" \
     -interaction=nonstopmode -enable-installer manuscript.tex     # run twice
```

Three guards, none of which may ever be weakened: `substitute.py` fails on an unmatched **or unused**
`{{CLAIM:...}}` marker; `build.py` raises on unmapped non-ASCII; `pdflatex` must exit 0.

`manuscript.md` is the master. The `.tex` and `.docx` are generated. Do not edit them.

## 10. Standing rules

1. **Add nothing to the manuscript that changes what it claims.** Narrowing an over-broad claim is
   required and is not "adding". Evidence that does not enter the paper stays in `NUMBERS.md`.
2. **Never cut a disclosure, a limitation, a confidence interval or a coverage figure to buy space.**
   If that is the only way something fits, it does not fit.
3. **Double-blind.** The author's name, email and affiliation belong in the OpenReview form, never in
   the PDF. `build.py` carries a `CAMERA_READY` flag, default False; flipping it is the last step
   before camera-ready and never before.
4. **Write only inside `SUBMISSION_2026/TAE/`.** `examples/`, `broker/` and `paper/nature_water/` are
   off limits — the first is the frozen run corpus, the last is a separate paused manuscript.
5. **Plain language.** The author is a water researcher, not a CS-venue regular, and has asked four
   times for plainer prose. Gloss any term of art in the same sentence it appears.
