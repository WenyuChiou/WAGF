# Skill Proposal Reasoning Taxonomy

Trace dir: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_42/gemma4_e4b_strict`

## Construct REASON Length Summary

| construct   |   char_count_mean |   token_count_mean |   truncation_rate |
|:------------|------------------:|-------------------:|------------------:|
| CP          |           151.662 |            22.6738 |                 0 |
| PA          |           107.908 |            16.73   |                 0 |
| SC          |           112.63  |            16.9492 |                 0 |
| SP          |           123.535 |            18.4504 |                 0 |
| TP          |           138.932 |            21.7923 |                 0 |

## Highest-Frequency Construct Vocabulary Families

| agent_type   |   year | construct   | keyword_family   |   count |   frequency |   n_decisions |
|:-------------|-------:|:------------|:-----------------|--------:|------------:|--------------:|
| owner        |      6 | PA          | attachment       |     200 |       1     |           200 |
| owner        |      8 | PA          | attachment       |     199 |       0.995 |           200 |
| owner        |      4 | PA          | attachment       |     199 |       0.995 |           200 |
| owner        |     12 | PA          | attachment       |     199 |       0.995 |           200 |
| owner        |      2 | PA          | attachment       |     198 |       0.99  |           200 |
| owner        |      4 | SC          | community_ties   |     197 |       0.985 |           200 |
| owner        |      7 | SC          | community_ties   |     197 |       0.985 |           200 |
| owner        |     10 | SC          | community_ties   |     196 |       0.98  |           200 |
| owner        |     12 | SC          | community_ties   |     196 |       0.98  |           200 |
| owner        |      8 | SC          | community_ties   |     196 |       0.98  |           200 |
| owner        |     13 | PA          | attachment       |     196 |       0.98  |           200 |
| owner        |      9 | SC          | community_ties   |     196 |       0.98  |           200 |
| owner        |      5 | PA          | attachment       |     195 |       0.975 |           200 |
| owner        |      2 | SC          | community_ties   |     195 |       0.975 |           200 |
| owner        |      6 | SC          | community_ties   |     195 |       0.975 |           200 |

## Audit Score Trajectory

|   year | agent_type   |   demographic_audit_mean |   semantic_correlation_audit_mean | demographic_audit_drop   | semantic_correlation_audit_drop   |   n_decisions |
|-------:|:-------------|-------------------------:|----------------------------------:|:-------------------------|:----------------------------------|--------------:|
|      1 | owner        |                   1      |                           0       | False                    | False                             |           200 |
|      2 | owner        |                   1      |                           0.12705 | False                    | False                             |           200 |
|      3 | owner        |                   1      |                           0.19965 | False                    | False                             |           200 |
|      4 | owner        |                   1      |                           0.198   | False                    | True                              |           200 |
|      5 | owner        |                   1      |                           0.0957  | False                    | True                              |           200 |
|      6 | owner        |                   1      |                           0.09735 | False                    | False                             |           200 |
|      7 | owner        |                   1      |                           0.10065 | False                    | False                             |           200 |
|      8 | owner        |                   1      |                           0.1023  | False                    | False                             |           200 |
|      9 | owner        |                   1      |                           0.10065 | False                    | True                              |           200 |
|     10 | owner        |                   1      |                           0.099   | False                    | True                              |           200 |
|     11 | owner        |                   0.99   |                           0       | True                     | True                              |           200 |
|     12 | owner        |                   1      |                           0       | False                    | False                             |           200 |
|     13 | owner        |                   1      |                           0       | False                    | False                             |           200 |
|      1 | renter       |                   1      |                           0       | False                    | False                             |           200 |
|      2 | renter       |                   1      |                           0.09075 | False                    | False                             |           200 |
|      3 | renter       |                   1      |                           0.1419  | False                    | False                             |           200 |
|      4 | renter       |                   1      |                           0.1353  | False                    | True                              |           200 |
|      5 | renter       |                   1      |                           0.06435 | False                    | True                              |           200 |
|      6 | renter       |                   1      |                           0.08085 | False                    | False                             |           200 |
|      7 | renter       |                   1      |                           0.07755 | False                    | True                              |           200 |
|      8 | renter       |                   1      |                           0.0759  | False                    | True                              |           200 |
|      9 | renter       |                   0.9925 |                           0.0759  | True                     | False                             |           200 |
|     10 | renter       |                   1      |                           0.0726  | False                    | True                              |           200 |
|     11 | renter       |                   1      |                           0       | False                    | True                              |           200 |
|     12 | renter       |                   0.9975 |                           0       | True                     | False                             |           200 |
|     13 | renter       |                   1      |                           0       | False                    | False                             |           200 |

## Main Reasoning Phrase Detection

| agent_type   |   year | phrase_family    |   count |   frequency |   n_decisions |
|:-------------|-------:|:-----------------|--------:|------------:|--------------:|
| owner        |      2 | self_referential |     138 |       0.69  |           200 |
| owner        |      9 | self_referential |     138 |       0.69  |           200 |
| owner        |      3 | self_referential |     136 |       0.68  |           200 |
| owner        |      4 | self_referential |     133 |       0.665 |           200 |
| owner        |      1 | self_referential |     130 |       0.65  |           200 |
| owner        |      8 | self_referential |     129 |       0.645 |           200 |
| owner        |      7 | self_referential |     128 |       0.64  |           200 |
| owner        |      6 | self_referential |     127 |       0.635 |           200 |
| owner        |     10 | self_referential |     126 |       0.63  |           200 |
| owner        |     12 | self_referential |     126 |       0.63  |           200 |
| owner        |      5 | self_referential |     123 |       0.615 |           200 |
| owner        |     13 | self_referential |     108 |       0.54  |           200 |

## Summary

- `reason_text_length_by_year.csv` captures REASON length and truncation flags per construct-year-decision.
- `reason_vocabulary_by_construct.csv` and `reason_vocabulary_by_mg.csv` quantify recurring semantic motifs in the construct-specific prose.
- `reasoning_phrase_detection_by_year.csv` isolates rationalization phrases in the main free-text justification, including `past_reference`.
- `audit_scores_by_year.csv` tracks both audit systems and flags year-over-year mean drops.