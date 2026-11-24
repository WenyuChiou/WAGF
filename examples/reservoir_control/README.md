# reservoir_control

Reservoir continuous-control worked example (Phase 6W). A single
governed LLM operator sets one bounded release-rate setpoint per year;
a hosted toy solver runs 12 monthly sub-steps and the framework tracks
storage against a dead-pool wall.

**Decision timing (hindcast-then-set)**: each year the solver advances
under the LAST committed release target, THEN the operator decides —
the dead-pool check runs the toy model forward from the storage just observed, with *next*
year's inflow forecast (rationale: `ops_modules.py` module docstring).

## Files

- `reservoir_pack.py` — `ReservoirControlDomainPack` (coupling OFF by default).
- `run_reservoir_ops.py` — the runnable experiment.
- `ops_modules.py` — the toy solver and its bundle (`apply_forecast`, `inputs_for_skill`).
- `ops_validators.py` — no checks any more; the dead-pool limit is a `feasibility:` bound in the contract.
- `config/reservoir_agent_types.yaml`, `config/reservoir_skill_registry.yaml`. The
  flood-control overflow limit (block `set_release` below 100% of demand while storage is
  above 90% of capacity) is one `expression:` rule in the YAML, under the `strict` profile.

## Run it

This is the first-run demo in the front-page [quickstart](../../README.md#quickstart).

```bash
python examples/reservoir_control/run_reservoir_ops.py --model mock --years 4 --seed 42 --output .tmp/readme-reservoir
```

The mock operator asks for 100% of demand, the dead-pool rule blocks that in year 3,
and the operator's retry at 50% is approved and executed. The run ends by printing
the blocked attempt with its reason, the approved retry, the executed release target
and the storage before and after. `--output` must be a new directory.

**Overflow rule, and one difference from the old Python check.** The overflow limit used
to be a Python check that blocked the proposal when `storage_now` or `proposed_magnitude`
was absent from the validation context. As a YAML `expression:` rule it follows the
framework rule for world conditions instead: a variable that is not there means the rule
does not fire, and the row gets a `world_variable_missing` WARNING. A variable that is
there but not a finite number gets a `world_variable_unusable` WARNING. The run's own
audit rows never have a missing variable (the runner publishes all three), so the demo
output is unchanged apart from the two grounding columns, which appear whenever a profile
has a world rule.

**Dead-pool check (feasibility bound).** The contract declares `dead_pool_violation`:
`storage_unclamped >= 6.0` must hold at every month of the coming year. Before a `set_release`
is approved, a deep copy of the toy reservoir is fed the forecast the operator saw and the
requested release, and run 12 months; the live model, its random numbers and files are not
touched. `storage_unclamped` is next month's storage before the clamp to [0, capacity]. The old
linear formula is gone: the check uses the model's own evaporation (see "Feasibility bounds" in
`docs/COUPLING_CONNECTORS.md`).

**Water balance.** The contract declares one relation, `storage_balance`: storage minus
(previous storage + inflow - release - evaporation - spill) must be within 1e-9 maf, checked
every month on the raw monthly values (see "Relations" in `docs/COUPLING_CONNECTORS.md`).
The toy solver publishes `inflow` and `evaporation` for it. A breach stops the run with
`CouplingViolation`. The toy solver clamps storage at 0, so in a month where the release takes
everything, the evaporation charged on the old storage is not removed and the balance is off
by that amount; the relation would stop such a run. The shipped 4-year mock run never reaches
that case (lowest storage is 6.36 maf against a release of at most 0.75 maf a month).
The relation reports `shortfall` under `observations_in_no_relation`: it is not part of the
balance.

Compare with `reservoir_control_multidim/` (three-setpoint variant).
