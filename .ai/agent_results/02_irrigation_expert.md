# C&V Validation Framework Review: Irrigation Domain Perspective

**Reviewer**: Dr. Wei Chen, Water Resources Systems Analyst
**Affiliation**: Colorado River Basin research group
**Date**: 2026-02-14
**Focus**: Portability assessment for CRSS-derived irrigation ABM (78 agents, 42-year horizon, WSA/ACA constructs)

---

## Executive Summary

The WAGF C&V framework represents a serious and well-structured attempt at LLM-ABM validation that goes far beyond the "subjective validation only" approach I see in 22 of the 35 LLM-ABM papers cited in the literature review. The three-level architecture (L1 micro, L2 macro, L3 cognitive) is conceptually sound and the separation of structural plausibility from predictive accuracy is the correct framing for our class of models.

However, as an irrigation researcher attempting to adopt this framework, I encounter significant friction. The framework was clearly built flood-first with irrigation as an afterthought example. The `IrrigationWSATheory` in `examples.py` is a useful sketch but would not survive contact with a real CRSS-based simulation. My overall assessment: **usable with 2-3 weeks of adaptation work**, but several architectural gaps would need to be addressed.

---

## Dimension Scores (1-5)

### 1. Domain Portability (3/5)

**What works well:**
- The `BehavioralTheory` Protocol in `base.py` is cleanly designed. The four required methods (`get_coherent_actions`, `extract_constructs`, `is_sensible_action`, plus properties) are genuinely theory-agnostic. I could implement this interface for WSA/ACA in an afternoon.
- The `BenchmarkRegistry` pattern (decorator-based dispatch) is elegant and extensible. Registering new benchmark computations is straightforward.
- YAML externalization via `config_loader.py` shows the right architectural direction -- separating theory configuration from computation logic.

**What does not work:**
- The `config_loader.py` hard-codes a 2-dimension tuple key parser (`_parse_rule_key` splits on `_` assuming exactly two parts). My WSA/ACA is also 2D so this happens to work, but any 3D theory (e.g., TPB with attitude/norm/PBC) would break the YAML key format `VH_VH_H`.
- The `TheoryConfig` dataclass hard-codes `owner_rules` and `renter_rules` as the two agent-type rule sets. For irrigation, I need `senior_rights_rules`, `junior_rights_rules`, `municipal_rules`, `tribal_rules`, etc. The config structure assumes a binary agent taxonomy.
- The `flood.py` benchmark functions have hard-coded column names (`final_has_insurance`, `final_elevated`, `flood_zone == "HIGH"`). These are not parameterized -- you cannot pass column name mappings. I would need to write an entirely new `irrigation.py` benchmark module.
- The `compute_validation_metrics.py` main entry point (imported in `example_cv_usage.py`) is tightly coupled to PMT constructs. The `compute_l1_metrics()` function signature takes `agent_type` as a string but internally dispatches to `PMT_OWNER_RULES` or `PMT_RENTER_RULES`. There is no way to inject a custom theory without modifying the source.

**Effort estimate**: ~2 weeks to write `irrigation_benchmarks.py`, a custom `IrrigationTheoryConfig`, and wire it through `compute_validation_metrics.py`. The Protocol interface itself is fine; the surrounding plumbing is flood-specific.

### 2. No-Historical-Data Scenario (2/5)

This is my biggest concern. The flood L2 benchmarks are grounded in extensive empirical literature: NFIP take-up rates (Choi et al. 2024), post-Sandy elevation data (Brick Township HMGP), insurance lapse rates (Michel-Kerjan et al. 2012). Each benchmark range has a clear citation.

For Colorado River Basin irrigation, I have:
- **CRSS allocation data** (water rights, not behavioral surveys)
- **USDA NASS crop statistics** (aggregate, not agent-level)
- **Some published technology adoption rates** from USGS reports
- **No household-level survey data** on farmer decision-making under scarcity

**What I could substitute for L2 benchmarks:**

| Benchmark | Proxy Data Source | Confidence |
|-----------|-------------------|------------|
| Deficit irrigation adoption | Ward & Pulido-Velazquez (2008), Grafton et al. (2018) aggregate rates | Medium |
| Technology adoption (drip/sprinkler) | USDA Farm and Ranch Irrigation Survey 2018 | Medium-High |
| Demand reduction during drought | CRSS curtailment records, Reclamation data | High |
| Fallowing rate | USDA CropScape time series | Medium |
| Water market participation | Libecap (2011), Brewer et al. (2008) transaction data | Low-Medium |
| Conjunctive use rate | State engineer reports | Low |

The framework provides no guidance on how to construct benchmarks from aggregate/administrative data rather than household surveys. The README's "Step 2: Define Empirical Benchmarks" section shows the data structure but says nothing about what to do when your ranges are derived from aggregate statistics rather than individual-level observations. This is a critical gap because the ecological inference problem (aggregate-to-individual) is real -- a 25% aggregate adoption rate does not mean each agent has a 25% probability of adopting.

**What is missing**: A discussion of benchmark construction methodology. When should ranges be wide vs. narrow? How to handle benchmarks derived from different spatial scales? The flood benchmarks implicitly assume survey-derived ranges, which is a luxury most water resource domains do not have.

### 3. Continuous vs. Categorical Constructs (2/5)

This is a fundamental architectural limitation. The entire CACR computation pipeline assumes ordinal categorical labels (VL/L/M/H/VH). The `get_coherent_actions()` method takes `Dict[str, str]` -- string labels, not floats.

My CRSS-derived WSA and ACA are continuous indices on [0, 1]:
- **WSA**: Computed from reservoir levels, snowpack, curtailment probability -- a continuous physical signal
- **ACA**: Derived from water rights seniority, financial reserves, infrastructure flexibility -- a continuous capacity score

The `IrrigationWSATheory` example discretizes these into VL/L/M/H/VH, which is what I would have to do. But this introduces several problems:

1. **Boundary artifacts**: An agent with WSA=0.499 gets "M" and WSA=0.501 gets "H", producing completely different allowed actions. With 78 agents over 42 years, these boundary effects accumulate.
2. **Information loss**: The 5-level discretization collapses a 2D continuous space into a 25-cell grid. The actual WSA x ACA landscape has nuanced gradients that matter for water allocation decisions.
3. **Threshold sensitivity**: The choice of cut-points (what constitutes "High" WSA?) is arbitrary and not discussed anywhere in the framework documentation.
4. **No Paradigm B support in practice**: The `base.py` docstring mentions "Paradigm B (Frame-Conditional): Prospect Theory, Nudge -- tendency matching" but there is zero implementation. Continuous constructs would naturally fit Paradigm B (e.g., "if WSA > 0.7 AND ACA > 0.5, tendency toward conservation"), but this pathway does not exist yet.

**What I would need**: Either (a) a `ContinuousBehavioralTheory` protocol that takes `Dict[str, float]` and returns coherence scores on [0,1] rather than binary match/no-match, or (b) explicit guidance on discretization methodology with sensitivity analysis requirements. Neither exists.

### 4. Multi-Agent Complexity (2/5)

The framework assumes a simple binary agent taxonomy: owner vs. renter. This manifests in multiple places:

- `TheoryConfig` has exactly two rule dicts: `owner_rules` and `renter_rules`
- The `pmt_flood.yaml` has exactly two rule blocks under `rules:`
- `compute_l1_metrics()` takes a single `agent_type` string
- L2 benchmarks split on `tenure == "Owner"` or `tenure == "Renter"` and `mg == True/False`

My CRSS model has 78 agents with:
- **7 water rights priority classes** (pre-1922 through post-2000)
- **4 use types** (agricultural, municipal, industrial, environmental)
- **3 geographic clusters** (Upper Basin, Lower Basin, tributaries)
- **Heterogeneous allocation volumes** (ranging from 50 AF to 500,000+ AF)

This is not a simple type split -- it is a continuous hierarchy where priority date, geographic location, and use type interact to determine what actions are physically and legally available. A senior agricultural right holder in the Upper Basin faces completely different constraints than a junior municipal user in the Lower Basin.

The `agent_types` property in `BehavioralTheory` returns `List[str]`, which could theoretically accommodate my types, but the rest of the pipeline (config loader, benchmark computations, trace readers) assumes at most 2-3 types. The `mg_adaptation_gap` benchmark, for instance, hard-codes a binary MG/NMG split that has no analog in my domain (the relevant equity dimension is senior vs. junior rights, not income-based marginalization).

**What I would need**:
- Rule tables parameterized by arbitrary agent attributes (not just type string)
- Benchmark definitions that can specify custom group-by columns
- A `_compute_benchmark()` signature that accepts group-definition functions, not just DataFrame column lookups

### 5. Temporal Validation Gap (4/5 -- critical)

This is the most technically important gap for irrigation. The README acknowledges it: "No temporal trajectory validation: EPI compresses multi-year dynamics into a single number."

Irrigation has strong temporal structure that aggregate metrics obliterate:

1. **Seasonal cycles**: Planting (Mar-Apr) vs. growing (May-Aug) vs. harvest (Sep-Oct) vs. fallow (Nov-Feb). Demand decisions follow this cycle. An agent choosing `increase_demand` in November is incoherent regardless of WSA/ACA levels.
2. **Drought memory**: After the 2002 Colorado River drought, conservation behaviors persisted for 3-5 years even after reservoir recovery. After 2020 Tier 1 shortage, curtailment responses were faster. A 42-year simulation without temporal trajectory validation cannot distinguish "behaviorally realistic drought response" from "random walk that happens to have correct aggregate statistics."
3. **Adaptation S-curves**: Technology adoption (drip irrigation, deficit scheduling) follows sigmoid diffusion. A model that linearly ramps adoption matches aggregate benchmarks but is temporally implausible.
4. **Allocation cascading**: Junior rights get curtailed before senior rights. The temporal sequence of who responds first matters enormously for system behavior. A metric that only checks end-state rates misses this entirely.

The framework mentions "post-flood adaptation spike ratio" and "insurance survival half-life" as future directions, which are the flood analogs of what I need. But they do not exist yet.

**What I would need**:
- **Seasonal coherence metric**: Fraction of decisions that are seasonally appropriate
- **Drought response lag**: Time between drought signal and behavioral shift (should be 0-2 years, not instant)
- **Adaptation trajectory shape**: Kolmogorov-Smirnov or dynamic time warping against empirical adoption curves
- **Priority-cascade timing**: Do junior rights curtail before senior rights? (binary pass/fail per drought event)

**Severity**: For flood models with annual decisions, the temporal gap is tolerable. For irrigation with sub-annual cycles over 42 years, it is disqualifying without supplementation. I rate this 4/5 severity (not 5/5 because I could implement temporal metrics as custom L2 benchmarks -- the registry is extensible enough).

### 6. C&V for Irrigation -- Concrete L1/L2/L3 (3/5)

Here is what the three levels would look like for my CRSS irrigation ABM:

**L3 Cognitive Validation** (pre-experiment):
- Design 15-20 archetypes spanning the priority-geography-use space:
  - "Senior agricultural, Upper Basin, abundant snowpack" (expected: maintain/increase)
  - "Junior municipal, Lower Basin, drought year 3" (expected: decrease_large, seek_transfer)
  - "Tribal reserved rights, drought, politically constrained" (expected: maintain, invoke decree)
- Probe each archetype 10x with Gemma 3 4B, compute ICC and eta-squared
- **Gap in framework**: No guidance on archetype design when agent heterogeneity is continuous rather than factorial. The flood model uses a 2x2 design (tenure x MG); I need a 7x4x3 design space, which means either combinatorial explosion or careful Latin hypercube sampling of archetypes.

**L1 Micro Validation** (per-decision):
- CACR: Does action match WSA x ACA coherence table? (Adaptable with `IrrigationWSATheory`)
- R_H: Domain hallucinations include:
  - Increasing demand when at allocation cap
  - Deficit irrigating crops that require full irrigation (alfalfa in some configurations)
  - Trading water rights the agent does not hold
  - Planting water-intensive crops during Tier 2+ shortage
- EBE: Should show diversity across 5 skills (increase_large, increase_small, maintain, decrease_small, decrease_large) -- neither all-maintain nor uniformly random

**L2 Macro Validation** (aggregate):
- B1: Deficit irrigation adoption rate [0.20, 0.45] -- Ward & Pulido-Velazquez 2008
- B2: Technology adoption rate [0.05, 0.20] -- USDA FRIS 2018
- B3: Aggregate demand reduction during drought [0.10, 0.30] -- CRSS records
- B4: Fallowing rate during severe drought [0.05, 0.25] -- CropScape analysis
- B5: Water market transaction rate [0.02, 0.10] -- Brewer et al. 2008
- B6: Priority-based curtailment compliance [0.85, 1.00] -- Legal requirement, should be near-perfect
- B7: Post-drought conservation persistence [0.30, 0.60] -- Estimated from NASS trends
- B8: Senior-junior adaptation gap [0.10, 0.35] -- Analog to MG adaptation gap

**Adequacy of examples**: The `IrrigationWSATheory` class and Example 4 in `example_cv_usage.py` provide a useful starting template for L1. The L2 benchmark construction methodology is where guidance falls short. The example shows how to *define* benchmarks (range, weight, description) but not how to *compute* them from irrigation-specific trace structures (no `irrigation.py` analog to `flood.py`). The hallucination examples in the README are helpful but insufficient -- irrigation hallucinations are more subtle than flood hallucinations (it is not just "impossible state + action" but also "physically possible but hydrologically nonsensical").

### 7. Biggest Barriers to Adoption (Summary)

**Barrier 1: Tight coupling to flood domain in computation layer** (HIGH)
The `BehavioralTheory` Protocol is clean, but everything downstream -- `config_loader.py`'s 2-type assumption, `flood.py`'s column names, `compute_validation_metrics.py`'s PMT dispatch -- is flood-specific. I cannot plug in `IrrigationWSATheory` and run `compute_validation()` end-to-end without rewriting the computation pipeline.

**Barrier 2: No continuous construct support** (HIGH)
My WSA/ACA are floats, not ordinal labels. Discretizing them is lossy and introduces boundary artifacts. The framework needs either a continuous CACR variant or explicit discretization guidance with sensitivity analysis tooling.

**Barrier 3: No benchmark computation templates for non-survey domains** (MEDIUM-HIGH)
The flood benchmarks have clear empirical grounding. I would need to construct my own benchmark ranges from aggregate administrative data, and there is no methodology section explaining how to do this defensibly. How wide should ranges be? How to weight benchmarks when confidence in the underlying data varies? These are methodological questions that the framework should address.

**Barrier 4: No temporal trajectory validation** (MEDIUM-HIGH for irrigation, MEDIUM for flood)
EPI compresses a 42-year simulation into one number. I need seasonal coherence, drought response lag, and adaptation curve shape metrics. These can be built as custom benchmarks using the registry, but it requires substantial effort.

**Barrier 5: Binary agent type assumption** (MEDIUM)
The 7-class priority hierarchy with geographic and use-type heterogeneity does not map onto owner/renter. The config loader, theory config, and benchmark computations all need generalization.

**Barrier 6: No streaming/scalability for large simulations** (LOW for my model, noted for others)
78 agents x 42 years = ~3,276 traces, well within memory limits. But the README notes 500K+ traces need streaming, which matters for larger ensembles.

---

## Specific Code-Level Observations

### `base.py` -- BehavioralTheory Protocol
- **Strength**: `runtime_checkable` decorator enables isinstance() checking at runtime. Good practice.
- **Strength**: `is_sensible_action()` as a fallback for unlisted construct combinations is pragmatic.
- **Weakness**: `construct_levels: Dict[str, str]` forces string values. Should be `Dict[str, Union[str, float]]` to support continuous constructs.
- **Weakness**: No `validate_trace()` method -- hallucination detection is external to the theory. In irrigation, hallucinations are theory-dependent (e.g., increasing demand at cap is a WSA-specific impossibility). The theory should own its hallucination rules.

### `examples.py` -- IrrigationWSATheory
- **Strength**: 25-cell WSA x ACA rule table is complete (5x5 grid, no gaps).
- **Weakness**: `agent_types` returns `["farmer"]` only. Real irrigation has multiple agent types with different rule sets.
- **Weakness**: `is_sensible_action()` returns `True` unconditionally. This is a stub, not an implementation. The docstring even says "Fallback check" but there is no actual check.
- **Weakness**: `extract_constructs()` looks for `WSA_LABEL` and `ACA_LABEL` in `skill_proposal.reasoning`, which assumes the LLM prompt is instrumented to produce these fields. No guidance on prompt template design for non-PMT theories.

### `flood.py` -- Benchmark Computations
- **Strength**: Each benchmark is a clean, self-contained function with null-safety checks.
- **Weakness**: The function signature `(df, traces, ins_col, elev_col)` passes flood-specific column references. An irrigation equivalent would need `(df, traces, allocation_col, priority_col, ...)`. The registry dispatch should be more generic.
- **Observation**: `_compute_insurance_lapse_rate()` at ~30 lines is the most complex benchmark. It tracks temporal agent state (was_insured -> lapsed). This pattern is what I need for drought response lag, but the framework does not abstract it into a reusable "temporal state tracking" utility.

### `registry.py` -- BenchmarkRegistry
- **Strength**: Simple, clean, no over-engineering. The decorator pattern is Pythonic.
- **Weakness**: `dispatch()` silently catches exceptions and returns None with a print warning. For debugging during development, this should optionally raise.
- **Weakness**: The fixed signature `(df, traces, ins_col, elev_col)` means every registered function must accept these four parameters even if they do not use them. A `**kwargs` pattern would be more extensible.

### `config_loader.py`
- **Strength**: YAML-first with hard-coded fallback is a good robustness pattern.
- **Weakness**: `_parse_rule_key()` splits on `_` with `maxsplit=1`. This works for 2D keys but fails for 3D (e.g., `VH_H_M` for TPB would parse as `("VH", "H_M")`).
- **Weakness**: `TheoryConfig` has `owner_rules` and `renter_rules` as named fields, not a `Dict[str, Dict[Tuple, List[str]]]` keyed by agent type. Adding a third type requires modifying the dataclass.

---

## Recommendations

1. **Generalize `TheoryConfig`**: Replace `owner_rules`/`renter_rules` with `rules: Dict[str, Dict[Tuple[str, ...], List[str]]]` keyed by agent type string. This is a one-line dataclass change with cascading config loader updates.

2. **Add `ContinuousBehavioralTheory` protocol variant**: Accept `Dict[str, float]` and return coherence as a score on [0,1] rather than binary. This enables fuzzy CACR for continuous constructs.

3. **Generalize benchmark function signatures**: Use `**kwargs` in the registry dispatch so domain-specific benchmarks can receive domain-specific parameters without polluting the interface.

4. **Add temporal validation metrics as a standard L2 extension**: At minimum, provide a `TemporalBenchmark` base class that computes time-series metrics (lag, shape, persistence) and integrates with EPI.

5. **Write a "Benchmark Construction Guide"**: A 2-page section on how to derive plausible ranges from (a) survey data, (b) aggregate statistics, (c) expert elicitation, and (d) sensitivity analysis. This is the intellectual infrastructure that makes the framework portable.

6. **Move hallucination detection into `BehavioralTheory`**: Add an `is_hallucination(trace)` method so domain-specific impossibility rules live with the theory, not in a separate YAML file that may not cover all cases.

---

## Overall Assessment

| Dimension | Score | Notes |
|-----------|-------|-------|
| Domain Portability | 3/5 | Protocol is clean; plumbing is flood-specific |
| No-Historical-Data Scenario | 2/5 | No benchmark construction methodology for non-survey domains |
| Continuous vs. Categorical | 2/5 | Forces discretization; no continuous construct support |
| Multi-Agent Complexity | 2/5 | Binary agent type assumption throughout |
| Temporal Validation Gap | 4/5 severity | Critical for 42-year irrigation; registry allows workarounds |
| C&V for Irrigation (guidance) | 3/5 | Good L1 template; weak L2 guidance; no L3 archetype design for continuous heterogeneity |
| Biggest Barriers | -- | Tight flood coupling, no continuous support, no benchmark methodology |

**Bottom line**: The conceptual architecture (Protocol + Registry + YAML config + three-level validation) is sound and publishable. The implementation is a flood ABM validation toolkit with aspirations of generality. For my irrigation ABM, I would adopt the conceptual framework and metric definitions (CACR, EBE, R_H, EPI), but I would need to rewrite approximately 40-60% of the computation layer. The `BehavioralTheory` Protocol and `BenchmarkRegistry` would survive as-is; everything else gets replaced.

**Would I use this tomorrow?** No. In two weeks with dedicated effort? Yes, and it would be significantly better than the "subjective validation only" approach used by 63% of the LLM-ABM literature.

---

*Review completed 2026-02-14 by Dr. Wei Chen*
