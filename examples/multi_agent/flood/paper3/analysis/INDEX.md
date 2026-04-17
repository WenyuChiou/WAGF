# Paper 3 analysis directory

2026-04-16 preliminary complete. See `PAPER3_POSITIONING.md` for the contribution narrative.

Current note: the task brief refers to a 484-file preliminary tree, but the live `paper3/analysis/` directory now contains 741 files because later runs added flat-arm logs, cross-seed outputs, and generated artifacts. This index prioritizes the files needed for Paper 3 Section 4 and labels older or generated material separately.

## 1. How to use this directory

- Start with `PAPER3_POSITIONING.md`, then `deep_synthesis/DEEP_SYNTHESIS_REPORT.md`, then the three `deep_synthesis/rq_deep/` reports.
- Use the `deep_synthesis/` subtree for paper-ready cross-arm evidence; use per-arm directories only when you need original arm-specific tables, figures, or validation JSON.
- Treat historical markdown and old smoke-test material as archive unless this index explicitly points you there.

## 2. Headline outputs

- `PAPER3_POSITIONING.md`: contribution catalog for Yang review and Section 4 drafting.
- `deep_synthesis/DEEP_SYNTHESIS_REPORT.md`: 10-section six-arm synthesis.
- `deep_synthesis/rq_deep/rq1_cross_paradigm_report.md`: RQ1 classification and comparison summary.
- `deep_synthesis/rq_deep/rq2_mechanism_report.md`: RQ2 premium-burden mechanism summary.
- `deep_synthesis/rq_deep/rq3_five_step_report.md`: RQ3 five-step chain summary.

## 3. Figure input CSVs

| File | Purpose | Notes |
|---|---|---|
| `deep_synthesis/figures/fig_rq1_dual_timeseries.csv` | RQ1 dual-timeseries figure | 4 paradigm/arm references x 13 years x 7 actions |
| `deep_synthesis/figures/fig_rq2_full_vs_flat_forest.csv` | Full vs Flat forest plot | 9 benchmarks with mean, SE, delta |
| `deep_synthesis/figures/fig_rq3_construct_action_heatmap.csv` | RQ3 construct-action heatmap | 5 constructs x 6 arms x levels x actions |
| `deep_synthesis/figures/fig_ratchet_timeseries.csv` | Ratchet/past-reference trend figure | Year 1-13 by arm |
| `deep_synthesis/figures/fig_4cell_bubble.csv` | 4-cell bubble figure | Cell, arm, Y13 insurance, cumulative OOP |

## 4. Master cross-arm tables

| File | What it stores |
|---|---|
| `deep_synthesis/benchmark_6arm.csv` | 16 benchmark rows with in/out/NA markers plus CLEAN Full and CLEAN Flat pooled summaries |
| `deep_synthesis/cell_actions_6arm.csv` | 4 cells x 6 arms x action category executed shares plus Y13 end states |
| `deep_synthesis/construct_yearly_6arm.csv` | Year x arm x construct x agent-type mean construct scores |
| `deep_synthesis/past_reference_6arm.csv` | Year x arm x agent-type past-reference rates |
| `deep_synthesis/memory_content_6arm.csv` | Year x arm x agent-type x content-type mean memory entries |
| `deep_synthesis/institutional_6arm.csv` | Year x arm subsidy/CRS/premium/loss-ratio trajectory table |

## 5. RQ-deep package

### Reports

- `deep_synthesis/rq_deep/rq1_cross_paradigm_report.md`
- `deep_synthesis/rq_deep/rq2_mechanism_report.md`
- `deep_synthesis/rq_deep/rq3_five_step_report.md`

### CSVs

- `deep_synthesis/rq_deep/rq1_cross_paradigm_stats.csv`: 7 actions x 3 LLM-arm classification matrix against Traditional FLOODABM.
- `deep_synthesis/rq_deep/rq2_premium_burden.csv`: yearly premium-burden rows by arm, tenure, MG status.
- `deep_synthesis/rq_deep/rq2_burden_quartile_protection.csv`: burden quartiles and protection rates.
- `deep_synthesis/rq_deep/rq3_step1_construct_validity.csv`: Step 1 construct validity with `reason_source`.
- `deep_synthesis/rq_deep/rq3_step2_cross_sectional.csv`: Step 2 level-to-protection rates.
- `deep_synthesis/rq_deep/rq3_step3_within_agent.csv`: Step 3 SP transition table.
- `deep_synthesis/rq_deep/rq3_step4_override.csv`: Step 4 override diagnostics.
- `deep_synthesis/rq_deep/rq3_step5_mg_owner.csv`: Step 5 MG-owner vs NMG-owner summary.

## 6. Statistical tests

Primary file: `deep_synthesis/significance_tests.md`

- Lines 5-29: RQ2 Mann-Whitney tests for Full vs Flat by cell and action.
- Lines 33-39: RQ3 SP x protective-action coupling by arm.
- Lines 43-49: within-agent SP-up to switch-to-protective test by arm.
- Lines 53-73: ANOVA plus Tukey HSD for MG-owner Y13 insurance across six arms.

## 7. Commit landmarks

| Commit | Meaning |
|---|---|
| `14b55a6` | Full-arm experiment batch and memory-policy CLI support |
| `5609508` | Cross-seed CLEAN vs LEGACY analysis and Ablation B launcher |
| `9fd89ba` | Flat-arm analysis integration |
| `4b595f3` | Six-arm deep synthesis package |
| `d28ac74` | RQ1/2/3 deep cross-arm scripts plus 11 deep tables |
| uncommitted local change | Step 1 renter construct-validity fallback fix reflected in `rq3_step1_construct_validity.csv` |

## 8. Core synthesis subtree

### `deep_synthesis/`

- `DEEP_SYNTHESIS_REPORT.md`
- `benchmark_6arm.csv`
- `cell_actions_6arm.csv`
- `construct_yearly_6arm.csv`
- `cross_cutting_findings.md`
- `institutional_6arm.csv`
- `memory_content_6arm.csv`
- `past_reference_6arm.csv`
- `significance_tests.md`

### `deep_synthesis/figures/`

- `fig_4cell_bubble.csv`
- `fig_ratchet_timeseries.csv`
- `fig_rq1_dual_timeseries.csv`
- `fig_rq2_full_vs_flat_forest.csv`
- `fig_rq3_construct_action_heatmap.csv`

### `deep_synthesis/rq_deep/`

- `rq1_cross_paradigm_report.md`
- `rq1_cross_paradigm_stats.csv`
- `rq2_burden_quartile_protection.csv`
- `rq2_mechanism_report.md`
- `rq2_premium_burden.csv`
- `rq3_five_step_report.md`
- `rq3_step1_construct_validity.csv`
- `rq3_step2_cross_sectional.csv`
- `rq3_step3_within_agent.csv`
- `rq3_step4_override.csv`
- `rq3_step5_mg_owner.csv`

## 9. Per-arm outputs

All six arm directories follow the same navigation logic:

- Validation files: `benchmark_comparison.csv`, `cgr_metrics.json`, `l1_micro_metrics.json`, `l2_macro_metrics.json`, `validation_report.json`.
- RQ1 files: `rq1_owner_comparison.csv`, `rq1_renter_comparison.csv`, `rq1_tp_decay_by_group.csv`, `rq1_tp_decay_within_agent.csv`, `rq1_trad_vs_llm_trajectories.png`.
- RQ2 files: `rq2_4cell_proposed_vs_executed.csv`, `rq2_equity_figure.png`, `rq2_equity_summary.csv`; Full arms also include `rq2_ablation_*`, `rq2_policy_trajectory.csv`, `rq2_institutional_dynamics.png`, `rq2_insurance_feedback.png`, and `rq2_affordability_constraint.png`.
- RQ3 files: `rq3_action_exhaustion.csv`, `rq3_construct_action_feedback.csv`, `rq3_construct_action_profiles.csv`, `rq3_construct_stats.csv`, `rq3_cp_by_income.csv`, `rq3_crosslayer_analysis.csv`, `rq3_feedback_rigorous.csv`, `rq3_sp_pa_yearly.csv`, `rq3_tp_by_cumflood.csv`, `rq3_tp_cp_gap.csv`, `rq3_tp_decay.csv`, `rq3_unconstrained_constructs.csv`, plus the figure set `rq3_entropy.png`, `rq3_decision_correlation.png`, `rq3_fig1_pmt_dynamics_4panel.png`, `rq3_fig2_pmt_action_heatmap.png`, `rq3_fig3_tp_decay.png`, `rq3_firstmover_channels.png`, `rq3_kaplan_meier.png`, `rq3_morans_i.png`, `rq3_channel_citation_rates.png`, `rq3_channel_flood_experience.png`.
- Common generated subdirs: `memory_dynamics/` and `reasoning_taxonomy/`.
- Full-only generated subdir: `institutional_rationale/`.

Shared generated subdirectory contents:

| Subdir | Files |
|---|---|
| `memory_dynamics/` | `memory_size_by_year.csv`, `memory_content_type_by_year.csv`, `memory_category_by_year.csv`, `memory_rationalization_phrases_by_year.csv`, `memory_new_writes_by_decision_year.csv`, `memory_content_dynamics_report.md` |
| `reasoning_taxonomy/` | `audit_scores_by_year.csv`, `reasoning_phrase_detection_by_year.csv`, `reason_text_length_by_year.csv`, `reason_vocabulary_by_construct.csv`, `reason_vocabulary_by_mg.csv`, `skill_proposal_reasoning_report.md` |
| `institutional_rationale/` | `institutional_trajectory.csv`, `institutional_rationale_text.csv`, `institutional_rationale_categories_by_year.csv`, `institutional_rationale_report.md` |

Arm-specific map:

| Directory | Identity | Commit context | Distinguishing notes |
|---|---|---|---|
| `gemma4_legacy_seed42/` | LEGACY Full seed 42 | `14b55a6` full run | Only LEGACY arm; strongest ratchet-language rows; includes `institutional_rationale/`; `epi=0.6115` |
| `gemma4_clean_seed42/` | CLEAN Full seed 42 | `14b55a6` full run | Main LEGACY vs CLEAN contrast; includes `institutional_rationale/`; `epi=0.4968` |
| `gemma4_clean_seed123/` | CLEAN Full seed 123 | `4b595f3` six-arm synthesis | Second CLEAN Full seed; includes `institutional_rationale/`; `epi=0.6115` |
| `gemma4_ablation_flat_seed42/` | CLEAN Flat seed 42 | `5609508` launcher, `9fd89ba` analysis | No adaptive institutional traces, so no `institutional_rationale/`; static-policy baseline |
| `gemma4_ablation_flat_seed123/` | CLEAN Flat seed 123 | `5609508` launcher, `9fd89ba` analysis | Adds `logs_20260416_170923/` and `logs_20260416_171048/` bundles |
| `gemma4_ablation_flat_seed456/` | CLEAN Flat seed 456 | `5609508` launcher, `9fd89ba` analysis | Only seed_456 evidence in final six-arm panel; adds `logs_20260416_171235/` |

Flat-arm caveat:

- Flat arms have 3-4 fewer institutional outputs because government/insurance are fixed context, not active agents.
- Institutional benchmark rows in `benchmark_6arm.csv` therefore show `NA` for several Flat-arm entries.

Recommended file-open order inside any arm directory:

1. `run_log.txt`
2. `l2_macro_metrics.json`
3. `rq2_4cell_proposed_vs_executed.csv`
4. `rq3_sp_pa_yearly.csv`
5. `memory_dynamics/memory_content_dynamics_report.md`
6. `reasoning_taxonomy/skill_proposal_reasoning_report.md`
7. `institutional_rationale/institutional_rationale_report.md` for Full arms only

## 10. Analysis scripts at root

### RQ1 scripts

- `rq1_deep_cross_paradigm.py`
- `rq1_memory_analysis.py`
- `rq1_publication_figure.py`
- `rq1_tp_decay_within_agent.py`
- `rq1_traditional_comparison.py`

### RQ2 scripts

- `rq2_equity_figure.py`
- `rq2_institutional_analysis.py`
- `rq2_mechanism_decomposition.py`
- `rq2_proposed_vs_executed.py`

### RQ3 scripts

- `rq3_construct_action_feedback.py`
- `rq3_construct_dynamics.py`
- `rq3_crosslayer_analysis.py`
- `rq3_feedback_rigorous.py`
- `rq3_five_step_chain.py`
- `rq3_pmt_dynamics.py`
- `rq3_social_analysis.py`
- `rq3_unconstrained_constructs.py`

### Memory / institutional analysis scripts

- `analyze_institutional_rationale.py`
- `analyze_memory_content_dynamics.py`
- `analyze_skill_proposal_reasoning.py`
- `memory_causal_test.py`

### Four-cell and figure scripts

- `4cell_behavior_analysis.py`
- `4cell_tp_decay_analysis.py`
- `fig_4cell_behavior_distribution.py`
- `fig_agent_spatial_distribution.py`
- `fig_system_architecture.py`

### Validation / compute scripts

- `audit_to_cv.py`
- `calibration_hooks.py`
- `compute_cacr_null_model.py`
- `compute_validation_metrics.py`
- `config_loader.py`
- `cross_seed_robustness.py`
- `empirical_benchmarks.py`
- `example_cv_usage.py`
- `export_agent_initialization.py`
- `verify_clean_policy_checkpoint.py`

### Experimental / sensitivity scripts

- `gemma4_ma_crossmodel_analysis.py`
- `gemma4_rerun_vs_gemma3_analysis.py`
- `pa_prompt_calibration_test.py`
- `persona_sensitivity.py`
- `prompt_sensitivity.py`

## 11. Root markdown and documents

### Current-use markdown

- `gemma4_cross_seed_clean_vs_legacy.md`
- `gemma4_legacy_clean_comprehensive_report.md`
- `rq1_gemma4_legacy_vs_traditional.md`
- `rq2_ablation_expert_panel.md`
- `README.md`

### Reference / background markdown

- `CV_Module_Expert_Review_2026-02-14.md`
- `expert_panel_renter_relocation.md`
- `expert_review_pilot_v4.md`
- `hybrid_expert_panel_discussion.md`
- `hybrid_expert_panel_gov_round2.md`
- `IMPLEMENTATION_CHECKLIST.md`
- `L2_behavioral_plausibility_diagnosis.md`
- `nfip_trajectory_validation.md`
- `pa_prompt_calibration_results.md`
- `README_CV_zh.md`
- `VALIDATION_EXPERT_ASSESSMENT.md`

### Binary documents

- `CV_Module_Expert_Review_2026-02-14.docx`
- `L2_benchmark_adjustment_analysis.docx`

## 12. Config, validation, and support subtrees

### `configs/`

- `benchmarks/`: benchmark YAML and calibration references.
- `hallucination/`: hallucination-detection configs.
- `theories/`: theory config inputs for validation.

### `validation/`

- Engine, metric modules, benchmark registries, trace schema, and reporting utilities.
- Not a paper-output directory; use when re-running validation or verifying how EPI is computed.

### `tables/`

- Older table outputs from pre-synthesis analyses.
- Useful for tracing script lineage, but superseded for Section 4 by `deep_synthesis/`.

### `figures/`

- Publication-facing figure scripts and working assets outside the `deep_synthesis/figures/` paper-ready CSV package.

### `working/`

- Notes, review drafts, and staging files.
- Not stable evidence unless promoted into `deep_synthesis/`.

## 13. Archived or historical material

- `gemma4_rerun_vs_gemma3.md`: historical comparison note only; do not cite in Paper 3 headline content.
- `traditional_vs_llm_comparison.md`: older comparison note superseded by `rq1_gemma4_legacy_vs_traditional.md` and the six-arm deep synthesis.
- `RESULTS_INVENTORY.md`: superseded by this index for navigation.
- `gemma3_400agent_smoke_test_recommendations.md`: pre-production smoke-test history.
- `gemma3_bias_analysis_dr_liu.md`: historical bias memo.
- `SMOKE_TEST_DIAGNOSIS_SUMMARY.md`: smoke-test workflow artifact.
- `SMOKE_TEST_EXPERT_ASSESSMENT.md`: smoke-test assessment artifact.

## 14. Fast lookup by question

### If you need the strongest headline result

- Open `PAPER3_POSITIONING.md`.
- Then check `deep_synthesis/significance_tests.md` lines 33-49.

### If you need RQ1 evidence

- Open `deep_synthesis/rq_deep/rq1_cross_paradigm_report.md`.
- Then inspect `deep_synthesis/rq_deep/rq1_cross_paradigm_stats.csv`.
- Use `deep_synthesis/figures/fig_rq1_dual_timeseries.csv` for plot-ready inputs.

### If you need RQ2 evidence

- Open `deep_synthesis/rq_deep/rq2_mechanism_report.md`.
- Then inspect `deep_synthesis/rq_deep/rq2_premium_burden.csv`.
- Use `deep_synthesis/significance_tests.md` lines 5-29 for pooled Full vs Flat tests.

### If you need RQ3 evidence

- Open `deep_synthesis/rq_deep/rq3_five_step_report.md`.
- Then inspect `rq3_step1_construct_validity.csv` through `rq3_step5_mg_owner.csv`.
- Use `deep_synthesis/significance_tests.md` lines 33-49 for the strongest SP-coupling rows.

### If you need the dual-role memory evidence

- Open `deep_synthesis/past_reference_6arm.csv`.
- Then inspect `deep_synthesis/cell_actions_6arm.csv`.
- If needed, drill into per-arm `memory_dynamics/` and `reasoning_taxonomy/` reports.

### If you need calibration/EPI evidence

- Open `gemma4_legacy_seed42/l2_macro_metrics.json`.
- Open `gemma4_clean_seed42/l2_macro_metrics.json`.
- Open `gemma4_clean_seed123/l2_macro_metrics.json`.
- Cross-check with `deep_synthesis/benchmark_6arm.csv`.

## 15. TODOs for next session

- Draft Section 4 prose using `PAPER3_POSITIONING.md` and the `deep_synthesis/` subtree.
- Decide whether the missing LEGACY Flat cell warrants a follow-on run.
- Decide whether CLEAN Full seed_456 should be rerun for fuller robustness.
- Keep EPI in a calibration table row and do not use the threshold as a verdict.
- Preserve the Step 1 renter `integrated_prose` caveat when drafting RQ3.
