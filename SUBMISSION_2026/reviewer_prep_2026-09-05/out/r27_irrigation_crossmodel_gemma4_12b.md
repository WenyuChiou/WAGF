# R27 -- irrigation gemma4:12b cross-model arms (c3391a53) vs gemma3:4b (faf1bb12), 2026-09-19

**Method.** Per-run metrics reuse `r25_table1_regen.py::_irr_llm_metrics` verbatim (imported) for IBR headline / EHE pooled (executed+proposal) / Mead min / shortage years / rejection / retry rate; telemetry (mean prompt_tokens/response_tokens/llm_latency_ms/tokens_per_second) and the think-log census are added here, same conventions as r26. Model-paired diff (Part 2) = gemma4:12b - gemma3:4b, literal seed 42-46, computed only when both models have all 5 seeds for that arm. Governed-vs-ungoverned contrast (Part 3) is scoped to the 2 metrics r25's own irrigation contrast block covers (IBR headline, EHE pooled executed) -- verified by reading `out/r25_table1_regen.csv`; the gemma3:4b row there is read verbatim, never recomputed. Manifest values are enforced (not just key presence), mirroring r26 verbatim: `thinking_mode=="disabled"`, `llm_timeout_seconds_effective==1800`, `model_quantization=="Q4_K_M"`, `model` starting with `"gemma4:12b"`, `git_commit` starting with `"c3391a53"` -- any mismatch raises naming run/field/value. Every gemma3:4b per-seed aggregate this script computes is cross-checked against r25's own recorded 5-seed mean/sd in `out/r25_table1_regen.csv` (tolerance 1e-6 after matching 4dp rounding) -- confirmed to agree on all 7 metrics x 2 arms. Strict: 5/5 seeds complete. Ungoverned: 5/5 seeds complete.

**Proposal-column semantics (round-3 addition, before-review finding):** `docs/AUDIT_SCHEMA.md`'s "Which Plane Answers What" table states plainly: "Per-attempt retry sequence | no | no | accepted gap" -- the framework's own documentation says the first-vs-later-attempt history is NOT recorded in the CSV or the JSONL, for any run. The audit writer (`broker/components/analytics/audit.py:trace_to_csv_row`, comment at the `initial_skill` key gate) is explicit about what `proposed_skill` actually is: "`skill_proposal` is reassigned on every governance retry, so `proposed_skill` records the LAST attempt and compares equal to `final_skill` on 100% of shipped rows." A first-attempt column pair does exist in the codebase (`initial_skill`/`initial_labels`/`attempt_skills`, gated by `global_config.audit.initial_proposal_columns`) but is ABSENT from every audit CSV header and every raw JSONL trace record checked in both the gemma4:12b and gemma3:4b corpora here -- that flag was off for these runs, confirmed by direct inspection, not assumed. Consequence: everything this script (and r25) calls "proposal-level" -- `ibr_headline`, the action-share breakdown, the WSA/IBR denominator in Part 1b -- is actually the POST-RETRY, validator-negotiated last attempt, not the agent's first impulse; the first impulse is an accepted gap in this corpus, recoverable nowhere. The Part 1b plain read below is worded to reflect exactly this.

## Part 1 -- per-seed metrics, gemma4:12b irrigation

| arm | seed | IBR headline | EHE pooled (executed) | EHE pooled (proposal) | Mead minimum (ft) | Shortage years | Rejection rate (%) | Retry rate (%) | rows | llm_fail | APPROVED | REJECTED | REJ_FALLBACK | fallback% | wall_h | mean_prompt_tok | mean_resp_tok | mean_latency_ms | mean_tok/s | think_lines | think_false |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| strict | 42 | 0.000 | 0.177 | 0.185 | 997.958 | 16.000 | 0.336 | 72.466 | 3276 | 0 | 3265 | 11 | 0 | 0.000 | 4.01 | 1256.4 | 178.4 | 6959.2 | 48.25 | 6250 | 6250 |
| strict | 43 | 0.000 | 0.258 | 0.262 | 1001.091 | 14.000 | 0.153 | 70.147 | 3276 | 0 | 3271 | 5 | 0 | 0.000 | 4.00 | 1257.9 | 178.4 | 6939.8 | 48.59 | 6241 | 6241 |
| strict | 44 | 0.000 | 0.203 | 0.210 | 997.944 | 14.000 | 0.275 | 76.801 | 3276 | 0 | 3267 | 9 | 0 | 0.000 | 3.98 | 1255.1 | 177.9 | 6850.2 | 49.13 | 6403 | 6403 |
| strict | 45 | 0.000 | 0.204 | 0.207 | 1000.860 | 13.000 | 0.122 | 73.382 | 3276 | 0 | 3272 | 4 | 0 | 0.000 | 4.03 | 1258.4 | 177.8 | 6936.3 | 49.03 | 6251 | 6251 |
| strict | 46 | 0.000 | 0.213 | 0.219 | 998.682 | 13.000 | 0.244 | 75.061 | 3276 | 0 | 3268 | 8 | 0 | 0.000 | 4.04 | 1258.8 | 177.7 | 6912.0 | 48.71 | 6365 | 6365 |
| ungoverned | 42 | 10.825 | 0.849 | 0.852 | 895.000 | 37.000 | 0.214 | 13.736 | 3276 | 0 | 3269 | 7 | 0 | 0.000 | 2.92 | 1209.0 | 186.7 | 7062.2 | 48.88 | 4087 | 4087 |
| ungoverned | 43 | 11.896 | 0.864 | 0.864 | 938.375 | 36.000 | 0.030 | 14.133 | 3276 | 0 | 3275 | 1 | 0 | 0.000 | 2.97 | 1206.2 | 186.9 | 7012.0 | 49.59 | 4097 | 4097 |
| ungoverned | 44 | 12.569 | 0.865 | 0.871 | 895.000 | 37.000 | 0.397 | 15.324 | 3276 | 0 | 3263 | 13 | 0 | 0.000 | 2.97 | 1204.5 | 187.1 | 7024.6 | 49.37 | 4171 | 4171 |
| ungoverned | 45 | 9.335 | 0.863 | 0.866 | 912.926 | 35.000 | 0.305 | 11.111 | 3276 | 0 | 3266 | 10 | 0 | 0.000 | 2.93 | 1197.8 | 185.8 | 7104.8 | 48.15 | 4030 | 4030 |
| ungoverned | 46 | 13.222 | 0.856 | 0.858 | 916.890 | 37.000 | 0.183 | 12.607 | 3276 | 0 | 3270 | 6 | 0 | 0.000 | 3.06 | 1211.2 | 187.1 | 7126.6 | 48.65 | 4040 | 4040 |

## Part 1b -- WSA/IBR denominator, proposal-level action shares, retry-cause census (pooled across available seeds, per arm)

Pooled by SUMMING per-run counts across every complete seed for that (model, arm) -- equivalent to concatenating the raw audit rows first, not averaging per-seed rates. Retry-cause classification is read directly from the audit CSV's own `failed_rules` (validator-triggered) and `format_retries` (parse/format-triggered) columns -- checked across every run processed: `failed_rules` is non-empty on 100% of retried rows and `n_unclassified_retry` (retry_count>0 with neither column populated) is 0 everywhere, so the CSV fully distinguishes the two failure modes here and the raw JSONL fallback was not needed (flagged below per row if that ever stops being true).

**strict**

| model | n_seeds | n_rows | WSA VL/L/M/H/VH/missing | n_highWSA | n_increase_high | IBR (audit-derived) % | action% incrL/incrS/maint/decrS/decrL/unparsed | n_retried | retry_rate % | mean retry_count (retried rows) | validator-triggered % of retries | also-parse-retry % of retries (format_retries) | final-attempt-unparsed % of retries | unclassified |
|---|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| gemma4:12b | 5 | 16380 | 4933/3962/2945/3973/567/0 | 4540 | 0 | 0.000 | 2.10/1.98/92.97/1.83/1.12/0.00 | 12051 | 73.571 | 1.12 | 100.0 | 0.0 | 0.0 | 0 |
| gemma3:4b | 5 | 16380 | 575/1203/8326/5086/991/199 | 6077 | 1915 | 31.512 | 11.34/27.48/56.61/2.86/0.49/1.21 | 10447 | 63.779 | 2.49 | 100.0 | 0.9 | 1.9 | 0 |

**ungoverned**

| model | n_seeds | n_rows | WSA VL/L/M/H/VH/missing | n_highWSA | n_increase_high | IBR (audit-derived) % | action% incrL/incrS/maint/decrS/decrL/unparsed | n_retried | retry_rate % | mean retry_count (retried rows) | validator-triggered % of retries | also-parse-retry % of retries (format_retries) | final-attempt-unparsed % of retries | unclassified |
|---|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| gemma4:12b | 5 | 16380 | 766/1646/1539/10393/2036/0 | 12429 | 1441 | 11.594 | 18.74/3.41/39.37/10.67/27.83/0.00 | 2192 | 13.382 | 1.09 | 100.0 | 0.0 | 0.0 | 0 |
| gemma3:4b | 5 | 16380 | 18/116/2848/9542/3849/7 | 13391 | 7590 | 56.680 | 30.07/30.79/20.47/17.53/1.10/0.04 | 5622 | 34.322 | 2.73 | 100.0 | 0.1 | 0.1 | 0 |

## Part 1c -- rule-id census: which rules fired, for retried rows and for REJECTED/REJECTED_FALLBACK rows (pooled across available seeds, per-seed min-max in brackets)

A row's `failed_rules` is the set of rule ids that fired at ANY point in its retry sequence (see the Method block's proposed_skill note); split on `|` into a set per row (a rule firing twice in one row's sequence counts once), so "% of retried rows" is well-defined. Top 8 by pooled % (this corpus has only 7 distinct rule ids total -- 6 named ones plus the rare `Unknown` producer `docs/AUDIT_SCHEMA.md` documents as a real, expected value (a specific format-check validator with no `metadata.rule_id`), checked here: it fires exactly once (gemma4:12b strict seed 45) -- so nothing is truncated by taking the top 8).

**strict**

_retried rows (retry_count > 0)_

| rule_id | gemma4:12b % (pooled) [seed min-max] | gemma3:4b % (pooled) [seed min-max] |
|---|---:|---:|
| demand_ceiling_stabilizer | 69.1 [68.5-69.8] | 82.2 [76.0-86.6] |
| low_threat_no_increase | 37.3 [35.5-39.5] | 2.0 [1.5-2.5] |
| demand_floor_stabilizer | 19.6 [18.2-23.1] | 9.6 [6.8-12.5] |
| curtailment_awareness | 15.0 [11.3-17.3] | 30.5 [27.1-34.6] |
| high_threat_high_cope_no_increase | 10.5 [8.7-12.3] | 53.2 [48.5-59.9] |
| supply_gap_block_increase | 7.3 [5.8-8.3] | 11.2 [10.4-12.6] |
| Unknown | 0.0 [0.0-0.0] | 0.0 [0.0-0.0] |

gemma4:12b pooled denominator = 12051 (retried rows (retry_count > 0)) over 5 seed(s); gemma3:4b pooled denominator = 10447 over 5 seed(s).

_REJECTED / REJECTED_FALLBACK rows_

| rule_id | gemma4:12b % (pooled) [seed min-max] | gemma3:4b % (pooled) [seed min-max] |
|---|---:|---:|
| low_threat_no_increase | 67.6 [33.3-100.0] | 2.7 [2.2-3.2] |
| demand_ceiling_stabilizer | 32.4 [0.0-100.0] | 86.1 [81.3-89.6] |
| demand_floor_stabilizer | 32.4 [0.0-66.7] | 9.4 [6.5-12.3] |
| curtailment_awareness | 13.5 [0.0-44.4] | 25.4 [20.7-30.0] |
| supply_gap_block_increase | 10.8 [0.0-25.0] | 11.1 [10.5-12.3] |
| high_threat_high_cope_no_increase | 8.1 [0.0-22.2] | 57.5 [52.1-64.6] |

gemma4:12b pooled denominator = 37 (REJECTED / REJECTED_FALLBACK rows) over 5 seed(s); gemma3:4b pooled denominator = 6268 over 5 seed(s).
CAUTION: gemma4:12b's REJECTED / REJECTED_FALLBACK rows denominator here is small (37) -- percentages above are noisy, shown with their denominator, not asserted as reliable.

**ungoverned**

_retried rows (retry_count > 0)_

| rule_id | gemma4:12b % (pooled) [seed min-max] | gemma3:4b % (pooled) [seed min-max] |
|---|---:|---:|
| precondition_violation | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |

gemma4:12b pooled denominator = 2192 (retried rows (retry_count > 0)) over 5 seed(s); gemma3:4b pooled denominator = 5622 over 5 seed(s).

_REJECTED / REJECTED_FALLBACK rows_

| rule_id | gemma4:12b % (pooled) [seed min-max] | gemma3:4b % (pooled) [seed min-max] |
|---|---:|---:|
| precondition_violation | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |

gemma4:12b pooled denominator = 37 (REJECTED / REJECTED_FALLBACK rows) over 5 seed(s); gemma3:4b pooled denominator = 4276 over 5 seed(s).
CAUTION: gemma4:12b's REJECTED / REJECTED_FALLBACK rows denominator here is small (37) -- percentages above are noisy, shown with their denominator, not asserted as reliable.

The recorded `proposed_skill` on gemma4:12b strict is POST-RETRY (the last attempt in each retry sequence, per the Method block's audit-writer quote), so the 0.000% IBR headline describes what the validator eventually negotiated, not the agent's first impulse -- which this corpus cannot recover (an accepted gap in both the CSV and the raw JSONL). What CAN be shown: 4540 of 16380 pooled rows have high self-reported water scarcity, the negotiated-increase count among them is exactly 0 (a substantial denominator, not a fragile small-sample one), and the retry rate itself (73.6% of all rows) is the share of decisions the validator intervened on at least once -- for gemma4:12b strict, dominated by `demand_ceiling_stabilizer` (69.1% of retried rows); `low_threat_no_increase` (37.3% of retried rows). The ungoverned arm is the un-nudged reference for the same model: gemma4:12b ungoverned's own audit-derived IBR is 11.6% on the same audit-derived measure, over 12429 high-WSA rows, i.e. far above strict's 0%, so the gap between the two arms -- not the strict arm's proposed_skill alone -- is what shows governance changing the recorded outcome.

## Part 2 -- model-paired comparison, gemma4:12b vs gemma3:4b (diff = 12b - 4b)


| arm | metric | mean_diff +/- sd | p_paired_t | p_exact_perm | sign-consistent |
|---|---|---:|---:|---:|:---:|
| strict | IBR headline | -31.413 +/- 5.474 | 0.0002 | 0.0625 | True |
| strict | EHE pooled (executed) | 0.058 +/- 0.053 | 0.0733 | 0.1250 | False |
| strict | EHE pooled (proposal) | -0.430 +/- 0.037 | 0.0000 | 0.0625 | True |
| strict | Mead minimum (ft) | 3.060 +/- 2.655 | 0.0615 | 0.0625 | True |
| strict | Shortage years | -1.200 +/- 2.864 | 0.4018 | 0.5000 | False |
| strict | Rejection rate (%) | -38.040 +/- 4.163 | 0.0000 | 0.0625 | True |
| strict | Retry rate (%) | 9.792 +/- 3.795 | 0.0045 | 0.0625 | True |
| ungoverned | IBR headline | -45.071 +/- 2.623 | 0.0000 | 0.0625 | True |
| ungoverned | EHE pooled (executed) | 0.041 +/- 0.013 | 0.0020 | 0.0625 | True |
| ungoverned | EHE pooled (proposal) | -0.009 +/- 0.008 | 0.0641 | 0.1250 | False |
| ungoverned | Mead minimum (ft) | 16.638 +/- 18.012 | 0.1078 | 0.2500 | False |
| ungoverned | Shortage years | -1.600 +/- 0.548 | 0.0028 | 0.0625 | True |
| ungoverned | Rejection rate (%) | -25.879 +/- 1.814 | 0.0000 | 0.0625 | True |
| ungoverned | Retry rate (%) | -20.940 +/- 1.746 | 0.0000 | 0.0625 | True |

## Part 3 -- governed-vs-ungoverned contrast, gemma4:12b vs gemma3:4b (diff = ungoverned - governed; scoped to the 2 metrics r25 covers)

| metric | gemma4:12b mean_diff +/- sd | gemma4:12b p_paired_t | gemma3:4b mean_diff +/- sd | gemma3:4b p_paired_t | same sign across models |
|---|---:|---:|---:|---:|:---:|
| IBR headline | 11.569 +/- 1.532 | 0.0001 | 25.227 +/- 7.054 | 0.0013 | True |
| EHE pooled (executed) | 0.648 +/- 0.026 | 0.0000 | 0.664 +/- 0.045 | 0.0000 | True |

## Part 4 -- manifest + think-log census

| arm | seed | model | thinking_mode | timeout_s | model_digest | quantization | git_commit | think_lines | think_false |
|---|---|---|---|---:|---|---|---|---:|---:|
| strict | 42 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 6250 | 6250 |
| strict | 43 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 6241 | 6241 |
| strict | 44 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 6403 | 6403 |
| strict | 45 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 6251 | 6251 |
| strict | 46 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 6365 | 6365 |
| ungoverned | 42 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 4087 | 4087 |
| ungoverned | 43 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 4097 | 4097 |
| ungoverned | 44 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 4171 | 4171 |
| ungoverned | 45 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 4030 | 4030 |
| ungoverned | 46 | gemma4:12b | disabled | 1800 | 2026-06-06T14:49:09.5129671-04:00 | Q4_K_M | c3391a53 | 4040 | 4040 |

## Plain read

gemma4:12b's irrigation strict arm is fully landed (5/5 seeds, all `integrity_ok`, `thinking_mode=disabled` and think=false on every request checked); the ungoverned arm has 5/5 seeds complete. On the model-paired strict-vs-strict comparison, IBR headline differs by -31.41 pp (12b - 4b, p_paired_t=0.0002, sign-consistent=True). The governed-vs-ungoverned contrast keeps its sign on the larger model: IBR headline mean_diff (ungoverned - governed) 11.57 pp on gemma4:12b vs 25.23 pp on gemma3:4b. No number in this report was hand-typed and every gemma3:4b aggregate is cross-checked against r25's own recorded values; the completeness gates mean this script can be re-run unchanged once ungoverned 45/46 land.
