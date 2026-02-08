# WRR v6 Metric Calculation Spec (Column-Level)

This document defines exactly how each reported metric is computed from `simulation_log.csv`.

## Input File Pattern

- `examples/single_agent/results/JOH_FINAL/<model>/<group>/Run_1/simulation_log.csv`
- Groups:
  - `Group_A` (ungoverned format)
  - `Group_B`, `Group_C` (governed format)

## Core Unit and Denominator

### `n_active`

Decision-level denominator for `R_H` and `R_R`.

A row is counted into `n_active` only if:
1. Agent was **not relocated in previous year**.
2. Current row has a real action (not empty / relocated placeholder).

State tracking columns used:
- `agent_id`
- `year`
- `relocated`

Action existence columns used:
- Group A: `decision`
- Group B/C: `yearly_decision`

Excluded placeholders:
- Group A: `""`, `"Already relocated"`
- Group B/C: `""`, `"N/A"`, `"relocated"`

## Action Normalization

Canonical action labels used for entropy and rule checks:
- `do_nothing`
- `insurance`
- `elevation`
- `both`
- `relocate`

Mapping columns:
- Group A from `decision`
- Group B/C from `yearly_decision`

## Feasibility Metric

### `R_H = n_id / n_active`

- `n_id` = decision-level identity/feasibility violations.
- Current rule used in v6 script:
  - Re-elevation violation: previous `elevated=True` and action is `elevation` or `both`.

Columns used:
- `elevated`
- normalized action (`decision` or `yearly_decision`)

## Rationality Metric

### `R_R = n_think / n_active`

- `n_think` = decision-level thinking-rule deviations.
- Threat appraisal label source:
  - primary: explicit token in `threat_appraisal` (`VH`, `H`, `M`, `L`, `VL`)
  - fallback (free-text): keyword mapping to `H`/`L`/`M`

Rule checks (decision-level):
1. High threat inaction: `TA in {H, VH}` and action `do_nothing`
2. Low threat relocation: `TA in {L, VL}` and action `relocate`
3. Low threat costly structural adaptation: `TA in {L, VL}` and action in `{elevation, both}`

Column used:
- `threat_appraisal`

Derived:
- `rationality_pass = 1 - R_R`

## Diversity Metrics

### `H_norm_k5`

- Shannon entropy normalized by `log2(5)` over action set:
  - `{do_nothing, insurance, elevation, both, relocate}`

### `H_norm_k4`

- For `/4` reporting, merge `both -> elevation`, then normalize by `log2(4)` over:
  - `{do_nothing, insurance, elevation, relocate}`

## Effective Diversity

### `EHE_k5 = H_norm_k5 * (1 - R_H)`
### `EHE_k4 = H_norm_k4 * (1 - R_H)`

Interpretation:
- Raw diversity discounted by feasibility burden.

## Workload Metrics (Not Violation Denominators)

### `intervention_rows`

Count of rows where:
- `governance_intervention == True`

### `retry_rows`

Count of rows where:
- `retry_count > 0`

### `retry_sum`

Sum of numeric `retry_count` over all rows.

Important:
- These are governance workload/event-frequency indicators.
- They are not equal to unique violating decisions because one decision can trigger multiple retries.

## Output Tables

Produced by `scripts/wrr_compute_metrics_v6.py`:

1. `docs/wrr_metrics_all_models_v6.csv`
- One row per `<model, group>`.

2. `docs/wrr_metrics_group_summary_v6.csv`
- Mean values aggregated by group (`Group_A/B/C`).
