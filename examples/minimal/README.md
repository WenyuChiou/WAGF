# Minimal Template for New Domains

This is the official scaffold for starting a new WAGF experiment.
Copy this directory and customize 3 files to build your own LLM-governed ABM.

## Quick Start

```bash
# 1. Copy this template
cp -r examples/minimal examples/my_domain
cd examples/my_domain

# 2. Customize the 3 files (see below)
# 3. Run
python run_hello_world.py --model gemma3:4b --years 5
```

## File Structure

| File | Lines | Purpose |
| ---- | ----- | ------- |
| `agent_types.yaml` | 53 | Agent cognitive config, constructs, governance rules |
| `skill_registry.yaml` | 20 | Available actions, preconditions, state changes |
| `run_hello_world.py` | 155 | Simulation engine, lifecycle hooks, experiment runner |

## What to Customize

### `agent_types.yaml`

**Boilerplate (keep as-is):**
- `global_config` block (memory, LLM, governance settings)
- `shared.rating_scale` (VL/L/M/H/VH scale)
- `shared.response_format` structure (delimiters, field types)

**Domain-specific (must edit):**
- `shared.response_format.fields` — Replace `TP_LABEL`/`CP_LABEL` with your theory's constructs
- `agent_types.<your_type>.prompt_template` — Write your LLM prompt
- `agent_types.<your_type>.governance.rules` — Define blocking rules for your domain

### `skill_registry.yaml`

**Domain-specific (must edit):**
- `skills[].skill_id` — Your domain's action names
- `skills[].description` — What the LLM sees
- `skills[].eligible_agent_types` — Which agents can use each skill
- `skills[].preconditions` — State conditions that block the skill
- `skills[].allowed_state_changes` — Which state fields the skill modifies
- `default_skill` — Fallback action when governance blocks all others

### `run_hello_world.py`

**Boilerplate (keep as-is):**
- `ExperimentBuilder` fluent API chain
- `create_llm_invoke()` setup
- Argument parsing

**Domain-specific (must edit):**
- `MinimalSimulation` class — Replace with your domain's environment logic
- `MinimalSimulation.advance_year()` — Return your domain's environmental state
- `SimpleHooks` class — Add domain-specific pre/post processing
- `make_agents()` — Initialize agents with your domain's state variables

## Next Steps

After your minimal experiment runs:

1. **Add validators** — Create `validators/my_validators.py` with domain-specific checks
2. **Add memory** — Switch from `WindowMemoryEngine` to `HumanCentricMemoryEngine`
3. **Add reflection** — Implement a `DomainReflectionAdapter`
4. **Scale up** — Increase agents, add multi-agent phases, social network

See `docs/guides/experiment_design_guide.md` for the full 6-component guide.
