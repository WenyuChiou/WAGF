# BOUNDARY.md — the folder contract

> **Entry point is [HANDOVER.md](HANDOVER.md).** This file is a working record and its status
> claims go stale. Anything about whether something passes, is complete or is ready is measured
> by `evidence/corpus_inventory.py`, `evidence/run_all.py` and `paper/submission_gate.py` --
> prefer those three to any sentence here.

`SUBMISSION_2026/TAE/` is the whole of one paper: NeurIPS 2026 TAE workshop, 8 pages, 29 Aug 2026 AoE.
This file is the contract that keeps it that way. It was written 2026-07-31 after an audit of every
inbound and outbound dependency, and every statement in it was checked against the tree rather than
assumed.

The contract in one line: **this folder reads the frozen experiment corpus and nothing else, writes
inside itself and nowhere else, and regenerates completely from one command.**

---

## 1. What may be READ

| may read | why |
|---|---|
| anything inside `SUBMISSION_2026/TAE/` | it is the paper |
| `examples/irrigation_abm/results/**` | the frozen irrigation corpus |
| `examples/single_agent/results/**` | the frozen flood corpus |
| `examples/**` configs, **by a human, for transcription only** | see §4, vendoring |

Exactly two file kinds are opened at runtime, both through `evidence/_data.py`:

```
examples/irrigation_abm/results/<run>/simulation_log.csv
examples/irrigation_abm/results/<run>/irrigation_farmer_governance_audit.csv
examples/single_agent/results/<base>/<model>/<group>/Run_N/household_governance_audit.csv
examples/single_agent/results/<base>/<model>/<group>/Run_N/reproducibility_manifest.json
```

`_verify_pipeline.py` opens the two irrigation files directly, by literal path, on purpose — a second
implementation that shared the first one's discovery code would not be independent evidence.

**41 run directories are read.** `_verify_pipeline.py` asserts this and prints `forbidden-token hits: 0`.

### What may NOT be read

`SUBMISSION_2026/evidence/`, `SUBMISSION_2026/decomposition/`, `SUBMISSION_2026/papers/`,
`SUBMISSION_2026/audit/`, `SUBMISSION_2026/ops/`, `SUBMISSION_2026/runs/` and `AAMAS2027/` are
**working directories of the wider campaign**. They keep changing. Nothing here imports, opens, or
depends on a file in any of them, and nothing here may start to. A number that lives only in a
sibling working directory is an **unsourced number** for this paper — `NUMBERS.md` §11 is the list of
those, kept deliberately.

`paper/` is a **separate, paused manuscript**. Do not read it for numbers, do not write to it, do not
plan work on it. Anything found here that bears on it goes into a note for later, never into an edit.

`broker/` is framework source. This folder does not import it and must not: the corpus was produced
by the code as it stood at run time, and importing today's `broker/` would silently re-define a rate.

---

## 2. What may be WRITTEN

**Only paths under `SUBMISSION_2026/TAE/`.** Verified empirically: a full `run_all.py` run on
2026-07-31 22:54 modified 10 files, all of them in `TAE/figures/` and `TAE/evidence/table1_cells.csv`,
and `find` across the rest of the repo for anything newer than that run returned **nothing**.

| written by the pipeline | |
|---|---|
| `evidence/table1_cells.csv` | `table1_cells.py` |
| `figures/fig1_rule_layers.{png,pdf,csv}` | `fig1_rule_layers.py` |
| `figures/fig2_mechanism.{png,pdf,csv}` | `fig2_mechanism.py` |
| `figures/fig3_consequence.{png,pdf,csv}` | `fig3_consequence.py` |
| `evidence/__pycache__/` | the interpreter; disposable |

`_data.py` and `_verify_pipeline.py` write nothing. No script takes an output path from an argument,
so there is no way to redirect one outside the folder.

The frozen corpus is **read-only from here**. No file under `examples/irrigation_abm/results/` or
`examples/single_agent/results/` has been modified since before 2026-07-01; the pipeline does not open
them for writing at all.

---

## 3. Inbound dependencies — the full list

Audited by grepping every `.py` and `.md` in this folder for paths outside it.

**Code: zero.** No `import`, no `sys.path` entry, and no `open()` reaches outside `TAE/` except into
the two frozen results trees. `sys.path.insert` appears in four scripts and every one of them inserts
the script's own directory so it can `import _data`.

**Prose: one remaining citation, not load-bearing on the pipeline.** Two were closed on 2026-08-01.

| where | what it points at | verdict |
|---|---|---|
| ~~`evidence/fig2_mechanism.py:16`~~ | ~~`SUBMISSION_2026/evidence/exogeneity_check.py`~~ | **CLOSED 2026-08-01.** `evidence/e0_year1_exogeneity.py` now re-derives it locally, in the shape prescribed below, and is step 2 of `run_all.py`. The docstring cites the local script. |
| ~~`DECISION.md:96`~~ | ~~the same script, same claim~~ | **CLOSED 2026-08-01.** `DECISION.md` §4 and `NUMBERS.md` §4a cite `evidence/e0_year1_exogeneity.py`. |
| `DECISION.md:3` | `workshop_skeleton.md` in `SUBMISSION_2026/papers/` | **Leave.** It is a historical note that this document supersedes that one. Nothing depends on the file existing. |

`NUMBERS.md` §11 flagged the first two honestly until they were closed, which is the reason this was a
known gap rather than a hidden one. That §11 row is now deleted and replaced by `NUMBERS.md` §4a,
which carries the produced values and their stdout locators.

**The fix that was applied, and the shape it took.** Do **not** copy `exogeneity_check.py` across. It is
739 lines, it depends on pandas, and it discovers run directories with `glob` — the exact hazard
`_data.py` was built to make unreachable, and dropping it into `evidence/` would re-open it. Vendor
instead a small `evidence/e0_year1_exogeneity.py` that gets its run directories from
`_data.irrigation_run()` and re-derives only the two facts the paper prints: year-1 exact-equality
across arms on the pre-treatment columns, and the year of first divergence. **Done 2026-08-01**: 300
lines, standard library only, no glob, no path construction, run directories from
`_data.irrigation_run()`. It gates on nine pre-decision columns and exits 1 if the year-1 rate is not
1.0. It also found that `utilisation_pct` and `below_minimum_utilisation` are **post**-decision
(written in `post_year` from the demand the year's skill just set) and excludes them from the gate,
printing them with a control rather than dropping them silently.

---

## 4. What is vendored

Facts transcribed by hand from files this folder is allowed to read, so that no config is parsed at
run time and no config change can silently move a number.

| vendored | source, transcribed from | checked |
|---|---|---|
| `fig1_rule_layers.APPRAISAL_CONDITIONED_RULES` — 3 rule ids | `examples/irrigation_abm/config/agent_types.yaml`, the `thinking_rules` carrying `construct: WSA_LABEL` / `ACA_LABEL` | yes, the three constructs are at `agent_types.yaml:349,359-360,389` |
| `fig1_rule_layers.WORLD_CONDITIONED_RULES` — 11 rule ids | `examples/irrigation_abm/validators/irrigation_validators.py` `rule_id` literals | yes, every vendored id appears there |
| "`not at_allocation_cap` is attached to `increase_large` and `increase_small` and to no other skill" | `examples/irrigation_abm/config/skill_registry.yaml` | printed as prose by `fig1_rule_layers.py`; it is a **config fact, not a computed statistic**, and `NUMBERS.md` §11 says so |
| the brief's verified values that each script cross-checks itself against | `DECISION.md` | the scripts exit non-zero on disagreement; one currently does — `NUMBERS.md` §12 |

The rule lists are guarded rather than trusted: `fig1_rule_layers.py:222-224` collects any
`failed_rules` token absent from both frozensets, and lines 252-255 abort the figure if the set is
non-empty. On the current corpus it is empty. One validator id, `zero_escape_floor`, exists in
`irrigation_validators.py` and is in neither list — it never fires in this corpus, so it is not a
defect today, and if it ever did fire the guard would stop the figure rather than misclassify it.

---

## 5. The one command

```
python SUBMISSION_2026/TAE/evidence/run_all.py
```

Zero GPU, no network. Runs the data-module self-test, the premise and specification checks, the
table, every figure, and the independent re-derivation, then prints a pass/fail summary.

**Which scripts it runs, how long it takes, and how many pass are deliberately not recorded here.**
The script prints all three itself, and this section previously carried three mutually incompatible
answers within nineteen lines — a six-script list, a "9/9 PASS" claim, and a run log showing 5 of 6.
Run the command.

Two companion checks answer the questions this one does not:

```
python SUBMISSION_2026/TAE/evidence/corpus_inventory.py     # is the experimental material enough?
python SUBMISSION_2026/TAE/paper/submission_gate.py         # is this ready to submit?
```

**The standing rule is unchanged: nothing here should ever be tuned until a disagreement stops
printing.** The scripts fail loudly rather than round quietly, so a non-zero exit is usually a
finding about a number rather than a broken script. The one historical disagreement this section
used to describe — `fig2_mechanism.py` computing +40.45 against +40.40 — was resolved on
2026-08-01 and is recorded in `NUMBERS.md` §12.

### Cold-start requirements

| | |
|---|---|
| Python | 3.14.0 confirmed; the pipeline is `from __future__ import annotations` throughout and uses no 3.14-only syntax |
| `_data.py`, `table1_cells.py`, the three figure scripts | standard library + **matplotlib** (3.10.7 confirmed) |
| `_verify_pipeline.py` only | **pandas** 2.3.3, **numpy** 2.4.2, **scipy** 1.17.0 — a different stack on purpose; that is what makes its agreement evidence |
| data | the two frozen results trees, unmodified |

**One cold-start fragility, unfixed and stated rather than hidden.** `_data.py:99` computes
`REPO = HERE/../../..`, so this folder must sit at `<repo>/SUBMISSION_2026/TAE/` for the results roots
to resolve. Copy it anywhere else — a reviewer's machine, an artefact zip — and every script raises
`DataError: missing irrigation results root`. It raises rather than returning nothing, which is the
right failure, but there is no environment-variable override. If the folder is ever shipped
standalone, add one before shipping.

---

## 6. Findings recorded, not acted on

Both were produced by earlier phases of the same working session, **before** any file in `TAE/`
existed, and neither is TAE work. The hook log `hooks/hook_debug.log` orders every `Edit`/`Write` of
the session: the last write to `broker/` is at log line 38057, to `examples/` at 38157, to
`paper/nature_water/drafts/` at 38667, and the **first** write to `SUBMISSION_2026/TAE/` is at 38882.
No write outside `SUBMISSION_2026/TAE/` occurs after that line.

1. **`paper/nature_water/drafts/` was edited on 2026-07-30.** Six files — `abstract_v16.md`,
   `introduction_v16.md`, `methods_v7.md`, `section2_v19_results.md`, `section3_v17_discussion.md`,
   `supplementary_information_v15.md` — carry mtime 2026-07-30 13:31 and creation times 13:09-13:18,
   and the hook log records 15 `Edit` calls against them. `paper/` is gitignored and untracked, so
   there is no diff and no way to recover what changed. The Nature Water manuscript is paused; this is
   recorded for the user to review and **must not be reverted, re-edited, or otherwise touched from
   this folder.**
2. **`paper/nature_water/figures/Fig3_cumulative_adaptation.{png,pdf}` were regenerated** 2026-07-30
   23:16 by an accidental figure-script execution. No other file under `paper/` was hit: those two are
   the only `paper/` files with a mtime later than 2026-06-13 apart from the six drafts above.

Neither the frozen corpus nor `broker/` was touched by TAE work. `examples/irrigation_abm/results/`
and `examples/single_agent/results/` contain **zero** files modified since 2026-07-01.

---

## 7. If you add a script to this folder

- Put it in `evidence/`. Import `_data` and use its discovery functions. Do not write a glob, a path
  template, an arm selector, or a rate definition — that re-implementation is what produced the sign
  error this project has already published once.
- Read only the two frozen results trees. If you need a number that currently lives in a sibling
  working directory, **vendor the derivation**, do not import across the boundary.
- Write only under `SUBMISSION_2026/TAE/`.
- Register it in `run_all.py`'s `SCRIPTS` list with the artefacts it writes, and add every number it
  produces to `NUMBERS.md` with the stdout fragment that carries it.
- Make it exit non-zero when it disagrees with `DECISION.md`. A loud disagreement is the point.

## Venue facts, resolved 2026-08-01 (closes W1 / R1 and R6)

Fetched from the workshop's own pages (`https://tai-eval.github.io/` and its Call for Papers), not
inferred from a previous year:

| item | value |
|---|---|
| page limit | **8 pages, excluding references and appendices** |
| archival | **non-archival**, no proceedings |
| review | **double-blind** |
| LaTeX | `\usepackage[dblblindworkshop]{neurips_2026}`; camera-ready `[dblblindworkshop, final]` |
| deadline / notification | 29 Aug 2026 AoE / 22 Sep 2026 AoE |
| OpenReview | `NeurIPS.cc/2026/Workshop/TAE` |
| **dual submission** | **NOT STATED on either page** |

**R1 (dual submission).** Neither page states a policy. Non-archival with no proceedings strongly
implies no exclusivity, and a main-track version later is the normal use of such a venue, so the
residual risk is low. Mitigation: one email to the organisers. Not a blocker for drafting.

**R6 (column width) — CONFIRMED 2026-08-01 against the real `.sty`, and the earlier assumption was
right.** `neurips_2026.sty` was obtained from the workshop's own CFP page
(`https://tai-eval.github.io/cfp/`, which names
`https://media.neurips.cc/Conferences/NeurIPS2026/Formatting_Instructions_For_NeurIPS_2026.zip` as the
official author kit) and saved to `SUBMISSION_2026/TAE/paper/template/` (`neurips_2026.sty`,
`neurips_2026.tex`, `checklist.tex`, plus the zip itself). The style is **single-column**
(`\usepackage[verbose=true,letterpaper]{geometry}` + `\newgeometry{textheight=9in, textwidth=5.5in,
top=1in, headheight=12pt, headsep=25pt, footskip=30pt}`, `neurips_2026.sty:127-141` — no
`\twocolumn`/`multicol` anywhere in the file). **Text width is exactly 5.5 in**, not "about" — the
earlier assumption was correct, not merely safe. One template requirement not previously recorded:
workshop mode (`dblblindworkshop`) requires **both** `\title{}` and `\workshoptitle{}}`
(`neurips_2026.tex:41-43`). **This has been done** — `paper/build.py:798` emits it and it appears at
`paper/manuscript.tex:63`.

**The toolchain gap recorded here is closed.** This section used to say no LaTeX engine was
installed and that nothing in the repo had ever produced a PDF from `manuscript.tex`. That was true
on 2026-08-01 and is not true now. MiKTeX is installed and `manuscript.pdf` is built from
`manuscript.tex` + `neurips_2026.sty` routinely:

```
C:\Users\wenyu\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe
```

`paper/submission_gate.py` drives the whole chain (`make_bibliography` → `substitute` → `build` →
`pdflatex` twice), then reads LaTeX errors and overfull boxes out of `manuscript.log` and the page
count out of the PDF itself. **Do not record the build state here again** — run the gate.
