# WRR v6 Live Results Snapshot

- Generated (UTC): 2026-02-09T15:48:38.382015+00:00
- Completion: 25/54 model-group-run cells

## Group Means (Available Runs)

| Group | n_cases | runs | R_H | R_R | Rationality pass | H_norm_k4 | EHE_k4 | retry_rows | retry_sum |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| Group_A | 9 | Run_1,Run_2 | 38.19% | 8.08% | 91.92% | 0.567 | 0.372 | 0.00 | 0.00 |
| Group_B | 8 | Run_1,Run_2 | 0.02% | 0.23% | 99.77% | 0.653 | 0.653 | 69.25 | 94.62 |
| Group_C | 8 | Run_1,Run_2 | 0.00% | 0.35% | 99.65% | 0.633 | 0.633 | 42.88 | 59.88 |

## Completion by Model x Group

| Model | Group_A | Group_B | Group_C |
|---|---:|---:|---:|
| gemma3_12b | 2/3 | 2/3 | 2/3 |
| gemma3_27b | 2/3 | 1/3 | 1/3 |
| gemma3_4b | 2/3 | 2/3 | 2/3 |
| ministral3_14b | 1/3 | 1/3 | 1/3 |
| ministral3_3b | 1/3 | 1/3 | 1/3 |
| ministral3_8b | 1/3 | 1/3 | 1/3 |

## Update Command

```bash
python scripts/wrr_compute_metrics_v6.py
python scripts/wrr_render_results_md_v6.py
```

## Notes

- This file updates from existing logs only; missing runs are not imputed.
- Retry metrics are workload diagnostics and are not violation prevalence.
- EHE_k4 = H_norm_k4 * (1 - R_H).
