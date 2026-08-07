# Experiment registry — every corpus, what it answers, who reads it

**Start here** if you are writing a paper against this repository and need to know what data exists,
what question it was produced to answer, and whether you may use it.

This file is the index. Each arm's full design record lives at
`examples/<domain>/experiments/<arm>.md` and is written **before** the run, not after.

> **Some paths below are not in this checkout.** `SUBMISSION_2026/`, `ICLR2027/` and
> `DATA_OWNERSHIP.md` are submission workspaces that live on the branch
> `p0-1-governance-instrumentation` and have deliberately not been merged: `main` is the
> framework platform line. They are cited here because they are where the evidence code and the
> ownership ruling actually are, and a citation you can chase to another branch is worth more
> than a gap. Everything under `broker/`, `examples/` and `tests/` resolves in this checkout.

---

## Why this file exists

`DATA_OWNERSHIP.md` at the repo root answers *which corpus belongs to which paper*, and it was
produced the hard way — by importing the analysis code and asking it what it reaches. That worked,
but it is archaeology: the design intent behind each corpus had to be reconstructed from the
directory name and the code that reads it.

Anything produced from 2026-08-05 onward carries its design record from the start, so the next
author does not have to do that reconstruction. Three layers, each with one job:

| layer | file | tracked by git | answers |
|---|---|---|---|
| **index** | this file | yes | what exists, who owns it, may I use it |
| **design** | `examples/<domain>/experiments/<arm>.md` | yes | what question, what design, what would falsify it |
| **provenance** | `<run>/reproducibility_manifest.json` | no — it lives with the data | which code, which config, which flags, which seed |

The run data itself is **not** in git. `.gitignore` excludes `results/`, deliberately: audit CSVs and
simulation logs are data, and a 9 GB repository helps nobody. The design record is tracked, so the
description survives even if a disk does not — and a copy of it is written **into** the run directory
at launch, so the description also travels with the data if the folder is moved or shared alone.

---

## The corpora

### Irrigation — `examples/irrigation_abm/results/`

| arm | model cells | seeds | question it answers | primary reader |
|---|---|---|---|---|
| `production_v21_42yr_*` | gemma3:4b · gemma3:12b · gemma4:e2b · gemma4:e4b · ministral3:8b | 42–46 (12b, ministral: 42–44) | governed behaviour under the full validator stack | conference paper; Nature Water Paper 1b |
| `ungoverned_v21_42yr_*` | same five | same | the no-validator comparison arm | same |
| `fql_raw/` | — | 42–51 | the Fuzzy Q-Learning kernel of Hung & Yang (2021), run **through WAGF with all 12 validators active** — 71% of its actions are blocked | Nature Water: Fig. 2's grey trace, Extended Data Table 1, SI Table 11; `examples/irrigation_abm/analysis/fql_comparison_*.py` |
| `fql_nogov/` | — | 42–51 | the same kernel with `--no-governance`. **Not used by any paper** — an audit arm, kept for the result: without validators the same kernel reaches dead pool in 10 of 10 seeds | nothing. See [its record](irrigation_abm/experiments/fql_nogov_2026-08.md) |
| `firstattempt_gov_gemma3_4b_seed4x` | gemma3:4b | 42–46 | **does the recorded appraisal differ from the one the agent first wrote?** | conference paper §5/§8; reusable by Nature Water — see the design record |

Design records: [`examples/irrigation_abm/experiments/`](irrigation_abm/experiments/)

### Flood, single agent — `examples/single_agent/results/`

| directory | question | primary reader |
|---|---|---|
| `JOH_FINAL` / `JOH_FINAL_v2` | governed flood adaptation across nine model configurations | **both** Nature Water Paper 1b and the conference paper |
| `JOH_ABLATION_DISABLED` / `_v2` | the no-validator flood comparison | **both** |
| `rulebased` | rule-based (non-LLM) baseline | Nature Water **only** |
| `_QUARANTINE_reflection_missing_2026-05-30` | **nothing — it is quarantined evidence** | nobody, by design |

**This directory has two owners.** A change made for one paper can silently move the other paper's
numbers, and Nature Water is the one going to a journal. Treat it as read-only for both.

**The quarantine is not clutter.** `_DATA_DEFECTS_2026-05-30.md` inside it records a reflection
confound that was caught, measured, and set aside rather than silently pooled. It is 226 MB that no
analysis reads, which makes it look like the obvious thing to delete. Deleting it destroys the
evidence that the defect was handled — in a project whose entire argument is about defects that pass
unnoticed. It stays.

### Flood, multi-agent — `examples/multi_agent/flood/results/`

Paper 3. Read by 14 analysis files under `examples/multi_agent/flood/paper3/`. Neither the Nature
Water analysis nor the conference pipeline touches it.

### Inert

`governed_flood/results` · `quickstart/results` · `cat_model/results` — 1.7 MB together, no analysis
file in any paper references them. `quickstart/results` is regenerated by anyone following
`wagf-quickstart`.

---

## Rules for adding a new arm

**1. A new arm writes to a NEW directory under `examples/<domain>/results/`.** Never into a frozen
one, and never without an explicit `--output`. A governed `gemma3:4b` irrigation run with `--output`
omitted writes next to the frozen `production_v21_42yr_seed<S>` corpus.

**2. The directory name must not contain `_v21_42yr_`.** This is not cosmetic. Two different
discovery mechanisms read this tree:

- `SUBMISSION_2026/TAE/evidence/_data.py` uses an **allow-list** — a directory is reachable only by
  being named there. Safe by construction.
- `SUBMISSION_2026/evidence/*.py` (`exogeneity_check.py:134`, `gate0_signal_floor.py:65`,
  `skeleton_claims_check.py:84` and five more) **glob** `{prefix}_v21_42yr_{seg}seed*`. A new
  directory matching that pattern is silently pooled into a published number.

Verified 2026-08-05. `firstattempt_gov_gemma3_4b_seed42` matches neither.

**3. Write the design record before the run, not after.** `examples/<domain>/experiments/<arm>.md`,
following the template in that directory. Writing it first is what forces the question,
the falsification condition, and the known limitations to be stated while they can still change the
design.

**4. Use an isolated config root.** Never edit a frozen config to enable a flag. The runners take
`--config-dir` (irrigation) or `--config-root` (single-agent flood). Copy the whole config tree,
change the one key, and record the diff. Note that
`examples/irrigation_abm/run_ungoverned_experiment.py` has **no such flag** as of 2026-08-05 — a
no-validator arm cannot use an isolated config until that is added.

**5. Add a row here when the arm lands.** One row, and a link to its design record.

---

## What is deliberately not here

Nothing in this file is derived from a directory name. Every claim above about who reads what was
established by reading the analysis code. If you add a row, do the same — a plausible-looking
directory name is how the `fql_raw/` corpus was nearly mistaken for an orphan.
