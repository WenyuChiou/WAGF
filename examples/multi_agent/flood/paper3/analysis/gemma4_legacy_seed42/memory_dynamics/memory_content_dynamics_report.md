# Memory Content Dynamics

Trace dir: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict`

## Latest-Year Memory Size

|   year | agent_type   | mg   |   mem_pre_mean |   mem_post_mean |   accumulation_mean |   n_decisions |
|-------:|:-------------|:-----|---------------:|----------------:|--------------------:|--------------:|
|     13 | owner        | MG   |              3 |           67.85 |               64.85 |           100 |
|     13 | owner        | NMG  |              3 |           67.58 |               64.58 |           100 |
|     13 | renter       | MG   |              3 |           65.37 |               62.37 |           100 |
|     13 | renter       | NMG  |              3 |           65.76 |               62.76 |           100 |

## Latest-Year New Writes

|   year | agent_type   | mg   |   agent_self_report_new_mean |   new_writes_mean |   n_decisions |
|-------:|:-------------|:-----|-----------------------------:|------------------:|--------------:|
|     13 | owner        | MG   |                        10.5  |             60.92 |           100 |
|     13 | owner        | NMG  |                        10.47 |             61.2  |           100 |
|     13 | renter       | MG   |                        10.12 |             59.16 |           100 |
|     13 | renter       | NMG  |                        10.02 |             59.16 |           100 |

## Highest Agent Self Report Counts

|   year | agent_type   |   count |   frequency |
|-------:|:-------------|--------:|------------:|
|     13 | owner        |    2308 |    0.17042  |
|     13 | renter       |    2231 |    0.170137 |
|     12 | owner        |    2117 |    0.169022 |
|     12 | renter       |    2041 |    0.167873 |
|     11 | owner        |    1919 |    0.167379 |
|     11 | renter       |    1847 |    0.165754 |

## Most Common Rationalization Phrase Families

|   year | agent_type   | phrase_family    |   count |   frequency |
|-------:|:-------------|:-----------------|--------:|------------:|
|     13 | owner        | self_referential |    2487 |    0.203652 |
|     13 | renter       | self_referential |    2439 |    0.206136 |
|     12 | owner        | self_referential |    2290 |    0.2039   |
|     12 | renter       | self_referential |    2248 |    0.206239 |
|     11 | owner        | self_referential |    2090 |    0.204201 |
|     11 | renter       | self_referential |    2061 |    0.207094 |
|     10 | owner        | self_referential |    1904 |    0.20546  |
|     10 | renter       | self_referential |    1892 |    0.209663 |

## Summary

- `memory_size_by_year.csv` reports pre/post memory load by year, tenure, and MG status.
- `memory_content_type_by_year.csv` and `memory_category_by_year.csv` expose the semantic composition of accumulated memory.
- `memory_rationalization_phrases_by_year.csv` isolates new memory writes and measures first-person rationalization markers.
- `memory_new_writes_by_decision_year.csv` is the direct ratchet-rate table, with `agent_self_report_new_mean` as the key metric.