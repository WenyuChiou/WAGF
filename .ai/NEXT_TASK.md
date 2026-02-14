# Next Task

## Immediate: Commit P0 fixes + README updates
Files to commit:
- `examples/multi_agent/flood/paper3/analysis/compute_validation_metrics.py` (3 P0 bug fixes)
- `examples/multi_agent/flood/paper3/analysis/README.md` (EN, aligned with ZH)
- `examples/multi_agent/flood/paper3/analysis/README_CV_zh.md` (ZH, updated)

## Then: C&V Module Refactoring (Phase 1-5)
See expert review Word doc and READMEs for full plan.
Priority order:
1. Phase 1: Externalize PMT rules and benchmarks to YAML
2. Phase 2: Split monolith into sub-modules
3. Phase 3: BehavioralTheory protocol + TheoryRegistry
4. Phase 4: BenchmarkComputation plugins
5. Phase 5: Streaming TraceReader + ValidationRunner facade

## Blocked: Re-run flood experiment with elevation prompt fix
- Need gemma to be free
- Will verify elevation_rate drops below 0.35 with new prompt (commit 7f92e7e)
