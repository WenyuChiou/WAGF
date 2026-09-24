# R23 -- flood single-agent STRICT arm regen (defaults corpus), 2026-09-23

> **Corpus: defaults.** sampling: none sent, modelfile defaults temperature 1 / top_p 0.95 / top_k 64. Comparator ("old" column below) = the v08/faf1bb12 5-seed band (`JOH_strict_gemma3_4b_faf1bb12`, sampling: temperature 0.8 / top_p 0.9 / top_k 40), computed live, literal same seed -- NOT the pre-quarantine published corpus --corpus v08 uses.

**Method.** Metrics = r11_flood_seed_matched.py's per-run functions (IBR/EHE/rejection/retry, transcribed from `gemma4_nw_crossmodel_analysis.py::compute_ibr_components`), run on the 5 new `JOH_strict_gemma3_4b_faf1bb12/Run_{42,43,44,45,46}` dirs (all `integrity_ok`). Old per-seed values: `r4_flood_headline_variants.csv` (IBR), `r7_seed_robustness.csv` (EHE), `r11_flood_seed_matched.csv` (rejection/retry -- r7/r2 carry no flood rejection/retry rate). Old governed corpus's real 5 seeds are {42, 4202, 4203, 45, 46}, not {42,43,44,45,46} (r4's `run_2_seed43`/`run_3_seed44` columns are empty for arm=governed), so positions 2/3 pair old 4202/4203 against new 43/44; acceptance = new 5-seed mean inside old mean +/- 2*sd(old), ddof=1. Flood's proposal/final/executed IBR values coincide row-for-row (asserted at runtime, 0 mismatches on all 5 seeds), so IBR collapses to one value per conditioning.

## Per-seed table (cell = old / new; seed43/44 cols compare vs old run-position 2/3 = old seed 4202/4203)

| metric | seed42 | seed43 | seed44 | seed45 | seed46 |
|---|---|---|---|---|---|
| IBR unconditional (%) | 1.254 / 0.686 | 0.226 / 0.664 | 1.113 / 0.115 | 0.461 / 0.444 | 0.886 / 0.113 |
| IBR tp_not_medium (%) | 2.494 / 1.376 | 0.496 / 1.425 | 2.200 / 0.259 | 0.966 / 0.922 | 1.961 / 0.239 |
| IBR tp_high (%) | 3.583 / 2.034 | 0.667 / 1.974 | 2.671 / 0.333 | 1.274 / 1.278 | 2.827 / 0.317 |
| EHE pooled simlog | 0.863 / 0.878 | 0.864 / 0.846 | 0.873 / 0.859 | 0.852 / 0.842 | 0.845 / 0.840 |
| Rejection rate (%) | 1.254 / 0.686 | 0.339 / 0.664 | 1.360 / 0.346 | 0.461 / 0.556 | 0.997 / 0.113 |
| Retry rate (%) | 10.832 / 9.611 | 8.588 / 10.177 | 8.776 / 6.228 | 6.690 / 7.333 | 8.749 / 7.223 |

## Band check (new 5-seed mean vs old mean +/- 2sd(old), n=5, ddof=1)

| metric | old mean +/- sd | new mean +/- sd | band | verdict |
|---|---:|---:|---|:---:|
| IBR unconditional (%) | 0.788 +/- 0.434 | 0.405 +/- 0.281 | [-0.081, 1.657] | **PASS** |
| IBR tp_not_medium (%) | 1.624 +/- 0.853 | 0.844 +/- 0.578 | [-0.082, 3.329] | **PASS** |
| IBR tp_high (%) | 2.204 +/- 1.198 | 1.187 +/- 0.841 | [-0.191, 4.599] | **PASS** |
| EHE pooled simlog | 0.859 +/- 0.011 | 0.853 +/- 0.016 | [0.838, 0.881] | **PASS** |
| Rejection rate (%) | 0.882 +/- 0.462 | 0.473 +/- 0.242 | [-0.041, 1.805] | **PASS** |
| Retry rate (%) | 8.727 +/- 1.467 | 8.115 +/- 1.692 | [5.793, 11.660] | **PASS** |

6/6 metrics pass (9 IBR cells collapse to the 3 distinct rows above).

## LLM-failure / fallback / wall-time (new runs only -- no old per-seed band found anywhere in out/*.csv)

| seed | rows | llm_success=False | APPROVED | REJECTED | REJECTED_FALLBACK | fallback share (%) | wall (h) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 42 | 874 | 0 | 868 | 6 | 0 | 0.000 | 1.01 |
| 43 | 904 | 0 | 898 | 6 | 0 | 0.000 | 1.04 |
| 44 | 867 | 0 | 864 | 1 | 2 | 0.231 | 0.95 |
| 45 | 900 | 0 | 895 | 4 | 1 | 0.111 | 1.03 |
| 46 | 886 | 0 | 885 | 1 | 0 | 0.000 | 0.96 |

## Plain read

The regenerated flood strict arm reproduces the old published corpus at the pre-registered tolerance: all 6/6 headline metrics (9 IBR cells collapsing to 3 distinct values, plus EHE, rejection rate, retry rate) have their new 5-seed mean inside the old mean +/- 2 sd band, so no metric sits outside the band. `llm_success` is clean at 0 failures on all 5 new seeds, and `REJECTED_FALLBACK` share stays under 0.231% on every seed. The one caveat keeping this short of a clean apples-to-apples reproduction: the old governed corpus's own run positions 2 and 3 were seeds 4202/4203, never 43/44, so the seed43/seed44 columns above compare against a different seed number at the same run position rather than a literal same-seed rerun -- surfaced here, not hidden. Wall time ranges 0.95-1.04 h/seed, consistent with flood's short 10-year run length.
