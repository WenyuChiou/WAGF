# Script index — production analyses to call (do NOT reimplement)

When a user request maps to one of these, shell out to the script
directly rather than reimplementing the formula.

## Cross-model paired analysis (flood)

```bash
python examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py
```

Reads `JOH_FINAL_v2/` and `JOH_ABLATION_DISABLED_v2/` (Gemma-4) plus
`JOH_FINAL/` and `JOH_ABLATION_DISABLED/` (other 6 models). Emits the
9-model paired-t table that backs SI Tables 5/6.

Key functions exposed (importable):
- `compute_ibr_components(work_df) -> (ibr_fraction, components_dict)`
- `summarize_pooled_metrics(df) -> dict`
- `normalize_action(s)`, `normalize_tp(s)` — vocabulary aliasing.

## Forest plot (SFig 1)

```bash
python paper/nature_water/scripts/gen_sfig_forest.py
```

Produces `paper/nature_water/figures/SFig_crossmodel_ehe_ibr.{png,pdf}`.
Routes Gemma-4 to V2 paths automatically; uses the R1+R3+R4 IBR.

Importable function: `paired_stats(gov_ibrs, dis_ibrs)`.

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
python examples/irrigation_abm/analysis/compute_ibr.py \
    --results-dir <run_dir>
python examples/irrigation_abm/analysis/compute_ibr.py \
    --results-dir <governed_run_dir> \
    --compare-ungoverned <ungoverned_run_dir>
```

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
schema at `references/manifest_schema.md`.

## What the skill should NEVER do

- Reimplement IBR. Always use `compute_ibr_components` or
  `compute_ibr.py`.
- Reimplement EHE. Always use `shannon_entropy`.
- Pool data without checking the manifests' `git_commit` for
  consistency (delegate that to `abm-reproducibility-checker`).
- Generate a forest plot from scratch. Use `gen_sfig_forest.py`.
