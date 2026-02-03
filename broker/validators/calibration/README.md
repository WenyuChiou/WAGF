# Calibration & Validation (C&V) Framework

Generic, domain-agnostic validation pipeline for LLM-driven agent-based
models.  Part of the **SAGE** (Structured Agent Governance Engine) framework.

## Architecture

The C&V framework validates LLM-ABM outputs at three hierarchical levels,
following Grimm et al. (2005) pattern-oriented modelling principles:

```text
Level 1 — MICRO    Individual agent reasoning coherence
Level 2 — MACRO    Population-level distributional calibration
Level 3 — COGNITIVE  Psychological construct fidelity (psychometric)
```

### Design Principles

- **Domain-agnostic**: All modules accept column names, construct keys,
  keyword lists, and framework definitions as parameters.  No flood-,
  irrigation-, or other domain-specific logic is hardcoded.
- **Config-driven routing**: The `ValidationRouter` auto-detects which
  validators are applicable based on an `agent_types.yaml` config and/or
  a simulation DataFrame — callers do not need to know which metrics to run.
- **Zero LLM calls for post-hoc**: Levels 1 and 2 operate entirely on
  trace CSVs.  Level 3 (psychometric probing) requires LLM calls but is
  orchestrated externally — the battery only handles statistics.
- **Framework-pluggable**: Psychological frameworks (PMT, utility,
  financial, or custom) are registered via `broker.core.psychometric` and
  referenced by name.  The validation layer delegates coherence checking to
  the active framework.

---

## Module Overview

| Module | Level | Purpose |
|--------|-------|---------|
| `micro_validator.py` | L1 | CACR, EGS, BRC computation |
| `temporal_coherence.py` | L1 | TCS and Action Stability |
| `distribution_matcher.py` | L2 | KS, Wasserstein, chi-squared, PEBA |
| `psychometric_battery.py` | L3 | ICC(2,1), Cronbach's alpha, Fleiss' kappa, eta-squared, convergent/discriminant validity |
| `validation_router.py` | — | Feature detection + decision-tree routing |
| `cv_runner.py` | — | Three-level orchestrator (explicit and auto-detect modes) |
| `__init__.py` | — | Public re-exports |

---

## Metrics Reference

### Level 1 — MICRO (Individual Reasoning)

| Metric | Full Name | What It Measures | Threshold |
|--------|-----------|-----------------|-----------|
| **CACR** | Construct-Action Coherence Rate | Fraction of agent-year observations where the chosen action is coherent with reported psychological constructs | >= 0.80 |
| **EGS** | Evidence Grounding Score | Fraction of reasoning traces that reference factual context-window information | Diagnostic |
| **R_H** | Hallucination Rate | Physical + thinking-rule hallucinations (via `unified_rh.py`) | <= 0.10 |
| **EBE** | Effective Behavioral Entropy | Diversity-correctness tradeoff: H_norm * (1 - R_H) | Diagnostic |
| **TCS** | Temporal Consistency Score | 1 - (impossible construct transitions / total transitions) | >= 0.90 |

### Level 2 — MACRO (Population Calibration)

| Metric | Full Name | What It Measures | Threshold |
|--------|-----------|-----------------|-----------|
| **BRC** | Behavioral Reference Concordance | Fraction of observations where LLM action matches the framework's expected behavior set | >= 0.60 |
| **KS** | Kolmogorov-Smirnov | CDF distance between simulated and reference distributions | N >= 200 |
| **Wasserstein** | Earth-Mover Distance | Continuous distribution distance | N >= 200 |
| **Chi-squared** | Goodness-of-Fit | Categorical action distribution match | N >= 200 |
| **PEBA** | Pattern Extraction-Based Analysis | Distribution shape features (mean, variance, skew, kurtosis) | Diagnostic |

### Level 3 — COGNITIVE (Psychometric Fidelity)

| Metric | Full Name | What It Measures | Threshold |
|--------|-----------|-----------------|-----------|
| **ICC(2,1)** | Intraclass Correlation Coefficient | Test-retest reliability across replicates (Shrout & Fleiss 1979) | >= 0.60 |
| **eta-squared** | Between-group effect size | Variance in construct ratings explained by archetype identity | >= 0.25 |
| **Cronbach's alpha** | Internal consistency | Correlation between construct ratings treated as scale items | >= 0.70 |
| **Fleiss' kappa** | Inter-rater agreement | Action agreement across replicates (nominal) | >= 0.40 |
| **Convergent validity** | Construct-criterion correlation | Spearman rho between construct ordinal and external criterion (e.g., scenario severity) | >= 0.30 |
| **Discriminant** | TP-CP correlation | Pearson r between constructs — too high (> 0.8) means constructs are not discriminated | < 0.80 |

---

## Key Classes

### `CVRunner` (cv_runner.py)

The main entry point.  Supports two construction modes:

**Explicit mode** — caller specifies framework, column names, and group:

```python
from broker.validators.calibration.cv_runner import CVRunner

runner = CVRunner(
    trace_path="results/simulation_log.csv",
    framework="pmt",               # or "utility", "financial"
    ta_col="threat_appraisal",     # primary appraisal column
    ca_col="coping_appraisal",     # secondary appraisal column
    decision_col="yearly_decision",
    reasoning_col="reasoning",
    group="B",
    start_year=2,
)
report = runner.run_posthoc()
print(report.summary)
```

**Auto-detect mode** — pass `agent_types.yaml` config and/or a DataFrame:

```python
import yaml

with open("agent_types.yaml") as f:
    config = yaml.safe_load(f)

runner = CVRunner.from_config(config=config, df=trace_df)
print(runner.plan.summary())      # inspect what will run
report = runner.run_posthoc()
report.save_json("cv_report.json")
```

### `ValidationRouter` (validation_router.py)

Auto-detects features and generates a validation plan:

```python
from broker.validators.calibration.validation_router import ValidationRouter

profile = ValidationRouter.detect_features(config=config, df=df)
plan = ValidationRouter.plan(profile)

for spec in plan.all_validators:
    print(f"  {spec.type.value}: {spec.reason}")
```

The router's decision tree:

- **L1 CACR**: enabled when constructs + framework detected
- **L1 R_H**: enabled when actions detected
- **L1 TCS**: enabled when temporal data + ordinal constructs detected
- **L2 BRC**: enabled when constructs + framework + actions detected
- **L2 Distribution Match**: enabled when N >= 200 + reference data
- **L3 ICC**: enabled when actions detected (requires external probing)
- **L3 EBE**: enabled when actions + temporal data detected

### `MicroValidator` (micro_validator.py)

Computes CACR and EGS from simulation trace DataFrames:

```python
from broker.validators.calibration.micro_validator import MicroValidator

validator = MicroValidator(
    framework="pmt",
    ta_col="threat_appraisal",
    ca_col="coping_appraisal",
    decision_col="yearly_decision",
    context_keywords=["flood depth", "damage", "insurance"],  # domain-specific
)
report = validator.compute_full_report(df, reasoning_col="reasoning")
print(f"CACR = {report.cacr:.3f}, EGS = {report.egs:.3f}")
```

The `context_keywords` parameter controls EGS keyword matching — callers
provide domain-specific terms.  An empty list disables keyword-based EGS.

### `DistributionMatcher` (distribution_matcher.py)

Population-level distributional tests (KS, Wasserstein, chi-squared, PEBA):

```python
from broker.validators.calibration.distribution_matcher import DistributionMatcher

matcher = DistributionMatcher()
report = matcher.compute_full_report(
    df,
    reference_data={"insurance_rate": 0.35, "elevation_rate": 0.05},
    decision_col="yearly_decision",
)
```

Requires `scipy` for statistical tests.  Falls back gracefully when not
installed (returns zero-valued results).

### `TemporalCoherenceValidator` (temporal_coherence.py)

Detects impossible construct transitions between consecutive years:

```python
from broker.validators.calibration.temporal_coherence import (
    TemporalCoherenceValidator,
    ActionStabilityValidator,
)

# Construct-level TCS (requires ordinal constructs)
tcs_validator = TemporalCoherenceValidator()
tcs_report = tcs_validator.compute_tcs(df, start_year=2)

# Construct-free action stability (works without psychological constructs)
stability = ActionStabilityValidator(decision_col="yearly_decision")
stability_report = stability.compute(df, start_year=2)
```

### `PsychometricBattery` (psychometric_battery.py)

Level 3 cognitive validation via standardized vignette probes:

```python
from broker.validators.calibration.psychometric_battery import (
    PsychometricBattery,
    ProbeResponse,
)

battery = PsychometricBattery(
    vignette_dir="path/to/domain/vignettes",  # caller provides vignettes
)
vignettes = battery.load_vignettes()

# Caller runs LLM probing externally, then feeds responses:
for archetype in archetypes:
    for vignette in vignettes:
        for rep in range(30):
            response = call_llm(archetype, vignette)  # external
            battery.add_response(ProbeResponse(
                vignette_id=vignette.id,
                archetype=archetype.id,
                replicate=rep + 1,
                tp_label=response["TP_LABEL"],
                cp_label=response["CP_LABEL"],
                decision=response["decision"],
            ))

report = battery.compute_full_report()
print(f"TP ICC = {report.overall_tp_icc.icc_value:.3f}")
print(f"eta^2  = {report.tp_effect_size.eta_squared:.3f}")
```

**Vignette format** (YAML):

```yaml
vignette:
  id: high_severity
  severity: high
  description: "Major flood event scenario"
  scenario: |
    A Category 3 flood has struck your neighborhood...
  state_overrides:
    flood_depth_ft: 4.5
    recent_damage: 42000
  expected_responses:
    TP_LABEL:
      acceptable: [H, VH]
      incoherent: [VL]
    decision:
      acceptable: [buy_insurance, elevate_house, buyout_program]
      incoherent: [do_nothing]
```

Vignettes are domain-specific and live in the caller's project directory,
not in `broker/`.  The battery module itself has no default vignette
directory — callers must provide one.

---

## Domain Integration

To use this framework with a new domain:

1. **Define a psychological framework** in `broker/core/psychometric.py`
   (or use an existing one: `pmt`, `utility`, `financial`).

2. **Create vignettes** in your domain's config directory following the
   YAML schema above.

3. **Create archetypes** (persona definitions for ICC probing) in your
   domain's config directory.

4. **Provide domain-specific keywords** to `MicroValidator` for EGS.

5. **Provide reference data** to `DistributionMatcher` for macro
   calibration (empirical rates from literature or surveys).

6. **Run via `CVRunner`** in explicit or auto-detect mode.

No changes to the `broker/validators/calibration/` code are needed.

---

## Migration Notes

### v3.5+ (Domain-Agnostic Refactoring)

If migrating from an earlier version:

- The `broker/validators/calibration/vignettes/` directory has been removed.
- `PsychometricBattery()` no longer has a default vignette directory.
- **Action required:** Explicitly provide `vignette_dir` when calling
  `PsychometricBattery(vignette_dir="path/to/your/domain/vignettes")`.
- Example vignettes (flood domain) are in
  `examples/multi_agent/flood/paper3/configs/vignettes/`.

---

## Batch Comparison

Compare C&V metrics across experiment groups, seeds, or ablations:

```python
reports = {
    "seed_42": runner_42.run_posthoc(),
    "seed_123": runner_123.run_posthoc(),
    "no_governance": runner_ng.run_posthoc(),
}
comparison_df = CVRunner.compare_groups(reports)
print(comparison_df[["group_label", "CACR", "BRC", "R_H", "TP_ICC"]])
```

---

## References

- Grimm, V., Revilla, E., et al. (2005). Pattern-oriented modeling of
  agent-based complex systems. *Science*, 310(5750), 987-991.
- Huang, J., et al. (2025). A psychometric framework for evaluating and
  shaping personality traits in large language models. *Nature Machine
  Intelligence*. doi:10.1038/s42256-025-01115-6
- Shrout, P.E. & Fleiss, J.L. (1979). Intraclass correlations: Uses in
  assessing rater reliability. *Psychological Bulletin*, 86(2), 420-428.
- Thiele, J.C., Kurth, W., & Grimm, V. (2014). Facilitating parameter
  estimation and sensitivity analysis of agent-based models: A cookbook
  using NetLogo and R. *JASSS*, 17(3), 11.
- Windrum, P., Fagiolo, G., & Moneta, A. (2007). Empirical validation
  of agent-based models: Alternatives and prospects. *JASSS*, 10(2), 8.
