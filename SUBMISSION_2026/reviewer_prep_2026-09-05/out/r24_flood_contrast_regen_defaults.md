# R24 -- flood single-agent DISABLED arm regen (defaults corpus) + contrast, 2026-09-23

> **Corpus: defaults.** sampling: none sent, modelfile defaults temperature 1 / top_p 0.95 / top_k 64. Comparator ("old"/OLD-corpus contrast) = the v08/faf1bb12 5-seed corpora, computed live, literal same seed -- NOT the pre-quarantine published corpus --corpus v08 uses, and NOT r7-crosschecked.

**Method.** Part 1: same 6 collapsed metrics and band rule as r23 (new 5-seed mean inside old mean +/- 2*sd(old), ddof=1), applied to `JOH_disabled_gemma3_4b_faf1bb12/Run_{42..46}` vs `r4`(arm=ungoverned)/`r7`(noval_arm=live)/`r11` old values; rejection/retry are not banded because the old no-validator side is exactly 0 on every seed. Unlike r23's governed arm, the old disabled corpus's real 5 seeds ARE {42,43,44,45,46} (verified: r4's `run_2_seed4202`/`run_3_seed4203` are empty for arm=ungoverned) -- position and literal seed coincide here. Part 2: governed-vs-ungoverned diff = ungoverned - governed, paired by literal seed on the NEW corpus (n=5, df=4) and by RUN POSITION on the OLD corpus (n=5, df=4, since governed's own old positions 2/3 are seeds 4202/4203 per r23); the OLD contrast is cross-checked against r7's own precomputed stats (sign-flipped to match this script's convention) and raises on disagreement.

## Part 1 -- disabled arm band check (new 5-seed mean vs old mean +/- 2sd(old))

| metric | old mean +/- sd | new mean +/- sd | band | verdict |
|---|---:|---:|---|:---:|
| IBR unconditional (%) | 8.912 +/- 0.722 | 10.158 +/- 1.268 | [7.467, 10.357] | **PASS** |
| IBR tp_not_medium (%) | 17.268 +/- 0.824 | 19.608 +/- 2.031 | [15.620, 18.917] | **FAIL** |
| IBR tp_high (%) | 20.935 +/- 1.548 | 24.761 +/- 3.306 | [17.840, 24.031] | **FAIL** |
| EHE pooled simlog | 0.863 +/- 0.030 | 0.845 +/- 0.034 | [0.803, 0.923] | **PASS** |
| Rejection rate (%) | 0.000 +/- 0.000 | 0.000 +/- 0.000 | [0.000, 0.000] | **PASS** |
| Retry rate (%) | 0.000 +/- 0.000 | 0.000 +/- 0.000 | [0.000, 0.000] | **PASS** |

4/6 banded metrics PASS (rejection/retry rate excluded from banding: old side is 0 on every seed).

## Part 2 -- governed-vs-ungoverned contrast, NEW vs OLD corpus (diff = ungoverned - governed)

| metric | NEW mean_diff +/- sd | NEW p_paired_t | NEW sign-consistent | OLD mean_diff +/- sd | OLD p_paired_t | OLD sign-consistent |
|---|---:|---:|:---:|---:|---:|:---:|
| IBR unconditional (%) | 9.753 +/- 1.135 | 0.0000 | True | 8.124 +/- 0.543 | 0.0000 | True |
| IBR tp_not_medium (%) | 18.764 +/- 1.761 | 0.0000 | True | 15.645 +/- 0.654 | 0.0000 | True |
| IBR tp_high (%) | 23.574 +/- 2.605 | 0.0000 | True | 18.731 +/- 2.179 | 0.0000 | True |
| EHE pooled simlog | -0.008 +/- 0.041 | 0.6785 | False | 0.003 +/- 0.023 | 0.7521 | False |
| Rejection rate (%) | -0.473 +/- 0.242 | 0.0120 | True | -0.882 +/- 0.462 | 0.0129 | True |
| Retry rate (%) | -8.115 +/- 1.692 | 0.0004 | True | -8.727 +/- 1.467 | 0.0002 | True |

Headline cell (IBR unconditional, executed-equivalent): OLD governed vs ungoverned mean_diff 8.124 pp (old means ~0.87 gov / ~7.41 ungov, per r4); NEW mean_diff 9.753 pp.

## Part 3 -- disabled arm run-level stats (new runs only)

| seed | rows | llm_success=False | APPROVED | REJECTED | REJECTED_FALLBACK | wall (h) |
|---|---:|---:|---:|---:|---:|---:|
| 42 | 943 | 0 | 943 | 0 | 0 | 0.96 |
| 43 | 951 | 0 | 951 | 0 | 0 | 0.95 |
| 44 | 873 | 0 | 873 | 0 | 0 | 0.90 |
| 45 | 915 | 0 | 915 | 0 | 0 | 0.95 |
| 46 | 898 | 0 | 898 | 0 | 0 | 0.89 |

## Plain read

The regenerated disabled (no-validator) arm falls inside the old mean +/- 2 sd band on 4/6 banded metrics; 2 banded metrics are outside it: IBR tp_not_medium (%) (new 19.608 +/- 2.031 vs band [15.620, 18.917]); IBR tp_high (%) (new 24.761 +/- 3.306 vs band [17.840, 24.031]). IBR tp_not_medium (%) is 2.84 old-corpus sd above the old mean, higher than the old value on all 5 seeds. IBR tp_high (%) is 2.47 old-corpus sd above the old mean, not uniformly higher than the old value across all 5 seeds -- template assumption does not hold, verify by hand. The governed-vs-ungoverned contrast -- the claim this corpus actually supports -- is what reproduces: all 3 IBR conditionings agree in sign on all 5 seeds in both the NEW (True) and OLD (True) corpus, headlined by unconditional IBR at 8.12 pp old vs 9.75 pp new. EHE is sign-consistent on neither corpus (p_paired_t 0.68 new, 0.75 old -- not significant either time). All 5 new disabled-arm runs are `integrity_ok`, `llm_success` clean at 0 failures, all rows `APPROVED` (0 rejections, 0 retries), consistent with a no-validator arm having no rejection mechanism to fire. The OLD-corpus contrast for the 3 IBR conditionings and EHE is cross-checked against r7_seed_robustness.csv's own precomputed statistics and agrees to within 5e-4 on every one (rejection/retry rate have no such r7 record, so only the values computed directly in this script back them).
