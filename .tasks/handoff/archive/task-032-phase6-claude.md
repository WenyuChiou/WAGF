# Task-032 Phase 6: Documentation (Claude Code)

**Status**: 🔲 Blocked on Phase 5
**Assignee**: Claude Code
**Effort**: 4-5 hours
**Priority**: MEDIUM
**Prerequisite**: Phase 5 (Integration Tests) complete

---

## Git Branch

```bash
# After Phase 5 completes:
git checkout task-032-phase5
git checkout -b task-032-phase6
```

**Stacked PR Structure**:
```
main
 └── task-032-sdk-base (Phase 0)
      └── task-032-phase1
           └── task-032-phase2
                └── task-032-phase4a/4b
                     └── task-032-phase5
                          └── task-032-phase6 (this branch) ← DOCS
```

---

## Objective

Create comprehensive documentation for the GovernedAI SDK including quick start guide, architecture overview, API reference, and migration guide.

---

## Deliverables

### 1. `governed_ai_sdk/README.md`

```markdown
# GovernedAI SDK

Universal Cognitive Governance Middleware for Agent Frameworks.

## Overview

GovernedAI SDK provides "Cognitive Governance" (Identity & Thinking Rules) to ANY agent framework including LangChain, CrewAI, AutoGen, and custom implementations.

## Quick Start

### Installation

```bash
# From project root
pip install -e .
```

### Basic Usage

```python
from governed_ai_sdk.v1_prototype import GovernedAgent, PolicyRule, GovernanceTrace
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader

# 1. Define your agent
class MyAgent:
    def __init__(self):
        self.savings = 300

    def decide(self, context):
        return {"action": "buy_insurance", "amount": 100}

# 2. Create policy
policy = PolicyLoader.from_dict({
    "id": "financial_prudence",
    "rules": [
        {
            "id": "min_savings",
            "param": "savings",
            "operator": ">=",
            "value": 500,
            "message": "Insufficient savings",
            "level": "ERROR"
        }
    ]
})

# 3. Wrap with governance
agent = MyAgent()
engine = PolicyEngine()

# 4. Verify action
state = {"savings": agent.savings}
action = agent.decide({})
trace = engine.verify(action, state, policy)

if trace.valid:
    print("Action ALLOWED")
else:
    print(f"Action BLOCKED: {trace.rule_message}")
    print(f"To pass: {trace.state_delta}")  # XAI explanation
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Policy Engine** | Stateless rule verification (numeric, categorical, composite) |
| **XAI Counterfactual** | "What change would make this action pass?" |
| **Symbolic Memory** | O(1) state signature lookup for novelty detection |
| **Entropy Calibration** | Detect over/under-governance |
| **Audit Trail** | JSONL logging with replay support |

## Architecture

```
GovernedAgent (wrapper)
    │
    ├── PolicyEngine (verify rules)
    │       │
    │       └── CounterfactualEngine (XAI)
    │
    ├── SymbolicMemory (novelty detection)
    │
    └── AuditWriter (logging)
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [API Reference](docs/api_reference.md)
- [Migration Guide](docs/migration_guide.md)

## Testing

```bash
# Run all tests
pytest governed_ai_sdk/tests/ -v

# Run demo
python governed_ai_sdk/demo_sdk_usage.py
```

## License

MIT
```

### 2. `governed_ai_sdk/docs/architecture.md`

```markdown
# GovernedAI SDK Architecture

## Design Principles

1. **Framework Agnostic**: Works with any agent framework
2. **Strangler Fig Pattern**: Built side-by-side, non-breaking migration
3. **Explainable**: Every decision has a trace and explanation
4. **Calibrated**: Measures governance impact on agent diversity

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     GovernedAgent                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Backend   │  │ Interceptors│  │  State Mapping Fn   │  │
│  │  (any agent)│  │   (list)    │  │  (lambda a: dict)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      PolicyEngine                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  verify(action, state, policy) → GovernanceTrace    │    │
│  │                                                     │    │
│  │  Operators: >, <, >=, <=, ==, !=, in, not_in       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌─────────────────────────┐  ┌─────────────────────────────┐
│  CounterfactualEngine   │  │     EntropyCalibrator       │
│                         │  │                             │
│  Strategies:            │  │  S_raw / S_governed > 2.0   │
│  - NUMERIC (delta)      │  │  → Over-Governed            │
│  - CATEGORICAL (flip)   │  │                             │
│  - COMPOSITE (multi)    │  │  S_raw / S_governed < 0.8   │
│                         │  │  → Under-Governed           │
└─────────────────────────┘  └─────────────────────────────┘
```

## Data Flow

```
1. Agent.decide(context) → action
2. state_mapping_fn(agent) → state
3. PolicyEngine.verify(action, state, policy) → trace
4. If blocked:
   - CounterfactualEngine.explain(rule, state) → delta
   - AuditWriter.log(action, state, trace)
5. EntropyCalibrator.calculate_friction(raw, governed)
```

## Type System

| Type | Purpose |
|------|---------|
| `PolicyRule` | Rule definition (id, param, operator, value, message, level) |
| `GovernanceTrace` | Verification result (valid, rule_id, state_delta) |
| `CounterFactualResult` | XAI output (delta_state, explanation, feasibility) |
| `EntropyFriction` | Calibration (S_raw, S_governed, friction_ratio) |

## Symbolic Memory (v4.0)

```
World State → Sensors → Quantized Bins → Signature Hash → Frequency Map
                                                              │
                                                              ▼
                                              Surprise = 1 - P(signature)
                                                              │
                                                              ▼
                                              System 1 (routine) or System 2 (crisis)
```

**Novelty-First Logic**: First occurrence of any signature = 100% surprise (System 2).
```

### 3. `governed_ai_sdk/docs/api_reference.md`

```markdown
# GovernedAI SDK API Reference

## Core Types

### PolicyRule

```python
@dataclass
class PolicyRule:
    id: str              # Unique identifier
    param: str           # State parameter to check
    operator: str        # ">", "<", ">=", "<=", "==", "!=", "in", "not_in"
    value: Any           # Target value
    message: str         # Human-readable explanation
    level: str           # "ERROR" (blocks) or "WARNING" (logs)
    xai_hint: str = None # Optional hint for XAI
```

### GovernanceTrace

```python
@dataclass
class GovernanceTrace:
    valid: bool                           # Pass or block
    rule_id: str                          # Which rule triggered
    rule_message: str                     # Why
    blocked_action: Optional[Dict] = None # Original action if blocked
    state_delta: Optional[Dict] = None    # What change would pass
    entropy_friction: Optional[float] = None
```

### CounterFactualResult

```python
@dataclass
class CounterFactualResult:
    passed: bool
    delta_state: Dict[str, Any]    # Minimal change to pass
    explanation: str               # Human-readable
    feasibility_score: float       # 0-1: how achievable
    strategy_used: CounterFactualStrategy
```

### EntropyFriction

```python
@dataclass
class EntropyFriction:
    S_raw: float            # Shannon entropy of raw actions
    S_governed: float       # Shannon entropy after governance
    friction_ratio: float   # S_raw / S_governed
    is_over_governed: bool  # friction_ratio > 2.0
    interpretation: str     # "Balanced" | "Over-Governed" | "Under-Governed"
```

## Core Classes

### PolicyEngine

```python
class PolicyEngine:
    def verify(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any],
        policy: Dict[str, Any]
    ) -> GovernanceTrace:
        """Verify action against policy rules."""
```

### CounterfactualEngine

```python
class CounterfactualEngine:
    def explain(
        self,
        failed_rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """Generate XAI explanation for blocked action."""
```

### EntropyCalibrator

```python
class EntropyCalibrator:
    def calculate_friction(
        self,
        raw_actions: List[str],
        governed_actions: List[str]
    ) -> EntropyFriction:
        """Measure governance impact on action diversity."""
```

### SymbolicMemory

```python
class SymbolicMemory:
    def observe(self, world_state: dict) -> Tuple[str, float]:
        """Returns (signature, surprise)."""

    def get_trace(self) -> dict:
        """Get last observation trace for XAI."""

    def explain(self) -> str:
        """Human-readable explanation."""
```

## Policy Format (YAML)

```yaml
id: policy_name
description: "What this policy does"

rules:
  - id: rule_id
    param: state_parameter
    operator: ">="  # or <, >, <=, ==, !=, in, not_in
    value: 500
    message: "Human-readable error message"
    level: ERROR  # or WARNING
    xai_hint: recommend_grant  # optional
```
```

### 4. `governed_ai_sdk/docs/migration_guide.md`

```markdown
# Migration Guide: broker → governed_ai_sdk

## Overview

This guide helps migrate from the research codebase (`broker/`) to the universal SDK (`governed_ai_sdk/`).

## Component Mapping

| broker (old) | governed_ai_sdk (new) | Notes |
|--------------|----------------------|-------|
| `validators/agent_validator.py` | `core/engine.py` | Simplified, no CSV |
| `broker/components/symbolic_context.py` | `memory/symbolic.py` | Re-exported |
| `broker/components/audit_writer.py` | `audit/replay.py` | + replay support |
| `broker/core/governed_broker.py` | `core/wrapper.py` | Cleaner interface |

## Code Changes

### Before (broker)

```python
from validators.agent_validator import AgentValidator
from broker.components.interaction_hub import InteractionHub

validator = AgentValidator(config_path="config.csv")
hub = InteractionHub(...)
result = hub.process_action(agent, action)
```

### After (SDK)

```python
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
from governed_ai_sdk.v1_prototype.core.policy_loader import load_policy

engine = PolicyEngine()
policy = load_policy("policy.yaml")
trace = engine.verify(action, state, policy)
```

## Key Differences

| Aspect | broker | SDK |
|--------|--------|-----|
| Config format | CSV | YAML/Dict |
| Dependencies | InteractionHub, Auditor | None (stateless) |
| XAI | Manual | Built-in CounterfactualEngine |
| Entropy | Not measured | EntropyCalibrator |

## Migration Steps

1. **Convert CSV rules to YAML format**
2. **Replace AgentValidator with PolicyEngine**
3. **Add CounterfactualEngine for XAI**
4. **Add EntropyCalibrator for monitoring**
5. **Update imports**

## Backwards Compatibility

The SDK is designed to run **alongside** the existing broker code (Strangler Fig pattern). You can migrate incrementally:

```python
# Use SDK for new experiments
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine

# Keep broker for running experiments
from broker.core.governed_broker import GovernedBroker
```
```

---

## Verification Commands

```bash
# 1. Verify README renders
cat governed_ai_sdk/README.md

# 2. Verify all docs exist
ls governed_ai_sdk/docs/

# 3. Test code examples in docs work
python -c "
# Quick start example from README
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader

engine = PolicyEngine()
policy = PolicyLoader.from_dict({
    'rules': [{'id': 'r1', 'param': 'x', 'operator': '>=', 'value': 10, 'message': '', 'level': 'ERROR'}]
})
trace = engine.verify({}, {'x': 5}, policy)
print(f'Example works: valid={trace.valid}')
"
```

---

## Success Criteria

1. README covers quick start and all features
2. Architecture diagram is accurate
3. API reference covers all public classes
4. Migration guide has clear before/after examples
5. All code examples in docs are tested and work

---

## Handoff Checklist

- [ ] `governed_ai_sdk/README.md` created
- [ ] `governed_ai_sdk/docs/architecture.md` created
- [ ] `governed_ai_sdk/docs/api_reference.md` created
- [ ] `governed_ai_sdk/docs/migration_guide.md` created
- [ ] All code examples tested
- [ ] Diagrams are accurate
