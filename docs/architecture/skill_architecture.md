# Skill-Governed Architecture (v0.3)

## Overview

Version 0.3 adds **Multi-LLM Extensibility** with YAML-driven configuration.

---

## v0.3 Architecture (Multi-LLM Ready)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CONFIGURATION LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ providers.yaml   │  │ domain.yaml      │  │ skill_registry   │          │
│  │ (Multi-LLM)      │  │ (State/Actions)  │  │ .yaml            │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
└───────────┼───────────────────┼───────────────────────┼─────────────────────┘
            │                    │                       │
            ▼                    ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LLM PROVIDER LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    LLMProviderRegistry                              │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │     │
│  │  │OllamaProvider│ │OpenAIProvider│ │MoreProviders│                 │     │
│  │  │(llama,gemma) │ │(gpt-4,gpt-3)│  │(anthropic)  │                 │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                 │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                    │                                                         │
│  ┌─────────────────┼───────────────────────────────────────────────────┐    │
│  │                 ▼                                                    │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │    │
│  │  │   RateLimiter   │  │  AsyncAdapter   │  │   RetryHandler      │  │    │
│  │  │(token bucket)   │  │ (batch invoke)  │  │(exp. backoff)       │  │    │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼ LLM Response
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GOVERNED BROKER LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐                                                       │
│  │DomainConfigLoader│ ←── domain.yaml                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │   ModelAdapter   │→ │  SkillProposal   │→ │     SkillRegistry        │   │
│  │  (UnifiedAdapter)│  │ (skill_name,     │  │ (from_domain_config())   │   │
│  │  + preprocessor  │  │  reasoning)      │  │                          │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
│                                │                                             │
│                                ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    VALIDATION PIPELINE                                 │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────────┐  │  │
│  │  │Admissibility│→│Feasibility │→│Constraints │→│ EffectSafety    │  │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └─────────────────┘  │  │
│  │                                                          │             │  │
│  │  ┌────────────────┐  ┌────────────────┐                  ▼             │  │
│  │  │PMTConsistency  │→ │ Uncertainty    │→→→→→→ APPROVED / REJECTED     │  │
│  │  └────────────────┘  └────────────────┘                               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                │                                             │
│           ┌────────────────────┴───────────────────────┐                    │
│           ▼                                            ▼                    │
│  ┌──────────────────┐                        ┌──────────────────┐          │
│  │  ValidatorFactory │ ←── Dynamic Load      │   AuditWriter    │          │
│  │ (from YAML config)│                       │ (skill_audit.jsonl)│        │
│  └──────────────────┘                        └──────────────────┘          │
└────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼ Approved Skill (SYSTEM-ONLY)
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SIMULATION / WORLD LAYER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ SimulationEngine │  │   Agent State    │  │   Environment    │          │
│  │ (ExecutionInterface)│ (elevated,       │  │ (flood_event,    │          │
│  │                   │  │  has_insurance)  │  │  year, memory)   │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## v0.3 New Components

| Component | File | Purpose |
|-----------|------|---------|
| `LLMProviderRegistry` | `interfaces/llm_provider.py` | Multi-LLM management |
| `OllamaProvider` | `providers/ollama.py` | Local model support |
| `OpenAIProvider` | `providers/openai_provider.py` | Cloud API support |
| `RateLimiter` | `providers/rate_limiter.py` | API rate control |
| `AsyncAdapter` | `broker/async_adapter.py` | Concurrent processing |
| `DomainConfigLoader` | `config/loader.py` | YAML domain loading |
| `ValidatorFactory` | `validators/factory.py` | Dynamic validator loading |

---

                    ┌────────────────────────────────────────┘
                    │ FEEDBACK: State updates flow back
                    ▼
              [Next cycle: Context Builder reads updated state]
```

---

## Context vs Skill

| Concept | Type | Direction |
|---------|------|-----------|
| Environment | Context | World → LLM |
| Memory | Context | World → LLM |
| Social | Context | World → LLM |
| Agent State | Context | World → LLM |
| **Skill** | **Action** | **LLM → World** |

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
