# Codex Tasks for Task-040

> **Date**: 2026-01-28
> **Priority**: HIGH
> **Context**: SA → MA Architecture Unification

---

## Task-C1: Config Schema Validation

### Goal
Create Pydantic validation models for `agent_types.yaml` configuration files.

### New File
`broker/config/schema.py`

### Reference Files (READ THESE FIRST)
```
examples/single_agent/agent_types.yaml          # SA config structure
examples/multi_agent/config/agents/agent_types.yaml  # MA config structure
governed_ai_sdk/memory/config/defaults.py       # Existing GlobalMemoryConfig
governed_ai_sdk/memory/config/domain_config.py  # Existing DomainMemoryConfig
```

### Requirements

1. **Create Pydantic models**:
```python
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Literal

class MemoryConfig(BaseModel):
    """Memory engine configuration."""
    engine_type: Literal["window", "importance", "humancentric", "hierarchical", "universal", "unified"] = "window"
    window_size: int = Field(default=5, ge=1, le=20)
    decay_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    consolidation_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    consolidation_probability: float = Field(default=0.7, ge=0.0, le=1.0)
    top_k_significant: int = Field(default=2, ge=1)
    arousal_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

class GovernanceRule(BaseModel):
    """Single governance rule."""
    id: str
    construct: Optional[str] = None
    conditions: Optional[List[Dict]] = None
    when_above: Optional[List[str]] = None
    blocked_skills: List[str]
    level: Literal["ERROR", "WARNING"] = "ERROR"
    message: Optional[str] = None

class GovernanceProfile(BaseModel):
    """Governance profile (strict/relaxed/disabled)."""
    thinking_rules: List[GovernanceRule] = []
    identity_rules: List[GovernanceRule] = []

class GlobalConfig(BaseModel):
    """Global experiment configuration."""
    memory: MemoryConfig = MemoryConfig()
    reflection: Optional[Dict] = None
    llm: Optional[Dict] = None
    governance: Optional[Dict] = None

class AgentTypeConfig(BaseModel):
    """Full agent_types.yaml configuration."""
    global_config: GlobalConfig
    shared: Optional[Dict] = None
    household: Optional[Dict] = None  # SA agent type
    # Add more agent types as needed
```

2. **Create loader function**:
```python
def load_agent_config(config_path: Path) -> AgentTypeConfig:
    """Load and validate agent_types.yaml configuration."""
    import yaml
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return AgentTypeConfig(**raw)
```

3. **Validation rules**:
   - Memory engine types must be one of: window, importance, humancentric, hierarchical, universal, unified
   - Governance profiles: strict, relaxed, disabled
   - Required fields: window_size, decay_rate

### Test File
`tests/test_config_schema.py`

```python
import pytest
from broker.config.schema import load_agent_config, AgentTypeConfig, MemoryConfig

def test_valid_config_loads():
    config = load_agent_config(Path("examples/single_agent/agent_types.yaml"))
    assert config.global_config.memory.window_size == 5

def test_invalid_engine_type_raises():
    with pytest.raises(ValueError):
        MemoryConfig(engine_type="invalid")

def test_all_memory_engine_types():
    for engine in ["window", "importance", "humancentric", "hierarchical", "universal", "unified"]:
        config = MemoryConfig(engine_type=engine)
        assert config.engine_type == engine
```

### Acceptance Criteria
- [ ] `broker/config/schema.py` created
- [ ] `tests/test_config_schema.py` passes
- [ ] SA config loads without error
- [ ] MA config loads without error

### Verification Command
```bash
python -m pytest tests/test_config_schema.py -v
```

---

## Task-C2: Unify Memory Factory

### Goal
Consolidate memory factory from SA Modular into broker for shared SA/MA usage.

### Files
- **Source**: `examples/single_agent_modular/components/memory_factory.py`
- **Target**: `broker/components/memory_factory.py` (NEW)

### Reference Files (READ THESE FIRST)
```
examples/single_agent_modular/components/memory_factory.py  # Current SA factory
broker/components/memory_engine.py                          # Base classes
governed_ai_sdk/memory/unified_engine.py                    # v5 engine
broker/components/engines/                                  # Existing engines
```

### Requirements

1. **Support all 6 memory engine types**:
```python
from typing import Optional, Dict, Any
from broker.components.memory_engine import MemoryEngine, WindowMemoryEngine
from broker.components.engines.importance_engine import ImportanceMemoryEngine
from broker.components.engines.humancentric_engine import HumanCentricMemoryEngine
from broker.components.engines.hierarchical_engine import HierarchicalMemoryEngine
from broker.components.universal_memory import UniversalCognitiveEngine
from governed_ai_sdk.memory.unified_engine import UnifiedCognitiveEngine as UnifiedEngine

def create_memory_engine(
    engine_type: str,
    config: Optional[Dict[str, Any]] = None,
    scorer: Optional[Any] = None,
    **kwargs
) -> MemoryEngine:
    """
    Factory function for creating memory engines.

    Args:
        engine_type: One of "window", "importance", "humancentric",
                     "hierarchical", "universal", "unified"
        config: Engine-specific configuration dict
        scorer: Optional memory scorer
        **kwargs: Additional engine parameters

    Returns:
        Configured MemoryEngine instance
    """
    config = config or {}

    if engine_type == "window":
        return WindowMemoryEngine(
            window_size=config.get("window_size", 5),
            scorer=scorer,
        )
    elif engine_type == "importance":
        return ImportanceMemoryEngine(
            window_size=config.get("window_size", 5),
            scorer=scorer,
        )
    elif engine_type == "humancentric":
        return HumanCentricMemoryEngine(
            window_size=config.get("window_size", 5),
            top_k_significant=config.get("top_k_significant", 2),
            consolidation_prob=config.get("consolidation_probability", 0.7),
            decay_rate=config.get("decay_rate", 0.1),
            scorer=scorer,
        )
    elif engine_type == "hierarchical":
        return HierarchicalMemoryEngine(
            window_size=config.get("window_size", 5),
            semantic_top_k=config.get("top_k_significant", 3),
            scorer=scorer,
        )
    elif engine_type == "universal":
        return UniversalCognitiveEngine(
            arousal_threshold=config.get("arousal_threshold", 1.0),
            scorer=scorer,
            **kwargs
        )
    elif engine_type == "unified":
        # v5 from SDK
        return UnifiedEngine(
            arousal_threshold=config.get("arousal_threshold", 0.5),
            working_capacity=config.get("window_size", 10),
            consolidation_threshold=config.get("consolidation_threshold", 0.6),
            **kwargs
        )
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")
```

2. **Update SA Modular to import from broker**:
```python
# examples/single_agent_modular/components/memory_factory.py
# Add deprecation notice and re-export

import warnings
warnings.warn(
    "Import from broker.components.memory_factory instead",
    DeprecationWarning
)
from broker.components.memory_factory import create_memory_engine

__all__ = ["create_memory_engine"]
```

### Test File
`tests/test_memory_factory.py`

```python
import pytest
from broker.components.memory_factory import create_memory_engine

@pytest.mark.parametrize("engine_type", [
    "window", "importance", "humancentric",
    "hierarchical", "universal", "unified"
])
def test_create_engine(engine_type):
    engine = create_memory_engine(engine_type)
    assert engine is not None

def test_unified_engine_from_sdk():
    engine = create_memory_engine("unified", config={
        "arousal_threshold": 0.5,
        "window_size": 10,
    })
    # Test basic operations
    engine.add_memory("agent1", "Test memory")
    memories = engine.retrieve("agent1")
    assert len(memories) > 0

def test_invalid_engine_raises():
    with pytest.raises(ValueError):
        create_memory_engine("nonexistent")
```

### Acceptance Criteria
- [ ] `broker/components/memory_factory.py` created
- [ ] `tests/test_memory_factory.py` passes
- [ ] SA Modular `--memory-engine unified` still works
- [ ] All existing tests pass

### Verification Commands
```bash
# Unit test
python -m pytest tests/test_memory_factory.py -v

# Integration test (don't run during active experiments!)
# cd examples/single_agent_modular
# python run_flood.py --memory-engine unified --years 1 --agents 3 --dry-run
```

---

## Important Notes

1. **Do NOT modify** files in `examples/single_agent/` - experiments may be running
2. **Prefer adding new files** over modifying existing ones
3. **Run tests** before committing
4. **Check imports** work from both SA and MA directories
