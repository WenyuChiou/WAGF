# WRR v6 Metric Calculation Spec (Column-Level)

This document defines exactly how each reported metric is computed from `simulation_log.csv`.

## Input File Pattern

- `examples/single_agent/results/JOH_FINAL/<model>/<group>/Run_<k>/simulation_log.csv`
- Default runs included by script: `Run_1, Run_2, Run_3` (if file exists)
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
- Current rules used in v6 script:
  - Group A (ungoverned):
    - intent action is parsed from `raw_llm_decision` (not cumulative `decision` label).
    - Re-elevation violation: `previous_elevated=True` and intent action in `{elevation, both}`.
  - Group B/C (governed):
    - structured action from `yearly_decision`.
    - Re-elevation violation: `previous_elevated=True` and action in `{elevation, both}`.

Columns used:
- `elevated`
- Group A intent action: `raw_llm_decision`
- Group B/C action: `yearly_decision`

Important implementation note:
- In Group A logs, `decision` is often cumulative/state-like and can overcount physical violations if treated as yearly intent.

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

Current manuscript lock:
- `R_R` follows the three threat-action thinking rules above (for comparability across runs/versions).
- `coping_appraisal` (`CP_LABEL`) is parsed in the metrics script for construct auditing, but is not added as an extra fourth RR rule in v6 tables.

Column used:
- `threat_appraisal`
- `coping_appraisal` (parsed for audit context; not part of RR numerator in v6)
- Group A action intent source for rule checks: `raw_llm_decision` (fallback to parsed `decision` only if raw field is missing)
- Group B/C action source for rule checks: `yearly_decision`

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
- One row per `<model, group, run>`.

2. `docs/wrr_metrics_group_summary_v6.csv`
- Mean values aggregated by group (`Group_A/B/C`) across all available runs.

3. `docs/wrr_metrics_vs_groupA_v6.csv`
- Per `<model, run>`, compares Group B/C against Group A:
  - `% reduction R_H vs A`
  - `% reduction R_R vs A`
  - `% gain EHE_k4 vs A`

4. `docs/wrr_metrics_completion_v6.csv`
- Completion matrix for all expected `<model, group, run>` cells with `has_simulation_log` flag.
