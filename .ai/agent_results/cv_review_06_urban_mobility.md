# Expert Review: Dr. Kenji Tanaka — Urban Mobility ABM

## Overall Score: 2.9/5.0

## Domain Context
2000 commuters, 6 modes (drive_alone, carpool, public_transit, bike, walk, work_from_home), 5 years, NO formal psychological theory. Agents reason via natural language about cost/time/convenience/social norms. Has ACS mode share data and transit ridership records.

## Dimension Scores

| Dimension | Score | Key Issue |
|-----------|-------|-----------|
| D1: Theoretical Flexibility | 3/5 | Protocol assumes construct labels exist; feasibility-as-coherence is a semantic stretch |
| D2: Metric Extensibility | 4/5 | Registry pattern is clean; new metric *types* need structural changes |
| D3: Benchmark Specification | 4/5 | Range/weight format works well; no temporal dimension |
| D4: Hallucination Detection | 2/5 | Hardcoded domain-specific import; no abstract protocol |
| D5: Null Model Design | 2/5 | Uniform random is wrong baseline for skewed distributions |
| D6: Temporal Validation | 1/5 | No mechanism for policy-response temporal benchmarks |
| D7: Multi-Agent-Type Support | 3/5 | Protocol supports it; engine hardcodes owner/renter |
| D8: Documentation Quality | 4/5 | Broker README excellent; Paper 3 module less documented |
| D9: Statistical Rigor | 4/5 | Bootstrap, kappa, p-value correction all sound |
| D10: Overall Usability (Theory-Free) | 2/5 | ~40% directly usable, ~40% inapplicable |

## Key Findings

### Without theory, can CACR be used?
**No as designed.** Could define `MobilityFeasibilityTheory` where coherence = feasibility (no car → can't drive), but this is a **different claim** than PMT's psychological coherence. Framework doesn't signal this distinction.

### L2 Benchmarks from ACS?
**Yes, strongest part.** Mode share ranges map directly to BenchmarkRegistry format. Weighted EPI works identically.

### CGR?
**Entirely inapplicable.** No psychological constructs to ground. Needs replacement: "Decision Grounding Rate" checking if agent correctly perceived numeric context (bus schedule, parking cost).

### Temporal validation?
**Largest gap (1/5).** "After congestion pricing, transit share should increase 10-15%" is the primary validation target for policy ABMs. Framework cannot express or evaluate this.

### Null model?
**Wrong baseline.** Uniform over 6 modes gives 16.7% each; observed is drive_alone=76%, transit=5%. Trivially easy to beat. Need custom probability distributions or "frozen baseline" null.

## Top 3 Strengths
1. **BenchmarkRegistry + weighted EPI** — directly applicable to ACS mode share targets
2. **Bootstrap CI** — fully generic, immediately usable
3. **Documentation quality** — broker README is comprehensive with integration guide

## Top 3 Gaps
1. **No temporal validation** — can't validate policy-response patterns over time
2. **Null model assumes uniform random** — meaningless for skewed distributions
3. **Hallucination detection not pluggable** — hardcoded flood import, no protocol

## Specific Recommendations
1. Add `FeasibilityTheory` alongside `BehavioralTheory` — coherence as physical possibility, not psychology
2. Add `TemporalBenchmark` with trigger_condition, pre/post period, expected direction/magnitude
3. Make null model accept custom `action_weights: Dict[str, float]` for non-uniform sampling

## Would You Adopt?
**Partially.** ~40% directly usable (L2 benchmarks, EBE, bootstrap). ~40% inapplicable (CACR, CGR, hallucination). Critical missing piece is temporal validation for policy ABMs.
