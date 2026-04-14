# Institutional Rationale

Trace dir: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict`

## Policy Trajectory

|   year | agent_id   | skill                     |   subsidy_rate |   crs_class |   crs_discount |   loss_ratio |   premium_rate |
|-------:|:-----------|:--------------------------|---------------:|------------:|---------------:|-------------:|---------------:|
|      1 | FEMA_NFIP  | maintain_crs              |           0.5  |           7 |          0.15  |        0     |       0.008    |
|      2 | FEMA_NFIP  | maintain_crs              |           0.55 |           7 |          0.15  |       87.039 |       0.008    |
|      3 | FEMA_NFIP  | improve_crs               |           0.55 |           7 |          0.15  |       15.012 |       0.00844  |
|      4 | FEMA_NFIP  | maintain_crs              |           0.55 |           7 |          0.175 |       16.256 |       0.00888  |
|      5 | FEMA_NFIP  | maintain_crs              |           0.55 |           7 |          0.175 |       22.09  |       0.00932  |
|      6 | FEMA_NFIP  | maintain_crs              |           0.55 |           7 |          0.175 |       11.278 |       0.009584 |
|      7 | FEMA_NFIP  | maintain_crs              |           0.55 |           7 |          0.175 |       14.85  |       0.009936 |
|      8 | FEMA_NFIP  | maintain_crs              |           0.55 |           7 |          0.175 |       17.072 |       0.010288 |
|      9 | FEMA_NFIP  | maintain_crs              |           0.55 |           7 |          0.175 |       12.613 |       0.01064  |
|     10 | FEMA_NFIP  | significantly_improve_crs |           0.55 |           7 |          0.175 |        9.723 |       0.01108  |
|     11 | FEMA_NFIP  | maintain_crs              |           0.55 |           6 |          0.225 |       11.276 |       0.0124   |
|     12 | FEMA_NFIP  | improve_crs               |           0.55 |           6 |          0.225 |       42.379 |       0.01328  |
|     13 | FEMA_NFIP  | maintain_crs              |           0.55 |           5 |          0.25  |       13.647 |       0.01372  |
|      1 | NJ_STATE   | large_increase_subsidy    |           0.5  |           7 |          0.15  |        0     |       0.008    |
|      2 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.15  |       87.039 |       0.008    |
|      3 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.15  |       15.012 |       0.00844  |
|      4 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.175 |       16.256 |       0.00888  |
|      5 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.175 |       22.09  |       0.00932  |
|      6 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.175 |       11.278 |       0.009584 |
|      7 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.175 |       14.85  |       0.009936 |
|      8 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.175 |       17.072 |       0.010288 |
|      9 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.175 |       12.613 |       0.01064  |
|     10 | NJ_STATE   | maintain_subsidy          |           0.55 |           7 |          0.175 |        9.723 |       0.01108  |
|     11 | NJ_STATE   | maintain_subsidy          |           0.55 |           6 |          0.225 |       11.276 |       0.0124   |
|     12 | NJ_STATE   | maintain_subsidy          |           0.55 |           6 |          0.225 |       42.379 |       0.01328  |
|     13 | NJ_STATE   | maintain_subsidy          |           0.55 |           5 |          0.25  |       13.647 |       0.01372  |

## Rationale Lengths

|   year | agent_id   | skill                     |   strategy_len |   reasoning_len |
|-------:|:-----------|:--------------------------|---------------:|----------------:|
|      1 | FEMA_NFIP  | maintain_crs              |              0 |            1148 |
|      2 | FEMA_NFIP  | maintain_crs              |              0 |            1061 |
|      3 | FEMA_NFIP  | improve_crs               |              0 |             944 |
|      4 | FEMA_NFIP  | maintain_crs              |              0 |             659 |
|      5 | FEMA_NFIP  | maintain_crs              |              0 |             610 |
|      6 | FEMA_NFIP  | maintain_crs              |              0 |            1061 |
|      7 | FEMA_NFIP  | maintain_crs              |              0 |             586 |
|      8 | FEMA_NFIP  | maintain_crs              |              0 |             764 |
|      9 | FEMA_NFIP  | maintain_crs              |              0 |             657 |
|     10 | FEMA_NFIP  | significantly_improve_crs |              0 |               0 |
|     11 | FEMA_NFIP  | maintain_crs              |              0 |            1038 |
|     12 | FEMA_NFIP  | improve_crs               |              0 |               0 |
|     13 | FEMA_NFIP  | maintain_crs              |              0 |               0 |
|      1 | NJ_STATE   | large_increase_subsidy    |              0 |            1091 |
|      2 | NJ_STATE   | maintain_subsidy          |              0 |            1277 |
|      3 | NJ_STATE   | maintain_subsidy          |              0 |            1193 |
|      4 | NJ_STATE   | maintain_subsidy          |              0 |            1052 |
|      5 | NJ_STATE   | maintain_subsidy          |              0 |            1176 |
|      6 | NJ_STATE   | maintain_subsidy          |              0 |            1022 |
|      7 | NJ_STATE   | maintain_subsidy          |              0 |            1115 |
|      8 | NJ_STATE   | maintain_subsidy          |              0 |            1377 |
|      9 | NJ_STATE   | maintain_subsidy          |              0 |            1007 |
|     10 | NJ_STATE   | maintain_subsidy          |              0 |            1020 |
|     11 | NJ_STATE   | maintain_subsidy          |              0 |            1065 |
|     12 | NJ_STATE   | maintain_subsidy          |              0 |            1314 |
|     13 | NJ_STATE   | maintain_subsidy          |              0 |            1167 |

## Rationale Category Counts

| agent_id   | category            |   count |
|:-----------|:--------------------|--------:|
| FEMA_NFIP  | mitigation_reward   |      10 |
| FEMA_NFIP  | status_quo          |      10 |
| FEMA_NFIP  | uncategorized       |       3 |
| FEMA_NFIP  | equity_concern      |       1 |
| FEMA_NFIP  | loss_ratio_reaction |       1 |
| NJ_STATE   | budget_concern      |      13 |
| NJ_STATE   | crisis_response     |      13 |
| NJ_STATE   | status_quo          |      12 |

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
- reactive_adjustments=4/4