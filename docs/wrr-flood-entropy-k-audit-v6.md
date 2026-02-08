# Flood Entropy K Audit (v6)

## Question

In flood results, should normalized entropy use `log2(4)` or `log2(5)`?

## What We Checked

### 1) Definitions in `paper/flood`

- `paper/flood/analysis/master_report.py:12` uses `H_norm = H / log2(4)`.
- `paper/flood/analysis/master_report.py:21` sets `h_max = np.log2(4)`.
- `paper/flood/docs/WRR_technical_notes_flood_v2.md:43` states `K = 4 decision categories`.

But:

- `paper/flood/scripts/corrected_entropy_analysis.py:13` states `k=5 actions`.
- `paper/flood/scripts/corrected_entropy_analysis.py:54` sets `K = 5`.

So the repository currently contains a 4-vs-5 inconsistency.

### 2) Numeric alignment against v5 reference values

We compared `V5_REFERENCE` in `paper/flood/verification/verify_flood_metrics.py` with
our recomputed outputs in `docs/wrr_metrics_all_models_v6.csv`:

- `H_norm_k4` matches v5 `H_norm` for 17/18 model-group rows exactly (rounding precision).
- The remaining row differs by 0.006 (small processing/path difference).
- `H_norm_k5` is systematically offset and does not match v5 paper numbers.

## Interpretation (Subagent-style consensus)

### Methods subagent

If the manuscript baseline numbers are those in `v5_data_update.md`/`V5_REFERENCE`,
then entropy normalization is effectively `K=4` in the published-result lineage.

### Statistics subagent

Mixing `K=4` and `K=5` within one paper is a specification error, not just style.
It changes scale and comparability across tables/figures.

### Reviewer subagent

For WRR review safety, lock one definition globally and state it once in Methods.
Given current manuscript numbers, use `log2(4)`.

## Recommended Decision

Use `log2(4)` for flood main-text metrics (`H_norm`, `EHE`) and regenerate any figures
or SI tables currently produced by `K=5` scripts before final submission freeze.

## Action Items

1. Keep manuscript formulas at `H_norm = H / log2(4)`.
2. Treat `scripts/wrr_compute_metrics_v6.py` outputs (`H_norm_k4`, `EHE_k4`) as source-of-truth for v6 write-up.
3. If any figure still depends on `paper/flood/scripts/corrected_entropy_analysis.py`, either:
   - switch that script to `K=4`, or
   - explicitly mark it as legacy/non-authoritative and do not cite its values in main text.
