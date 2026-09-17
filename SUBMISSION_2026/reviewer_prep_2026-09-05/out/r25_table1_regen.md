# R25 -- paper Table 1, old vs new, all governance arms, 2026-09-17

**Method.** Cell = "old mean +/- sd / new mean +/- sd" (ddof=1, n=5 seeds 42-46 on every row, including FQL which has 10 old+10 new seeds on disk -- only the first 5 are used here to match every other row). `n.a.` = the arm has no such quantity; `no old record` = the quantity applies but no old per-seed value exists in any out/*.csv (checked, never invented). **Irrigation EHE (round-2 fix):** r25's `EHE pooled (executed)` is NOT sourced from any function in `examples/irrigation_abm/analysis/` -- it is inline code matching `r14_advise_arm.py`'s own convention (`audit_executed_metrics`), built on `_common.py::irr_executed` + `_common.py::normalized_entropy`. The canonical analysis module DOES expose a second definition: `examples/irrigation_abm/analysis/a1_ablation_metrics.py::ehe_5skill` (its own docstring: "primary metric -- paper uses k=5 for irrigation"), pooled entropy over simulation_log `yearly_decision` (proposal-level, k=5) -- added here as the separate `EHE pooled (proposal)` column (matches r14's own `ehe_pooled_proposal` column and regen_progress's "EHE pooled, proposal" row, crosschecked below). IBR headline = proposal-level conditional high-WSA increase rate (`_loader.ibr`, simulation_log). FQL's IBR/EHE use a LOCAL 3-category definition (`increase_demand` vs the LLM's 5-skill vocabulary); its EHE is k=3, its proposal-level IBR reads the RAW pre-block `fql_raw_skill` column, not `yearly_decision` (which is already post-block executed -- see docstring). **Flood EHE / protection-share (round-2/3 fix):** rule-based EHE now uses the EXACT same action classification as `paper/nature_water/scripts/regen/gen_fig3_regen.py::_rulebased_action` (elevated+has_insurance -> buy_insurance, elevated alone -> elevate_house, has_insurance alone -> buy_insurance, relocated -> relocate, else do_nothing), crosschecked LIVE against a direct call into `gen_fig3_regen.py::_ehe_from_decisions` (imported read-only, no hardcoded reference numbers -- see the EHE pooled (executed)/rule-based per-cell caveat below for the live mean/sd this run actually produced) -- gen_fig3's own sd convention is numpy `.std()`'s DEFAULT ddof=0 population sd, NOT this package's ddof=1 sample sd (`_loader.py::sd`'s docstring: "Sample standard deviation (n-1)"); both are reported, never silently reconciled into one. "Final-year share with any protection" is computed IDENTICALLY for all three flood arms from simulation_log.csv's own boolean columns at year=10: elevated OR has_insurance OR RELOCATED (relocated counts as protected -- the one rule, applied everywhere), crosschecked against gen_fig3's own `_classify_state_from_cols` pooled-all-year complement of "No protection" (gen_fig3 has no year-10-only print, so the crosscheck is on the all-year-pooled share, not the year-10 slice actually reported in Table 1). `elevated` and `relocated` never revert (0 flips in all 15 runs); `has_insurance` lapses and is repurchased (127-163 True->False flips per run, see the flip-check table below), so the year-10 protection share mixes cumulative uptake (elevation, relocation) with a year-10 snapshot (insurance) -- values are far higher than the AUDIT-based method this script used before the round-2 fix. Governed/no-validator's OLD side for this metric is `no old record` (the old raw simulation_log no longer exists); the old AUDIT-based number from `r2_flood_trajectories.csv` is kept as a reference note only, a different metric, never substituted.

| case / arm | n | IBR headline | EHE pooled (executed) | EHE pooled (proposal) | domain outcome: Mead min (ft) | domain outcome: shortage years | domain outcome: final-year protection % | rejection rate % | retry rate % | LLM failures | governance fallback % | wall h per run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| irrigation: governed (strict) | 5/5 | 36.052 +/- 3.597 / 31.413 +/- 5.474 | 0.170 +/- 0.043 / 0.153 +/- 0.044 | 0.672 +/- 0.046 / 0.647 +/- 0.039 | 989.801 +/- 14.467 / 996.247 +/- 1.214 | 14.800 +/- 1.923 / 15.200 +/- 1.789 | n.a. | 39.493 +/- 4.602 / 38.266 +/- 4.076 | no old record / 63.779 +/- 3.026 | no old record / 0.000 +/- 0.000 | no old record / 1.215 +/- 0.132 | no old record / 3.176 +/- 0.123 |
| irrigation: ungoverned | 5/5 | 59.070 +/- 1.659 / 56.640 +/- 2.099 | 0.810 +/- 0.026 / 0.818 +/- 0.015 | 0.857 +/- 0.011 / 0.872 +/- 0.005 | 895.000 +/- 0.000 / 895.000 +/- 0.000 | 38.200 +/- 0.837 / 38.000 +/- 1.000 | n.a. | 29.041 +/- 2.491 / 26.105 +/- 1.787 | no old record / 34.322 +/- 2.251 | no old record / 0.000 +/- 0.000 | no old record / 0.043 +/- 0.051 | no old record / 2.494 +/- 0.079 |
| irrigation: irrigation rule-based FQL rebalanced | 5/5 | 87.436 +/- 2.293 / 87.180 +/- 2.564 | 0.365 +/- 0.036 / 0.354 +/- 0.036 | n.a. / n.a. | 998.102 +/- 2.163 / 998.440 +/- 1.250 | 13.800 +/- 1.923 / 14.000 +/- 1.414 | n.a. | n.a. / n.a. | n.a. / n.a. | n.a. / n.a. | n.a. / n.a. | 0.001 +/- 0.000 / 0.001 +/- 0.000 |
| irrigation: irrigation rule-based FQL matched (no-rebalance) | 5/5 | 87.436 +/- 2.293 / 87.180 +/- 2.564 | 0.348 +/- 0.056 / 0.333 +/- 0.033 | n.a. / n.a. | 998.134 +/- 2.193 / 998.481 +/- 1.250 | 13.600 +/- 1.517 / 13.200 +/- 0.837 | n.a. | n.a. / n.a. | n.a. / n.a. | n.a. / n.a. | n.a. / n.a. | 0.000 +/- 0.000 / 0.001 +/- 0.000 |
| flood: governed (strict) | 5/5 | 0.868 +/- 0.907 / 0.788 +/- 0.434 | 0.861 +/- 0.044 / 0.859 +/- 0.011 | 0.861 +/- 0.044 / 0.859 +/- 0.011 | n.a. | n.a. | no old record / 100.000 +/- 0.000 | 1.071 +/- 1.060 / 0.882 +/- 0.462 | no old record / 8.727 +/- 1.467 | no old record / 0.000 +/- 0.000 | no old record / 0.094 +/- 0.102 | no old record / 1.011 +/- 0.039 |
| flood: no-validator | 5/5 | 7.412 +/- 0.761 / 8.912 +/- 0.722 | 0.786 +/- 0.040 / 0.863 +/- 0.030 | 0.786 +/- 0.040 / 0.863 +/- 0.030 | n.a. | n.a. | no old record / 100.000 +/- 0.000 | 0.000 +/- 0.000 / 0.000 +/- 0.000 | no old record / 0.000 +/- 0.000 | no old record / 0.000 +/- 0.000 | no old record / 0.000 +/- 0.000 | no old record / 0.903 +/- 0.069 |
| flood: rule-based | 5/5 | n.a. / n.a. | 0.598 +/- 0.019 / 0.598 +/- 0.019 | n.a. / n.a. | n.a. | n.a. | 96.600 +/- 2.074 / 96.600 +/- 2.074 | n.a. / n.a. | n.a. / n.a. | n.a. / n.a. | n.a. / n.a. | 0.000 +/- 0.000 / 0.001 +/- 0.000 |

Cells with `no old record` (18): irrigation/governed (strict)/retry rate %; irrigation/governed (strict)/LLM failures; irrigation/governed (strict)/governance fallback %; irrigation/governed (strict)/wall h per run; irrigation/ungoverned/retry rate %; irrigation/ungoverned/LLM failures; irrigation/ungoverned/governance fallback %; irrigation/ungoverned/wall h per run; flood/governed (strict)/domain outcome: final-year protection %; flood/governed (strict)/retry rate %; flood/governed (strict)/LLM failures; flood/governed (strict)/governance fallback %; flood/governed (strict)/wall h per run; flood/no-validator/domain outcome: final-year protection %; flood/no-validator/retry rate %; flood/no-validator/LLM failures; flood/no-validator/governance fallback %; flood/no-validator/wall h per run

Per-cell caveats:
- irrigation/governed (strict)/wall h per run: new mean/sd cross-checked equal to r21_compute_cost_by_arm.csv irrigation_strict row (3.1762)
- irrigation/irrigation rule-based FQL rebalanced/EHE pooled (executed): k=3 action space (increase_demand/maintain_demand/decrease_demand), NOT comparable to the LLM arms' k=5 EHE
- irrigation/irrigation rule-based FQL rebalanced/EHE pooled (proposal): FQL's true raw proposal space is Hung & Yang's binary increase/decrease (k=2, from fql_raw_skill), not the LLM's 5-skill space -- no k=5 proposal EHE exists for this arm
- irrigation/irrigation rule-based FQL rebalanced/rejection rate %: rule-based has no LLM audit trail
- irrigation/irrigation rule-based FQL rebalanced/retry rate %: rule-based has no LLM audit trail
- irrigation/irrigation rule-based FQL rebalanced/LLM failures: rule-based has no LLM audit trail
- irrigation/irrigation rule-based FQL rebalanced/governance fallback %: rule-based has no LLM audit trail
- irrigation/irrigation rule-based FQL matched (no-rebalance)/EHE pooled (executed): k=3 action space (increase_demand/maintain_demand/decrease_demand), NOT comparable to the LLM arms' k=5 EHE
- irrigation/irrigation rule-based FQL matched (no-rebalance)/EHE pooled (proposal): FQL's true raw proposal space is Hung & Yang's binary increase/decrease (k=2, from fql_raw_skill), not the LLM's 5-skill space -- no k=5 proposal EHE exists for this arm
- irrigation/irrigation rule-based FQL matched (no-rebalance)/rejection rate %: rule-based has no LLM audit trail
- irrigation/irrigation rule-based FQL matched (no-rebalance)/retry rate %: rule-based has no LLM audit trail
- irrigation/irrigation rule-based FQL matched (no-rebalance)/LLM failures: rule-based has no LLM audit trail
- irrigation/irrigation rule-based FQL matched (no-rebalance)/governance fallback %: rule-based has no LLM audit trail
- flood/governed (strict)/EHE pooled (proposal): identical to EHE pooled (executed) -- flood's proposal/final/executed levels coincide row-for-row, proven in r23 (0 mismatches, all 5 seeds)
- flood/governed (strict)/domain outcome: final-year protection %: no old value for THIS metric (simulation_log boolean OR, relocated counts as protected) -- the old raw simulation_log no longer exists. A DIFFERENT metric (audit-based, 100-share_do_nothing at year 10) has an old value of 71.5+/-6.8% from r2_flood_trajectories.csv, kept for reference only, not substituted
- flood/no-validator/EHE pooled (proposal): identical to EHE pooled (executed) -- flood's proposal/final/executed levels coincide row-for-row, proven in r23/r24 (0 mismatches)
- flood/no-validator/domain outcome: final-year protection %: no old value for THIS metric (simulation_log boolean OR, relocated counts as protected) -- the old raw simulation_log no longer exists. A DIFFERENT metric (audit-based, 100-share_do_nothing at year 10) has an old value of 56.9+/-7.4% from r2_flood_trajectories.csv, kept for reference only, not substituted
- flood/rule-based/IBR headline: no threat-appraisal (construct_TP_LABEL) column in the rule-based simulation_log -- R1/R3/R4 all condition on it, so IBR is undefined for this row, not silently substituted
- flood/rule-based/EHE pooled (executed): mapping matches gen_fig3_regen.py's _rulebased_action exactly (live crosscheck via FIG3._ehe_from_decisions: mean 0.598 = this script's 0.598; this script's sd 0.019 is ddof=1 sample sd per package convention, gen_fig3's own ddof=0 population sd for the same 5 values is 0.017 -- both reported, not silently reconciled)
- flood/rule-based/EHE pooled (proposal): no separate proposal stage in a deterministic rule-based baseline (unlike FQL, there is no raw-vs-blocked distinction here)
- flood/rule-based/domain outcome: final-year protection %: same rule as governed/no-validator (simulation_log boolean OR, relocated counts as protected, all 100 agents, year 10) -- old and new both computable here since the old raw simulation_log for rule-based (unlike governed/no-validator) was never destroyed
- flood/rule-based/rejection rate %: rule-based has no LLM audit trail
- flood/rule-based/retry rate %: rule-based has no LLM audit trail
- flood/rule-based/LLM failures: rule-based has no LLM audit trail
- flood/rule-based/governance fallback %: rule-based has no LLM audit trail

## Flip-check: True->False agent-year transitions, new corpus, per (arm, column), across the 5 seeds

| arm | elevated | has_insurance | relocated |
|---|---:|---:|---:|
| governed (strict) | 0-0 (mean 0.0) | 135-159 (mean 148.6) | 0-0 (mean 0.0) |
| no-validator | 0-0 (mean 0.0) | 127-163 (mean 142.2) | 0-0 (mean 0.0) |
| rule-based | 0-0 (mean 0.0) | 143-161 (mean 149.6) | 0-0 (mean 0.0) |

## Governed-vs-ungoverned contrast (diff = ungoverned - governed)

| case | metric | corpus | mean_diff +/- sd | p_paired_t | p_exact_perm | sign-consistent |
|---|---|---|---:|---:|---:|:---:|
| irrigation | IBR headline | old | 23.018 +/- 3.187 | 0.0001 | 0.0625 | True |
| irrigation | IBR headline | new | 25.227 +/- 7.054 | 0.0013 | 0.0625 | True |
| irrigation | EHE pooled | old | 0.640 +/- 0.049 | 0.0000 | 0.0625 | True |
| irrigation | EHE pooled | new | 0.664 +/- 0.045 | 0.0000 | 0.0625 | True |
| flood | IBR headline | old | 6.544 +/- 0.915 | 0.0001 | 0.0625 | True |
| flood | IBR headline | new | 8.124 +/- 0.543 | 0.0000 | 0.0625 | True |
| flood | EHE pooled | old | -0.075 +/- 0.072 | 0.0785 | 0.1250 | False |
| flood | EHE pooled | new | 0.003 +/- 0.023 | 0.7521 | 0.9375 | False |

Both cases reproduce the governed-vs-ungoverned direction on the new corpus: irrigation IBR headline mean_diff 23.02 pp old vs 25.23 pp new (sign-consistent old=True, new=True); flood IBR headline mean_diff 6.54 pp old vs 8.12 pp new (sign-consistent old=True, new=True).
