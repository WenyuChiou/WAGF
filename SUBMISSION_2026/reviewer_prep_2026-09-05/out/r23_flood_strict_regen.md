# R23 -- flood single-agent STRICT arm regen (faf1bb12) vs old published, 2026-09-16

**Method.** Metrics = r11_flood_seed_matched.py's per-run functions (IBR/EHE/rejection/retry, transcribed from `gemma4_nw_crossmodel_analysis.py::compute_ibr_components`), run on the 5 new `JOH_strict_gemma3_4b_faf1bb12/Run_{42,43,44,45,46}` dirs (all `integrity_ok`). Old per-seed values: `r4_flood_headline_variants.csv` (IBR), `r7_seed_robustness.csv` (EHE), `r11_flood_seed_matched.csv` (rejection/retry -- r7/r2 carry no flood rejection/retry rate). Old governed corpus's real 5 seeds are {42, 4202, 4203, 45, 46}, not {42,43,44,45,46} (r4's `run_2_seed43`/`run_3_seed44` columns are empty for arm=governed), so positions 2/3 pair old 4202/4203 against new 43/44; acceptance = new 5-seed mean inside old mean +/- 2*sd(old), ddof=1. Flood's proposal/final/executed IBR values coincide row-for-row (asserted at runtime, 0 mismatches on all 5 seeds), so IBR collapses to one value per conditioning.

## Per-seed table (cell = old / new; seed43/44 cols compare vs old run-position 2/3 = old seed 4202/4203)

| metric | seed42 | seed43 (old=4202) | seed44 (old=4203) | seed45 | seed46 |
|---|---|---|---|---|---|
| IBR unconditional (%) | 2.334 / 1.254 | 0.228 / 0.226 | 0.106 / 1.113 | 1.107 / 0.461 | 0.566 / 0.886 |
| IBR tp_not_medium (%) | 3.914 / 2.494 | 0.461 / 0.496 | 0.217 / 2.200 | 2.252 / 0.966 | 1.171 / 1.961 |
| IBR tp_high (%) | 6.061 / 3.583 | 0.730 / 0.667 | 0.351 / 2.671 | 3.650 / 1.274 | 1.761 / 2.827 |
| EHE pooled simlog | 0.916 / 0.863 | 0.872 / 0.864 | 0.792 / 0.873 | 0.857 / 0.852 | 0.870 / 0.845 |
| Rejection rate (%) | 2.800 / 1.254 | 0.228 / 0.339 | 0.317 / 1.360 | 1.329 / 0.461 | 0.679 / 0.997 |
| Retry rate (%) | 14.936 / 10.832 | 5.574 / 8.588 | 5.814 / 8.776 | 7.420 / 6.690 | 8.041 / 8.749 |

## Band check (new 5-seed mean vs old mean +/- 2sd(old), n=5, ddof=1)

| metric | old mean +/- sd | new mean +/- sd | band | verdict |
|---|---:|---:|---|:---:|
| IBR unconditional (%) | 0.868 +/- 0.907 | 0.788 +/- 0.434 | [-0.945, 2.681] | **PASS** |
| IBR tp_not_medium (%) | 1.603 +/- 1.514 | 1.624 +/- 0.853 | [-1.426, 4.632] | **PASS** |
| IBR tp_high (%) | 2.510 +/- 2.361 | 2.204 +/- 1.198 | [-2.212, 7.232] | **PASS** |
| EHE pooled simlog | 0.861 +/- 0.044 | 0.859 +/- 0.011 | [0.772, 0.951] | **PASS** |
| Rejection rate (%) | 1.071 +/- 1.060 | 0.882 +/- 0.462 | [-1.048, 3.190] | **PASS** |
| Retry rate (%) | 8.357 +/- 3.823 | 8.727 +/- 1.467 | [0.711, 16.003] | **PASS** |

6/6 metrics pass (9 IBR cells collapse to the 3 distinct rows above).

## LLM-failure / fallback / wall-time (new runs only -- no old per-seed band found anywhere in out/*.csv)

| seed | rows | llm_success=False | APPROVED | REJECTED | REJECTED_FALLBACK | fallback share (%) | wall (h) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 42 | 877 | 0 | 866 | 11 | 0 | 0.000 | 1.07 |
| 43 | 885 | 0 | 882 | 2 | 1 | 0.113 | 1.00 |
| 44 | 809 | 0 | 798 | 9 | 2 | 0.247 | 1.01 |
| 45 | 867 | 0 | 863 | 4 | 0 | 0.000 | 0.96 |
| 46 | 903 | 0 | 894 | 8 | 1 | 0.111 | 1.01 |

## Plain read

The regenerated flood strict arm reproduces the old published corpus at the pre-registered tolerance: all 6/6 headline metrics (9 IBR cells collapsing to 3 distinct values, plus EHE, rejection rate, retry rate) have their new 5-seed mean inside the old mean +/- 2 sd band, so no metric sits outside the band. `llm_success` is clean at 0 failures on all 5 new seeds, and `REJECTED_FALLBACK` share stays under 0.247% on every seed. The one caveat keeping this short of a clean apples-to-apples reproduction: the old governed corpus's own run positions 2 and 3 were seeds 4202/4203, never 43/44, so the seed43/seed44 columns above compare against a different seed number at the same run position rather than a literal same-seed rerun -- surfaced here, not hidden. Wall time ranges 0.96-1.07 h/seed, consistent with flood's short 10-year run length.
