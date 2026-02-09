# Table 1 (v8 main) Behavioral Rationalization + Diversity Retention

| model | group | n_runs | R_R_pct | H_norm_k4 | EHE_k4 |
|---|---:|---:|---:|---:|---:|
| gemma3_12b | Group_A | 2 | 0.511 | 0.486 | 0.486 |
| gemma3_12b | Group_B | 2 | 0.062 | 0.502 | 0.502 |
| gemma3_12b | Group_C | 2 | 0.051 | 0.422 | 0.422 |
| gemma3_27b | Group_A | 2 | 12.000 | 0.645 | 0.645 |
| gemma3_27b | Group_B | 1 | 0.000 | 0.629 | 0.629 |
| gemma3_27b | Group_C | 1 | 0.000 | 0.685 | 0.685 |
| gemma3_4b | Group_A | 2 | 1.051 | 0.584 | 0.584 |
| gemma3_4b | Group_B | 2 | 0.411 | 0.756 | 0.756 |
| gemma3_4b | Group_C | 2 | 1.281 | 0.778 | 0.778 |
| ministral3_14b | Group_A | 1 | 1.747 | 0.480 | 0.480 |
| ministral3_14b | Group_B | 1 | 0.000 | 0.695 | 0.695 |
| ministral3_14b | Group_C | 1 | 0.000 | 0.712 | 0.712 |
| ministral3_3b | Group_A | 1 | 10.091 | 0.435 | 0.435 |
| ministral3_3b | Group_B | 1 | 0.872 | 0.755 | 0.754 |
| ministral3_3b | Group_C | 1 | 0.131 | 0.640 | 0.640 |
| ministral3_8b | Group_A | 1 | 0.711 | 0.752 | 0.752 |
| ministral3_8b | Group_B | 1 | 0.000 | 0.627 | 0.627 |
| ministral3_8b | Group_C | 1 | 0.000 | 0.623 | 0.623 |

Feasibility note (secondary diagnostic):
- Mean `R_H_pct` (Group_A): 0.000
- Mean `R_H_pct` (Group_B): 0.024
- Mean `R_H_pct` (Group_C): 0.000

Interpretation:
- Main performance axis: lower `R_R_pct` with retained `EHE_k4`.
- `R_H_pct` is retained as a strict safety diagnostic (reported here as note and in SI).