# reservoir_control

Reservoir continuous-control worked example (Phase 6W). A single
governed LLM operator sets one bounded release-rate setpoint per year;
a hosted toy solver runs 12 monthly sub-steps and the framework tracks
storage against a dead-pool wall.

**Decision timing (hindcast-then-set)**: each year the solver advances
under the LAST committed release target, THEN the operator decides —
the dead-pool projection combines just-observed storage with *next*
year's inflow forecast (rationale: `ops_modules.py` module docstring,
lines 3-7; the "C1" review-finding label is a code comment at line 60).

## Files

- `reservoir_pack.py` — `ReservoirControlDomainPack` (coupling OFF by default).
- `run_reservoir_ops.py` — the runnable experiment.
- `ops_modules.py`/`ops_validators.py` — solver + bounded-release check.
- `config/reservoir_agent_types.yaml`, `config/reservoir_skill_registry.yaml`.

## Run it

```bash
python examples/reservoir_control/run_reservoir_ops.py --model mock --years 4
```
Compare with `reservoir_control_multidim/` (three-setpoint variant).
