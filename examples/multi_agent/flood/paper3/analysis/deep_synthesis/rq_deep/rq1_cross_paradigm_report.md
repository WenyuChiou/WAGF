# RQ1 Deep Cross-Paradigm Comparison

Source: `examples/multi_agent/flood/paper3/analysis/deep_synthesis/figures/fig_rq1_dual_timeseries.csv`

All rates use the existing yearly means from `fig_rq1_dual_timeseries.csv`. 
Mean values are stored as 0-1 rates; `mad_pp` is reported in percentage points.

## Classification Matrix

|                                      | CLEAN_Flat          | CLEAN_Full          | LEGACY_Full         |
|:-------------------------------------|:--------------------|:--------------------|:--------------------|
| ('owner', 'buy_insurance')           | DIVERGE             | DIVERGE             | DIVERGE             |
| ('owner', 'buyout_program')          | MAGNITUDE_CONVERGE  | MAGNITUDE_CONVERGE  | MAGNITUDE_CONVERGE  |
| ('owner', 'do_nothing')              | TRAJECTORY_CONVERGE | TRAJECTORY_CONVERGE | DIVERGE             |
| ('owner', 'elevate_house')           | CONVERGE            | CONVERGE            | MAGNITUDE_CONVERGE  |
| ('renter', 'buy_contents_insurance') | DIVERGE             | DIVERGE             | TRAJECTORY_CONVERGE |
| ('renter', 'do_nothing')             | DIVERGE             | DIVERGE             | TRAJECTORY_CONVERGE |
| ('renter', 'relocate')               | DIVERGE             | DIVERGE             | DIVERGE             |

## Lowest-MAD Pairings

| agent_type   | action        | llm_arm    |    mad_pp |   pearson_r | classification   |
|:-------------|:--------------|:-----------|----------:|------------:|:-----------------|
| owner        | elevate_house | CLEAN_Flat |  0.928623 |   -0.63487  | CONVERGE         |
| owner        | elevate_house | CLEAN_Full |  1.05608  |   -0.564028 | CONVERGE         |
| renter       | do_nothing    | CLEAN_Full |  7.6182   |    0.33683  | DIVERGE          |
| renter       | do_nothing    | CLEAN_Flat |  7.84059  |    0.317975 | DIVERGE          |
| owner        | buy_insurance | CLEAN_Flat | 19.2557   |    0.49059  | DIVERGE          |

## Highest-Divergence Pairings

| agent_type   | action                 | llm_arm     |   mad_pp |   pearson_r | classification   |
|:-------------|:-----------------------|:------------|---------:|------------:|:-----------------|
| owner        | buy_insurance          | LEGACY_Full |  30.2383 |   -0.232922 | DIVERGE          |
| owner        | do_nothing             | LEGACY_Full |  28.9499 |   -0.345126 | DIVERGE          |
| renter       | buy_contents_insurance | CLEAN_Full  |  26.3553 |    0.425761 | DIVERGE          |
| renter       | buy_contents_insurance | CLEAN_Flat  |  25.5412 |    0.413045 | DIVERGE          |
| renter       | relocate               | CLEAN_Full  |  24.1238 |    0.402298 | DIVERGE          |
