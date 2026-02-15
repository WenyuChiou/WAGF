# Expert Review: Dr. Anna Petrov — Epidemiology / Health Behavior ABM

## Overall Score: 3.5/5.0

## Domain Context
1000 individuals, 6 actions (vaccinate, mask, social_distance, quarantine, seek_testing, do_nothing), 52 weeks. Health Belief Model (HBM) with 6 constructs: perceived susceptibility, severity, benefits, barriers, cues to action, self-efficacy. Has CDC county-level vaccination data + epidemic curves.

## Dimension Scores

| Dimension | Score | Key Issue |
|-----------|-------|-----------|
| D1: Theoretical Flexibility | 3/5 | Protocol handles HBM but 6D → 15,625 cell lookup table is impractical; needs hierarchical collapse guidance |
| D2: Metric Extensibility | 4/5 | Registry pattern is clean; time-series benchmarks (epidemic curves) are missing |
| D3: Benchmark Specification | 3/5 | Scalar rates work (vaccination coverage); no DTW/curve-fitting for temporal trajectories |
| D4: Hallucination Detection | 3/5 | Structural impossibilities detectable; behavioral contagion without network proximity = new hallucination class |
| D5: Null Model Design | 3/5 | Uniform random is lowest-tier null; needs zero-intelligence + noise trader equivalents for health |
| D6: Temporal Validation | 1/5 | Epidemic curve shape is the PRIMARY observable — framework cannot validate temporal patterns |
| D7: Multi-Agent-Type Support | 4/5 | Protocol supports arbitrary agent types; could model age groups, risk categories |
| D8: Documentation Quality | 4/5 | Broker README thorough; HBM integration path undocumented |
| D9: Statistical Rigor | 3/5 | Single-seed validation is non-starter for epidemiology; needs ensemble aggregation (50+ seeds with CI) |
| D10: Network Validation | 2/5 | Zero network infrastructure; disease transmission is fundamentally network-driven |

## Key Findings

### Can HBM fit the BehavioralTheory protocol?
**Yes, with hierarchical collapse.** Collapse 6D into 2-3 effective dimensions: (susceptibility + severity → threat), (benefits - barriers → net_evaluation), (self-efficacy as modifier). Protocol allows this but examples push toward flat lookup tables.

### L2 Benchmarks from CDC data?
**Yes for scalar rates.** Vaccination coverage ranges map directly to BenchmarkRegistry. But epidemic CURVES (S-shaped adoption trajectories) are the primary validation target — framework cannot express these.

### Ensemble validation?
**Largest gap for epidemiology (single-seed = non-publishable).** Need `compute_ensemble_validation(traces_dirs: List[Path], ...)` returning mean/CI for all metrics across 50+ seeds. Model passes if lower CI bound exceeds threshold.

### Network effects?
**Critical gap.** Network position stronger predictor of vaccination timing than individual beliefs (Centola 2010). Network-conditioned CACR (coherence stratified by neighborhood vaccination rate) is essential.

## Top 3 Strengths
1. **Three-level validation hierarchy (L1/L2/L3)** mirrors multi-scale validation epidemiology needs
2. **Graceful degradation** — with no data, L1+L3 still validate theory-consistency
3. **CACR decomposition (raw vs. governance-filtered)** addresses "constrained RNG" critique

## Top 3 Gaps
1. **No temporal validation** — epidemic curve shape is THE primary observable
2. **No ensemble aggregation** — single-seed results are unpublishable in epidemiology
3. **No network validation** — behavioral contagion and disease transmission are network phenomena

## Specific Recommendations
1. Add `TemporalBenchmark` with DTW distance between simulated and observed curves
2. Add `compute_ensemble_validation()` for multi-seed aggregation with CI
3. Document hierarchical construct collapse pattern for high-dimensional theories (HBM, TPB)
4. Add network-conditioned CACR: stratify coherence by neighborhood state
5. Generalize benchmark dispatch signature: `(df, traces, **domain_context)` instead of flood-specific params

## Would You Adopt?
**Yes, adopt and extend.** The architectural decisions are sound. Would invest 3-4 months extending with ensemble aggregation, time-series benchmarks, and network metrics. CACR decomposition methodology alone strengthens any LLM-ABM paper's methods section. Framework gets ~60% of the way there — far better than building from scratch.
