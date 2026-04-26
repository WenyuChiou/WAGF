# Coupling contract checklist

Run through this checklist for every (ABM, external model) pair. Each
question is YES/NO; any NO is a finding.

## A. Schema completeness

- [ ] ABM state schema is documented (file path declared).
- [ ] External model input schema is documented.
- [ ] External model output schema is documented.
- [ ] Each schema declares every field's type AND unit AND valid
  range.

## B. Field mapping

- [ ] Every external-input field maps to either an ABM agent field
  or an env field.
- [ ] Every external-output field maps to either an agent field, an
  env field, or an explicit "drop / log only" sink.
- [ ] No external-input field is computed inside the external model
  from another external-input field that is itself derived from this
  same agent's prior decision (phantom-input loop).

## C. Unit compatibility

- [ ] Volume units are consistent (don't mix m³, acre-ft, MAF, gal
  silently).
- [ ] Rate units are consistent (m³/s vs m³/day vs m³/year).
- [ ] Currency units are consistent (USD vs USD/year vs annualized).
- [ ] Probability units are consistent (annualized vs per-event).
- [ ] Depth units are consistent (m vs ft; ground-elevation vs
  water-surface).

## D. Time-step alignment

- [ ] Both systems agree on the canonical step duration.
- [ ] If steps differ, the aggregation rule (sum / mean / max / first
  / last) is explicit per field.
- [ ] No external-model output is consumed by the same-step agent
  decision that produced its input (read-after-write within step).
- [ ] Asynchronous events (e.g., flood occurrence) have a documented
  trigger and queue model.

## E. Feedback loops

- [ ] For every (action → external → state) loop, the
  anti-double-counting guard is named.
- [ ] Damage / cost / exposure is debited on EXACTLY ONE ledger per
  event (not both agent.cost AND env.aggregate_cost).
- [ ] Insurance payouts and government subsidies are not
  double-counted across the agent's ledger and the external model's
  ledger.
- [ ] Retries do not re-trigger the external model unless the
  external model is explicitly idempotent.

## F. Missing / out-of-range handling

- [ ] Every input field has a documented missing-value policy
  (e.g., NaN → clip to 0, NaN → fail loud).
- [ ] Every input field has a documented out-of-physical-range
  policy (e.g., negative demand → clamp to 0).
- [ ] When the external model returns a missing value, the agent
  state has a documented fallback rule.

## G. Randomness and reproducibility

- [ ] Both systems share the same random seed OR independently seed
  with documented derivation (e.g., env_seed = base_seed + 1).
- [ ] Stochastic external-model outputs are recorded in the
  reproducibility manifest (e.g., realized flood depth per seed-year).
- [ ] Re-running the same seed produces the same trajectory.

## H. Versioning

- [ ] The external model's version (commit / digest / build hash) is
  recorded in `reproducibility_manifest.json`.
- [ ] Schema-changing updates to either side bump a coupling-contract
  version number.

## Verdict rubric

- **RED**: any NO in sections A, B, C, D, E (structural / safety
  issues — must fix before next run).
- **YELLOW**: any NO in F, G, H (operational / reproducibility — must
  fix before submission).
- **GREEN**: all YES.

## Worked example: irrigation ABM ↔ Lake Mead reservoir

- **A**: ✓ — schemas in `examples/irrigation_abm/irrigation_env.py`
  and `agent_types.yaml`.
- **B**: ✓ — every reservoir input traces to agent.request
  (post-curtailment) or env.inflow (CRSS forcing).
- **C**: ✓ — all volumes in MAF (million acre-ft); rates in
  MAF/year. Lake elevation in ft.
- **D**: ✓ — agent decides annually; reservoir mass balance daily,
  aggregated to annual delivered volume before the next agent step.
- **E**: ⚠ until v21 fix landed at `irrigation_env.py:585-595`. The
  v20 bug was: increase/decrease scaled off `diversion` (post-
  curtailment), maintain preserved `request` — asymmetric base.
  Anti-double-counting guard now: `current = agent["request"]` for
  ALL skills. Documented at the same line range.
- **F**: ✓ — negative demand clipped to MIN_UTIL × water_right;
  out-of-range diversion clamped to [0, water_right].
- **G**: ✓ — env_seed derived from base seed; realized supply path
  recorded in `simulation_log.csv`.
- **H**: ⚠ — reservoir module version not currently recorded in the
  manifest; recommend adding to `_collect_reproducibility_metadata`.

Verdict: **YELLOW** (one operational gap: external-model versioning).
