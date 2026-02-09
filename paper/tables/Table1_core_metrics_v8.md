# Table 1 (v8) Core Flood Metrics by Model and Group

| model | group | n_runs | R_H_pct | R_R_pct | H_norm_k4 | EHE_k4 |
|---|---:|---:|---:|---:|---:|---:|
| gemma3_12b | Group_A | 2 | 0.000 | 0.511 | 0.486 | 0.486 |
| gemma3_12b | Group_B | 2 | 0.000 | 0.062 | 0.502 | 0.502 |
| gemma3_12b | Group_C | 2 | 0.000 | 0.051 | 0.422 | 0.422 |
| gemma3_27b | Group_A | 2 | 0.000 | 12.000 | 0.645 | 0.645 |
| gemma3_27b | Group_B | 1 | 0.000 | 0.000 | 0.629 | 0.629 |
| gemma3_27b | Group_C | 1 | 0.000 | 0.000 | 0.685 | 0.685 |
| gemma3_4b | Group_A | 2 | 0.000 | 1.051 | 0.584 | 0.584 |
| gemma3_4b | Group_B | 2 | 0.000 | 0.411 | 0.756 | 0.756 |
| gemma3_4b | Group_C | 2 | 0.000 | 1.281 | 0.778 | 0.778 |
| ministral3_14b | Group_A | 1 | 0.000 | 1.747 | 0.480 | 0.480 |
| ministral3_14b | Group_B | 1 | 0.000 | 0.000 | 0.695 | 0.695 |
| ministral3_14b | Group_C | 1 | 0.000 | 0.000 | 0.712 | 0.712 |
| ministral3_3b | Group_A | 1 | 0.000 | 10.091 | 0.435 | 0.435 |
| ministral3_3b | Group_B | 1 | 0.145 | 0.872 | 0.755 | 0.754 |
| ministral3_3b | Group_C | 1 | 0.000 | 0.131 | 0.640 | 0.640 |
| ministral3_8b | Group_A | 1 | 0.000 | 0.711 | 0.752 | 0.752 |
| ministral3_8b | Group_B | 1 | 0.000 | 0.000 | 0.627 | 0.627 |
| ministral3_8b | Group_C | 1 | 0.000 | 0.000 | 0.623 | 0.623 |

Notes:
- Values are means across available runs in `docs/wrr_metrics_all_models_v6.csv`.
- `R_H_pct` and `R_R_pct` are percentages (0-100).
- `H_norm_k4` and `EHE_k4` are /4 diversity metrics.