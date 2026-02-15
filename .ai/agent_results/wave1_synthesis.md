# Wave 1 Synthesis: 6 Domain Expert Reviews of C&V Module

**Date**: 2026-02-14
**Module**: `examples/multi_agent/flood/paper3/analysis/validation/`

## Overall Scores

| Expert | Domain | Score | Would Adopt? |
|--------|--------|-------|--------------|
| Dr. Sarah Chen | Flood Risk ABM | 3.4/5.0 | Conditional — L1 immediately, L2/CGR after mods |
| Dr. Miguel Torres | Irrigation/Agriculture | 3.2/5.0 | Conditional — need GroundingStrategy + HallucinationChecker protocols |
| Dr. Priya Sharma | Financial Behavior | 3.3/5.0 | Conditional — need continuous theory (Paradigm B) support |
| Dr. James Okonkwo | Education/Learning | 3.8/5.0 | Yes partially — L2+null-model immediately, skip CGR |
| Dr. Anna Petrov | Epidemiology/Health | 3.5/5.0 | Yes adopt+extend — invest 3-4 months |
| Dr. Kenji Tanaka | Urban Mobility | 2.9/5.0 | Partially — ~40% usable, ~40% inapplicable |
| **Mean** | | **3.35/5.0** | |

## Consensus Strengths (All 6 experts agree)

1. **BehavioralTheory Protocol design** — runtime_checkable Protocol is the right abstraction; clean, extensible, no inheritance required
2. **Bootstrap CI module** — fully generic, publication-ready, immediately usable in any domain
3. **BenchmarkRegistry + weighted EPI** — decorator pattern is clean engineering; weighted EPI is defensible single-number metric

## Consensus Gaps (≥4/6 experts flagged)

### GAP 1: No Temporal Validation (flagged by 5/6)
- Epidemiology: epidemic curves are THE primary observable
- Urban Mobility: policy-response patterns over time (e.g., congestion pricing → transit share increase)
- Education: behavior trajectories over semesters
- Finance: autocorrelation, volatility clustering
- **Only flood has partial coverage** (year-over-year rates)

### GAP 2: CGR Not Pluggable (flagged by 5/6)
- Hardcoded flood-specific grounding rules
- No `GroundingStrategy` protocol analogous to `BehavioralTheory`
- Agriculture: environmental variables, not psychological constructs
- Finance: continuous grounding (reference points, value functions)
- Education: constructs lack environmental correlates — must skip CGR entirely

### GAP 3: Hallucination Detection Hardcoded (flagged by 5/6)
- `_is_hallucination()` imported from flood module
- No `HallucinationChecker` protocol or registry
- Each domain has distinct hallucination types (physical impossibility vs. institutional violation vs. behavioral implausibility)

### GAP 4: Only Paradigm A Supported (flagged by 4/6)
- Protocol assumes `Dict[str, str]` discrete construct levels
- Prospect Theory, SDT, HBM (6 constructs) cannot fit cleanly
- Need: `ContinuousBehavioralTheory` with probability distributions over actions
- Need: continuous coherence scoring (KL-divergence instead of set membership)

### GAP 5: Null Model Uniform-Only (flagged by 4/6)
- Uniform random over actions is meaningless for skewed distributions (drive_alone=76%)
- Need custom probability distributions or "frozen baseline" null
- Finance: need zero-intelligence traders, not random action sampling
- Epidemiology: need noise/momentum nulls

### GAP 6: No Trace Schema Documentation (flagged by 3/6)
- Trace dict structure discoverable only by reading source
- No `TRACE_SCHEMA.md`
- Each adopter must reverse-engineer the expected format

### GAP 7: No Ensemble Aggregation (flagged by 3/6)
- Single-seed validation is non-publishable in epidemiology/stochastic domains
- Need `compute_ensemble_validation()` with multi-seed CI

## Dimension Score Heatmap

| Dimension | Flood | Irrig | Fin | Edu | Epi | Urban | Mean |
|-----------|-------|-------|-----|-----|-----|-------|------|
| Theory Protocol | 4.5 | 3 | 2.5 | 4 | 3 | 3 | 3.3 |
| Benchmark/EPI | 3.5 | 3 | 4 | 4 | 3 | 4 | 3.6 |
| CGR/Grounding | 2.5 | 1 | 3 | 3 | 2 | 2 | 2.3 |
| Hallucination | 2 | 2 | — | 4 | 3 | 2 | 2.6 |
| Null Model | 3.5 | 3 | 3.5 | — | 3 | 2 | 3.0 |
| Temporal | — | 2 | — | — | 1 | 1 | 1.3 |
| Bootstrap/Stats | 4.5 | 4 | 4.5 | 4 | 3 | 4 | 4.0 |
| Documentation | 3 | 3 | 3.5 | 4 | 4 | 4 | 3.6 |

**Strongest**: Bootstrap/Stats (4.0), Benchmark/EPI (3.6), Documentation (3.6)
**Weakest**: Temporal (1.3), CGR/Grounding (2.3), Hallucination (2.6)

## Adoption Barrier Analysis

| Barrier | Domains Affected | Fix Complexity |
|---------|-----------------|----------------|
| No temporal benchmarks | Epi, Urban, Edu, Fin | 2-3 weeks |
| CGR not pluggable | All non-flood | 1 week (protocol only) |
| Hallucination not pluggable | All non-flood | 1 week (protocol only) |
| Paradigm B not implemented | Fin, Edu, Urban | 2-3 weeks |
| No ensemble aggregation | Epi, stochastic ABMs | 2 weeks |
| Null model too simple | Urban, Fin | 1 week |
| No trace schema docs | All new adopters | 2-3 days |

## Key Insight: Theory vs. Architecture Gap

The **architecture** scores consistently high (Protocol design, Registry pattern, Bootstrap).
The **implementation** scores low (flood-specific coupling, missing protocols, incomplete Paradigm B).

This means the framework's DESIGN is already universal — the CODE is not yet.
Wave 2 technical experts should evaluate: what minimal code changes close this gap?
