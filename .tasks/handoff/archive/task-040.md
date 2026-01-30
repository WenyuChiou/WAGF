# Task-040: SA/MA Unified Architecture

## Overview

Build a unified architecture supporting both Single-Agent (SA) and Multi-Agent (MA) scenarios with:
- Mode-based feature isolation (SA/MA don't conflict)
- Per-agent-type configuration (PMT/Utility/Financial frameworks)
- Backward compatibility with existing experiments

## Plan Reference

Full plan: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md` (Part 14-15)

---

## Subtasks

### 040-A: AgentTypeRegistry ✅ COMPLETE

- **assigned_to**: Claude Code
- **status**: completed
- **scope**: `broker/config/agent_types/`
- **tests_passed**: 38

**Files Created**:
- `broker/config/agent_types/base.py` - AgentTypeDefinition, ConstructDefinition, etc.
- `broker/config/agent_types/registry.py` - AgentTypeRegistry with YAML loading
- `broker/config/agent_types/__init__.py` - Module exports
- `tests/test_agent_type_registry.py` - 38 unit tests

**Key Features**:
- Type registration and lookup
- YAML loading with inheritance support
- PsychologicalFramework enum (PMT, UTILITY, FINANCIAL)
- Default registry with household types

---

### 040-B: UnifiedContextBuilder 🔄 IN PROGRESS

- **assigned_to**: Codex
- **status**: completed
- **scope**: `broker/core/unified_context_builder.py`

**Requirements**:
```python
class UnifiedContextBuilder:
    def __init__(
        self,
        agents: Dict[str, Any],
        mode: str = "single_agent",  # "single_agent" | "multi_agent"
        enable_social: bool = False,
        enable_multi_type: bool = False,
        ...
    ):
```

**Done When**:
- [ ] SA mode works with default providers
- [ ] MA mode adds AgentTypeContextProvider
- [ ] `enable_social` toggles SocialProvider
- [ ] `TieredContextBuilder` alias for backward compatibility
- [ ] Tests pass (`tests/test_unified_context_builder.py`)

---

### 040-C: AgentInitializer 🔄 IN PROGRESS

- **assigned_to**: Gemini
- **status**: in_progress
- **scope**: `broker/core/agent_initializer.py`

**Requirements**:
```python
def initialize_agents(
    mode: str,  # "survey" | "csv" | "synthetic"
    path: Path,
    config: Dict[str, Any],
    enrichers: Optional[Dict[str, Enricher]] = None,
    seed: int = 42,
) -> Tuple[List[AgentProfile], Dict[str, List[MemoryTemplate]], Dict]:
```

**Done When**:
- [ ] Survey mode loads PMT scores from Excel
- [ ] CSV mode loads basic attributes
- [ ] Synthetic mode generates test agents
- [ ] Enrichers can be applied
- [ ] Tests pass (`tests/test_agent_initializer.py`)

---

### 040-D: PsychometricFramework 🔄 IN PROGRESS

- **assigned_to**: Codex
- **status**: in_progress
- **scope**: `broker/core/psychometric.py`

**Requirements**:
```python
class PsychologicalFramework(ABC):
    def get_constructs(self) -> Dict[str, ConstructDef]: ...
    def validate_coherence(self, appraisals: Dict) -> ValidationResult: ...

class PMTFramework(PsychologicalFramework): ...
class UtilityFramework(PsychologicalFramework): ...
class FinancialFramework(PsychologicalFramework): ...
```

**Done When**:
- [ ] PMT framework with coherence validation
- [ ] Utility framework for government
- [ ] Financial framework for insurance
- [ ] Factory function `get_framework(name)`
- [ ] Tests pass (`tests/test_psychometric.py`)

---

### 040-E: TypeValidator 🔄 IN PROGRESS

- **assigned_to**: Gemini
- **status**: completed
- **scope**: `broker/governance/type_validator.py`

**Requirements**:
```python
class TypeValidator:
    def validate(
        self,
        skill_name: str,
        agent_type: str,
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
```

**Done When**:
- [ ] Skill eligibility check by agent type
- [ ] Per-type validation rules applied
- [ ] Integrated with `validate_all`
- [ ] Tests pass (`tests/test_type_validator.py`)

---

## Verification

After all subtasks complete:

```bash
# Run all new tests
pytest tests/test_agent_type_registry.py -v
pytest tests/test_unified_context_builder.py -v
pytest tests/test_agent_initializer.py -v
pytest tests/test_psychometric.py -v
pytest tests/test_type_validator.py -v

# Regression tests
pytest tests/test_governance_rules.py -v
pytest tests/test_config_schema.py -v

# Integration test (SA)
cd examples/single_agent_modular
python run_flood.py --years 3 --agents 10 --memory-engine unified
```

---

## Dependencies

```
040-A (AgentTypeRegistry) ✅
  ↓
040-B (UnifiedContextBuilder) ← depends on AgentTypeRegistry
040-D (PsychometricFramework) ← uses AgentTypeRegistry
  ↓
040-E (TypeValidator) ← depends on AgentTypeRegistry
  ↓
040-C (AgentInitializer) ← can use TypeValidator
```

---

## Notes

- Keep backward compatibility with existing SA experiments
- Do not modify `examples/single_agent/run_flood.py` or `agent_types.yaml`
- Test new features in `examples/single_agent_modular/` first
