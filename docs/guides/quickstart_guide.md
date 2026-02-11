# Quickstart Guide

Get up and running with the WAGF governance framework in 3 progressive tiers.
Each tier adds complexity, building on the previous one.

---

## Tier 1: Barebone Decision Loop (~30 seconds)

See the core governance loop with 1 agent, 2 skills, and a mock LLM.
No Ollama installation required.

```bash
python examples/quickstart/01_barebone.py
```

**What you'll see:**

```
WAGF Quickstart — Barebone Decision Loop
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

**Source:** `examples/quickstart/01_barebone.py` (< 90 lines)

---

## Tier 2: Governance in Action (~1 minute)

See how governance rules **block** invalid decisions and trigger retries.

```bash
python examples/quickstart/02_governance.py
```

**What you'll see:**

```
WAGF Quickstart — Governance in Action
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

**Source:** `examples/quickstart/02_governance.py` (< 130 lines)

---

## Tier 3: Real LLM Experiment

Run a governed flood experiment with a real LLM (requires Ollama).

```bash
python examples/governed_flood/run_experiment.py --model gemma3:4b --years 5
```

**What it demonstrates:**

- Real LLM decision-making with governance constraints
- Domain-specific validators (flood risk rules)
- Custom adapter for output parsing
- YAML-driven skill registry and agent configuration

**To build your own domain**, copy `examples/governed_flood/` as a template:

- `run_experiment.py` — ExperimentBuilder setup
- `adapters/` — Domain-specific output parsing
- `validators/` — Domain-specific governance rules
- `config/` — Agent types and skill definitions (YAML)

**Source:** `examples/governed_flood/` (5 Python files + YAML config)

---

## Next Steps

| Goal | Guide |
| ---- | ----- |
| Build a full experiment | [Experiment Design Guide](experiment_design_guide.md) |
| Add custom validators | Experiment Design Guide, Step 4 |
| Add memory + reflection | Experiment Design Guide, Steps 5-6 |
| Multi-agent setup | [Multi-Agent Specs](../../docs/multi_agent_specs/) |
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
