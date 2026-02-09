# WRR v6 Results Table Design (Independent Reviewer Round 3)

## Scope

Goal: use minimal metrics/tables to demonstrate two claims for WAGF flood case.
1. Reduce irrational/invalid decisions.
2. Preserve population-level behavioral diversity.

Data sources:
- `docs/wrr_metrics_all_models_v6.csv`
- `docs/wrr_metrics_group_summary_v6.csv`
- `docs/wrr_metrics_vs_groupA_v6.csv`

## Reviewer-Style Conclusions (Round 3)

1. Keep **rationality** and **identity/feasibility** separated.
- Rationality deviation: `R_R` (thinking-rule).
- Feasibility/identity violation: `R_H` (identity-rule / hard-constraint mismatch).
- Do not collapse them into one "hallucination" metric.

2. Diversity claim should use **effective diversity** not raw entropy only.
- Report both `H_norm_k4` and `EHE_k4`.
- `EHE_k4 = H_norm_k4 * (1 - R_H)` ties diversity to feasibility quality.

3. Retry/intervention is workload, not prevalence.
- `retry_rows` / `retry_sum` show governance effort.
- They must not be interpreted as number of violating agents.

## WRR Technical Note: Recommended Main Table

Use one compact table in main text (`Table 1`) with group means:

Columns:
- `Group`
- `R_H` (mean)
- `R_R` (mean)
- `Rationality pass = 1 - R_R`
- `H_norm_k4`
- `EHE_k4`
- `%Δ EHE vs Group A`
- `retry_rows` (mean)
- `retry_sum` (mean)

Current values (Run_1 snapshot):

| Group | R_H | R_R | Rationality pass | H_norm_k4 | EHE_k4 | %Δ EHE vs A | retry_rows | retry_sum |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Group_A | 0.4253 | 0.0944 | 0.9056 | 0.5832 | 0.3671 | baseline | 0.00 | 0.00 |
| Group_B | 0.0002 | 0.0024 | 0.9976 | 0.6623 | 0.6621 | +80.4% | 82.83 | 114.67 |
| Group_C | 0.0000 | 0.0041 | 0.9959 | 0.6563 | 0.6563 | +78.8% | 48.50 | 67.17 |

Computation note:
- `%Δ EHE vs A = (EHE_group - EHE_A) / EHE_A * 100` using group means.

## Secondary Table (SI): Model-Level Delta vs Group A

Use SI (`Table S1`) for robustness across models.

Columns:
- `model`
- `group` (`B` or `C`)
- `R_H`
- `R_R`
- `EHE_k4`
- `% reduction R_H vs A`
- `% reduction R_R vs A`
- `% gain EHE vs A`

Source file already prepared:
- `docs/wrr_metrics_vs_groupA_v6.csv`

This supports claims like:
- Mean `% reduction R_H vs A`: B `~99.96%`, C `100%`.
- Mean `% gain EHE vs A`: B `~180.4%`, C `~170.5%`.

## Figure Budget (3 figures max)

Recommended packing:
1. Fig 1: framework architecture (already exists).
2. Fig 2: rationality/feasibility panel (`R_H`, `R_R`, pass) by group.
3. Fig 3: diversity panel (`H_norm_k4`, `EHE_k4`) by group.

If one figure must be dropped, keep Fig 2 and Fig 3; move architecture to SI.

## Calculation Mapping (column-level)

From `simulation_log.csv` to metrics:
- `R_H = n_id_violation / n_active`
- `R_R = n_think_violation / n_active`
- `rationality_pass = 1 - R_R`
- `H_norm_k4`: normalized Shannon entropy on 4-action set (`both -> elevation` merged)
- `EHE_k4 = H_norm_k4 * (1 - R_H)`
- `retry_rows`: count of rows with `retry_count > 0`
- `retry_sum`: sum of `retry_count`

Detailed definitions remain in:
- `docs/wrr-metric-calculation-spec-v6.md`

## Claim Strength and Next Requirement

What current Run_1 can support:
- Strong directional evidence that governance reduces invalid/irrational decisions while keeping high effective diversity.

What reviewers will still ask:
- Variability across seeds/runs.

Minimum next step before submission claim hardening:
- Run the same matrix for Run_2/Run_3 (predefined seeds), then report mean +/- SD (or median/IQR) by group.
