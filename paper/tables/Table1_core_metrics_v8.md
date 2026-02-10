# Table 1 (v8) Core Flood Metrics by Model and Group

| model | group | n_runs | R_H_pct | R_R_pct | H_norm_k4 | EHE_k4 |
|---|---|---|---|---|---|---|
| gemma3_4b | Group_A | 2 | 0.000 | 1.051 | 0.584 | 0.584 |
| gemma3_4b | Group_B | 2 | 0.000 | 0.411 | 0.756 | 0.756 |
| gemma3_4b | Group_C | 2 | 0.000 | 1.281 | 0.778 | 0.778 |
| gemma3_12b | Group_A | 2 | 0.000 | 0.511 | 0.486 | 0.486 |
| gemma3_12b | Group_B | 2 | 0.000 | 0.062 | 0.502 | 0.502 |
| gemma3_12b | Group_C | 2 | 0.000 | 0.051 | 0.422 | 0.422 |
| gemma3_27b | Group_A | 2 | 0.000 | 12.000 | 0.645 | 0.645 |
| gemma3_27b | Group_B | 2 | 0.000 | 0.000 | 0.623 | 0.623 |
| gemma3_27b | Group_C | 2 | 0.000 | 0.000 | 0.670 | 0.670 |
| ministral3_3b | Group_A | 2 | 0.000 | 8.380 | 0.445 | 0.445 |
| ministral3_3b | Group_B | 2 | 0.073 | 0.506 | 0.736 | 0.735 |
| ministral3_3b | Group_C | 2 | 0.000 | 0.065 | 0.682 | 0.682 |
| ministral3_8b | Group_A | 2 | 0.000 | 1.107 | 0.746 | 0.746 |
| ministral3_8b | Group_B | 2 | 0.000 | 0.000 | 0.622 | 0.622 |
| ministral3_8b | Group_C | 2 | 0.000 | 0.000 | 0.639 | 0.639 |
| ministral3_14b | Group_A | 2 | 0.000 | 1.806 | 0.488 | 0.488 |
| ministral3_14b | Group_B | 2 | 0.000 | 0.000 | 0.706 | 0.706 |
| ministral3_14b | Group_C | 2 | 0.000 | 0.000 | 0.699 | 0.699 |

Notes:
- Values are means across available runs in `docs/wrr_metrics_all_models_v6.csv`.
- This refresh uses `Run_1` and `Run_2` only (Run_3 intentionally excluded while running).
- `R_H_pct` and `R_R_pct` are percentages (0-100).
- `H_norm_k4` and `EHE_k4` are /4 diversity metrics.
