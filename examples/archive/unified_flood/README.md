# Unified Flood Experiment

> **Task-040**: SA/MA Unified Architecture Demonstration

This example demonstrates the new unified architecture that supports both Single-Agent (SA) and Multi-Agent (MA) scenarios.

## New Architecture Components

| Component | Location | Description |
|-----------|----------|-------------|
| **AgentTypeRegistry** | `broker/config/agent_types/` | Central registry for agent type definitions |
| **UnifiedContextBuilder** | `broker/core/unified_context_builder.py` | Mode-based context building (SA/MA) |
| **AgentInitializer** | `broker/core/agent_initializer.py` | Survey/CSV/Synthetic initialization |
| **PsychometricFramework** | `broker/core/psychometric.py` | PMT/Utility/Financial frameworks |
| **TypeValidator** | `broker/governance/type_validator.py` | Per-type skill validation |

## Quick Start

```bash
# Dry run (verify components)
python run_experiment.py --dry-run

# SA mode with synthetic agents
python run_experiment.py --mode single_agent --agents 10 --years 5

# SA mode with social features
python run_experiment.py --mode single_agent --enable-social --agents 20

# MA mode (future: with multiple agent types)
python run_experiment.py --mode multi_agent --enable-multi-type --agents 30
```

## Agent Types

This example defines multiple agent types with different psychological frameworks:

### Household Types (PMT Framework)

| Type | Skills | Description |
|------|--------|-------------|
| `household` | All adaptation options | Base household type |
| `household_owner` | Full options | Homeowner (inherits from household) |
| `household_renter` | Limited options | Renter (cannot elevate/buyout) |

### Institutional Types (MA Only)

| Type | Framework | Description |
|------|-----------|-------------|
| `government` | Utility | Policy decisions |
| `insurance` | Financial | Premium/coverage decisions |

## Initialization Modes

```bash
# Synthetic agents (default)
python run_experiment.py --init-mode synthetic --agents 50

# From CSV file
python run_experiment.py --init-mode csv --csv-path agents.csv

# From survey data
python run_experiment.py --init-mode survey --survey-path survey.xlsx
```

## Configuration

### agent_types.yaml

New unified schema with:

```yaml
agent_types:
  household_owner:
    type_id: household_owner
    category: household
    psychological_framework: pmt
    eligible_skills: [buy_insurance, elevate_house, ...]
    validation:
      identity_rules: [...]
      thinking_rules: [...]
    memory_config:
      engine: unified
      surprise_strategy: ema
```

### skill_registry.yaml

Skills with `eligible_agent_types`:

```yaml
skills:
  elevate_house:
    eligible_agent_types: [household, household_owner]
    preconditions: [not_elevated, is_owner]
```

## Comparison with Old Examples

| Feature | single_agent | single_agent_modular | **unified_flood** |
|---------|--------------|---------------------|-------------------|
| Context Builder | TieredContextBuilder | FloodContextBuilder | **UnifiedContextBuilder** |
| Agent Init | CSV loader | CSV/Survey loader | **AgentInitializer** |
| Agent Types | Single type | Single type | **Multi-type support** |
| Validation | GovernanceRule | GovernanceRule | **TypeValidator** |
| Psych Framework | Hardcoded PMT | Hardcoded PMT | **Configurable** |

## File Structure

```
unified_flood/
├── run_experiment.py       # Main entry point
├── agent_types.yaml        # Unified agent type config
├── skill_registry.yaml     # Skill definitions
├── README.md              # This file
└── results/               # Output directory
```

## Tests

```bash
# Run all Task-040 tests
pytest tests/test_agent_type_registry.py -v
pytest tests/test_unified_context_builder.py -v
pytest tests/test_agent_initializer.py -v
pytest tests/test_psychometric.py -v
pytest tests/test_type_validator.py -v
```
