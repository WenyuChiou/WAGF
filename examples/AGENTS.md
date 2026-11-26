# AGENTS.md — `examples/` Benchmarks & Starters

## Categories under `examples/`

1. **Frozen single-agent-type paper benchmarks (protect byte-identity)**:
   - `examples/single_agent/` — Flood household adaptation (`run_flood.py`). Guarded by `tests/test_frozen_guard_flood.py`.
   - `examples/irrigation_abm/` — Colorado River irrigation ABM (`run_experiment.py`). Keep existing YAML specs and USBR tables byte-stable unless explicitly revising a paper experiment.
2. **Shared domain pack & `broker.run` reference cases**:
   - `examples/governed_flood/` — Shared flood `DomainPack` imported by `examples/single_agent/` and `broker/tests/` fixtures; do not remove.
   - `examples/reservoir_control/`, `examples/reservoir_control_multidim/`, `examples/coupling_examples/`, `examples/quickstart/` — Reference `python -m broker.run` and SDK examples. Keep mock quickstarts fast and self-contained.
3. **Experimental multi-actor archive / extension**:
   - `examples/multi_agent/flood/` — Heterogeneous multi-actor PRB study (guarded by `tests/test_frozen_guard_multi_agent.py`); deferred to follow-up multi-agent research.
   - `examples/cat_model/` — Catastrophe-insurance coupling fixture used by `broker/tests/`.
