# Table 1 (v8 main) Behavioral Rationalization + Diversity Retention

| model | group | n_runs | R_R_pct | H_norm_k4 | EHE_k4 |
|---|---|---|---|---|---|
| gemma3_4b | Group_A | 2 | 1.051 | 0.584 | 0.584 |
| gemma3_4b | Group_B | 2 | 0.411 | 0.756 | 0.756 |
| gemma3_4b | Group_C | 2 | 1.281 | 0.778 | 0.778 |
| gemma3_12b | Group_A | 2 | 0.511 | 0.486 | 0.486 |
| gemma3_12b | Group_B | 2 | 0.062 | 0.502 | 0.502 |
| gemma3_12b | Group_C | 2 | 0.051 | 0.422 | 0.422 |
| gemma3_27b | Group_A | 2 | 12.000 | 0.645 | 0.645 |
| gemma3_27b | Group_B | 2 | 0.000 | 0.623 | 0.623 |
| gemma3_27b | Group_C | 2 | 0.000 | 0.670 | 0.670 |
| ministral3_3b | Group_A | 2 | 8.481 | 0.445 | 0.445 |
| ministral3_3b | Group_B | 2 | 0.506 | 0.736 | 0.735 |
| ministral3_3b | Group_C | 2 | 0.065 | 0.682 | 0.682 |
| ministral3_8b | Group_A | 2 | 1.107 | 0.746 | 0.746 |
| ministral3_8b | Group_B | 2 | 0.000 | 0.622 | 0.622 |
| ministral3_8b | Group_C | 2 | 0.000 | 0.639 | 0.639 |
| ministral3_14b | Group_A | 2 | 1.806 | 0.488 | 0.488 |
| ministral3_14b | Group_B | 2 | 0.000 | 0.706 | 0.706 |
| ministral3_14b | Group_C | 2 | 0.000 | 0.699 | 0.699 |

Feasibility note (secondary diagnostic):
- Mean `R_H_pct` (Group_A): 0.000
- Mean `R_H_pct` (Group_B): 0.012
- Mean `R_H_pct` (Group_C): 0.000

Interpretation:
- Main performance axis: lower `R_R_pct` with retained `EHE_k4`.
- `R_H_pct` is retained as a strict safety diagnostic (reported here as note and in SI).
