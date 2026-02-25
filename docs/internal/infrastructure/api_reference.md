# Water Agent Governance Framework - API Reference

Welcome to the Water Agent Governance Framework API documentation.

## Quick Start

```python
from broker import (
    ExperimentBuilder,
    SkillRegistry,
    BaseAgentContextBuilder,
    AgentValidator
)

# Build and run a governed experiment
runner = (
    ExperimentBuilder()
    .with_model("llama3.2:3b")
    .with_agents(agents)
    .with_skill_registry("skills.yaml")
    .with_governance("strict", "agent_types.yaml")
    .build()
)
runner.run()
```

## Core Modules

### broker.core

- **SkillBrokerEngine** - Main orchestrator for skill-governed architecture
- **ExperimentBuilder** - Fluent API for experiment configuration
- **ExperimentRunner** - Standardized simulation loop

### broker.components

- **SkillRegistry** - Skill definition and validation registry
- **BaseAgentContextBuilder** - Context construction with provider pipeline
- **MemoryEngine** - Memory retrieval strategies (Window, Importance, HumanCentric)
- **InteractionHub** - Agent interaction and social graph management

### broker.interfaces

- **SkillProposal** - LLM output representation
- **ApprovedSkill** - Validated skill ready for execution
- **SkillBrokerResult** - Complete processing result

### broker.utils

- **UnifiedAdapter** - Multi-model output parsing with fallback layers
- **LLMStats** - LLM invocation statistics
- **LLMProvider** - Abstract interface for LLM providers

### broker.validators

- **AgentValidator** - Governance rule validation

## Generating HTML Documentation

```bash
# Install pdoc3
pip install pdoc3

# Generate HTML docs
pdoc --html broker -o docs/api --force

# Serve locally
pdoc --http localhost:8080 broker
```

## Module Index

For detailed API documentation, see generated HTML files or use:

```python
import broker
help(broker)
```
