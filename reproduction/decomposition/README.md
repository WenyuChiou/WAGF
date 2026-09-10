# `reproduction/decomposition/` — how much of the published −23.0 pp survives?

The published Nature Water irrigation headline (IBR governed **36.05 %** vs no-validator
**59.07 %**, gap **−23.02 pp**) is a rate **conditional on `wsa_label ∈ {H, VH}`** — a
self-report emitted by the same LLM call that emits the action, and demonstrably shifted by
governance. The two arms' denominators are therefore different populations of decisions.
Every script here exists to answer one question: *how much of that gap survives estimators
that do not condition on the post-treatment self-report, and what is honestly not identified?*

Sign convention used everywhere in this directory: **`gap = governed − ungoverned`**.
A **negative** gap means governance **lowered** the rate — the direction the paper claims as
the governance benefit. (The paper quotes the same magnitude flipped, as "+23.0 pp
improvement"; that flip is cosmetic and no script here uses it.)

## One command

Run from the **repo root**:

```
python reproduction/decomposition/run_all.py
```

Runs all 17 scripts in dependency order, streams their output, prints a PASS/FAIL summary,
and exits non-zero if any sub-script fails. Options: `--core` (exogeneity + e1..e6 only),
`--list` (print the plan, run nothing).

Full sweep as of 2026-09-07 (post quarantine of the defective ministral-3:8b ungoverned
seed44 backfill): **17/17 PASS, ~86 s total, no GPU, no network.**

## Files

| file | what it computes | run |
|---|---|---|
| `run_all.py` | harness only — executes everything below in order, aggregates failures | `python reproduction/decomposition/run_all.py` |
| `_loader.py` | canonical corpus loader (paths, arms, seeds, IBR/increase definitions). Imported by the estimators so they all count the corpus identically; run directly for a self-test | `python .../_loader.py` |
| `seed_inventory.py` | which seeds exist per model cell, which cells are arm-balanced, headline rates per cell; ministral-3:8b is unbalanced again as of the 2026-09-07 quarantine of its defective seed44 backfill (governed 42/43/44, ungoverned 42/43) | `python .../seed_inventory.py [--csv out.csv]` |
| `reproduce_published.py` | reproduces the published 36.05 / 59.07 conditional headline from the raw CSVs, per seed, without tuning the definition | `python .../reproduce_published.py` |
| `linkage_check.py` | is `yearly_decision` really the executed action? 1:1 linkage between `simulation_log.csv` and the governance audit; proposed vs final; rejection/fallback shares | `python .../linkage_check.py` |
| `../evidence/exogeneity_check.py` | **Phase 1A** — which environment columns are treatment-invariant, hence legal to condition on. Must run before e2/e3/e4. Lives in `evidence/` and writes its CSVs there | `python reproduction/evidence/exogeneity_check.py` |
| `e1_total_effect.py` | **e1** — the unconditional (total) effect of governance on the increase rate: no conditioning on any post-treatment variable | `python .../e1_total_effect.py` |
| `e2_stratified.py` | **e2** — increase rate directly standardized over pre-treatment environment strata | `python .../e2_stratified.py` |
| `e3_decomposition.py` | **e3** — Kitagawa / Oaxaca-Blinder split of the published conditional gap into behaviour vs composition components | `python .../e3_decomposition.py` |
| `e4_bounds.py` | **e4** — worst-case partial-identification bounds on the published conditional gap | `python .../e4_bounds.py` |
| `e5_year1.py` | **e5** — year-1 clean-slate estimator, before the coupled reservoir can carry treatment forward | `python .../e5_year1.py` |
| `e6_flood_placebo.py` | **e6** — flood negative control, where the theory rules almost never bind | `python .../e6_flood_placebo.py [--csv out.csv]` |
| `_verify_e1..e6_*.py` | six **independent adversarial re-derivations**, one per estimator: pandas/scipy, no import of `_loader`, deliberately different algebraic route. Agreement between two independent implementations is the evidence | `python .../_verify_eN_*.py` |

### Generated outputs (all written inside this directory)

| file | written by |
|---|---|
| `seed_inventory.csv` | `seed_inventory.py --csv` |
| `e2_stratified_strata.csv` | `e2_stratified.py` |
| `e3_decomposition.csv` | `e3_decomposition.py` |
| `e5_year1_trajectory.csv` | `e5_year1.py` |
| `e6_flood_placebo.csv` | `e6_flood_placebo.py` |
| `../evidence/exogeneity_by_column.csv`, `..._by_column_year.csv`, `..._join_report.csv` | `exogeneity_check.py` (into its own directory) |

## Ground rules these scripts follow

- Read-only against `examples/` — the frozen published experiments are never modified.
- No script writes outside `reproduction/` (verified by mtime sweep after a full run).
- Unit of inference is the **seed**, n = 5 → paired t-test, df = 4. Per-seed values are always
  printed, never a pooled-only number.
- ministral-3:8b is UNBALANCED again as of the 2026-09-07 quarantine of its defective
  ungoverned seed44 backfill (governed 42/43/44 vs ungoverned 42/43) and is excluded from
  every paired contrast, reported separately, by the data-driven balance logic — no code
  change was needed to make this happen. Between the 2026-08 backfill and the 2026-09-07
  quarantine it was briefly treated as balanced (3 paired seeds); pooling it in moved the
  unconditional cross-model mean gap from −11.39 pp (4 cells, the current and correct
  figure) to −4.68 pp (5 cells) purely because it is the only sign-flipping cell
  (+22.17 pp) — exactly why it is not pooled without a clean rerun (see Provenance below).
- Nothing is repaired to make it pass: a missing run raises, a divergence is reported.

## Provenance: the ministral-3:8b seed44 backfill

`ungoverned_v21_42yr_ministral3_8b_seed44` ran 2026-08-03T14:38:47 at
`git_commit=10e190cf1f3805e2869e91b52d8c178a01b0f5f3` with `git_dirty: true`, carrying the
full ~20-field `reproducibility_manifest.json` schema (model digest, quantization,
`config_hash`, `run_integrity` block, etc.). Its arm-mates `ungoverned_v21_42yr_ministral3_8b_seed42`
(manifest file dated 2026-03-21) and `..._seed43` (2026-03-22) predate that schema and carry
only 5 fields, with no `git_commit` recorded at all. This pools two different code states into
one model cell, which is the exact situation this project's standing rule says to never do
silently (CLAUDE.md: "never pool across commits without flagging") — flagged here rather than
fixed, because the runs cannot be re-executed at a matched commit without the original GPU
batch. The check that matters is whether the fields the two schemas share, and that govern
behaviour, actually agree: `governance_profile` = `"disabled"` in both; `model` =
`"ministral-3:8b"` in both; `num_years` = `42` in both; `agent_types_config` resolves to the
same absolute path in both, and neither schema stores a content hash of that file, so the
check was extended to git history — `examples/irrigation_abm/config/agent_types.yaml` changed
exactly once between the seed42/43 runs (2026-03) and the seed44 backfill (2026-08-03,
commit `10e190cf`): commit `8c6e48c4` (2026-05-24), a single 10-line additive hunk (`template_vars:`,
a prompt-variable-source declaration) with zero deletions and no change to any governance,
threshold, or magnitude field.

Comparing the produced runs rather than only the manifests surfaced a large, structural
difference, not just a smaller one on the record: mean `memory` content is 340 chars/row
in the backfilled run against 784–1013 in the five arm-mates (identical 22-column schema,
3276 rows each), and the literal broken placeholder `Consolidated Reflection: {`
(immediately followed by a raw year-by-year history dump instead of the normal generated
prose) covers 3106/3198 = 97.1% of year-2-onward rows in the backfilled run, against
20.4%–30.6% in the five arm-mates — there it is a transient early-warm-up artifact
concentrated in each agent's first 2–3 years, not a persistent failure across the whole
42-year run. `reflection_log.jsonl`'s own `summary` field shows the same collapse: median
1 char in the backfilled run vs 232–253 chars in the arm-mates. The shared manifest fields
still match and the one `agent_types.yaml` change is still additive, but that audit never
covered `broker/` memory-engine changes in the same window, and `git_dirty: true` means
the code that actually produced this run cannot be confirmed either way.

**Decision (user, 2026-09-07): QUARANTINE rather than pool.** The run is moved to
`examples/irrigation_abm/results/_QUARANTINE_reflection_truncated_2026-09-07/` (see that
folder's `README.txt` for the full record, including the note that an earlier pass's
"85.5% / 194.6 chars" figures did not reproduce from disk and have been superseded by the
numbers above). It is excluded from every table here — `e2_stratified_strata.csv`,
`e3_decomposition.csv`, `seed_inventory.py`, `run_all.py` — by the same data-driven
balance logic that excludes any other unbalanced cell (`L.balanced()` / `L.paired_seeds()`
in `_loader.py`); a quarantined run directory is simply absent from `RESULTS`, so no code
change was needed. `e3_decomposition.csv` accordingly contains zero ministral-3:8b rows
again (PART F reports unbalanced cells to the console only, never into the CSV), and
`e2_stratified_strata.csv` is back to byte-identical with its pre-2026-08 content. A clean
rerun of the ungoverned seed44 arm at a pinned (non-dirty) commit can lift the quarantine.

Evidence — mean `memory` column length, all six ministral-3:8b runs (22 columns, 3276 rows
each, `simulation_log.csv`), as measured 2026-09-07:

| run | arm | seed | rows | cols | mean memory chars/row |
|---|---|---|---:|---:|---:|
| `production_v21_42yr_ministral3_8b_seed42` | governed | 42 | 3276 | 22 | 1013.0 |
| `production_v21_42yr_ministral3_8b_seed43` | governed | 43 | 3276 | 22 | 926.3 |
| `production_v21_42yr_ministral3_8b_seed44` | governed | 44 | 3276 | 22 | 935.4 |
| `ungoverned_v21_42yr_ministral3_8b_seed42` | ungoverned | 42 | 3276 | 22 | 784.1 |
| `ungoverned_v21_42yr_ministral3_8b_seed43` | ungoverned | 43 | 3276 | 22 | 836.1 |
| `ungoverned_v21_42yr_ministral3_8b_seed44` | **QUARANTINED** (backfill) | 44 | 3276 | 22 | **339.8** |
