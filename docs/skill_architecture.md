# Skill-Governed Architecture (v0.2)

## Overview

Version 0.2 introduces a **Skill-Governed Architecture** that elevates governance from action/tool-level to behavioral skill-level control.

---

## Architecture Comparison

### v0.1 (Action-Based) vs v0.2 (Skill-Governed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         v0.1 ACTION-BASED                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   LLM Agent                                                                 │
│       │                                                                     │
│       ▼ action_code: "1", "2", "3"...                                      │
│   ┌─────────────────────────────────┐                                      │
│   │     Governed Broker Layer       │                                      │
│   │  ┌─────────┐  ┌──────────────┐  │                                      │
│   │  │ Context │→ │  Validation  │  │  • Format check                      │
│   │  │ Builder │  │ (Schema+PMT) │  │  • PMT consistency only              │
│   │  └─────────┘  └──────────────┘  │                                      │
│   │           ↓                     │                                      │
│   │   ActionRequest → Execution    │                                      │
│   └─────────────────────────────────┘                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     v0.2 SKILL-GOVERNED                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   LLM Agent                                                                 │
│       │                                                                     │
│       ▼ skill_name: "buy_insurance", "elevate_house"...                    │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │              Governed Broker Layer                           │          │
│   │  ┌─────────┐  ┌────────────────┐  ┌─────────────────────┐   │          │
│   │  │ Model   │→ │ SkillProposal  │→ │   SkillRegistry     │   │          │
│   │  │ Adapter │  │ (abstract      │  │ (institutional      │   │          │
│   │  │         │  │  behavior)     │  │  charter)           │   │          │
│   │  └─────────┘  └────────────────┘  └─────────────────────┘   │          │
│   │                      ↓                                       │          │
│   │  ┌──────────────────────────────────────────────────────┐   │          │
│   │  │              Validation Pipeline                      │   │          │
│   │  │  Admissibility → Feasibility → Constraints → Safety  │   │          │
│   │  └──────────────────────────────────────────────────────┘   │          │
│   │                      ↓                                       │          │
│   │              ApprovedSkill → Execution                      │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Differences

| Aspect | v0.1 Action-Based | v0.2 Skill-Governed |
|--------|-------------------|---------------------|
| **LLM Output** | `action_code: "1"` | `skill_name: "buy_insurance"` |
| **Abstraction** | Low (numeric codes) | High (semantic names) |
| **Governance Unit** | Action / Tool | **Skill** (abstract behavior) |
| **Behavior Definition** | Hardcoded in engine | **SkillRegistry** (YAML config) |
| **Validation** | Format + PMT only | 5-stage pipeline |
| **Multi-LLM** | Manual parsing | **ModelAdapter** layer |
| **MCP Role** | Implicit | Explicit: execution substrate only |

---

## New Components

### 1. SkillProposal
```python
@dataclass
class SkillProposal:
    skill_name: str      # "buy_insurance", not "1"
    agent_id: str
    reasoning: Dict      # PMT appraisals
    confidence: float
```

### 2. SkillRegistry
Institutional charter defining:
- `skill_id`: Unique identifier
- `preconditions`: Required states
- `institutional_constraints`: Once-only, annual, exclusive
- `allowed_state_changes`: Effect scope
- `implementation_mapping`: Execution command

### 3. ModelAdapter
Thin layer for multi-LLM support:
- `OllamaAdapter`: Llama, Gemma, DeepSeek
- `OpenAIAdapter`: GPT-4, etc.

### 4. Validation Pipeline
```
SkillAdmissibilityValidator → Agent type has permission?
ContextFeasibilityValidator → Preconditions met?
InstitutionalConstraintValidator → Once-only, limits?
EffectSafetyValidator → Safe state changes?
PMTConsistencyValidator → Reasoning consistent?
```

---

## MCP Role Clarification

| MCP Does | MCP Does NOT |
|----------|--------------|
| ✅ Execution | ❌ Decision making |
| ✅ Sandbox | ❌ Expose to LLM |
| ✅ Logging | ❌ Governance |
| ✅ Tool access control | ❌ Validation |

> MCP = **Execution Substrate**, NOT governance unit

---

## Migration Guide

### Using Legacy API (v0.1)
```python
from broker import BrokerEngine, DecisionRequest
engine = BrokerEngine(...)
result = engine.process_step(agent_id, step_id, run_id, seed)
```

### Using Skill-Governed API (v0.2)
```python
from broker import SkillBrokerEngine, SkillRegistry, get_adapter
from validators import create_default_validators

registry = create_flood_adaptation_registry()
adapter = get_adapter("llama3.2:3b")
validators = create_default_validators()

engine = SkillBrokerEngine(
    skill_registry=registry,
    model_adapter=adapter,
    validators=validators,
    simulation_engine=sim,
    context_builder=ctx
)
result = engine.process_step(agent_id, step_id, run_id, seed, llm_invoke)
```

---

## Benefits

1. **Semantic Clarity**: `"buy_insurance"` vs `"1"`
2. **Institutional Governance**: Rules in YAML, not code
3. **Multi-LLM Ready**: Plug-in adapters
4. **Deeper Validation**: 5-stage vs 2-stage
5. **Auditable**: Skill-level traces
