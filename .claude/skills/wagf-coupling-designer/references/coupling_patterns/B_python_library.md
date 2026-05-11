# Pattern B: Python library

Use Python-library coupling when the external model can be imported into
the WAGF process and called through a stable function or object API.

## When to use

Symptoms that point to Pattern B:

- The model is already Python and runs fast enough for one call per
  WAGF step.
- The model author can expose `step()`, `predict()`, `simulate()`, or a
  narrow wrapper with typed inputs.
- The PhD wants to iterate on the model and the agent prompts in
  lockstep.
- The model needs arrays, nested dictionaries, or custom objects that
  would be clumsy through CSV.
- Debugging across the WAGF/model boundary matters more than process
  isolation.

For example, a small scipy reservoir ODE can run inside the lifecycle
hook while the agent still receives only contract-approved outputs.

## Strengths

- No IPC overhead: calls are normal Python calls.
- Complex types are available: `np.ndarray`, pandas frames, dataclasses,
  torch tensors, or domain objects.
- The debugger can step from WAGF into the model wrapper.
- Initialization can be amortized: load weights, grids, or calibration
  data once.
- Unit tests can monkeypatch the model object directly.

Pattern B is usually the fastest path from mock to real model when the
external code is under the research team's control.

## Weaknesses

- Model state is shared with the WAGF process.
- Memory leaks or large caches can grow across years, seeds, or agents.
- Global state pollution can make seed-to-seed results depend on run
  order.
- A model crash raises inside WAGF and can kill the experiment.
- Threading bugs appear if the model is not safe under parallel agent
  workers.
- Dependency conflicts can break the whole environment.

If the model mutates module-level globals, write that risk into the
contract and reset plan before production runs.

## Concrete examples

- sklearn surrogate: `model.predict(feature_matrix)` returns risk,
  yield, or demand response.
- scipy ODE: `solve_ivp` advances a reservoir, epidemic, or inventory
  state between agent decision points.
- Custom in-house ABM: `external.step(actions, state)` advances
  households, firms, or parcels and returns aggregate observations.
- pytorch policy network: a trained model maps agent/environment
  features to a stressor, response probability, or constraint signal.

These examples are only acceptable when the contract names the exact
input keys, output keys, state reset behavior, and units.

## Implementation skeleton

Start from:

```python
.claude/skills/wagf-coupling-designer/templates/adapter_B_python_library.py.tmpl
```

Choose one initialization pattern:

- Initialize once per experiment when model load is expensive and the
  API exposes `reset(seed=...)`.
- Initialize once per seed when model state must be isolated by seed.
- Initialize per step only when the model is pure and cheap.

Prefer a thin adapter that converts WAGF dictionaries into model-native
types, calls the external API, validates outputs, and returns only the
contract-named observations.

Stateful modules need an explicit reset rule:

```python
adapter.reset(seed=base_seed + run_index)
```

Without reset semantics, cross-seed runs can inherit state from the
previous experiment.

## Coupling contract checklist for this pattern

Declare whether the external API is:

- Pure function: same inputs and seed produce same outputs, no retained
  state.
- Stateful object: internal state advances each call and must be reset.
- Hybrid: loaded parameters are fixed, but runtime caches or RNG change.

Document these items before real wiring:

- Import path and package version or commit.
- Constructor arguments, model artifact paths, and calibration files.
- Per-step input schema and shape.
- Output schema, shape, unit, valid range, and owner.
- Reset semantics for seed, scenario, and batch runs.
- Threading safety under WAGF worker settings.
- Failure policy for exceptions, NaN/inf, wrong shapes, and timeouts.

Specific traps:

- A numpy scalar is not the same as a Python `float` if JSON logging is
  expected.
- A torch tensor on GPU may outlive the step unless detached or moved.
- A pandas row indexed by label can silently reorder fields.
- A global RNG inside the model can leak across WAGF seeds.

The audit version of these checks lives in
`model-coupling-contract-checker/references/feedback_loop_traps.md`.
