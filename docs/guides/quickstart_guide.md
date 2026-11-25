# Quickstart Guide

> **Recommended entry for new water cases:** Use the [front-page quickstart](../../README.md#quickstart) (`python -m broker.run CONFIG`) and the [six-chapter tutorial](../tutorial/README.md).
> **Low-level Python API (`ExperimentBuilder`):** The scripts below demonstrate assembling an experiment directly in Python without YAML `global_config.run` slots. Run all commands from the repository root with fresh `--output` directories.

---

## Tier 1: Barebone Decision Loop (~30 seconds)

See the core governance loop with 1 agent, 2 skills, and a mock LLM.
No Ollama installation required.

```bash
python examples/quickstart/01_barebone.py --output .tmp/quickstart-barebone
```

**What you'll see:**

```
WAGF Quickstart - Barebone Decision Loop
========================================
--- Year 1 ---
  Agent_1: take_action (APPROVED)
--- Year 2 ---
  Agent_1: take_action (APPROVED)
--- Year 3 ---
  Agent_1: take_action (APPROVED)
Done!
```

**What it demonstrates:**
- `ExperimentBuilder` fluent API assembles the experiment
- Mock LLM returns a fixed skill proposal
- Broker parses, validates, and approves the decision
- Simulation engine applies state changes

**Source:** `examples/quickstart/01_barebone.py` (~110 lines)

---

## Tier 2: Governance in Action (~1 minute)

See how governance rules **block** invalid decisions and trigger retries.

```bash
python examples/quickstart/02_governance.py --output .tmp/quickstart-gov
```

**What you'll see:**

```
WAGF Quickstart - Governance in Action
========================================
--- Year 1 --- (protected=False)
  Agent_1: take_action (APPROVED)
--- Year 2 --- (protected=True)
  Agent_1: do_nothing (APPROVED) [retried 1x]
--- Year 3 --- (protected=True)
  Agent_1: do_nothing (APPROVED) [retried 1x]
```

**What it demonstrates:**
- Year 1: Agent proposes `take_action` -> APPROVED, state changes to `protected=True`
- Year 2: Agent proposes `take_action` again -> BLOCKED by `already_protected` rule
- Broker sends intervention report to LLM -> LLM retries with `do_nothing` -> APPROVED

**Source:** `examples/quickstart/02_governance.py` (< 140 lines)

---

## Tier 3: Real LLM Experiment

Run the `broker.run` reservoir case or the flood benchmark with a real local LLM (requires [Ollama](https://ollama.com/) and `ollama pull gemma3:4b`):

```bash
# Generic broker.run entry (reservoir control):
python -m broker.run examples/reservoir_control/config/reservoir_agent_types.yaml --model gemma3:4b --years 4 --seed 42 --output .tmp/reservoir-llm

# Flood benchmark runner:
python examples/single_agent/run_flood.py --model gemma3:4b --years 5 --output .tmp/flood-ollama
```

**What it demonstrates:**

- Real LLM decision-making with governance constraints
- Domain-specific validators (flood risk rules)
- Custom adapter for output parsing
- YAML-driven skill registry and agent configuration

**To build your own domain**, scaffold via `python -m broker.tools.scaffold_domain <domain-name>` (or invoke the `wagf-domain-builder` Claude Code skill):

- `world.py` and a `global_config.run` block in `config/agent_types.yaml` - the world model and run settings; run the case with `python -m broker.run`
- `adapters/` - Domain-specific output parsing
- `validators/` - Domain-specific governance rules
- `config/` - Agent types and skill definitions (YAML)

**Source:** `broker.tools.scaffold_domain` CLI (official starter scaffold) + `wagf-domain-builder` skill walkthrough

---

## Next Steps

| Goal | Guide |
| ---- | ----- |
| Build a full experiment | [Experiment Design Guide](experiment_design_guide.md) |
| Add custom validators | Experiment Design Guide, Step 4 |
| Add memory + reflection | Experiment Design Guide, Steps 5-6 |
| Multi-agent setup | [Multi-agent flood example](../../examples/multi_agent/flood/) |
| Run without social network | [Single-Agent Mode](experiment_design_guide.md#single-agent-mode-no-social-network) |

---

## Protocol Reference

For IDE type checking and autocompletion, import these protocols:

```python
# Simulation engine
from broker.interfaces.simulation_protocols import SimulationEngineProtocol, SkillExecutorProtocol

# Lifecycle hooks
from broker.interfaces.lifecycle_protocols import PreYearHook, PostStepHook, PostYearHook

# Environment
from broker.interfaces.environment_protocols import EnvironmentProtocol, TieredEnvironmentProtocol

# Event generators
from broker.interfaces.event_generator import EventGeneratorProtocol
```
