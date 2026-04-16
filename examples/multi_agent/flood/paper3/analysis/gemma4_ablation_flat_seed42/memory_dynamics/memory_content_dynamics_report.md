# Memory Content Dynamics

Trace dir: `C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_42/gemma4_e4b_strict`

## Latest-Year Memory Size

|   year | agent_type   | mg   |   mem_pre_mean |   mem_post_mean |   accumulation_mean |   n_decisions |
|-------:|:-------------|:-----|---------------:|----------------:|--------------------:|--------------:|
|     13 | owner        | MG   |              3 |           54.32 |               51.32 |           100 |
|     13 | owner        | NMG  |              3 |           53.83 |               50.83 |           100 |
|     13 | renter       | MG   |              3 |           53.23 |               50.23 |           100 |
|     13 | renter       | NMG  |              3 |           53.36 |               50.36 |           100 |

## Latest-Year New Writes

|   year | agent_type   | mg   |   agent_self_report_new_mean |   new_writes_mean |   n_decisions |
|-------:|:-------------|:-----|-----------------------------:|------------------:|--------------:|
|     13 | owner        | MG   |                            0 |             47.84 |           100 |
|     13 | owner        | NMG  |                            0 |             47.7  |           100 |
|     13 | renter       | MG   |                            0 |             47.12 |           100 |
|     13 | renter       | NMG  |                            0 |             47.18 |           100 |

## Highest Agent Self Report Counts

No agent_self_report entries found.

## Most Common Rationalization Phrase Families

|   year | agent_type   | phrase_family    |   count |   frequency |
|-------:|:-------------|:-----------------|--------:|------------:|
|      4 | renter       | self_referential |     178 |   0.0743836 |
|      5 | renter       | self_referential |     178 |   0.0557819 |
|      6 | renter       | self_referential |     178 |   0.0449041 |
|      7 | renter       | self_referential |     178 |   0.0375686 |
|      4 | owner        | self_referential |     171 |   0.0713094 |
|      5 | owner        | self_referential |     171 |   0.0534709 |
|      6 | owner        | self_referential |     171 |   0.0428679 |
|      7 | owner        | self_referential |     171 |   0.035789  |

## Summary

- `memory_size_by_year.csv` reports pre/post memory load by year, tenure, and MG status.
- `memory_content_type_by_year.csv` and `memory_category_by_year.csv` expose the semantic composition of accumulated memory.
- `memory_rationalization_phrases_by_year.csv` isolates new memory writes and measures first-person rationalization markers.
- `memory_new_writes_by_decision_year.csv` is the direct ratchet-rate table, with `agent_self_report_new_mean` as the key metric.