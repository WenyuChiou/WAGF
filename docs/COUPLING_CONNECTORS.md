# Coupling Connectors — plugging external models into WAGF

How to host a NEW external model behind `broker/coupling/` (2026-06-10
env-layer review). The binding surface a connector implements is small:
`run_pipeline` / `commit_world_delta` on an `InterfaceBundle` subclass (plus
optional duck-typed `get_provenance`). The typed sub-protocols
(ExposureUpdater / VulnerabilityModel / FinancialLedger) are optional
vocabulary used by the catastrophe family — no generic code consumes them.

Everything below inherits for free from `EnvironmentCouplingAdapter`:
contract checks #1/#2 at construction, runtime observation validation,
commit brackets (#1/#3 + the execution-sampling guard), `world_delta` audit
payload (JSONL + key-gated `world_*` CSV columns), and manifest provenance
(`coupling_provenance`). Wire via `ExperimentBuilder.with_coupling(contract,
bundle, domain=...)` — flag-gated, default OFF.

## The four connector archetypes

### A. BMI/CSDMS numerical solver — READY
Wrap the model: `BmiEventSource(bmi, value_var, unit, threshold)` for
event-style coupling, or `ContinuousBundle(contract=..., solver=...)` for
K-sub-step control (declared `observation_reduce` roll-ups; write-back via
`BmiControlSink` → `set_value`). Worked example: `examples/cat_model/
bmi_flood_model.py` (toy, no bmipy dependency) + `broker/tests/
test_continuous_coupling.py` (toy reservoir).
**Known limit**: `BmiEventSource._scalar` accepts only 1-element arrays and
`intensity_at` ignores `agent_id` — a GRIDDED model needs a researcher-written
grid→agent projection (subclass `intensity_at`; see the MA cat zone-multiplier
source for the per-agent pattern).

### B. File-replay driver (scenario CSVs / traces) — READY by copying
`examples/cat_model/coupling_modules.py::FloodFootprintSource` IS this
archetype: a period→value table implementing `draw_events / intensity_at /
units` (~30 lines), provenance = sha256 of the forcing table (a file hash
drops in identically). Multi-variable traces: pack them into `Event.payload`.
A CONTINUOUS replay (no events): implement the four BMI verbs over your file
(~15 lines) and feed `ContinuousBundle`.

### C. Service model (REST / subprocess) — one rule to respect
The Protocols fit (an `EventSource` whose `draw_events` calls HTTP); put
`{"endpoint": ..., "model_version": ...}` in `get_provenance`. THE RULE:
`VarSpec.on_missing` accepts only `fail_loud` — `last_good` / `quarantine`
are REJECTED at construction because no runtime executor exists (a policy
you can write but that silently doesn't run is the worst failure class in
this repo). A flaky endpoint needs YOUR retry/cache INSIDE the source;
mid-run failures then surface as `CouplingViolation`, loudly.

### D. Another ABM, two-way — READY for period-lagged exchange
Pass the external ABM as `real_engine` (the adapter pumps it once per period
via `advance_step`); WAGF decisions flow through the PURE-COMMITTER
`execute_skill` into `commit_world_delta`, mutate external state, and are
read back next period. **The cadence is one env snapshot per period** —
same-period reaction loops are out of scope by design.
THE CANONICAL PATTERN (period-lagged, settle-at-period-end — from the MA cat
model): accumulate agent intents in the bundle during phases; mutate the
shared world ONCE at period end via an order-independent resolver
(`PortfolioLedger.settle` pro-rata is the reference); guard AGGREGATES with
an ERROR validator (e.g. `pool_insolvent_aggregate`) instead of letting N
individually-valid commits jointly overdraw; project the settlement summary
into NEXT period's env. If your research question needs within-period
feedback, that is a different framework regime, not a missing WAGF feature.

## Two models at once
One bundle per adapter, one `event_src` slot — compose INSIDE one bundle:
`run_pipeline` pumps both models and merges their env projections; contract
checks operate on the merged env unchanged; report both identities in
`bundle_provenance`. Worth this paragraph, not worth an orchestrator.

## What NOT to build (review-confirmed)
Connector SDK / per-archetype base classes (each is ≤30 lines over existing
Protocols) · async/retry REST adapter (no consumer exists) · model registry /
plugin discovery · YAML contract DSL (`contract.py` already keeps
enum-strings so YAML loading later needs zero machinery) · multi-bundle
orchestrator · a generic grid→agent mapper in broker/ (build it in the first
spatial example) · `ramp`/`rate` hold-policy executors before a real domain
needs them.
