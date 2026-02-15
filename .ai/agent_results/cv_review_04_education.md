# Expert Review: Dr. James Okonkwo — Education / LLM-Based Student Learning ABMs

## Overall Score: 3.8/5.0

## Domain Context
300 students, 5 actions (study_hard, study_moderate, seek_help, skip_class, collaborate), 4 semesters. Self-Determination Theory (SDT) with 3 continuous needs: autonomy, competence, relatedness. NO individual longitudinal data — only cross-sectional surveys (NSSE) and aggregate education statistics.

## Dimension Scores

| Dimension | Score | Key Issue for Education Domain |
|-----------|-------|-------------------------------|
| D1. Theoretical Soundness | 4/5 | Assumes categorical construct-action mappings; SDT predicts probabilistic tendencies |
| D2. Generalizability | 3/5 | ~60% reusable; CGR and continuous constructs are blockers |
| D3. Metric Completeness | 4/5 | Missing temporal trajectory and network-level validation |
| D4. Empirical Grounding | 3/5 | L1 thresholds lack formal derivation; education benchmarks exist but are wider |
| D5. LLM Artifact Handling | 4/5 | Good coverage; missing anchoring bias detection |
| D6. Scalability | 4/5 | Three-stage protocol is practical for education scale |
| D7. Statistical Rigor | 4/5 | Binary EPI discards deviation magnitude information |
| D8. Transparency | 5/5 | Excellent: deterministic, auditable, JSON/CSV outputs |
| D9. Extensibility | 3/5 | Protocol assumes string constructs; CGR not pluggable |
| D10. Documentation | 4/5 | Missing "when to use which metric" guidance |

## Key Findings

### Can SDT fit the BehavioralTheory protocol?
**Partially, with significant friction.** SDT has 3 continuous dimensions → would need a 5x5x5=125-cell lookup table that is theoretically unjustified. Nobody has validated 125 SDT construct-action rules. SDT predicts *quality of motivation* (intrinsic vs extrinsic vs amotivation), not deterministic actions.

**Need "Paradigm C"**: continuous construct scores with probabilistic action tendencies rather than categorical lookup tables.

### Without historical data, what validates at L2?
Can use aggregate statistics as benchmarks: graduation rate [0.55-0.65], mean GPA [2.8-3.2], retention [0.70-0.80], help-seeking [0.20-0.40]. BenchmarkRegistry handles this. But these are *outcome* statistics, not *behavioral process* rates.

### Is CGR useful without objective grounding?
**No — sharpest limitation.** Cannot write `ground_autonomy_from_state()` with theoretical justification. Autonomy/relatedness are fundamentally internal states without environmental correlates. Must skip CGR entirely and rely on L3 psychometric probing as circularity check.

### What counts as hallucination in education?
- **Structural impossibility**: graduated student enrolling in first-year courses ✓
- **Psychological implausibility**: amotivated student choosing study_hard — fuzzy boundary
- **Institutional violations**: suspended student enrolling in classes ✓
R_H works for structural impossibilities only; the interesting validation is CACR, not R_H.

## Top 3 Strengths
1. **Multi-level hierarchy (L1/L2/L3)** is well-motivated by Grimm et al. (2005)
2. **Transparency and reproducibility** — deterministic, seeded, JSON/CSV audit trail
3. **Null-model significance testing** — domain-agnostic, immediately usable

## Top 3 Gaps
1. **Protocol forecloses continuous constructs** — `Dict[str, str]` cannot express SDT scores
2. **CGR is not pluggable** and inapplicable when constructs lack environmental correlates
3. **Binary EPI** discards how far values are from boundaries — continuous scoring would be more useful

## Specific Recommendations
1. Add "Paradigm C" to BehavioralTheory: `get_coherent_actions` returns `Dict[str, float]` (probability distribution)
2. Make CGR pluggable with `GroundingFunction` protocol; document "skip CGR" guidance for non-groundable domains
3. Add continuous EPI scoring (trapezoidal membership function instead of binary pass/fail)
4. Document metric applicability matrix: which metrics need which preconditions
5. Add temporal trajectory validation at L2 (behavior curves over time, not just aggregate rates)

## Would You Adopt?
**Yes, partially.** Would adopt L2 benchmarking + null-model immediately. Use discretized approximation for L1 CACR temporarily. Skip CGR entirely. Invest in L3 psychometric probing as primary circularity check. Framework gets ~60% of the way there — far better than from scratch, but remaining 40% is the hard part.
