# WAGF metric definitions (canonical implementations)

Every metric used by this skill cites the exact production
implementation. Never reimplement; always import or shell out.

## IBR (Irrational Behaviour Rate)

**Definition** (per Methods + MEMORY.md): IBR = (R1+R3+R4) / total
where:

- R1: high-threat inaction → `construct_TP_LABEL ∈ {H, VH}` AND
  `final_skill == do_nothing`
- R3: low-threat relocation → `construct_TP_LABEL ∈ {VL, L}` AND
  `final_skill == relocate`
- R4: low-threat elevation → `construct_TP_LABEL ∈ {VL, L}` AND
  `final_skill == elevate_house`
- R5: re-elevation → EXCLUDED per EDT2.

Returns a fraction (0..1). Multiply by 100 for percent in tables.

**Canonical implementation**:
- `examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py:100`
  (`compute_ibr_components`).

**For irrigation** (different action vocabulary): IBR = fraction of
high-WSA decisions that propose increase (any `increase_*` skill).
Implementation at `examples/irrigation_abm/analysis/compute_ibr.py`.
The two formulations are NOT interchangeable — the skill must dispatch
to the domain-specific one.

## EHE (Effective Heterogeneity Entropy)

**Definition**: normalized Shannon entropy over the action distribution
across all decisions in the pool, divided by `log2(k)` where k is the
number of unique actions in the agent's decision interface.

- Flood: k = 4 (do_nothing, buy_insurance, elevate_house, relocate).
- Irrigation: k = 5 (increase_large/small, maintain_demand,
  decrease_small/large).

Pool ALL decisions across agents and years; do NOT yearly-average then
mean. (Yearly-averaging gives ~0.63 vs aggregate ~0.86 — the latter is
correct per MEMORY.md.)

**Canonical implementation**:
- `examples/irrigation_abm/analysis/nw_bootstrap_ci.py:shannon_entropy`.

## Rejection rate

**Definition**: fraction of decisions where `status != "APPROVED"`.

**Where to read**: `household_governance_audit.csv:status` column.

## Retry rate

**Definition**: fraction of decisions where `retry_count > 0`.

**Where to read**: `household_governance_audit.csv:retry_count` column.

## Mean retries per decision

**Definition**: mean of `retry_count` across all decisions.

## Retry compliance Pattern A/B/C

Per Methods + `tests/test_gemma4_nw_crossmodel_analysis.py`:

- **Pattern A (appraisal downgrade)**: TP label lowered AND original
  proposed_skill retained.
- **Pattern B (action upgrade)**: TP label held AND action shifted to
  more protective.
- **Pattern C (joint recalibration)**: BOTH TP and action change.

**Canonical implementation**:
- `examples/single_agent/analysis/compute_retry_compliance.py`.

## Temporal diagnostic M1/M2/M3

- **M1 (appraisal-history coherence)**: salient event in prior
  3-year memory window AND current threat label in low set.
- **M2 (behavioural inertia)**: 5 consecutive years of same action
  while environmental threat spans ≥2 ordinal levels.
- **M3 (evidence-grounded irreversibility)**: year-1 irreversible
  action with no salient event in seed memory.

**Canonical implementation**:
- `examples/single_agent/analysis/compute_temporal_diagnostics.py`
  with `--gemma4-pipeline {v1,v2}` flag.

## Paired t-test (governed vs disabled)

**ΔIBR** = (no-validator IBR) − (governed IBR), positive = validators
reduce IBR.

**ΔEHE** = (governed EHE) − (no-validator EHE).

Use `scipy.stats.ttest_rel` on matched seeds. 95% CI via
`scipy.stats.t.interval(0.95, df=n-1, loc=diff.mean(),
scale=diff.std(ddof=1)/sqrt(n))`.

**Reference implementation**:
- `paper/nature_water/scripts/gen_sfig_forest.py:paired_stats`.

## What this skill does NOT compute

- **Cohen's d**: only by request. Implementation at
  `examples/irrigation_abm/analysis/nw_bootstrap_ci.py:cohens_d`.
- **Bootstrap CIs**: only by request. Same file.
- **Construct-action coherence rate**: out-of-scope; defer to a
  separate analysis or expand metrics catalogue.
- **WAGF Coherence Index**: does not exist; refuse if asked.
