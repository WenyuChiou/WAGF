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

### C. Service model (REST / subprocess) — SUBPROCESS ready, REST deferred
(PR-9 coupling-retrofit, finding F2: this section previously described the
pattern with zero shipped code. `broker.coupling.SubprocessModelConnector`
closes the subprocess half.)

**Subprocess — READY.** `SubprocessModelConnector(command, contract=...,
value_var=..., timeout_sec=...)` (`broker/coupling/subprocess_source.py`)
drives an external process once per period: JSON on stdin
(`{"period": <int>}`), one JSON object back on stdout, exit 0 required. The
reply is validated against `contract.observations` with the same fail-loud
+ range-check logic `EnvironmentCouplingAdapter` uses; a non-zero exit, a
timeout, or a non-JSON/wrong-shape reply all raise `CouplingViolation`
(the last two carry the exit code / stderr tail / wall time so the failure
is diagnosable without re-running the process by hand). Worked example:
`examples/coupling_examples/archetype_c_subprocess/` (a governed
single-agent run driving a real ~25-line subprocess "sensor" model,
`--model mock`, completes in under 4 seconds).

**REST — still deferred, and here is why.** No first-party domain needs
one yet (the same "no consumer exists" reasoning the "What NOT to build"
list below already applied to an async/retry REST adapter), and an HTTP
client adds a real dependency + auth/retry surface that would ship
untested against any actual endpoint. The Protocol fit is unchanged from
before this PR: an `EventSource` whose `draw_events` calls `requests.get`
(or your HTTP client of choice) instead of `subprocess.run`, put
`{"endpoint": ..., "model_version": ...}` in `get_provenance`, same
fail-loud discipline. When a domain needs it, copy
`subprocess_source.py`'s validation logic (`_guard_reply`) rather than
reinventing it — the reply-checking code is transport-agnostic already.

**THE RULE, either transport:** `VarSpec.on_missing` accepts only
`fail_loud` — `last_good` / `quarantine` are REJECTED at construction
because no runtime executor exists (a policy you can write but that
silently doesn't run is the worst failure class in this repo). A flaky
endpoint or subprocess needs YOUR retry/cache INSIDE the source; mid-run
failures then surface as `CouplingViolation`, loudly.

**What the guard on this path DOES and DOES NOT check.** Archetype C runs
two of the four numerical-correctness checks, not four — say so in a paper
rather than crediting the whole set:

| When | What is enforced | By |
|---|---|---|
| Contract construction | check #3 direction (observations must be `world_to_agent`) and check #4 double-count (one `consumer_of_record` per quantity) | `CouplingContract.__post_init__` |
| Contract construction | a numeric variable declares a non-empty unit; `lo <= hi` | `VarSpec.__post_init__` |
| Every call, per declared observation | presence (`on_missing="fail_loud"`), then finite (no NaN/±inf), inside `[lo, hi]`, and of the declared dtype (a bool or a `"55"` in a numeric slot is refused, not coerced) | `VarSpec.range_violation`, via `_guard_reply` |
| Every call, whole reply | `NaN` / `Infinity` / `-Infinity` tokens refused at parse time; non-JSON, non-object, non-zero exit and timeout refused | `SubprocessModelConnector.draw_events` |

NOT checked at any point on this path: `check_units()` and
`check_cadence()` are never called, and NO unit conversion is verified. The
contract RECORDS that a variable is metres or acre-feet; nothing compares
that declaration against what the external model actually sends, so a
wrong-unit value that lands inside the declared range passes silently. Keys
the reply carries but the contract does not declare are logged as a warning
and otherwise ignored.

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

## Continuous control (archetype A extension — PROVEN)

When the decision is a NUMERIC setpoint rather than a discrete skill choice,
use `ContinuousBundle` (`broker/coupling/continuous.py`): the hosted
BMI-conformant solver advances `substeps_per_decision` (K) sub-steps per
decision period, per-variable sub-step series roll up by each observation
VarSpec's `observation_reduce` (mean/min/max/sum/last), and the approved
skill's setpoint writes into the solver through a `ControlSink`
(`BmiControlSink` adapts `set_value` automatically). Worked example:
`examples/reservoir_control/` — annual decision × 12 monthly sub-steps,
`magnitude_pct` (0-100% of demand) mapped to a named solver input in a small
bundle subclass, governed by a dead-pool projection wall BEFORE the commit.

Three contracts the example pins (copy them, don't rediscover):

1. **Decision timing is part of the physics.** Hindcast-then-set cadence
   (solver runs the year, THEN the agent sets next year's control) means the
   projection wall must consume the COMING period's forecast
   (`forecast_for(year + 1)`) — feeding the just-consumed period's value
   makes the wall fire for the wrong physical reason and the demo lies.
2. **Derived setpoints re-check the contract range in the bundle.** The
   adapter's generic PRE check sees the proposal's raw parameter names
   (`magnitude_pct`); a bundle that DERIVES the solver input
   (`release_target`) must re-validate the derived value against the same
   VarSpec range before calling the sink.
3. **The model-agnostic slot is real**: the example's test suite swaps in a
   second solver with a different evaporation law under the SAME contract and
   bundle, unchanged. Any BMI-conformant model (update / get_value /
   set_value / get_var_units / get_current_time) drops into the slot;
   non-BMI models implement the 4-verb surface in a ~30-line wrapper.

Real-LLM validated (gemma4:e4b, 4-yr run, exit-clean, 4/4 APPROVED): the
model self-curtailed (20-40% of demand in drought years) so the dead-pool
wall never needed to fire — walls are backstops, not steering. What the
real run DID exercise: two early-year magnitude parse failures were caught
by the output-schema check plus the validator's honest missing-key result
(`missing_world_state`), governed re-prompts recovered both, and no
silent fallback occurred. The deterministic wall→retry→APPROVED narrative
is pinned by the scripted-mock path and its test suite instead. One more
real-LLM lesson baked into both coupled examples: the hub-less builder
path does not populate `{options_text}`, so inject the action menu via
`dynamic_state` and give the `decision` field an explicit `description`
(the format builder's default claims "1, 2, or 3" regardless of menu size).

## Two models at once
One bundle per adapter, one `event_src` slot — compose INSIDE one bundle:
`run_pipeline` pumps both models and merges their env projections; contract
checks operate on the merged env unchanged; report both identities in
`bundle_provenance`. Worth this paragraph, not worth an orchestrator.

## Two orderings, two different things

(PR-9 naming audit.) Two config knobs share the word "order" and nothing
else — a multi-agent coupled domain sets BOTH, independently, and setting
one does not configure or imply the other:

| Knob | Lives on | Orders | Meaningless without |
|---|---|---|---|
| `ExperimentBuilder.with_phase_order([[...], [...]])` | the WAGF execution loop | WHICH AGENT TYPES run before which others within one period (e.g. government decides before household) | nothing — applies whether or not coupling is in use at all |
| `CouplingContract.operation_order` | one coupled bundle | the STAGES inside that bundle's `InterfaceBundle.run_pipeline` (e.g. `("hazard", "exposure", "vulnerability", "financial")` — cat_model's chain) | a bundle; a domain with no coupling has no `operation_order` to set |

Concretely: `with_phase_order` decides that the insurer agent proposes a
payout before the household agent reflects on it THIS period.
`operation_order` decides that, INSIDE the insurer's own coupled world
update, hazard is computed before exposure, before vulnerability, before
the financial ledger — a sequence that has nothing to do with which agent
type runs when. Confusing the two produces a domain that pins the wrong
sequence: reordering `operation_order` will not change agent-type
execution order, and reordering `with_phase_order` will not change a
bundle's internal pipeline stages.

## What NOT to build (review-confirmed)
Connector SDK / per-archetype base classes (each is ≤30 lines over existing
Protocols) · async/retry REST adapter (no consumer exists) · model registry /
plugin discovery · YAML contract DSL (`contract.py` already keeps
enum-strings so YAML loading later needs zero machinery) · multi-bundle
orchestrator · a generic grid→agent mapper in broker/ (build it in the first
spatial example) · `ramp`/`rate` hold-policy executors before a real domain
needs them.
