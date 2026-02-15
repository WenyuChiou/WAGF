# Expert Review: WAGF C&V Validation Module
## Epidemiology / Health Behavior ABM Perspective

**Reviewer**: Dr. Priya Sharma (Epidemiologist, Health Behavior ABM)
**Date**: 2026-02-14
**Framework Version**: C&V Module as of commit 51ec1db

---

## Executive Summary

The WAGF C&V framework provides a thoughtful, theory-grounded validation protocol for LLM-driven agent-based models. As someone who builds pandemic preparedness ABMs using the Health Belief Model (HBM), I find the core architecture --- behavioral theory protocol, empirical benchmarks, hallucination detection --- to be the right abstractions. The three-level validation hierarchy (L3 cognitive, L1 micro, L2 macro) mirrors the kind of multi-scale validation that epidemiological ABMs desperately need but rarely implement.

However, the framework has significant gaps for health behavior applications: no network validation, no time-series metrics, no ensemble aggregation, and the construct-action mapping paradigm struggles with high-dimensional theories like HBM. I would estimate 3-4 months of targeted development to make this production-ready for a Lancet Digital Health submission.

**Overall Score: 3.3 / 5** (Promising architecture, significant domain gaps)

---

## Dimension-by-Dimension Evaluation

### 1. HBM Fit (Score: 2.5 / 5)

**The Problem**: HBM has 6 constructs (perceived susceptibility, perceived severity, perceived benefits, perceived barriers, cues to action, self-efficacy). The `BehavioralTheory` protocol uses `Dict[str, str]` for construct levels, which is technically flexible enough. The `get_coherent_actions()` method accepts arbitrary dimension names --- good.

**The Combinatorial Explosion**: With 5 ordinal levels per construct and 6 constructs, the full lookup table has 5^6 = 15,625 cells. The PMT implementation enumerates all 25 cells (5x5) explicitly in `PMT_OWNER_RULES`. Doing this for 15,625 cells is impractical and scientifically questionable --- we do not have empirical evidence for every combination.

**What Would Work Instead**: The `is_sensible_action()` fallback method in the protocol is the right escape hatch. For HBM, I would implement a hierarchical rule system:

```python
class HBMTheory:
    def get_coherent_actions(self, constructs, agent_type):
        # Primary gate: susceptibility x severity -> threat level
        threat = self._compute_threat(constructs["susceptibility"], constructs["severity"])
        # Secondary gate: benefits x barriers -> net motivation
        motivation = self._compute_net_motivation(constructs["benefits"], constructs["barriers"])
        # Modifiers: cues_to_action, self_efficacy
        return self._resolve_actions(threat, motivation,
                                      constructs["cues_to_action"],
                                      constructs["self_efficacy"],
                                      agent_type)
```

This collapses the 6D space into interpretable 2D gates plus modifiers --- consistent with how HBM actually works theoretically (Champion & Skinner 2008). The framework's protocol allows this, but the documentation and examples strongly imply flat lookup tables. A hierarchical composition pattern should be documented as a first-class paradigm.

**Verdict**: The protocol is flexible enough, but the examples and documentation push users toward an unscalable flat-table pattern. The `is_sensible_action()` fallback is under-documented.

---

### 2. Epidemiological Benchmarks (Score: 2.0 / 5)

**Current Design**: Each benchmark in `BenchmarkRegistry` is a function that takes a DataFrame and trace list, returns a single `Optional[float]`. The EPI metric is a weighted pass/fail over scalar values against plausibility ranges.

**What Epidemiology Needs**:

| Benchmark Type | Example | Current Support |
|----------------|---------|-----------------|
| Scalar rate | Vaccination coverage at end of campaign | Yes |
| Time-series shape | S-curve of cumulative vaccination | No |
| Reproduction number (R0/Rt) | Effective R at different time points | No |
| Age-stratified rates | Attack rate by age group | Partially (via agent_type filtering) |
| Spatial spread pattern | Moran's I, wavefront speed | No |
| Contact tracing metrics | Secondary attack rate, serial interval | No |

The registry pattern (`@_registry.register("name")`) is clean and extensible. I could register new benchmark functions. But the `dispatch()` signature is rigid: `(df, traces, ins_col, elev_col)`. The `ins_col`/`elev_col` parameters are flood-specific. For epidemiological benchmarks, I would need `(df, traces, **domain_kwargs)`.

**Time-Series Benchmarks Are Critical**: The README explicitly acknowledges "No temporal trajectory validation" as a limitation. For pandemic models, the *trajectory* is the primary observable. A single-number compression of a vaccination S-curve loses most of the information. I would need:
- Dynamic Time Warping (DTW) distance between simulated and observed curves
- Curve-fitting parameters (logistic growth rate, inflection point, plateau)
- Phase-specific metrics (e.g., coverage at 30/60/90 days post-rollout)

**Verdict**: The registry pattern is sound but the interface is too narrow. Time-series and spatial benchmarks are non-negotiable for epidemiological applications.

---

### 3. Network Effects (Score: 1.5 / 5)

**Critical Gap**: Disease transmission is fundamentally a network phenomenon. The C&V framework has **zero** network validation infrastructure. No metrics for:
- Degree distribution effects on behavioral adoption
- Clustering coefficient influence on information cascading
- Network assortativity by vaccination status
- Contagion dynamics (behavioral contagion vs. disease contagion)

**Why This Matters for Health Behavior**: In my vaccination ABMs, network position is a stronger predictor of vaccination timing than individual beliefs (Bakshy et al. 2012; Centola 2010). An agent surrounded by vaccinated neighbors has different cues-to-action than one in an unvaccinated cluster, even with identical HBM construct levels. CACR computed without accounting for network context would be misleading.

**What I Would Need**:
- L1 extension: Network-conditioned CACR (coherence stratified by neighborhood vaccination rate)
- L2 extension: Degree-stratified adoption curves, clustering-adoption correlation
- New hallucination class: Behavioral contagion without network proximity (agent adopts behavior they could not have observed)

**The README Lists This**: The Known Limitations section mentions "No spatial validation" and suggests Moran's I. This is a good start, but for epidemiology, spatial and network are distinct --- a household in a dense urban network and one in a sparse rural network at the same geographic distance have very different social dynamics.

**Verdict**: This is the single largest gap for health behavior applications. Network validation is not optional in epidemiological ABM.

---

### 4. Rich vs. No Data (Score: 3.0 / 5)

**Rich Data Scenario** (county-level vaccination rates): The `EMPIRICAL_BENCHMARKS` dictionary with `(low, high)` ranges is exactly right. I have CDC county-level data; I can set tight ranges. The weight system allows me to emphasize benchmarks I trust more (e.g., weight=2.0 for the CDC's National Immunization Survey data, weight=0.5 for self-reported behaviors).

**No Data Scenario** (novel pathogen): This is where the framework's design philosophy --- "structural plausibility, not predictive accuracy" --- actually shines. For a novel pathogen, I cannot set L2 benchmark ranges because no empirical data exists. But L1 metrics (CACR, R_H, EBE) and L3 cognitive validation (ICC, eta-squared) are still computable. This three-level architecture naturally degrades:

| Data Availability | Usable Levels | Interpretation |
|-------------------|---------------|----------------|
| Rich empirical data | L1 + L2 + L3 | Full validation |
| Sparse/uncertain data | L1 + L2 (wide ranges) + L3 | Plausibility check |
| No empirical data | L1 + L3 only | Theory-consistency only |

**What Is Missing**: Explicit guidance on how to set benchmark ranges under uncertainty. For a novel pathogen, I might use analogical reasoning (e.g., SARS-CoV-2 vaccination patterns as a prior for the next pandemic). The framework should support:
- Bayesian updating of benchmark ranges as early data arrives
- Hierarchical benchmarks: "at least match the *shape* of uptake curves from prior pandemics"
- Explicit calibration/validation split labeling (the README mentions this but no tooling exists)

**Verdict**: The architectural degradation from L1+L2+L3 to L1+L3-only is elegant and well-suited to epidemiological uncertainty. Needs better guidance for the no-data case.

---

### 5. Stochastic Validation (Score: 1.5 / 5)

**The Problem**: Epidemiological ABMs require Monte Carlo validation. A single seed tells you nothing about model behavior --- stochastic extinction can make one run look radically different from another. Standard practice is 50+ seeds with confidence intervals (Ten Broeke et al. 2016).

**Current State**: The framework processes one seed at a time. The `compute_validation()` function takes a single `traces_dir` (one seed directory). The `ValidationReport` dataclass has a `seed` field but it is just metadata --- no aggregation logic exists.

**What I Need**:

```python
# Desired API
ensemble_report = compute_ensemble_validation(
    traces_dirs=["seed_1/", "seed_2/", ..., "seed_50/"],
    profiles=profiles_df,
    confidence_level=0.95,
)
# Returns: mean EPI, CI, per-benchmark mean+CI, cross-seed CACR variance
```

**Specific Requirements**:
- **EPI distribution**: Mean EPI across seeds, with 95% CI. A model passes if the lower CI bound exceeds 0.60.
- **CACR stability**: If CACR varies wildly across seeds (e.g., 0.65-0.90), this suggests the LLM's behavioral fidelity is seed-dependent --- a finding in itself.
- **Benchmark convergence**: How many seeds are needed for each benchmark to stabilize within +/- 0.02? This is an important power analysis question.
- **EBE across seeds**: Does behavioral diversity change with different initial conditions?

**Verdict**: Single-seed validation is a non-starter for epidemiological publication. The framework needs an ensemble aggregation layer.

---

### 6. Construct Dimensionality (Score: 2.5 / 5)

**CACR with 6 Dimensions**: CACR asks "does the agent's action match what the theory predicts given its construct levels?" With 2 dimensions (PMT: TP x CP), the lookup table is tractable (25 cells). With 6 dimensions (HBM), two problems emerge:

1. **Sparse coverage**: Even with 50,000 traces (1,000 agents x 50 years), many of the 15,625 cells will have zero observations. CACR becomes unstable in the tails.

2. **Construct correlation**: In HBM, perceived susceptibility and perceived severity are strongly correlated (both are "threat" constructs). Treating them as independent dimensions inflates the apparent dimensionality. CACR does not account for construct inter-correlation.

**Risk of Meaninglessness**: With 6 dimensions at 5 levels, a random agent would have CACR near 1/k (where k is the number of possible actions) for any given cell. If most cells map to 2-3 actions out of 6-8 total, random coherence is ~30-40%. The CACR threshold of 0.75 still has discriminative power, but the gap between random and coherent narrows as dimensionality increases.

**Proposed Mitigation**:
- Collapse correlated dimensions before CACR computation (susceptibility + severity -> threat; benefits - barriers -> net_evaluation)
- Report CACR by construct quadrant (the `quadrant_cacr` in `CACRDecomposition` does this for 2D --- extend to hierarchical quadrants)
- Use the `is_sensible_action()` fallback for sparse cells rather than requiring exact lookup matches

**Verdict**: CACR's interpretation weakens with high dimensionality but does not become meaningless if the implementer collapses correlated dimensions. The framework allows this but does not guide it.

---

### 7. Publication Readiness (Score: 3.0 / 5)

**Target**: Lancet Digital Health or PNAS

**Strengths for Publication**:
- The three-level validation hierarchy is novel and defensible. No existing LLM-ABM paper (of the 35 I have reviewed) implements anything this systematic.
- CACR decomposition (raw vs. governance-filtered) directly addresses the "constrained RNG" critique --- this is the strongest methodological contribution.
- The UNKNOWN sentinel for extraction failures is honest and methodologically rigorous.
- Supplementary metrics around governance rejection rates as environmental justice indicators are novel and publishable.

**Gaps for Publication**:

| Gap | Severity | Fix Effort |
|-----|----------|------------|
| No ensemble aggregation | Blocking | 2-3 weeks |
| No time-series benchmarks | Blocking for epi | 3-4 weeks |
| No network validation | Blocking for epi | 4-6 weeks |
| No formal sensitivity analysis API | Major | 2 weeks |
| No calibration/validation split tooling | Major | 1 week |
| Single-theory code coupling (l1_micro.py imports PMT directly) | Minor | 1 week (refactor) |
| No Wasserstein distance or distributional comparison | Minor | 1-2 weeks |

**Code Quality**: The code is well-structured with clear separation (theories/, benchmarks/, metrics/, hallucinations/). The `BehavioralTheory` protocol is correctly `@runtime_checkable`. The YAML config pattern (`pmt_flood.yaml`) is good practice. The `example_cv_usage.py` is thorough and would serve well as a supplementary methods appendix.

**Remaining Coupling**: `l1_micro.py` still imports `PMT_OWNER_RULES` directly (line 17-20) rather than using the `BehavioralTheory` protocol. The `compute_l1_metrics()` function takes an `agent_type` string and switches on it to select rules. This should be refactored to accept a `BehavioralTheory` instance, making the L1 computation theory-agnostic. Without this, every new theory needs to modify core validation code --- unacceptable for a general framework.

**Verdict**: Could be published in current state for a water resources journal (WRR). For Lancet Digital Health or PNAS, the ensemble and time-series gaps are blocking. The CACR decomposition methodology is the strongest publishable contribution.

---

## Specific Recommendations for Health Behavior ABM Adaptation

### Priority 1 (Must-Have)

1. **Refactor `compute_l1_metrics()` to accept `BehavioralTheory` instance** instead of importing PMT rules directly. The protocol exists; use it.

2. **Add ensemble aggregation layer**: `compute_ensemble_validation(traces_dirs: List[Path], ...)` returning mean/CI for all metrics across seeds.

3. **Generalize benchmark dispatch signature**: Replace `(df, traces, ins_col, elev_col)` with `(df, traces, **domain_context)` so domain-specific parameters are not hard-coded.

### Priority 2 (Important)

4. **Document hierarchical construct collapse pattern**: Show HBM users how to reduce 6D to 2-3 effective dimensions before CACR computation.

5. **Add time-series benchmark type**: Support benchmarks that compare simulated curves against reference shapes (DTW, logistic fit parameters).

6. **Add network-conditioned CACR**: Stratify coherence by network neighborhood state (e.g., fraction of neighbors vaccinated).

### Priority 3 (Nice-to-Have)

7. **Bayesian benchmark ranges**: Allow prior distributions on benchmark ranges that update as early simulation data arrives.

8. **Wasserstein distance for distributional comparisons**: Compare entire action distributions rather than just marginal rates.

9. **Formal sensitivity analysis API**: Systematically vary one construct while holding others fixed, measure CACR/EBE response.

---

## Comparison to Existing Health Behavior ABM Validation

| Validation Approach | Typical Health ABM | This Framework |
|--------------------|--------------------|----------------|
| Face validity | Expert review | L3 (ICC, eta-squared) --- more rigorous |
| Micro-level | None or ad hoc | L1 (CACR, R_H, EBE) --- systematic |
| Macro-level | Visual pattern matching | L2 (EPI, benchmarks) --- quantitative |
| Ensemble | 50+ seeds with CI | Single seed --- gap |
| Network | Degree-distribution matching | None --- gap |
| Time-series | Epidemic curve fitting | None --- gap |
| Theory grounding | Verbal description | CACR against lookup table --- superior |

The framework is ahead of the state-of-the-art in theory-grounded micro validation (CACR, hallucination detection) and cognitive validation (L3 ICC probing). It is behind in ensemble and network validation, which are standard in computational epidemiology.

---

## Final Assessment

The C&V framework represents the most systematic LLM-ABM validation protocol I have seen. The BehavioralTheory protocol, while currently under-utilized in the codebase, provides the right abstraction for multi-theory support. For my pandemic preparedness ABM, I would adopt this framework and invest 3-4 months extending it with ensemble aggregation, time-series benchmarks, and network-conditioned metrics. The CACR decomposition methodology alone would strengthen any LLM-ABM paper's methods section.

The key insight --- validating behavioral fidelity (structural plausibility) rather than predictive accuracy --- is epistemologically sound for both flood and health behavior domains, where we lack ground-truth future trajectories but have strong behavioral theory.

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| HBM Fit | 2.5 | 1.0 | 2.5 |
| Epidemiological Benchmarks | 2.0 | 1.2 | 2.4 |
| Network Effects | 1.5 | 1.5 | 2.25 |
| Rich vs No Data | 3.0 | 0.8 | 2.4 |
| Stochastic Validation | 1.5 | 1.3 | 1.95 |
| Construct Dimensionality | 2.5 | 1.0 | 2.5 |
| Publication Readiness | 3.0 | 1.2 | 3.6 |
| **Weighted Average** | | | **2.51** |

**Bottom Line**: Adopt and extend, do not build from scratch. The architectural decisions are sound; the domain-specific gaps are tractable.

---

*Dr. Priya Sharma, Department of Epidemiology*
*Reviewed: 2026-02-14*
