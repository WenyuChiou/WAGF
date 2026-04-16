# Skill Proposal Reasoning Taxonomy

Trace dir: `C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_42/gemma4_e4b_strict`

## Construct REASON Length Summary

| construct   |   char_count_mean |   token_count_mean |   truncation_rate |
|:------------|------------------:|-------------------:|------------------:|
| CP          |           151.078 |            22.6171 |                 0 |
| PA          |           106.924 |            16.5921 |                 0 |
| SC          |           111.654 |            16.8823 |                 0 |
| SP          |           122.14  |            18.0798 |                 0 |
| TP          |           140.457 |            21.9054 |                 0 |

## Highest-Frequency Construct Vocabulary Families

| agent_type   |   year | construct   | keyword_family   |   count |   frequency |   n_decisions |
|:-------------|-------:|:------------|:-----------------|--------:|------------:|--------------:|
| owner        |      9 | SC          | community_ties   |     200 |       1     |           200 |
| owner        |      4 | SC          | community_ties   |     199 |       0.995 |           200 |
| owner        |     12 | SC          | community_ties   |     198 |       0.99  |           200 |
| owner        |      3 | PA          | attachment       |     198 |       0.99  |           200 |
| owner        |     13 | TP          | severity         |     198 |       0.99  |           200 |
| owner        |     11 | SC          | community_ties   |     198 |       0.99  |           200 |
| owner        |      5 | PA          | attachment       |     197 |       0.985 |           200 |
| owner        |     12 | PA          | attachment       |     197 |       0.985 |           200 |
| owner        |     10 | PA          | attachment       |     197 |       0.985 |           200 |
| owner        |     10 | SC          | community_ties   |     197 |       0.985 |           200 |
| owner        |      2 | PA          | attachment       |     196 |       0.98  |           200 |
| owner        |     11 | TP          | severity         |     196 |       0.98  |           200 |
| owner        |      4 | PA          | attachment       |     196 |       0.98  |           200 |
| owner        |      6 | PA          | attachment       |     196 |       0.98  |           200 |
| owner        |     13 | PA          | attachment       |     196 |       0.98  |           200 |

## Audit Score Trajectory

|   year | agent_type   |   demographic_audit_mean |   semantic_correlation_audit_mean | demographic_audit_drop   | semantic_correlation_audit_drop   |   n_decisions |
|-------:|:-------------|-------------------------:|----------------------------------:|:-------------------------|:----------------------------------|--------------:|
|      1 | owner        |                   1      |                           0       | False                    | False                             |           200 |
|      2 | owner        |                   1      |                           0.13035 | False                    | False                             |           200 |
|      3 | owner        |                   1      |                           0.2145  | False                    | False                             |           200 |
|      4 | owner        |                   1      |                           0.1683  | False                    | True                              |           200 |
|      5 | owner        |                   1      |                           0.09735 | False                    | True                              |           200 |
|      6 | owner        |                   1      |                           0.1023  | False                    | False                             |           200 |
|      7 | owner        |                   1      |                           0.10065 | False                    | True                              |           200 |
|      8 | owner        |                   1      |                           0.10065 | False                    | False                             |           200 |
|      9 | owner        |                   1      |                           0.09735 | False                    | True                              |           200 |
|     10 | owner        |                   1      |                           0.10065 | False                    | False                             |           200 |
|     11 | owner        |                   0.995  |                           0.00165 | True                     | True                              |           200 |
|     12 | owner        |                   1      |                           0       | False                    | True                              |           200 |
|     13 | owner        |                   1      |                           0       | False                    | False                             |           200 |
|      1 | renter       |                   1      |                           0       | False                    | False                             |           200 |
|      2 | renter       |                   1      |                           0.1023  | False                    | False                             |           200 |
|      3 | renter       |                   1      |                           0.15015 | False                    | False                             |           200 |
|      4 | renter       |                   1      |                           0.14025 | False                    | True                              |           200 |
|      5 | renter       |                   0.9925 |                           0.0726  | True                     | True                              |           200 |
|      6 | renter       |                   0.995  |                           0.0792  | False                    | False                             |           200 |
|      7 | renter       |                   1      |                           0.0759  | False                    | True                              |           200 |
|      8 | renter       |                   0.99   |                           0.07755 | True                     | False                             |           200 |
|      9 | renter       |                   1      |                           0.0726  | False                    | True                              |           200 |
|     10 | renter       |                   0.995  |                           0.0759  | True                     | False                             |           200 |
|     11 | renter       |                   1      |                           0       | False                    | True                              |           200 |
|     12 | renter       |                   1      |                           0       | False                    | False                             |           200 |
|     13 | renter       |                   0.995  |                           0       | True                     | False                             |           200 |

## Main Reasoning Phrase Detection

| agent_type   |   year | phrase_family    |   count |   frequency |   n_decisions |
|:-------------|-------:|:-----------------|--------:|------------:|--------------:|
| owner        |      3 | self_referential |     146 |       0.73  |           200 |
| owner        |      6 | self_referential |     137 |       0.685 |           200 |
| owner        |      2 | self_referential |     135 |       0.675 |           200 |
| owner        |      4 | self_referential |     130 |       0.65  |           200 |
| owner        |      5 | self_referential |     128 |       0.64  |           200 |
| owner        |      9 | self_referential |     127 |       0.635 |           200 |
| owner        |      7 | self_referential |     124 |       0.62  |           200 |
| owner        |      1 | self_referential |     122 |       0.61  |           200 |
| owner        |     10 | self_referential |     121 |       0.605 |           200 |
| owner        |     13 | self_referential |     116 |       0.58  |           200 |
| owner        |     11 | self_referential |     114 |       0.57  |           200 |
| owner        |      8 | self_referential |     114 |       0.57  |           200 |

## Summary

- `reason_text_length_by_year.csv` captures REASON length and truncation flags per construct-year-decision.
- `reason_vocabulary_by_construct.csv` and `reason_vocabulary_by_mg.csv` quantify recurring semantic motifs in the construct-specific prose.
- `reasoning_phrase_detection_by_year.csv` isolates rationalization phrases in the main free-text justification, including `past_reference`.
- `audit_scores_by_year.csv` tracks both audit systems and flags year-over-year mean drops.