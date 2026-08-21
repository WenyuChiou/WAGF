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
