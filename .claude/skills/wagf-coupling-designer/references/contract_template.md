# Coupling contract guide

The coupling contract names the boundary between WAGF agents and an
external model. It prevents the common failure where the adapter works
for one demo run but nobody can say which side owns time, units, state,
or failures.

Use the fill-in template at:

```text
.claude/skills/wagf-coupling-designer/templates/coupling_contract.md.tmpl
```

## Cadence

This section exists because agent decisions and model updates rarely
share the same clock.

Good content names both clocks and the sync rule. Example: irrigation
agents decide annually; reservoir forcing may be daily or annual; WAGF
passes year-start context into the agent and records model outputs for
the next decision.

Bad content says "the model runs each step" without defining whether
step means day, month, year, event, or agent turn.

Align with
`model-coupling-contract-checker/references/time_step_alignment.md`
before treating the loop as safe.

## Inputs table

Inputs are the decision flow from LLM/agent state into the model. Each
row must declare variable, type, unit, valid range, and mapping from
`skill_id` or environment field.

Good: `demand_delta_pct`, float, decimal fraction, `[-0.20, 0.20]`,
mapped from `increase_small` or `decrease_small`.

Bad: `demand_change`, number, "percent", "reasonable", "from prompt".
That leaves decimal vs whole percent unresolved.

## Outputs table

Outputs are the observation flow from model to agent context. Each row
must say whether the value is visible to the next agent decision,
written to environment state, logged only, or dropped.

Good: irrigation model outputs `powell_release_maf`, `mead_elevation_ft`,
and `shortage_tier`, all consumed in the next year's context.

Bad: output table lists "water status" without defining fields or
whether agents see the same-step result.

## Failure modes

Every timeout, NaN, crash, and wrong shape needs a planned response. The
CONTRACT's policy is always fail loudly — `VarSpec.on_missing` accepts
only `"fail_loud"`; `broker/coupling/contract.py` rejects `"last_good"`
or `"quarantine"` at construction because neither has a runtime executor
(a policy you can write but that silently never runs is worse than no
policy). Never silently zero-fill.

A reuse-last-good behaviour is still allowed, but it lives INSIDE your
adapter/source — before the value ever reaches the contract boundary —
not as a contract-level policy. See
`.claude/skills/wagf-coupling-designer/templates/adapter_A_file_replay.py.tmpl`
for the worked pattern (it caches the last good payload itself and tags
its own `external_model_status`).

Good: "Timeout over 30 seconds: the adapter reuses its cached
`mead_elevation_ft`, tags the reply `external_model_status=timeout`, and
writes a warning row. The CONTRACT still declares `on_missing=fail_loud`
for `mead_elevation_ft` — a call with NO cached value yet raises."

Bad: "If the model fails, use default values." Defaults erase the signal
that the experiment is no longer measuring the stated model. Equally bad:
"the contract sets `on_missing=last_good`" — that VarSpec will not
construct.

## Units audit checklist

This section exists because most coupling bugs are legal Python and
illegal science.

Check percent representation, currency base year, elevation datum,
volume units, rate units, per-agent vs aggregate values, and cadence.
Use `.claude/skills/wagf-coupling-designer/references/units_audit_checklist.md`
while drafting.

## Mock fidelity

The mock is not the external model. It is a contract test double. The
contract must state what the mock preserves and what it does not.

Good: "Mock preserves key names, ranges, deterministic seed behavior,
and monotonic response to demand. It does not preserve reservoir mass
balance."

Bad: "Mock behaves like the real model." That cannot be checked.

## Worked examples

Irrigation: the agent decides demand percent change; the adapter maps it
to `request_maf_delta`; the model returns Powell release, Mead elevation,
and shortage tier. The contract must say whether the demand perturbation
feeds a live mass balance or only scales replayed scenario output.

Flood replay: the agent decides mitigation; the adapter reads a
pre-computed PRB depth grid for `(scenario, year, parcel_id)`; the model
output is flood depth and damage. The contract must say whether
mitigation reduces damage after replay or changes flood depth itself.

Catastrophe model with cost feedback (the hardest single-agent case):
the agent decides a protective action (insure / elevate / relocate / do
nothing); the CAT model consumes that state plus a hazard draw and
returns, per agent, `flood_damage` (USD), `insurance_payout` (USD), and
`oop_cost = flood_damage − insurance_payout + premium_paid +
deductible`. `oop_cost` and a "was I flooded" flag feed next year's
risk-perception context — that is the decision loop. The contract MUST
pin, in order: (1) the operation sequence `damage → payout → oop →
risk-perception-input → memory` and which vintage each consumer reads
(the agent prompt AND every validator must read post-payout `oop_cost`,
not the gross figure — taxonomy E3); (2) that the `oop_cost` an agent
reads at year *t+1* is the value the model produced for year *t*, with
an ordering guarantee, not the `self.env = env` aliasing convention
alone (E1); (3) exactly one consumer-of-record for `insurance_payout`
and `flood_damage` so neither is double-credited into both the agent
ledger and an aggregate (E2). If a feasibility validator reads a
model-produced flag such as `condemned` (e.g., "cannot insure a
condemned structure"), the contract must record that the flag is
E1-current and the validator is scoped to the right agent type (E5).
Multi-agent variants of this example (a shared insurance pool whose
loss ratio resets every agent's premium — taxonomy E4) are out of v1
scope; see the Multi-agent caveat in SKILL.md and the disaster-coupling
worked example in
`wagf-domain-builder/references/multi_agent_walkthrough.md`. Full
taxonomy:
`model-coupling-contract-checker/references/coupling_interaction_taxonomy.md`.
