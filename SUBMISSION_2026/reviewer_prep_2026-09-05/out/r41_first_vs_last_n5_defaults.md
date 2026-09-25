# R41 -- first-attempt vs last-proposal IBR (flood n=5, irrigation n=3)

Source: `r41_first_vs_last_n5.py`. Every number below is read live from the `rows` list this script writes to the paired CSV. Extends r33's single-seed irrigation result; see that script and `out/r33_first_vs_last_proposal.md` for the single-seed baseline this corpus builds on.

> **Flood corpus: defaults.** sampling: none sent, modelfile defaults temperature 1 / top_p 0.95 / top_k 64. Part B (irrigation) is UNCHANGED (always v08). Part A's band comparator is the defaults baseline strict corpus, NOT faf1bb12.

## Part A -- flood (`JOH_strict_initprop_defaults_gemma3_4b_83fa97e1`, seeds 42-46, n=5)

### IBR: first-attempt vs last-proposal vs executed

| seed | first-attempt (initial_skill) | last-proposal (proposed_skill) | executed |
|---|---|---|---|
| 42 | 8.78% (77/877) | 1.03% (9/877) | 0.91% (8/877) |
| 43 | 8.83% (77/872) | 0.11% (1/872) | 0.11% (1/872) |
| 44 | 9.14% (75/821) | 0.61% (5/821) | 0.61% (5/821) |
| 45 | 8.96% (79/882) | 0.45% (4/882) | 0.45% (4/882) |
| 46 | 6.84% (62/907) | 0.44% (4/907) | 0.44% (4/907) |
| pooled (rows combined) | 8.49% (370/4359) | 0.53% (23/4359) | 0.50% (22/4359) |

Mean +/- sd across landed seeds:

| action | n | mean (%) | sd |
|---|---|---|---|
| initial_skill | 5 | 8.51 | 0.945 |
| proposed_skill | 5 | 0.53 | 0.331 |
| executed | 5 | 0.51 | 0.290 |

### Walk-back rate (first-attempt rule-violating proposals whose last proposal is compliant)

| seed | numerator | denominator | rate (%) |
|---|---|---|---|
| 42 | 40 | 77 | 51.95 |
| 43 | 49 | 77 | 63.64 |
| 44 | 51 | 75 | 68.00 |
| 45 | 49 | 79 | 62.03 |
| 46 | 35 | 62 | 56.45 |
| pooled (rows combined) | 224 | 370 | 60.54 |

Mean walk-back rate across landed seeds (n=5): 60.41% (sd 6.283).

### First-minus-last difference, sd, exact permutation p, and the audit's gate

| seed | first-attempt IBR (%) | last-proposal IBR (%) | diff (first-last) |
|---|---|---|---|
| 42 | 8.78 | 1.03 | 7.75 |
| 43 | 8.83 | 0.11 | 8.72 |
| 44 | 9.14 | 0.61 | 8.53 |
| 45 | 8.96 | 0.45 | 8.50 |
| 46 | 6.84 | 0.44 | 6.39 |

n=5: mean diff = 7.979 pp, sd of diffs (ddof=1) = 0.959 pp, sd(first group) = 0.945, sd(last group) = 0.331, pooled sd = 0.708 pp, exact permutation p (paired sign, floor 2/2^5 = 0.0625 at n=5) = 0.0625.

**Decision rule (audit, verbatim): "if the five-seed first-attempt IBR mean exceeds the last-proposal mean by more than the pooled standard deviation, 'negotiation, not relabelling' holds ... and can be printed as a headline."** At n=5 on flood (this corpus), mean diff (7.979 pp) EXCEEDS the pooled sd (0.708 pp): the gate is MET -- "negotiation, not relabelling" holds and may be printed as a headline on this corpus.

### Band check vs `JOH_strict_defaults_gemma3_4b_83fa97e1` 5-seed band (mean +/- 2 sd)

| metric | seed | arm value | band (mean +/- 2 sd) | inside band? |
|---|---|---|---|---|
| IBR headline | 42 | 1.0262 | [-0.1584, 0.9676] (mean 0.4046, sd 0.2815) | NO |
| IBR headline | 43 | 0.1147 | [-0.1584, 0.9676] (mean 0.4046, sd 0.2815) | YES |
| IBR headline | 44 | 0.6090 | [-0.1584, 0.9676] (mean 0.4046, sd 0.2815) | YES |
| IBR headline | 45 | 0.4535 | [-0.1584, 0.9676] (mean 0.4046, sd 0.2815) | YES |
| IBR headline | 46 | 0.4410 | [-0.1584, 0.9676] (mean 0.4046, sd 0.2815) | YES |
| IBR headline | mean(n=5) | 0.5289 | [-0.1584, 0.9676] (mean 0.4046, sd 0.2815) | YES |
| EHE pooled | 42 | 0.8687 | [0.8216, 0.8845] (mean 0.8531, sd 0.0157) | YES |
| EHE pooled | 43 | 0.8641 | [0.8216, 0.8845] (mean 0.8531, sd 0.0157) | YES |
| EHE pooled | 44 | 0.8743 | [0.8216, 0.8845] (mean 0.8531, sd 0.0157) | YES |
| EHE pooled | 45 | 0.8811 | [0.8216, 0.8845] (mean 0.8531, sd 0.0157) | YES |
| EHE pooled | 46 | 0.8453 | [0.8216, 0.8845] (mean 0.8531, sd 0.0157) | YES |
| EHE pooled | mean(n=5) | 0.8667 | [0.8216, 0.8845] (mean 0.8531, sd 0.0157) | YES |
| Final-year protection % | 42 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | 43 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | 44 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | 45 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | 46 | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |
| Final-year protection % | mean(n=5) | 100.0000 | [100.0000, 100.0000] (mean 100.0000, sd 0.0000) | YES |

All three pooled (mean-of-landed-seeds) metrics fall INSIDE the defaults strict 5-seed (`JOH_strict_defaults_gemma3_4b_83fa97e1`, seeds 42-46, n=5) band -- the initprop flag did not visibly shift governed behaviour relative to the pre-initprop strict corpus, except one seed (42) falls outside on IBR headline alone (1.0262 against [-0.1584, 0.9676]).

The initprop arm and the defaults strict 5-seed comparator band were both run at code 83fa97e1 -- the SAME commit, so this comparison carries none of the v08 corpus's c3391a53/83fa97e1 code-provenance question (there is no commit difference to justify here); any gap between the two arms is attributable to the initprop flag alone.

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

Flood, n=5: pooled first-attempt IBR 8.49% vs pooled last-proposal IBR 0.53% (rows combined across the 5 landed seed(s)); mean per-seed diff 7.979 pp against a pooled sd of 0.708 pp -- gate MET.

Irrigation, n=3 (of 3 target seeds; seed 44 landed): pooled first-attempt IBR 65.47% vs pooled last-proposal IBR 30.03%; mean per-seed diff 35.318 pp against a pooled sd of 2.685 pp -- gate MET. This is n=3, not the five-seed n the audit's decision rule was framed for -- reported at the n this corpus actually has, not extrapolated.

This whole script computes exact permutation tests, not asymptotic ones, and at n=5 (flood) the floor is 2/32 = 0.0625; at irrigation's landed n (3) the floor is 2/2^3 = 0.2500 -- none of these p-values should be read as passing a conventional 0.05 significance bar just because a number is printed.

## Method

Flood IBR formula = R1+R3+R4 (R5 excluded per EDT2), canonical at `examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py (compute_ibr_components)`, transcribed as `_common.py (flood_ibr_components)`; this script's own `_flood_rate()` restates the same per-row predicate (`_flood_is_violation`) so it can be evaluated against `initial_labels`' first-attempt TP_LABEL as well as `construct_TP_LABEL` (final) -- self-tested against `_common.py (flood_ibr_components)` directly on action=proposed_skill/label=final (raises on disagreement, verified live on every landed seed, never assumed). Irrigation IBR formula = `SUBMISSION_2026/decomposition/_loader.py (ibr)`'s own conditional-high-WSA-increase-rate formula, reused via `r33_first_vs_last_proposal.py (_rate, _initial_wsa, _final_wsa, _crosscheck_published_ibr)` unmodified -- this script adds no new irrigation IBR logic, only iterates it over 3 seeds instead of r33's 1 and adds the pooled/diff/gate layer. Executed action = `_common.py (irr_executed)` for irrigation, `_common.py (flood_executed)` for flood -- both remap a REJECTED proposal to the domain's registry default (`maintain_demand` / `do_nothing`) and otherwise use `final_skill`. The exact permutation test is `_common.py (exact_perm_p)`, reused unmodified (all 2^n sign-flip assignments on the paired per-seed differences); "pooled standard deviation" for the audit's gate is this script's own `_pooled_sd()` = sqrt((sd_first^2 + sd_last^2)/2), the standard two-sample equal-n pooled-SD (Cohen's-d denominator) convention -- the audit text does not define this term itself, so this is a flagged judgment call, distinct from the SD of the paired differences (also reported, separately). Flood's band-check metrics (`IBR headline`, `EHE pooled`, `final_year_protection_pct`) are `r25_table1_regen.py (_flood_llm_metrics)`, imported unmodified -- note its own `ibr_headline` uses action=final_skill (`r23_flood_strict_regen.py`'s `LEVELS["final"]`), a different action-column choice from this script's own "last-proposal" cell (action=proposed_skill, matching r33's irrigation naming); both are reported side by side, never asserted identical. Walk-back rate for both domains holds the FIRST-attempt label fixed and re-checks only the terminal action -- flood's `_flood_walkback_stat()` and irrigation's `_irr_walkback()` -- a judgment call made by direct analogy to r33's own inline irrigation walk-back block, not an independently-invented rule. "rows where initial_skill is null" (Part C) is read as "rows where the stripped `initial_skill` cell is the empty string", the same quantity r33 calls `n_initial_unparsed` -- the audit CSVs never carry a distinct NULL cell type.
