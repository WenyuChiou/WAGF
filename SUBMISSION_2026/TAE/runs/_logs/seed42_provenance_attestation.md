# Contemporaneous provenance record — `firstattempt_gov_seed42`

**Written 2026-08-06 while the run was at 3,124 of 3,276 traces (95.4%), roughly 25 minutes before it
finalises.** Written *before* the fact rather than reconstructed afterwards, because the thing it
records is about to be measured wrongly.

## Why this file exists

`broker/core/experiment_runner.py:509-521` samples `git status --porcelain` inside
`_collect_reproducibility_metadata`, which is reached only from `_finalize_experiment` at `:402` —
**about ten hours after launch**. It writes the answer into `reproducibility_manifest.json` as
`git_dirty`.

`SUBMISSION_2026/TAE/evidence/e3_run_integrity.py:404-408` reads that field as though it described
the tree **at launch**, and raises when it is true.

**The working tree is dirty right now and will be dirty at finalize.** So this run is about to record
`git_dirty: true` and fail its own integrity gate — and the statement that produces the failure is
**false about this run**. This file records what was actually true, measured at the time.

## What was measured, 2026-08-06, run at 95.4%

Launch commit `50247de3` (tag `firstattempt-launch-2026-08-05`). HEAD at measurement `c2e5205f`,
**26 commits later, all made during the run.**

| path the run reads | committed drift since launch | uncommitted changes |
|---|---|---|
| `broker/**` (the entire framework) | **0** | **0** |
| `examples/irrigation_abm/run_experiment.py` | **0** | **0** |
| `.../config_irrigation_firstattempt/agent_types.yaml` | **0** | **0** |
| `.../config_irrigation_firstattempt/skill_registry.yaml` | **0** | **0** |
| `.../config_irrigation_firstattempt/prompts/irrigation_farmer.txt` | **0** | **0** |
| `.../config_irrigation_firstattempt/policies/financial_prudence.yaml` | **0** | **0** |

**Every file this run reads was byte-identical from launch to finalize**, both in the index and in
the working tree.

### What the 24 dirty entries actually are

None is under `broker/` or on the run's path.

- **5 regenerated binaries** — `SUBMISSION_2026/TAE/figures/fig{0,1,2,3}*.pdf` and
  `paper/manuscript.docx`, rebuilt by a verification step that ran a figure generator. Content
  unchanged; PDFs embed build timestamps.
- **2 files under `ICLR2027/submission/`** — the manuscript and a check report, **being edited by
  another agent while this ran**.
- **10 under `examples/multi_agent/flood/`** — Paper 3, a different workstream.
- `.playwright-mcp/`, `examples/reservoir_control/results_ops_e4b/`, and this sweep's own report.

### Three `examples/irrigation_abm/` files did change, and none is on the path

`experiments/firstattempt_gov_2026-08.md` and `experiments/fql_nogov_2026-08.md` are design records.
`run_fql_baseline.py` is the fuzzy-Q baseline runner, which this experiment does not invoke — it uses
`run_experiment.py`, which shows zero drift above.

## Why the tree was not cleaned instead

It could not be, honestly. Making `git status` empty would have required committing another agent's
in-progress manuscript and a second workstream's uncommitted work. **Editing someone else's
mid-edit state to make a gate pass is worse than the gate misreporting**, and it is the kind of act
this project's own review rules exist to prevent.

## What this does and does not claim

**Claims:** the code and configuration this run consumed did not change between launch and finalize,
and the forthcoming `git_dirty: true` describes unrelated files in other directories.

**Does not claim:** that the run is reproducible in every other respect. It is not — `--memory-seed`
is recorded in no artefact (see the hazard sweep, item A3), and the launch banner is absent from the
captured log because the runner's `print()` output went to stdout while only stderr was redirected
(item A4). Those are separate defects and this file does not paper over them.

## For seeds 43–46

**This will repeat on all four**, for the same reason and with the same falsity. Decide before the
next launch, and the choice is not obvious:

1. **Fix the sampling point** — capture `git status` at launch rather than at finalize. Correct, and
   it is a `broker/` change, so it cannot happen while a run is live.
2. **Fix the gate's reading** — have `e3_run_integrity.py` state that `git_dirty` is sampled at
   finalize and therefore cannot certify launch state. Honest, but it weakens a gate, and weakening a
   gate to make a run pass is precisely the defect this paper is about. Not to be done quietly.
3. **Attest per run, as here.** Cheapest, no code change, and it leaves the gate's verdict standing
   with a documented rebuttal beside it.

**Option 3 for seeds 43–46; option 1 afterwards, when no run is live.** Option 2 only with the
author's explicit agreement, and never as a side effect of wanting a green gate.

---

*Measured with `git diff --name-only 50247de3..HEAD -- <path>` and `git status --porcelain -- <path>`
at 95.4% completion. No file was modified to produce this record.*
