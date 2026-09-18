# R26 -- flood gemma4:12b cross-model arms (c3391a53) vs gemma3:4b (faf1bb12), 2026-09-17

**Method.** Per-run metrics reuse `r23_flood_strict_regen.py::_metrics_for` verbatim (imported); telemetry (mean prompt_tokens/response_tokens/llm_latency_ms/tokens_per_second) is read directly from the audit CSV's per-call columns (the last-call value per row, not the `_total` cumulative variants). Model-paired diff (Part 2) = gemma4:12b - gemma3:4b, literal seed 42-46. Governed-vs-ungoverned contrast (Part 3) = ungoverned - governed, same `C.paired_t`/`C.exact_perm_p` r24 uses; the gemma3:4b contrast row is read verbatim from `out/r24_flood_contrast_regen.csv`, never recomputed. Every manifest checked has its VALUES verified, not just key presence -- `thinking_mode=="disabled"`, `llm_timeout_seconds_effective==1800`, `model_quantization=="Q4_K_M"`, `model` starting with `"gemma4:12b"`, `git_commit` starting with `"c3391a53"` -- any mismatch raises naming the run, field, and offending value; `model_digest` and `git_commit` (short form) are reported per run (table below). Strict: 5/5 seeds complete. Disabled: 5/5 seeds complete.

## Part 1 -- per-seed metrics, gemma4:12b

| arm | seed | IBR unconditional (%) | IBR tp_not_medium (%) | IBR tp_high (%) | EHE pooled simlog | Rejection rate (%) | Retry rate (%) | rows | llm_fail | APPROVED | REJECTED | REJ_FALLBACK | fallback% | wall_h | mean_prompt_tok | mean_resp_tok | mean_latency_ms | mean_tok/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| strict | 42 | 0.000 | 0.000 | 0.000 | 0.599 | 0.000 | 2.733 | 988 | 0 | 988 | 0 | 0 | 0.000 | 1.66 | 920.3 | 219.1 | 5755.9 | 67.78 |
| strict | 43 | 0.000 | 0.000 | 0.000 | 0.633 | 0.000 | 2.160 | 972 | 0 | 972 | 0 | 0 | 0.000 | 1.57 | 919.5 | 219.7 | 5661.1 | 69.84 |
| strict | 44 | 0.206 | 0.250 | 1.869 | 0.640 | 0.206 | 2.270 | 969 | 0 | 967 | 2 | 0 | 0.000 | 1.60 | 910.7 | 219.6 | 5749.9 | 67.71 |
| strict | 45 | 0.200 | 0.247 | 2.198 | 0.553 | 0.200 | 1.800 | 1000 | 0 | 998 | 2 | 0 | 0.000 | 1.63 | 914.7 | 219.5 | 5701.0 | 68.74 |
| strict | 46 | 0.000 | 0.000 | 0.000 | 0.606 | 0.000 | 1.740 | 977 | 0 | 977 | 0 | 0 | 0.000 | 1.60 | 922.1 | 219.8 | 5754.1 | 67.77 |
| disabled | 42 | 1.800 | 2.209 | 10.417 | 0.535 | 0.000 | 0.000 | 1000 | 0 | 1000 | 0 | 0 | 0.000 | 1.59 | 909.9 | 218.9 | 5712.1 | 68.40 |
| disabled | 43 | 1.809 | 2.211 | 15.069 | 0.551 | 0.000 | 0.000 | 995 | 0 | 995 | 0 | 0 | 0.000 | 1.59 | 922.8 | 218.8 | 5734.3 | 67.78 |
| disabled | 44 | 1.400 | 1.733 | 10.476 | 0.560 | 0.000 | 0.000 | 1000 | 0 | 1000 | 0 | 0 | 0.000 | 1.59 | 902.6 | 220.4 | 5725.8 | 68.78 |
| disabled | 45 | 2.300 | 2.748 | 9.184 | 0.538 | 0.000 | 0.000 | 1000 | 0 | 1000 | 0 | 0 | 0.000 | 1.59 | 913.6 | 219.4 | 5716.9 | 68.65 |
| disabled | 46 | 3.200 | 3.809 | 21.951 | 0.526 | 0.000 | 0.000 | 1000 | 0 | 1000 | 0 | 0 | 0.000 | 1.59 | 922.8 | 219.4 | 5716.9 | 68.83 |

## Part 2 -- model-paired comparison, gemma4:12b vs gemma3:4b (diff = 12b - 4b)


| arm | metric | mean_diff +/- sd | p_paired_t | p_exact_perm | sign-consistent |
|---|---|---:|---:|---:|:---:|
| strict | IBR unconditional (%) | -0.707 +/- 0.448 | 0.0242 | 0.0625 | True |
| strict | IBR tp_not_medium (%) | -1.524 +/- 0.869 | 0.0172 | 0.0625 | True |
| strict | IBR tp_high (%) | -1.391 +/- 1.810 | 0.1608 | 0.2500 | False |
| strict | EHE pooled simlog | -0.253 +/- 0.029 | 0.0000 | 0.0625 | True |
| strict | Rejection rate (%) | -0.801 +/- 0.467 | 0.0185 | 0.0625 | True |
| strict | Retry rate (%) | -6.586 +/- 1.160 | 0.0002 | 0.0625 | True |
| disabled | IBR unconditional (%) | -6.810 +/- 1.303 | 0.0003 | 0.0625 | True |
| disabled | IBR tp_not_medium (%) | -14.726 +/- 1.433 | 0.0000 | 0.0625 | True |
| disabled | IBR tp_high (%) | -7.516 +/- 5.329 | 0.0344 | 0.1250 | False |
| disabled | EHE pooled simlog | -0.321 +/- 0.019 | 0.0000 | 0.0625 | True |
| disabled | Rejection rate (%) | 0.000 +/- 0.000 | n.a. (zero variance: both arms 0 on all 5 seeds) | 1.0000 | n.a. (zero variance: both arms 0 on all 5 seeds) |
| disabled | Retry rate (%) | 0.000 +/- 0.000 | n.a. (zero variance: both arms 0 on all 5 seeds) | 1.0000 | n.a. (zero variance: both arms 0 on all 5 seeds) |

## Part 3 -- governed-vs-ungoverned contrast, gemma4:12b vs gemma3:4b (diff = ungoverned - governed)

| metric | gemma4:12b mean_diff +/- sd | gemma4:12b p_paired_t | gemma3:4b mean_diff +/- sd | gemma3:4b p_paired_t | same sign across models |
|---|---:|---:|---:|---:|:---:|
| IBR unconditional (%) | 2.021 +/- 0.737 | 0.0036 | 8.124 +/- 0.543 | 0.0000 | True |
| IBR tp_not_medium (%) | 2.443 +/- 0.852 | 0.0030 | 15.645 +/- 0.654 | 0.0000 | True |
| IBR tp_high (%) | 12.606 +/- 6.037 | 0.0095 | 18.731 +/- 2.179 | 0.0000 | True |
| EHE pooled simlog | -0.064 +/- 0.028 | 0.0072 | 0.003 +/- 0.023 | 0.7521 | False |
| Rejection rate (%) | -0.081 +/- 0.111 | 0.1779 | -0.882 +/- 0.462 | 0.0129 | True |
| Retry rate (%) | -2.141 +/- 0.401 | 0.0003 | -8.727 +/- 1.467 | 0.0002 | True |

## Part 4 -- manifest fields (thinking mode, timeout floor, model)

| arm | seed | model | thinking_mode | timeout_s | model_digest | quantization | git_commit |
|---|---|---|---|---:|---|---|---|
| strict | 42 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| strict | 43 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| strict | 44 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| strict | 45 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| strict | 46 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| disabled | 42 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| disabled | 43 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| disabled | 44 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| disabled | 45 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |
| disabled | 46 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 |

## Plain read

gemma4:12b's strict arm is fully landed (5/5 seeds, all `integrity_ok`, `thinking_mode=disabled` on every manifest checked); the disabled arm is also complete. On the model-paired strict-vs-strict comparison, IBR unconditional differs by -0.71 pp (12b - 4b, p_paired_t=0.0242, sign-consistent=True across all 5 seeds). The governed-vs-ungoverned contrast keeps its sign on the larger model: unconditional IBR mean_diff (ungoverned - governed) 2.02 pp on gemma4:12b vs 8.12 pp on gemma3:4b (both positive -- governance lowers IBR on both models). No number in this report was hand-typed: every cell is rendered from the same in-memory rows the CSV is written from, and the completeness gates mean this script can be re-run unchanged once the disabled arm lands.
