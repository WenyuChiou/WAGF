# Skill Proposal Reasoning Taxonomy

Trace dir: `examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_123/gemma4_e4b_strict`

## Construct REASON Length Summary

| construct   |   char_count_mean |   token_count_mean |   truncation_rate |
|:------------|------------------:|-------------------:|------------------:|
| CP          |           150.218 |            22.4014 |                 0 |
| PA          |           106.363 |            16.478  |                 0 |
| SC          |           110.995 |            16.7823 |                 0 |
| SP          |           121.02  |            17.9513 |                 0 |
| TP          |           136.916 |            21.5992 |                 0 |

## Highest-Frequency Construct Vocabulary Families

| agent_type   |   year | construct   | keyword_family   |   count |   frequency |   n_decisions |
|:-------------|-------:|:------------|:-----------------|--------:|------------:|--------------:|
| owner        |      5 | PA          | attachment       |     199 |     0.995   |           200 |
| owner        |      8 | PA          | attachment       |     199 |     0.995   |           200 |
| owner        |      4 | SC          | community_ties   |     198 |     0.99    |           200 |
| owner        |     12 | SC          | community_ties   |     198 |     0.99    |           200 |
| owner        |     10 | PA          | attachment       |     198 |     0.99    |           200 |
| owner        |      7 | SC          | community_ties   |     197 |     0.98995 |           199 |
| owner        |      3 | SC          | community_ties   |     197 |     0.985   |           200 |
| owner        |      2 | PA          | attachment       |     197 |     0.985   |           200 |
| owner        |      9 | PA          | attachment       |     197 |     0.985   |           200 |
| owner        |     13 | PA          | attachment       |     197 |     0.985   |           200 |
| owner        |     12 | TP          | severity         |     197 |     0.985   |           200 |
| owner        |      9 | SC          | community_ties   |     196 |     0.98    |           200 |
| owner        |      6 | PA          | attachment       |     196 |     0.98    |           200 |
| owner        |      3 | PA          | attachment       |     196 |     0.98    |           200 |
| owner        |     12 | PA          | attachment       |     195 |     0.975   |           200 |

## Audit Score Trajectory

|   year | agent_type   |   demographic_audit_mean |   semantic_correlation_audit_mean | demographic_audit_drop   | semantic_correlation_audit_drop   |   n_decisions |
|-------:|:-------------|-------------------------:|----------------------------------:|:-------------------------|:----------------------------------|--------------:|
|      1 | owner        |                    1     |                          0        | False                    | False                             |           200 |
|      2 | owner        |                    1     |                          0.1221   | False                    | False                             |           200 |
|      3 | owner        |                    1     |                          0.2178   | False                    | False                             |           200 |
|      4 | owner        |                    1     |                          0.19635  | False                    | True                              |           200 |
|      5 | owner        |                    0.995 |                          0.0891   | True                     | True                              |           200 |
|      6 | owner        |                    1     |                          0.1089   | False                    | False                             |           200 |
|      7 | owner        |                    1     |                          0.102814 | False                    | True                              |           199 |
|      8 | owner        |                    1     |                          0.09735  | False                    | True                              |           200 |
|      9 | owner        |                    1     |                          0.099    | False                    | False                             |           200 |
|     10 | owner        |                    1     |                          0.10395  | False                    | False                             |           200 |
|     11 | owner        |                    1     |                          0        | False                    | True                              |           200 |
|     12 | owner        |                    1     |                          0        | False                    | False                             |           200 |
|     13 | owner        |                    1     |                          0        | False                    | False                             |           200 |
|      1 | renter       |                    1     |                          0        | False                    | False                             |           200 |
|      2 | renter       |                    1     |                          0.1089   | False                    | False                             |           200 |
|      3 | renter       |                    1     |                          0.16005  | False                    | False                             |           200 |
|      4 | renter       |                    0.995 |                          0.16665  | True                     | False                             |           200 |
|      5 | renter       |                    1     |                          0.0594   | False                    | True                              |           200 |
|      6 | renter       |                    1     |                          0.08415  | False                    | False                             |           200 |
|      7 | renter       |                    0.995 |                          0.07425  | True                     | True                              |           200 |
|      8 | renter       |                    0.995 |                          0.0759   | False                    | False                             |           200 |
|      9 | renter       |                    0.995 |                          0.07755  | False                    | False                             |           200 |
|     10 | renter       |                    0.995 |                          0.0759   | False                    | True                              |           200 |
|     11 | renter       |                    0.995 |                          0        | False                    | True                              |           200 |
|     12 | renter       |                    1     |                          0        | False                    | False                             |           200 |
|     13 | renter       |                    0.995 |                          0        | True                     | False                             |           200 |

## Main Reasoning Phrase Detection

| agent_type   |   year | phrase_family    |   count |   frequency |   n_decisions |
|:-------------|-------:|:-----------------|--------:|------------:|--------------:|
| owner        |      2 | self_referential |     144 |    0.72     |           200 |
| owner        |      1 | self_referential |     140 |    0.7      |           200 |
| owner        |      3 | self_referential |     136 |    0.68     |           200 |
| owner        |     10 | self_referential |     136 |    0.68     |           200 |
| owner        |      7 | self_referential |     134 |    0.673367 |           199 |
| owner        |      8 | self_referential |     128 |    0.64     |           200 |
| owner        |      4 | self_referential |     127 |    0.635    |           200 |
| owner        |      6 | self_referential |     126 |    0.63     |           200 |
| owner        |      9 | self_referential |     126 |    0.63     |           200 |
| owner        |      5 | self_referential |     122 |    0.61     |           200 |
| owner        |     13 | self_referential |     114 |    0.57     |           200 |
| owner        |     11 | self_referential |     114 |    0.57     |           200 |

## Summary

- `reason_text_length_by_year.csv` captures REASON length and truncation flags per construct-year-decision.
- `reason_vocabulary_by_construct.csv` and `reason_vocabulary_by_mg.csv` quantify recurring semantic motifs in the construct-specific prose.
- `reasoning_phrase_detection_by_year.csv` isolates rationalization phrases in the main free-text justification, including `past_reference`.
- `audit_scores_by_year.csv` tracks both audit systems and flags year-over-year mean drops.