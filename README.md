# Governed Broker Framework

**🌐 Language / 語言: [English](README.md) | [中文](README_zh.md)**

<div align="center">

**A governance middleware for LLM-driven Agent-Based Models**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Overview

The Governed Broker Framework provides a **skill-governed architecture** for building reliable LLM-based Agent-Based Models (ABMs). It ensures that LLM decisions are validated through a multi-stage pipeline before affecting simulation state.

### Key Features

- **Multi-Stage Validation**: Configurable validators ensure admissibility, feasibility, constraints, safety, and consistency
- **Multi-Agent Support**: Supports heterogeneous agent types with different skills and eligibility rules
- **Multi-Level State**: Individual, Social, Shared, and Institutional state layers with access control
- **Extensible LLM Providers**: Default Ollama, extensible to OpenAI, Anthropic, etc.
- **Full Traceability**: Complete audit trail for reproducibility

---

## Challenges & Solutions

![Challenges and Solutions](docs/challenges_solutions.png)

| Challenge | Problem | Solution | Component |
|-----------|---------|----------|-----------|
| **Hallucination** | LLM generates invalid/non-existent actions | Skill Registry restricts to registered skills only | `SkillRegistry` |
| **Asymmetric Information** | LLM lacks state awareness, makes infeasible decisions | Context Builder provides bounded observable state | `ContextBuilder` |
| **Inconsistent Decisions** | Contradictory or illogical choices | Multi-stage validators check PMT consistency | `Validators` |
| **No Traceability** | Cannot reproduce or audit decisions | Complete audit trail with timestamps | `AuditWriter` |
| **Uncontrolled State Mutation** | Direct, unvalidated state changes | State Manager controls all state updates | `StateManager` |
| **Social Blindness** | No awareness of neighbor behaviors | Social module observes neighbor actions | `NeighborProvider` |

---

## Architecture

### Single-Agent Mode

![Single-Agent Architecture](docs/single_agent_architecture.png)

**Flow**: Environment → Context Builder → LLM → Model Adapter → Skill Broker Engine → Validators → Executor → State

### Multi-Agent Mode

![Multi-Agent Architecture](docs/multi_agent_architecture.png)

**Flow**: Agents → LLM (Skill Proposal) → Governed Broker Layer (Context Builder + Validators) → State Manager with four layers: Individual (memory), Social (neighbor observation), Shared (environment), and Institutional (policy rules).

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run example experiment
cd examples/skill_governed_flood
python run_experiment.py --model llama3.2:3b --num-agents 100 --num-years 10
```

---

## Framework Evolution

![Framework Evolution](docs/framework_evolution.png)

**No MCP → MCP v1 → Skill-Governed (v2)**: Progressive governance layers added for reliable LLM-ABM integration.

---

## Core Components

### Broker Layer (`broker/`)

| Component | File | Description |
|-----------|------|-------------|
| `SkillBrokerEngine` | `skill_broker_engine.py` | Main orchestrator: validates skills, manages execution pipeline |
| `SkillRegistry` | `skill_registry.py` | Skill definitions with agent type eligibility and parameter schemas |
| `ContextBuilder` | `context_builder.py` | Builds bounded context from state, includes neighbor observation |
| `ModelAdapter` | `model_adapter.py` | Parses LLM output into structured SkillProposal |
| `AuditWriter` | `audit_writer.py` | Complete audit trail for reproducibility |

### State Layer (`simulation/`)

| Component | File | Description |
|-----------|------|-------------|
| `StateManager` | `state_manager.py` | Multi-level state: Individual / Social / Shared / Institutional |
| `SimulationEngine` | `engine.py` | ABM simulation loop with skill execution |

### Provider Layer (`providers/`)

| Component | File | Description |
|-----------|------|-------------|
| `OllamaProvider` | `ollama.py` | Default LLM provider (local Ollama) |
| `OpenAIProvider` | `openai_provider.py` | OpenAI API provider |
| `ProviderFactory` | `factory.py` | Dynamic provider instantiation |
| `RateLimiter` | `rate_limiter.py` | Rate limiting for API calls |

### Validator Layer (`validators/`)

| Component | File | Description |
|-----------|------|-------------|
| `BaseValidator` | `base.py` | Abstract validator interface |
| `SkillValidators` | `skill_validators.py` | 6 validators: Admissibility, Feasibility, Constraints, Safety, PMT, Uncertainty |
| `ValidatorFactory` | `factory.py` | Dynamic validator loading from YAML |


---

## State Management

### State Ownership (Multi-Agent)

```
┌─────────────────────────────────────────────────────────────┐
│  Agent 1          Agent 2          Agent 3                  │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │ INDIVIDUAL│     │ INDIVIDUAL│     │ INDIVIDUAL│           │
│  │ • memory  │     │ • memory  │     │ • memory  │           │
│  │ • elevated│     │ • elevated│     │ • elevated│           │
│  │ • insured │     │ • insured │     │ • insured │           │
│  └─────┬────┘     └─────┬────┘     └─────┬────┘            │
│        │                │                │                  │
│        └────────────────┼────────────────┘                  │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               SHARED STATE                           │   │
│  │  • flood_occurred  • year  • community_stats         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

| State Type | Examples | Scope | Read | Write |
|------------|----------|-------|------|-------|
| **Individual** | `memory`, `elevated`, `has_insurance` | Per-agent private | Self only | Self only |
| **Social** | `neighbor_actions`, `last_decisions` | Observable neighbors | Neighbors | System |
| **Shared** | `flood_occurred`, `year` | All agents | All | System |
| **Institutional** | `subsidy_rate`, `policy_mode` | All agents | All | Gov only |

> **Key Point**: `memory` is **Individual** - each agent has their own memory, not shared.

```python
from simulation import StateManager

state = StateManager()
state.register_agent("agent_1", agent_type="homeowner")

# Individual: agent's private state (including memory)
state.update_individual("agent_1", {
    "memory": ["flood in year 2", "bought insurance in year 3"],
    "elevated": True
})

# Shared: environment visible to all
state.update_shared({"flood_occurred": True, "year": 5})
```

---

## Validation Pipeline

| Stage | Validator | Check |
|-------|-----------|-------|
| 1 | Admissibility | Skill exists? Agent eligible for this skill? |
| 2 | Feasibility | Preconditions met? (e.g., not already elevated) |
| 3 | Constraints | Once-only? Annual limit? |
| 4 | Effect Safety | State changes valid? |
| 5 | PMT Consistency | Reasoning matches decision? |
| 6 | Uncertainty | Response confident? |

---

## Multi-Agent Configuration

```yaml
# config/agent_types.yaml
agent_types:
  homeowner:
    skills: [buy_insurance, elevate_house, relocate, do_nothing]
    observable: [neighbors, community]
  
  government:
    skills: [set_subsidy, change_policy]
    can_modify: [institutional]
```

---

## Framework Comparison

| Dimension | Single-Agent | Multi-Agent |
|-----------|--------------|-------------|
| State | Individual only | Individual + Social + Shared + Institutional |
| Agent Types | 1 type | N types (Resident, Gov, Insurance) |
| Observable | Self only | Self + Neighbors + Community Stats |
| Context | Direct | Via Context Builder + Social Module |
| Use Case | Basic ABM | Policy simulation with social dynamics |

---

## Documentation

- [Architecture Details](docs/skill_architecture.md)
- [Customization Guide](docs/customization_guide.md)
- [Experiment Design](docs/experiment_design_guide.md)

---

## License

MIT
