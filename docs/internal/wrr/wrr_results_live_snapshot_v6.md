# WRR v6 Live Results Snapshot

- Generated (UTC): 2026-02-10T22:32:59.497467+00:00
- Completion: 36/54 model-group-run cells

## Group Means (Available Runs)

| Group | n_cases | runs | R_H | R_R | Rationality pass | H_norm_k4 | EHE_k4 | retry_rows | retry_sum |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| Group_A | 12 | Run_1,Run_2 | 0.00% | 4.16% | 95.84% | 0.566 | 0.566 | 0.00 | 0.00 |
| Group_B | 12 | Run_1,Run_2 | 0.01% | 0.16% | 99.84% | 0.658 | 0.658 | 58.92 | 78.92 |
| Group_C | 12 | Run_1,Run_2 | 0.00% | 0.23% | 99.77% | 0.648 | 0.648 | 42.00 | 55.17 |

## Completion by Model x Group

| Model | Group_A | Group_B | Group_C |
|---|---:|---:|---:|
| gemma3_12b | 2/3 | 2/3 | 2/3 |
| gemma3_27b | 2/3 | 2/3 | 2/3 |
| gemma3_4b | 2/3 | 2/3 | 2/3 |
| ministral3_14b | 2/3 | 2/3 | 2/3 |
| ministral3_3b | 2/3 | 2/3 | 2/3 |
| ministral3_8b | 2/3 | 2/3 | 2/3 |

## Update Command

```bash
python scripts/wrr_compute_metrics_v6.py
python scripts/wrr_render_results_md_v6.py
```

## Notes

- This file updates from existing logs only; missing runs are not imputed.
- Retry metrics are workload diagnostics and are not violation prevalence.
- EHE_k4 = H_norm_k4 * (1 - R_H).
