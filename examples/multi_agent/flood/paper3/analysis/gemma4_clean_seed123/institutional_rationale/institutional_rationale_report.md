# Institutional Rationale

Trace dir: `C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_123/gemma4_e4b_strict`

## Policy Trajectory

|   year | agent_id   | skill                     |   subsidy_rate |   crs_class |   crs_discount |   loss_ratio |   premium_rate |
|-------:|:-----------|:--------------------------|---------------:|------------:|---------------:|-------------:|---------------:|
|      1 | FEMA_NFIP  | maintain_crs              |          0.5   |           7 |          0.15  |        0     |       0.008    |
|      2 | FEMA_NFIP  | maintain_crs              |          0.475 |           7 |          0.15  |       85.866 |       0.008    |
|      3 | FEMA_NFIP  | significantly_improve_crs |          0.475 |           7 |          0.15  |       13.226 |       0.00844  |
|      4 | FEMA_NFIP  | maintain_crs              |          0.475 |           6 |          0.2   |       19.134 |       0.00888  |
|      5 | FEMA_NFIP  | maintain_crs              |          0.475 |           6 |          0.2   |       22.131 |       0.00932  |
|      6 | FEMA_NFIP  | significantly_improve_crs |          0.475 |           6 |          0.2   |       13.295 |       0.009584 |
|      7 | FEMA_NFIP  | reduce_crs                |          0.475 |           5 |          0.25  |       13.885 |       0.009936 |
|      8 | FEMA_NFIP  | maintain_crs              |          0.475 |           6 |          0.225 |       21.165 |       0.010288 |
|      9 | FEMA_NFIP  | maintain_crs              |          0.475 |           6 |          0.225 |       20.418 |       0.01064  |
|     10 | FEMA_NFIP  | reduce_crs                |          0.475 |           6 |          0.225 |       16.323 |       0.01108  |
|     11 | FEMA_NFIP  | maintain_crs              |          0.475 |           6 |          0.2   |       15.491 |       0.0124   |
|     12 | FEMA_NFIP  | improve_crs               |          0.475 |           6 |          0.2   |       54.144 |       0.01328  |
|     13 | FEMA_NFIP  | maintain_crs              |          0.475 |           6 |          0.225 |       18.754 |       0.01372  |
|      1 | NJ_STATE   | small_decrease_subsidy    |          0.5   |           7 |          0.15  |        0     |       0.008    |
|      2 | NJ_STATE   | maintain_subsidy          |          0.475 |           7 |          0.15  |       85.866 |       0.008    |
|      3 | NJ_STATE   | maintain_subsidy          |          0.475 |           7 |          0.15  |       13.226 |       0.00844  |
|      4 | NJ_STATE   | maintain_subsidy          |          0.475 |           6 |          0.2   |       19.134 |       0.00888  |
|      5 | NJ_STATE   | maintain_subsidy          |          0.475 |           6 |          0.2   |       22.131 |       0.00932  |
|      6 | NJ_STATE   | maintain_subsidy          |          0.475 |           6 |          0.2   |       13.295 |       0.009584 |
|      7 | NJ_STATE   | maintain_subsidy          |          0.475 |           5 |          0.25  |       13.885 |       0.009936 |
|      8 | NJ_STATE   | maintain_subsidy          |          0.475 |           6 |          0.225 |       21.165 |       0.010288 |
|      9 | NJ_STATE   | maintain_subsidy          |          0.475 |           6 |          0.225 |       20.418 |       0.01064  |
|     10 | NJ_STATE   | maintain_subsidy          |          0.475 |           6 |          0.225 |       16.323 |       0.01108  |
|     11 | NJ_STATE   | maintain_subsidy          |          0.475 |           6 |          0.2   |       15.491 |       0.0124   |
|     12 | NJ_STATE   | maintain_subsidy          |          0.475 |           6 |          0.2   |       54.144 |       0.01328  |
|     13 | NJ_STATE   | large_increase_subsidy    |          0.475 |           6 |          0.225 |       18.754 |       0.01372  |

## Rationale Lengths

|   year | agent_id   | skill                     |   strategy_len |   reasoning_len |
|-------:|:-----------|:--------------------------|---------------:|----------------:|
|      1 | FEMA_NFIP  | maintain_crs              |              0 |             761 |
|      2 | FEMA_NFIP  | maintain_crs              |              0 |             912 |
|      3 | FEMA_NFIP  | significantly_improve_crs |              0 |               0 |
|      4 | FEMA_NFIP  | maintain_crs              |              0 |             989 |
|      5 | FEMA_NFIP  | maintain_crs              |              0 |             637 |
|      6 | FEMA_NFIP  | significantly_improve_crs |              0 |               0 |
|      7 | FEMA_NFIP  | reduce_crs                |              0 |            1304 |
|      8 | FEMA_NFIP  | maintain_crs              |              0 |             634 |
|      9 | FEMA_NFIP  | maintain_crs              |              0 |             769 |
|     10 | FEMA_NFIP  | reduce_crs                |              0 |             807 |
|     11 | FEMA_NFIP  | maintain_crs              |              0 |             766 |
|     12 | FEMA_NFIP  | improve_crs               |              0 |             655 |
|     13 | FEMA_NFIP  | maintain_crs              |              0 |             647 |
|      1 | NJ_STATE   | small_decrease_subsidy    |              0 |               0 |
|      2 | NJ_STATE   | maintain_subsidy          |              0 |            1146 |
|      3 | NJ_STATE   | maintain_subsidy          |              0 |            1178 |
|      4 | NJ_STATE   | maintain_subsidy          |              0 |            1413 |
|      5 | NJ_STATE   | maintain_subsidy          |              0 |            1275 |
|      6 | NJ_STATE   | maintain_subsidy          |              0 |            1038 |
|      7 | NJ_STATE   | maintain_subsidy          |              0 |            1004 |
|      8 | NJ_STATE   | maintain_subsidy          |              0 |             863 |
|      9 | NJ_STATE   | maintain_subsidy          |              0 |            1016 |
|     10 | NJ_STATE   | maintain_subsidy          |              0 |             903 |
|     11 | NJ_STATE   | maintain_subsidy          |              0 |            1179 |
|     12 | NJ_STATE   | maintain_subsidy          |              0 |             819 |
|     13 | NJ_STATE   | large_increase_subsidy    |              0 |               0 |

## Rationale Category Counts

| agent_id   | category            |   count |
|:-----------|:--------------------|--------:|
| FEMA_NFIP  | mitigation_reward   |      11 |
| FEMA_NFIP  | status_quo          |       8 |
| FEMA_NFIP  | loss_ratio_reaction |       2 |
| FEMA_NFIP  | uncategorized       |       2 |
| NJ_STATE   | budget_concern      |      11 |
| NJ_STATE   | crisis_response     |      11 |
| NJ_STATE   | status_quo          |      11 |
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