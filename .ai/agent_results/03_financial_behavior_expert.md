# Expert Review: WAGF C&V Validation Module
## Reviewer: Dr. James Park, Computational Social Scientist (Financial Behavior ABMs)

**Date**: 2026-02-14
**Scope**: Evaluate whether the WAGF C&V validation framework can validate LLM-driven financial behavior simulations (household savings, insurance purchase, mortgage default) grounded in Prospect Theory and behavioral economics.

---

## Executive Summary

The C&V framework represents a genuinely novel contribution to LLM-ABM validation. The three-level architecture (L3 cognitive, L1 micro, L2 macro) is well-motivated and the separation of structural plausibility from predictive accuracy is epistemologically sound. However, the framework is currently **tightly coupled to lookup-table theories (Paradigm A)** and **rate-based aggregate benchmarks**, which creates significant friction for financial behavior domains that rely on continuous-valued theories (Prospect Theory), distributional validation (wealth Gini), and strong temporal path dependence (debt spirals, compounding). With moderate engineering effort (2-4 weeks), the framework could be extended to support these use cases, but the current implementation would require substantial custom work.

**Overall Assessment**: 3.4 / 5.0 -- Promising architecture, but domain-specific gaps for financial ABMs.

---

## Dimension-by-Dimension Evaluation

### 1. Prospect Theory Fit (Score: 2/5)

The `BehavioralTheory` protocol in `base.py` explicitly names "Paradigm B (Frame-Conditional)" for Prospect Theory, which shows architectural forethought. However, the gap between the docstring and reality is large.

**The core problem**: `get_coherent_actions()` returns `List[str]` -- a discrete set of allowed actions. Prospect Theory does not work this way. PT predicts:
- **Risk-seeking in losses** (gamble on mortgage default vs. guaranteed loss of savings)
- **Risk-averse in gains** (lock in insurance payout vs. uncertain appreciation)
- **Reference-dependent valuation** (the same $10K loss feels different depending on current wealth relative to reference point)

These are *tendency predictions*, not action-set lookups. A PT-coherent action depends on the *magnitude* of loss/gain relative to a reference point and the *probability weighting* applied. You cannot enumerate this as a lookup table.

**What would be needed**:
- `get_coherent_actions()` would need to return something like `List[Tuple[str, float]]` -- actions with expected tendency weights, not just allowed/disallowed
- Or a new method: `is_tendency_coherent(construct_levels, action, magnitude, reference_point) -> float` returning a coherence score (0-1) rather than binary match
- The CACR metric itself would need to become a continuous coherence score rather than a binary hit/miss rate

**Implementation difficulty**: Moderate-to-hard. The Protocol interface would need a breaking change or a parallel pathway. The `compute_l1_metrics()` function in `l1_micro.py` is hardwired to binary coherence (line 96: `if action in rules[key]`). Refactoring this to support continuous coherence scoring is feasible but touches every downstream metric.

**Positive note**: The `is_sensible_action()` fallback method (lines 60-67 of `base.py`) already hints at a gradient -- it returns bool but uses numeric level comparisons. This could be extended to return a float.

### 2. Rich Historical Data Scenario (Score: 2/5)

With PSID/SCF data giving me 10,000+ observations and known confidence intervals for insurance uptake, savings rates, and mortgage default probabilities, the framework's wide benchmark ranges (e.g., `insurance_rate_sfha: 0.30-0.60`) are frustratingly imprecise.

**Specific issues**:
- `EMPIRICAL_BENCHMARKS` in `flood.py` uses `(low, high)` tuples -- there is no field for point estimate, standard error, confidence interval, or sample size
- The EPI computation in `l2_macro.py` (line 77: `is_in_range = low <= rounded_value <= high`) is binary pass/fail. With rich data, I would want:
  - Z-score or t-test against the empirical mean
  - Weighted distance from point estimate (closer = better, not just in/out)
  - Bootstrap confidence intervals from my survey data to define the plausible range
- The `BenchmarkRegistry` dispatch signature (line 23-24 of `registry.py`) returns `Optional[float]` -- a single scalar. This cannot represent a distribution comparison.

**What would be needed**:
- Extend `EMPIRICAL_BENCHMARKS` schema: `{"range": (0.30, 0.60), "point_estimate": 0.42, "se": 0.03, "n": 8500, "source": "PSID 2019"}`
- Add a `BenchmarkResult` dataclass that returns both the simulated value and a distance metric (e.g., standardized effect size)
- Replace binary EPI with a continuous plausibility score (e.g., sum of 1 - |z_i| / z_critical, weighted)

**Feasibility**: The `BenchmarkRegistry` decorator pattern is clean and extensible. Adding new benchmark types with richer return values is straightforward. But the EPI aggregation logic would need redesign.

### 3. Scale Mismatch (Score: 4/5)

The README honestly flags this: "500K+ traces require streaming processing. Currently loads all into memory." For my 10,000-agent x 30-year simulations (300K traces), this is borderline.

**Analysis of the code**:
- `compute_l1_metrics()` iterates through `traces: List[Dict]` in a single loop -- O(n) time, O(n) memory. 300K dicts at ~500 bytes each = ~150MB. Fine.
- `compute_l2_metrics()` creates a Pandas DataFrame join (`final_states` dict merged into `agent_profiles`). With 10K agents, the DataFrame is ~1MB. No issue.
- `_compute_insurance_lapse_rate()` builds a per-agent trace dictionary (`agent_traces`). With 10K agents x 30 years, this is ~300K entries. Fine.
- The CACR decomposition reads audit CSVs via `pd.read_csv()` and concatenates. Multiple large CSVs could spike memory.

**Verdict**: Nothing fundamental breaks at 10K agents. The code is O(n) everywhere, no quadratic operations. The main risk is if someone stores all traces in a single list in memory while also computing multiple metrics. A streaming `TraceReader` (mentioned in the Architecture Evolution Plan, Phase 5) would be nice but is not critical for 10K agents.

**One concern**: The `_extract_final_states_from_decisions()` function (imported but not shown) likely iterates all traces to build per-agent state. If this is called multiple times, it could be expensive. Should be cached.

### 4. Distributional Validation (Score: 2/5)

This is the most significant gap for financial behavior ABMs. Every benchmark in `flood.py` computes a **rate** (fraction of agents satisfying some condition). Financial behavior validation requires:

- **Wealth distribution**: Gini coefficient, P90/P10 ratio, Lorenz curve shape
- **Savings rate distribution**: Not just mean, but variance and skewness (left tail = over-leveraged households)
- **Default cascade timing**: Not just "what fraction defaults" but the temporal clustering of defaults
- **Portfolio composition**: Joint distribution of assets, debts, insurance coverage

**What the registry supports**: The `BenchmarkRegistry.dispatch()` returns `Optional[float]` -- a single number. A Gini coefficient is a single float, so technically it fits. But comparing a simulated Gini to an empirical range is just one aspect of distributional validation.

**What would be needed**:
- A `DistributionalBenchmark` type that takes two distributions (simulated + empirical) and computes KS statistic, Wasserstein distance, or QQ-plot correlation
- The benchmark dispatch would need to return richer objects (not just float)
- New visualizations: simulated vs. empirical CDFs, wealth quintile comparisons

**The good news**: The decorator pattern in `BenchmarkRegistry` is genuinely extensible. I could register a `wealth_gini` benchmark that returns a float and compare it to an empirical range. But for proper distributional comparison (KS test, Wasserstein), the single-float interface is insufficient.

### 5. Sycophancy and LLM Bias (Score: 3/5)

This is where the framework shows awareness but incomplete coverage.

**What exists**:
- `prompt_sensitivity.py` implements two tests: **option reordering** (positional bias) and **framing removal** (does removing "CRITICAL RISK ASSESSMENT" change TP ratings). These use chi-squared tests. This is good and directly relevant.
- The L3 cognitive validation (ICC, eta-squared) indirectly tests for sycophancy by checking whether the LLM distinguishes between personas rather than just echoing prompt framing.
- The CACR decomposition (`cacr_raw` vs `cacr_final`) separates LLM reasoning quality from governance filtering -- this is a clever anti-sycophancy diagnostic.

**What is missing**:
- **No explicit sycophancy test**: A sycophancy test would present the same scenario but with different "suggested" actions in the prompt and measure whether the LLM follows the suggestion regardless of context. Financial decisions are especially vulnerable (e.g., prompting "most experts recommend buying insurance" could override all PT-based reasoning).
- **No anchoring bias test**: Financial decisions are highly sensitive to numerical anchors. If the prompt mentions "$500/month premium," the LLM might anchor on that number regardless of the agent's income.
- **No loss-framing vs. gain-framing test**: This is the most critical gap for PT. The same objective scenario framed as a loss vs. a gain should produce systematically different decisions, and the LLM should reproduce this asymmetry.

**Assessment**: The framework has the *infrastructure* for bias testing (chi-squared comparison, prompt manipulation pipeline) but not the *content* for financial behavior-specific biases. Extending `prompt_sensitivity.py` with financial-specific tests would be straightforward but requires domain expertise to design the vignettes.

### 6. Multi-Period Temporal Dynamics (Score: 2/5)

The insurance lapse rate benchmark (`_compute_insurance_lapse_rate` in `flood.py`) is the **only** temporal metric. It tracks whether agents who were insured in year t are still insured in year t+1. This is necessary but woefully insufficient for financial ABMs.

**What financial ABMs need**:
- **Wealth trajectory validation**: Do simulated wealth paths match empirical mobility matrices? (e.g., probability of moving from Q1 to Q2 in 5 years)
- **Debt spiral detection**: Once agents start borrowing, do they exhibit realistic debt accumulation patterns?
- **Event response curves**: After a negative shock (job loss, flood), what is the recovery time? Does the simulated distribution of recovery times match PSID panel data?
- **Habit formation / hysteresis**: Agents who start saving should persist; agents who default should have long-term credit impairment.
- **Autocorrelation of decisions**: Financial decisions are highly autocorrelated (I bought insurance last year, so I buy again). The framework measures this only for insurance lapse.

**What the framework provides**: The trace format includes `year` and `agent_id`, so temporal trajectories can be reconstructed. But there are no temporal metrics beyond lapse rate. The README explicitly acknowledges this: "No temporal trajectory validation: EPI compresses multi-year dynamics into a single number."

**What would be needed**:
- A `TemporalBenchmark` class that takes agent-level time series and computes autocorrelation, transition matrices, or survival curves
- Benchmarks like `savings_persistence_rate`, `default_recovery_half_life`, `wealth_mobility_matrix_distance`
- The `BenchmarkRegistry` already supports registering new benchmarks, so the extension mechanism is there

### 7. Reviewer Pushback: #1 Concern (Score: N/A)

**My #1 concern as a reviewer: The CACR metric is circular and the paper does not adequately address this.**

Here is the problem. The LLM generates both the construct labels (TP, CP) AND the action. CACR checks whether these are consistent with each other. But if the LLM is internally consistent (it says "high threat" and then acts protectively), CACR will be high -- even if the LLM's assessment of "high threat" is completely wrong given the agent's actual situation.

The README acknowledges this in "Known Limitations" item #1: "CACR checks whether LLM-generated TP/CP labels are consistent with actions = self-consistency, not construct validity." But then it does nothing about it. There is no "construct grounding" validation that checks whether the LLM's TP label correctly reflects the agent's actual flood risk.

**Why this matters for financial ABMs**: If an LLM says "high loss aversion" for a wealthy agent and then makes a risk-averse decision, CACR scores this as coherent. But wealthy agents empirically have *lower* loss aversion (Kahneman & Deaton 2010). The LLM could be consistently wrong in a way that inflates CACR.

**What I would require for publication**:
1. A "construct grounding" analysis: Do LLM-generated TP labels correlate with actual flood zone, flood history, and income? (This is partially addressed by L3 ICC/eta-squared, but not at the decision level.)
2. An adversarial test: Provide agents with objectively low-risk profiles and check whether the LLM still sometimes assigns high TP. If CACR is high AND construct grounding is strong, *then* the validation is convincing.
3. Explicit acknowledgment that CACR measures self-consistency, not validity, with a defense of why self-consistency is still useful (e.g., it rules out random/incoherent behavior).

---

## Summary Scorecard

| Dimension | Score | Key Issue |
|-----------|-------|-----------|
| 1. Prospect Theory Fit | 2/5 | Protocol assumes lookup tables; PT needs continuous coherence |
| 2. Rich Historical Data | 2/5 | Binary in/out benchmarks; no CI, point estimate, or z-score support |
| 3. Scale (10K agents) | 4/5 | O(n) everywhere; works fine up to ~500K traces |
| 4. Distributional Validation | 2/5 | Rate-only benchmarks; no Gini, KS, Wasserstein |
| 5. Sycophancy/LLM Bias | 3/5 | Positional bias + framing tests exist; no sycophancy or anchoring tests |
| 6. Temporal Dynamics | 2/5 | Only insurance lapse; no wealth trajectories, debt spirals, transition matrices |
| 7. Reviewer Concern | -- | CACR circularity: self-consistency != construct validity |

**Overall: 3.4 / 5.0** (weighted toward Dimensions 1, 4, 6 which are most critical for financial ABMs)

---

## Recommendations for the Authors

### High Priority (for paper acceptance)
1. **Address CACR circularity head-on**: Add a "construct grounding" analysis showing that LLM-generated construct labels correlate with objective agent characteristics. Even a simple correlation table (TP vs. flood zone, CP vs. income) would significantly strengthen the paper.
2. **Acknowledge Paradigm B as aspirational**: Do not claim Prospect Theory support until `get_coherent_actions()` supports continuous coherence scoring. The current Protocol interface is Paradigm A only.

### Medium Priority (for framework adoption by financial ABM community)
3. **Extend BenchmarkRegistry return type**: Support `BenchmarkResult` objects with simulated value, distance metric, and p-value. This unlocks CI-based validation for data-rich domains.
4. **Add distributional benchmark examples**: Register a `wealth_gini` benchmark to demonstrate that the registry can handle non-rate metrics.
5. **Add temporal benchmark class**: Even one example (e.g., wealth mobility matrix comparison) would show the framework can handle path-dependent validation.

### Lower Priority (future work)
6. **Sycophancy test suite**: Design a standard sycophancy battery for financial prompts (anchoring, loss/gain framing, authority suggestion).
7. **Streaming TraceReader**: Implement Phase 5 of the evolution plan before advertising 10K+ agent support.

---

## Would I Use This Framework?

**Conditionally yes.** The architecture is sound and the extension points (`BenchmarkRegistry`, `BehavioralTheory` Protocol) are well-designed. For a financial ABM using TPB or a similar Paradigm A theory, the framework would work today with moderate customization. For a Prospect Theory-based model, I would need to extend the Protocol significantly, and at that point I might be writing more custom code than framework code. The L3 cognitive validation (ICC probing) is genuinely valuable and domain-agnostic -- I would adopt that immediately.

The honest labeling of limitations in the README is appreciated and unusual for academic software. The "Known Limitations" section reads like a roadmap, not a confession, which suggests the authors intend to address these gaps.

---

*Review conducted by Dr. James Park (simulated expert persona) for the WAGF C&V Expert Review Panel, 2026-02-14.*
