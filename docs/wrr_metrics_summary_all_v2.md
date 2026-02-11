# WRR Metrics Summary (All Indicators, Clean v2)

Data scope: flood case, Run_1 + Run_2 + Run_3 where available (43 model-group-run cells).
Coverage: 18 model-group cells total; 7 cells with n_runs=3, 11 cells with n_runs=2.

## A. Primary Outcome Indicators (decision-level)
Definition: executed-only indicators count governed decisions only when trace outcome is `APPROVED`.

| Group | n_cases | R_R_proposal | R_R_executed | R_H_proposal | R_H_executed | H_norm_k4_executed | EHE_k4_executed |
|---|---:|---:|---:|---:|---:|---:|---:|
| Group_A | 15 | 4.142% | 4.142% | 0.000% | 0.000% | 0.481 | 0.481 |
| Group_B | 14 | 0.227% | 0.000% | 0.010% | 0.000% | 0.639 | 0.639 |
| Group_C | 14 | 0.207% | 0.000% | 0.000% | 0.000% | 0.628 | 0.628 |

## B. Model-Level Effect Summary (A vs governed mean of B,C)
| Model | A RR(%) | Gov RR mean(%) | RR reduction(%) | A EHE | Gov EHE mean | EHE gain(%) |
|---|---:|---:|---:|---:|---:|---:|
| gemma3_12b | 0.545 | 0.000 | 100.0 | 0.471 | 0.451 | -4.2 |
| gemma3_27b | 11.733 | 0.000 | 100.0 | 0.462 | 0.647 | 40.0 |
| gemma3_4b | 0.901 | 0.000 | 100.0 | 0.337 | 0.735 | 118.1 |
| ministral3_14b | 1.806 | 0.000 | 100.0 | 0.667 | 0.701 | 5.1 |
| ministral3_3b | 8.380 | 0.000 | 100.0 | 0.458 | 0.686 | 49.9 |
| ministral3_8b | 1.107 | 0.000 | 100.0 | 0.574 | 0.624 | 8.7 |

## C. Governance Process Indicators (trace-level; B/C focus)
| Group | n_cells | n_rows_total | retry_positive_rate | mean_retry_count | approved_rate | retry_success_rate | rejected_rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Group_A | 2 | 1216 | 0.000% | 0.0000 | 100.000% | 0.000% | 0.000% |
| Group_B | 15 | 12410 | 6.785% | 0.0938 | 93.215% | 6.440% | 0.338% |
| Group_C | 14 | 12575 | 4.737% | 0.0624 | 95.263% | 4.481% | 0.207% |

## D. Indicator Definitions
- `R_R`: rationality-deviation rate (thinking-rule coherence contradiction / active decisions).
- `R_H`: feasibility-contradiction rate (identity/precondition contradiction / active decisions).
- `H_norm_k4`: normalized Shannon entropy over 4-action space.
- `EHE_k4`: effective behavioral entropy (`H_norm_k4 * (1 - R_H)`).
- `retry_positive_rate`: fraction of trace rows with `retry_count > 0`.
- `mean_retry_count`: average `retry_count` across trace rows.
- `approved_rate`, `retry_success_rate`, `rejected_rate`: outcome proportions from trace `outcome`.