# Expert Assessment: Validation Framework for LLM-Governed Multi-Agent Flood Adaptation ABM

**Reviewer**: Independent expert review of validation code and design
**Date**: 2026-02-10
**Scope**: L1 Micro, L2 Macro, and L3 Cognitive validation tiers
**Target journal**: Water Resources Research (WRR)

---

## 1. Executive Summary

This validation framework implements a three-tier approach (L1 Micro, L2 Macro, L3 Cognitive) for assessing the structural plausibility of an LLM-governed agent-based model of household flood adaptation in the Passaic River Basin. The framework is methodologically ambitious and internally consistent, with well-grounded PMT coherence rules, weighted empirical benchmarks drawn from peer-reviewed literature, and an independent psychometric probing protocol (ICC/eta-squared) that separates model reliability testing from experiment execution. However, several implementation gaps -- most notably the absence of site-specific historical calibration, a tolerance mechanism that implicitly widens benchmark ranges by 30%, and dual code paths for the same metrics that risk divergent results -- require attention before submission to WRR.

---

## 2. Strengths of the Validation Approach

### 2.1 Theory-Grounded Micro Validation (L1)

The Construct-Action Coherence Rate (CACR) implementation in `compute_validation_metrics.py` (lines 68-136) encodes a comprehensive 5x5 PMT rule table for both owners and renters. Several design choices are commendable:

- **Separate rule tables by agent type**: `PMT_OWNER_RULES` and `PMT_RENTER_RULES` correctly reflect the asymmetric action space (renters cannot elevate or accept buyouts; they can only relocate). This is a genuine structural constraint that many ABMs ignore.
- **Permissive treatment of fatalism**: The mapping `(VH, VL) -> ["do_nothing"]` and `(VH, L) -> ["buy_insurance", "do_nothing"]` explicitly encodes the risk perception paradox (Grothmann & Reusswig, 2006), permitting inaction under high threat when coping capacity is very low. This is empirically well-supported and avoids the common error of forcing protective action on all high-threat agents.
- **Habitual insurance at low threat**: The inclusion of `buy_insurance` for `(L, H)`, `(L, L)`, and `(VL, H)` combinations, justified via the PADM framework (Lindell & Perry, 2012), reflects real-world behavior where insurance is maintained as a low-cost habitual action even when threat perception is low. The in-line citations (lines 92-98) are a good practice for auditability.
- **Fallback coherence check**: The `_is_sensible_action()` function (lines 377-394) provides a soft second check for TP/CP combinations not in the rule table, preventing unknown combinations from being automatically scored as incoherent.

### 2.2 Physically-Grounded Hallucination Detection

The `_is_hallucination()` function (lines 397-422) implements three physically meaningful checks:

1. Repeated elevation on already-elevated structures (irreversible action)
2. Active decisions by already-bought-out agents (exit state)
3. Renters attempting structural elevation (type constraint)

These map directly to state-space constraints of the physical system. The parallel implementation in `unified_rh.py` (lines 34-87) generalizes this via parameterized `irreversible_states` mappings, demonstrating that the framework layer is domain-agnostic while the application layer (`compute_validation_metrics.py`) provides domain-specific checks.

### 2.3 Decision-Based State Inference

The `_extract_final_states_from_decisions()` function (lines 547-617) represents a well-engineered workaround for a simulation engine limitation: `state_after` is never updated because no `FloodSimulationEngine.execute_skill()` exists. The function correctly distinguishes:

- **Annual renewable actions**: Insurance status is determined by the *last year's* action only (line 608), reflecting real NFIP annual renewal semantics.
- **Irreversible actions**: Elevation, buyout, and relocation use "EVER" logic (lines 610-612), appropriate for permanent structural modifications.
- **REJECTED trace filtering**: Lines 574-576 correctly exclude governance-blocked actions from state inference, preventing false positive state attribution.

The test suite (`test_decision_based_inference.py`, 446 lines, 25+ test cases) provides thorough coverage including edge cases (malformed traces, out-of-order years, empty agent IDs, action normalization variants), and regression tests that explicitly document the bug this function was designed to fix (lines 371-413).

### 2.4 Weighted Empirical Plausibility Index (EPI)

The EPI computation (lines 494-522 of `compute_validation_metrics.py`) uses a principled weighting scheme:

| Weight | Rationale | Benchmarks |
|--------|-----------|------------|
| 2.0 | Core equity metric for RQ2 | mg_adaptation_gap |
| 1.5 | Tests risk perception paradox (key theoretical claim) | do_nothing_rate_postflood |
| 1.0 | Core behavioral metrics with good data quality | insurance_rate_sfha, elevation_rate, renter_uninsured_rate, insurance_lapse_rate |
| 0.8 | Partially redundant or event-dependent | insurance_rate_all, buyout_rate |

The weighting reflects research priorities rather than data availability, which is appropriate for a theory-testing ABM. The highest-weighted benchmark (mg_adaptation_gap at 2.0) directly serves RQ2 (institutional feedback and protection inequality), ensuring that the model cannot pass validation while producing implausible equity outcomes.

### 2.5 Independent Psychometric Validation (L3)

The ICC probing protocol (15 archetypes x 6 vignettes x 30 replicates = 2,700 calls) is architecturally separate from the primary experiment. This is a significant strength:

- It can be executed *before* the 52,000-call experiment, serving as a gate check.
- It tests LLM *reliability* (ICC >= 0.60) and *persona sensitivity* (eta-squared >= 0.25) without confounding from simulation dynamics.
- The 15 archetypes span the full demographic-situational space including adversarial cases (high_income_denier, recently_flooded).
- The 6 vignettes cover the severity spectrum from routine (low_severity) to catastrophic (extreme_compound) to cognitively challenging (contradictory_signals, post_adaptation).

The reported pilot results (ICC = 0.964, eta-squared = 0.33) are well above thresholds, suggesting the Gemma 3 4B model produces reliable, persona-differentiated responses.

### 2.6 Extensive Infrastructure

The validation stack comprises approximately 8,400+ lines of code across generic framework modules (`broker/validators/calibration/`, ~6,469 lines) and domain-specific modules (`paper3/analysis/`, ~2,000+ lines). The separation of concerns -- generic `BenchmarkRegistry`, `PsychometricBattery`, and `MicroValidator` classes in the broker layer versus flood-specific `empirical_benchmarks.py`, `compute_validation_metrics.py`, and archetype configs in the paper3 layer -- is well-designed and promotes reusability.

---

## 3. Identified Gaps

### 3.1 Dual Code Paths for the Same Metrics [Severity: HIGH]

There are two independent implementations of the same validation metrics:

| Metric | Implementation 1 (`compute_validation_metrics.py`) | Implementation 2 (broker framework) |
|--------|-----------------------------------------------------|--------------------------------------|
| CACR | `compute_l1_metrics()` with inline PMT rule tables | `MicroValidator.compute_cacr()` via `PMTFramework` |
| R_H | `_is_hallucination()` (3 physical checks) | `unified_rh.py` (parameterized irreversible states + thinking rule violations V1/V2/V3) |
| EBE | `_compute_entropy()` (Shannon entropy) | `unified_rh.py` yearly EBE = H_norm * (1 - R_H_year) |
| EPI | `compute_l2_metrics()` with inline `EMPIRICAL_BENCHMARKS` | `BenchmarkRegistry.compare()` via `empirical_benchmarks.py` |
| Lapse | Decision-sequence tracking (lines 716-749) | Year-over-year `insured_prev -> not insured_next` (lines 216-232 of `empirical_benchmarks.py`) |

**Risk**: The two CACR implementations may diverge. `compute_validation_metrics.py` uses a 5x5 lookup table with 25 owner entries and 25 renter entries (lines 68-136), while `MicroValidator` delegates to `PMTFramework.validate_action_coherence()`. If the rule sets differ even slightly, the same trace data will produce different CACR scores depending on which code path is invoked. Similarly, the R_H implementations differ: the standalone version checks 3 physical conditions only, while `unified_rh.py` adds V1/V2/V3 thinking rule violations, which would systematically produce higher R_H values.

**Also notable**: The CACR threshold is 0.75 in `compute_validation_metrics.py` (line 211) but 0.80 in `PAPER3_COMPLETE_REFERENCE.md` (Section 4.1) and `calibration.yaml`. This inconsistency must be resolved before any reported results are meaningful.

### 3.2 Benchmark Range Discrepancies Between the Two Implementations [Severity: HIGH]

The `EMPIRICAL_BENCHMARKS` dictionary in `compute_validation_metrics.py` (lines 143-184) defines 8 benchmarks, but the set does not exactly match the 8 benchmarks in `empirical_benchmarks.py` (FLOOD_BENCHMARKS, lines 43-124):

| Benchmark key in `compute_validation_metrics.py` | Benchmark key in `empirical_benchmarks.py` | Match? |
|---|---|---|
| `insurance_rate_sfha` | `insurance_rate` | Different key names |
| `insurance_rate_all` | `insurance_rate_all` | Match |
| `elevation_rate` | `elevation_rate` | Match |
| `buyout_rate` | `buyout_rate` | Match |
| `do_nothing_rate_postflood` | `do_nothing_rate_postflood` | Match |
| `mg_adaptation_gap` | `mg_adaptation_gap` | Match |
| `renter_uninsured_rate` | `rl_uninsured_rate` | Different key AND different semantics |
| `insurance_lapse_rate` | `insurance_lapse_rate` | Match, but different ranges |

The `insurance_lapse_rate` range is (0.20-0.40) according to the user's specification, (0.05-0.15) in `compute_validation_metrics.py` line 179, and (0.05-0.15) in `empirical_benchmarks.py` line 118. The user-specified range (0.20-0.40) appears nowhere in the code. Similarly, `renter_uninsured_rate` in the standalone script computes "renters in HIGH zone without insurance" while `rl_uninsured_rate` in the benchmark module computes "agents flooded >= 2 times without insurance" -- these are conceptually distinct populations.

### 3.3 Tolerance-Based Range Expansion Undocumented [Severity: MEDIUM]

The `BenchmarkRegistry.compare()` method applies a 30% tolerance expansion to all benchmark ranges (i.e., an observed value is "in range" if it falls within `[low * 0.70, high * 1.30]`). For example, the insurance_rate_sfha range of (0.30-0.50) effectively becomes (0.21-0.65) after tolerance. This is noted in `PAPER3_COMPLETE_REFERENCE.md` Section 5 ("Benchmark Limitations") but the standalone `compute_validation_metrics.py` does *not* apply any tolerance -- it uses strict range checking (line 504: `low <= value <= high`). This means the two code paths will produce different EPI scores for the same data.

### 3.4 Insurance Lapse Rate Definition Mismatch [Severity: MEDIUM]

The lapse rate computation in `compute_validation_metrics.py` (lines 716-749) measures "attention shift" -- an agent who was previously insured but chose a *different action* in the next year is counted as a lapse, even though the model has no explicit insurance policy cancellation mechanism (acknowledged in the code comment at lines 744-748). This conflates behavioral decision diversity with actual policy lapse. An agent who elevates their home (a protective action) after previously buying insurance would be counted as a "lapse," inflating the metric. The comment correctly identifies this as a model limitation, but the metric should be labeled differently (e.g., "insurance non-renewal rate" or "action switching rate from insurance") to avoid confusion with the NFIP administrative lapse rate from Gallagher (2014) against which it is benchmarked.

### 3.5 EBE Computation Inconsistency [Severity: LOW]

The standalone `_compute_entropy()` (lines 425-437) computes raw Shannon entropy over the entire action distribution. The `unified_rh.py` implementation (lines 192-222) computes yearly normalized entropy (H/H_max, where H_max = log2(4)) and then scales by `(1 - R_H_year)` to penalize hallucination-inflated diversity. These are different quantities. The combined L1 EBE in `compute_validation_metrics.py` (line 825) averages the owner and renter entropies, which is also statistically questionable since entropy is not generally additive over heterogeneous sub-populations.

### 3.6 No Spatial Validation [Severity: MEDIUM]

Despite agents being assigned to real PRB census tracts with latitude/longitude coordinates and ESRI raster-based flood zones, no spatial validation metric is included. Standard ABM validation for flood models typically includes spatial pattern comparison (e.g., Moran's I for adaptation clustering, spatial concordance of insurance uptake with flood hazard zones). The social network analysis metrics mentioned in RQ3 (Moran's I, contagion half-life) serve as analysis outputs but are not incorporated into the validation pass/fail criteria.

### 3.7 No Temporal Trajectory Validation [Severity: MEDIUM]

The L2 benchmarks are all cross-sectional (end-state or period-aggregate rates). No benchmark validates the *temporal dynamics* of adaptation -- for example, the well-documented "flood-spike-decay" pattern in insurance uptake (Gallagher, 2014), where NFIP policies surge after a flood event and then decay over 3-5 years. The `TemporalCoherenceValidator` exists in the framework (`temporal_coherence.py`, 426 lines) but is not invoked by `compute_validation_metrics.py`. This is a missed opportunity, as temporal patterns are among the most diagnostic validation targets for longitudinal ABMs.

### 3.8 Missing Confidence Intervals on L2 Metrics [Severity: LOW]

EPI and individual benchmark values are reported as point estimates from a single seed. The 10-seed design provides the data for bootstrap confidence intervals, but `compute_validation_metrics.py` does not compute cross-seed uncertainty. The `run_cv.py --mode aggregate` pathway is mentioned in the execution plan but the aggregation logic for cross-seed EPI confidence intervals is not implemented in the standalone validation script.

---

## 4. No-Historical-Data Justification: Is This Defensible for WRR?

### 4.1 The Core Issue

This ABM uses the Passaic River Basin as its study area with real flood rasters (2011-2023), real census tract geometry, and survey-initialized agent demographics -- but has **no site-specific historical calibration data** for any of the 8 L2 benchmarks. All benchmark ranges are drawn from national NFIP statistics (Kousky, 2017; Gallagher, 2014), cross-national survey data (Grothmann & Reusswig, 2006 -- German), and prior ABM calibration targets from other study areas (Haer et al., 2017 -- Netherlands; de Ruig et al., 2022 -- Louisiana).

### 4.2 Precedents in the WRR Literature

This is defensible, but requires careful framing. Several precedents exist:

1. **Pattern-Oriented Modeling (POM)**: Grimm et al. (2005) and Grimm & Railsback (2012) argue that multi-pattern validation against qualitative patterns from different sources is superior to single-metric calibration against site-specific time series. The EPI approach with 8 benchmarks from 4 categories (aggregate, conditional, temporal, demographic) is consistent with POM philosophy.

2. **Structural plausibility claims**: The paper explicitly disclaims predictive accuracy (PAPER3_COMPLETE_REFERENCE.md Section 4: "We do not claim predictive accuracy. We demonstrate structural plausibility"). WRR has published ABMs with similar framing, particularly in the socio-hydrology literature (e.g., Di Baldassarre et al., 2013; Haer et al., 2017).

3. **National-to-local transferability**: NFIP statistics are federal program data with reasonable geographic transferability for insurance uptake rates. New Jersey post-Sandy dynamics may differ from national averages, but the 30% tolerance (when applied) partially accounts for this.

### 4.3 Vulnerabilities

Two aspects are harder to defend:

- **Elevation rate benchmark** (0.03-0.12): Sourced from Netherlands and Louisiana ABMs, not from US census or permit data. A WRR reviewer may question whether Dutch or Gulf Coast elevation rates are transferable to the mid-Atlantic. Recommendation: cite FEMA Hazard Mitigation Grant Program (HMGP) data for NJ if available, or explicitly acknowledge this as a calibrated-ABM-derived benchmark.

- **MG-NMG adaptation gap** (0.10-0.30): Sourced partly from the authors' own survey (Choi et al., 2024). Self-citation as the benchmark source is inherently circular if the survey also initializes the agent personas. The paper should clarify that the benchmark range is derived from *different variables* (observed aggregate behavior) than the persona initialization (individual-level PMT construct scores).

### 4.4 Assessment

**Defensible with proper framing.** The key is to frame the benchmarks as "empirical plausibility envelopes" rather than "calibration targets." The paper should include a table explicitly stating the geographic scope, temporal scope, and data quality grade for each benchmark (partially done in PAPER3_COMPLETE_REFERENCE.md Section 5). The limitation that "most benchmarks derive from national-level or non-PRB studies" should appear in the Methods section, not buried in an appendix.

---

## 5. Comparison to Standard ABM Validation Practices

### 5.1 ODD+D Protocol Compliance

The ODD+D (Overview, Design concepts, Details + Decision-making) protocol (Muller et al., 2013) is the de facto standard for documenting human-decision ABMs in environmental science. Comparing against its validation requirements:

| ODD+D Element | Status | Notes |
|---------------|--------|-------|
| Individual decision model documentation | Strong | PMT rule tables, construct definitions, governance rules all documented |
| Sensitivity analysis | Planned | 7 directional tests + 5 prompt sensitivity tests defined |
| Calibration | Partial | Three-stage protocol defined but no site-specific calibration |
| Validation against empirical patterns | Strong | 8 benchmarks with POM philosophy |
| Uncertainty analysis | Planned | 10 seeds, but no uncertainty propagation through benchmarks |
| Comparison to simpler models | Planned | Baseline traditional (no LLM) configuration defined |

### 5.2 Pattern-Oriented Modeling (POM) Compliance

Grimm et al. (2005) advocate validating against multiple patterns at different scales and from different data sources:

| POM Criterion | Status | Assessment |
|---------------|--------|------------|
| Multiple patterns | Yes | 8 benchmarks + 3 L1 metrics + 3 L3 metrics = 14 validation targets |
| Different hierarchical levels | Yes | L1 (per-decision), L2 (aggregate), L3 (model-level reliability) |
| Different data sources | Partial | NFIP administrative data, survey data, prior ABM calibrations -- but no PRB-specific observational data |
| Patterns that are independent | Partial | insurance_rate_sfha and insurance_rate_all are correlated by construction; mg_adaptation_gap depends on insurance_rate. Weight adjustments (0.8 for redundant benchmarks) partially address this |
| Temporal patterns | Weak | No temporal trajectory validation despite 13-year simulation |

### 5.3 LLM-ABM-Specific Validation (Novel Contribution)

The L1 CACR and L3 ICC/eta-squared tiers are novel contributions that address validation challenges specific to LLM-based ABMs:

- **CACR**: No traditional ABM needs this because equation-based decision models are deterministic given inputs. LLM agents can produce construct labels that contradict their chosen action, making CACR a necessary new metric.
- **R_H**: Hallucination detection is unique to LLM agents. Traditional ABMs cannot produce physically impossible actions because the action space is explicitly enumerated in code.
- **ICC probing**: Addresses the "prior leakage" concern -- that the LLM's pre-training data (not the persona) drives behavior. The eta-squared >= 0.25 threshold ensures that at least 25% of behavioral variance is attributable to persona content, not LLM defaults.

This three-tier structure represents a meaningful methodological contribution that could influence how future LLM-ABMs are validated. However, the paper should explicitly position it against the Huang et al. (2025) psychometric framework for LLMs (Nature Machine Intelligence), which the code already cites (line 17 of `psychometric_battery.py`), to demonstrate awareness of the broader LLM evaluation literature.

---

## 6. Prioritized Recommendations for WRR Submission

### Priority 1: Resolve Dual Code Path Divergences [BEFORE SUBMISSION]

Unify or explicitly cross-validate the two implementation paths. Specifically:

1. **CACR threshold**: Resolve the 0.75 vs. 0.80 discrepancy between `compute_validation_metrics.py` (line 211) and the reference document / `calibration.yaml`. Choose one threshold and use it consistently.
2. **Benchmark key alignment**: Ensure `insurance_rate_sfha` vs. `insurance_rate` and `renter_uninsured_rate` vs. `rl_uninsured_rate` are either reconciled or one path is designated as canonical.
3. **Tolerance application**: Either apply the 30% tolerance consistently in both paths or remove it entirely and widen the raw benchmark ranges. Document which approach is used.
4. **Cross-check test**: Add an integration test that runs both code paths on the same synthetic trace data and asserts they produce identical (or documented-different) results.

### Priority 2: Add Temporal Pattern Validation [BEFORE SUBMISSION]

Implement at least one temporal benchmark, such as:

- **Post-flood insurance spike**: Insurance uptake should increase in the 1-2 years following a flood event and then decay. This is one of the most robust empirical findings in the flood insurance literature (Gallagher, 2014; Atreya et al., 2013).
- **Adaptation persistence**: Agents who elevate should not subsequently un-elevate (already checked by R_H, but could also be expressed as a temporal consistency benchmark).

The `TemporalCoherenceValidator` in `broker/validators/calibration/temporal_coherence.py` (426 lines) appears to already support this; it simply needs to be wired into the L2 validation pipeline.

### Priority 3: Document Benchmark Transferability [BEFORE SUBMISSION]

Create a formal benchmark provenance table for the paper's Methods section:

| Benchmark | Empirical Source | Geography | Period | Transferability Risk |
|-----------|-----------------|-----------|--------|---------------------|
| insurance_rate_sfha | FEMA NFIP statistics | National (US) | 2001-2020 | Low (federal program, uniform structure) |
| elevation_rate | Haer et al. (2017); de Ruig et al. (2022) | Netherlands; Louisiana | Model-calibrated | High (no US census benchmark exists) |
| buyout_rate | NJ DEP Blue Acres | NJ-specific | Post-Sandy | Low (site-specific data exists) |
| do_nothing_postflood | Grothmann & Reusswig (2006) | Germany (Cologne) | 2002 survey | Medium (cross-national, but PMT is universal) |
| insurance_lapse_rate | Gallagher (2014, AER) | National (US) | 1978-2007 | Medium (pre-Risk Rating 2.0) |

### Priority 4: Compute Cross-Seed Uncertainty [BEFORE SUBMISSION]

After running the 10-seed primary experiment, compute:

- Mean and standard deviation of each L2 benchmark across seeds.
- 95% confidence interval for EPI using bootstrap or normal approximation.
- Report whether EPI >= 0.60 holds for the *lower bound* of the CI, not just the point estimate.

### Priority 5: Rename Insurance Lapse Metric [BEFORE SUBMISSION]

The current "insurance_lapse_rate" metric measures action switching away from insurance, not actual NFIP policy cancellation. Either:

(a) Rename to `insurance_nonrenewal_decision_rate` or `insurance_attention_shift_rate` to avoid confusion with the administrative lapse rate from Gallagher (2014), or
(b) Implement a proper insurance state tracker in the simulation engine that models explicit policy duration and cancellation.

Option (a) is lower effort and still valuable. Document the distinction explicitly in the paper.

### Priority 6: Consider Adding Spatial Validation [NICE TO HAVE]

If time permits, compute Moran's I for insurance uptake on the social network graph at end-of-simulation. This tests whether socially connected agents (same neighborhood, gossip network) show correlated adaptation behavior -- a signature prediction of RQ3. The spatial data infrastructure already exists (`assign_flood_zones()` with lat/lon coordinates).

---

## 7. Conclusion

### Overall Assessment

The validation framework is **methodologically strong and well-engineered**, representing one of the more comprehensive validation efforts for an LLM-based ABM in the environmental modeling literature. The three-tier structure (L1 Micro, L2 Macro, L3 Cognitive) addresses the unique validation challenges posed by LLM agents -- construct-action coherence, physical hallucination, stochastic reliability, and persona sensitivity -- in a principled way that builds on established ABM validation paradigms (POM, ODD+D) while extending them for the LLM context.

The primary concerns are **implementation consistency** (dual code paths with divergent definitions) and **benchmark provenance** (national/international benchmarks applied to a site-specific study area). Neither is a fatal flaw. The dual code path issue is a software engineering problem that can be resolved with test coverage and documentation. The benchmark transferability issue is inherent to any ABM that targets a specific study area without site-specific historical data, and it is well-handled by the "structural plausibility" framing as long as the paper is transparent about limitations.

**The no-historical-data approach is defensible for WRR** provided the paper: (1) frames benchmarks as plausibility envelopes, not calibration targets; (2) includes a provenance table documenting the geographic and temporal scope of each benchmark; (3) reports cross-seed uncertainty on all L2 metrics; and (4) uses the `TemporalCoherenceValidator` to demonstrate at least one temporal pattern match.

The L3 cognitive validation (ICC probing) is the strongest element of the framework and a genuine methodological contribution. The pilot results (ICC = 0.964, eta-squared = 0.33) substantially exceed thresholds, suggesting that the Gemma 3 4B model produces reliable, persona-driven behavior. This addresses the most common reviewer concern about LLM-ABMs: "Is the LLM just producing generic responses regardless of the persona?"

**Verdict**: With the Priority 1-5 recommendations addressed, this validation framework is suitable for WRR submission. The L1+L2+L3 structure provides a template that the LLM-ABM community can adopt and extend.

---

## Appendix: Key File References

| File | Absolute Path | Role |
|------|---------------|------|
| Standalone validation | `c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3\analysis\compute_validation_metrics.py` | L1+L2 computation from JSONL traces |
| Framework micro validator | `c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\validators\calibration\micro_validator.py` | Generic CACR/EGS computation |
| Framework R_H computation | `c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\validators\posthoc\unified_rh.py` | Domain-agnostic R_H + EBE |
| Framework benchmark registry | `c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\validators\calibration\benchmark_registry.py` | Generic EPI engine |
| Domain benchmark definitions | `c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3\analysis\empirical_benchmarks.py` | Flood-specific 8 benchmarks |
| Psychometric battery | `c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\validators\calibration\psychometric_battery.py` | ICC/eta-squared probing |
| Unit tests | `c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3\tests\test_decision_based_inference.py` | Decision-based inference tests |
| Project reference | `c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3\PAPER3_COMPLETE_REFERENCE.md` | Full design specification |
