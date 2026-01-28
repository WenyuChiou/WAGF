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

## Task-C3: Extract Memory Templates to Broker (Originally G1)

### Goal
Move MA memory templates to broker for SA/MA reuse.

### Files
- **Source**: `examples/multi_agent/memory/templates.py` (378 lines)
- **Target**: `broker/components/prompt_templates/memory_templates.py` (NEW)

### Reference Files (READ THESE FIRST)
```
examples/multi_agent/memory/templates.py         # Current templates
examples/multi_agent/generate_agents.py          # How templates are used
```

### Requirements

1. **Create directory structure**:
```
broker/components/prompt_templates/
├── __init__.py
└── memory_templates.py
```

2. **Create MemoryTemplateProvider class**:
```python
"""
Memory template generation for agent initialization.
Moved from examples/multi_agent/memory/templates.py for SA/MA reuse.
"""
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class MemoryTemplate:
    """Generated memory with metadata."""
    content: str
    category: str  # flood_event, insurance_claim, etc.
    emotion: str = "neutral"  # major, minor, neutral
    source: str = "personal"  # personal, neighbor, community

class MemoryTemplateProvider:
    """
    Provides memory templates for different domains.

    Categories:
    - flood_event: Direct flood experience
    - insurance_claim: Insurance interactions
    - social_interaction: Neighbor discussions
    - government_notice: Government communications
    - adaptation_action: Past adaptation decisions
    - risk_awareness: Flood zone awareness
    """

    @staticmethod
    def flood_experience(profile: Dict[str, Any]) -> MemoryTemplate:
        """Generate flood experience memory from survey data."""
        if profile.get("flood_experience", False):
            freq = profile.get("flood_frequency", 1)
            recent = profile.get("recent_flood_text", "recently")
            content = f"I experienced flooding {freq} time(s). Last flood was {recent}."
            return MemoryTemplate(
                content=content,
                category="flood_event",
                emotion="major",
                source="personal"
            )
        return MemoryTemplate(
            content="I have not experienced significant flooding.",
            category="flood_event",
            emotion="neutral",
            source="personal"
        )

    @staticmethod
    def insurance_interaction(profile: Dict[str, Any]) -> MemoryTemplate:
        """Generate insurance memory from survey data."""
        ins_type = profile.get("insurance_type", "none")
        if ins_type and ins_type.lower() != "none":
            content = f"I have {ins_type} flood insurance coverage."
            emotion = "minor"
        else:
            content = "I do not currently have flood insurance."
            emotion = "neutral"
        return MemoryTemplate(
            content=content,
            category="insurance_claim",
            emotion=emotion,
            source="personal"
        )

    @classmethod
    def generate_all(cls, profile: Dict[str, Any]) -> List[MemoryTemplate]:
        """Generate all 6 memory templates for an agent profile."""
        return [
            cls.flood_experience(profile),
            cls.insurance_interaction(profile),
            # Add remaining 4 methods...
        ]
```

3. **Update original file with deprecation**:
```python
# examples/multi_agent/memory/templates.py
import warnings
warnings.warn(
    "Import from broker.components.prompt_templates.memory_templates instead",
    DeprecationWarning,
    stacklevel=2
)
from broker.components.prompt_templates.memory_templates import (
    MemoryTemplateProvider,
    MemoryTemplate,
)
```

4. **Create __init__.py**:
```python
# broker/components/prompt_templates/__init__.py
from .memory_templates import MemoryTemplateProvider, MemoryTemplate

__all__ = ["MemoryTemplateProvider", "MemoryTemplate"]
```

### Acceptance Criteria
- [ ] `broker/components/prompt_templates/` directory created
- [ ] `MemoryTemplateProvider` class implemented with all 6 categories
- [ ] MA experiment imports work
- [ ] Backward compatibility maintained

### Verification Commands
```bash
# Test import from broker
python -c "from broker.components.prompt_templates import MemoryTemplateProvider; print('OK')"

# Test backward compatibility
python -c "from examples.multi_agent.memory.templates import MemoryTemplateProvider; print('OK')"
```

---

## Task-C4: Add Parse Confidence Scoring (Originally G2)

### Goal
Add parsing quality metrics to SkillProposal for audit trail.

### Target File
`broker/utils/model_adapter.py` (NOT broker/adapters/)

### Reference Files (READ THESE FIRST)
```
broker/utils/model_adapter.py       # Main adapter (lines 209-688)
broker/interfaces/skill_types.py    # SkillProposal definition
broker/components/audit_writer.py   # How traces are written
```

### Current State
`parse_layer` field ALREADY EXISTS in SkillProposal. Need to ADD:
- `parse_confidence: float`
- `construct_completeness: float`

### Requirements

1. **Update SkillProposal** (`broker/interfaces/skill_types.py`):
```python
@dataclass
class SkillProposal:
    # ... existing fields ...
    parse_layer: str = ""
    parse_confidence: float = 0.0      # NEW: 0.0-1.0
    construct_completeness: float = 0.0  # NEW: 0.0-1.0
```

2. **Add confidence scoring in parse_output** (`broker/utils/model_adapter.py`):

After each successful parse layer, set confidence:
```python
# After JSON extraction succeeds (around line 295):
parse_confidence = 0.95

# After keyword extraction succeeds (around line 487):
parse_confidence = 0.70

# After digit extraction succeeds (around line 494):
parse_confidence = 0.50

# Fallback (around line 587):
parse_confidence = 0.20
```

3. **Calculate construct completeness** (before returning SkillProposal):
```python
# Required constructs from config
required_constructs = ["TP_LABEL", "CP_LABEL", "decision"]
found = sum(1 for c in required_constructs if c in reasoning or c.lower() in str(skill_name))
construct_completeness = found / len(required_constructs)
```

4. **Update SkillProposal creation** (around line 685):
```python
return SkillProposal(
    skill_name=skill_name,
    reasoning=reasoning,
    raw_output=raw_output,
    parsing_warnings=parsing_warnings,
    parse_layer=parse_layer,
    parse_confidence=parse_confidence,        # NEW
    construct_completeness=construct_completeness,  # NEW
)
```

### Test File
`tests/test_parse_confidence.py`

```python
import pytest
from broker.utils.model_adapter import UnifiedAdapter

def test_json_parse_confidence():
    adapter = UnifiedAdapter(agent_type="household")
    raw_output = '<<<DECISION_START>>>{"decision": 2, "threat_appraisal": "H", "coping_appraisal": "M"}<<<DECISION_END>>>'
    context = {"agent_id": "test", "agent_type": "household"}

    result = adapter.parse_output(raw_output, context)

    assert result is not None
    assert result.parse_confidence >= 0.9
    assert result.parse_layer == "enclosure+json"

def test_construct_completeness():
    adapter = UnifiedAdapter(agent_type="household")
    raw_output = '<<<DECISION_START>>>{"decision": 2}<<<DECISION_END>>>'
    context = {"agent_id": "test", "agent_type": "household"}

    result = adapter.parse_output(raw_output, context)

    # Only decision found, missing TP_LABEL and CP_LABEL
    assert result.construct_completeness < 1.0
```

### Acceptance Criteria
- [ ] `parse_confidence` field added to SkillProposal
- [ ] `construct_completeness` field added to SkillProposal
- [ ] Confidence scores vary by parse method
- [ ] Existing tests pass
- [ ] New tests pass

### Verification Commands
```bash
# Run unit tests
python -m pytest tests/test_parse_confidence.py -v

# Check existing tests still pass
python -m pytest tests/ -v --ignore=tests/integration
```

---

## Important Notes

1. **Do NOT modify** files in `examples/single_agent/` - experiments may be running
2. **Correct path**: `broker/utils/model_adapter.py` (NOT broker/adapters/)
3. **Run tests** before committing
4. **Check imports** work from both SA and MA directories

---

## Task Status

| Task | Status | Notes |
|------|--------|-------|
| C1: Config Schema | ✅ DONE | 4 tests pass |
| C2: Memory Factory | ✅ DONE | 8 tests pass |
| C3: Memory Templates | ❌ TODO | Extract to broker |
| C4: Parse Confidence | ❌ TODO | Add confidence scoring |
