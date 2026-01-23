# SDK Migration Handover: The GovernedAI Framework

## 1. Context & Objective

We are refactoring the research codebase (`governed_broker_framework`) into a universal SDK (`governed_ai_sdk`).
**Goal**: Create a middleware layer that provides "Cognitive Governance" (Identity & Thinking Rules) to ANY agent framework (LangChain, CrewAI, etc.).

## 1.5 Execution Strategy: The "Strangler Fig" Pattern (CRITICAL)

**WARNING**: This is a large-scale architectural refactor. DO NOT attempt to rewrite the entire codebase in one go.

- **Methodology**: Build the new `governed_ai_sdk` side-by-side with the existing `broker`.
- **Why?**: The current `broker` is running live experiments (JOH Phase 7). If you modify it directly, you will break the ongoing research.
- **Approach**:
  1.  Create `governed_ai_sdk` as a standalone package.
  2.  Port logic incrementally (Copy-Paste-Refactor).
  3.  Only when `v1_prototype` is fully tested (via `demo_sdk.py`), do we switch the main experiment to use it.

## 1.6 Asset Reuse Mapping (Don't Reinvent the Wheel)

Verify existing modules before writing new code. We have 60% of the logic already.

| SDK Component (New)  | Existing Source (Ref)                   | Action Required                                                                |
| :------------------- | :-------------------------------------- | :----------------------------------------------------------------------------- |
| `core/engine.py`     | `validators/agent_validator.py`         | **Extract** `_run_rule_set` logic. Remove CSV loading.                         |
| `memory/symbolic.py` | `broker/components/symbolic_context.py` | **Extract** `hash_context` logic. Keep it lightweight.                         |
| `audit/replay.py`    | `broker/components/audit_writer.py`     | **Adapt** existing JSONL writing logic. Add "Replay" metadata.                 |
| `core/wrapper.py`    | `broker/core/governed_broker.py`        | **REFERENCE ONLY**. Do not copy. The new wrapper must be much simpler/cleaner. |

## 2. Core Architecture: The Dual-Layer Interceptor

You need to implement the following architecture:

```python
agent = GovernedAgent(
    backend=UserAgent,
    interceptors=[
        CognitiveInterceptor(mode="LogicalConsistency"), # Anti-Hallucination
        ActionInterceptor(mode="EnvironmentConstraints") # Anti-Asymmetry
    ]
)
```

### 2.1 Technical Mechanics (CRITICAL)

1.  **Counter-factual XAI**:
    - _Challenge_: Don't just block. Explain _why_.
    - _Implementation_: When a rule fails (e.g., `savings < 500`), the engine must calculate the delta (`savings_needed = 500 - current`).
    - _Output_: "Blocked. Logic: If savings were +$200, action would pass."
2.  **Entropy Friction**:
    - _Challenge_: Measure if we are over-governing.
    - _Implementation_: Calculate $S_{raw}$ (distribution of intended actions) vs $S_{gov}$ (distribution of allowed actions). Log this ratio.

## 3. Implementation Roadmap (Step-by-Step)

### Phase 1: Skeleton & Core (The Wrapper)

- [ ] Create `governed_ai_sdk/v1_prototype/`.
- [ ] Implement `core/wrapper.py`: A clean, framework-agnostic class `GovernedAgent`.
  - **Requirement**: Must accept a `state_mapping_fn` to read environment state from any object.

### Phase 2: The Brain (Porting Validators)

- [ ] **Lift & Shift**: Extract the logic from `validators/agent_validator.py` (`_run_rule_set`).
- [ ] **Refactor**: Remove CSV dependencies. Create a `PolicyLoader` that reads pure Dict/YAML.
- [ ] **Destination**: `core/engine.py`.

### Phase 3: The Memory (Porting v4 Symbolic)

- [ ] **Lift & Shift**: Extract `hash_context` from `broker/components/symbolic_context.py`.
- [ ] **Destination**: `memory/symbolic.py`.
- [ ] **Requirement**: Ensure $O(1)$ lookup speed for state signatures.

### Phase 4: The New Layers (XAI & Calibration)

- [ ] **Build New**: Implement `xai/counterfactual.py`.
  - _Input_: Rule Condition + Current State.
  - _Output_: Minimal State Change required for True.
- [ ] **Build New**: Implement `core/calibrator.py`.
  - _Input_: Batch of (Raw_Action, Governed_Action).
  - _Output_: Entropy Friction score.

## 4. Existing Assets to Reuse

- `validators/agent_validator.py`: Contains 80% of the rule logic.
- `broker/components/symbolic_context.py`: Contains the efficient hashing logic.
- `broker/components/audit_writer.py`: Contains the JSONL logging logic.

## 5. Instructions for Claude Code

1.  Read `validators/agent_validator.py` first to understand the _Thinking Rules_ logic.
2.  Start by building the `GovernedAgent` wrapper in isolation.
3.  Port the rule engine _without_ the legacy interaction hub dependencies.
4.  Focus on the **Universal Adapter** pattern: `wrapper.py` should effectively be a "Translation Layer" between the User's Env and our Policy Engine.
5.  **Validation**: Ensure that `demo_sdk_usage.py` passes before attempting any integration with the main experiment.

## Appendix A: Critical Interface Definitions (Python Protocols)

To prevent over-engineering, adhere to these simple interfaces:

### A.1 Universal Adapter

```python
class EnvironmentAdapter(Protocol):
    """
    Maps your simulation object to a standard dict.
    Example: { "savings": 500, "flood_risk": 0.8 }
    """
    def get_state(self, internal_agent: Any) -> Dict[str, Any]: ...
```

### A.2 The Governance Engine

```python
class PolicyEngine(Protocol):
    """
    Stateless verifier.
    """
    def verify(self, action: Dict, state: Dict, policy: Dict) -> GovernanceTrace: ...
```

### A.3 The XAI Generator

```python
class CounterFactualEngine(Protocol):
    """
    Inverses the failed rule to find the pass condition.
    """
    def explain(self, failed_rule: Rule, state: Dict) -> str:
        # Return e.g., "If savings > 500 (+200 needed)..."
        ...
```
