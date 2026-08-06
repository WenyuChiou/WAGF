# Workspace consolidation plan — 2026-08-06

Status: PLAN ONLY. Two moves proposed, twelve questions for the author, nothing executed.
Scope: the three submission workspaces (`SUBMISSION_2026/`, `ICLR2027/`, `AAMAS2027/`) and the
one orphan directory at the repository root (`figures/`).

---

## Read this first

The paper was going to a NeurIPS workshop called TAE. TAE closed on 5 August, and the work moved
to a main-track venue with ICLR 2027 in front. The move was done in a hurry and it was done
halfway, so the repository now has three folders that all look like "the submission folder" and
nothing on disk says which is which.

**What is actually messy is not the files — it is the labelling.** The ICLR package is real and
buildable: I rebuilt its PDF from a copy in a scratch directory and got the same nine pages, and
all three of its self-checks pass. The evidence pipeline that produces every number in that paper
is real too. The problem is that they live in *different folders*, the folder holding the evidence
is named after the dead venue (`SUBMISSION_2026/TAE/`), and a reader who tidied by name would
delete the thing the live paper depends on.

**What I am proposing to move: two files.** A stray figure attempt-log sitting alone in a
repository-root `figures/` folder, and a style-file zip that belongs one directory deeper next to
the files that were unpacked from it. That is the entire safe list. Everything else that looks
movable turned out to have a script, a build, or a git rule pointing at it.

**What I am not touching.** The experiment currently running — `SUBMISSION_2026/TAE/runs/` was
still being written to at 00:19 this morning and must not be moved, renamed or edited until it
finishes. Both manuscripts. The evidence scripts. Every dated record file, including the ones that
are now wrong about the venue, because a wrong record with a banner is history and a corrected
record is a lost audit trail.

**What I need from you.** Twelve decisions, listed in §3. Three of them matter more than the rest:
(1) how an `_archive/` folder should interact with git, because the repository's `.gitignore`
currently makes "archive it" mean "quietly remove it from version control"; (2) whether ICLR 2027
gets written into `DECISION.md` as the confirmed destination, because two files currently
disagree; (3) what to do about a submission gate that still reports PASS against the withdrawn
workshop's rules.

---

## 1. One target layout

This is not a redesign. It is the layout the repository already half-declares, written down once
so the boundaries are visible. `ICLR2027/submission/SOURCE_OF_TRUTH.md:33-44` already fixes the
inside of the ICLR package; this extends the same idea up one level.

```text
governed_broker_framework/
│
├─ ICLR2027/                       ACTIVE SUBMISSION — the paper being written now
│  ├─ README.md                    entry point: what this package is, where its numbers come from
│  ├─ FIGURE_STYLE_AUDIT.md        survey of how comparable papers draw figures
│  ├─ experiments/                 run CONFIGS authored for ICLR, plus their smoke outputs
│  └─ submission/                  the release package; internal layout fixed by SOURCE_OF_TRUTH.md
│     ├─ paper/                    manuscript.tex + references.bib  ←  THE LIVE MANUSCRIPT
│     ├─ figures/active/           only the four figures manuscript.tex actually includes
│     ├─ figures/assets/           canonical generated source asset for Figure 1
│     ├─ figures/candidates/       rejected Figure 1 alternatives; never referenced by TeX
│     ├─ source/                   Figure 1 builder + vendored ICLR style files
│     ├─ checks/                   the three gates + the reproducibility audit copy
│     └─ supplement/               machine-readable release CSVs
│
├─ SUBMISSION_2026/                EVIDENCE BACKEND + HISTORICAL RECORD — not a dead folder
│  ├─ TAE/                         frozen TAE package; ICLR's authority rank 1 lives inside it
│  │  ├─ evidence/                 THE evidence pipeline (_data.py, e0–e7, fig0–fig3, run_all.py)
│  │  ├─ figures/                  pipeline figure outputs; source of ICLR's figures/active
│  │  ├─ NUMBERS.md                the number ledger both papers are checked against
│  │  ├─ paper/                    the TAE manuscript + its build chain + submission_gate.py
│  │  ├─ runs/                     LIVE EXPERIMENT + its run configs — UNTOUCHABLE
│  │  ├─ analysis/                 dated analysis and adjudication records (this file)
│  │  └─ _archive/                 superseded TAE material (already invisible to git)
│  ├─ evidence/ decomposition/     pre-TAE campaign: superseded, but two live consumers
│  ├─ papers/ audit/ ops/          pre-TAE campaign records and audits
│  ├─ runs/config_flood/           pre-TAE flood run config
│  └─ README.md                    campaign index — currently stale, see decision 6
│
├─ AAMAS2027/                      PRE-TAE ANCESTOR workspace (misnamed) — 0 files tracked by git
│
└─ figures/                        repo-root orphan: one TAE figure attempt log (see move S1)
```

### Why each thing lives where it lives

**The manuscript lives in `ICLR2027/submission/paper/manuscript.tex`** — and the TAE manuscript
stays where it is, because they are two different papers, not one file that moved. They share
43 of roughly 2,500 eight-word sequences and exactly one sentence; they carry different titles,
different section sets, and different citation machinery. `SUBMISSION_2026/TAE/paper/manuscript.md`
is still the input to `build.py:111`, `substitute.py:40` and `make_bibliography.py:49`, and its
sha256 still matches the release hash recorded in `SUBMISSION_2026/TAE/manuscript_state.json`.

**The evidence pipeline stays in `SUBMISSION_2026/TAE/evidence/`** because
`ICLR2027/submission/checks/evidence_boundary_check.py:32-41` names eight files there by literal
path and errors if any one is absent, and ten sibling scripts import `_data.py` by bare name.

**Figures are generated in `SUBMISSION_2026/TAE/figures/` and copied into
`ICLR2027/submission/figures/active/`** because that split is the documented contract at
`ICLR2027/submission/supplement/FIGURE_REGENERATION.md:31-33`, which warns that regenerating
writes back into the historical TAE tree.

**Run configs stay under `<workspace>/runs/config_*`** because
`SUBMISSION_2026/TAE/evidence/e3_run_integrity.py:85` matches the literal string
`config_irrigation_firstattempt`, and `.gitignore:317` keeps `config_*` directories trackable by
name inside an otherwise-ignored `runs/` tree.

**Superseded material goes to an `_archive/` inside its own workspace** — subject to decision 1
below, which is currently unresolved and blocks almost every archival move.

---

## 2. Safe moves

A move qualifies only if no script builds a path into it, it is not a manuscript, it is not under
`SUBMISSION_2026/TAE/runs/`, and it does not change the file's git tracking status. Two qualify.

Prefix every verification command with `PYTHONIOENCODING=utf-8` — the console is cp950.

### S1 — the repo-root `figures/` orphan

```
FROM  figures/fig0_generated_v2.md
TO    SUBMISSION_2026/TAE/analysis/fig0_generated_v2_attempt_log.md
```

**Why safe.** It is the only file in a repository-root `figures/` directory, and it is a dated log
of how a TAE figure was produced — which is exactly what `SUBMISSION_2026/TAE/analysis/` holds.
A grep across all `*.py` finds no script reference. The only inbound mentions are three historical
Codex briefs (`.ai/codex_task_tae_fig1_imagegen_{detailed,v3,v4}.md`) that name it as a file to
*write*, not to read. Destination is tracked and not ignored (`git check-ignore` on
`SUBMISSION_2026/TAE/analysis/cleanup_2026-08-05.md` exits 1), so the file stays in version
control. Not a manuscript; not under `TAE/runs/`.

**Why renamed.** A different file of the same name already exists at
`SUBMISSION_2026/TAE/_archive/cleanup_2026-08-05/figure-history/_rejected_imagegen/fig0_generated_v2.md`
(23,781 B versus 18,553 B — different documents). Keeping both names identical would recreate the
confusion this plan exists to remove. **Record of the rename:** the moved file is the *attempt log*
whose closing line records the final saved artifact; the archived twin is the *image-generation
log* for the three rejected imagegen attempts. Neither supersedes the other.

**Verify after moving:**
```
git status --porcelain figures SUBMISSION_2026/TAE/analysis
git check-ignore -v SUBMISSION_2026/TAE/analysis/fig0_generated_v2_attempt_log.md   # expect exit 1
PYTHONIOENCODING=utf-8 python ICLR2027/submission/checks/evidence_boundary_check.py # expect exit 0, PASS
```
Expected: exactly one rename pair and no other change. The now-empty `figures/` directory can be
left on disk; git does not track empty directories.

### S2 — the ICLR style zip next to what was unpacked from it

```
FROM  ICLR2027/submission/source/iclr-2027-style-files.zip
TO    ICLR2027/submission/source/iclr_style/iclr-2027-style-files.zip
```

**Why safe.** A grep across `*.py`, `*.md` and `*.tex` for `iclr-2027-style-files` returns nothing
anywhere in the repository — no script, no doc, no build step reads it. It is the distribution
archive that `source/iclr_style/iclr2027/` was unpacked from, so it belongs beside it. Source and
destination are both tracked and non-ignored. The LaTeX build reads
`source/iclr_style/iclr2027/` through `TEXINPUTS`; adding a `.zip` to the *parent* of that
directory does not enter the search path. Not a manuscript; not under `TAE/runs/`.

**Verify after moving:**
```
git status --porcelain ICLR2027/submission/source
PYTHONIOENCODING=utf-8 python ICLR2027/submission/checks/manuscript_static_check.py   # expect exit 0, PASS
PYTHONIOENCODING=utf-8 python ICLR2027/submission/checks/figure1_geometry_check.py    # expect exit 0
```

### Why the list is only two items long

The working tree has **zero untracked, non-ignored files** across all three workspaces
(`git status --porcelain --untracked-files=all` returns nothing) — there is no loose cruft to
sweep. Everything else that looked movable failed one of the four tests:
`figures/candidates/` is named in the ICLR layout rule; the design-record `.md` files are cited by
`manuscript_state.json` path fields and by same-directory markdown links; `manuscript.docx` is a
build product marked ACTIVE in `manuscript_state.json`; the pre-TAE campaign directories have two
live consumers. Each of those is a question in §3 instead.

---

## 3. Needs decision

### 1. How should `_archive/` interact with git? *(blocks most other archival moves)*

`.gitignore:219` is a bare `_archive/`, which matches at any depth. Verified:
`git check-ignore -v SUBMISSION_2026/TAE/_archive/README.md` resolves to that line, and
`git ls-files SUBMISSION_2026/TAE/_archive` returns 0 files. So **moving any tracked file into any
`_archive/` directory removes it from version control while leaving it on disk** — which defeats
the point of archiving instead of deleting.

- (a) Add targeted negations, e.g. `!ICLR2027/submission/_archive/` plus `!.../**`.
- (b) Use a name that is not ignored, e.g. `superseded/` or `history/`.
- (c) Accept untracking for archived material.

**Recommend (b)** for anything currently tracked, and leave `_archive/` for material that is
already untracked. It needs no `.gitignore` surgery and keeps provenance inside git.

### 2. The venue gate that PASSes against the dead spec *(reported, not fixed — constraint 4)*

`SUBMISSION_2026/TAE/paper/submission_gate.py:127-129`:
```python
BODY_PAGE_LIMIT = 8          # NeurIPS 2026 TAE workshop: 8 pages excl. refs + appendices
VENUE_CFP_URL = "https://tai-eval.github.io/cfp/"
VENUE_WORKSHOP_TITLE = "TAE (Trust-AI-Eval): Can We Trust AI Evaluation?"
```
`gate_venue()` at `:835-864` requires `\usepackage[dblblindworkshop]{neurips_2026}` and an exact
`\workshoptitle` match, and it reads only `SUBMISSION_2026/TAE/paper/manuscript.tex`, whose line 13
still satisfies both. It therefore reports PASS for a venue that no longer exists. The compounding
problem: it never reads the live ICLR manuscript, and the ICLR side has **no page gate at all** —
`manuscript_static_check.py` checks page count only per figure. `ICLR2027/submission/REVIEW_ROUNDS.md:464`
records the last build at 9 pages, against ICLR's own 9-page limit
(`source/iclr_style/iclr2027/iclr2027_conference.tex:131`). Zero slack, ungated.

- (a) Record ICLR in `DECISION.md`, then re-point `BODY_PAGE_LIMIT` to 9 and swap the CFP/style checks.
- (b) Make the venue gate hard-fail until a destination is recorded.
- (c) Freeze TAE's gate as a historical artifact and add a separate page/anonymity gate under
      `ICLR2027/submission/checks/`, where the live manuscript is.

**Recommend (c), then (a).** The TAE gate is a correct record of a real contract; the live paper
needs a gate that lives next to it. `DECISION.md:20-22` already names this as blocked on decision 4.

### 3. Are the two manuscripts one source or two?

**Two.** Evidence: no build consumes the `.md` for ICLR (the only markdown→TeX pipeline is
`SUBMISSION_2026/TAE/paper/build.py:110-113`, TAE-local); the two share 43 of ~2,500 eight-grams
(Jaccard 0.0086) and exactly one sentence; different titles
(`manuscript.md:1` vs `manuscript.tex:15`); different section sets; different citation machinery;
and each declares itself `current_manuscript` in its own `manuscript_state.json`. The only open
question is what to do about it.

- (a) Declare both live in the layout doc; neither is archived.
- (b) Archive the TAE manuscript as superseded.

**Recommend (a).** `build.py`, `substitute.py`, `make_bibliography.py` and `submission_gate.py`
all read the TAE `.md`, and its sha256 still matches the release hash in `manuscript_state.json`.
Archiving it breaks four scripts to tidy one folder.

### 4. Where does the destination get recorded?

`SUBMISSION_2026/TAE/DECISION.md:14-18` reads "**No destination is confirmed.** … whoever confirms
the destination must write it into this file. Until then, no file in this project records where
the paper is going." Meanwhile `ICLR2027/submission/manuscript_state.json:294-299` already asserts
`"active_venue": {"primary": "ICLR 2027", ...}` and `VENUE_MATRIX.md:5` says "Primary target:
ICLR 2027". The package has been built as if the decision were made; the file designated to hold
the decision says it was not.

- (a) Write ICLR 2027 into `DECISION.md` as a new dated entry below the existing banner.
- (b) Demote the `manuscript_state.json` claim to "working assumption".

**Recommend (a).** This is the single decision that unblocks decision 2 and decision 12.

### 5. The pre-TAE campaign directories

`SUBMISSION_2026/{evidence, decomposition, papers, audit, ops}` are superseded by `TAE/evidence/`,
and `TAE/BOUNDARY.md:43` declares that nothing in TAE imports or opens them. But they have two live
consumers: `papers/workshop_evidence.py:70,77` inserts `decomposition/` on `sys.path` and reads
`evidence/appraisal_composition.csv` by literal name, and `audit/audit_data_selection.py:43-46`
requires a file in `AAMAS2027/`. They are also depth-2 locked: 23 scripts compute
`REPO = __file__/../..` with no assertion that the result is the repo root, so re-parenting them
fails silently on an empty corpus rather than raising.

- (a) Keep in place; add a short "superseded pre-TAE campaign, kept for provenance" note to
      `SUBMISSION_2026/README.md`.
- (b) Move to `SUBMISSION_2026/_archive/pre_tae_campaign/` — blocked on decision 1 and breaks both consumers.

**Recommend (a).**

### 6. `SUBMISSION_2026/README.md:3` is false

It says "Gitignored (`.gitignore:291`). This repo is public; nothing here is for the public tree."
Both halves are wrong: `git ls-files` counts 143 tracked files under `SUBMISSION_2026`, and
`.gitignore:296-300` records that the repository went **private on 2026-08-05** and these
workspaces were deliberately tracked. `AAMAS2027/README.md:12` carries the same half-stale claim.
An agent trusting that line could either force-add unpublished material believing it inert, or
refuse to commit legitimate provenance.

- (a) Correct the two sentences, dated, leaving the rest of the file unedited.
- (b) Leave and rely on this plan.

**Recommend (a).** It is a two-sentence doc edit, not a move, so I did not make it.

### 7. `AAMAS2027/` is misnamed

It is the **pre-TAE ancestor** workspace, created 2026-07-28 (`AAMAS2027/README.md:12`), whose own
README carries a superseded banner. But `ICLR2027/submission/VENUE_MATRIX.md:9` names AAMAS 2027 as
the live *fallback venue*, so a future reader will reasonably assume this folder is the AAMAS
submission. It is not.

**A rename is not free.** Its own three scripts use pure `../..` walks and would survive, but
`SUBMISSION_2026/audit/audit_data_selection.py:43-46` hardcodes the string
`"AAMAS2027/experiments/appraisal_composition.py"`. Renaming breaks that audit.

- (a) Rename to something like `_pre_tae_2026-07/` **and** update `audit_data_selection.py` in the same change.
- (b) Leave the name; add a banner to `AAMAS2027/README.md` stating it predates the TAE paper and is
      not the AAMAS submission workspace.

**Recommend (b).** The whole tree is gitignored (`.gitignore:294`, 0 files tracked), so a rename
there is unrecoverable if it goes wrong.

### 8. The retracted number still on disk

`AAMAS2027/experiments/appraisal_composition.csv:12` carries
`flood ministral3_3b … +2.0352, n_governed = 4577`. The corrected value in
`SUBMISSION_2026/evidence/appraisal_composition.csv:12` is `-0.2189, n_governed = 3674` — the
opposite sign, from 903 contaminated rows pulled in by a `**` glob that reached a backup of a
different experiment. `SUBMISSION_2026/audit/MATERIALS_VERDICT.md:250` calls deleting it BLOCKING;
`audit_data_selection.py:43-46` deliberately depends on it existing, commented "the UNFIXED
original, still runnable".

- (a) Keep as a regression fixture; add a `RETRACTED.md` beside it naming the corrected value and
      the audit that depends on the broken one.
- (b) Apply the fix and update `audit_data_selection.py` to stop expecting the bug.

**Recommend (a).** Nothing is deleted, the audit keeps working, and the on-disk demonstration of
the contamination is preserved. `TAE/BACKLOG.md:83` (item W6) tracks this as open.

### 9. A bug that is byte-identical in two places

`rederive_executed_levels.py` is byte-identical across `SUBMISSION_2026/evidence/` and
`AAMAS2027/experiments/`, and **both copies carry the same `**` glob defect**
(`SUBMISSION_2026/evidence/rederive_executed_levels.py:59-62`;
`MATERIALS_VERDICT.md:100`, defect 6, still open). Fixing one copy would create a fresh divergence
of exactly the kind described in decision 8.

- (a) Leave both until the defect is scheduled.
- (b) Patch both in a single change, never one alone.

**Recommend (a) now, (b) when it is scheduled.** Flagged here so a tidy-up does not accidentally
touch one side.

### 10. ICLR design and review records at the package root

`AGENT_ARCHITECTURE_FIGURE_RESET.md`, `AGENT_PAPER_FIGURE_REDESIGN.md`, `FIGURE1_DESIGN.md`,
`FIGURE1_DESIGN_AUDIT.md` and `REVIEW_ROUNDS.md` sit at `ICLR2027/submission/` root, outside the
layout rule that file itself declares at `SOURCE_OF_TRUTH.md:33-44`. Moving them into a
`submission/history/` directory would break four things: the `"path"` fields at
`manuscript_state.json:34` and `:41`, the "Figure 1 contract" pointer at `SOURCE_OF_TRUTH.md:13`,
the handoff table at `HANDOFF.md:39-40`, and the same-directory markdown links inside the documents
themselves (e.g. `AGENT_PAPER_FIGURE_REDESIGN.md:7`).

- (a) Move to `submission/history/` and update those four references in one change.
- (b) Leave them and extend the layout rule in `SOURCE_OF_TRUTH.md` to name them.

**Recommend (b).** Cheaper, loses nothing, and the layout rule is the thing that was incomplete.

### 11. Figure duplication inside the ICLR package

`ICLR2027/submission/figures/candidates/` is 50 MB across 52 tracked files, and there are 12 groups
of byte-identical duplicates across `assets/` and `candidates/` — including a four-way group where
`figures/active/figure1_concept.png`, `figures/active/figure1_concept_print.png`,
`assets/figure1_architecture_agentpaper_shared_condition_v4.png` and
`candidates/fresh-agent-paper-round/candidate_F_black_border.png` are the same bytes. Note the trap:
`figure1_concept_print.png` is **not** a print-resolution render despite its name.

- (a) Archive `candidates/` — blocked on decision 1, and contradicts `SOURCE_OF_TRUTH.md:22,41`,
      which names `figures/candidates/` as part of the declared layout.
- (b) Keep, and add a `candidates/README.md` recording that the accepted Figure 1 is candidate F and
      that `figure1_concept_print.png` is a byte-copy, not a higher-resolution render.

**Recommend (b).** If camera-ready needs a true print render, one must be generated.

### 12. The reproducibility waiver crossed a venue boundary

`SUBMISSION_2026/TAE/HANDOVER.md:111` states the RED reproducibility audit was "narrowly waived for
a non-archival PDF-only workshop. **That waiver does not transfer to an archival venue.**" ICLR is
archival, yet `ICLR2027/submission/SUBMISSION_CHECKLIST.md` marks the row `[x]` with the same
reasoning, and `manuscript_state.json` records the issue as `WAIVED`. Separately, the audit shipped
in the package (`checks/reproducibility/artifact_inventory.yml`) covers three smoke runs, while the
audit of the actual evidence corpus — `SUBMISSION_2026/TAE/analysis/reproducibility_2026-08-04/`,
52 runs surveyed, 42/52 manifests present — is not the one shipped.

- (a) Re-decide the waiver for an archival venue and swap the 52-run corpus audit into the package.
- (b) Keep as is.

**Recommend (a).** Not a move; recorded here so it is not lost inside a tidy-up.

---

## 4. Must not move

### Deliberately left, with the reason

**The live experiment — absolute, no exceptions.** Everything under `SUBMISSION_2026/TAE/runs/`:
`firstattempt_gov_seed42/` (its `reflection_log.jsonl` was 88,549 B at 2026-08-06 00:19 and
growing), `config_irrigation_firstattempt/` (matched as a literal substring by
`evidence/e3_run_integrity.py:85`; a mismatch raises only after ~10.5 GPU-hours are already spent),
`config_irrigation_modelsmoke/`, `smoke_gemma3_4b_a2y1/`, `smoke_gemma4_12b_a2y1/`,
`smoke_gemma4_12b_a4y2/`, `_logs/`, `launch_firstattempt.md`, `probe_parse_reliability.py`. Read
only. Note also that `.gitignore:316-320` protects this tree by *literal path* — renaming
`SUBMISSION_2026` would silently make the run's output trackable.

**Anything a build or check reads:**

- `SUBMISSION_2026/TAE/evidence/**` — eight files named literally at
  `ICLR2027/submission/checks/evidence_boundary_check.py:32-41`; `_data.py` imported by bare name
  by ten sibling scripts.
- `SUBMISSION_2026/TAE/NUMBERS.md` — read by path at `evidence_boundary_check.py:20`.
- `SUBMISSION_2026/TAE/figures/**` — source of the ICLR active figures; referenced by
  `run_all.py:85`, `fig1_rule_layers.py:135`, `fig2_mechanism.py:123`, `fig3_consequence.py:92`,
  `fig0_problem_schematic.py:35`, `e7_appraisal_drift.py:63`.
- `SUBMISSION_2026/TAE/paper/**` — the manuscript plus its whole build chain (`build.py`,
  `substitute.py`, `make_bibliography.py`, `submission_gate.py`, `references.bib`,
  `neurips_2026.sty`, `_body_only.txt`, `ANONYMITY.md`, the generated `.substituted.md`, `.tex`,
  `.docx`, `.pdf`, `.aux`, `.log`, `.out`). `template/` looks redundant — its `neurips_2026.sty` is
  byte-identical to the copy one level up — but `build.py:999-1014` treats `template/` as the source
  and copies it on every run.
- `ICLR2027/submission/paper/**` — the live manuscript. Constraint: do not edit, do not move.
- `ICLR2027/submission/{figures/active, figures/assets, source, checks, supplement}/` — read by
  `manuscript.tex:58,119,141,170`, by `TEXINPUTS`, and by the three check scripts.
  `checks/` is depth-locked specifically: `evidence_boundary_check.py:17` uses `parents[3]`.
- `ICLR2027/experiments/config_firstattempt/` and `_smoke_firstattempt/` — the config is the input
  half of the only pre-seed-42 fill-rate measurement; moving it orphans the output.
  `SUPERSEDED.md` beside it is the record of why it was superseded.
- `SUBMISSION_2026/runs/config_flood/` — trackable only via the `.gitignore:317` negation
  `!SUBMISSION_2026/**/runs/config_*/`; moving it out of a `runs/` directory changes its git status.

**Three directory NAMES are load-bearing:** `SUBMISSION_2026`, `ICLR2027`, and
`SUBMISSION_2026/TAE`. They are literal strings in `evidence_boundary_check.py:18-19` and
`SUBMISSION_2026/papers/workshop_evidence.py:70,77`. Renaming any of them breaks the ICLR
evidence gate — including renaming `ICLR2027`, which that script does from inside `ICLR2027`.

**Every historical record, kept unedited:** `TAE/DECISION.md` (its own banner at `:10-11` says "do
not rewrite it"), `TAE/README.md`, `TAE/HANDOVER.md` (the primary evidence that TAE closed, with
two verbatim organiser emails), `TAE/CODEX_REVIEW.md`, `TAE/SUBMISSION_READINESS.md`,
`TAE/PLAN.md`, `TAE/STATUS.md`, `TAE/BACKLOG.md`, `TAE/BOUNDARY.md`, `TAE/EXPERIMENT_OPTIONS.md`,
`TAE/RUN_DECISION.md`, `TAE/manuscript_state.json`, `SUBMISSION_2026/CAMPAIGN_PLAN.md`,
`SUBMISSION_2026/TAE/analysis/**`, `SUBMISSION_2026/TAE/_archive/**`. Several of these are now
wrong about the venue. That is what makes them records.

**`SUBMISSION_2026/{evidence, decomposition, papers, audit, ops}/`** — depth-2 locked across 23
scripts, with two live consumers. See decision 5.

**`AAMAS2027/**`** — `git ls-files AAMAS2027` returns 0. There is no git history to restore from;
a filesystem move there is unrecoverable.

### Not yet examined — treat as unknown, not as cleared

- I did not read the `leave_alone` section of `SUBMISSION_2026/TAE/analysis/cleanup_2026-08-05.md`
  (around `:389`) in full, so I cannot say whether `STATUS.md`, `BACKLOG.md` and `BOUNDARY.md` were
  deliberately left without a venue banner on 2026-08-05 or simply missed.
- I could not establish whether `SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py` is live. It was
  written 2026-08-05 12:33 and writes `TAE/figures/e7_appraisal_drift.csv`, but
  `grep -c e7_appraisal_drift SUBMISSION_2026/TAE/evidence/run_all.py` returns 0. It sits outside the
  verified pipeline and outside the ICLR supplement. Treated as must-not-move.
- I did not inventory `ICLR2027/submission/figures/candidates/legacy/` file by file.
- I read only the filenames in `SUBMISSION_2026/ops/`, not the contents.
- `ICLR2027/experiments/config_firstattempt/SUPERSEDED.md:28` cites
  `SUBMISSION_2026/TAE/ops/_lane_prereg_v1_superseded.md:98`. No `TAE/ops/` directory exists; the
  file is at `SUBMISSION_2026/ops/`. Already broken before this plan; not caused by any move.

---

## 5. Provenance of this plan

Four read-only mapping lanes ran before this plan was written (authority, dependencies, submission
requirements, duplication). **None failed.** One lane recorded that it could not determine
manuscript authority from the dependency graph alone; that is resolved in decision 3 from build
evidence, not from the graph.

Nothing was moved, renamed, edited or deleted in producing this plan. No writing git command was
run. The three ICLR check scripts were executed and rewrote only their own report JSON files to
byte-identical content. `SUBMISSION_2026/TAE/runs/` was listed and read only.
