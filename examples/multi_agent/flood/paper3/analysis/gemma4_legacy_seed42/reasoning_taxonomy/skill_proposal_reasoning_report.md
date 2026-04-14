# Skill Proposal Reasoning Taxonomy

Trace dir: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict`

## Construct REASON Length Summary

| construct   |   char_count_mean |   token_count_mean |   truncation_rate |
|:------------|------------------:|-------------------:|------------------:|
| CP          |           144.456 |            21.3938 |                 0 |
| PA          |           102.426 |            15.6852 |                 0 |
| SC          |           108.283 |            16.1233 |                 0 |
| SP          |           117.685 |            17.23   |                 0 |
| TP          |           127.953 |            19.8867 |                 0 |

## Highest-Frequency Construct Vocabulary Families

| agent_type   |   year | construct   | keyword_family   |   count |   frequency |   n_decisions |
|:-------------|-------:|:------------|:-----------------|--------:|------------:|--------------:|
| owner        |      6 | SC          | community_ties   |     199 |       0.995 |           200 |
| owner        |      5 | SC          | community_ties   |     195 |       0.975 |           200 |
| owner        |      7 | TP          | severity         |     193 |       0.965 |           200 |
| owner        |      2 | SC          | community_ties   |     190 |       0.95  |           200 |
| owner        |      5 | TP          | severity         |     190 |       0.95  |           200 |
| owner        |      6 | TP          | severity         |     190 |       0.95  |           200 |
| owner        |     12 | CP          | affordability    |     190 |       0.95  |           200 |
| owner        |      4 | SC          | community_ties   |     190 |       0.95  |           200 |
| owner        |      5 | PA          | attachment       |     189 |       0.945 |           200 |
| owner        |     13 | PA          | attachment       |     189 |       0.945 |           200 |
| owner        |     13 | TP          | severity         |     189 |       0.945 |           200 |
| owner        |      8 | TP          | severity         |     188 |       0.94  |           200 |
| owner        |      2 | TP          | severity         |     188 |       0.94  |           200 |
| owner        |      3 | PA          | attachment       |     188 |       0.94  |           200 |
| owner        |     12 | TP          | severity         |     188 |       0.94  |           200 |

## Audit Score Trajectory

|   year | agent_type   |   demographic_audit_mean |   semantic_correlation_audit_mean | demographic_audit_drop   | semantic_correlation_audit_drop   |   n_decisions |
|-------:|:-------------|-------------------------:|----------------------------------:|:-------------------------|:----------------------------------|--------------:|
|      1 | owner        |                   1      |                           0       | False                    | False                             |           200 |
|      2 | owner        |                   1      |                           0.10195 | False                    | False                             |           200 |
|      3 | owner        |                   0.995  |                           0.2636  | True                     | False                             |           200 |
|      4 | owner        |                   0.995  |                           0.2512  | False                    | True                              |           200 |
|      5 | owner        |                   1      |                           0.14275 | False                    | True                              |           200 |
|      6 | owner        |                   1      |                           0.13275 | False                    | True                              |           200 |
|      7 | owner        |                   1      |                           0.20515 | False                    | False                             |           200 |
|      8 | owner        |                   1      |                           0.2125  | False                    | False                             |           200 |
|      9 | owner        |                   0.99   |                           0.1995  | True                     | True                              |           200 |
|     10 | owner        |                   0.975  |                           0.1883  | True                     | True                              |           200 |
|     11 | owner        |                   0.995  |                           0.19725 | False                    | False                             |           200 |
|     12 | owner        |                   0.995  |                           0.1917  | False                    | True                              |           200 |
|     13 | owner        |                   1      |                           0.1825  | False                    | True                              |           200 |
|      1 | renter       |                   1      |                           0       | False                    | False                             |           200 |
|      2 | renter       |                   1      |                           0.10725 | False                    | False                             |           200 |
|      3 | renter       |                   0.99   |                           0.20515 | True                     | False                             |           200 |
|      4 | renter       |                   1      |                           0.2015  | False                    | True                              |           200 |
|      5 | renter       |                   0.995  |                           0.1353  | True                     | True                              |           200 |
|      6 | renter       |                   1      |                           0.1244  | False                    | True                              |           200 |
|      7 | renter       |                   0.9925 |                           0.16525 | True                     | False                             |           200 |
|      8 | renter       |                   0.9875 |                           0.1759  | True                     | False                             |           200 |
|      9 | renter       |                   0.9925 |                           0.1597  | False                    | True                              |           200 |
|     10 | renter       |                   0.9175 |                           0.16925 | True                     | False                             |           200 |
|     11 | renter       |                   0.975  |                           0.175   | False                    | False                             |           200 |
|     12 | renter       |                   0.9925 |                           0.1804  | False                    | False                             |           200 |
|     13 | renter       |                   0.9825 |                           0.1838  | True                     | False                             |           200 |

## Main Reasoning Phrase Detection

| agent_type   |   year | phrase_family    |   count |   frequency |   n_decisions |
|:-------------|-------:|:-----------------|--------:|------------:|--------------:|
| owner        |      6 | self_referential |     144 |       0.72  |           200 |
| owner        |      3 | self_referential |     143 |       0.715 |           200 |
| owner        |      5 | self_referential |     141 |       0.705 |           200 |
| owner        |      2 | self_referential |     137 |       0.685 |           200 |
| owner        |      4 | self_referential |     134 |       0.67  |           200 |
| owner        |      7 | self_referential |     118 |       0.59  |           200 |
| owner        |      1 | self_referential |     114 |       0.57  |           200 |
| owner        |      8 | self_referential |     109 |       0.545 |           200 |
| owner        |      9 | self_referential |     102 |       0.51  |           200 |
| owner        |     10 | self_referential |     100 |       0.5   |           200 |
| owner        |     13 | self_referential |     100 |       0.5   |           200 |
| owner        |     11 | self_referential |      94 |       0.47  |           200 |

## Summary

- `reason_text_length_by_year.csv` captures REASON length and truncation flags per construct-year-decision.
- `reason_vocabulary_by_construct.csv` and `reason_vocabulary_by_mg.csv` quantify recurring semantic motifs in the construct-specific prose.
- `reasoning_phrase_detection_by_year.csv` isolates rationalization phrases in the main free-text justification, including `past_reference`.
- `audit_scores_by_year.csv` tracks both audit systems and flags year-over-year mean drops.