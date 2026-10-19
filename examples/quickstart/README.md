# Start with the water cases

The supported introduction is the [two-case quickstart](../../README.md#quickstart):
[household flood adaptation](../single_agent/README.md) for one-way coupling,
and [Colorado River irrigation](../irrigation_abm/README.md) for two-way coupling
with Lake Mead. Follow the [tutorial](../../docs/tutorial/README.md) to inspect
rules, audits, water state, recovery and analysis.

The pre-existing `01_barebone.py`, `02_governance.py`, `agent_types.yaml` and
`skill_registry.yaml` remain here unchanged for compatibility. They are not the
front-page teaching path.

- `01_barebone.py` shows a minimal agent–broker–simulation loop with the built-in mock: run `python examples/quickstart/01_barebone.py --output ../../.tmp/quickstart-barebone` from the repository root.
- `02_governance.py` shows a rule blocking repeated protection and a mock retry choosing `do_nothing`: run `python examples/quickstart/02_governance.py` from the repository root; it writes to `examples/quickstart/results/`, so delete `examples/quickstart/results/` first if an earlier run is there.

Read the [quickstart guide](../../docs/guides/quickstart_guide.md) for the underlying API.
