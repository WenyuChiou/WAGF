# R41 -- first-attempt vs last-proposal IBR (flood n=5, irrigation n=3)

Source: `r41_first_vs_last_n5.py`. Every number below is read live from the `rows` list this script writes to the paired CSV. Extends r33's single-seed irrigation result; see that script and `out/r33_first_vs_last_proposal.md` for the single-seed baseline this corpus builds on.

## Part A -- flood (`JOH_strict_initprop_gemma3_4b_83fa97e1`, seeds 42-46, n=5)

### IBR: first-attempt vs last-proposal vs executed

| seed | first-attempt (initial_skill) | last-proposal (proposed_skill) | executed |
|---|---|---|---|
| 42 | 9.62% (87/904) | 0.77% (7/904) | 0.77% (7/904) |
| 43 | 9.25% (83/897) | 0.33% (3/897) | 0.33% (3/897) |
| 44 | 9.44% (81/858) | 0.82% (7/858) | 0.82% (7/858) |
| 45 | 8.34% (72/863) | 0.23% (2/863) | 0.23% (2/863) |
| 46 | 8.48% (77/908) | 0.33% (3/908) | 0.33% (3/908) |
| pooled (rows combined) | 9.03% (400/4430) | 0.50% (22/4430) | 0.50% (22/4430) |

Mean +/- sd across landed seeds:

| action | n | mean (%) | sd |
|---|---|---|---|
| initial_skill | 5 | 9.03 | 0.580 |
| proposed_skill | 5 | 0.50 | 0.275 |
| executed | 5 | 0.50 | 0.275 |

### Walk-back rate (first-attempt rule-violating proposals whose last proposal is compliant)

| seed | numerator | denominator | rate (%) |
|---|---|---|---|
| 42 | 59 | 87 | 67.82 |
| 43 | 50 | 83 | 60.24 |
| 44 | 49 | 81 | 60.49 |
| 45 | 51 | 72 | 70.83 |
| 46 | 43 | 77 | 55.84 |
| pooled (rows combined) | 252 | 400 | 63.00 |

Mean walk-back rate across landed seeds (n=5): 63.05% (sd 6.117).

### First-minus-last difference, sd, exact permutation p, and the audit's gate

| seed | first-attempt IBR (%) | last-proposal IBR (%) | diff (first-last) |
|---|---|---|---|
| 42 | 9.62 | 0.77 | 8.85 |
| 43 | 9.25 | 0.33 | 8.92 |
| 44 | 9.44 | 0.82 | 8.62 |
| 45 | 8.34 | 0.23 | 8.11 |
| 46 | 8.48 | 0.33 | 8.15 |

n=5: mean diff = 8.531 pp, sd of diffs (ddof=1) = 0.382 pp, sd(first group) = 0.580, sd(last group) = 0.275, pooled sd = 0.454 pp, exact permutation p (paired sign, floor 2/2^5 = 0.0625 at n=5) = 0.0625.

**Decision rule (audit, verbatim): "if the five-seed first-attempt IBR mean exceeds the last-proposal mean by more than the pooled standard deviation, 'negotiation, not relabelling' holds ... and can be printed as a headline."** At n=5 on flood (this corpus), mean diff (8.531 pp) EXCEEDS the pooled sd (0.454 pp): the gate is MET -- "negotiation, not relabelling" holds and may be printed as a headline on this corpus.

### Band check vs `JOH_strict_gemma3_4b_faf1bb12` 5-seed band (mean +/- 2 sd)

| metric | seed | arm value | band (mean +/- 2 sd) | inside band? |
|---|---|---|---|---|
| IBR headline | 42 | 0.7743 | [-0.0808, 1.6568] (mean 0.7880, sd 0.4344) | YES |
| IBR headline | 43 | 0.3344 | [-0.0808, 1.6568] (mean 0.7880, sd 0.4344) | YES |
| IBR headline | 44 | 0.8159 | [-0.0808, 1.6568] (mean 0.7880, sd 0.4344) | YES |
| IBR headline | 45 | 0.2317 | [-0.0808, 1.6568] (mean 0.7880, sd 0.4344) | YES |
| IBR headline | 46 | 0.3304 | [-0.0808, 1.6568] (mean 0.7880, sd 0.4344) | YES |
| IBR headline | mean(n=5) | 0.4974 | [-0.0808, 1.6568] (mean 0.7880, sd 0.4344) | YES |
| EHE pooled | 42 | 0.8450 | [0.8380, 0.8808] (mean 0.8594, sd 0.0107) | YES |
| EHE pooled | 43 | 0.8264 | [0.8380, 0.8808] (mean 0.8594, sd 0.0107) | NO |
| EHE pooled | 44 | 0.8658 | [0.8380, 0.8808] (mean 0.8594, sd 0.0107) | YES |
| EHE pooled | 45 | 0.8448 | [0.8380, 0.8808] (mean 0.8594, sd 0.0107) | YES |
| EHE pooled | 46 | 0.8524 | [0.8380, 0.8808] (mean 0.8594, sd 0.0107) | YES |
| EHE pooled | mean(n=5) | 0.8469 | [0.8380, 0.8808] (mean 0.8594, sd 0.0107) | YES |
| Final-year protection % | 42 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | 43 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | 44 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | 45 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | 46 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | mean(n=5) | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |

All three pooled (mean-of-landed-seeds) metrics fall INSIDE the faf1bb12 strict 5-seed band -- the initprop flag did not visibly shift governed behaviour relative to the pre-initprop strict corpus, except one seed (43) falls outside on EHE pooled alone (0.8264 against [0.8380, 0.8808]).

The initprop arm was run at code 83fa97e1 while the strict 5-seed comparator band comes from faf1bb12. The comparison is accepted on three pieces of evidence recorded in out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md: the only framework change between c3391a53 and 83fa97e1 is PR #46 (eleven files, all plumbing for the retry_feedback_mode feature), whose only behaviour-changing branch is in the domain-generic retry loop broker/core/_retry_loop.py (RetryMixin._governance_retry_loop); the full-mode retry prompt rendered by that loop is byte-identical across the two commits for both the rule-violation and the format-violation branch; and mock runs at both commits give identical governance-audit and simulation logs for flood (4 of 4 comparisons) and for irrigation (4 of 4, strict and disabled, synthetic agents). The earlier faf1bb12 -> c3391a53 gate in out/regen_progress_2026-09-15.md covers both domains.

## Part B -- irrigation (seed 42 c3391a53 + seeds 43-44 83fa97e1, n=3)

Commit mix (from each run's own manifest, never assumed): seed 42: c3391a53; seed 43: 83fa97e1; seed 44: 83fa97e1. Pooling across c3391a53 and 83fa97e1 for this feature is accepted on the three-piece evidence chain in `out/mock_equiv_c3391a53_83fa97e1_2026-09-22.md`; the earlier faf1bb12 -> c3391a53 gate is recorded in `out/regen_progress_2026-09-15.md`.

### IBR: first-attempt vs last-proposal vs executed

| seed | first-attempt (initial_skill) | last-proposal (proposed_skill) | executed |
|---|---|---|---|
| 42 | 67.74% (779/1150) | 32.97% (359/1089) | 1.29% (14/1089) |
| 43 | 66.12% (806/1219) | 29.68% (376/1267) | 1.66% (21/1267) |
| 44 | 62.44% (705/1129) | 27.71% (330/1191) | 0.59% (7/1191) |
| pooled (rows combined) | 65.47% (2290/3498) | 30.03% (1065/3547) | 1.18% (42/3547) |

Mean +/- sd across landed seeds:

| action | n | mean (%) | sd |
|---|---|---|---|
| initial_skill | 3 | 65.43 | 2.713 |
| proposed_skill | 3 | 30.12 | 2.657 |
| executed | 3 | 1.18 | 0.543 |

### Walk-back rate (first-attempt increase under high first-attempt WSA whose last attempt is maintain/decrease)

| seed | numerator | denominator | rate (%) |
|---|---|---|---|
| 42 | 321 | 779 | 41.21 |
| 43 | 351 | 806 | 43.55 |
| 44 | 317 | 705 | 44.96 |
| pooled (rows combined) | 989 | 2290 | 43.19 |

Mean walk-back rate across landed seeds (n=3): 43.24% (sd 1.898).

### First-minus-last difference, sd, exact permutation p, and the audit's gate

| seed | first-attempt IBR (%) | last-proposal IBR (%) | diff (first-last) |
|---|---|---|---|
| 42 | 67.74 | 32.97 | 34.77 |
| 43 | 66.12 | 29.68 | 36.44 |
| 44 | 62.44 | 27.71 | 34.74 |

n=3: mean diff = 35.318 pp, sd of diffs (ddof=1) = 0.975 pp, sd(first group) = 2.713, sd(last group) = 2.657, pooled sd = 2.685 pp, exact permutation p (paired sign, floor 2/2^n (n=2 -> 0.5, n=3 -> 0.25; the audit's 0.0625 floor is stated for n=5, which irrigation does not reach in this step)) = 0.2500.

**Decision rule (audit, verbatim): "if the five-seed first-attempt IBR mean exceeds the last-proposal mean by more than the pooled standard deviation, 'negotiation, not relabelling' holds ... and can be printed as a headline."** At n=3 on irrigation (this corpus), mean diff (35.318 pp) EXCEEDS the pooled sd (2.685 pp): the gate is MET -- "negotiation, not relabelling" holds and may be printed as a headline on this corpus.

## Part C -- provenance census

`initial_proposal_columns` never appears in `reproducibility_manifest.json` on any run in this package (confirmed per run below, consistent with r33's own finding) -- it is recorded only in `config_snapshot.yaml`'s `global_config.audit.initial_proposal_columns`. "rows where initial_skill is null" is read as "rows where initial_skill is the empty string after stripping" -- the audit CSVs carry no distinct NULL cell type (see Method).

| domain | seed | model | git_commit | thinking_mode | manifest has key? | config_snapshot flag | empty initial_skill rows |
|---|---|---|---|---|---|---|---|
| flood | 42 | gemma3:4b | 83fa97e1... | disabled | False | True | 0 |
| flood | 43 | gemma3:4b | 83fa97e1... | disabled | False | True | 0 |
| flood | 44 | gemma3:4b | 83fa97e1... | disabled | False | True | 0 |
| flood | 45 | gemma3:4b | 83fa97e1... | disabled | False | True | 0 |
| flood | 46 | gemma3:4b | 83fa97e1... | disabled | False | True | 0 |
| irrigation | 42 | gemma3:4b | c3391a53... | auto | False | True | 0 |
| irrigation | 43 | gemma3:4b | 83fa97e1... | auto | False | True | 0 |
| irrigation | 44 | gemma3:4b | 83fa97e1... | auto | False | True | 0 |

## Plain read

Flood, n=5: pooled first-attempt IBR 9.03% vs pooled last-proposal IBR 0.50% (rows combined across the 5 landed seed(s)); mean per-seed diff 8.531 pp against a pooled sd of 0.454 pp -- gate MET.

Irrigation, n=3 (of 3 target seeds; seed 44 landed): pooled first-attempt IBR 65.47% vs pooled last-proposal IBR 30.03%; mean per-seed diff 35.318 pp against a pooled sd of 2.685 pp -- gate MET. This is n=3, not the five-seed n the audit's decision rule was framed for -- reported at the n this corpus actually has, not extrapolated.

This whole script computes exact permutation tests, not asymptotic ones, and at n=5 (flood) the floor is 2/32 = 0.0625; at irrigation's landed n (3) the floor is 2/2^3 = 0.2500 -- none of these p-values should be read as passing a conventional 0.05 significance bar just because a number is printed.

## Method

Flood IBR formula = R1+R3+R4 (R5 excluded per EDT2), canonical at `examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py (compute_ibr_components)`, transcribed as `_common.py (flood_ibr_components)`; this script's own `_flood_rate()` restates the same per-row predicate (`_flood_is_violation`) so it can be evaluated against `initial_labels`' first-attempt TP_LABEL as well as `construct_TP_LABEL` (final) -- self-tested against `_common.py (flood_ibr_components)` directly on action=proposed_skill/label=final (raises on disagreement, verified live on every landed seed, never assumed). Irrigation IBR formula = `SUBMISSION_2026/decomposition/_loader.py (ibr)`'s own conditional-high-WSA-increase-rate formula, reused via `r33_first_vs_last_proposal.py (_rate, _initial_wsa, _final_wsa, _crosscheck_published_ibr)` unmodified -- this script adds no new irrigation IBR logic, only iterates it over 3 seeds instead of r33's 1 and adds the pooled/diff/gate layer. Executed action = `_common.py (irr_executed)` for irrigation, `_common.py (flood_executed)` for flood -- both remap a REJECTED proposal to the domain's registry default (`maintain_demand` / `do_nothing`) and otherwise use `final_skill`. The exact permutation test is `_common.py (exact_perm_p)`, reused unmodified (all 2^n sign-flip assignments on the paired per-seed differences); "pooled standard deviation" for the audit's gate is this script's own `_pooled_sd()` = sqrt((sd_first^2 + sd_last^2)/2), the standard two-sample equal-n pooled-SD (Cohen's-d denominator) convention -- the audit text does not define this term itself, so this is a flagged judgment call, distinct from the SD of the paired differences (also reported, separately). Flood's band-check metrics (`IBR headline`, `EHE pooled`, `final_year_protection_pct`) are `r25_table1_regen.py (_flood_llm_metrics)`, imported unmodified -- note its own `ibr_headline` uses action=final_skill (`r23_flood_strict_regen.py`'s `LEVELS["final"]`), a different action-column choice from this script's own "last-proposal" cell (action=proposed_skill, matching r33's irrigation naming); both are reported side by side, never asserted identical. Walk-back rate for both domains holds the FIRST-attempt label fixed and re-checks only the terminal action -- flood's `_flood_walkback_stat()` and irrigation's `_irr_walkback()` -- a judgment call made by direct analogy to r33's own inline irrigation walk-back block, not an independently-invented rule. "rows where initial_skill is null" (Part C) is read as "rows where the stripped `initial_skill` cell is the empty string", the same quantity r33 calls `n_initial_unparsed` -- the audit CSVs never carry a distinct NULL cell type.
