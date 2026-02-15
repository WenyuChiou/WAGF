# Wave 2 Expert Review: Hydrology & ABM Perspective

**Reviewer**: Dr. Maria Gonzalez (Hydrology & ABM Expert)
**Affiliation**: Coupled Human-Water Systems Lab; publications in WRR, JAWRA, HESS
**Date**: 2026-02-14
**Module Reviewed**: `examples/multi_agent/flood/paper3/analysis/validation/`

---

## 1. Overall Assessment

**Score: 3.2 / 5.0**

A well-engineered micro-to-meso validation pipeline with a genuinely novel construct-grounding mechanism (CGR), but it lacks the temporal, spatial, and multi-scale validation infrastructure that the ABM community now expects for publication in WRR or HESS. The framework validates *individual decisions* and *aggregate rates* competently but does not yet validate *dynamics* -- the time-evolving, spatially-structured, feedback-driven patterns that define coupled human-natural systems.

---

## 2. Dimension Scores

| Dimension | Score | Short Assessment |
|-----------|-------|------------------|
| D1: ODD+D Compliance | 2.0 | No ODD+D template; L1/L2 partially map to POM but no explicit link |
| D2: Coupled Human-Natural System | 2.5 | Benchmarks capture static outcomes; no feedback-loop validation |
| D3: Spatial Validation | 1.0 | No spatial metrics whatsoever |
| D4: Calibration-Validation Split | 2.0 | No explicit holdout or cross-validation protocol |
| D5: Sensitivity Analysis Integration | 3.0 | CACR decomposition is implicit SA; no Morris/Sobol interface |
| D6: Multi-Scale Validation | 3.5 | L1-to-L2 bridge is clean; L0/L3 absent from this module |
| D7: Publication Readiness (WRR/HESS) | 3.5 | Null model + bootstrap + EPI are solid; temporal + spatial gaps block acceptance |

---

## 3. Top 3 Strengths from ABM Validation Perspective

### S1: Construct Grounding Rate (CGR) Addresses the Circularity Problem

The CGR module (`cgr.py`) is, to my knowledge, the first systematic attempt to validate LLM-assigned psychological constructs against rule-derived ground truth from objective state variables. This directly addresses the CACR circularity concern raised by Windrum et al. (2007): if construct labels are self-reported by the LLM, CACR merely checks internal consistency, not external validity. By grounding TP from `{flood_zone, flood_count, years_since_flood}` and CP from `{mg, income, elevated}`, CGR provides an independent anchor.

The inclusion of both exact match and adjacent-level agreement with Cohen's kappa is methodologically appropriate. The confusion matrix output enables diagnostic analysis of systematic biases (e.g., LLM over-estimating threat perception).

### S2: BenchmarkRegistry + Weighted EPI is Publication-Ready

The decorator-based `BenchmarkRegistry` pattern in `registry.py` is clean, extensible, and avoids the 141-line if/elif chain it replaced. The 8 flood benchmarks span aggregate (B1-B4), conditional (B5, B7), demographic (B6), and temporal (B8) categories, which maps well to what Schluter et al. (2017) call "multi-criteria pattern matching."

The weighted EPI computation with domain-informed weights (e.g., `mg_adaptation_gap` at 2.0 weight, `do_nothing_rate_postflood` at 1.5) reflects genuine domain expertise. The null-model significance test (`null_model.py`) with Monte Carlo p-values is exactly what WRR reviewers would demand.

### S3: BehavioralTheory Protocol Enables Theory-Agnostic Validation

The `BehavioralTheory` Protocol class with runtime checkability is well-designed. The examples file demonstrates TPB (3-dimension) and Irrigation WSA (2-dimension) implementations, proving the interface works beyond PMT. This is important because ABM validation should not be locked to one behavioral theory -- different domains require different theoretical anchors (Schluter et al. 2017, Section 3.2).

The fact that `compute_l1_metrics()` accepts an optional `theory` parameter and defaults to PMT means the same pipeline works for any domain that implements the protocol.

---

## 4. Top 3 Gaps from ABM Validation Perspective

### G1: No Temporal Validation (Critical)

This is the most significant gap. The framework validates end-state aggregate rates (B1-B8) but not the *trajectory* of those rates over simulation time. For flood adaptation ABMs, the temporal dynamics are the primary scientific contribution:

- **Adaptation diffusion curves**: How does insurance uptake evolve over 13 years? Does it match S-curve diffusion (Rogers 2003)?
- **Post-flood response dynamics**: Is there a spike in adaptation after flood events, followed by decay (the "levee effect" / availability heuristic decay)?
- **Convergence diagnostics**: Does the system reach equilibrium? Is the equilibrium sensitive to initial conditions?

The `insurance_lapse_rate` benchmark (B8) is the only temporal metric, and it collapses temporal structure into a single scalar. A WRR reviewer studying flood adaptation would ask: "Show me how adaptation rates evolve year-by-year and compare against empirical post-disaster uptake curves."

**Recommendation**: Add `L2_temporal` metrics:
- Time-series of benchmark values per year (not just final aggregate)
- Trend test (Mann-Kendall or similar) for monotonic adaptation growth
- Post-event response function: action distribution in year T vs T+1 after flood
- Autocorrelation of agent-level action sequences (are decisions persistent or volatile?)

### G2: CGR Grounding Rules Are Not Pluggable

The `ground_tp_from_state()` and `ground_cp_from_state()` functions in `cgr.py` are hardcoded rule-based implementations for the flood domain. They use flood-specific state variables (`flood_zone`, `flood_count`, `mg`, `income`). There is no protocol or interface for swapping in alternative grounding functions for other domains.

For an irrigation ABM, TP would be grounded from `{drought_severity, reservoir_level, crop_stage}` and CP from `{well_depth, irrigation_efficiency, capital}`. The current CGR module would require copy-paste modification.

**Recommendation**: Define a `ConstructGrounder` protocol:
```python
class ConstructGrounder(Protocol):
    def ground_constructs(self, state_before: Dict) -> Dict[str, str]: ...
```
Then `compute_cgr()` accepts an optional `grounder` parameter, defaulting to a `FloodGrounder` implementation.

### G3: No Spatial Validation

The framework has zero spatial metrics. For a flood ABM in the Passaic River Basin with spatially-explicit agents, this is a significant omission. Key questions a reviewer would ask:

- Do agents in the same flood zone exhibit spatial clustering of adaptation behaviors? (Moran's I on binary adapted/not-adapted)
- Is there spatial diffusion of adaptation from flooded to non-flooded adjacent areas?
- Does the MG-NMG adaptation gap have spatial structure? (Are MG agents concentrated in high-risk zones, and does this spatial correlation drive the gap?)

The agent profiles have `flood_zone` (HIGH/MODERATE/LOW) which is a coarse spatial indicator, but there is no census tract, coordinates, or neighborhood structure in the validation module.

**Recommendation**: At minimum, add:
- Spatial autocorrelation of adaptation (Moran's I using flood_zone adjacency)
- Within-zone vs between-zone behavioral variance decomposition
- If agent locations are available: nearest-neighbor adaptation correlation

---

## 5. How L1/L2/L3 Maps to Existing ABM Validation Frameworks

### Mapping to Grimm et al. (2005) Pattern-Oriented Modeling (POM)

| POM Level | WAGF Equivalent | Assessment |
|-----------|----------------|------------|
| Individual-level patterns | L1 (CACR, EBE, R_H) | Strong. CACR validates individual decision coherence. |
| Population-level patterns | L2 (EPI, 8 benchmarks) | Good. B1-B8 are aggregate population patterns. |
| Spatial patterns | (missing) | Gap. POM requires spatial pattern validation. |
| Temporal patterns | B8 (lapse rate) only | Weak. POM requires temporal pattern matching. |
| Multiple patterns simultaneously | EPI (weighted composite) | Reasonable. EPI aggregates multiple patterns. |

Grimm (2005) argues that the more patterns a model reproduces simultaneously, the more constrained (and therefore credible) its structure. The EPI approach is aligned with this philosophy, but the pattern space is limited to aggregate rates. POM would require at least one spatial and one temporal pattern.

### Mapping to Windrum et al. (2007) Empirical Validation

| Windrum Category | WAGF Equivalent | Assessment |
|------------------|----------------|------------|
| Input validation | Not in module (L0) | Gap. No ODD+D compliance check. |
| Descriptive output validation | L2 benchmarks B1-B4 | Adequate. Aggregate rates match empirical data. |
| Predictive output validation | Null model significance test | Good. Tests if EPI exceeds random baseline. |
| Cross-validation | (missing) | Gap. No train/test split. |
| Historical replay | (partial: 2011-2023 flood schedule) | The simulation uses historical floods, but validation does not compare year-by-year outputs to year-by-year empirical data. |

### Mapping to Muller et al. (2013) ODD+D

ODD+D extends ODD with a structured decision-making description. The `BehavioralTheory` protocol captures the *what* of decision-making (construct-to-action mapping), but ODD+D also requires:
- **Individual Sensing**: How agents perceive the environment (partially captured by `state_before`)
- **Individual Prediction**: How agents predict future states (not validated)
- **Interaction**: Social influence on decisions (not in the validation module)
- **Collectives**: Group-level decision processes (not addressed)

The L1/L2/L3 hierarchy is a reasonable simplification, but it does not map 1:1 to ODD+D's 7 decision-related sub-elements.

---

## 6. Specific Recommendations for WRR-Readiness

### R1: Add Temporal Validation Layer (Priority: HIGH)

WRR and HESS reviewers will demand time-series comparison. Minimum viable:
- Compute B1-B8 at each simulation year, not just final aggregate
- Plot simulated vs empirical adaptation curves (if empirical time-series data exists)
- Report Theil inequality coefficient or RMSE for temporal trajectory matching
- Test for structural break detection after major flood events (Chow test or equivalent)

### R2: Implement Calibration-Validation Split Protocol (Priority: HIGH)

The current framework uses all data for both metric computation and threshold assessment. For WRR:
- Document which data informed the benchmark ranges (calibration) vs which data tests the ranges (validation)
- Support k-fold cross-validation across seed replications (e.g., calibrate on seeds 1-3, validate on seeds 4-6)
- At minimum, clearly label the 8 benchmark ranges as "derived from literature" (external validation) vs "tuned from pilot runs" (internal calibration)

### R3: Connect CACR Decomposition to Formal Sensitivity Analysis (Priority: MEDIUM)

The CACR decomposition (raw vs final, quadrant-level, retry/fallback rates) is already an implicit sensitivity analysis of governance effects. Formalize this:
- Frame the decomposition as a variance attribution: how much of CACR is explained by governance filtering vs LLM reasoning?
- Report effect sizes (eta-squared or similar) for the governance intervention
- Connect to Morris method: the governance parameters (retry limit, fallback policy) are natural screening variables

### R4: Add at Least One Spatial Metric (Priority: MEDIUM)

Even without fine-grained spatial data, you can compute:
- Between-zone behavioral variance ratio: Var(adaptation | flood_zone) / Var(adaptation | total)
- This tests whether flood zone assignment structures adaptation behavior spatially

### R5: Strengthen the Null Model (Priority: LOW-MEDIUM)

The uniform-random null model is a necessary baseline but not sufficient. Add:
- **Frequency-matched null**: Agents choose actions with empirically-observed marginal frequencies (breaks construct-action coupling while preserving base rates)
- **Shuffled null**: Permute agent-action assignments across agents within each year (preserves temporal structure, breaks agent-specific patterns)
- **Theory-consistent null**: Random actions drawn from PMT-coherent set (breaks actual LLM reasoning while preserving theory structure)

These three null models test different aspects of the model's non-randomness and would substantially strengthen the statistical argument.

### R6: Document Benchmark Provenance (Priority: HIGH)

For each of the 8 benchmarks, the validation report should include:
- The specific empirical source (paper, dataset, year)
- The geographic context of the empirical data
- How the range was derived (point estimate +/- uncertainty, or multiple sources)
- Whether the range was used during model development (calibration) or reserved (validation)

Currently, benchmark descriptions are one-line strings. This is insufficient for peer review.

---

## 7. "Minimum Viable Universal" for Environmental ABMs

To make this framework genuinely universal for environmental ABMs, the following components are required:

### Must-Have (before claiming "universal"):

1. **Pluggable construct grounding** -- `ConstructGrounder` protocol for CGR, not hardcoded flood rules
2. **Temporal validation metrics** -- Year-by-year benchmark tracking with trend/change-point tests
3. **Benchmark provenance metadata** -- Source, geography, uncertainty, calibration/validation label per benchmark
4. **Configurable hallucination rules** -- Move hallucination detection from `hallucinations/flood.py` to a domain-configurable checker (currently checks flood-specific constraints like "renter cannot elevate")
5. **ODD+D template integration** -- L0 compliance check that reads an ODD+D document and verifies simulation components match declared design

### Nice-to-Have (for strong universality):

6. **Spatial metrics module** -- Moran's I, variograms, spatial clustering indices
7. **Formal SA interface** -- Morris/Sobol wrapper that uses the validation metrics as response variables
8. **Paradigm B support** -- Frame-conditional theories (Prospect Theory, nudge) with tendency-based rather than lookup-table coherence checking
9. **Cross-scale emergence tests** -- Statistical tests for whether L2 patterns emerge from L1 mechanisms (e.g., if you shuffle L1 coherence, does L2 EPI degrade proportionally?)
10. **Multi-model comparison** -- Side-by-side validation reports for different LLMs on the same scenario

### Not Needed for MVP:

- Full Wasserstein distance comparison (too heavy for most ABMs)
- Sycophancy/prompt injection testing (important but belongs in a separate LLM evaluation module)
- Real-time dashboard (nice but not for publication)

---

## 8. Would I Adopt This Framework?

**Yes, conditionally.** I would adopt WAGF's C&V module for an irrigation ABM project under these conditions:

### Adoption Requirements:

1. **CGR grounding is pluggable**: I need to define `ground_wsa_from_state()` and `ground_aca_from_state()` using reservoir levels and crop stage, without modifying `cgr.py` itself. The current architecture requires me to fork the file.

2. **Temporal validation exists**: My irrigation ABM runs 42-year simulations. I need year-by-year crop yield and water demand validation against USGS/NASS data. The current framework only validates end-state aggregates.

3. **Hallucination detection is configurable**: "Farmer irrigates during winter wheat dormancy" is a hallucination in my domain, but `hallucinations/flood.py` only knows about flood-specific impossibilities.

4. **Benchmark registry is truly domain-agnostic**: The current `BenchmarkRegistry` is clean, but `_compute_benchmark()` in `flood.py` passes `ins_col` and `elev_col` -- flood-specific column helpers. A universal dispatch should not leak domain columns into the registry interface.

### What I Would Keep As-Is:

- The `BehavioralTheory` Protocol -- already works for my `IrrigationWSATheory`
- The bootstrap CI module -- completely generic, no domain coupling
- The null model framework -- would just need different action pools
- The EPI computation logic -- weighted benchmark aggregation is domain-agnostic
- The CACR decomposition -- governance filtering analysis applies to any governed ABM

### What I Would Need to Replace:

- `hallucinations/flood.py` -- entirely domain-specific
- `benchmarks/flood.py` -- need `benchmarks/irrigation.py` with USGS/NASS ranges
- `cgr.py` grounding functions -- need hydrology-specific state-to-construct rules
- `io/trace_reader.py` normalization mappings -- irrigation actions differ from flood actions

### Bottom Line:

The framework is approximately 60% universal and 40% flood-specific. The 60% that is universal (protocol interfaces, statistical machinery, report structure) is well-engineered. The 40% that is flood-specific is cleanly separated into domain modules, which means refactoring to full universality is feasible -- probably 2-3 days of work to abstract the domain layer.

For a WRR submission specifically, I would want to see temporal validation and benchmark provenance added. Without those, Reviewer 2 will flag it.

---

## Appendix: Comparison to Recent LLM-ABM Water Resources Papers

The C&V framework is more rigorous than most published LLM-ABM validation approaches. From the literature review (CV_LLM_ABM_Literature_Review.docx), 22/35 recent LLM-ABM papers use only subjective/qualitative validation. WAGF's L1 (CACR, CGR) and L2 (EPI with null model) exceed the current publication standard. However, the leading edge of ABM validation (e.g., Grimm et al. 2005's POM, Ten Broeke et al. 2016's SA integration) sets a higher bar that the framework does not yet meet.

The closest comparable work in water resources is likely Haer et al. (2017, WRR) on flood risk adaptation ABMs, which uses empirical calibration targets similar to B1-B8 but also includes temporal insurance uptake curves. WAGF's EPI formalization and null model testing go beyond Haer et al., but their temporal validation is stronger.

---

*Review completed: 2026-02-14*
*Reviewer: Dr. Maria Gonzalez (Hydrology & ABM Expert)*
