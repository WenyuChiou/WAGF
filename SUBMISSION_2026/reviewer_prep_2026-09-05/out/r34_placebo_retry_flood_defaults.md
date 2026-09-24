# R34 -- placebo-retry flood: extra attempt vs rule content

Source: `r34_placebo_retry_flood.py`. Every number below is read live from the `rows` list this script writes to the paired CSV. n=2 seeds (42, 43) throughout -- no t-test anywhere in this file.

> **Corpus: defaults.** sampling: none sent, modelfile defaults temperature 1 / top_p 0.95 / top_k 64. All three arms (placebo/strict/disabled) read the defaults corpus.

## Part 1 -- per (arm, seed) metrics

| arm | seed | n_rows | IBR uncond | IBR tp_not_medium | IBR tp_high | EHE pooled | retry rate % | n_retried | mean retries (if retried) | fallback % | LLM fail | wall h |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| placebo | 42 | 914 | 1.53 | 3.31 | 4.55 | 0.831 | 8.42 | 77 | 1.558 | 0.00 | 0 | 1.094 |
| placebo | 43 | 931 | 1.40 | 2.87 | 4.29 | 0.817 | 8.59 | 80 | 1.663 | 0.21 | 0 | 1.169 |
| strict | 42 | 874 | 0.69 | 1.38 | 2.03 | 0.878 | 9.61 | 84 | 1.310 | 0.00 | 0 | 1.009 |
| strict | 43 | 904 | 0.66 | 1.43 | 1.97 | 0.846 | 10.18 | 92 | 1.467 | 0.00 | 0 | 1.038 |
| disabled | 42 | 943 | 10.29 | 19.88 | 27.33 | 0.818 | 0.00 | 0 | n.a. (n_retried=0) | 0.00 | 0 | 0.962 |
| disabled | 43 | 951 | 11.99 | 22.22 | 28.65 | 0.804 | 0.00 | 0 | n.a. (n_retried=0) | 0.00 | 0 | 0.949 |

### Rule-id census, top 6 among retried rows

| arm | seed | rank | rule_id | count |
|---|---|---|---|---|
| placebo | 42 | 1 | extreme_threat_block | 69 |
| placebo | 42 | 2 | elevation_threat_low | 7 |
| placebo | 42 | 3 | elevation_block | 1 |
| placebo | 42 | 4 | precondition_violation | 1 |
| placebo | 43 | 1 | extreme_threat_block | 75 |
| placebo | 43 | 2 | elevation_threat_low | 5 |
| strict | 42 | 1 | extreme_threat_block | 76 |
| strict | 42 | 2 | elevation_threat_low | 4 |
| strict | 42 | 3 | relocation_threat_low | 4 |
| strict | 42 | 4 | elevation_block | 1 |
| strict | 42 | 5 | precondition_violation | 1 |
| strict | 43 | 1 | extreme_threat_block | 84 |
| strict | 43 | 2 | elevation_threat_low | 7 |
| strict | 43 | 3 | relocation_threat_low | 1 |
| disabled | 42 | -- | pending | -- |
| disabled | 43 | -- | pending | -- |

### Manifest census

| arm | seed | model | git_commit | thinking_mode | retry_feedback_mode | key present | enforced |
|---|---|---|---|---|---|---|---|
| placebo | 42 | gemma3:4b | 83fa97e1... | disabled | placebo | True | True |
| placebo | 43 | gemma3:4b | 83fa97e1... | disabled | placebo | True | True |
| strict | 42 | gemma3:4b | 83fa97e1... | disabled | full | True | False |
| strict | 43 | gemma3:4b | 83fa97e1... | disabled | full | True | False |
| disabled | 42 | gemma3:4b | 83fa97e1... | disabled | full | True | False |
| disabled | 43 | gemma3:4b | 83fa97e1... | disabled | full | True | False |

## Part 2 -- seed-paired contrasts (n=2, both per-seed values reported, no t-test)

| metric | seed | placebo | strict | disabled | placebo-strict | placebo-disabled | share on strict->disabled line |
|---|---|---|---|---|---|---|---|
| IBR unconditional (%) | 42 | 1.532 | 0.686 | 10.286 | 0.845 | -8.755 | 0.088 |
| IBR unconditional (%) | 43 | 1.396 | 0.664 | 11.987 | 0.733 | -10.591 | 0.065 |
| IBR tp_not_medium (%) | 42 | 3.310 | 1.376 | 19.877 | 1.933 | -16.567 | 0.104 |
| IBR tp_not_medium (%) | 43 | 2.870 | 1.425 | 22.222 | 1.445 | -19.352 | 0.070 |
| IBR tp_high (%) | 42 | 4.545 | 2.034 | 27.327 | 2.512 | -22.782 | 0.099 |
| IBR tp_high (%) | 43 | 4.290 | 1.974 | 28.649 | 2.317 | -24.358 | 0.087 |
| EHE pooled simlog | 42 | 0.831 | 0.878 | 0.818 | -0.047 | 0.013 | 0.782 |
| EHE pooled simlog | 43 | 0.817 | 0.846 | 0.804 | -0.029 | 0.013 | n.a. (denominator |disabled-strict| = 0.0424 < threshold 0.05) |

## Part 3 -- did the validator fire on a comparable schedule (placebo vs strict)?

| seed | placebo retry rate % | strict retry rate % | placebo top rule | strict top rule | placebo fallback % | strict fallback % | disabled fallback % |
|---|---|---|---|---|---|---|---|
| 42 | 8.42 | 9.61 | extreme_threat_block | extreme_threat_block | 0.00 | 0.00 | 0.00 |
| 43 | 8.59 | 10.18 | extreme_threat_block | extreme_threat_block | 0.21 | 0.00 | 0.00 |

## Plain read

Across the 6 non-degenerate IBR (conditioning, seed) cells, placebo sits close to STRICT on IBR (mean share 0.085, range 0.065 to 0.105, i.e. near 0) -- most of governance's measured value here looks like it comes from the EXTRA ATTEMPT existing at all (the "previous response was flagged, reconsider" framing), not from the specific rule id/reason/suggestion the retry prompt would otherwise carry.

Per-seed IBR share: seed 42: mean 0.097 (0.088, 0.105, 0.099); seed 43: mean 0.074 (0.065, 0.069, 0.087).

EHE pooled simlog CANNOT discriminate extra-attempt from rule-content here -- strict and disabled are themselves nearly identical on this metric (seed 43: |disabled-strict|=0.0424, both below the 0.05 degenerate threshold), so a placebo-vs-strict-vs-disabled share on EHE is not interpretable and is excluded from the verdict above (raw shares are still in the Part 2 table, marked n.a. with the reason).

Placebo and strict retry rates track each other closely (max per-seed gap 1.58pp), consistent with the manipulation being clean -- the validator fires on the same schedule in both, only the retry prompt's content differs.

This whole comparison is n=2 seeds (42, 43) -- no significance test is computed anywhere in this script; the per-seed numbers and their sign agreement are reported directly, and any conclusion here should be read as suggestive, not statistically established.

## Method

The 6 collapsed flood metrics (3 IBR conditionings at the final action level, EHE pooled simlog, rejection rate, retry rate) are `r23_flood_strict_regen.py::_metrics_for()`, imported, not re-derived -- the SAME definitions every other script in this package uses for these columns. `retry_feedback_mode` is reported from each run's `reproducibility_manifest.json` and value-enforced =='placebo' ONLY for the placebo arm (raises otherwise, including if the key is simply absent -- that would itself be a real finding, not something to pass silently); the strict/disabled comparator manifests are read and reported with the same fields, never enforced. Rule-id census counts each RETRIED row's `failed_rules` (pipe-delimited) once per distinct rule id per row (a row with the same rule id repeated is not double-counted), ranked by count then alphabetically, with rule ids `sorted()` before counting -- the exact fix `r27_irrigation_crossmodel_gemma4_12b.py` applied for a Python set-hash-randomization nondeterminism bug, reused here since the same pattern (splitting a pipe-delimited column into a set) recurs. share_on_strict_to_disabled_line = (placebo-strict)/(disabled-strict): 0 = placebo behaves like strict (attempt count matters), 1 = placebo behaves like disabled (rule content matters); raises on a zero denominator rather than reporting inf/nan.

All three arms (placebo, strict, disabled) were run at the same code commit 83fa97e1.
