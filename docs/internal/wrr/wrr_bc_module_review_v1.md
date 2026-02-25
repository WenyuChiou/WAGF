# WRR B/C Module Review (Log-Deep Audit v1)

## Reviewer-Critical Findings
- Blocking: current audit trace field `memory_audit.retrieval_mode` is not reliable for B vs C attribution; in code it is hardcoded to `"humancentric"` when `memory_pre` is non-empty (`broker/core/skill_broker_engine.py`).
- Confirmed: Group C has reflection integration signal; rows with `"Consolidated Reflection:"` in `memory_pre` are 11,174/12,575 (88.86%), Group B is 0/12,415 (0.00%).
- Process-level pattern (all available runs): Group C shows lower retry burden and lower rejection rate than Group B in aggregate, but pairwise model-run differences are mixed; this is supportive but not decisive causal evidence.

## Aggregate Process Snapshot (from traces)
- Group B: retry-positive rate mean = 6.79%, mean retry count = 0.0938, approved rate = 93.21%, rejected rate = 0.3377%.
- Group C: retry-positive rate mean = 4.74%, mean retry count = 0.0624, approved rate = 95.26%, rejected rate = 0.2072%.

## Year-Stratified B vs C
- Years 1-8: C has consistently lower retry-positive rate than B.
- Years 9-10: C is slightly higher than B, so effect is not monotonic.
- File: `docs/wrr_bc_yearly_process_compare_v1.csv`.

## Suggested Manuscript Direction
- Keep primary claim as Governance effectiveness (A vs B/C) on executed irrationality reduction + diversity retention.
- Reframe memory/reflection as process-quality module: reduced intervention burden and richer contextual continuity, not guaranteed universal gain on all outcome metrics.
- Add balanced SI evidence: include both improvement and regression paired cases (same model/run/agent/year) from `docs/wrr_bc_case_examples_v1.csv`.
- Add a limitation sentence: current B/C contrast is partially confounded by audit instrumentation and uneven run completion.

## Data Sources
- `docs/wrr_process_audit_by_run_v1.csv`
- `docs/wrr_process_audit_group_summary_v1.csv`
- `docs/wrr_bc_yearly_process_compare_v1.csv`
- `docs/wrr_bc_case_examples_v1.csv`