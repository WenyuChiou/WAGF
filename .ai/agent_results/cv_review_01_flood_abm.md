# Expert Review: Dr. Sarah Chen -- Flood Risk ABM Validation

## Overall Score: 3.4/5.0

## Dimension Scores

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| D1. Onboarding Friction | 2.5 | No quickstart example or minimal working script; must reverse-engineer trace format from `trace_reader.py` |
| D2. Theory Pluggability | 4.5 | PMT already implemented; `BehavioralTheory` Protocol is clean and easy to subclass with custom rules |
| D3. Data Requirements | 2.0 | Trace dict schema not formally documented; field names like `skill_proposal.reasoning.TP_LABEL` are discoverable only by reading source |
| D4. Benchmark Portability | 3.5 | `BenchmarkRegistry` decorator pattern is elegant; but `EMPIRICAL_BENCHMARKS` dict and `_compute_benchmark` functions are hardcoded to flood column names |
| D5. CGR Generalizability | 2.5 | Grounding rules (`ground_tp_from_state`, `ground_cp_from_state`) are 100% flood-specific with hardcoded field names; no pluggable interface |
| D6. Null Model Validity | 3.5 | Uniform random is a reasonable lower bound for flood; would want a status-quo-biased null for more realistic baseline |
| D7. Hallucination Generality | 2.0 | `_is_hallucination()` checks only 3 flood-specific conditions; no protocol/interface for domain-specific hallucination rules |
| D8. Bootstrap/CI Utility | 4.5 | Generic, well-designed; the `extractor` lambda pattern is publication-ready for any metric |
| D9. Documentation Sufficiency | 3.0 | README covers the broker-level C&V framework well; but the `validation/` package under `paper3/analysis/` has NO dedicated README or docstring-level usage guide |
| D10. Missing Capabilities | 3.0 | No temporal coherence (TCS), no distributional tests (KS/Wasserstein), no L3 psychometric integration in this package |

## Top 3 Strengths

**1. Clean Theory Abstraction (Protocol pattern).** The `BehavioralTheory` Protocol in `base.py` is the best-designed component. It uses Python's `runtime_checkable` Protocol, meaning I can implement PMT for my 500-household model without inheriting from any base class -- just match the interface. The PMT implementation already covers my use case (owners and renters with TP/CP dimensions), and I can override the rule tables via constructor injection (`PMTTheory(owner_rules=my_rules)`). The TPB and Irrigation examples in `examples.py` demonstrate that extending to 3-dimension theories or entirely different domains is straightforward. This is a genuine contribution to the LLM-ABM validation literature, where most frameworks hardcode their behavioral theory.

**2. Bootstrap CI module is publication-ready.** The `bootstrap_ci()` function in `bootstrap.py` is cleanly generic: it accepts any metric function, an optional extractor lambda, and arbitrary `**kwargs`. I could immediately use this in a Water Resources Research submission to report CACR = 0.82 [95% CI: 0.78, 0.86]. The interface is intuitive: `bootstrap_ci(traces, compute_l1_metrics, extractor=lambda m: m.cacr)`. This is a capability I would otherwise have to build from scratch.

**3. L2 Benchmark Registry with weighted EPI.** The decorator-based `BenchmarkRegistry` pattern in `registry.py` is clean engineering. The 8 flood benchmarks in `flood.py` are well-sourced (FEMA data), and the weighted EPI formula in `l2_macro.py` produces a defensible single-number plausibility score. The separation of benchmark definition (`EMPIRICAL_BENCHMARKS` dict) from computation (`@_registry.register` decorated functions) means I could, in principle, define my own benchmarks without touching the EPI logic.

## Top 3 Gaps

**1. No formal trace schema documentation.** This is the single biggest barrier to adoption. The trace dict structure is implicitly defined across `trace_reader.py`, `hallucinations/flood.py`, `cgr.py`, and `l2_macro.py`. I had to read all four files to reconstruct the expected format. This schema is nowhere written down. My FEMA survey data comes as flat CSV rows, not nested JSON dicts. I would need to write a substantial adapter layer, and I have no confidence I have identified all required fields until I hit a runtime `KeyError`.

**2. CGR and Hallucination modules are not pluggable.** The `compute_cgr()` function calls `ground_tp_from_state()` and `ground_cp_from_state()`, which are hardcoded to flood-domain variables. There is no `GroundingStrategy` protocol analogous to `BehavioralTheory`. Similarly, `_is_hallucination()` checks exactly three flood-specific conditions. The fix would be a `GroundingStrategy` protocol with `ground_constructs(state_before) -> Dict[str, str]` and a `HallucinationChecker` protocol with `is_hallucination(trace) -> bool`.

**3. L2 benchmark functions are tightly coupled to WAGF column conventions.** Every benchmark function in `flood.py` expects specific column names (`final_has_insurance`, `final_elevated`, etc.). A column-mapping dict in the API would solve this.

## Specific Recommendations (Prioritized)

**P0 (Blocking for external adoption):**
1. Write a `TRACE_SCHEMA.md` documenting every field
2. Add a `GroundingStrategy` protocol to `theories/base.py`
3. Add a `HallucinationChecker` protocol

**P1 (Important for usability):**
4. Add column-name mapping to L2 benchmarks
5. Create a `quickstart.py` example
6. Add a `compute_validation()` overload accepting `List[Dict]` directly

**P2 (Nice to have):**
7. Status-quo-biased null model
8. Port TCS and distributional tests from broker-level C&V
9. Add `summary()` methods to dataclasses

## Would You Adopt? Conditional -- Yes, with caveats.

Would adopt L1 theory-pluggable layer immediately. Would NOT adopt L2 or CGR without modification. The architectural vision is strong -- the theory-pluggable L1 layer is genuinely novel. But implementation is still 60% domain-specific (flood) and 40% generic.
