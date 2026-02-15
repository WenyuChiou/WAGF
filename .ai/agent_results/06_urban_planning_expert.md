# Expert Review: WAGF C&V Validation Module
## Perspective: Urban Planning / Residential Mobility ABMs

**Reviewer**: Dr. Carlos Rivera, Urban Planning & Residential Mobility ABM Researcher
**Date**: 2026-02-14
**Focus**: Evaluating the C&V framework's applicability to Discrete Choice Theory (DCT)-based residential mobility models with Census tract-level aggregate data

---

## Executive Summary

The WAGF C&V framework represents a serious and well-structured effort to bring behavioral validation rigor to LLM-agent simulations. Its three-level architecture (L3 cognitive, L1 micro, L2 macro) is a genuine contribution. However, from the perspective of urban planning ABMs -- where agents make continuous utility-maximizing location choices across dozens of neighborhoods using aggregate Census data -- the framework has significant structural gaps. The `BehavioralTheory` Protocol is hard-wired around categorical construct-action lookup tables, which is a poor fit for DCT's continuous utility functions. The complete absence of spatial validation metrics is a critical limitation for any geographically explicit urban model. That said, the L2 benchmark architecture is surprisingly well-suited to aggregate-only data, and several targeted extensions could make this framework genuinely useful for the urban ABM community.

---

## Dimension Scores

### 1. Utility-Based Theory Fit — Score: 2/5

**The core problem**: DCT does not map onto categorical construct-action tables. In residential mobility, an agent evaluates the utility of 50+ neighborhoods simultaneously via:

```
U_ij = V_ij + epsilon_ij
V_ij = beta_1 * rent_j + beta_2 * school_quality_j + beta_3 * ethnic_similarity_j + ...
```

where the agent chooses `argmax(U_ij)`. There is no "threat perception" or "coping perception" -- there is a continuous utility surface with stochastic error terms.

The `BehavioralTheory` Protocol (`base.py`) defines `get_coherent_actions()` as returning a `List[str]` of valid actions given discrete construct levels. This is Paradigm A: categorical construct-action mapping. The README mentions a "Paradigm B (Frame-Conditional): Prospect Theory, Nudge -- tendency matching" but **no implementation exists**. There is no Paradigm C for continuous utility theories.

**What "Paradigm B" would look like for DCT**: Rather than checking `action in allowed_list`, coherence validation for DCT would need to verify:
- The chosen neighborhood ranks in the top-K by estimated utility (partial ordering check)
- Utility-decreasing moves are rare and explainable (e.g., cultural attachment, social network pull)
- The distribution of choices across neighborhoods follows a logit-like probability distribution (aggregate coherence)

This would require a fundamentally different `get_coherent_actions()` signature -- something like `get_coherence_score(chosen_action, all_options, agent_state) -> float` returning a continuous score rather than a binary in/out check. The current Protocol does not support this.

**Positive note**: The `is_sensible_action()` fallback method hints at the right direction -- it implements a softer, ordinal logic rather than strict lookup. A DCT extension could build on this pattern.

### 2. Aggregate-Only Data — Score: 4/5

**This is the framework's hidden strength.** The L2 macro benchmarks (`flood.py`, `l2_macro.py`) are explicitly designed around aggregate plausibility ranges, not individual trace matching. The benchmark specification format:

```python
"insurance_rate_sfha": {
    "range": (0.30, 0.60),
    "weight": 1.0,
}
```

maps directly to how Census-derived validation works in urban ABMs. I could define:

```python
"tract_level_turnover_rate": {
    "range": (0.08, 0.18),  # ACS 1-year mobility rates
    "weight": 1.0,
}
"gentrification_displacement_rate": {
    "range": (0.03, 0.12),
    "weight": 1.5,
}
"segregation_index_dissimilarity": {
    "range": (0.40, 0.65),  # typical US metro D-index
    "weight": 2.0,
}
```

The EPI (Empirical Plausibility Index) computation in `l2_macro.py` is clean and extensible. The weighted pass/fail with configurable thresholds is exactly how POM-style validation works. The YAML externalization (`flood_benchmarks.yaml`) means I could define `urban_benchmarks.yaml` without touching any code.

**One concern**: The `_compute_benchmark()` functions in `flood.py` are domain-specific (they reference `flood_zone`, `tenure`, etc.). The benchmark *definitions* are extensible, but the *computation functions* would all need to be rewritten. The `BenchmarkRegistry` pattern with `@_registry.register()` decorators is the right architecture, but there is no guidance on how to register custom computations from outside the flood domain.

### 3. Spatial Validation — Score: 1/5

**This is the most critical gap.** The framework has zero spatial support. No metric, no interface, no placeholder. For urban ABMs, spatial patterns ARE the primary validation target:

- **Segregation indices** (Dissimilarity D, Information Theory H, Spatial Exposure P*): Do simulated residential patterns reproduce observed segregation levels?
- **Moran's I / LISA**: Is spatial autocorrelation of property values / demographics consistent with observed patterns?
- **Distance decay**: Do migration flows follow gravity-model distance decay?
- **Hotspot analysis**: Do gentrification / disinvestment hotspots emerge in plausible locations?

The README acknowledges this gap explicitly: "No spatial validation: All metrics are aspatial. Water resources applications need Moran's I." But even for the flood domain itself, spatial clustering of adaptation decisions (e.g., "do neighborhoods that elevate cluster near each other?") would strengthen validation significantly.

For urban planning adoption, this is a non-negotiable requirement. Without spatial metrics, I would have to build an entirely separate validation pipeline anyway, defeating the purpose of a shared framework.

### 4. Emergent Pattern Validation — Score: 2/5

**The framework validates structure, not dynamics.** The L2 benchmarks are static snapshots -- "at the end of the simulation, is the insurance rate between 30-60%?" This says nothing about:

- **Tipping points**: Does gentrification accelerate nonlinearly past a threshold?
- **Path dependence**: Do different random seeds produce qualitatively different trajectories?
- **Temporal signatures**: Do adaptation waves follow an S-curve, logistic growth, or step function?
- **Regime shifts**: Does the system transition between stable states?

The README acknowledges temporal limitations: "EPI compresses multi-year dynamics into a single number." The insurance lapse rate benchmark (`insurance_lapse_rate`) is the closest thing to a temporal metric, but it measures a single rate, not a trajectory shape.

For residential mobility ABMs, I care about emergent segregation dynamics (Schelling tipping), gentrification wave propagation, and self-reinforcing feedback loops (rising rents -> displacement -> concentrated poverty -> disinvestment). None of these can be captured by endpoint aggregate rates.

**Partial credit**: The `_compute_do_nothing_rate_postflood()` benchmark shows the framework CAN do conditional analysis (filtering traces by `flooded_this_year`). This pattern could be extended to temporal conditioning (e.g., "adaptation rate in years 1-3 vs years 10-13"). The architecture supports this; it just has not been implemented.

### 5. Action Space Complexity — Score: 2/5

**The framework assumes a small, discrete action set.** The flood domain has 6 actions: `buy_insurance`, `elevate`, `buyout`, `relocate`, `retrofit`, `do_nothing`. The PMT lookup tables enumerate all 25 (TP x CP) combinations for each agent type.

In residential mobility, agents choose among 50+ Census tracts. The action space is:
- **Large**: 50-200 neighborhoods in a metro area
- **Continuous in attributes**: Each neighborhood has rent, school quality, crime rate, ethnic composition
- **Dynamic**: Neighborhood attributes change endogenously as agents move

A lookup table of 25 x 50+ entries is infeasible and meaningless. The `get_coherent_actions()` interface returning `List[str]` fundamentally assumes the action space is small enough to enumerate.

**What would work**: A scoring/ranking interface where coherence is measured as "did the agent choose from the top-K ranked neighborhoods given their utility function?" This maps to DCT's random utility maximization. CACR would become something like "fraction of choices where the selected neighborhood is in the top-10 by utility."

The EBE (Effective Behavioral Entropy) metric is actually relevant here -- if all 400 households choose the same 3 neighborhoods, something is wrong. But the current implementation computes entropy over a small action set. For a 50-neighborhood choice set, the expected entropy is much higher, and the 0.1 < ratio < 0.9 threshold would need recalibration.

### 6. Cross-Framework Comparison (POM) — Score: 4/5

**The C&V framework is clearly POM-inspired and largely complementary.** The README cites Grimm et al. (2005) explicitly, and the architecture follows POM's core logic: define multiple patterns at different scales, check if the model reproduces them simultaneously.

Key differences from standard POM:

| Aspect | POM (Grimm et al.) | WAGF C&V |
|--------|--------------------|----|
| Theory role | Patterns derived from empirical observations | Patterns derived from behavioral theory + empirical lit |
| Micro validation | No standard micro protocol | L1 CACR (construct-action coherence) |
| Cognitive check | Not addressed | L3 ICC/eta-squared (persona discriminability) |
| Temporal patterns | Often included (population dynamics, cycles) | Absent (endpoint only) |
| Spatial patterns | Often included (home range, clustering) | Absent |
| Implementation | Typically ad hoc scripts | Modular code with registries and protocols |

The L3 cognitive validation and L1 CACR decomposition are genuine additions that POM lacks. These are especially valuable for LLM-agents where "is the model reasoning correctly?" is a distinct question from "does the output match patterns?" In equation-based ABMs, there is no reasoning to validate -- the code IS the reasoning. LLM-agents introduce a new layer of opacity that L1/L3 address.

**My assessment**: C&V should be positioned as POM-for-LLM-ABMs, not as a POM replacement. It adds LLM-specific micro/cognitive validation while inheriting POM's macro pattern-matching philosophy. For urban ABMs, I would use C&V's L1/L3 for LLM reasoning validation and POM's spatial/temporal patterns for emergent dynamics validation. They are complementary.

### 7. What Would Make Me Adopt This — Score: 3/5

**Three features that would change my mind:**

**Feature 1: Spatial Metrics Module (`validation/metrics/spatial.py`)**
- `compute_moran_i(agent_locations, attribute)` -- spatial autocorrelation of any agent attribute
- `compute_dissimilarity_index(agent_locations, group_attribute)` -- segregation index
- `compute_spatial_clustering(agent_actions, geography)` -- LISA-style local spatial statistics
- Benchmark format: `{"segregation_D": {"range": (0.40, 0.65), "weight": 2.0}}`
- This is table-stakes for any geographically explicit ABM

**Feature 2: Paradigm B/C Theory Interface for Continuous Utility Theories**
- Replace `get_coherent_actions() -> List[str]` with `get_coherence_score(chosen, alternatives, state) -> float`
- Support ranking-based coherence: "is the choice in the top-K?"
- Support distributional coherence: "does the choice probability distribution match a logit model?"
- CACR becomes a continuous metric (average coherence score) rather than binary (in/out of list)

**Feature 3: Temporal Trajectory Validation**
- `compute_trajectory_shape(metric_timeseries)` -- classify as linear, S-curve, step, or stochastic
- `compute_trend_consistency(simulated_trajectory, reference_trajectory)` -- DTW or similar
- Benchmark format: `{"gentrification_wave": {"shape": "S-curve", "inflection_year_range": (5, 10)}}`
- This would catch models that produce the right endpoint but wrong dynamics

**Honorable mention**: Streaming processing for large trace files (500K+ traces). Urban ABMs with 50K agents over 50 years generate 2.5M decision traces. The README notes this as a known limitation.

---

## Detailed Observations

### Strengths

1. **Modular, protocol-based design**: The `BehavioralTheory` Protocol in `base.py` is well-designed for extensibility. The separation of theory, benchmarks, metrics, and I/O is clean.

2. **CACR decomposition (raw vs. final)**: This is a clever idea. Distinguishing pre-governance and post-governance coherence directly addresses the "constrained RNG" critique. If the LLM reasons coherently before governance intervenes, the model has genuine behavioral reasoning, not just random choices filtered to look reasonable.

3. **Supplementary rejection metrics**: The environmental justice framing of governance rejection rates (MG vs NMG) is both methodologically honest and substantively interesting. In urban planning, we have analogous institutional barriers (zoning, mortgage redlining, school district boundaries) that disproportionately constrain minority mobility. The `constrained_non_adaptation_rate` concept transfers directly.

4. **YAML externalization of benchmarks**: `flood_benchmarks.yaml` is exactly the right pattern. I could create `urban_mobility_benchmarks.yaml` without modifying framework code (if the computation functions were also pluggable).

5. **Honest limitation documentation**: The README explicitly lists spatial, temporal, and scalability limitations. This is refreshingly honest compared to most framework papers.

### Weaknesses

1. **Hard-coded flood domain assumptions**: Despite the extensibility rhetoric, `l2_macro.py` imports directly from `validation.theories.pmt` and `validation.benchmarks.flood`. A truly domain-agnostic framework would inject the theory and benchmarks at runtime.

2. **No distributional validation**: All benchmarks are point estimates (rates). Urban ABMs need distributional comparisons -- e.g., "does the simulated rent distribution match the observed distribution?" KS tests, Wasserstein distance, or Q-Q plots would be needed.

3. **Binary pass/fail thresholds**: The EPI reduces 8 continuous benchmark values to binary pass/fail, then averages. This loses information. A benchmark that misses by 0.001 is treated the same as one that misses by 0.30. A continuous distance metric (normalized deviation from range midpoint) would be more informative.

4. **No cross-scale consistency check**: The framework validates L1 (micro) and L2 (macro) independently but does not check whether they are consistent. It is possible for CACR to be high (individual decisions are coherent) while EPI is low (aggregate outcomes are wrong), indicating a systematic bias. This micro-macro linkage is a key concern in urban ABMs.

---

## Summary Table

| Dimension | Score | Key Issue |
|-----------|-------|-----------|
| 1. Utility-Based Theory Fit | 2/5 | Categorical lookup only; no continuous utility support |
| 2. Aggregate-Only Data | 4/5 | L2 benchmarks naturally fit aggregate validation |
| 3. Spatial Validation | 1/5 | Complete absence; non-negotiable for urban ABMs |
| 4. Emergent Pattern Validation | 2/5 | Endpoint-only; no tipping points, trajectories, or regime shifts |
| 5. Action Space Complexity | 2/5 | Assumes small discrete set; infeasible for 50+ neighborhoods |
| 6. Cross-Framework Comparison (POM) | 4/5 | Complementary to POM; adds LLM-specific L1/L3 layers |
| 7. What Would Make Me Adopt | 3/5 | Spatial metrics + continuous theory interface + temporal validation |

**Overall Assessment**: 18/35 (2.6/5.0 average)

**Bottom line**: The C&V framework solves a real problem (LLM-ABM behavioral validation) that no one else has addressed systematically. The L1 CACR decomposition and L3 cognitive validation are genuinely novel contributions. However, for urban planning ABMs specifically, the framework's assumptions (categorical theories, small action sets, aspatial metrics, endpoint validation) conflict with fundamental requirements of the domain. The L2 benchmark architecture is the most transferable component. I would recommend urban ABM researchers watch this framework's development -- particularly if spatial metrics and continuous theory support are added -- but current adoption would require substantial custom extension work that largely duplicates existing POM pipelines.

---

*Review conducted as part of the WAGF C&V expert panel, 2026-02-14.*
