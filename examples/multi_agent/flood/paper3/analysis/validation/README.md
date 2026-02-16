# C&V Validation Package

Modular validation framework for LLM-ABMs implementing the
L0→L1→L2→L3→L4 validation hierarchy.

## Quick Start

```python
from validation import compute_validation

report = compute_validation(
    traces_dir=Path("results/seed_42"),
    agent_profiles_path=Path("data/agent_profiles.csv"),
    output_dir=Path("results/validation"),
)
print(f"Pass: {report.pass_all}, EPI: {report.l2.epi}")
```

## Package Structure

```
validation/
├── __init__.py              # Public API exports
├── engine.py                # Main pipeline (compute_validation, load_traces)
├── EXTENDING.md             # Guide: extending to new domains
├── TRACE_SCHEMA.md          # Trace dict field reference
├── README.md                # This file
│
├── theories/                # BehavioralTheory protocol
│   ├── base.py              #   Protocol definition
│   └── pmt.py               #   PMT implementation (flood)
│
├── hallucinations/          # HallucinationChecker protocol
│   ├── base.py              #   Protocol + NullChecker
│   └── flood.py             #   Flood-specific rules
│
├── grounding/               # GroundingStrategy protocol
│   ├── base.py              #   Protocol definition
│   └── flood.py             #   Flood PMT grounding
│
├── benchmarks/              # L2 empirical benchmarks
│   ├── registry.py          #   BenchmarkRegistry (decorator dispatch)
│   └── flood.py             #   8 flood benchmarks + EMPIRICAL_BENCHMARKS
│
├── metrics/                 # Metric computations
│   ├── l1_micro.py          #   CACR, R_H, EBE, CACRDecomposition
│   ├── l2_macro.py          #   EPI, benchmark scoring
│   ├── cgr.py               #   Construct Grounding Rate
│   ├── entropy.py           #   Shannon entropy
│   ├── bootstrap.py         #   Bootstrap confidence intervals
│   └── null_model.py        #   Null-model EPI distribution
│
├── io/                      # Data I/O
│   ├── trace_reader.py      #   Action normalization, TP/CP extraction
│   └── state_inference.py   #   Decision-based state inference
│
└── reporting/               # Output formatting
    └── report_builder.py    #   ValidationReport, JSON serialization
```

## Validation Levels

| Level | What | Key Metrics | Threshold |
|-------|------|-------------|-----------|
| L1 Micro | Per-decision quality | CACR ≥ 0.75, R_H ≤ 0.10, 0.1 < EBE ratio < 0.9 | All three |
| L1+ | Governance decomposition | CACR_raw, retry_rate, fallback_rate | Informational |
| CGR | Construct grounding | CGR_TP, CGR_CP, weighted + unweighted Kappa | Informational |
| L2 Macro | Population plausibility | EPI ≥ 0.60 (weighted benchmark score) | EPI |
| L3 | Cognitive consistency | ICC(2,1) ≥ 0.60, eta² ≥ 0.25 | Both |

## 4 Extension Protocols

The package is designed for cross-domain use. Any domain can plug in by
implementing these protocols:

1. **BehavioralTheory** (`theories/base.py`) — construct-action coherence rules
2. **HallucinationChecker** (`hallucinations/base.py`) — impossible action detection
3. **GroundingStrategy** (`grounding/base.py`) — objective construct derivation
4. **Benchmark functions** (`benchmarks/registry.py`) — domain-specific L2 benchmarks

Plus 6 configurable parameters (action aliases, state rules, trace patterns,
action space size, hazard function, benchmark definitions) — all with
backward-compatible flood defaults.

See **[EXTENDING.md](EXTENDING.md)** for the full domain extension guide with
irrigation examples. See **[TRACE_SCHEMA.md](TRACE_SCHEMA.md)** for the
complete trace dict field reference.

## Architecture Evolution

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0: Extract to package | Complete | Monolith → 7 sub-packages |
| Phase 1: Protocol interfaces | Complete | 4 Protocols (BehavioralTheory, HallucinationChecker, GroundingStrategy, BenchmarkRegistry) |
| Phase 2: P0/P1 fixes | Complete | CGR, Null Model, Bootstrap CI, Benchmark sync |
| Phase 3: Cross-domain generalization | Complete | 6 configurable extension points, EXTENDING.md |

## Known Limitations

1. **L0 (documentation audit)** uses keyword matching — not semantic analysis. May miss rephrased content. See `metrics/l0_audit.py`.
2. **L4 (meta-validation)** uses Wasserstein-1 on categorical distributions. Requires empirical reference data for meaningful comparison. See `metrics/l4_meta.py`.
3. **Sycophancy testing** provides probe framework but requires LLM inference loop (external). See `metrics/sycophancy.py`.
4. **State inference** uses rule-based approach (configurable via `state_rules`) — more complex domains may need custom inference functions.

## Tests

```bash
# All validation tests (264+)
python -m pytest examples/multi_agent/flood/paper3/tests/ -v

# Broker-level CV tests
python -m pytest tests/test_cv_psychometric.py tests/test_cv_router.py -v
```
