# What the tests check, and what they do not

This note says which parts of the paper's claims the automated tests check on
every push, which they check only on the author's machine, and which no test
checks. The paper's Methods and Data availability sections point here.

## Where the tests run

| | CI (`.github/workflows/test.yml`) | The paper runs |
|---|---|---|
| Python | 3.10, 3.11, 3.12 on Ubuntu | 3.14.0 on Windows (all 30 manifests) |
| numpy | whatever pip resolves: 2.2.6, 2.4.6 and 2.5.5 on the three rows of run 45018709621 (2026-11-22) | not recorded in the LLM-run manifests; the FQL reference runs record 2.4.2 |
| LLM | none; tests marked `real_llm` are deselected and the rest use mocks | gemma3:4b through Ollama |
| CRSS data (`ref/CRSS_DB`) | absent (gitignored, see `DATA.md`) | present |

So CI never runs the Python version the paper ran on, never calls a real LLM,
and never sees the CRSS data.

## Tests that need the CRSS data

`examples/irrigation_abm/tests/conftest.py` marks every test that reads
`ref/CRSS_DB/CRSS_DB/` and skips it when the folder is absent. On a clone
without the data, the irrigation session gives 1,313 passed and 213 skipped
(local run at commit `1af3a48d` with the folder absent and `GITHUB_ACTIONS=true`
set); 209 of the 213 skip reasons name the CRSS data, and the other 4 name run
folders that are not in the repository, or a test kept only as history. CI
run 45018709621 on the same commit gives 1,312 passed and 214 skipped; the
extra skip is the golden comparison below.

The skipped tests include four that the paper relies on:

- `test_persona_claims_hold_for_cluster_means`: each comparison the irrigation
  personas state holds for the cluster means of the calibrated parameters.
- `test_workers_1_4_8_byte_identical`: see "Workers" below.
- `test_recorded_replay_regression`: a recorded run replays to the same result.
- the CRSS-based journal-resume tests (all of `test_llm_journal_resume.py`, and
  the tests in `test_workers_resume_integration.py` that use CRSS runs): a
  crashed run resumes to the same result.

Local run with the CRSS data, on the author's machine, in a fresh checkout:

| | |
|---|---|
| Date | 2026-11-22 |
| Commit | `1af3a48d0fec0bbd06734d5017e1130ac9f5af57` |
| Machine | Windows 11, Python 3.14.0, numpy 2.4.2, pandas 2.3.3 |
| Command | `python -m pytest examples/irrigation_abm/tests -ra --tb=short -k "not real_llm" -p no:cacheprovider --timeout=900 --durations=5` |
| Result | 1,521 passed, 5 skipped, 0 failed, in 476.94 s (pytest's `0:07:56`) |
| The 5 skips | run folders and a USBR workbook that a fresh checkout does not have, and one test kept only as history |

## The irrigation golden files

`test_fql_v3.py` compares a fresh FQL run against golden CSV files in
`examples/irrigation_abm/tests/fixtures/`, captured under numpy 2.4.2 (their
`.meta.json`). When the installed numpy differs, the test fails on a local
machine and skips on CI (`GITHUB_ACTIONS=true`), because numpy versions can
differ in the last digit. None of the three CI rows has numpy 2.4.2, so on CI
today the synthetic-input golden is skipped, not passed; the golden built from
the CRSS profiles already skips there for lack of the data. Both pass in the
local run above, because that machine has numpy 2.4.2.

## Workers

Both paper corpora ran with `--workers 4` (manifest `workers`), that is, four
agents' LLM calls in parallel within a year. What the tests show:

- Irrigation: `test_workers_1_4_8_byte_identical` runs the irrigation case for
  3 years with seed 42 and the CRSS profiles, at workers 1, 4 and 8, under the
  strict and feasibility-only rule settings, with a scripted mock that answers
  each prompt from a hash of the prompt text and sleeps a random 0 to 20 ms so
  threads finish in a scrambled order. The audit CSVs must be identical. It
  needs the CRSS data, so it runs only locally. In the run above it passed in
  22.4 s (strict) and 20.9 s (feasibility-only).
- Flood: `tests/test_parallel_determinism.py` checks, with stubbed agents, that
  parallel results come back in submission order. No test runs the flood case
  end to end at more than one worker count.

What this does not show: that a 42-year run with a live LLM gives the same
result at workers 4 as at workers 1. A live LLM through Ollama is not
repeatable to the byte even at one worker (the same seed and commit give
different replies), so the paper's claims rest on the spread over five seeds,
not on byte identity.

## What no test checks

- Real-LLM runs: no test calls Ollama on CI; the `real_llm` tests are
  deselected there.
- The paper's numbers: they come from the 30 run folders, which are not in the
  repository. `reproduction/check_manifests.py` checks the folders' manifests
  and the tests in `tests/test_repro_kit.py` that read them run only when
  `WAGF_RESULTS_ROOT` points at the folders, so they skip on CI.
- The flood runs' uncommitted changes: all 15 flood runs were launched from a
  tree with uncommitted changes that were not recorded (see
  `reproduction/recipes/flood.md`), so no test can check the exact code they
  ran.
