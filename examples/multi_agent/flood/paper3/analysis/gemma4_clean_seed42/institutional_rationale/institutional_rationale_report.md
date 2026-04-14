# Institutional Rationale

Trace dir: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_42/gemma4_e4b_strict`

## Policy Trajectory

|   year | agent_id   | skill                  |   subsidy_rate |   crs_class |   crs_discount |   loss_ratio |   premium_rate |
|-------:|:-----------|:-----------------------|---------------:|------------:|---------------:|-------------:|---------------:|
|      1 | FEMA_NFIP  | maintain_crs           |           0.5  |           7 |          0.15  |        0     |       0.008    |
|      2 | FEMA_NFIP  | improve_crs            |           0.55 |           7 |          0.15  |       84.717 |       0.008    |
|      3 | FEMA_NFIP  | reduce_crs             |           0.55 |           7 |          0.175 |       15.319 |       0.00844  |
|      4 | FEMA_NFIP  | maintain_crs           |           0.55 |           7 |          0.15  |       14.481 |       0.00888  |
|      5 | FEMA_NFIP  | maintain_crs           |           0.55 |           7 |          0.15  |       25.701 |       0.00932  |
|      6 | FEMA_NFIP  | reduce_crs             |           0.55 |           7 |          0.15  |       13.58  |       0.009584 |
|      7 | FEMA_NFIP  | maintain_crs           |           0.55 |           8 |          0.125 |       14.837 |       0.009936 |
|      8 | FEMA_NFIP  | maintain_crs           |           0.55 |           8 |          0.125 |       19.507 |       0.010288 |
|      9 | FEMA_NFIP  | maintain_crs           |           0.55 |           8 |          0.125 |       19.64  |       0.01064  |
|     10 | FEMA_NFIP  | maintain_crs           |           0.55 |           8 |          0.125 |       16.084 |       0.01108  |
|     11 | FEMA_NFIP  | maintain_crs           |           0.55 |           8 |          0.125 |       16.66  |       0.0124   |
|     12 | FEMA_NFIP  | improve_crs            |           0.55 |           8 |          0.125 |       48.35  |       0.01328  |
|     13 | FEMA_NFIP  | improve_crs            |           0.6  |           7 |          0.15  |       18.694 |       0.01372  |
|      1 | NJ_STATE   | large_increase_subsidy |           0.5  |           7 |          0.15  |        0     |       0.008    |
|      2 | NJ_STATE   | maintain_subsidy       |           0.55 |           7 |          0.15  |       84.717 |       0.008    |
|      3 | NJ_STATE   | maintain_subsidy       |           0.55 |           7 |          0.175 |       15.319 |       0.00844  |
|      4 | NJ_STATE   | maintain_subsidy       |           0.55 |           7 |          0.15  |       14.481 |       0.00888  |
|      5 | NJ_STATE   | maintain_subsidy       |           0.55 |           7 |          0.15  |       25.701 |       0.00932  |
|      6 | NJ_STATE   | maintain_subsidy       |           0.55 |           7 |          0.15  |       13.58  |       0.009584 |
|      7 | NJ_STATE   | maintain_subsidy       |           0.55 |           8 |          0.125 |       14.837 |       0.009936 |
|      8 | NJ_STATE   | maintain_subsidy       |           0.55 |           8 |          0.125 |       19.507 |       0.010288 |
|      9 | NJ_STATE   | maintain_subsidy       |           0.55 |           8 |          0.125 |       19.64  |       0.01064  |
|     10 | NJ_STATE   | maintain_subsidy       |           0.55 |           8 |          0.125 |       16.084 |       0.01108  |
|     11 | NJ_STATE   | maintain_subsidy       |           0.55 |           8 |          0.125 |       16.66  |       0.0124   |
|     12 | NJ_STATE   | large_increase_subsidy |           0.55 |           8 |          0.125 |       48.35  |       0.01328  |
|     13 | NJ_STATE   | maintain_subsidy       |           0.6  |           7 |          0.15  |       18.694 |       0.01372  |

## Rationale Lengths

|   year | agent_id   | skill                  |   strategy_len |   reasoning_len |
|-------:|:-----------|:-----------------------|---------------:|----------------:|
|      1 | FEMA_NFIP  | maintain_crs           |              0 |             953 |
|      2 | FEMA_NFIP  | improve_crs            |              0 |               0 |
|      3 | FEMA_NFIP  | reduce_crs             |              0 |               0 |
|      4 | FEMA_NFIP  | maintain_crs           |              0 |             619 |
|      5 | FEMA_NFIP  | maintain_crs           |              0 |             713 |
|      6 | FEMA_NFIP  | reduce_crs             |              0 |            1082 |
|      7 | FEMA_NFIP  | maintain_crs           |              0 |             677 |
|      8 | FEMA_NFIP  | maintain_crs           |              0 |            1007 |
|      9 | FEMA_NFIP  | maintain_crs           |              0 |            1095 |
|     10 | FEMA_NFIP  | maintain_crs           |              0 |            1204 |
|     11 | FEMA_NFIP  | maintain_crs           |              0 |             890 |
|     12 | FEMA_NFIP  | improve_crs            |              0 |            1218 |
|     13 | FEMA_NFIP  | improve_crs            |              0 |               0 |
|      1 | NJ_STATE   | large_increase_subsidy |              0 |             997 |
|      2 | NJ_STATE   | maintain_subsidy       |              0 |            1242 |
|      3 | NJ_STATE   | maintain_subsidy       |              0 |            1104 |
|      4 | NJ_STATE   | maintain_subsidy       |              0 |               0 |
|      5 | NJ_STATE   | maintain_subsidy       |              0 |            1448 |
|      6 | NJ_STATE   | maintain_subsidy       |              0 |            1162 |
|      7 | NJ_STATE   | maintain_subsidy       |              0 |            1068 |
|      8 | NJ_STATE   | maintain_subsidy       |              0 |             907 |
|      9 | NJ_STATE   | maintain_subsidy       |              0 |             894 |
|     10 | NJ_STATE   | maintain_subsidy       |              0 |             790 |
|     11 | NJ_STATE   | maintain_subsidy       |              0 |            1303 |
|     12 | NJ_STATE   | large_increase_subsidy |              0 |               0 |
|     13 | NJ_STATE   | maintain_subsidy       |              0 |            1074 |

## Rationale Category Counts

| agent_id   | category            |   count |
|:-----------|:--------------------|--------:|
| FEMA_NFIP  | mitigation_reward   |      10 |
| FEMA_NFIP  | status_quo          |      10 |
| FEMA_NFIP  | loss_ratio_reaction |       3 |
| FEMA_NFIP  | uncategorized       |       3 |
| FEMA_NFIP  | crisis_response     |       1 |
| NJ_STATE   | budget_concern      |      11 |
| NJ_STATE   | crisis_response     |      11 |
| NJ_STATE   | status_quo          |      10 |
| NJ_STATE   | uncategorized       |       2 |

## Summary

- `institutional_trajectory.csv` lists yearly government and insurance policy states.
- `institutional_rationale_text.csv` extracts the free-text policy rationale and its lengths.
- `institutional_rationale_categories_by_year.csv` tags crisis, budget, equity, loss-ratio, mitigation, and status-quo motifs.
- Memory audit cross-check warnings are preserved below rather than suppressed.

## Warnings

- NJ_STATE year 2 retrieved_count=3
- NJ_STATE year 3 retrieved_count=3
- NJ_STATE year 4 retrieved_count=3
- NJ_STATE year 5 retrieved_count=3
- NJ_STATE year 6 retrieved_count=3
- NJ_STATE year 7 retrieved_count=3
- NJ_STATE year 8 retrieved_count=3
- NJ_STATE year 9 retrieved_count=3
- NJ_STATE year 10 retrieved_count=3
- NJ_STATE year 11 retrieved_count=3
- NJ_STATE year 12 retrieved_count=3
- NJ_STATE year 13 retrieved_count=3
- FEMA_NFIP year 2 retrieved_count=3
- FEMA_NFIP year 3 retrieved_count=3
- FEMA_NFIP year 4 retrieved_count=3
- FEMA_NFIP year 5 retrieved_count=3
- FEMA_NFIP year 6 retrieved_count=3
- FEMA_NFIP year 7 retrieved_count=3
- FEMA_NFIP year 8 retrieved_count=3
- FEMA_NFIP year 9 retrieved_count=3
- FEMA_NFIP year 10 retrieved_count=3
- FEMA_NFIP year 11 retrieved_count=3
- FEMA_NFIP year 12 retrieved_count=3
- FEMA_NFIP year 13 retrieved_count=3
- reactive_adjustments=7/7