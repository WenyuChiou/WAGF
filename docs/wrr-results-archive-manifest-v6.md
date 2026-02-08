# WRR v6 Results Archive Manifest

This manifest records the analysis inputs, scripts, and outputs used for the flood results section (rationality and diversity) in the WRR v6 workflow.

## Source Data

- Primary raw logs:
  - `examples/single_agent/results/JOH_FINAL/*/Group_*/Run_1/simulation_log.csv`

## Reproducible Script

- Metric computation script:
  - `scripts/wrr_compute_metrics_v6.py`

Run command:

```powershell
python scripts/wrr_compute_metrics_v6.py
```

Optional explicit paths:

```powershell
python scripts/wrr_compute_metrics_v6.py \
  --joh-final-dir examples/single_agent/results/JOH_FINAL \
  --out-all docs/wrr_metrics_all_models_v6.csv \
  --out-group docs/wrr_metrics_group_summary_v6.csv
```

## Output Tables

- Full model x group table (18 rows):
  - `docs/wrr_metrics_all_models_v6.csv`
- Group-level summary table:
  - `docs/wrr_metrics_group_summary_v6.csv`

## Writing/Presentation Plans

- Results focus draft:
  - `docs/wrr-results-rationality-diversity-v6.md`
- Section 2 method counting clarification:
  - `docs/wrr-ch2-review-plan-v6.md`
- Section 4 result focus lock:
  - `docs/wrr-ch4-review-plan-v6.md`

## Notes on Traceability

- `R_H` and `R_R` are computed at decision-level with denominator `n_active`.
- Intervention/retry frequencies are workload metrics and are not used as `R_H`/`R_R` numerators.
- Retry policy assumption documented for manuscript text: bounded retry up to 3 attempts, terminal action retained if exhausted.
