# R24 -- flood single-agent DISABLED arm regen (faf1bb12) + governed-vs-ungoverned contrast, 2026-09-17

**Method.** Part 1: same 6 collapsed metrics and band rule as r23 (new 5-seed mean inside old mean +/- 2*sd(old), ddof=1), applied to `JOH_disabled_gemma3_4b_faf1bb12/Run_{42..46}` vs `r4`(arm=ungoverned)/`r7`(noval_arm=live)/`r11` old values; rejection/retry are not banded because the old no-validator side is exactly 0 on every seed. Unlike r23's governed arm, the old disabled corpus's real 5 seeds ARE {42,43,44,45,46} (verified: r4's `run_2_seed4202`/`run_3_seed4203` are empty for arm=ungoverned) -- position and literal seed coincide here. Part 2: governed-vs-ungoverned diff = ungoverned - governed, paired by literal seed on the NEW corpus (n=5, df=4) and by RUN POSITION on the OLD corpus (n=5, df=4, since governed's own old positions 2/3 are seeds 4202/4203 per r23); the OLD contrast is cross-checked against r7's own precomputed stats (sign-flipped to match this script's convention) and raises on disagreement.

## Part 1 -- disabled arm band check (new 5-seed mean vs old mean +/- 2sd(old))

| metric | old mean +/- sd | new mean +/- sd | band | verdict |
|---|---:|---:|---|:---:|
| IBR unconditional (%) | 7.412 +/- 0.761 | 8.912 +/- 0.722 | [5.891, 8.933] | **PASS** |
| IBR tp_not_medium (%) | 14.218 +/- 0.772 | 17.268 +/- 0.824 | [12.675, 15.761] | **FAIL** |
| IBR tp_high (%) | 22.560 +/- 3.640 | 20.935 +/- 1.548 | [15.280, 29.841] | **PASS** |
| EHE pooled simlog | 0.786 +/- 0.040 | 0.863 +/- 0.030 | [0.707, 0.865] | **PASS** |
| Rejection rate (%) | 0.000 +/- 0.000 | 0.000 +/- 0.000 | n/a (old all-zero) | no-band |
| Retry rate (%) | 0.000 +/- 0.000 | 0.000 +/- 0.000 | n/a (old all-zero) | no-band |

3/4 banded metrics PASS (rejection/retry rate excluded from banding: old side is 0 on every seed).

## Part 2 -- governed-vs-ungoverned contrast, NEW vs OLD corpus (diff = ungoverned - governed)

| metric | NEW mean_diff +/- sd | NEW p_paired_t | NEW sign-consistent | OLD mean_diff +/- sd | OLD p_paired_t | OLD sign-consistent |
|---|---:|---:|:---:|---:|---:|:---:|
| IBR unconditional (%) | 8.124 +/- 0.543 | 0.0000 | True | 6.544 +/- 0.915 | 0.0001 | True |
| IBR tp_not_medium (%) | 15.645 +/- 0.654 | 0.0000 | True | 12.615 +/- 1.450 | 0.0000 | True |
| IBR tp_high (%) | 18.731 +/- 2.179 | 0.0000 | True | 20.050 +/- 2.410 | 0.0000 | True |
| EHE pooled simlog | 0.003 +/- 0.023 | 0.7521 | False | -0.075 +/- 0.072 | 0.0785 | False |
| Rejection rate (%) | -0.882 +/- 0.462 | 0.0129 | True | -1.071 +/- 1.060 | 0.0867 | True |
| Retry rate (%) | -8.727 +/- 1.467 | 0.0002 | True | -8.357 +/- 3.823 | 0.0081 | True |

Headline cell (IBR unconditional, executed-equivalent): OLD governed vs ungoverned mean_diff 6.544 pp (old means ~0.87 gov / ~7.41 ungov, per r4); NEW mean_diff 8.124 pp.

## Part 3 -- disabled arm run-level stats (new runs only)

| seed | rows | llm_success=False | APPROVED | REJECTED | REJECTED_FALLBACK | wall (h) |
|---|---:|---:|---:|---:|---:|---:|
| 42 | 927 | 0 | 927 | 0 | 0 | 0.92 |
| 43 | 911 | 0 | 911 | 0 | 0 | 0.91 |
| 44 | 776 | 0 | 776 | 0 | 0 | 0.79 |
| 45 | 899 | 0 | 899 | 0 | 0 | 0.93 |
| 46 | 915 | 0 | 915 | 0 | 0 | 0.97 |

## Plain read

The regenerated disabled (no-validator) arm falls inside the old mean +/- 2 sd band on 3/4 banded metrics; IBR tp_not_medium (%) is outside it (new 17.268 vs band upper 15.761), higher than the old value on all 5 seeds. The governed-vs-ungoverned contrast -- the claim this corpus actually supports -- is what reproduces: all 3 IBR conditionings agree in sign on all 5 seeds in both the NEW (True) and OLD (True) corpus, headlined by unconditional IBR at 6.54 pp old vs 8.12 pp new. EHE is sign-consistent on neither corpus (p_paired_t 0.75 new, 0.08 old -- not significant either time). All 5 new disabled-arm runs are `integrity_ok`, `llm_success` clean at 0 failures, all rows `APPROVED` (0 rejections, 0 retries), consistent with a no-validator arm having no rejection mechanism to fire. The OLD-corpus contrast for the 3 IBR conditionings and EHE is cross-checked against r7_seed_robustness.csv's own precomputed statistics and agrees to within 5e-4 on every one (rejection/retry rate have no such r7 record, so only the values computed directly in this script back them).
