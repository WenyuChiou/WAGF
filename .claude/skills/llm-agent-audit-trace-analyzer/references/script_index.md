# Script index — production analyses to call (do NOT reimplement)

When a user request maps to one of these, shell out to the script
directly rather than reimplementing the formula.

## Cross-model paired analysis (flood)

```bash
python examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py
```

Reads `JOH_FINAL_v2/` and `JOH_ABLATION_DISABLED_v2/` (Gemma-4) plus
`JOH_FINAL/` and `JOH_ABLATION_DISABLED/` (other 6 models). Emits the
9-model governed-vs-disabled table that backs SI Tables 5/6.

Key functions exposed (importable):
- `compute_ibr_components(work_df) -> (ibr_fraction, components_dict)`
- `summarize_pooled_metrics(df) -> dict`
- `normalize_action(s)`, `normalize_tp(s)` — vocabulary aliasing.

## Cross-model figure (Supp Fig 1)

```bash
python reproduction/nature_water/gen_fig3_crossmodel.py
```

Reads the cross-model flood runs under `examples/single_agent/results/`
(not in a clone). It is a figure script; for a per-model median and range
across seeds, use `process_llm_csv` from
`examples/single_agent/analysis/compute_flood_metrics.py`.

## Temporal diagnostics (SI Table 7)

```bash
python examples/single_agent/analysis/compute_temporal_diagnostics.py \
    --gemma4-pipeline v2 \
    --output-csv .ai/temporal_diagnostic_v2.csv \
    --output-md  .ai/temporal_diagnostic_v2.md
```

Walks all 9 model dirs, applies M1/M2/M3 rules via the framework
adapter at
`broker/components/governance/temporal_rules/`, emits per-run trigger
counts.

## Retry compliance (SI Table 8)

```bash
python examples/single_agent/analysis/compute_retry_compliance.py
```

Emits `.ai/retry_compliance_gemma4_v2_*.md` with Pattern A/B/C counts
across the Gemma-4 family governed runs.

## Irrigation IBR / governance comparison

```bash
python reproduction/decomposition/reproduce_published.py
```

Prints the published irrigation pair per seed under every candidate definition
(conditional and unconditional denominator, last-proposal and executed action),
plus the appraisal-share shift between arms. Import
`reproduction/decomposition/_loader.py::ibr()` to compute it on one run.

A script named `compute_ibr.py` in `examples/irrigation_abm/analysis/` used to be the
entry point here. It was deleted 2026-08-20: every results directory it pointed at was a v20
path that no longer exists, so it had not been runnable for some time. Four
sibling scripts went with it for the same reason — `ensemble_analysis.py`,
`governed_vs_ungoverned.py`, `nw_comprehensive_analysis.py`,
`ibr_wsa_aca_decomposition.py`. They are recoverable from git history if a v20
corpus is ever restored.

## Audit-CSV sentinel sweep

```python
from broker.components.analytics.audit import detect_audit_sentinels_in_csv
warnings = detect_audit_sentinels_in_csv(
    "examples/.../household_governance_audit.csv"
)
for w in warnings:
    print(w)
```

## Bootstrap CI / Cohen's d / Shannon entropy

Importable functions in
`examples/irrigation_abm/analysis/nw_bootstrap_ci.py`:

- `shannon_entropy(probs) -> float`
- `cohens_d(a, b) -> float`
- `bootstrap_ci(values, n_iter=10000, ci=0.95) -> (lo, hi)`

## Comparison: V1 vs V2 (Gemma-4 prompt-regime audit)

```bash
python examples/single_agent/analysis/compare_gemma4_v1_vs_v2.py
```

Reads both V1 (archived contaminated) and V2 (canonical) paths, emits
side-by-side ΔIBR with prompt-sanity check on each trace's `input`
field.

## Reproducibility manifest collector

```python
from broker.core.experiment_runner import _collect_reproducibility_metadata
manifest = _collect_reproducibility_metadata(...)
```

Used by all run scripts at startup. Returns a dict matching the
schema at `../../abm-reproducibility-checker/references/manifest_schema.md`.

## What the skill should NEVER do

- Reimplement IBR. Use `reproduction/decomposition/_loader.py::ibr()` for
  the published conditional statistic, or `compute_ibr_components` for the
  flood R1/R3/R4/R5 component counts — note that the latter divides by the
  all-rows denominator and does NOT give the published pair. Which denominator
  applies is set out in `references/metrics_definitions.md`; state it whenever
  you report a number.
- Reimplement EHE. Always use `shannon_entropy`.
- Pool data without checking the manifests' `git_commit` for
  consistency (delegate that to `abm-reproducibility-checker`).
- Rebuild Supplementary Figure 1 from an older `gen_sfig_forest.py` (no longer
  in the repo): it drew a different plot on the superseded unconditional
  denominator. Use `reproduction/nature_water/gen_fig3_crossmodel.py`.
