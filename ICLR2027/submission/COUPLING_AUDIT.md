# Irrigation coupling contract audit

Updated: 2026-08-08
Scope: read-only audit of the WAGF irrigation path and the generic coupling
interfaces that could affect the ICLR 2027 submission.

## Why this audit matters for the figures

The irrigation example is the paper's primary worked example because it has
the feedback loop needed to make the measurement-validity problem visible:

```text
agent request -> validator/retry -> accepted execution
       -> actual diversion -> annual reservoir state
       -> next year's agent context
```

This loop is the reason irrigation carries Figures 2--4 and the main numeric
tables. Flood remains a secondary boundary check in Table 3. It uses a
different action and feedback ontology, so giving it a second mechanism panel
or equal visual weight would make the paper look like two competing studies.

## Verdict

**Current ICLR paper configuration: YELLOW, with an explicit worker-1
boundary.** The annual sequence and the request/diversion/reservoir linkage
are coherent for the configuration used by the frozen irrigation corpus and
the manuscript. The coupling is not yet a generic GREEN contract for every
WAGF configuration: the direct irrigation path does not instantiate the
formal `CouplingContract`, the generic runner exposes parallel workers, and
some direct-path missing-field handling can silently fall back to defaults.

This is a release caveat, not a reason to add another figure. The paper should
state the worker-1 execution boundary in the reproducibility material and
should not imply that the audit proves safety for arbitrary parallel runs.

## Schema findings

| Signal | Direction and role | Unit or type | Audit status |
|---|---|---|---|
| `request` | agent proposal to the environment | acre-feet/year | Explicitly clamped to `[0, water_right]`; distinct from executed diversion |
| `diversion` | accepted/actual withdrawal used by the environment | acre-feet/year | Used by the annual reservoir update; distinct from the proposal |
| `water_right` | agent-side allocation bound | acre-feet/year | Propagated into the validator context |
| `precipitation` | environment to current-year context | millimetres | Generated at the annual environment step |
| `lake_mead_level` | environment to agent context | feet | Logged after the annual step and fed into later context |
| `mead_storage` | environment state | million acre-feet | Bounded by the reservoir surrogate |
| `natural_flow` / flow terms | environment state | million acre-feet/year | Used by the annual mass-balance surrogate |
| `shortage_tier` | environment to validator context | categorical | Synchronized before the agent decision |
| `WSA_LABEL` / `ACA_LABEL` | agent-authored appraisal fields | categorical | Selection inputs, not external simulator state |

The units and field meanings are documented in the irrigation environment, but
the direct irrigation execution path does not encode them in a formal
`VarSpec`/`CouplingContract`. The audit therefore treats the schema as
documented and tested, not as universally enforced by the framework.

## Time-step alignment

The current path is internally ordered as follows:

1. `advance_year` increments the year, generates the annual environment
   state, applies curtailment and the Powell constraint, and exposes the new
   context.
2. `pre_year` copies validator-relevant fields into the agent context and
   records prior feedback when a prior action exists.
3. The agent proposes a request. Validation and retry happen before any
   accepted request is executed.
4. The environment converts the accepted request into an actual diversion and
   records the post-year state.
5. The next annual reservoir update consumes the previous year's actual
   diversion, not the unexecuted proposal.

This gives the paper a defensible annual lag: a decision at year `t` affects
the reservoir state used at year `t+1`. The audit found no same-step
read-after-write dependency in the direct irrigation path, and retry does not
advance the environment or apply a partial action.

## Feedback-loop audit

| Check | Result | Interpretation |
|---|---|---|
| E1: state timing | PASS for the paper path | Prior-year actual diversions feed the next annual state |
| E2: action ledger | PASS with a documentation caveat | Proposal and actual diversion are separate; an exhaustive ledger is not enforced by the generic contract |
| E3: validator/execution order | PASS for the paper path | `advance -> pre_year -> propose/validate/retry -> execute -> post_year` |
| E4: shared-state concurrency | YELLOW | The frozen paper configuration is worker-1; the generic runner permits `workers > 1`, so no blanket parallel-safety claim is justified |
| E5: rule scoping | YELLOW/PASS conditional | Irrigation registration supplies the domain rule set; individual checks rely on the domain dispatch boundary rather than asserting agent type locally |

The irrigation model's pro-rata Powell constraint is computed at the annual
aggregate, which avoids an order-dependent one-agent-at-a-time reservoir
update in the paper configuration. That observation is not a proof that
arbitrary concurrent extensions preserve the same semantics.

## Failure-mode handling

- Requests are bounded by the agent's water right. Actual diversion is then
  shaped by curtailment and the Powell constraint.
- Reservoir storage and annual changes are bounded by the irrigation
  surrogate's documented limits.
- Missing fields in the direct irrigation context can use local defaults in
  some paths. This is the main coupling reason for the YELLOW verdict: a
  malformed context is not uniformly forced to fail loudly.
- The generic coupling layer supports explicit unit, range, cadence,
  direction, duplicate-consumer, and `fail_loud` checks, but those checks are
  not automatically applied to the direct irrigation adapter.
- The current corpus records seeds and configuration information, but dirty
  manifests and incomplete launch metadata in the new first-attempt branch
  prevent a clean reproducibility claim. That branch remains outside the
  manuscript; see `EXPERIMENT_AUDIT.md`.

## What this means for the paper

The figures should explain a measurement pipeline, not advertise the
irrigation simulator as the contribution:

- Figure 1 is domain-neutral and introduces the reusable counted-set problem.
- Figure 2 shows which rule layer supplies the selection condition.
- Figure 3 shows why a coupled environment makes the denominator difference
  consequential over time.
- Figure 4 shows the reported endpoint gap and its direction-sensitive
  interpretation.
- Table 3 gives Flood one bounded cross-testbed check without turning it into
  a co-primary mechanism study.

The manuscript should keep the claim at the level supported by this audit:
agent-authored selection can change what is counted, and in a coupled model
that selection can also change the state trajectory being interpreted. It
should not claim a generic causal effect, a universally safe parallel runner,
or that the irrigation-specific contract has been fully formalized for every
WAGF adapter.

## Reproducible checks

The following read-only checks were run for this audit:

```text
python -m pytest -q broker/tests/test_coupling_contract.py broker/tests/test_continuous_coupling.py broker/tests/test_cat_model_coupling.py tests/test_irrigation_env.py tests/test_irrigation_integration.py
```

Result: exit code 0; all collected tests passed. Python emitted existing
dependency-compatibility warnings, but no test failures.

The source inspection also covered the irrigation environment, lifecycle
hooks, retry loop, experiment runner, generic `CouplingContract`/`VarSpec`,
and the domain validator registry. No source files, live run directories, or
Cloud-owned experiment outputs were modified by this audit.
