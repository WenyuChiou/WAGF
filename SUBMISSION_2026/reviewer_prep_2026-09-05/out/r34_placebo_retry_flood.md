# R34 -- placebo-retry flood: extra attempt vs rule content

Source: `r34_placebo_retry_flood.py`. Every number below is read live from the `rows` list this script writes to the paired CSV. n=2 seeds (42, 43) throughout -- no t-test anywhere in this file.

## Part 1 -- per (arm, seed) metrics

| arm | seed | n_rows | IBR uncond | IBR tp_not_medium | IBR tp_high | EHE pooled | retry rate % | n_retried | mean retries (if retried) | fallback % | LLM fail | wall h |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| placebo | 42 | 859 | 1.28 | 2.59 | 3.37 | 0.865 | 9.55 | 82 | 1.683 | 0.23 | 0 | 1.036 |
| placebo | 43 | 921 | 2.06 | 4.30 | 6.25 | 0.846 | 11.40 | 105 | 1.676 | 0.11 | 0 | 1.080 |
| strict | 42 | 877 | 1.25 | 2.49 | 3.58 | 0.863 | 10.83 | 95 | 1.568 | 0.00 | 0 | 1.068 |
| strict | 43 | 885 | 0.23 | 0.50 | 0.67 | 0.864 | 8.59 | 76 | 1.368 | 0.11 | 0 | 1.001 |
| disabled | 42 | 927 | 9.71 | 18.40 | 22.16 | 0.844 | 0.00 | 0 | n.a. (n_retried=0) | 0.00 | 0 | 0.923 |
| disabled | 43 | 911 | 8.89 | 17.09 | 22.85 | 0.862 | 0.00 | 0 | n.a. (n_retried=0) | 0.00 | 0 | 0.908 |

### Rule-id census, top 6 among retried rows

| arm | seed | rank | rule_id | count |
|---|---|---|---|---|
| placebo | 42 | 1 | extreme_threat_block | 74 |
| placebo | 42 | 2 | elevation_threat_low | 8 |
| placebo | 43 | 1 | extreme_threat_block | 96 |
| placebo | 43 | 2 | elevation_threat_low | 9 |
| strict | 42 | 1 | extreme_threat_block | 89 |
| strict | 42 | 2 | elevation_threat_low | 6 |
| strict | 42 | 3 | elevation_block | 1 |
| strict | 42 | 4 | precondition_violation | 1 |
| strict | 43 | 1 | extreme_threat_block | 69 |
| strict | 43 | 2 | elevation_threat_low | 7 |
| disabled | 42 | -- | pending | -- |
| disabled | 43 | -- | pending | -- |

### Manifest census

| arm | seed | model | git_commit | thinking_mode | retry_feedback_mode | key present | enforced |
|---|---|---|---|---|---|---|---|
| placebo | 42 | gemma3:4b | 83fa97e1... | disabled | placebo | True | True |
| placebo | 43 | gemma3:4b | 83fa97e1... | disabled | placebo | True | True |
| strict | 42 | gemma3:4b | faf1bb12... | disabled | None | False | False |
| strict | 43 | gemma3:4b | faf1bb12... | disabled | None | False | False |
| disabled | 42 | gemma3:4b | faf1bb12... | disabled | None | False | False |
| disabled | 43 | gemma3:4b | faf1bb12... | disabled | None | False | False |

## Part 2 -- seed-paired contrasts (n=2, both per-seed values reported, no t-test)

| metric | seed | placebo | strict | disabled | placebo-strict | placebo-disabled | share on strict->disabled line |
|---|---|---|---|---|---|---|---|
| IBR unconditional (%) | 42 | 1.281 | 1.254 | 9.709 | 0.026 | -8.428 | 0.003 |
| IBR unconditional (%) | 43 | 2.063 | 0.226 | 8.891 | 1.837 | -6.828 | 0.212 |
| IBR tp_not_medium (%) | 42 | 2.594 | 2.494 | 18.405 | 0.100 | -15.811 | 0.006 |
| IBR tp_not_medium (%) | 43 | 4.299 | 0.496 | 17.089 | 3.802 | -12.790 | 0.229 |
| IBR tp_high (%) | 42 | 3.374 | 3.583 | 22.157 | -0.209 | -18.783 | -0.011 |
| IBR tp_high (%) | 43 | 6.250 | 0.667 | 22.849 | 5.583 | -16.599 | 0.252 |
| EHE pooled simlog | 42 | 0.865 | 0.863 | 0.844 | 0.003 | 0.022 | n.a. (denominator |disabled-strict| = 0.0189 < threshold 0.05) |
| EHE pooled simlog | 43 | 0.846 | 0.864 | 0.862 | -0.018 | -0.015 | n.a. (denominator |disabled-strict| = 0.0026 < threshold 0.05) |

## Part 3 -- did the validator fire on a comparable schedule (placebo vs strict)?

| seed | placebo retry rate % | strict retry rate % | placebo top rule | strict top rule | placebo fallback % | strict fallback % | disabled fallback % |
|---|---|---|---|---|---|---|---|
| 42 | 9.55 | 10.83 | extreme_threat_block | extreme_threat_block | 0.23 | 0.00 | 0.00 |
| 43 | 11.40 | 8.59 | extreme_threat_block | extreme_threat_block | 0.11 | 0.11 | 0.00 |

## Plain read

Across the 6 non-degenerate IBR (conditioning, seed) cells, placebo sits close to STRICT on IBR (mean share 0.115, range -0.011 to 0.252, i.e. near 0) -- most of governance's measured value here looks like it comes from the EXTRA ATTEMPT existing at all (the "previous response was flagged, reconsider" framing), not from the specific rule id/reason/suggestion the retry prompt would otherwise carry.

Per-seed IBR share: seed 42: mean -0.001 (0.003, 0.006, -0.011); seed 43: mean 0.231 (0.212, 0.229, 0.252).

EHE pooled simlog CANNOT discriminate extra-attempt from rule-content here -- strict and disabled are themselves nearly identical on this metric (seed 42: |disabled-strict|=0.0189; seed 43: |disabled-strict|=0.0026, both below the 0.05 degenerate threshold), so a placebo-vs-strict-vs-disabled share on EHE is not interpretable and is excluded from the verdict above (raw shares are still in the Part 2 table, marked n.a. with the reason).

Placebo and strict retry rates track each other closely (max per-seed gap 2.81pp), consistent with the manipulation being clean -- the validator fires on the same schedule in both, only the retry prompt's content differs.

This whole comparison is n=2 seeds (42, 43) -- no significance test is computed anywhere in this script; the per-seed numbers and their sign agreement are reported directly, and any conclusion here should be read as suggestive, not statistically established.

## Method

The 6 collapsed flood metrics (3 IBR conditionings at the final action level, EHE pooled simlog, rejection rate, retry rate) are `r23_flood_strict_regen.py::_metrics_for()`, imported, not re-derived -- the SAME definitions every other script in this package uses for these columns. `retry_feedback_mode` is reported from each run's `reproducibility_manifest.json` and value-enforced =='placebo' ONLY for the placebo arm (raises otherwise, including if the key is simply absent -- that would itself be a real finding, not something to pass silently); the strict/disabled comparator manifests are read and reported with the same fields, never enforced. Rule-id census counts each RETRIED row's `failed_rules` (pipe-delimited) once per distinct rule id per row (a row with the same rule id repeated is not double-counted), ranked by count then alphabetically, with rule ids `sorted()` before counting -- the exact fix `r27_irrigation_crossmodel_gemma4_12b.py` applied for a Python set-hash-randomization nondeterminism bug, reused here since the same pattern (splitting a pipe-delimited column into a set) recurs. share_on_strict_to_disabled_line = (placebo-strict)/(disabled-strict): 0 = placebo behaves like strict (attempt count matters), 1 = placebo behaves like disabled (rule content matters); raises on a zero denominator rather than reporting inf/nan.
