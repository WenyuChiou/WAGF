# R36 -- no-ceiling ablation: is the Mead/demand envelope bought by one rule?

Source: `r36_no_ceiling_ablation.py`. Every number below is read live from the `rows` list this script writes to the paired CSV. n=2 seeds (42, 43) throughout -- no t-test anywhere in this file.

## Part 1 -- per (arm, seed) metrics

| arm | seed | n_rows | IBR headline | EHE exec | EHE prop | Mead min ft | shortage yrs | demand mean (acre-ft) | % yrs over ceiling | Mead KGE vs FQL matched | retry rate % | fallback % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ablated | 42 | 3276 | 27.15 | 0.511 | 0.762 | 895.0 | 35 | 8,138,498 | 97.62 | 0.4536 | 64.07 | 0.06 |
| ablated | 43 | 3276 | 26.78 | 0.570 | 0.792 | 895.0 | 35 | 8,020,228 | 90.48 | 0.5019 | 62.79 | 0.15 |
| strict | 42 | 3276 | 26.64 | 0.139 | 0.598 | 997.0 | 13 | 6,019,226 | 80.95 | 0.9484 | 59.83 | 1.31 |
| strict | 43 | 3276 | 39.56 | 0.132 | 0.655 | 995.7 | 15 | 6,069,173 | 90.48 | 0.9461 | 63.58 | 1.34 |
| ungoverned | 42 | 3276 | 59.33 | 0.804 | 0.868 | 895.0 | 39 | 11,909,071 | 100.00 | 0.1224 | 37.21 | 0.03 |
| ungoverned | 43 | 3276 | 55.29 | 0.804 | 0.871 | 895.0 | 37 | 11,957,962 | 100.00 | 0.4517 | 34.92 | 0.12 |

IBR headline by seed (ablated vs strict vs ungoverned, no interpretation beyond stating the three values):

- seed 42: IBR headline: ablated 27.15, strict 26.64, ungoverned 59.33.
- seed 43: IBR headline: ablated 26.78, strict 39.56, ungoverned 55.29.

### Ablation check (ablated arm only): does `demand_ceiling_stabilizer` ever fire?

| arm | seed | rule hits (failed_rules or rules_triggered, all rows) | LAUNCH_COMMAND.txt has `--ablation-mode no_demand_ceiling` |
|---|---|---|---|
| ablated | 42 | 0 | True |
| ablated | 43 | 0 | True |

### Rule-id census, top 6 among retried rows

| arm | seed | rank | rule_id | count |
|---|---|---|---|---|
| ablated | 42 | 1 | curtailment_awareness | 1785 |
| ablated | 42 | 2 | high_threat_high_cope_no_increase | 1758 |
| ablated | 42 | 3 | demand_floor_stabilizer | 276 |
| ablated | 42 | 4 | supply_gap_block_increase | 102 |
| ablated | 42 | 5 | low_threat_no_increase | 12 |
| ablated | 43 | 1 | curtailment_awareness | 1726 |
| ablated | 43 | 2 | high_threat_high_cope_no_increase | 1701 |
| ablated | 43 | 3 | demand_floor_stabilizer | 276 |
| ablated | 43 | 4 | supply_gap_block_increase | 147 |
| ablated | 43 | 5 | low_threat_no_increase | 12 |
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

| arm | seed | model | git_commit | thinking_mode (not enforced) | enforced (model/commit) |
|---|---|---|---|---|---|
| ablated | 42 | gemma3:4b | 83fa97e1... | auto | True |
| ablated | 43 | gemma3:4b | 83fa97e1... | auto | True |
| strict | 42 | gemma3:4b | faf1bb12... | auto | False |
| strict | 43 | gemma3:4b | faf1bb12... | auto | False |
| ungoverned | 42 | gemma3:4b | faf1bb12... | auto | False |
| ungoverned | 43 | gemma3:4b | faf1bb12... | auto | False |

## Part 2 -- where the ablated arm sits between strict and ungoverned

level=envelope (Mead min, shortage years, basin-demand mean) asks whether the governed basin physically reaches the same state as ungoverned without the ceiling rule; level=trajectory (Mead KGE vs FQL matched) asks whether the ablated arm's water-level path still agrees with the traditional model -- a different question. Envelope metrics listed first.

| metric | level | seed | ablated | strict | ungoverned | ablated-strict | ablated-ungoverned | share on strict->ungoverned line |
|---|---|---|---|---|---|---|---|---|
| Mead min (ft) | envelope | 42 | 895.0000 | 996.9707 | 895.0000 | -101.9707 | 0.0000 | 1.000 |
| Mead min (ft) | envelope | 43 | 895.0000 | 995.6719 | 895.0000 | -100.6719 | 0.0000 | 1.000 |
| Shortage years | envelope | 42 | 35.0000 | 13.0000 | 39.0000 | 22.0000 | -4.0000 | 0.846 |
| Shortage years | envelope | 43 | 35.0000 | 15.0000 | 37.0000 | 20.0000 | -2.0000 | 0.909 |
| Basin demand mean (acre-ft) | envelope | 42 | 8,138,497.6820 | 6,019,225.8607 | 11,909,070.7718 | 2,119,271.8213 | -3,770,573.0898 | 0.360 |
| Basin demand mean (acre-ft) | envelope | 43 | 8,020,228.3439 | 6,069,173.1626 | 11,957,962.1942 | 1,951,055.1813 | -3,937,733.8504 | 0.331 |
| Mead KGE vs FQL matched | trajectory | 42 | 0.4536 | 0.9484 | 0.1224 | -0.4948 | 0.3312 | 0.599 |
| Mead KGE vs FQL matched | trajectory | 43 | 0.5019 | 0.9461 | 0.4517 | -0.4442 | 0.0503 | 0.898 |

## Plain read

`demand_ceiling_stabilizer` fired 0 times across all landed seeds of the ablated run (verified over every audit row's `failed_rules` and `rules_triggered`, total hits=0), and every landed seed's LAUNCH_COMMAND.txt confirms `--ablation-mode no_demand_ceiling` was passed -- the manipulation is behaviourally clean even though neither field is recorded in the manifest by name.

Mead min (ft) (envelope level): share 1.000 / 1.000 (seed 42 / seed 43), mean 1.000: tracks UNGOVERNED.

Shortage years (envelope level): share 0.846 / 0.909 (seed 42 / seed 43), mean 0.878: tracks UNGOVERNED.

Basin demand mean (acre-ft) (envelope level): share 0.360 / 0.331 (seed 42 / seed 43), mean 0.346: tracks STRICT.

Mead KGE vs FQL matched (trajectory level): share 0.599 / 0.898 (seed 42 / seed 43), mean 0.749: tracks UNGOVERNED.

Removing only the demand-ceiling rule lets the governed basin fall to the same Mead floor as the ungoverned arm: the water-system envelope in the strict arm is this one institutional rule, not governance in general. Coherence metrics (IBR headline) are reported in Part 1 and are not part of this verdict.

This whole comparison is n=2 seeds (42, 43) -- no significance test is computed anywhere in this script; the per-seed numbers are reported directly, and any conclusion here should be read as suggestive, not statistically established.

## Method

IBR headline and both EHE definitions are `r25_table1_regen.py::_irr_llm_metrics()`; Mead min ft and shortage years come from the same call. Basin-demand mean/share-over-ceiling use `r28_trajectory_vs_traditional.py::_yearly_series()` on the `request` column plus `DEMAND_CEILING_AF` imported (via r29) from `examples/irrigation_abm/validators/irrigation_validators.py` (6,000,000 acre-ft). Mead KGE vs FQL matched uses the same `_yearly_series()` on `lake_mead_level` for both the run and the same-seed `fql_raw_norebalance_faf1bb12` reference, then `_kge_and_rmse()` -- the identical Gupta et al. (2009) original-formulation KGE every other script in this package uses. The ablation itself (`--ablation-mode no_demand_ceiling`, `examples/irrigation_abm/run_experiment.py`) flips a module-level flag in `irr_validators` and is NOT recorded in either `reproducibility_manifest.json` or `config_snapshot.yaml` by name (verified by reading `broker/core/experiment_runner.py::_collect_reproducibility_metadata` end to end) -- this script instead verifies the ablation behaviourally, asserting `demand_ceiling_stabilizer` appears zero times in `failed_rules`/`rules_triggered` across every row of the ablated run, and textually, checking LAUNCH_COMMAND.txt for the literal flag string; either check failing raises rather than silently reporting unverified numbers. share_on_strict_to_ungoverned_line = (ablated-strict)/(ungoverned-strict): 0 = ablated behaves like strict, 1 = ablated behaves like ungoverned; a cell is marked degenerate (excluded from the Part 3 verdict, never hidden from the Part 2 table) when |ungoverned-strict| falls below a per-metric threshold set from the comparators' own observed line length -- the same rule r34/r35 established for flood/irrigation placebo, applied here from the start. 2026-09-22: METRIC_LEVEL labels Mead min (ft), shortage years, and basin-demand mean as level=envelope (the physical state of the governed water system -- the audit's own step [2] decision rule is stated in these terms, `out/paper_readiness_audit_2026-09-22.md`) and Mead KGE vs FQL matched as level=trajectory (agreement with the traditional model's time path, a different question); Mead min ft and shortage years reuse r35_placebo_retry_irrigation.py's own thresholds (5.0 ft, 1.0 year) for the identical quantity on the identical faf1bb12 strict/ungoverned comparator runs. Part 3's per-metric sentences and gated closing sentence use `_track_label()`, the same 0.35/0.65 thresholds r35_placebo_retry_irrigation.py's own `_track_label` uses -- re-declared here, not imported, since r35 does not export it as a module-level name meant for reuse, but byte-identical, so the two scripts' STRICT/midway/UNGOVERNED language cannot disagree.

Mead min saturates at the 895.0 ft dead-pool floor (read from the ungoverned arm's own Mead min above, not assumed): once sustained basin demand exceeds available supply for long enough, elevation cannot fall further, so any arm whose demand overshoots supply for long enough settles at that identical floor regardless of how far demand overshoots it -- this is why the ablated arm's Mead-min share is 1.000 / 1.000 (seed 42 / seed 43, mean 1.000) even though its own basin-demand mean sits only 0.360 / 0.331 (mean 0.346) of the way from strict to ungoverned; basin-demand mean does not saturate the same way.

Shortage years saturate less than Mead min but still track UNGOVERNED (share 0.846 / 0.909, mean 0.878), so the dead-pool reading in the Plain read section above does not rest on Mead min alone.

The ablated arm was run at code 83fa97e1 while the strict and ungoverned comparators come from faf1bb12. The comparison is accepted on three pieces of evidence recorded in out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md: the only framework change between c3391a53 and 83fa97e1 is PR #46 (eleven files, all plumbing for the retry_feedback_mode feature), whose only behaviour-changing branch is in the domain-generic retry loop broker/core/_retry_loop.py (RetryMixin._governance_retry_loop); the full-mode retry prompt rendered by that loop is byte-identical across the two commits for both the rule-violation and the format-violation branch; and mock runs at both commits give identical governance-audit and simulation logs for flood (4 of 4 comparisons) and for irrigation (4 of 4, strict and disabled, synthetic agents). The earlier faf1bb12 -> c3391a53 gate in out/regen_progress_2026-09-15.md covers both domains.
