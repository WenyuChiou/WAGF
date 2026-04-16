# Skill Proposal Reasoning Taxonomy

Trace dir: `C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_123/gemma4_e4b_strict`

## Construct REASON Length Summary

| construct   |   char_count_mean |   token_count_mean |   truncation_rate |
|:------------|------------------:|-------------------:|------------------:|
| CP          |           151.602 |            22.6673 |                 0 |
| PA          |           107.675 |            16.7277 |                 0 |
| SC          |           112.552 |            17.0365 |                 0 |
| SP          |           123.772 |            18.5562 |                 0 |
| TP          |           138.661 |            21.8421 |                 0 |

## Highest-Frequency Construct Vocabulary Families

| agent_type   |   year | construct   | keyword_family   |   count |   frequency |   n_decisions |
|:-------------|-------:|:------------|:-----------------|--------:|------------:|--------------:|
| owner        |      3 | PA          | attachment       |     199 |       0.995 |           200 |
| owner        |      7 | SC          | community_ties   |     199 |       0.995 |           200 |
| owner        |     11 | SC          | community_ties   |     198 |       0.99  |           200 |
| owner        |     12 | SC          | community_ties   |     198 |       0.99  |           200 |
| owner        |     13 | SC          | community_ties   |     196 |       0.98  |           200 |
| owner        |     11 | PA          | attachment       |     196 |       0.98  |           200 |
| owner        |      4 | SC          | community_ties   |     196 |       0.98  |           200 |
| owner        |      6 | SC          | community_ties   |     196 |       0.98  |           200 |
| owner        |      6 | PA          | attachment       |     196 |       0.98  |           200 |
| owner        |      2 | SC          | community_ties   |     196 |       0.98  |           200 |
| owner        |      9 | PA          | attachment       |     196 |       0.98  |           200 |
| owner        |     10 | CP          | affordability    |     195 |       0.975 |           200 |
| owner        |      7 | PA          | attachment       |     195 |       0.975 |           200 |
| owner        |     10 | SC          | community_ties   |     195 |       0.975 |           200 |
| owner        |      5 | SC          | community_ties   |     195 |       0.975 |           200 |

## Audit Score Trajectory

|   year | agent_type   |   demographic_audit_mean |   semantic_correlation_audit_mean | demographic_audit_drop   | semantic_correlation_audit_drop   |   n_decisions |
|-------:|:-------------|-------------------------:|----------------------------------:|:-------------------------|:----------------------------------|--------------:|
|      1 | owner        |                   1      |                           0       | False                    | False                             |           200 |
|      2 | owner        |                   1      |                           0.12375 | False                    | False                             |           200 |
|      3 | owner        |                   1      |                           0.20625 | False                    | False                             |           200 |
|      4 | owner        |                   1      |                           0.19965 | False                    | True                              |           200 |
|      5 | owner        |                   1      |                           0.0825  | False                    | True                              |           200 |
|      6 | owner        |                   1      |                           0.09405 | False                    | False                             |           200 |
|      7 | owner        |                   1      |                           0.10065 | False                    | False                             |           200 |
|      8 | owner        |                   1      |                           0.10395 | False                    | False                             |           200 |
|      9 | owner        |                   1      |                           0.1023  | False                    | True                              |           200 |
|     10 | owner        |                   1      |                           0.1023  | False                    | False                             |           200 |
|     11 | owner        |                   0.995  |                           0       | True                     | True                              |           200 |
|     12 | owner        |                   1      |                           0       | False                    | False                             |           200 |
|     13 | owner        |                   0.995  |                           0       | True                     | False                             |           200 |
|      1 | renter       |                   1      |                           0       | False                    | False                             |           200 |
|      2 | renter       |                   1      |                           0.10725 | False                    | False                             |           200 |
|      3 | renter       |                   1      |                           0.1551  | False                    | False                             |           200 |
|      4 | renter       |                   1      |                           0.15345 | False                    | True                              |           200 |
|      5 | renter       |                   1      |                           0.0726  | False                    | True                              |           200 |
|      6 | renter       |                   0.995  |                           0.0759  | True                     | False                             |           200 |
|      7 | renter       |                   1      |                           0.07755 | False                    | False                             |           200 |
|      8 | renter       |                   0.995  |                           0.07425 | True                     | True                              |           200 |
|      9 | renter       |                   0.9975 |                           0.0759  | False                    | False                             |           200 |
|     10 | renter       |                   1      |                           0.07425 | False                    | True                              |           200 |
|     11 | renter       |                   1      |                           0       | False                    | True                              |           200 |
|     12 | renter       |                   0.995  |                           0       | True                     | False                             |           200 |
|     13 | renter       |                   1      |                           0       | False                    | False                             |           200 |

## Main Reasoning Phrase Detection

| agent_type   |   year | phrase_family    |   count |   frequency |   n_decisions |
|:-------------|-------:|:-----------------|--------:|------------:|--------------:|
| owner        |      2 | self_referential |     145 |       0.725 |           200 |
| owner        |      7 | self_referential |     133 |       0.665 |           200 |
| owner        |      1 | self_referential |     132 |       0.66  |           200 |
| owner        |      8 | self_referential |     129 |       0.645 |           200 |
| owner        |      3 | self_referential |     128 |       0.64  |           200 |
| owner        |      5 | self_referential |     127 |       0.635 |           200 |
| owner        |      4 | self_referential |     126 |       0.63  |           200 |
| owner        |      9 | self_referential |     123 |       0.615 |           200 |
| owner        |      6 | self_referential |     122 |       0.61  |           200 |
| owner        |     13 | self_referential |     117 |       0.585 |           200 |
| owner        |     12 | self_referential |     114 |       0.57  |           200 |
| owner        |     10 | self_referential |     113 |       0.565 |           200 |

## Summary

- `reason_text_length_by_year.csv` captures REASON length and truncation flags per construct-year-decision.
- `reason_vocabulary_by_construct.csv` and `reason_vocabulary_by_mg.csv` quantify recurring semantic motifs in the construct-specific prose.
- `reasoning_phrase_detection_by_year.csv` isolates rationalization phrases in the main free-text justification, including `past_reference`.
- `audit_scores_by_year.csv` tracks both audit systems and flags year-over-year mean drops.