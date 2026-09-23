# R35 -- placebo-retry irrigation: extra attempt vs rule content

Source: `r35_placebo_retry_irrigation.py`. Every number below is read live from the `rows` list this script writes to the paired CSV. n=2 seeds (42, 43) throughout -- no t-test anywhere in this file.

## Part 1 -- per (arm, seed) metrics

| arm | seed | n_rows | IBR headline | EHE executed | EHE proposal | Mead min ft | shortage yrs | retry rate % | n_retried | mean retries (if retried) | fallback % | LLM fail | wall h |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| placebo | 42 | 3276 | 57.17 | 0.121 | 0.698 | 997.0 | 14 | 67.73 | 2219 | 2.587 | 0.34 | 0 | 3.161 |
| placebo | 43 | 3276 | 55.13 | 0.151 | 0.696 | 993.9 | 15 | 64.84 | 2124 | 2.525 | 0.31 | 0 | 3.051 |
| strict | 42 | 3276 | 26.64 | 0.139 | 0.598 | 997.0 | 13 | 59.83 | 1960 | 2.434 | 1.31 | 0 | 3.022 |
| strict | 43 | 3276 | 39.56 | 0.132 | 0.655 | 995.7 | 15 | 63.58 | 2083 | 2.588 | 1.34 | 0 | 3.218 |
| ungoverned | 42 | 3276 | 59.33 | 0.804 | 0.868 | 895.0 | 39 | 37.21 | 1219 | 2.760 | 0.03 | 0 | 2.591 |
| ungoverned | 43 | 3276 | 55.29 | 0.804 | 0.871 | 895.0 | 37 | 34.92 | 1144 | 2.714 | 0.12 | 0 | 2.502 |

### Rule-id census, top 6 among retried rows

| arm | seed | rank | rule_id | count |
|---|---|---|---|---|
| placebo | 42 | 1 | demand_ceiling_stabilizer | 1796 |
| placebo | 42 | 2 | high_threat_high_cope_no_increase | 1209 |
| placebo | 42 | 3 | curtailment_awareness | 666 |
| placebo | 42 | 4 | supply_gap_block_increase | 244 |
| placebo | 42 | 5 | low_threat_no_increase | 180 |
| placebo | 42 | 6 | demand_floor_stabilizer | 143 |
| placebo | 43 | 1 | demand_ceiling_stabilizer | 1781 |
| placebo | 43 | 2 | high_threat_high_cope_no_increase | 1190 |
| placebo | 43 | 3 | curtailment_awareness | 692 |
| placebo | 43 | 4 | supply_gap_block_increase | 248 |
| placebo | 43 | 5 | low_threat_no_increase | 150 |
| placebo | 43 | 6 | demand_floor_stabilizer | 129 |
| strict | 42 | 1 | demand_ceiling_stabilizer | 1489 |
| strict | 42 | 2 | high_threat_high_cope_no_increase | 950 |
| strict | 42 | 3 | curtailment_awareness | 532 |
| strict | 42 | 4 | demand_floor_stabilizer | 216 |
| strict | 42 | 5 | supply_gap_block_increase | 215 |
| strict | 42 | 6 | low_threat_no_increase | 45 |
| strict | 43 | 1 | demand_ceiling_stabilizer | 1803 |
| strict | 43 | 2 | high_threat_high_cope_no_increase | 1248 |
| strict | 43 | 3 | curtailment_awareness | 655 |
| strict | 43 | 4 | supply_gap_block_increase | 233 |
| strict | 43 | 5 | demand_floor_stabilizer | 141 |
| strict | 43 | 6 | low_threat_no_increase | 53 |
| ungoverned | 42 | 1 | precondition_violation | 1219 |
| ungoverned | 43 | 1 | precondition_violation | 1144 |

### Manifest census

| arm | seed | model | git_commit | thinking_mode (not enforced) | retry_feedback_mode | key present | enforced (model/commit/mode) |
|---|---|---|---|---|---|---|---|
| placebo | 42 | gemma3:4b | 83fa97e1... | auto | placebo | True | True |
| placebo | 43 | gemma3:4b | 83fa97e1... | auto | placebo | True | True |
| strict | 42 | gemma3:4b | faf1bb12... | auto | None | False | False |
| strict | 43 | gemma3:4b | faf1bb12... | auto | None | False | False |
| ungoverned | 42 | gemma3:4b | faf1bb12... | auto | None | False | False |
| ungoverned | 43 | gemma3:4b | faf1bb12... | auto | None | False | False |

## Part 2 -- seed-paired contrasts (n=2, both per-seed values reported, no t-test)

| metric | seed | placebo | strict | ungoverned | placebo-strict | placebo-ungoverned | share on strict->ungoverned line |
|---|---|---|---|---|---|---|---|
| IBR headline (%) | 42 | 57.171 | 26.642 | 59.325 | 30.529 | -2.154 | 0.934 |
| IBR headline (%) | 43 | 55.134 | 39.563 | 55.294 | 15.571 | -0.160 | 0.990 |
| EHE pooled executed | 42 | 0.121 | 0.139 | 0.804 | -0.018 | -0.683 | -0.026 |
| EHE pooled executed | 43 | 0.151 | 0.132 | 0.804 | 0.019 | -0.653 | 0.028 |
| EHE pooled proposal | 42 | 0.698 | 0.598 | 0.868 | 0.100 | -0.171 | 0.368 |
| EHE pooled proposal | 43 | 0.696 | 0.655 | 0.871 | 0.041 | -0.175 | 0.188 |
| Mead min (ft) | 42 | 996.968 | 996.971 | 895.000 | -0.003 | 101.968 | 0.000 |
| Mead min (ft) | 43 | 993.859 | 995.672 | 895.000 | -1.813 | 98.859 | 0.018 |
| Shortage years | 42 | 14.000 | 13.000 | 39.000 | 1.000 | -25.000 | 0.038 |
| Shortage years | 43 | 15.000 | 15.000 | 37.000 | 0.000 | -22.000 | 0.000 |

## Part 3 -- did the validator fire on a comparable schedule (placebo vs strict)?

| seed | placebo retry rate % | strict retry rate % | placebo top rule | strict top rule | placebo fallback % | strict fallback % | ungoverned fallback % |
|---|---|---|---|---|---|---|---|
| 42 | 67.73 | 59.83 | demand_ceiling_stabilizer | demand_ceiling_stabilizer | 0.34 | 1.31 | 0.03 |
| 43 | 64.84 | 63.58 | demand_ceiling_stabilizer | demand_ceiling_stabilizer | 0.31 | 1.34 | 0.12 |

## Plain read

Across the 2 non-degenerate IBR (seed) cells, placebo sits close to UNGOVERNED on IBR (mean share 0.962, range 0.934 to 0.990, i.e. near 1) -- most of governance's measured value here looks like it comes from the SPECIFIC RULE CONTENT in the retry prompt, not just from having another attempt.

Per-seed IBR share: seed 42: mean 0.934 (0.934); seed 43: mean 0.990 (0.990).

Excluded from the verdict: EHE pooled executed, EHE pooled proposal, Mead min (ft), Shortage years (non-IBR, excluded from this verdict by definition -- see Part 4b below for how they split by proposal vs executed level).

Placebo and strict retry rates track each other closely (max per-seed gap 7.91pp), consistent with the manipulation being clean -- the validator fires on the same schedule in both, only the retry prompt's content differs.

This whole comparison is n=2 seeds (42, 43) -- no significance test is computed anywhere in this script; the per-seed numbers and their sign agreement are reported directly, and any conclusion here should be read as suggestive, not statistically established.

## Part 4b -- proposal level versus executed level

Same `contrast_pair` rows as Part 2/4, each metric labelled by which level it measures: level=proposal is what the agent asked for / negotiated to, before any validator (IBR headline, EHE pooled proposal); level=executed is what actually happened to the water system after the executed-remap convention (`_common.py::irr_executed`) is applied (EHE pooled executed, Mead min, shortage years). No share value is recomputed here -- this table and the two means below only relabel and aggregate Part 2's own numbers.

| metric | level | seed | share on strict->ungoverned line |
|---|---|---|---|
| IBR headline (%) | proposal | 42 | 0.934 |
| IBR headline (%) | proposal | 43 | 0.990 |
| EHE pooled proposal | proposal | 42 | 0.368 |
| EHE pooled proposal | proposal | 43 | 0.188 |
| EHE pooled executed | executed | 42 | -0.026 |
| EHE pooled executed | executed | 43 | 0.028 |
| Mead min (ft) | executed | 42 | 0.000 |
| Mead min (ft) | executed | 43 | 0.018 |
| Shortage years | executed | 42 | 0.038 |
| Shortage years | executed | 43 | 0.000 |

Proposal-level mean share (non-degenerate cells): 0.620 (n=4).
Executed-level mean share (non-degenerate cells): 0.010 (n=6).

IBR headline (%) (proposal level): share 0.934 / 0.990, mean 0.962: tracks UNGOVERNED.

EHE pooled proposal (proposal level): share 0.368 / 0.188, mean 0.278: tracks STRICT.

EHE pooled executed (executed level): share -0.026 / 0.028, mean 0.001: tracks STRICT.

Mead min (ft) (executed level): share 0.000 / 0.018, mean 0.009: tracks STRICT.

Shortage years (executed level): share 0.038 / 0.000, mean 0.019: tracks STRICT.

On the coherence metric the placebo tracks UNGOVERNED while every executed outcome tracks STRICT: in irrigation, rule text in the retry prompt is what moves the agent's last recorded proposal, and blocking alone protects the water system. Compare r34 (flood), where placebo tracked STRICT on IBR as well.

## Method

IBR headline, both EHE definitions (pooled executed, pooled proposal), Mead min ft, and shortage years are `r25_table1_regen.py::_irr_llm_metrics()`, imported, not re-derived -- the SAME definitions every other script in this package uses for these columns (IBR itself traces to `_loader.py::ibr`). `retry_feedback_mode` is reported from each run's `reproducibility_manifest.json` and value-enforced =='placebo' ONLY for the placebo arm (raises otherwise, including if the key is simply absent); the strict/ungoverned comparator manifests are read and reported with the same fields, never enforced. `thinking_mode` is read and reported for every arm but never enforced -- irrigation's own faf1bb12 comparator manifests record "auto", which this script does not assume the placebo run will also record, and there is no existing irrigation run at commit 83fa97e1 to check against. Rule-id census counts each RETRIED row's `failed_rules` (pipe-delimited) once per distinct rule id per row, ranked by count then alphabetically, rule ids `sorted()` before counting -- the same Python set-hash-randomization fix `r27_irrigation_crossmodel_gemma4_12b.py` and `r34_placebo_retry_flood.py` applied. share_on_strict_to_ungoverned_line = (placebo-strict)/(ungoverned-strict): 0 = placebo behaves like strict, 1 = placebo behaves like ungoverned; a cell is marked degenerate (excluded from the Part 4 verdict, never hidden from the Part 2 table) when |ungoverned-strict| falls below a per-metric threshold set from the comparators' own observed line length -- the exact rule `r34_placebo_retry_flood.py`'s 2026-09-22 review fix introduced for flood, applied here from the start. The Part 4 verdict itself is computed over non-degenerate IBR cells ONLY, mirroring `r34_placebo_retry_flood.py`'s identical 2026-09-22 fix for its own verdict -- a naive mean across all 5 heterogeneous metrics is not interpretable; the 4 non-IBR metrics are named as excluded from that verdict in the plain-read text above, never hidden. Part 4b's proposal/executed level table and level means are informational only (METRIC_LEVEL, a static per-metric lookup); its per-metric classification sentences and closing sentence use `_track_label()`, the SAME 0.35/0.65 thresholds as Part 4's own IBR verdict, so the two parts cannot disagree -- no share value is recomputed anywhere in Part 4b.

The placebo arm was run at code 83fa97e1 while the strict and ungoverned comparators come from faf1bb12. The comparison is accepted on three pieces of evidence recorded in out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md: the only framework change between c3391a53 and 83fa97e1 is PR #46 (eleven files, all plumbing for the retry_feedback_mode feature), whose only behaviour-changing branch is in the domain-generic retry loop broker/core/_retry_loop.py (RetryMixin._governance_retry_loop); the full-mode retry prompt rendered by that loop is byte-identical across the two commits for both the rule-violation and the format-violation branch; and mock runs at both commits give identical governance-audit and simulation logs for flood (4 of 4 comparisons) and for irrigation (4 of 4, strict and disabled, synthetic agents). The earlier faf1bb12 -> c3391a53 gate in out/regen_progress_2026-09-15.md covers both domains.
