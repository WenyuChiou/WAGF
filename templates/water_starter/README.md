# Water Starter Template (`templates/water_starter/`)

A minimal, copy-and-adapt WAGF case modeling a single reservoir operator choosing a monthly water release fraction (`magnitude` in `[0, 1]`) under a physical dead-pool constraint.

## Directory Layout

| File | Role |
|---|---|
| [config/agent_types.yaml](config/agent_types.yaml) | `global_config.run` slots, prompt variables, response fields, and the `dead_pool_guard` rule |
| [config/skill_registry.yaml](config/skill_registry.yaml) | Allowed actions (`set_release`, `maintain_release`) and proposal schema |
| [config/prompts/operator.txt](config/prompts/operator.txt) | Agent-facing prompt template populated per simulation year |
| [world.py](world.py) | 1-reservoir mass-balance world, agent factory, lifecycle hooks, and scripted `--model mock` responder |

## 30-Second Quickstart

Run from the repository root using a fresh `--output` directory:

```bash
python -m broker.tools.validate_prompt templates/water_starter/config/agent_types.yaml --strict
python -m broker.run templates/water_starter/config/agent_types.yaml --model mock --years 2 --output .tmp/starter-run
```

Expected behavior under `--model mock`:
- **Year 1** (`inflow_forecast = 10.0 maf`): the operator proposes full demand release (`magnitude = 1.0`) and is **APPROVED**.
- **Year 2** (`inflow_forecast = 1.5 maf` drought): proposing `magnitude = 1.0` would project storage (`4.5 maf`) below `dead_pool` (`5.0 maf`), so `dead_pool_guard` **blocks** attempt 1 and triggers a retry; the mock responder revises to `magnitude = 0.4`, which is **APPROVED**.

## Copy and Adapt to Your Own Case

1. Copy `templates/water_starter/` to a new folder (for example, `examples/my_basin/` or an external directory on `PYTHONPATH`).
2. Update the Variable & Unit Dictionary and equations in `world.py` (`build_world`, `build_agents`, `build_hooks`).
3. Edit [config/skill_registry.yaml](config/skill_registry.yaml), [config/agent_types.yaml](config/agent_types.yaml), and [config/prompts/operator.txt](config/prompts/operator.txt).
4. Re-run `validate_prompt --strict` and `--model mock` before switching `--model` to a local Ollama model (for example `gemma3:4b`) or a cloud provider configured in `providers/`.
