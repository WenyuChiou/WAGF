# Pattern A: file replay

Use file replay when the external model output already exists and WAGF
only needs to look up the value that belongs to a year, scenario,
agent, grid cell, or event.

## When to use

Symptoms that point to Pattern A:

- The simulator costs money, cluster time, license tokens, or days of
  wallclock to run.
- The PhD does not control the simulator, but has historical outputs or
  a collaborator's scenario bundle.
- The model is opaque: CSV, NetCDF, GeoTIFF, HDF5, or database export is
  the documented interface.
- The experiment compares policies across scenarios that were already
  simulated.
- The research question can tolerate replayed forcing plus documented
  perturbations.

For example, a Lake Mead run can replay annual Powell release and Mead
elevation under each climate scenario while WAGF agents vary demand.

## Strengths

- Fast: startup is file parsing, not model execution.
- Deterministic: the same seed, scenario, and year return the same row.
- Offline: no license server, API token, binary, or service dependency.
- Easy to vary by seed or scenario: use one file per scenario or add
  columns such as `seed`, `scenario`, and `year`.
- Easy to smoke test: the mock adapter can load a tiny three-row CSV.

Pattern A is the right first scaffold when the real model exists only as
data. It lets the WAGF side settle its contract before runtime coupling.

## Weaknesses

- Agent actions do not truly feed back into the external model.
- Feedback can only be approximated by scaling or perturbing replayed
  values.
- Extrapolation is dangerous: missing years and out-of-scenario actions
  are not model predictions.
- Spatial joins are fragile when agent IDs, grid IDs, or coordinates
  change.
- Scenario metadata can drift away from the files if it is not recorded
  in the contract.

Do not present Pattern A as a live closed-loop hydrology model unless the
contract states exactly which feedback is approximated.

## Concrete examples from water domain

- `examples/irrigation_abm/` uses annual water-system context with
  Powell release and Lake Mead elevation semantics; a file-replay
  variant would read those annual values from CRSS-derived CSVs.
- `examples/irrigation_abm/docs/irrigation_physics.md` documents Powell
  release, Mead storage, Mead elevation, and agent demand variables that
  make good contract rows.
- Flood Paper 3 style integrations can replay pre-computed PRB depth
  grids by year/event and map each household to its grid cell.
- Multi-decade climate scenario CSVs can provide annual precipitation,
  shortage tier, or basin inflow forcing.

In each case, the file is not the model. It is a fixed realization of
one model scenario.

## Implementation skeleton

Start from:

```python
.claude/skills/wagf-coupling-designer/templates/adapter_A_file_replay.py.tmpl
```

The adapter normally:

1. Loads CSV or NetCDF once at initialization.
2. Indexes values by `(year, scenario)` or `(year, scenario, agent_id)`.
3. Accepts agent decisions such as `demand_delta_pct`.
4. Applies a documented perturbation to the replayed value.
5. Returns contract-named outputs for the WAGF context.

Agent decisions are often applied as multiplicative factors:

```python
adjusted = replay_value * (1.0 + demand_delta_pct)
```

That formula is not universal. The contract must say whether the offset
is linear, saturating, clipped, or diagnostic-only.

## Coupling contract checklist for this pattern

Track these variables explicitly:

- `year`: integer, calendar year or simulation year, not both.
- `scenario`: string or code matching the file metadata.
- `seed`: if the file contains stochastic realizations.
- `agent_id` or spatial key: only if outputs vary by agent.
- `agent_perturbation_factor`: name, unit, range, and clipping rule.
- Replay source path and version hash.

Handle these failure modes:

- Missing year: fail loudly or reuse last good output with a warning.
- Missing scenario: fail loudly; do not silently use baseline.
- Out-of-range value: reject, clip with logged bounds, or quarantine the row.
- Duplicate key rows: fail loudly unless aggregation is declared.
- Unit mismatch: convert exactly once at the adapter boundary.

Unit gotchas:

- Percent deltas must declare decimal vs whole percent.
- Elevation must declare feet vs meters and datum.
- Volumes must declare AF, MAF, cubic meters, or rate units.
- Annual CSV values must not be consumed as monthly signals without an
  aggregation or forward-fill rule.

The audit version of this checklist lives in
`model-coupling-contract-checker/references/contract_checklist.md`.
