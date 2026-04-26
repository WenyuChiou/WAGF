# WAGF metrics catalogue

The complete list of metrics this skill can include in an experiment
matrix. Adding a new metric requires implementing the formula in
`examples/<domain>/analysis/` first. Do NOT include any metric not
listed here.

## ibr (Irrational Behaviour Rate)

- **Domains**: flood, irrigation
- **Definition (flood)**: (R1+R3+R4) / total_decisions, where R1 =
  high-threat inaction, R3 = low-threat relocation, R4 = low-threat
  elevation. R5 (re-elevation) excluded per EDT2.
- **Definition (irrigation)**: fraction of high-WSA (H or VH) decisions
  that propose any `increase_*` skill.
- **Canonical scripts**:
  - flood: `examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py:100`
    (`compute_ibr_components`)
  - irrigation: `examples/irrigation_abm/analysis/compute_ibr.py`
- **Output**: fraction in [0, 1].
- **Use for**: governance-effect headline (paper EDT1/EDT2).

## ehe (Effective Heterogeneity Entropy)

- **Domains**: flood (k=4), irrigation (k=5)
- **Definition**: normalized Shannon entropy over the action
  distribution pooled across all decisions, divided by `log2(k)`.
- **Canonical script**:
  `examples/irrigation_abm/analysis/nw_bootstrap_ci.py:shannon_entropy`
- **Output**: float in [0, 1].
- **Important**: pool decisions across agents AND years; do NOT
  yearly-average then mean (gives ~0.63 vs correct ~0.86).
- **Use for**: behavioural diversity (paper EDT1/EDT2).

## rejection_rate

- **Domains**: flood, irrigation, MA flood
- **Definition**: fraction of decisions where `status != "APPROVED"`.
- **Read from**: `household_governance_audit.csv:status`.
- **Output**: fraction in [0, 1].
- **Use for**: governance assertiveness (paper SI Note 5).

## retry_rate

- **Domains**: flood, irrigation, MA flood
- **Definition**: fraction of decisions where `retry_count > 0`.
- **Read from**: `household_governance_audit.csv:retry_count`.
- **Output**: fraction in [0, 1].
- **Use for**: validator-LLM friction (paper SI Note 5).

## mean_retries_per_decision

- **Definition**: mean of `retry_count` across all decisions.
- **Read from**: `household_governance_audit.csv:retry_count`.

## retry_compliance_pattern_abc

- **Domains**: flood (Pattern A/B/C), irrigation
- **Definition**:
  - Pattern A (appraisal downgrade): TP label lowered AND original
    proposed_skill retained.
  - Pattern B (action upgrade): TP label held AND action shifted to
    more protective.
  - Pattern C (joint recalibration): both TP and action change.
- **Canonical script**:
  `examples/single_agent/analysis/compute_retry_compliance.py`
- **Output**: counts per pattern per (model, condition).
- **Use for**: paper SI Table 8.

## temporal_diagnostics (M1, M2, M3)

- **Domains**: flood
- **Definition**:
  - M1 = appraisal–history coherence violations
    (salient flood in 3-yr memory window AND current TP in low set).
  - M2 = behavioural inertia (5 consecutive years same action while
    threat spans ≥2 ordinal levels).
  - M3 = evidence-grounded irreversibility (year-1 irreversible
    action with no salient seed memory).
- **Canonical script**:
  `examples/single_agent/analysis/compute_temporal_diagnostics.py
  --gemma4-pipeline {v1,v2}`
- **Output**: per-run M1/M2/M3 trigger counts and rates.
- **Use for**: paper SI Note 11 + Table 7.

## demand_ratio (irrigation only)

- **Definition**: per-agent-row mean of `request / water_right`,
  averaged across agent-year rows (M3 aggregation).
- **Read from**: `simulation_log.csv:request, water_right`.
- **Output**: float in [0, 1].
- **Use for**: paper EDT1 system-outcome.

## mean_mead_level (irrigation only)

- **Definition**: per-year mean of `lake_mead_level` averaged across
  the 42-year horizon.
- **Read from**: `simulation_log.csv:lake_mead_level`.
- **Use for**: paper EDT1.

## min_mead_level (irrigation only)

- **Definition**: minimum `lake_mead_level` across all years.
- **Read from**: `simulation_log.csv:lake_mead_level`.
- **Use for**: paper EDT1.

## shortage_years (irrigation only)

- **Definition**: count of years with `shortage_tier > 0`.
- **Read from**: `simulation_log.csv:shortage_tier`.
- **Use for**: paper EDT1.

## paired_t_delta_ibr / paired_t_delta_ehe

- **Definition**: paired t-test on (governed_metric, disabled_metric)
  vectors matched by seed.
- **Canonical helper**: `paper/nature_water/scripts/gen_sfig_forest.py:paired_stats`.
- **Output**: (mean_diff, ci_lo, ci_hi, p, n).
- **Use for**: paper SI Table 6, SFig 1.

## NOT in catalogue (refuse)

If user asks for any of these, the skill must refuse and require
either implementing a new script or picking an existing metric:

- "WAGF Coherence Index" — does not exist.
- "Hallucination Severity" — not formalized.
- "Trust score" — not formalized.
- "Composite governance score" — not formalized.
- Any metric whose canonical implementation is not in
  `examples/<domain>/analysis/` or
  `paper/nature_water/scripts/`.
