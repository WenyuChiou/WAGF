# HANDOVER — everything about this submission, in one file

**This is the only file you need.** You do not need the conversation that produced it.

**Read LIVE STATE first — it is about right now.** Then VENUE CHANGE. Everything below those — every
status line, every gate result, every deadline, and the whole of the older "why this venue" reasoning
— was written while this paper was going to the TAE workshop. **It is not.** The work is sound; the
destination moved.

---

# LIVE STATE — 2026-08-06, Claude → Codex. Read before touching anything.

**Two things are happening in this repository right now. One of them will be destroyed by an ordinary
edit if you do not know about it.**

## 0. WRITE BOUNDARY — who owns what, so we do not collide

**You keep the paper. I keep the plumbing.** The author has asked you to carry on with the paper's
direction and Figure 1; this section exists so you can do that without checking with anyone.

| | owner | notes |
|---|---|---|
| `ICLR2027/submission/paper/**` | **Codex** | the manuscript, its bibliography, its build. I do not write here. I have read it and reported findings below; acting on them is yours. |
| `ICLR2027/submission/figures/**`, `source/**` | **Codex** | Figure 1, its generator, the style files |
| `ICLR2027/submission/*.md` (design, handoff, review rounds, checklist) | **Codex** | your working record |
| `ICLR2027/submission/checks/**` | **Codex** | your gates. One suggestion below (§3③); yours to take or leave. |
| `SUBMISSION_2026/TAE/evidence/**` | **shared — coordinate** | the pipeline your numbers come from. See the note below. |
| `SUBMISSION_2026/TAE/figures/**` | **shared — coordinate** | generated here, copied into `ICLR2027/submission/figures/active/` |
| `SUBMISSION_2026/TAE/runs/**` | **nobody, until ~10:30** | a live experiment is writing here (§1) |
| `broker/**`, `examples/**` | **Claude** | framework and corpora. Do not edit `broker/` at all while the run is live. |
| `.gitignore`, `DATA_OWNERSHIP.md`, `examples/EXPERIMENTS.md` | **Claude** | repository plumbing |
| `SUBMISSION_2026/TAE/HANDOVER.md` | **shared — append, never rewrite** | you have a section below (`CURRENT HANDOFF`); this one is mine. Neither of us edits the other's. |

### What I changed, exhaustively, so you can rule it out as a cause

Everything below happened between 2026-08-05 22:00 and 2026-08-06 01:00.

| file | change |
|---|---|
| `.gitignore` | **three rules fixed**, all the same defect class — unanchored patterns matching at any depth. `paper/` → `/paper/` (it was swallowing all 22 files of `SUBMISSION_2026/TAE/paper/`, manuscript included). `SUBMISSION_2026/**/runs/` → `runs/**` plus negations (it was excluding the isolated config a run reads). `_archive/` given submission-scoped negations (it was making "archive it" mean "untrack it"). Also added LaTeX build-output rules, which surfaced only once `/paper/` was anchored. **Every one verified with `git check-ignore -q` exit codes in both directions.** |
| `SUBMISSION_2026/TAE/evidence/_data.py` | added `"output_schema_violation"` to `_NO_RULE_TOKENS`; rewrote the comment above it (it named the wrong commit) and the `rejection_cause` docstring. **No number moves**: 0 of 348 audit CSVs carry that token in `failed_rules`, and re-deriving the anchor cell reproduces gov 6,469 theory / noval 4,757 precondition exactly. |
| `examples/EXPERIMENTS.md`, `examples/irrigation_abm/experiments/` | **new** — a corpus registry and per-arm design records, so a future author can tell which data belongs to which paper without re-deriving it from code |
| `DATA_OWNERSHIP.md` | pointer block added at the top |
| `ICLR2027/experiments/config_firstattempt/SUPERSEDED.md` | **new** — that config tree lacks `executed_skill_columns` and would fail the integrity gate on every seed. Kept, not deleted; it is the input half of the only smoke test that exists. |
| commit `50247de3` + tag `firstattempt-launch-2026-08-05` | 151 files brought into version control, including the 22 that `paper/` had been hiding |
| two file moves | listed in §2 below |

**Nothing I changed touches the manuscript, its figures, or its build.** If an ICLR build breaks, I
am not the cause — with one exception, disclosed in §2: a verification step regenerated
`SUBMISSION_2026/TAE/figures/fig{0,1,2,3}*.pdf` and `manuscript.docx`. Content unchanged, timestamps
differ, all validated.

### The one place we genuinely share: `SUBMISSION_2026/TAE/evidence/`

Your numbers come from there and I edited one file in it. **If you need to change anything under
`evidence/`, append a line to your `CURRENT HANDOFF` section saying which file and why, rather than
editing silently** — that directory is the single point where a change of mine could move a number of
yours, and vice versa. I will do the same in reverse.

### What I am doing next, in order

1. **Establishing which copy of `appraisal_composition.py` is authoritative** (§4①, the sign flip).
   Analysis only; touches no manuscript.
2. **After the run finishes (~10:30): the `broker/` validator fix** (a bare `except Exception: pass`
   with its logger commented out, on the Tier-0 governance path). Latent, never fired in 137,592
   rows, but real. Will go through the review gate plus a mock byte-identity check.
3. **After that: the workspace consolidation proper**, which needs directory renames and therefore
   script edits — safe only once nothing is reading `SUBMISSION_2026/TAE/runs/`.

**When you reach a stopping point, append a handover to your section.** Tell me what changed in the
manuscript's direction, what Figure 1 became, and anything you need from the evidence pipeline. I
will fold it in.

### WHICH PAPER NEEDS WHAT — there are three, and only one is yours

This repository holds three manuscripts and they are at different stages. Confusing them is the most
likely way effort gets spent in the wrong place.

| paper | where | status | who acts |
|---|---|---|---|
| **ICLR 2027** — *When Governance Changes What Gets Counted: Measurement Validity for LLM Agent Evaluation* | `ICLR2027/submission/paper/manuscript.tex` | **live, and the one to work on** | **Codex** |
| **TAE workshop** — *When Guardrails Change What Gets Counted: Conformance Metrics with Agent-Reported Rule Conditions* | `SUBMISSION_2026/TAE/paper/manuscript.md` | **frozen** — the venue closed 2026-08-05 | nobody |
| **Nature Water Paper 1b** (a different project) | `paper/nature_water/drafts/` — gitignored | paused; has its own defects, listed below | the author, later |

**These are two different papers, not two renderings of one.** Measured, not assumed: the ICLR `.tex`
shares **43 of roughly 2,500 eight-grams** with the TAE markdown (Jaccard 0.0086) and exactly one
sentence. Different titles, different framings — "guardrails / conformance metrics" became
"governance / measurement validity" — 12 sections became 7. **Do not treat the TAE manuscript as a
source to regenerate from, and do not port edits between them.**

**What the ICLR paper needs, in order:**

1. **The bibliography, from 6 to something a main-track reviewer will accept.** §3① above has the gap
   analysis and the fabrication warning. Free in page terms. Highest value.
2. **Item C1 — restore what the 8-page limit cut** (§1's roadmap paragraph, §2's worked-example
   walkthrough, §6's different-estimand paragraph). Partly available now, more available as the
   bibliography grows; see §3②.
3. **A page gate that reads the live manuscript.** Nothing currently watches it (§4②).
4. **A real answer on the RED reproducibility audit.** It was waived because TAE was non-archival.
   **That waiver does not transfer to an archival venue** and the carry-over is not bannered anywhere.

**What Nature Water needs — recorded here so it is not lost, but it is not yours and not now:**
its flood arms are seed-unpaired (governed 42/**4202**/**4203**/45/46 against control 42/43/44/45/46,
paired by folder index, so 2 of every 5 pairs compare unlike with unlike across six models), and three
of its analysis scripts test `status == "REJECTED"` by exact equality and so silently drop
`REJECTED_FALLBACK` — 105 of 6,469 rejections in the published irrigation cell.

### WHAT I WILL MOVE, and when — so nothing surprises you

Nothing further moves while the run is live. After it finishes:

| when | what | why it waits |
|---|---|---|
| **~10:30, immediately after the run** | the `broker/` validator fix (§4 below) | editing `broker/` mid-run can kill the run |
| **after that** | workspace consolidation proper | it needs directory renames, and `e3_run_integrity.py:85` hardcodes `config_irrigation_firstattempt` while the run is reading that tree |
| **not scheduled** | renaming `SUBMISSION_2026/TAE/` | four directory names are load-bearing and ~31 scripts are locked to their exact depth. This is a code change, not a file move, and it needs its own decision |

**Two moves have already happened**, both listed in §2: a root-level `figures/fig0_generated_v2.md`
became `SUBMISSION_2026/TAE/analysis/fig0_generated_v2_attempt_log.md`, and
`iclr-2027-style-files.zip` moved one level down into `source/iclr_style/`. **Neither touches your
build.** That is the complete list to date.

### THE RUNNING EXPERIMENT — results will be appended below when it lands

**One run, in flight**: `gemma3:4b`, governed arm, seed 42, 42 years, 78 agents. Started
2026-08-05 23:20, expected ~10:30 on 2026-08-06. Four more seeds (43–46) are conditional on seed 42
passing its gate — the queue is not automatic and will not start without a decision.

It answers one question: **among decisions the governance loop blocked, did the recorded appraisal
end up different from the one the agent first wrote?** The shipped corpus cannot answer it, which is
what §8 admits.

<!-- RESULTS PLACEHOLDER — Claude fills this at ~10:30. Do not write here. -->

**RESULTS: pending.** When the run lands I will append, in this spot:

- the `initial_labels` fill rate by stratum, against the >95% gate — **the stop condition**; if
  retried rows come in under 95%, seeds 43–46 do not run and this section says so
- the drift rate **with its denominator**, and whether it is reported as a floor (it must be — the
  appraisal is captured at the first and final attempts only, never mid-retry)
- the `failed_rules` literal census, which is the first real-data check of whether
  `output_schema_violation` ever fires
- wall clock, and any integrity assertion that failed
- **what it means for §5, §8 and Figure 1's caption** — that is the part you need. If the appraisal
  barely moves, §5's world-composition account carries the whole effect and §8's admission narrows.
  If it moves substantially, there is a within-decision revision channel alongside the compositional
  one, and §5, §8 and the abstract each need a paragraph distinguishing two different quantities.
  **Neither outcome falsifies the paper**; both change what it can say.

**Until that section is filled, write nothing that depends on the answer.** `PLAN.md` §5 pre-authorises
one extra writing day for the second case, so there is no schedule pressure to guess.

## 1. 🔴 A REAL 11-HOUR EXPERIMENT IS RUNNING. Do not touch `broker/`.

Launched 2026-08-05 23:20 local. Expected finish ~10:30 on 2026-08-06.

```
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed 42 --memory-seed 42 --workers 1 \
  --governance-mode strict --num-ctx 8192 --num-predict 4096 \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt \
  --output      SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42
```

**What this forbids until it finishes:**

| do not | why |
|---|---|
| **edit anything under `broker/`** | the runner spawns subprocesses that re-import the package mid-run; an edit can kill it at hour 9 |
| **touch `SUBMISSION_2026/TAE/runs/`** — config, output, logs, launch doc | the process is reading the config and writing the output; a move or edit corrupts a run that cannot be restarted before the fence |
| **start another GPU job** | one model is resident at 100% GPU; a second evicts it and the run silently falls back to CPU, which ran 12× slower on 2026-05-13 and cost four hours before anyone noticed |
| **let Windows Update reboot** | paused until 2026-08-10; an auto-reboot has killed a run at year 10 before |

Progress is readable without touching anything:
`SUBMISSION_2026/TAE/runs/_logs/seed42.log` (grep `^--- Year`) and
`SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42/raw/irrigation_farmer_traces.jsonl` (line count).

**Why it matters to the paper.** It records `initial_skill` / `initial_labels` / `attempt_skills` —
the appraisal the agent wrote at attempt 0, before the retry loop reassigned it. §8's admission that
"its first attempt is absent from the shipped corpus" is what this closes. **Early result at 262
traces: `initial_labels` non-empty on 99.6% of all rows and 100% of retried rows**, against a >95%
gate. The pre-launch worry — a 1b smoke showing 80% on retried rows — was a weak-model artefact.

**Do not weaken the Figure 1 caption's disclosure on the strength of this.** It says "the **frozen**
corpus does not preserve the first response before a retry", which is precisely scoped and stays
literally true after this arm lands. That wording is correct; leave it.

## 2. Claude is consolidating the submission workspaces. Expect files to move.

Three workspaces exist and the migration between them was half-finished:

| dir | files | tracked | governance `.md` | python |
|---|---|---|---|---|
| `SUBMISSION_2026/` | 376 | 143 | 28 | **60** |
| `ICLR2027/` | 146 | 122 | 12 | **5** |
| `AAMAS2027/` | 27 | **0** | 20 | 3 |

**The structural fact is the last column: the paper moved to `ICLR2027/`, the evidence pipeline did
not.** `ICLR2027/submission/checks/evidence_boundary_check.py` reaches back into `SUBMISSION_2026/`
for it. 60 governance markdown files across three workspaces is what the author asked to be reduced.

A mapping-then-move pass is in flight. **Rules it operates under, so you know what will and will not
happen:** nothing is deleted — superseded material moves into `_archive/<venue>/` with a README
saying what it was and why; no manuscript is edited or moved; nothing under
`SUBMISSION_2026/TAE/runs/` moves at all; the venue gate is *not* re-pointed, because the destination
is still not recorded in `DECISION.md`.

### WHAT MOVED — completed 2026-08-06 00:45. **Two files. That is the whole list.**

| from | to | why |
|---|---|---|
| `figures/fig0_generated_v2.md` (repo root) | `SUBMISSION_2026/TAE/analysis/fig0_generated_v2_attempt_log.md` | a figure attempt-log sitting alone in a root-level `figures/` directory; it belongs with the other dated analysis records. The root directory is now empty. |
| `ICLR2027/submission/source/iclr-2027-style-files.zip` | `ICLR2027/submission/source/iclr_style/` | it sat one level above the files unpacked from it |

**Nothing else moved, and the reason is worth reading, because it is the opposite of what "tidy up"
suggests.**

**The live ICLR paper's evidence backend lives inside the folder named after the dead venue.** Every
number in `ICLR2027/submission/paper/manuscript.tex` is produced by `SUBMISSION_2026/TAE/evidence/`.
`ICLR2027/submission/checks/evidence_boundary_check.py:32-41` names eight files there by literal
path and errors if any is absent; ten sibling scripts import `_data.py` by bare name;
`supplement/FIGURE_REGENERATION.md:31-33` documents the generate-in-TAE, copy-into-ICLR split as the
contract. **`SUBMISSION_2026/TAE/` is not a dead folder. Tidying by name would delete what the live
paper depends on.**

Four directory names are load-bearing — `SUBMISSION_2026`, `ICLR2027`, `TAE`, and `runs/config_*` —
and roughly 31 scripts are locked to their exact depth below the repo root. Renaming any of them is a
code change, not a file move.

### ONE GITIGNORE RULE WAS FIXED, because it made archiving destructive

`.gitignore:219` was a bare `_archive/`, unanchored, matching at any depth. It was silently excluding
`SUBMISSION_2026/TAE/_archive/` — **165 files, 52 MB, of which 25 markdown files are the written
reasoning for why each rejected figure candidate was refused.** `git ls-files` on that directory
returned zero.

So "archive it" meant "remove it from version control while leaving it on disk". Archiving a
superseded governance document would have destroyed the audit trail it exists to preserve.

That this was not the intent is not a guess: a narrower rule,
`SUBMISSION_2026/TAE/_archive/**/candidates/*.pdf`, sits further down the same file — dead code,
written by someone who believed the archive was tracked.

Now: inside a submission workspace's archive, **the records are tracked and the weight is not** —
`.md`/`.py`/`.yml`/`.json`/`.txt` in, rasters and PDFs and caches out. Verified with
`git check-ignore -q` exit codes on 21 paths in both directions including deep nesting, plus a
regression sweep confirming no already-tracked file became newly excluded. 36 archive records enter
version control; the 52 MB of rejected rasters stay on disk and out of git.

**This is the third unanchored-gitignore defect found in two days.** The other two: `paper/` was
swallowing all 22 files of `SUBMISSION_2026/TAE/paper/` including the manuscript and
`submission_gate.py` (fixed to `/paper/`); `SUBMISSION_2026/**/runs/` was excluding the isolated
config a run reads while the comment above it claimed configs were tracked (fixed to `runs/**` plus
negations). If you add a `.gitignore` rule in this repository, anchor it and verify it with
`git check-ignore -q` in **both** directions.

### AN UNINTENDED WRITE, disclosed

The consolidation pass was told to run evidence scripts "read-only where safe". **A figure generator
is not read-only.** Its verification step regenerated
`SUBMISSION_2026/TAE/figures/fig{0,1,2,3}*.pdf` and `SUBMISSION_2026/TAE/paper/manuscript.docx`, so
those five binaries now show as modified against the commit. **No damage**: the committed blobs were
extracted and validated (PDF magic + `%%EOF`, docx zip integrity all pass), and the regenerated
working copies validate too. PDFs embed build timestamps, so the bytes differ and the content does
not. Mentioned because a modified binary with no explanation is exactly the kind of thing that costs
someone an hour later.

## 3. Findings from reviewing your completed work — three, all worth your attention

Read-only review of `ICLR2027/submission/` as of 2026-08-05 21:50. **The work is good**: Figure 1
carries the actual argument (the agent-written condition both feeds the validator rule *and* selects
the counted records), the caption is honest and precisely scoped, and omitting the retry branch was
the right call — it keeps the figure to what §5 establishes rather than to what the data cannot yet
support. Three things stand out.

**① Six references is the largest acceptance risk in the current draft, and expanding the
bibliography costs nothing in pages. This is the highest-value thing you can do next.**

`references.bib` holds exactly six entries and all six are cited:

```
rebedea2023nemo · wang2026agentspec · kapoor2024agents
liu2023agentbench · bean2025construct · rosenbaum1984adjustment
```

A main-track ICLR submission with six references reads as insufficient engagement with related work
**regardless of the contribution's quality** — it is the kind of thing a reviewer notices before
reading §1. The field norm is 30–60.

**And it is free.** See ② — ICLR's page limit excludes references, so entries can be added without
displacing a single line of body text. There is no trade-off to weigh here.

Where the current six leave the paper exposed, judged against what it actually claims:

| the paper's move | what it currently cites | what a reviewer will expect |
|---|---|---|
| post-treatment conditioning as the core defect | `rosenbaum1984adjustment` alone | the causal-inference literature on conditioning on post-treatment variables, and the measurement-validity literature it borrows from |
| LLM agents are governed by runtime rules | `rebedea2023nemo`, `wang2026agentspec` | the guardrail / runtime-enforcement literature more broadly, including work this paper's mechanism resembles |
| agent evaluation is the setting | `liu2023agentbench`, `kapoor2024agents` | the benchmark-critique literature, which is large and directly adjacent |
| self-reported constructs are the conditioning variable | `bean2025construct` | self-report validity, and the chain-of-thought-faithfulness work — the paper's claim is a measurement claim about self-report |

**A warning that is not optional here.** This repository has a recorded incident from 2026-05-20: a
subagent given a citation-conversion task **fabricated roughly 30% of the references it added** —
12 of 14 — despite an explicit instruction to stop if a source could not be found. Every entry you
add must resolve to a real DOI or arXiv ID that you have actually retrieved. A fabricated citation in
a submission is worse than a thin bibliography by a wide margin.

**② Correction to what I told the author earlier: the body is NOT yet at the limit.** I said the
paper was at 9 pages and therefore full. That was wrong in a way that changes what you can do.

The PDF is 9 pages **including** the bibliography — `\bibliography{references}` sits at
`manuscript.tex:211`, inside the document. **ICLR's 9-page limit excludes references.** So the body
allowance is not exhausted; the room available equals whatever the bibliography currently occupies,
which with six entries is small but real.

The useful consequence: **as the bibliography grows it frees body space rather than consuming it.**
Going from 6 to 30 references pushes roughly a page of material out of the counted region.

So `HANDOVER` item C1 — "restore what the 8-page limit forced out", meaning §1's roadmap paragraph,
§2's worked-example walkthrough and §6's different-estimand paragraph — **is partly available now and
becomes more available as ① proceeds.** Do ① first and the space for C1 appears as a side effect.

Before drafting into that space, measure rather than estimate: build, then check where the
bibliography starts, and treat the pages before it as the counted body.

**③ `figure1_geometry_report.json` reports `PASS_MANUAL_VISUAL_REVIEW_REQUIRED` while
`text_overlap_count` and `route_intersection_count` are both `null`.** Labelling it that way rather
than plain `PASS` was the right instinct. But anything grepping for `PASS` still matches, and in a
paper whose whole subject is checks that report success while validating the wrong thing, that is a
poor field value. Suggest `NEEDS_VISUAL_REVIEW`. The visual review itself has been done: the figure
reads correctly; the only minor note is that the Validator orange and the condition amber are close
in hue for a colourblind reader, mitigated by their spatial separation.

Also recorded, not acted on: `figure1_concept.png` and `figure1_concept_print.png` are byte-identical
(same sha256), so there is no separate print-resolution asset despite the name. At 0.98\textwidth the
raster lands at ~268 DPI — usable, marginally under the 300 convention.

## 4. Two analysis findings that outrank the tidying — both reproduced by hand

**① Two copies of `appraisal_composition.py` disagree on one cell, and the sign flips.** Both were
run against the same corpus. Thirteen of fourteen rows are identical to the digit. The fourteenth:

```
flood ministral3_3b   AAMAS2027/experiments/    0.09%   28.88%   30.92%   +2.04
flood ministral3_3b   SUBMISSION_2026/evidence/ 0.11%   31.14%   30.92%   -0.22
```

The governed-arm figure differs (28.88 vs 31.14) and the shift changes sign. The headline survives
either way — regime separation stays COMPLETE, carried by min-high +21.26 against max-low +6.25 —
but the LOW-group mean moves from +0.81 to +0.56 pp, and one published-able cell has two answers.
`ministral3_3b`'s flood arm is known partial data (pre-F1 whole-run abort, ~65–73% coverage), so the
divergence is most likely a row-inclusion difference. **Whichever number reaches a paper, the other
script is wrong; decide which is authoritative before either is cited.**

**② The ICLR paper has no page gate, and the only page gate in the repository watches the wrong
manuscript.** `SUBMISSION_2026/TAE/paper/submission_gate.py:127-129` hardcodes `BODY_PAGE_LIMIT = 8`
and TAE's CFP URL and workshop title; `gate_venue()` at `:835-864` reads **only**
`SUBMISSION_2026/TAE/paper/manuscript.tex`, whose line 13 still satisfies it — so it reports PASS for
a venue that no longer exists and has never looked at the live manuscript.
`ICLR2027/submission/checks/manuscript_static_check.py` checks page counts per figure, not for the
document. The live PDF is 9 pages against ICLR's 9-page limit, with nothing watching it. Not fixed
here, because re-pointing a venue gate requires a confirmed venue and `DECISION.md` still records TAE.

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
