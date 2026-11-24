# Analysis code behind the published numbers

This directory holds the code that turns WAGF audit traces into the quantities a
paper reports. It is here so a reader can see exactly how a number was computed
rather than take it on trust.

**What it does not include: the run outputs.** Every script below reads
`examples/*/results/`, which is gitignored and therefore absent from any clone.
The code is auditable from this repository; reproducing a specific published
figure needs the corpus as well, which is obtained from the authors. Be aware of
that limit before treating a green run here as a reproduction.

## `decomposition/` — six estimators and six independent verifiers

The headline governance metric is a rate conditioned on the agent's own reported
appraisal, and that appraisal is produced by the same model call as the action.
Conditioning on it is conditioning on a post-treatment variable, so the
conditional contrast does not identify a causal effect. This suite exists to say
what survives that objection and what does not.

Six estimators (`e1`–`e6`), each re-derived by a `_verify_*.py` script that
shares no code with it:

| | Estimand |
|---|---|
| `e1_total_effect.py` | total effect on the unconditional increase rate, denominator fixed by design |
| `e2_stratified.py` | the same rate standardised on exogenous precipitation × static water-right strata |
| `e3_decomposition.py` | Kitagawa/Oaxaca split into composition and behaviour |
| `e4_bounds.py` | worst-case bounds on the conditional estimand for a fixed population |
| `e5_year1.py` | the contrasts restricted to year 1, where both arms face a bit-identical world |
| `e6_flood_placebo.py` | the same machinery on a testbed where the theory rules rarely bind |

Start with:

```bash
python reproduction/decomposition/reproduce_published.py   # the headline, from raw files
python reproduction/decomposition/run_all.py               # all six plus their verifiers
```

Each estimator prints its own result and each `_verify_*.py` prints an
independent re-derivation, so the comparison a reader wants is in the two
outputs side by side rather than in a summary someone wrote afterwards. Several
of the estimators' own summary labels did not survive their verifier, which is
the reason the verifiers exist and print separately. `_loader.py` is the
canonical loader, and
its `ibr()` is the reference implementation of the published conditional
statistic. The `.csv` files are recorded outputs kept as reference values, not
inputs.

## `nature_water/` — the adopted display-item generators

Six scripts, one per display item that a paper actually uses. Run them from the
repository root, since two of them resolve data paths relative to the working
directory:

| Script | Display item |
|---|---|
| `gen_fig2_case1_irrigation.py` | irrigation case figure |
| `gen_fig3_case2_flood.py` | flood case figure |
| `gen_fig3_crossmodel.py` | cross-model EHE × appraisal-action scatter |
| `gen_sfig_crossmodel_trajectories.py` | cross-model adaptation trajectories |
| `gen_table1_decision_traces.py` | decision-trace table |
| `gen_tableS1_S6_crossmodel_unified.py` | cross-model metric tables |

`tests/test_nature_water_figure_helpers.py` exercises the pure helper functions
in the first two against synthetic frames, so their layout and labelling logic
is covered by CI even though the figures themselves cannot be regenerated
without the corpus.

Deliberately not copied here: the manuscript build and citation tooling, which
is submission machinery rather than analysis; two superseded generators that
write an adopted figure's filename with a different plot or overwrite a
hand-drawn figure; and two reference-only analyses that no display item uses.

## `history_rewrite/` — old commit ids in run records

The repository history was rewritten on 2026-11-21, so every commit id changed.
Run manifests and folder names written before then (for example
`JOH_strict_defaults_gemma3_4b_9c4ba160`) still name the old ids.
`history_rewrite/commit-map.txt` gives the new id for every old one, and
`history_rewrite/README.md` lists the paper's commits and the tag on each.
`tests/test_history_rewrite_map.py` checks that all 30 paper runs resolve.

## Metric definitions

Before quoting any number these scripts produce, read
`.claude/skills/llm-agent-audit-trace-analyzer/references/metrics_definitions.md`.
The same metric name means four different things depending on the denominator,
the action column and the aggregation level; that file records which combination
each published pair uses and what the alternatives give.

## Two different drift risks, which need different handling

**`nature_water/`** was copied from `paper/nature_water/scripts/`, which is
gitignored. The originals still sit in the author's working copy and nothing in
git can see them diverge. Treat the copies here as authoritative and fix them
here first.

**`decomposition/` and `evidence/`** came from a path that *is* tracked, just on
another branch, so this is a cross-branch fork of live history rather than a copy
out of an untracked folder. Ordinary tooling will not flag divergence between two
branches that never merge, and the source side was still being worked on when the
copy was taken. The copy point is recorded so that check is mechanical rather
than from memory:

```
source   p0-1-governance-instrumentation @ d49dadfb61d7
         SUBMISSION_2026/decomposition/                -> reproduction/decomposition/
         SUBMISSION_2026/evidence/exogeneity_check.py  -> reproduction/evidence/

check    git diff d49dadfb61d7:SUBMISSION_2026/decomposition                   main:reproduction/decomposition
```

Two files were changed rather than copied verbatim, and both changes belong here
rather than upstream. `_verify_e5_year1.py` had the repository root hardcoded to
one machine's absolute path while its five siblings resolved it from `__file__`,
which meant it silently re-derived its result from a different tree than the one
under test. And the prose in `decomposition/README.md` still named the old
directory in every command it told the reader to run. One file from the source
directory, a memo about what the analysis implied for a manuscript in progress,
was deliberately not copied: this directory carries the computation, not
commentary on a draft.

## Recipes, manifest checker and share step (the paper runs)

These three pieces describe and check the 30 paper runs (15 flood, 15 irrigation). They read run
folders that are not in git; the code is here, the folders come from the authors.

| What | Where | Use |
|---|---|---|
| Recipes | `recipes/flood.md`, `recipes/irrigation.md` (prose), `recipes/flood.yaml`, `recipes/irrigation.yaml` (machine-readable) | Every flag per set of simulations and seed, the arm-to-config map, the model digest, the Python version, the run tag, and what each run folder does and does not record. The flood run folders store no launch command; the irrigation ones do. |
| Manifest checker | `check_manifests.py` | `python reproduction/check_manifests.py --root <checkout that holds the run folders> --expect-missing-digest 5` prints one row per run: old commit to new commit, dirty flags, model digest present or not, config and data hashes against the tracked files at the run tag. It exits non-zero on any problem: a mismatch, or a hash, file or data field that is absent. Five of the paper runs carry only a short model id; `--expect-missing-digest 5` accepts exactly that count. A prompt hash absent from the manifest is never a problem (none of the paper manifests records one). It reads only. |
| Share step | `share_allowlist.txt`, `check_share.py` | `python reproduction/check_share.py --stage <dest> <run folder>` copies the allowlisted files with absolute paths blanked, then scans the copy for drive letters, network and user-folder paths (also URL-encoded), e-mail addresses and literal keys. It never follows a link, refuses a target that already exists or overlaps a run folder, and reports a file it could not parse or read instead of passing it. It prints file paths, field names and counts, never the matched text. |

`tests/test_repro_kit.py` checks all three on synthetic fixtures. With `WAGF_RESULTS_ROOT` set to the
checkout that holds the run folders it also checks the recipes and the checker against the real ones.
A rerun of the irrigation runs needs the CRSS data (`ref/CRSS_DB`; see `DATA.md`); the listed run artifacts do not include it. See the recipe.

## What the tests check

[`TESTS.md`](TESTS.md) says which claims CI checks on every push, which only the author's local run
with the CRSS data checks (with its date, commit and result), and which no test checks: CI runs
Python 3.10-3.12 while the paper ran on 3.14.0, the irrigation golden comparison skips on CI, and the
workers test is a 3-year scripted mock, not a 42-year live run.

## Frozen-case guard (before a merge that touches `broker/`)

A change to `broker/` for a new feature merges only if the guard shows the paper's frozen cases still behave the same. The guard runs each case on a mock LLM whose answer is a pure function of the prompt text (sha256). It states appraisal labels and takes the action from the prompt's own menu, so a changed rule threshold or a changed prompt line changes the run. The stock `--model mock` cannot do this (first option, no labels). Each arm runs as its own subprocess.

| Case | Arms | Size | Runs on |
|---|---|---|---|
| Flood single agent (`tests/test_frozen_guard_flood.py`) | without rules, with rules, with rules and silent retries (the three arms of `recipes/flood.yaml`) | 12 agents, 4 years (floods in years 3 and 4), seed 42, workers 1 | CI, in the existing `tests/` step; about 10 s |
| Multi-agent flood (`tests/test_frozen_guard_multi_agent.py`) | the frozen config `ma_agent_types.yaml`, gossip off | 8 synthetic households (`--mode random`, no survey file) plus the two institutions, 4 years, floods in years 2 and 3, seed 42 | CI, same step; about 5 s |
| Irrigation (`examples/irrigation_abm/tests/test_frozen_guard_irrigation.py`) | without rules, with the use limit only, with rules (`recipes/irrigation.yaml`) | 78 farmers, 2 years, seed 42, workers 1 | **manual row**; skips on CI (needs CRSS data); about 25 s |

**What is compared, per arm, against `reproduction/frozen_guard/fixtures/<case>/<arm>/`:** the step prompt of every agent and year (sha256, plus the full text of a few prompts so a diff reads), and the ordered hash of every retry and reflection prompt; the governance audit CSV (timestamps, timing columns and set order normalised with `broker/tools/compare_audit_csv.py`; a cell over 100 characters kept as a hash); the executed action per agent and year; the simulation state (`simulation_log.csv`; for multi-agent the household state at decision time). Numbers are compared to a relative 1e-8 (absolute 1e-9), except that two integers must match exactly; everything else exactly. The strict arms must reject, retry and fall to the default at least once (flood, irrigation) or reject and retry (multi-agent); the tests assert it, so a mock change that stops reaching those paths fails.

**A pass means** the covered fixtures matched, on the machine that ran it. It does not mean every paper path is unchanged, and it says nothing about a real model, other seeds, the 42-year or 10-year runs, gossip, or the mixed-population and influencer configs.

**Multi-agent limit:** two identical runs list equal-scored memories in a different order from year 4 on, so the guard compares the `RELEVANT MEMORIES` block as a set (and the mock sees it sorted); every other prompt byte is compared as it is. With gossip on, the case itself differs between identical runs, so that arm is not covered.

**Fixtures** change only through `python reproduction/frozen_guard/regenerate.py` (reports what differs, writes nothing) and `... --update` (writes). The tests never write. Read the printed differences before committing an update: a changed fixture means the case now behaves differently from the frozen one.

**Manual irrigation row (run before each merge that touches `broker/`).** Copy the CRSS bundle into the checkout (a copy, not a link): `ref/CRSS_DB` from the checkout that holds it (gitignored). Then

```bash
python -m pytest examples/irrigation_abm/tests/test_frozen_guard_irrigation.py --timeout=900 -p no:cacheprovider
```

and put the pass or fail line in the merge note. The same command with `tests/test_frozen_guard_flood.py tests/test_frozen_guard_multi_agent.py` runs the two CI rows locally.
