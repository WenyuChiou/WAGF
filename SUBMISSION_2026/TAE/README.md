# TAE submission workspace

> ## ⚠ VENUE WITHDRAWN — 2026-08-05
>
> The TAE workshop closed on 2026-08-05 (organiser withdrawal, AGU date-line conflict). **The
> "29 August 2026" deadline and the "≤ 8 pages" and "non-archival" constraints below are dead
> — they are kept as the record of what this work was built against.** No destination is
> confirmed; the leading candidate is ICLR 2027 main track (25 September 2026 AoE, 9 pages,
> unlimited appendix). See [HANDOVER.md](HANDOVER.md) and [DECISION.md](DECISION.md).
>
> The "Dual-submission policy is **unconfirmed**" note below is also superseded: the organisers
> gave written clearance for a later main-conference version (`HANDOVER.md:37`).
>
> Banner added by `analysis/cleanup_2026-08-05.md`. Nothing else in this file was changed.

> **Entry point is [HANDOVER.md](HANDOVER.md).** This file is a working record and its status
> claims go stale. Anything about whether something passes, is complete or is ready is measured
> by `evidence/corpus_inventory.py`, `evidence/run_all.py` and `paper/submission_gate.py` --
> prefer those three to any sentence here.

## Start here: three commands, three questions

Run these instead of trusting anything written in this folder. Each one reads the
actual files on disk and tells you what is true right now. Every other document
here is prose, and prose goes out of date without anyone noticing.

```
python SUBMISSION_2026/TAE/evidence/corpus_inventory.py     # is the experimental material enough?
python SUBMISSION_2026/TAE/evidence/run_all.py              # are all the numbers still right?
python SUBMISSION_2026/TAE/paper/submission_gate.py         # is this ready to submit?
```

**1. Is the experimental material enough?** — `evidence/corpus_inventory.py`
Counts the finished runs, checks that each model has the same number of governed
and no-validator runs, and names the exact runs still missing. Takes 3 seconds.
*Passing looks like:* the last line reads `VERDICT: COMPLETE`. If it says
`IN PROGRESS`, a run is still being written and you only need to wait. If it says
`FAIL`, something disagrees and the reason is printed above the verdict.

**2. Are all the numbers still right?** — `evidence/run_all.py`
Recomputes every number the paper prints, straight from the run outputs, and
redraws the figures. Takes about a minute, no GPU, no network.
*Passing looks like:* every script reported `PASS` in the summary table, and an exit
code of 0. (The script count is printed by the command and is deliberately not
written here — it has grown several times, and every document that recorded it
went stale.) These scripts stop on purpose when a value disagrees with the recorded
one, so a failure here is a finding about the numbers, not usually a broken script.

**3. Is this ready to submit?** — `paper/submission_gate.py`
Rebuilds the PDF and checks the seven things that would get it rejected: the
numbers, the figures, the build, the page limit, the fonts, the anonymity, and the
citations. Takes about two minutes.
*Passing looks like:* the last line reads `VERDICT: READY TO SUBMIT` and the exit
code is 0. Anything else prints a `WHAT TO DO` list under each failing check.

`corpus_inventory.py --help` and `submission_gate.py --help` explain their options;
`run_all.py` takes none and ignores the flag, so do not pass it — it will simply run
the whole pipeline. None of the three writes anything outside this folder, and none
of them touches the experiment results.

> **Today (3 Aug):** checks 2 and 3 are **red**, for one known reason — a
> ministral3:8b run is still being written and the data module refuses to read a
> half-written run. This is expected and is not damage. Run check 1 to see whether
> it has landed. Nothing needs fixing until it does.

---

Everything for one paper: **NeurIPS 2026 TAE workshop, "Can We Trust AI Evaluation?"** — the claim
that when a governance layer's norm conditions on a state the agent itself reports, the conformance
statistic has no observation channel independent of the process it governs, so enforcement rewrites
the distribution of its own conditioning variable.

This folder is self-contained. It **reads** the experiment results under `examples/` and writes
nothing outside itself.

## Three hard constraints

| | |
|---|---|
| **Deadline** | **29 August 2026, AoE.** Notification 22 Sep. |
| **Length** | **≤ 8 pages**, references excluded. Appendices unlimited, but reviewers need not read them. |
| **Anonymity** | **Double-blind.** The group's own WRR 2026 predecessor and the Nature Water manuscript must be cited in the **third person** throughout. Non-archival. Dual-submission policy is **unconfirmed** on the CFP — check before submitting, a main-track version is planned. |

## Regenerate everything

```
python SUBMISSION_2026/TAE/evidence/run_all.py
```

Zero GPU, no network. Runs the data-module self-test, the premise and specification checks, the
table, every figure, and the independent re-derivation, then prints a pass/fail summary.

**How many scripts it runs, how long it takes, and how many pass are not recorded here** — the
script prints all three every time, and any number written down in this file would be wrong within
a day. Run it and read its own summary line.

The scripts are written to fail loudly rather than round quietly. A non-zero exit is usually a
finding about a number, not a broken script, so read the failure before assuming the code is at
fault. Nothing here should ever be tuned until a disagreement stops being printed. Resolved
disagreements are recorded in `NUMBERS.md` §12.

## Files

| path | what it is |
|---|---|
| `DECISION.md` | The decision document: venue, the one-sentence claim, the corrected mechanism, and the claims-discipline list. **Read first.** Its §8 structure table and §9 figure list are stale — the manuscript is the authority on both. |
| `PLAN.md` | The claim + forbidden-claims block (§2) and the experiment fences (§5) are live and load-bearing. **Its day-by-day calendar is overtaken by about two weeks — do not follow it.** Use `STATUS.md` for what to do next. |
| `BACKLOG.md` | The historical backlog. **Most items marked OPEN are in fact closed**; the statuses were last verified 1 Aug. Kept for the audit trail — the verification method recorded in each row is its real value. Do not read it for status. |
| `EXPERIMENT_OPTIONS.md` | The costed experiment menu behind `PLAN.md` §5. |
| `NUMBERS.md` | Claim → value → script → exact stdout line, for every number the paper may print. Includes the list of claims **no script produces**. This is what the red-team reads. |
| `BOUNDARY.md` | The folder contract: what may be read, what may be written, what is vendored from the frozen configs, the one regeneration command, and the cold-start requirements. Read before adding a script or moving the folder. |
| `STATUS.md` | Today's state, the open decisions, and what is blocking. Rewritten each working pass — the only tracking file meant to be current. |
| `SUBMISSION_READINESS.md` | The pre-submission risk register and the weakest-link analysis of the argument. Its per-item statuses are stale; see the header note. |
| `RUN_DECISION.md` | The go/no-go on running more experiments, and its fences. Expires 6 Aug. |
| `README.md` | This file. |
| **`paper/manuscript.md`** | **The master source of the paper.** Everything in `paper/` is generated from it. Edit this, never the `.tex` or `.docx`. |
| `paper/build.py`, `substitute.py`, `make_bibliography.py` | The build chain, run in that reverse order: bibliography → claim substitution → LaTeX/docx. `paper/submission_gate.py` drives all three. |
| `paper/submission_gate.py` | The submission check: numbers, figures, build, page limit, fonts, anonymity, citations. See the top of this file. |
| `paper/references.bib`, `template/`, `ANONYMITY.md` | Bibliography, the venue's official style files, and the anonymity checklist. |
| `evidence/run_all.py` | Runs every evidence script in order and aggregates pass/fail. It prints the script count itself; this table does not duplicate it. |
| `evidence/corpus_inventory.py` | Reads both results trees and reports which runs exist, which cells are balanced, and which runs are missing. Writes nothing. See the top of this file. |
| `evidence/e1`…`e6_*.py` | The premise, limitation and specification checks behind sections 4, 5 and 8. Each writes no artefact and exits non-zero if its check fails. |
| `evidence/fig0_problem_schematic.py` | Figure 1: the problem schematic (TikZ). |
| `runs/` | Captured stdout from past pipeline runs, kept as an audit trail. |
| `evidence/_data.py` | The shared data-access module. Every other script imports it. Owns the contamination rules, the arm/seed selection, the rate definitions, and the paired-t machinery. Run it directly for a self-test. |
| `evidence/e0_year1_exogeneity.py` | The cornerstone premise: exact equality of the two arms' year-1 world, per column, plus the first divergence year. Writes no artefact; exits 1 if the premise fails. |
| `evidence/table1_cells.py` | Per-cell table, 14 cells, both testbeds, both action readings → `evidence/table1_cells.csv`. |
| `evidence/fig1_rule_layers.py` | **Figure 2**: what causes a rejection, by arm and by rule kind. |
| `evidence/fig2_mechanism.py` | **Figure 3**: year-1 null, reservoir divergence, never-retried stratum — why the conditioning variable moves. |
| `evidence/fig3_consequence.py` | **Figure 4**: conditional vs unconditional Delta across five irrigation cells. |

> **The figure filenames are one lower than the figure numbers.** `fig0_` is Figure 1, `fig1_` is
> Figure 2, `fig2_` is Figure 3, `fig3_` is Figure 4 — `fig0_problem_schematic` was added after the
> others were named. The manuscript's `<!-- FIGURE n -->` markers are the authority. Do not rename
> the files to match; several documents still use the old numbering and renaming would silently
> repoint them.
| `evidence/_verify_pipeline.py` | Independent re-derivation of the headline numbers. Imports nothing from `_data.py`; uses pandas/numpy/scipy and literal per-seed paths. Agreement between two unrelated implementations is the check. |
| `figures/*.png`, `*.pdf` | Generated figures. Do not hand-edit; regenerate. |
| `figures/*.csv`, `evidence/table1_cells.csv` | Every plotted value, machine-readable. |

## Conventions that are not optional

**Dependencies.** `_data.py` and the three figure scripts need only the standard library plus
matplotlib. `_verify_pipeline.py` additionally needs pandas, numpy and scipy — deliberately, since
using different libraries is what makes its agreement evidence.

**Sign.** `Delta = (no-validator) MINUS (with-validators)`. Positive means the validators **lowered**
the quantity. Every figure axis and every table column carries it. `_data.DELTA` is keyword-only —
`DELTA(a, b)` raises `TypeError` — precisely so this cannot be transposed by accident again.

**Inferential unit is the seed**, not the decision. Paired t-test, df = n−1. Any cell whose two arms
have different seed counts is **excluded from every paired contrast**, shown separately and marked;
the exclusion list is `_data.IRRIGATION_UNBALANCED_PREFIXES`.

Which cells that currently covers, and how many seeds each cell has, is **not written down here** —
run `evidence/corpus_inventory.py`, which measures it and also tells you when an entry in that
exclusion list has outlived its reason. As of the last check `ministral3:8b` was the only excluded
cell, and the run that would balance it was still being written; the script will say so plainly
either way.

**Cell value is the mean of per-seed rates**, not a pooled rate. This is load-bearing: the anchor
governed pooled conditional rate is 36.26, the mean of per-seed rates is 36.05, and 36.05 is the
published number.

**Two action readings, always labelled.** `LAST-PROPOSED` (`yearly_decision` as written) is what every
published number uses. `EXECUTED` substitutes `maintain_demand` on rejected rows. They differ
enormously — the anchor governed conditional rate is 36.05 under one and 0.86 under the other — and
are never interchangeable.

**Flood is a cross-theory portability demonstration, not a control.** It has no action→environment
feedback. Never call it a "low enforcement pressure control".

---

# DATA HYGIENE — read before touching any path

**A `Group_A` backup directory once flipped the sign of a published cell.** The results trees under
`examples/` contain, side by side with the real runs, a different experiment, several backups, a
quarantine folder, and dead partial runs. A bare `**` glob from a model directory picks them up
silently, produces a plausible-looking number, and nothing errors.

**Never match:**

- `Group_A` — a *different experiment* (no structured prompts), not an arm of this one
- any `*_bak*` / `*backup*` directory
- `_QUARANTINE_*`, `_dead_*`, or **any** path segment beginning with `_`

**Always:**

- Name `Group_C` / `Group_C_disabled` **explicitly**. Never descend to them with a wildcard.
- Select both arms with patterns of the **same strictness**. An asymmetric pair is a silent bias —
  it will not raise, it will just be wrong.
- Let it raise on empty. A discovery function that returns `{}` instead of raising is how a
  contaminated or missing arm becomes a published number.

**These rules are enforced structurally in `evidence/_data.py`, not by convention.** The module
exports no glob pattern and no path template — a caller cannot construct a path, only request one.
Four independent layers: hand-written literal model allow-lists; anchored `re.fullmatch` on run
directory names; literal group names per flood arm; and `_reject_contaminated()` applied to every
path the module ever returns. The self-test **actively attempts** each known hazard and asserts it
refuses — 15 guards, checked on every run.

**If you write a new analysis script, import `_data` and use its discovery functions.** Do not
re-implement a path, a glob, an arm selector, or a rate definition. That re-implementation is exactly
what the sign error was.

**Two known provenance defects, both reported rather than absorbed** (details in `NUMBERS.md` §8):

1. Flood manifest seeds disagree across arms in 6 of 9 models; pairing is by **run index**.
2. The flood audit CSV coverage is 70.5–100% of the nominal 1,000 (100 agents × 10 years)
   design-expected decisions. This is **not damage** — relocation is a designed absorbing state that
   ends an agent's participation, so an agent that relocates in year *y* stops generating rows for
   the remaining years. Verified exactly on 5/5 `ministral3:3b` `Group_C` runs: audit rows =
   1,000 − relocated-agent-years-lost (764/236, 705/295, 714/286, 735/265, 756/244). Every flood
   rate is a per-run rate over rows that exist, never pooled over a nominal 1,000 denominator.
