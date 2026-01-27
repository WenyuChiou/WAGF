# Task-038: SA/MA Flood Adaptation Integration Test Plan

> **Date**: 2026-01-26
> **Status**: PLANNING
> **Priority**: HIGH
> **Depends On**: Task-037 (SDK-Broker Architecture Separation - COMPLETED)

---

## Executive Summary

Comprehensive verification that SA (Single-Agent) and MA (Multi-Agent) flood adaptation experiments work correctly with the new SDK-Broker architecture. Focus areas:

1. **Parsing** - LLM response parsing works correctly
2. **Skill Registry** - Skill proposal and selection mechanism
3. **Validators** - Agent-type-based validator assignment
4. **Environment** - Physical simulation coupling
5. **Audit** - Complete trace recording (parse, validation, reasoning, VL/L/M/H/VH scoring)
6. **Memory & Social** - Memory module and social network in MA

**Strategy**: Start with SA, then extend to MA. Use new SDK modules, not legacy dependencies.

---

## Test Architecture Overview

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
│    - Real LLM: 1 agent, 1 year (optional)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: SA Parsing Tests

### 1.1 Unit Tests - Response Parsing

**File**: `tests/test_sa_parsing.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `SA-P01` | Parse JSON with delimiters | `<<<DECISION_START>>>{"decision": 1}<<<DECISION_END>>>` | skill=buy_insurance |
| `SA-P02` | Parse numeric skill mapping | `{"decision": "2"}` | skill=elevate_house |
| `SA-P03` | Parse VL/L/M/H/VH labels | `{"threat_appraisal": {"label": "VH"}}` | TP_LABEL=VH |
| `SA-P04` | Parse reasoning field | `{"reasoning": {"threat": "High..."}}` | reasoning dict extracted |
| `SA-P05` | Naked digit recovery | `buy_insurance\n\n1` | skill=buy_insurance |
| `SA-P06` | Qwen3 think tag stripping | `<think>...</think>{"decision": 1}` | JSON extracted |
| `SA-P07` | Case-insensitive keys | `{"DECISION": 1}` | skill extracted |
| `SA-P08` | Invalid JSON fallback | `I choose option 2` | skill=elevate_house (keyword) |

**Key Files**:
- `broker/utils/model_adapter.py` (UnifiedAdapter.parse_output)
- `broker/components/context_builder.py` (skill mapping)

### 1.2 Integration Tests - Parse Layer Tracking

**File**: `tests/test_sa_parse_integration.py`

**Test Cases**:

| Test ID | Description | Verify |
|---------|-------------|--------|
| `SA-PI01` | Parse layer recorded | `parse_layer` in trace is "json" or "keyword" |
| `SA-PI02` | Construct extraction | `threat_appraisal`, `coping_appraisal` in reasoning |
| `SA-PI03` | Retry on parse failure | retry_count increments, InterventionReport generated |
| `SA-PI04` | Dynamic skill map (elevated) | Elevated agent gets 3 options, not 4 |

---

## Phase 2: SA Skill Registry Tests

### 2.1 Unit Tests - Registry Operations

**File**: `tests/test_sa_skill_registry.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `SA-SR01` | Load from YAML | `skill_registry.yaml` | 4 skills loaded |
| `SA-SR02` | Get skill by ID | `get("buy_insurance")` | SkillDefinition returned |
| `SA-SR03` | Check eligibility | household + buy_insurance | True |
| `SA-SR04` | Check preconditions | elevated=True + elevate_house | blocked |
| `SA-SR05` | Get execution mapping | buy_insurance | "sim.buy_insurance" |

**Key Files**:
- `broker/components/skill_registry.py`
- `examples/single_agent/skill_registry.yaml`

### 2.2 Integration Tests - Skill Retrieval

**File**: `tests/test_sa_skill_retrieval_integration.py`

**Test Cases**:

| Test ID | Description | Verify |
|---------|-------------|--------|
| `SA-SRI01` | RAG retriever filters skills | Only relevant skills returned |
| `SA-SRI02` | Proposal contains metadata | `skill_name`, `reasoning`, `parse_layer` |
| `SA-SRI03` | ApprovedSkill has mapping | `execution_mapping` is callable |

---

## Phase 3: SA Validator Tests

### 3.1 Unit Tests - Validator Logic

**File**: `tests/test_sa_validators.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `SA-V01` | Tier 0 format check | Missing threat_appraisal | ValidationResult.warning |
| `SA-V02` | Tier 1 identity rule | elevated=True + elevate_house | BLOCKED |
| `SA-V03` | Tier 2 thinking rule (strict) | TP=VH + do_nothing | BLOCKED |
| `SA-V04` | Tier 2 thinking rule (relaxed) | TP=VH + do_nothing | WARNING (allowed) |
| `SA-V05` | Governance disabled | Any input | APPROVED |
| `SA-V06` | Multiple validators AND | All must pass for approval |

**Key Files**:
- `validators/agent_validator.py`
- `examples/single_agent/agent_types.yaml` (governance profiles)

### 3.2 Integration Tests - Validator Assignment

**File**: `tests/test_sa_validator_assignment.py`

**Test Cases**:

| Test ID | Description | Verify |
|---------|-------------|--------|
| `SA-VAI01` | Load validators from config | DomainConfigLoader returns validator names |
| `SA-VAI02` | Factory instantiation | ValidatorFactory creates correct validators |
| `SA-VAI03` | Agent-type specific rules | household gets household rules |
| `SA-VAI04` | Intervention report format | Contains rule_id, violation_summary, suggestion |

---

## Phase 4: SA Environment Integration

### 4.1 Unit Tests - Environment Operations

**File**: `tests/test_sa_environment.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `SA-E01` | Set flood event | year=1, flood=True | env["flood_occurred"]=True |
| `SA-E02` | Set flood depth | depth=2.0m | env["flood_depth_m"]=2.0 |
| `SA-E03` | Grant availability | year=2 | env["grant_available"]=True |
| `SA-E04` | Crisis event trigger | flood=True | env["crisis_event"]=True |

**Key Files**:
- `examples/single_agent/run_flood.py` (ResearchSimulation)
- `simulation/environment.py` (TieredEnvironment)

### 4.2 Integration Tests - Lifecycle Hooks

**File**: `tests/test_sa_lifecycle.py`

**Test Cases**:

| Test ID | Description | Verify |
|---------|-------------|--------|
| `SA-LI01` | pre_year sets flood | HazardModule called, flood_event set |
| `SA-LI02` | post_step updates state | Agent state changed after skill execution |
| `SA-LI03` | post_year calculates damage | Damage computed if flood occurred |
| `SA-LI04` | Memory updated post-year | Experience memory added |

---

## Phase 5: SA Audit Tests

### 5.1 Unit Tests - Audit Writer

**File**: `tests/test_sa_audit.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `SA-A01` | Write trace JSONL | Single trace | Valid JSON line |
| `SA-A02` | Required fields | trace | All fields present |
| `SA-A03` | Reasoning format | VL/L/M/H/VH | Labels validated |
| `SA-A04` | Intervention report | Blocked skill | rule_id in trace |

**Key Files**:
- `broker/components/audit_writer.py`

### 5.2 Audit Trace Schema

**Required Fields**:

```json
{
  "run_id": "string",
  "step_id": "int",
  "timestamp": "ISO-8601",
  "year": "int",
  "agent_id": "string",
  "agent_type": "string",

  "input": "LLM prompt text",
  "raw_output": "LLM raw response",

  "skill_proposal": {
    "skill_name": "string",
    "reasoning": {
      "threat_appraisal": {"label": "VL|L|M|H|VH", "reason": "..."},
      "coping_appraisal": {"label": "VL|L|M|H|VH", "reason": "..."}
    },
    "parse_layer": "json|keyword|naked_digit"
  },

  "validation_result": {
    "outcome": "APPROVED|BLOCKED|WARNING",
    "issues": [
      {
        "rule_id": "string",
        "severity": "ERROR|WARNING",
        "message": "string"
      }
    ]
  },

  "approved_skill": {
    "skill_name": "string|null",
    "execution_mapping": "string|null"
  },

  "state_before": {"elevated": false, "has_insurance": false},
  "state_after": {"elevated": true, "has_insurance": false},

  "retry_count": "int",
  "validated": "bool"
}
```

### 5.3 Integration Tests - Complete Audit Trail

**File**: `tests/test_sa_audit_integration.py`

**Test Cases**:

| Test ID | Description | Verify |
|---------|-------------|--------|
| `SA-AI01` | Full trace captured | All required fields present |
| `SA-AI02` | Parse info in trace | `parse_layer`, `skill_proposal` recorded |
| `SA-AI03` | Validation in trace | `validation_result`, `issues` recorded |
| `SA-AI04` | State changes in trace | `state_before`, `state_after` differ |
| `SA-AI05` | Retry captured | Multiple traces for retried decisions |

---

## Phase 6: SA E2E Smoke Test

### 6.1 Mock LLM E2E Test

**File**: `tests/test_sa_e2e_smoke.py`

**Setup**:
```python
# Mock LLM returns deterministic responses
mock_responses = {
    "year_1": '<<<DECISION_START>>>{"decision": 1, "threat_appraisal": {"label": "H"}}<<<DECISION_END>>>',
    "year_2": '<<<DECISION_START>>>{"decision": 2, "threat_appraisal": {"label": "VH"}}<<<DECISION_END>>>',
    "year_3": '<<<DECISION_START>>>{"decision": 4, "threat_appraisal": {"label": "L"}}<<<DECISION_END>>>'
}
```

**Test Cases**:

| Test ID | Description | Setup | Verify |
|---------|-------------|-------|--------|
| `SA-E2E01` | 3-year simulation | 1 agent, mock LLM | Completes without error |
| `SA-E2E02` | Skill execution | buy_insurance Y1 | has_insurance=True |
| `SA-E2E03` | Audit file created | output_dir | traces.jsonl exists |
| `SA-E2E04` | All traces valid | Read JSONL | All lines parse as JSON |
| `SA-E2E05` | State progression | 3 years | State changes recorded |

---

## Phase 7: MA Memory Module Tests

### 7.1 Unit Tests - Symbolic Memory

**File**: `tests/test_ma_symbolic_memory.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `MA-M01` | Sensor quantization | flood_depth=2.0 | "FLOOD:MODERATE" |
| `MA-M02` | Signature computation | multi-sensor state | 16-char hex |
| `MA-M03` | Novelty first | First observation | surprise=1.0 |
| `MA-M04` | Repeated signature | Same state twice | surprise < 1.0 |
| `MA-M05` | System determination | surprise=0.8 | "SYSTEM_2" |
| `MA-M06` | Trace captured | observe() | trace has quantized_sensors |

**Key Files**:
- `governed_ai_sdk/v1_prototype/memory/symbolic_core.py`
- `governed_ai_sdk/v1_prototype/memory/symbolic.py`

### 7.2 Unit Tests - Memory Scoring

**File**: `tests/test_ma_memory_scoring.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `MA-MS01` | FloodMemoryScorer | flood context | flood_relevance > 0 |
| `MA-MS02` | Crisis booster | crisis=True | emotional_weight boosted |
| `MA-MS03` | Retrieve top-k | k=3 | 3 memories returned |
| `MA-MS04` | Score components | any | components dict returned |

**Key Files**:
- `governed_ai_sdk/v1_prototype/memory/scoring.py`
- `broker/components/memory_engine.py`

### 7.3 Integration Tests - Memory Engine

**File**: `tests/test_ma_memory_integration.py`

**Test Cases**:

| Test ID | Description | Verify |
|---------|-------------|--------|
| `MA-MI01` | Engine factory | Creates correct engine type |
| `MA-MI02` | Store memory | Memory persisted |
| `MA-MI03` | Retrieve with scoring | Scored results returned |
| `MA-MI04` | Memory in context | Retrieved memories in LLM prompt |

---

## Phase 8: MA Social Network Tests

### 8.1 Unit Tests - Social Graph

**File**: `tests/test_ma_social_network.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `MA-S01` | Create spatial graph | agent positions | Graph with edges |
| `MA-S02` | Create ring graph | k=4 | Each node has 4 neighbors |
| `MA-S03` | Get neighbors | agent_id | List of neighbor IDs |
| `MA-S04` | Radius-based | radius=3.0 | Nearby agents connected |

**Key Files**:
- `examples/multi_agent/environment/social_network.py`

### 8.2 Unit Tests - Interaction Hub

**File**: `tests/test_ma_interaction_hub.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `MA-IH01` | Get gossip | agent with neighbors | List of gossip strings |
| `MA-IH02` | Visible neighbor actions | neighbors with actions | elevated_pct, insured_pct |
| `MA-IH03` | Social context | agent_id | Combined social info |

**Key Files**:
- `broker/components/interaction_hub.py`

### 8.3 Integration Tests - Social in Context

**File**: `tests/test_ma_social_integration.py`

**Test Cases**:

| Test ID | Description | Verify |
|---------|-------------|--------|
| `MA-SI01` | Social in context | context["local"]["social"] populated |
| `MA-SI02` | Gossip in prompt | Neighbor mentions in LLM prompt |
| `MA-SI03` | Observable actions | Visible actions affect TP/CP |

---

## Phase 9: MA Environment & Lifecycle

### 9.1 Unit Tests - Tiered Environment

**File**: `tests/test_ma_environment.py`

**Test Cases**:

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| `MA-E01` | Global state | subsidy_rate=0.5 | env.global_state["subsidy_rate"]=0.5 |
| `MA-E02` | Local state | agent flood depth | env.local_states[agent_id] |
| `MA-E03` | Institutional | govt decision | env.institutions["government"] |
| `MA-E04` | Policy broadcast | post_step | households see new rates |

**Key Files**:
- `examples/multi_agent/environment/core.py`

### 9.2 Integration Tests - MA Lifecycle

**File**: `tests/test_ma_lifecycle.py`

**Test Cases**:

| Test ID | Description | Verify |
|---------|-------------|--------|
| `MA-LI01` | Tier order | Institutional → Household |
| `MA-LI02` | Policy propagation | Subsidy change visible to households |
| `MA-LI03` | Damage calculation | Flood damage computed per agent |
| `MA-LI04` | Memory consolidation | Post-year memories added |

---

## Phase 10: MA E2E Smoke Test

### 10.1 Mock LLM E2E Test

**File**: `tests/test_ma_e2e_smoke.py`

**Setup**:
```python
# 5 households + 1 government + 1 insurance
agents = create_test_agents(n_households=5)
mock_llm = MockLLM(responses={
    "government": {"decision": "increase_subsidy"},
    "insurance": {"decision": "maintain_premium"},
    "household_*": {"decision": 1, "threat_appraisal": {"label": "H"}}
})
```

**Test Cases**:

| Test ID | Description | Setup | Verify |
|---------|-------------|-------|--------|
| `MA-E2E01` | 3-year simulation | 5 agents, mock LLM | Completes without error |
| `MA-E2E02` | Tier ordering | Check trace | Govt before households |
| `MA-E2E03` | Social context | Check trace | Gossip in context |
| `MA-E2E04` | Memory across years | Year 3 | Year 1 memories available |
| `MA-E2E05` | Policy propagation | Govt changes rate | Household sees change |
| `MA-E2E06` | Audit complete | Check traces | All agents have traces |

---

## Implementation Order

### Week 1: SA Foundation

1. **Day 1-2**: Parsing tests (SA-P*, SA-PI*)
2. **Day 3**: Skill registry tests (SA-SR*, SA-SRI*)
3. **Day 4-5**: Validator tests (SA-V*, SA-VAI*)

### Week 2: SA Integration & E2E

4. **Day 6**: Environment tests (SA-E*, SA-LI*)
5. **Day 7-8**: Audit tests (SA-A*, SA-AI*)
6. **Day 9-10**: E2E smoke tests (SA-E2E*)

### Week 3: MA Foundation

7. **Day 11-12**: Memory tests (MA-M*, MA-MS*, MA-MI*)
8. **Day 13-14**: Social tests (MA-S*, MA-IH*, MA-SI*)

### Week 4: MA Integration & E2E

9. **Day 15-16**: Environment & lifecycle (MA-E*, MA-LI*)
10. **Day 17-18**: E2E smoke tests (MA-E2E*)

---

## Key Files to Create/Modify

### New Test Files

| File | Purpose |
|------|---------|
| `tests/integration/test_sa_parsing.py` | SA parsing unit tests |
| `tests/integration/test_sa_skill_registry.py` | SA skill registry tests |
| `tests/integration/test_sa_validators.py` | SA validator tests |
| `tests/integration/test_sa_environment.py` | SA environment tests |
| `tests/integration/test_sa_audit.py` | SA audit tests |
| `tests/integration/test_sa_e2e_smoke.py` | SA E2E smoke test |
| `tests/integration/test_ma_memory.py` | MA memory tests |
| `tests/integration/test_ma_social.py` | MA social network tests |
| `tests/integration/test_ma_environment.py` | MA environment tests |
| `tests/integration/test_ma_e2e_smoke.py` | MA E2E smoke test |

### Test Fixtures

| File | Purpose |
|------|---------|
| `tests/fixtures/mock_llm.py` | Deterministic mock LLM |
| `tests/fixtures/sample_agents.yaml` | Test agent configurations |
| `tests/fixtures/sample_skills.yaml` | Test skill registry |
| `tests/fixtures/sample_responses.json` | LLM response samples |

---

## SDK Dependency Verification

Before each test phase, verify correct imports:

```python
# ✅ CORRECT: Import from SDK
from governed_ai_sdk.agents import BaseAgent, AgentProtocol
from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory
from governed_ai_sdk.v1_prototype.memory.symbolic_core import Sensor

# ❌ WRONG: Import from legacy
from agents.base_agent import BaseAgent  # Deprecated
from broker.components.symbolic_context import Sensor  # Deprecated
```

---

## Success Criteria

### SA Tests

- [ ] All SA-P* parsing tests pass
- [ ] All SA-SR* skill registry tests pass
- [ ] All SA-V* validator tests pass
- [ ] All SA-E* environment tests pass
- [ ] All SA-A* audit tests pass
- [ ] SA E2E smoke test completes with valid audit trail

### MA Tests

- [ ] All MA-M* memory tests pass
- [ ] All MA-S* social tests pass
- [ ] All MA-E* environment tests pass
- [ ] MA E2E smoke test completes with:
  - Memory across years
  - Social context in prompts
  - Policy propagation from institutions
  - Complete audit trail

### Architecture

- [ ] No imports from deprecated paths without warnings
- [ ] All tests use SDK modules directly
- [ ] No SDK → Broker dependencies

---

## Verification Commands

```bash
# Phase 1: SA Parsing
pytest tests/integration/test_sa_parsing.py -v

# Phase 2: SA Skill Registry
pytest tests/integration/test_sa_skill_registry.py -v

# Phase 3: SA Validators
pytest tests/integration/test_sa_validators.py -v

# Phase 4-5: SA Environment & Audit
pytest tests/integration/test_sa_environment.py tests/integration/test_sa_audit.py -v

# Phase 6: SA E2E
pytest tests/integration/test_sa_e2e_smoke.py -v

# Phase 7-8: MA Memory & Social
pytest tests/integration/test_ma_memory.py tests/integration/test_ma_social.py -v

# Phase 9-10: MA Environment & E2E
pytest tests/integration/test_ma_environment.py tests/integration/test_ma_e2e_smoke.py -v

# Full Suite
pytest tests/integration/ -v --tb=short
```

---

## Phase 11: Real LLM Test (Llama 3.2 3B)

### 11.1 Real LLM E2E Test

**File**: `tests/integration/test_real_llm_smoke.py`

**Prerequisites**:
- Ollama running locally: `http://localhost:11434`
- Model pulled: `ollama pull llama3.2:3b`

**Setup**:
```python
from providers.ollama import OllamaProvider
from interfaces.llm_provider import LLMConfig

config = LLMConfig(model="llama3.2:3b", temperature=0.7, max_tokens=512)
provider = OllamaProvider(config, base_url="http://localhost:11434")
```

**Test Cases**:

| Test ID | Description | Setup | Verify |
|---------|-------------|-------|--------|
| `RL-01` | Ollama connection | Check endpoint | `validate_connection()` returns True |
| `RL-02` | Parse real response | 1 decision prompt | SkillProposal extracted |
| `RL-03` | VL/L/M/H/VH format | Real response | Labels in valid set |
| `RL-04` | 1-year E2E | 1 agent, real LLM | Decision + audit trace |

**Key Files**:
- `providers/ollama.py` (OllamaProvider)
- `interfaces/llm_provider.py` (LLMConfig)

---

## Phase 12: Memory V4 Integration Test

### 12.1 HouseholdAgent Memory V4 Integration

**File**: `tests/integration/test_ma_memory_v4_integration.py`

**Purpose**: Verify `HouseholdAgent._init_memory_v4()` correctly initializes SDK's `SymbolicMemory`

**Test Cases**:

| Test ID | Description | Setup | Verify |
|---------|-------------|-------|--------|
| `MV4-01` | Init symbolic memory | engine="symbolic" | Returns SymbolicMemory |
| `MV4-02` | Sensors configured | Flood sensors | Quantizes flood_depth correctly |
| `MV4-03` | Arousal threshold | threshold=0.5 | System switching at 0.5 |
| `MV4-04` | Memory in agent context | observe() called | Trace in agent context |
| `MV4-05` | Surprise across years | Multi-year | Repeated states have lower surprise |

**Key Files**:
- `examples/multi_agent/ma_agents/household.py` (`_init_memory_v4()`)
- `governed_ai_sdk/v1_prototype/memory/symbolic.py` (SymbolicMemory)

---

## Updated Success Criteria

### SA Tests (Phases 1-6) ✅ COMPLETE

- [x] All SA-P* parsing tests pass (18 tests)
- [x] All SA-SR* skill registry tests pass (19 tests)
- [x] All SA-V* validator tests pass (12 tests)
- [x] All SA-E* environment tests pass (20 tests)
- [x] SA E2E smoke test completes (7 tests)

### MA Tests (Phases 7-10) ✅ COMPLETE

- [x] All MA-M* memory tests pass (26 tests)
- [x] All MA-E* environment tests pass (16 tests)
- [x] MA E2E smoke test completes with:
  - Memory across years
  - Social context in prompts
  - Policy propagation from institutions
  - Complete audit trail

### Real LLM Tests (Phase 11) ✅ COMPLETE

- [x] Ollama connection works
- [x] Parse real Llama 3.2 3B response (6 tests)
- [x] 1-year E2E with real LLM

### Memory V4 Integration (Phase 12) ✅ COMPLETE

- [x] `_init_memory_v4()` creates SymbolicMemory (11 tests)
- [x] Flood sensors correctly configured
- [x] Multi-year surprise detection works

---

## Phase 13: Comprehensive Documentation

### 13.1 SDK README (Update)

**File**: `governed_ai_sdk/README.md`

**Contents**:
1. **Architecture Overview** - SDK vs Broker separation diagram
2. **Core Modules**:
   - `PolicyEngine` - Stateless rule verification with XAI counterfactuals
   - `SymbolicMemory` - O(1) state signature lookup, novelty-first surprise
   - `EntropyCalibrator` - Governance calibration metrics
3. **Independence** - pip installable, no broker dependencies
4. **Quick Start** - Complete working examples
5. **Integration with Broker** - How to use SDK in broker-based applications

### 13.2 Integration Tests README

**File**: `tests/integration/README.md`

**Contents**:
1. **Test Coverage Summary** (135 tests)
2. **Phase Breakdown** (1-12)
3. **Verified Requirements** (8 original + 2 new)
4. **How to Run** - Commands for each phase
5. **Architecture Independence Verification**

### 13.3 SA Case Design Documentation

**File**: `examples/single_agent/CASE_DESIGN.md`

**Contents**:
1. **PMT-Based Decision Framework**
   - 5 Constructs: TP, CP, SP, SC, PA
   - VL/L/M/H/VH scoring format
2. **Pipeline Architecture**
   - Parse → Validate → Execute → Audit
3. **Governance Rules**
   - Tier 0: Format check
   - Tier 1: Identity rules
   - Tier 2: Thinking rules
4. **Memory System** - Human-centric memory engine

### 13.4 MA Case Design Documentation

**File**: `examples/multi_agent/CASE_DESIGN.md`

**Contents**:
1. **Multi-Agent Architecture**
   - Tier ordering: Institutional → Household
   - Environment: Global/Local/Social state
2. **Social Network**
   - Spatial/Ring graph
   - Gossip propagation
   - Visible neighbor actions
3. **Memory V4 (SymbolicMemory)**
   - Sensor quantization
   - Novelty-first surprise detection
   - System 1/2 switching
4. **Institutional Agents**
   - Government: Subsidy adjustment
   - Insurance: Premium adjustment

---

## Notes

1. **Mock LLM Strategy**: Use deterministic responses to test logic, not LLM behavior
2. **Isolation**: Each test should be independent, use fixtures for setup
3. **Trace Verification**: Always verify audit trail captures complete information
4. **SDK-First**: All new code should import from SDK, not legacy paths
5. **Real LLM Tests**: Mark as `@pytest.mark.slow` and skip if Ollama unavailable

---

## Phase 14: SA Reproducibility Verification (Gemini CLI Task)

> **Target**: Gemini CLI
> **Goal**: Verify SA flood adaptation experiment can be reproduced end-to-end
> **Method**: Follow OpenSkills TDD process (RED-GREEN-REFACTOR)

### Task Description for Gemini CLI

```markdown
# SA Reproducibility Verification Task

## Context

You are verifying that the Single-Agent (SA) flood adaptation experiment
can be fully reproduced. This ensures the framework is correctly assembled
and all components work together.

## OpenSkills Process Reference

Read these files to understand the skill format:
- `.claude/skills/my-first-skill/SKILL.md` - Basic skill format
- `.claude/skills/my-first-skill/references/skill-format.md` - Format spec
- `.claude/skills/writing-plans/SKILL.md` - Plan writing skill

## TDD Verification Steps (RED-GREEN-REFACTOR)

### Step 1: RED - Verify baseline exists

Run the SA experiment with minimal configuration:

```bash
cd examples/single_agent
python run_flood.py --model llama3.2:3b --years 3 --agents 5 --verbose
```

**Expected outputs to verify**:
1. `results/llama3_2_3b_strict/simulation_log.csv` - Created
2. `results/llama3_2_3b_strict/raw/household_traces.jsonl` - Contains traces
3. Console shows year-by-year stats

### Step 2: GREEN - Verify all components work

Check each SA component:

| Component | File | Verification Command |
|-----------|------|---------------------|
| Parsing | `broker/utils/model_adapter.py` | Check `parse_layer` in traces |
| Skills | `examples/single_agent/skill_registry.yaml` | 4 skills loaded |
| Validators | `examples/single_agent/agent_types.yaml` | strict/relaxed modes |
| Memory | `broker/components/memory_engine.py` | Memory in context |
| Audit | `broker/components/audit_writer.py` | JSONL traces valid |

### Step 3: REFACTOR - Document any gaps

If any step fails, document:
1. **What failed** - Exact error message
2. **Root cause** - Which file/function
3. **Fix needed** - Specific change required

## Reproduction Checklist

- [ ] Environment setup: Python 3.10+, Ollama running
- [ ] Dependencies: `pip install -e .`
- [ ] Model available: `ollama pull llama3.2:3b`
- [ ] SA experiment runs without error
- [ ] Audit traces are valid JSON
- [ ] All 4 skills are available (buy_insurance, elevate_house, relocate, do_nothing)
- [ ] Governance rules applied (strict mode blocks extreme violations)
- [ ] Memory engine stores and retrieves experiences
- [ ] State changes tracked (elevated, has_insurance, relocated)

## Key Files to Understand

| File | Purpose |
|------|---------|
| `examples/single_agent/run_flood.py` | Main SA runner |
| `examples/single_agent/skill_registry.yaml` | Skill definitions |
| `examples/single_agent/agent_types.yaml` | Governance config |
| `broker/core/experiment.py` | ExperimentBuilder/Runner |
| `broker/utils/model_adapter.py` | UnifiedAdapter parsing |

## Output Artifacts

After verification, report:

1. **Reproducibility Status**: PASS/FAIL
2. **Test Summary**: Which components verified
3. **Issues Found**: Any gaps between docs and implementation
4. **CASE_DESIGN Alignment**: Does implementation match documented design?

## Alignment Check with CASE_DESIGN.md

Compare actual implementation with `examples/single_agent/CASE_DESIGN.md`:

| Documented | Actual | Match? |
|------------|--------|--------|
| 4 skills (buy, elevate, grant, nothing) | 4 skills (buy, elevate, relocate, nothing) | ⚠️ grant vs relocate |
| PMT VL/L/M/H/VH scoring | PMT VL/L/M/H/VH scoring | ✅ |
| Tier 0/1/2 governance | strict/relaxed profiles | ⚠️ Check mapping |
| Simple memory | Multiple engine types | ⚠️ Docs simplified |
```

### Gemini CLI Command

```bash
gemini -p "Read the task at '.claude/plans/cozy-roaming-perlis.md' section 'Phase 14: SA Reproducibility Verification'. Follow the OpenSkills TDD process to verify SA can be reproduced. Report your findings."
```

### Expected Gemini Output

1. **Environment Check**: Python, Ollama, dependencies
2. **Run SA Experiment**: Execute with real LLM
3. **Verify Outputs**: Check traces, logs, state changes
4. **CASE_DESIGN Alignment**: Compare docs vs implementation
5. **Reproducibility Report**: PASS/FAIL with details

---

## Phase 15: Update CASE_DESIGN.md (Post-Verification)

After Gemini verifies reproducibility, update documentation to match actual implementation:

### SA CASE_DESIGN.md Updates Needed

1. **Skills**: Change `apply_for_grant` → `relocate`
2. **Memory**: Document multiple engine types (window, importance, humancentric, hierarchical)
3. **Governance**: Add complete rule listing (5 thinking rules + 1 identity rule)
4. **Environment**: Document fixed vs prob flood modes

### Files to Update

| File | Changes |
|------|---------|
| `examples/single_agent/CASE_DESIGN.md` | Align skills, memory, governance |
| `governed_ai_sdk/README.md` | Already updated ✅ |
| `tests/integration/README.md` | Already created ✅ |
