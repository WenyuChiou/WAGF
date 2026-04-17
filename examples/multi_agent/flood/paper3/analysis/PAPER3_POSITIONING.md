# Paper 3 Positioning

## 1. Paper 3 in 100 words

Paper 3 asks what happens when a governed LLM-ABM changes its memory policy and institutional setting while keeping the hazard process fixed. In the flood WAGF testbed, households, government, and insurance interact through a broker-governed architecture that records executed actions rather than unfiltered proposals. The main result is not that one configuration is simply "better." Instead, the six-arm panel shows a dual-role pattern: LEGACY memory sustains self-referential continuity and stronger insurance persistence, while CLEAN memory suppresses ratchet language but also compresses behavioral diversity. For WRR, the paper matters because it turns memory governance from a prompt tweak into an explicit, testable modeling choice.

## 2. Four Contribution Claims

**Claim 1. SP-protection coupling is invariant across all six policy arms, making it the strongest framework-validation result.** Across the six executed-outcome arms, the SP x protective-action association remains tightly clustered at Cramer's V `0.383901-0.416349` in `deep_synthesis/significance_tests.md` lines 34-39. The cross-sectional table shows why that matters substantively: SP=`L` protection is only `0.028441-0.078667` across the six `rq3_step2_cross_sectional.csv` rows for level `L`, while SP=`H` protection rises to `0.862361-0.892286` across the six level `H` rows. The same structure appears dynamically: `rq3_step3_within_agent.csv` reports chi-squared values from `57.4869` (`CLN_Flat_123`) to `115.8429` (`CLN_Full_42`), all with p-values below `1e-11`, and SP-up transitions raise switch-to-protective rates from `0.060513` in `LEG_Full_42` to `0.115261` in `CLN_Full_42`. The novelty is not merely construct-action coupling, which prior LLM-ABM work can show in one condition, but coupling invariance under memory variation, institutional variation, and seed variation.

**Claim 2. The RQ2 mechanism is a tenure-asymmetric premium burden channel, not a generic institutional effect.** `deep_synthesis/rq_deep/rq2_premium_burden.csv` shows owner premium burden means between `4.1441` (`LEG_Full_42`, owner, yearly mean implied by year rows) and `5.6428` (`CLN_Flat_42`, year 13, NMG-owner) for non-MG owners, and up to `9.3924` for MG owners in Flat arms; by contrast, renter burdens stay around `0.2412-0.7584`, with year-13 renter rows such as `LEG_Full_42, renter, MG = 0.5119` and `CLN_Full_42, renter, NMG = 0.3309`. The mechanism summary in `rq2_mechanism_report.md` condenses that into arm-level means: owners average `4.144-5.630%` of income while renters average `0.343-0.466%`. The statistical test is directionally consistent but modest: `significance_tests.md` lines 6-13 show owner do-nothing and insurance differences under Full vs Flat with `p=0.018940`, `0.020573`, `0.016747`, and `0.025141`, while rank-biserial effects stay around `|0.027-0.030|`; renter comparisons on lines 18-29 remain non-significant (`p>0.15`). The novel contribution is the first executed-outcome estimate of tenure-asymmetric institutional propagation in an LLM-ABM: transaction-cost settings matter mainly because owner insurance is large enough to bite, while renter contents insurance is too small to create the same elasticity.

**Claim 3. Memory has a dual role: it carries rationalization ratchet and, at the same time, preserves action diversity.** The ratchet side is visible in `deep_synthesis/past_reference_6arm.csv`: at year 13, `LEG_Full_42` records `0.27` for owners and `0.37` for renters, whereas CLEAN rows stay far lower, from `0.01-0.03` for owners and `0.05-0.085` for renters. The behavioral-diversity side appears in `deep_synthesis/cell_actions_6arm.csv`. For renter relocation, `LEG_Full_42` has executed relocation rates of `0.010000` (`MG-Renter`) and `0.010769` (`NMG-Renter`), which correspond to about `13` and `14` events out of `1300` decisions, while CLEAN rows fall to `0.000000-0.002308`, or roughly `0-3` events. The six-arm synthesis also shows owner entropy compression visually in per-arm `rq3_entropy.png` outputs, consistent with the same action-space narrowing. The novelty is the trade-off itself: the same memory channel that amplifies self-referential continuity also helps the model sustain a broader long-run behavioral repertoire, which is a framework-level design tension rather than a simple bug/fix story.

**Claim 4. The RQ1 cross-paradigm matrix identifies where memory and institutions move the LLM closer to, or farther from, the Traditional FLOODABM baseline.** `deep_synthesis/rq_deep/rq1_cross_paradigm_stats.csv` gives a seven-action by three-arm classification map. For owners, `elevate_house` is `CONVERGE` in `CLEAN_Flat` (`mad_pp=0.928623`) and `CLEAN_Full` (`1.056077`), while `buyout_program` is `MAGNITUDE_CONVERGE` in all three arms with the same `mad_pp=0.759877`. For renters, `do_nothing` and `buy_contents_insurance` are `TRAJECTORY_CONVERGE` only in `LEGACY_Full`, with `pearson_r=0.812612` and `0.842507`, while both CLEAN arms are marked `DIVERGE`; for owner `do_nothing`, both CLEAN arms are `TRAJECTORY_CONVERGE` (`pearson_r=0.586819`, `0.554688`) and `LEGACY_Full` is `DIVERGE`. This is intentionally a mapping claim, not a victory claim. Its novelty is descriptive: Paper 3 can now say which WAGF settings reproduce which parts of a calibrated Bayesian benchmark, which is useful when future LLM-ABM studies need to choose a memory-policy regime for a particular empirical target.

## 3. Claims We Will Not Headline

Owner Year-1 PA priming is real, but it is not the paper's headline mechanism because it is prompt-level rather than memory-fixable. `deep_synthesis/rq_deep/rq3_step1_construct_validity.csv` shows owner PA home-attachment rates still above `0.872692` in `LEG_Full_42` and `0.891154-0.901154` in the CLEAN rows, while renters move much more sharply (`LEG_Full_42 = 0.714615`, `CLN_Full_42 = 0.447308`). That belongs in Methods or Discussion as a negative result about prompt affordances, not as a core contribution.

EPI should be reported as a calibration heuristic, never as a pass/fail verdict. `gemma4_legacy_seed42/l2_macro_metrics.json` gives `epi=0.6115`, `gemma4_clean_seed42/l2_macro_metrics.json` gives `0.4968`, and `gemma4_clean_seed123/l2_macro_metrics.json` returns to `0.6115`. The threshold is author-chosen, and the difference hinges on marginal bracket crossings such as `insurance_rate_all` and `govt_decrease_count`, not on a stable regime change.

The triple-lock interpretation of the MG-owner trap does not hold. `deep_synthesis/rq_deep/rq3_step5_mg_owner.csv` shows MG-owner survey PA is lower than NMG-owner in every arm (`3.0146` vs `3.2255/3.2261`), and MG-owner SP-low shares are also lower, not higher: for example `LEG_Full_42` is `0.178462` for MG-owner versus `0.206154` for NMG-owner, and `CLN_Full_42` is `0.153846` versus `0.198462`. The gap remains behaviorally real because pooled do-nothing and Y13 insurance still separate, but it is a single-channel affordability/persistence story, not a multi-channel lock.

RQ2 pairwise significance must stay secondary. `deep_synthesis/significance_tests.md` line 53 reports `ANOVA F=1.677360, p=1.380151e-01` for MG-owner Y13 insurance across the six arms, and the Tukey table on lines 57-73 rejects no pairwise comparison. The direction is informative; the inferential claim is not strong enough for a headline.

## 4. Framework Contributions (WAGF)

The paper's framework contribution is broader than any one benchmark row. At the implementation level, WAGF exposes memory policy as a broker-level API rather than a hidden prompt decision. The relevant machinery lives in `broker/components/memory/` and in the run manifests that distinguish which content types are retained or blocked. That makes memory policy reproducible, auditable, and experimentally comparable, which is the precondition for the dual-role result above.

The second framework contribution is sequential governance. Paper 3 is not reporting raw LLM intentions; it reports approved and executed actions after Government, Insurance, and Household logic have all acted. That alignment is the reason the EXECUTED-ONLY rule matters. It also makes the comparison to Traditional FLOODABM conceptually cleaner because both paradigms are judged on realized outcomes, not on pre-governance drafts.

The most transferable WAGF observation is therefore the dual-role memory result. In future LLM-ABMs, "cleaning" memory may remove undesirable self-reference while simultaneously weakening persistence, diversity, or path dependence. Paper 3 gives a concrete six-arm example of that design trade-off.

## 5. RQ-to-Contribution Mapping

| Contribution | RQ1 | RQ2 | RQ3 | Discussion |
|---|---|---|---|---|
| SP coupling invariance |  |  | HEADLINE | framework validation |
| Premium burden mechanism |  | HEADLINE |  | institutional interpretation |
| Dual-role memory |  |  |  | HEADLINE |
| Cross-paradigm matrix | HEADLINE |  |  | model selection map |
| Owner Y1 priming |  |  | supporting | prompt-level negative result |
| EPI calibration row | supporting | supporting |  | methods caveat |

## 6. Evidence Table

| Claim / caveat | Evidence file | Specific row(s) / line(s) |
|---|---|---|
| SP coupling invariance | `deep_synthesis/significance_tests.md` | Lines 34-39: six arm rows with `cramers_v=0.383901-0.416349` |
| SP low vs high protection | `deep_synthesis/rq_deep/rq3_step2_cross_sectional.csv` | Rows `(LEG_Full_42,L=0.078667)`, `(CLN_Full_42,L=0.042161)`, `(CLN_Full_42,H=0.892286)`, `(LEG_Full_42,H=0.879195)` plus analogous Flat rows |
| Within-agent SP transitions | `deep_synthesis/rq_deep/rq3_step3_within_agent.csv` | Arm rows `CLN_Flat_123`, `CLN_Flat_42`, `CLN_Flat_456`, `CLN_Full_123`, `CLN_Full_42`, `LEG_Full_42` |
| Premium burden | `deep_synthesis/rq_deep/rq2_premium_burden.csv` | Representative year-13 rows for owners and renters across `LEG_Full_42`, `CLN_Full_42`, `CLN_Flat_42` |
| Full vs Flat owner significance | `deep_synthesis/significance_tests.md` | Lines 6-13 |
| Full vs Flat renter non-significance | `deep_synthesis/significance_tests.md` | Lines 18-29 |
| Ratchet language | `deep_synthesis/past_reference_6arm.csv` | Year-13 rows for all six arms, owner and renter |
| Renter relocation collapse | `deep_synthesis/cell_actions_6arm.csv` | Rows where `action_category=relocate` and `cell in {MG-Renter,NMG-Renter}` |
| Cross-paradigm matrix | `deep_synthesis/rq_deep/rq1_cross_paradigm_stats.csv` | Rows for `elevate_house`, `buyout_program`, `buy_contents_insurance`, `do_nothing` |
| Triple-lock does not hold | `deep_synthesis/rq_deep/rq3_step5_mg_owner.csv` | MG-owner vs NMG-owner rows for all six arms |
| ANOVA non-significant | `deep_synthesis/significance_tests.md` | Lines 53-73 |
| EPI seed sensitivity | `gemma4_legacy_seed42/l2_macro_metrics.json`, `gemma4_clean_seed42/l2_macro_metrics.json`, `gemma4_clean_seed123/l2_macro_metrics.json` | Top-level `epi` field |

## 7. Limitations

The design remains asymmetric. There is only one LEGACY Full seed, no LEGACY Flat arm, and the interrupted CLEAN Full seed_456 was not rerun. That means the six-arm panel supports CLEAN cross-seed robustness and Full-vs-Flat institutional contrasts, but not a complete 2 x 2 institutional x memory factorial. There is also a small trace-count anomaly: `CLN_Flat_123` owner traces total `2599`, not `2600`, which is reflected in `rq3_step1_construct_validity.csv` and the synthesis totals.

RQ3 Step 1 is now usable for both tenures, but renter construct validity comes from integrated prose fallback rather than per-construct reason fields. `deep_synthesis/rq_deep/rq3_step1_construct_validity.csv` flags this explicitly in the `reason_source` column (`per_construct` for owners, `integrated_prose` for renters). Finally, EPI ranges remain author-selected brackets, and several institutional benchmarks are structurally `NA` in Flat arms because those runs do not instantiate adaptive government or insurance agents.

## 8. Ready-to-Write Signal

Section `4.1` is ready because the six-arm panel, commit history, and Traditional FLOODABM reference outputs are all in place. Section `4.2` is ready from `rq1_cross_paradigm_stats.csv` and `rq1_cross_paradigm_report.md`. Section `4.3` is ready with the explicit caveat that MG-owner Y13 insurance is pattern-level, not statistically significant. Section `4.4` is ready because the five-step chain is complete and Step 1 now includes renter data via integrated prose fallback. Section `4.5` is ready because the dual-role memory narrative is now supported by both ratchet-language and action-diversity evidence. Section `4.6` is ready for CLEAN cross-seed robustness. The only real blocker left is authorial judgment: Yang review should decide how prominently to foreground the dual-role trade-off and how much calibration detail belongs in the main text versus a table.
