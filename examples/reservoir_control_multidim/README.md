# reservoir_control_multidim

Reservoir MULTI-DIMENSIONAL control worked example (Phase 6W-B7). The
operator sets THREE bounded setpoints in one decision —
`release_rate_cms`, `hydropower_target_mw`, `flood_pool_pct` — via
per-field `ParameterBoundsValidator` (reject-and-retry), committed to
`ToyMultiReservoir` through a plain `ContinuousBundle`.

Unlike `reservoir_control/` (one setpoint), coupling is ON by default here.

## Files

- `reservoir_multidim_pack.py` — `ReservoirMultidimDomainPack`.
- `run_reservoir_multidim.py` — the runnable experiment.
- `ops_modules_multidim.py` — the three-setpoint solver.
- `config/multidim_agent_types.yaml`, `config/multidim_skill_registry.yaml`.
- `BASELINE_e4b.md` — the real-LLM (`gemma4:e4b`) worked-run baseline.

## Run it

```bash
python examples/reservoir_control_multidim/run_reservoir_multidim.py --model mock --years 4
```

Mock-validated skeleton; see `BASELINE_e4b.md` for real-LLM status.
