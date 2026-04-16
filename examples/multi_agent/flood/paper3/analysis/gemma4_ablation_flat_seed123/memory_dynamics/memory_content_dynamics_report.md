# Memory Content Dynamics

Trace dir: `examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_123/gemma4_e4b_strict`

## Latest-Year Memory Size

|   year | agent_type   | mg   |   mem_pre_mean |   mem_post_mean |   accumulation_mean |   n_decisions |
|-------:|:-------------|:-----|---------------:|----------------:|--------------------:|--------------:|
|     13 | owner        | MG   |              3 |           54.41 |               51.41 |           100 |
|     13 | owner        | NMG  |              3 |           53.91 |               50.91 |           100 |
|     13 | renter       | MG   |              3 |           53.77 |               50.77 |           100 |
|     13 | renter       | NMG  |              3 |           53.73 |               50.73 |           100 |

## Latest-Year New Writes

|   year | agent_type   | mg   |   agent_self_report_new_mean |   new_writes_mean |   n_decisions |
|-------:|:-------------|:-----|-----------------------------:|------------------:|--------------:|
|     13 | owner        | MG   |                            0 |             47.94 |           100 |
|     13 | owner        | NMG  |                            0 |             47.78 |           100 |
|     13 | renter       | MG   |                            0 |             47.7  |           100 |
|     13 | renter       | NMG  |                            0 |             47.42 |           100 |

## Highest Agent Self Report Counts

No agent_self_report entries found.

## Most Common Rationalization Phrase Families

|   year | agent_type   | phrase_family    |   count |   frequency |
|-------:|:-------------|:-----------------|--------:|------------:|
|      4 | renter       | self_referential |     178 |   0.0741667 |
|      5 | renter       | self_referential |     178 |   0.0556598 |
|      6 | renter       | self_referential |     178 |   0.0446227 |
|      7 | renter       | self_referential |     178 |   0.0372151 |
|      4 | owner        | self_referential |     171 |   0.07125   |
|      5 | owner        | self_referential |     171 |   0.0534542 |
|      6 | owner        | self_referential |     171 |   0.0428035 |
|      8 | owner        | self_referential |     171 |   0.0306122 |

## Summary

- `memory_size_by_year.csv` reports pre/post memory load by year, tenure, and MG status.
- `memory_content_type_by_year.csv` and `memory_category_by_year.csv` expose the semantic composition of accumulated memory.
- `memory_rationalization_phrases_by_year.csv` isolates new memory writes and measures first-person rationalization markers.
- `memory_new_writes_by_decision_year.csv` is the direct ratchet-rate table, with `agent_self_report_new_mean` as the key metric.