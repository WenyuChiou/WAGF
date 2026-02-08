# Water Agent Governance Framework Architecture

## Overview

The Water Agent Governance Framework is a cognitive governance middleware for LLM-driven agent-based models of human-water interactions. It provides skill-based governance, memory, and reflection capabilities designed for coupled human-water simulations — including flood risk adaptation, irrigation water management, and water resource policy evaluation.

The framework's extensible architecture allows new water sub-domains to be added through configuration (YAML skill registries + domain validators) without modifying the core broker.

**Version**: v0.30+

---

## Core Design Principles

### 1. Extensible Water-Domain Core

The `broker/` directory contains **reusable components** designed for coupled human-water ABMs, extensible to new water sub-domains:

- Core governance pipeline (skill proposal → validation → execution) is domain-independent
- Water sub-domain logic (flood adaptation, irrigation management) lives in `examples/<domain>/`
- Configuration-driven behavior via YAML skill registries and validator definitions

### 2. Protocol-Based Dependency Injection

Domain-specific code can extend broker capabilities without modifying broker source:

```python
# broker/interfaces/enrichment.py - Generic Protocol
class PositionEnricher(Protocol):
    def assign_position(self, profile) -> PositionData: ...

# examples/multi_agent/environment/depth_sampler.py - Domain Implementation
class DepthSampler:  # Implicitly implements PositionEnricher
    def assign_position(self, profile) -> PositionData:
        # MA-specific flood zone assignment
        ...
```

### 3. Extensions Pattern for Domain Data

Generic data structures support domain-specific extensions:

```python
# broker/modules/survey/agent_initializer.py
@dataclass
class AgentProfile:
    agent_id: str
    family_size: int
    extensions: Dict[str, Any]  # Domain-specific data here

# Domain code adds extensions
profile.extensions["flood"] = FloodExposureData(...)
profile.extensions["trading"] = TradingPreferences(...)
```

---

## Directory Structure

```
broker/                          # Core governance middleware
├── components/                  # Core components
│   ├── audit_writer.py         # Trace logging
│   ├── context_builder.py      # LLM prompt construction
│   ├── memory.py               # Memory management (config-driven)
│   ├── memory_engine.py        # Memory retrieval engine
│   ├── reflection_engine.py    # Batch reflection processing
│   ├── skill_registry.py       # Action/skill management
│   ├── skill_retriever.py      # Skill selection
│   ├── social_graph.py         # Agent network relationships
│   └── universal_memory.py     # Cognitive System 1/2 switching
├── interfaces/                  # Protocol definitions
│   ├── enrichment.py           # PositionEnricher, ValueEnricher
│   ├── schemas.py              # Data schemas
│   └── skill_types.py          # Skill type definitions
├── modules/
│   └── survey/                  # Generic survey processing
│       ├── agent_initializer.py # Generic profile creation
│       └── survey_loader.py     # Generic CSV/Excel loading
└── utils/                       # Utilities
    ├── agent_config.py         # YAML config loading
    ├── llm_utils.py            # LLM API utilities
    └── logging.py              # Logging configuration

examples/                        # Domain-specific implementations
├── multi_agent/                 # MA Flood Simulation
│   ├── environment/            # Flood-specific enrichers
│   │   ├── depth_sampler.py    # Flood zone assignment
│   │   └── rcv_generator.py    # Property value generation
│   ├── survey/                 # MA-specific survey processing
│   │   ├── flood_survey_loader.py
│   │   ├── ma_initializer.py   # MG classification + flood extensions
│   │   └── mg_classifier.py    # Marginalized Group classifier
│   ├── ma_agent_types.yaml     # MA agent configurations
│   └── run_unified_experiment.py
└── single_agent/               # Single agent experiments
```

---

## Extensible Design Patterns (v0.30+)

### 1. Protocol-Based Dependency Injection

**Problem**: broker/modules/survey/ was importing from examples/multi_agent/

**Solution**: PEP 544 Protocols define interfaces without implementation coupling.

```python
# broker/interfaces/enrichment.py
from typing import Protocol, NamedTuple

class PositionData(NamedTuple):
    zone_name: str
    base_depth_m: float
    flood_probability: float

class PositionEnricher(Protocol):
    """Protocol for position/location enrichment."""
    def assign_position(self, profile) -> PositionData: ...

# Domain implementations satisfy the protocol implicitly:

# examples/multi_agent/environment/depth_sampler.py
class DepthSampler:
    def assign_position(self, profile) -> PositionData:
        # MA-specific: flood zone based on income, prior experience
        ...

# examples/trading_sim/location_sampler.py (hypothetical)
class TradingLocationSampler:
    def assign_position(self, profile) -> PositionData:
        # Trading-specific: market region based on assets
        ...
```

**Usage**:
```python
from broker.modules.survey import initialize_agents_from_survey

# Generic (no enrichers)
profiles, stats = initialize_agents_from_survey(survey_path)

# With domain-specific enrichers
profiles, stats = initialize_agents_from_survey(
    survey_path,
    position_enricher=DepthSampler(seed=42),
    value_enricher=RCVGenerator(seed=42)
)
```

### 2. Extensions Pattern for Domain-Specific Data

**Problem**: SurveyRecord and AgentProfile contained MA-specific fields.

**Solution**: Generic base classes + domain-specific extensions.

```python
# broker/modules/survey/survey_loader.py
@dataclass
class SurveyRecord:
    """Generic survey record."""
    record_id: str
    family_size: int
    income_bracket: str
    housing_status: str
    # No flood fields - generic!

# examples/multi_agent/survey/flood_survey_loader.py
@dataclass
class FloodSurveyRecord(SurveyRecord):
    """MA-specific survey record with flood fields."""
    flood_experience: bool = False
    financial_loss: bool = False
```

```python
# broker/modules/survey/agent_initializer.py
@dataclass
class AgentProfile:
    """Generic agent profile."""
    agent_id: str
    family_size: int
    extensions: Dict[str, Any] = field(default_factory=dict)

# Domain code adds extensions:
profile.extensions["flood"] = SimpleNamespace(
    flood_zone="Zone_A",
    base_depth_m=1.5,
    flood_probability=0.25
)
```

### 3. Config-Driven Domain Logic

**Problem**: Memory tags hardcoded as "MG" → "subsidy".

**Solution**: Load tags from agent_types.yaml.

```yaml
# examples/multi_agent/ma_agent_types.yaml
household_mg:
  memory:
    retrieval_tags: ["subsidy", "vulnerability", "financial_hardship"]
    window_size: 3

household_nmg:
  memory:
    retrieval_tags: ["insurance", "elevation", "adaptation"]
    window_size: 5
```

```python
# broker/components/memory.py
def _get_relevant_tags(self, agent_type: str) -> List[str]:
    """Load retrieval tags from config (not hardcoded)."""
    cfg = load_agent_config()
    memory_config = cfg.get_memory_config(agent_type)
    return memory_config.get("retrieval_tags", ["general"])
```

### 4. Classification Generalization

**Problem**: `is_mg` field was MA-specific (Marginalized Group).

**Solution**: Generic classification fields with backward-compatible aliases.

```python
# broker/modules/survey/agent_initializer.py
@dataclass
class AgentProfile:
    # Generic classification
    is_classified: bool = False
    classification_score: int = 0
    classification_criteria: Dict[str, bool] = field(default_factory=dict)

    # Backward compatibility aliases for MA code
    @property
    def is_mg(self) -> bool:
        return self.is_classified

    @property
    def mg_score(self) -> int:
        return self.classification_score
```

---

## Component Interactions

```
┌─────────────────────────────────────────────────────────────────┐
│                        broker/ (Generic)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │ SurveyLoader │───▶│AgentInitializer│───▶│ AgentProfile │     │
│  │   (generic)  │    │   (generic)   │    │  (generic)   │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│         │                   │                    │              │
│         │            ┌──────┴──────┐             │              │
│         │            │  Protocols  │             │              │
│         │            └──────┬──────┘             │              │
│         │                   │                    │              │
└─────────┼───────────────────┼────────────────────┼──────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   examples/multi_agent/ (MA Domain)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │FloodSurveyLoader│  │DepthSampler  │  │ profile.extensions│   │
│  │  (extends)     │  │(PositionEnricher)│  │   ["flood"]    │   │
│  └────────────────┘  └──────────────┘  └─────────────────┘    │
│                                                                 │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │  MGClassifier  │  │ RCVGenerator │  │ MAAgentProfile  │    │
│  │(MA-specific)   │  │(ValueEnricher)│  │   (extends)     │    │
│  └────────────────┘  └──────────────┘  └─────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration System

### Agent Type Configuration

```yaml
# examples/multi_agent/ma_agent_types.yaml
household_owner:
  cognitive_config:
    stimulus_key: "flood_depth_m"
    arousal_threshold: 2.0
    ema_alpha: 0.3

  memory_config:
    engine: "humancentric"
    window_size: 3
    top_k_significant: 2
    retrieval_tags: ["insurance", "elevation"]

  skills:
    - elevate
    - purchase_insurance
    - relocate
```

### Loading Configuration

```python
from broker.utils.agent_config import load_agent_config

cfg = load_agent_config()
cog = cfg.get_cognitive_config("household_owner")
mem = cfg.get_memory_config("household_owner")
```

---

## Migration Guide

For migrating from v0.28 to v0.29, see [task-029-migration-guide.md](.tasks/handoff/task-029-migration-guide.md).

Key changes:
1. SurveyRecord no longer has flood fields → Use FloodSurveyRecord
2. AgentProfile uses extensions dict → Access via `profile.extensions["flood"]`
3. Enrichers use Protocol pattern → Pass domain-specific enrichers explicitly

---

## Future Development

### Adding a New Water Sub-Domain

1. Create `examples/<new_water_domain>/` directory
2. Define skill registry YAML (e.g., `skill_registry.yaml` with domain-specific actions)
3. Implement domain validators (physical constraints, behavioral rules)
4. Implement domain environment (state transitions, feedback mechanisms)
5. Create domain-specific `agent_types.yaml` with prompt templates
6. Use broker/ components (ExperimentBuilder, SkillBrokerEngine, memory engines)

**Current water domains**:
- `examples/single_agent/` — Flood household adaptation (100 agents, PMT-based decisions)
- `examples/multi_agent/irrigation_abm/` — Irrigation water management (78 CRSS agents)

---

## Related Documents

- [Task-029 Migration Guide](.tasks/handoff/task-029-migration-guide.md)
- [Task-029 Audit Report](.tasks/handoff/task-029-audit-report.md)
- [MA Experiment Guide](examples/multi_agent/README.md)
