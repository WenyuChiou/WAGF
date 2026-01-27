# Integration Tests - Task-038

> **Test Suite**: SA/MA Flood Adaptation Integration Tests
> **Total Tests**: 135
> **Status**: All Passing

---

## Overview

This test suite verifies that Single-Agent (SA) and Multi-Agent (MA) flood adaptation experiments work correctly with the SDK-Broker architecture. The tests cover:

1. **Parsing** - LLM response parsing (JSON, keyword, naked digit)
2. **Skill Registry** - Skill proposal and selection mechanism
3. **Validators** - Agent-type-based validator assignment
4. **Environment** - Physical simulation coupling
5. **Audit** - Complete trace recording
6. **Memory** - Symbolic memory with novelty-first surprise
7. **Real LLM** - Ollama integration with Llama 3.2 3B

---

## Test Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Test Hierarchy                                │
├─────────────────────────────────────────────────────────────────┤
│  Level 1: Unit Tests (Fast, Isolated)                           │
│    - Parsing utilities                                          │
│    - Skill registry                                             │
│    - Validator logic                                            │
│    - Memory scoring                                             │
├─────────────────────────────────────────────────────────────────┤
│  Level 2: Integration Tests (Component coupling)                │
│    - Broker engine + parser                                     │
│    - Validator + governance rules                               │
│    - Memory + context builder                                   │
│    - Environment + lifecycle hooks                              │
├─────────────────────────────────────────────────────────────────┤
│  Level 3: E2E Smoke Tests (Full pipeline)                       │
│    - SA: 1 agent, 3 years, mock LLM                            │
│    - MA: 5 agents, 3 years, mock LLM                           │
│    - Real LLM: 1 agent, 1 year, Llama 3.2 3B                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Test Coverage by Phase

| Phase | File | Tests | Description |
|-------|------|-------|-------------|
| 1-2 | `test_sa_parsing.py` | 18 | SA response parsing |
| 3 | `test_sa_skill_registry.py` | 19 | SA skill registry |
| 4 | `test_sa_validators.py` | 12 | SA validator logic |
| 5-6 | `test_sa_environment.py` | 20 | SA environment & lifecycle |
| 7 | `test_sa_e2e_smoke.py` | 7 | SA E2E with mock LLM |
| 8-9 | `test_ma_memory.py` | 26 | MA memory & scoring |
| 10 | `test_ma_environment.py` | 16 | MA environment & lifecycle |
| 11 | `test_real_llm_smoke.py` | 6 | Real LLM (Ollama) |
| 12 | `test_ma_memory_v4_integration.py` | 11 | Memory V4 SDK integration |
| **Total** | | **135** | |

---

## Verified Requirements

### Original Requirements (Task-038)

| ID | Requirement | Status |
|----|-------------|--------|
| R1 | Parse JSON with delimiters | ✅ Verified |
| R2 | Parse VL/L/M/H/VH labels | ✅ Verified |
| R3 | Skill registry loads from YAML | ✅ Verified |
| R4 | Validators block invalid decisions | ✅ Verified |
| R5 | Environment lifecycle hooks work | ✅ Verified |
| R6 | Audit traces complete | ✅ Verified |
| R7 | MA memory persistence | ✅ Verified |
| R8 | Social context propagation | ✅ Verified |

### Extended Requirements (Phase 11-12)

| ID | Requirement | Status |
|----|-------------|--------|
| R9 | Real LLM integration (Ollama) | ✅ Verified |
| R10 | Memory V4 SDK integration | ✅ Verified |

---

## SDK Independence Verification

```python
# ✅ CORRECT: Import from SDK
from governed_ai_sdk.agents import BaseAgent, AgentProtocol
from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory
from governed_ai_sdk.v1_prototype.memory.symbolic_core import Sensor

# ❌ WRONG: Import from legacy paths
from agents.base_agent import BaseAgent  # Deprecated
```

**Dependency Direction**:
- SDK → Broker: **0 violations** (SDK is independent)
- Broker → SDK: **23 imports** (correct direction)

---

## How to Run

### Full Suite

```bash
pytest tests/integration/ -v --tb=short
```

### By Phase

```bash
# Phase 1-2: SA Parsing
pytest tests/integration/test_sa_parsing.py -v

# Phase 3: SA Skill Registry
pytest tests/integration/test_sa_skill_registry.py -v

# Phase 4: SA Validators
pytest tests/integration/test_sa_validators.py -v

# Phase 5-6: SA Environment
pytest tests/integration/test_sa_environment.py -v

# Phase 7: SA E2E
pytest tests/integration/test_sa_e2e_smoke.py -v

# Phase 8-9: MA Memory
pytest tests/integration/test_ma_memory.py -v

# Phase 10: MA Environment
pytest tests/integration/test_ma_environment.py -v

# Phase 11: Real LLM (requires Ollama)
pytest tests/integration/test_real_llm_smoke.py -v

# Phase 12: Memory V4 Integration
pytest tests/integration/test_ma_memory_v4_integration.py -v
```

### Skip Slow Tests

```bash
pytest tests/integration/ -v -m "not slow"
```

---

## Test Files Reference

### SA Tests

| File | Purpose | Key Classes |
|------|---------|-------------|
| `test_sa_parsing.py` | Response parsing | `UnifiedAdapter` |
| `test_sa_skill_registry.py` | Skill loading | `SkillRegistry` |
| `test_sa_validators.py` | Validation logic | `AgentValidator` |
| `test_sa_environment.py` | Environment setup | `ResearchSimulation` |
| `test_sa_e2e_smoke.py` | Full pipeline | `SkillBrokerEngine` |

### MA Tests

| File | Purpose | Key Classes |
|------|---------|-------------|
| `test_ma_memory.py` | Memory operations | `SymbolicMemory` |
| `test_ma_environment.py` | Multi-agent env | `TieredEnvironment` |
| `test_ma_memory_v4_integration.py` | V4 integration | `HouseholdAgent` |

### Real LLM Tests

| File | Purpose | Key Classes |
|------|---------|-------------|
| `test_real_llm_smoke.py` | Ollama integration | `OllamaProvider` |

---

## Fixtures

### Mock LLM

```python
@pytest.fixture
def mock_llm():
    """Deterministic mock LLM for testing."""
    return MockLLM(responses={
        "year_1": '<<<DECISION_START>>>{"decision": 1}<<<DECISION_END>>>',
        "year_2": '<<<DECISION_START>>>{"decision": 2}<<<DECISION_END>>>',
    })
```

### Symbolic Memory

```python
@pytest.fixture
def symbolic_memory():
    """Pre-configured symbolic memory."""
    sensors = [
        {"path": "flood_depth_m", "name": "FLOOD", "bins": [
            {"label": "SAFE", "max": 0.3},
            {"label": "MINOR", "max": 1.0},
            {"label": "SEVERE", "max": 99.0}
        ]}
    ]
    return SymbolicMemory(sensors, arousal_threshold=0.5)
```

### Ollama Provider

```python
@pytest.fixture
def ollama_provider():
    """Real LLM provider (skips if unavailable)."""
    config = LLMConfig(model="llama3.2:3b", temperature=0.7, max_tokens=512)
    provider = OllamaProvider(config, base_url="http://localhost:11434")
    if not provider.validate_connection():
        pytest.skip("Ollama not available")
    return provider
```

---

## Audit Trace Schema

All tests verify that audit traces contain the required fields:

```json
{
  "run_id": "string",
  "step_id": "int",
  "timestamp": "ISO-8601",
  "year": "int",
  "agent_id": "string",
  "agent_type": "string",
  "input": "LLM prompt",
  "raw_output": "LLM response",
  "skill_proposal": {
    "skill_name": "string",
    "reasoning": {
      "threat_appraisal": {"label": "VL|L|M|H|VH"},
      "coping_appraisal": {"label": "VL|L|M|H|VH"}
    },
    "parse_layer": "json|keyword|naked_digit"
  },
  "validation_result": {
    "outcome": "APPROVED|BLOCKED|WARNING",
    "issues": []
  },
  "approved_skill": {
    "skill_name": "string|null"
  },
  "state_before": {},
  "state_after": {},
  "retry_count": "int",
  "validated": "bool"
}
```

---

## Known Limitations

1. **Real LLM Tests**: Require Ollama running locally (`http://localhost:11434`)
2. **Mock LLM**: Does not test actual LLM behavior, only parsing logic
3. **Social Network**: MA social tests use simplified ring topology

---

## Maintenance

When adding new tests:

1. Follow the naming convention: `test_<phase>_<component>.py`
2. Use fixtures from `conftest.py` when available
3. Verify SDK imports (not legacy paths)
4. Add test counts to this README

---

## Related Documentation

- [SDK README](../../governed_ai_sdk/README.md) - SDK architecture and usage
- [SA Case Design](../../examples/single_agent/CASE_DESIGN.md) - Single-agent experiment design
- [MA Case Design](../../examples/multi_agent/CASE_DESIGN.md) - Multi-agent experiment design
