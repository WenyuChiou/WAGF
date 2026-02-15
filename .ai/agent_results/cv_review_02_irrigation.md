# Expert Review: Dr. Miguel Torres -- Agricultural Water Management ABM

## Overall Score: 3.2/5.0

## Dimension Scores

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| D1. Onboarding Friction | 2/5 | Protocol requires "construct levels" (VL/L/M/H/VH) -- assumes LLM agents produce labeled psychological constructs. Heuristic farmers don't. IrrigationWSATheory example presupposes WSA_LABEL/ACA_LABEL in prompts. |
| D2. Theory Pluggability | 3/5 | Could create a `PriceResponseTheory` with price_pressure/drought_severity mapped to ordinal levels. But "constructs" terminology is overloaded -- my dimensions are observable environmental variables, not psychological constructs. `is_sensible_action()` returning True in examples suggests nobody has thought about domain-specific "sensibility". |
| D3. Data Requirements | 2/5 | L1 requires per-agent per-decision trace dicts with `skill_proposal.reasoning` containing labeled constructs. I have USDA county-level aggregate data but no individual farmer decision traces. No guidance on bridging aggregate to trace-level format. |
| D4. Benchmark Portability | 3/5 | BenchmarkRegistry decorator pattern is clean. But flood.py hardcodes column names and engine.py imports EMPIRICAL_BENCHMARKS directly from flood -- not pluggable without code changes. |
| D5. CGR Generalizability | 1/5 | Entirely flood-specific. No protocol or base class. Would need to write grounding functions from scratch with no place to register them. |
| D6. Null Model Validity | 3/5 | Uniform random over 5 ordinal actions is reasonable starting null. But actions have ordinal structure -- random walk null would be more meaningful. Null model hardcodes flood action pools. |
| D7. Hallucination Generality | 2/5 | `_is_hallucination()` imported from flood module. No protocol or registry. Irrigation hallucinations (exceeding canal capacity, negative water) are physically-grounded, not psychological. |
| D8. Bootstrap/CI Utility | 4/5 | Well-designed, generic, immediately usable. Extractor pattern is elegant. 200 agents x 30 years = statistically meaningful. |
| D9. Documentation Sufficiency | 3/5 | broker/validators/calibration/README.md is comprehensive. But paper3 validation/ has no README. Unclear which system to use (broker-level CVRunner vs paper3-level engine.py). |
| D10. Missing Capabilities | 2/5 | Missing: temporal validation (drought response lag), spatial validation (neighbor correlation), aggregate distribution matching (KS/Wasserstein), ordinal action structure metric, multi-year trajectory validation. |

## Top 3 Strengths

1. **BehavioralTheory Protocol is genuinely extensible.** Clean abstraction with IrrigationWSATheory demonstrating non-PMT theories in ~60 lines.

2. **Bootstrap CI module is domain-agnostic and production-ready.** Immediately usable without modification.

3. **BenchmarkRegistry decorator pattern is clean engineering.** Weighted EPI computation is a sensible aggregate metric adoptable for irrigation benchmarks.

## Top 3 Gaps

1. **CGR is monolithically flood-specific with no extension point.** Needs a `ConstructGrounder` protocol.

2. **No aggregate-to-individual bridging guidance.** Most agricultural economists have county-level data, not individual traces. No guidance on ecological inference problem.

3. **Hallucination detection has no protocol or registry.** Hard dependency on flood module in l1_micro.py.

## Specific Recommendations

1. Create `ConstructGrounder` Protocol in `theories/base.py`
2. Create `HallucinationDetector` Protocol, make `compute_l1_metrics()` accept it
3. Decouple `engine.py` from flood-specific imports (accept benchmarks/hallucination_detector as params)
4. Add `OrdinalCoherenceMetric` that uses action ordering (near-miss vs gross-miss)
5. Add `TrajectoryValidator` for time-series comparison (DTW, RMSE, correlation)
6. Document the two-system relationship (broker-level vs paper3-level)

## Would You Adopt? Conditional

Yes if recommendations 1-3 implemented. Current adoption requires ~430 lines of new code + forking engine.py. With protocol changes, reduces to ~280 lines with zero forking.
