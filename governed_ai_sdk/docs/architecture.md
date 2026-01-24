# GovernedAI SDK Architecture

This SDK provides a thin, modular governance layer for agent systems. It is organized into independent components that can be adopted incrementally.

## Component Overview

- **Types** (`v1_prototype/types.py`): Core dataclasses and enums.
- **PolicyEngine** (`v1_prototype/core/engine.py`): Stateless rule evaluation.
- **PolicyLoader** (`v1_prototype/core/policy_loader.py`): Policy ingestion and validation.
- **SymbolicMemory** (`v1_prototype/memory/symbolic.py`): Novelty detection and system mode.
- **CounterfactualEngine** (`v1_prototype/xai/counterfactual.py`): Explain blocked actions.
- **EntropyCalibrator** (`v1_prototype/core/calibrator.py`): Governance friction metrics.
- **GovernedAgent** (`v1_prototype/core/wrapper.py`): Adapter for existing agents.

## Data Flow

```
Agent (decide)
    |  action
    v
GovernedAgent
    |  state mapping
    v
PolicyEngine -> GovernanceTrace
    |  if blocked
    v
CounterfactualEngine -> CounterFactualResult
    |  optional
    v
EntropyCalibrator -> EntropyFriction

SymbolicMemory runs in parallel for novelty detection
```

## Design Principles

- **Stateless core**: PolicyEngine and CounterfactualEngine do not store state.
- **Pluggable**: Each module can be used standalone.
- **Transparent**: Outputs are structured dataclasses for easy logging.
