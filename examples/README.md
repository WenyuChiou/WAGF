# Framework Examples Directory

This directory contains reference implementations of the **Governed Broker Framework** across different domains and complexities.

| Domain                 | Description                                                                                         | Complexity    | Main Script                          |
| :--------------------- | :-------------------------------------------------------------------------------------------------- | :------------ | :----------------------------------- |
| **Multi-Agent Flood**  | Full simulation with Resident, Government, and Insurance agents interacting in a social network.    | ⭐⭐⭐ (High) | `multi_agent/run_flood.py`           |
| **Single-Agent Flood** | Controlled "Parity Benchmark" to test single agent reasoning against baseline scenarios.            | ⭐ (Low)      | `single_agent/run_flood.py`          |
| **Finance Trading**    | Demonstrates domain transferability via a Stock Market simulation with retail/institutional agents. | ⭐⭐ (Med)    | `finance/run_finance_multi_agent.py` |

## 🚀 Quick Start

### 1. Multi-Agent Flood Simulation (Flagship)

The most complete demonstration of the framework's capabilities, including the new **Demographic Audit**.

```bash
# Run a 5-step simulation with verbose logging to see reasoning audit
python examples/multi_agent/run_flood.py --steps 5 --agents 10 --verbose
```

### 2. Single-Agent Parity Check

Useful for testing new LLMs against standard prompt templates without social dynamics.

```bash
python examples/single_agent/run_flood.py --model llama3.2:3b --years 5
```

### 3. Finance Multi-Agent Simulation

Shows how the _exact same_ Broker and Context system adapts to a completely different domain (Stock Trading) just by changing the `agent_types.yaml` and `skill_registry.yaml`.

```bash
python examples/finance/run_finance_multi_agent.py
```

## 📂 Configuration Guide

Each example folder typically contains:

- `agent_types.yaml`: Defines Prompt Templates and available Skills.
- `skill_registry.yaml`: Defines physical constraints and effects of skills.
- `README.md` (Optional): Domain-specific details.
