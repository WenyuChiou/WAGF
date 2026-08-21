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

Full sweep as of 2026-07-30: **17/17 PASS, ~55 s total, no GPU, no network.**

## Files

| file | what it computes | run |
|---|---|---|
| `run_all.py` | harness only — executes everything below in order, aggregates failures | `python reproduction/decomposition/run_all.py` |
| `_loader.py` | canonical corpus loader (paths, arms, seeds, IBR/increase definitions). Imported by the estimators so they all count the corpus identically; run directly for a self-test | `python .../_loader.py` |
| `seed_inventory.py` | which seeds exist per model cell, which cells are arm-balanced, headline rates per cell. Unbalanced cells (ministral-3:8b) flagged, never silently dropped | `python .../seed_inventory.py [--csv out.csv]` |
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
- ministral-3:8b has unbalanced arms (3 governed seeds vs 2 ungoverned) and is excluded from
  every paired contrast, reported separately.
- Nothing is repaired to make it pass: a missing run raises, a divergence is reported.
