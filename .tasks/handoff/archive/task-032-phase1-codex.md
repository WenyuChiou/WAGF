# Task-032 Phase 1: Skeleton & Core (Codex)

**Status**: 🔲 Ready for Implementation
**Assignee**: Codex
**Effort**: 2-3 hours
**Priority**: HIGH (blocks all other phases)
**Prerequisite**: Phase 0 ✅ COMPLETE (types.py created)

---

## Git Branch

```bash
# Checkout this branch to start work
git checkout task-032-phase1

# Base commit: 927c4cc (Phase 0 complete)
```

**Stacked PR Structure**:
```
main
 └── task-032-sdk-base (Phase 0) ← 927c4cc
      └── task-032-phase1 (this branch) ← YOUR WORK HERE
```

---

## Objective

Create the SDK skeleton structure with the `GovernedAgent` wrapper class - the central abstraction that wraps any agent framework with cognitive governance.

---

## Prerequisite Verification

Before starting, verify Phase 0 is complete:

```bash
cd c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework
python -c "from governed_ai_sdk.v1_prototype.types import GovernanceTrace, PolicyRule; print('Phase 0 OK')"
```

---

## Directory Structure (Already Created)

```
governed_ai_sdk/
├── __init__.py                    ✅ EXISTS
├── v1_prototype/
│   ├── __init__.py                ✅ EXISTS
│   ├── types.py                   ✅ EXISTS (Phase 0)
│   ├── core/
│   │   ├── __init__.py            ✅ EXISTS
│   │   ├── wrapper.py             🔲 CREATE (this phase)
│   │   ├── engine.py              🔲 Phase 2 (Gemini)
│   │   └── calibrator.py          🔲 Phase 4B (Gemini)
│   ├── memory/
│   │   ├── __init__.py            ✅ EXISTS
│   │   └── symbolic.py            🔲 Phase 3 (Claude)
│   ├── audit/
│   │   ├── __init__.py            ✅ EXISTS
│   │   └── replay.py              🔲 CREATE (this phase)
│   ├── xai/
│   │   ├── __init__.py            ✅ EXISTS
│   │   └── counterfactual.py      🔲 Phase 4A (Claude)
│   └── interfaces/
│       ├── __init__.py            ✅ EXISTS
│       └── protocols.py           🔲 CREATE (this phase)
├── tests/
│   ├── __init__.py                ✅ EXISTS
│   └── test_types.py              ✅ EXISTS (18 tests pass)
└── demo_sdk_usage.py              🔲 CREATE (this phase)
```

---

## Deliverables

### 1. `interfaces/protocols.py` - Protocol Definitions

```python
"""
Protocol definitions for SDK interfaces.

Reference: .tasks/SDK_Handover_Plan.md Appendix A
"""

from typing import Any, Dict, Protocol, List, Optional
from governed_ai_sdk.v1_prototype.types import GovernanceTrace, PolicyRule


class EnvironmentAdapter(Protocol):
    """
    Maps your simulation object to a standard dict.

    Example implementation:
        class FloodABMAdapter:
            def get_state(self, agent) -> Dict:
                return {
                    "savings": agent.savings,
                    "flood_risk": agent.environment.flood_depth,
                    "insurance_status": agent.insurance_policy.status
                }
    """
    def get_state(self, internal_agent: Any) -> Dict[str, Any]:
        """Extract state from any agent object."""
        ...


class PolicyEngine(Protocol):
    """
    Stateless rule verifier.

    Implementation in Phase 2 (Gemini CLI).
    """
    def verify(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any],
        policy: Dict[str, Any]
    ) -> GovernanceTrace:
        """Evaluate rules against state."""
        ...


class CounterFactualEngine(Protocol):
    """
    Generates XAI explanations for failed rules.

    Implementation in Phase 4A (Claude Code).
    """
    def explain(self, failed_rule: PolicyRule, state: Dict[str, Any]) -> str:
        """Return e.g., 'If savings > 500 (+200 needed)...'"""
        ...


class Interceptor(Protocol):
    """
    Base interceptor interface for governance layers.
    """
    def intercept(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any]
    ) -> GovernanceTrace:
        """Intercept and validate an action."""
        ...
```

### 2. `core/wrapper.py` - GovernedAgent Class

```python
"""
GovernedAgent - Universal wrapper for any agent framework.

This is the central abstraction that provides cognitive governance
to ANY agent framework (LangChain, CrewAI, AutoGen, etc.).
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from governed_ai_sdk.v1_prototype.types import GovernanceTrace
from governed_ai_sdk.v1_prototype.interfaces.protocols import Interceptor


@dataclass
class AuditConfig:
    """Configuration for audit logging."""
    enabled: bool = True
    output_path: str = "audit.jsonl"
    include_state: bool = True
    include_trace: bool = True


@dataclass
class ExecutionResult:
    """Result of a governed action execution."""
    action: Dict[str, Any]
    trace: GovernanceTrace
    was_modified: bool = False
    original_action: Optional[Dict[str, Any]] = None


class GovernedAgent:
    """
    Universal wrapper for any agent framework.

    Intercepts agent actions and applies cognitive governance rules
    before execution. Works with any backend that can produce actions.

    Example:
        >>> class MyAgent:
        ...     def decide(self, context): return {"action": "buy", "amount": 100}

        >>> governed = GovernedAgent(
        ...     backend=MyAgent(),
        ...     interceptors=[CognitiveInterceptor()],
        ...     state_mapping_fn=lambda a: {"savings": 500}
        ... )
        >>> result = governed.execute(context={})
    """

    def __init__(
        self,
        backend: Any,
        interceptors: List[Interceptor],
        state_mapping_fn: Callable[[Any], Dict[str, Any]],
        audit_config: Optional[AuditConfig] = None,
        on_block: Optional[Callable[[GovernanceTrace], Dict[str, Any]]] = None,
    ):
        """
        Initialize governed agent.

        Args:
            backend: The underlying agent object (any framework)
            interceptors: List of governance interceptors to apply
            state_mapping_fn: Function to extract state dict from backend
            audit_config: Optional audit logging configuration
            on_block: Optional callback when action is blocked (return modified action)
        """
        self.backend = backend
        self.interceptors = interceptors
        self.state_fn = state_mapping_fn
        self.audit_config = audit_config
        self.on_block = on_block

        # Lazy import to avoid circular dependency
        self._audit_writer = None
        if audit_config and audit_config.enabled:
            from governed_ai_sdk.v1_prototype.audit.replay import AuditWriter
            self._audit_writer = AuditWriter(audit_config.output_path)

    def execute(
        self,
        context: Dict[str, Any],
        action: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute an action with governance checks.

        Args:
            context: Context to pass to backend for decision-making
            action: Optional pre-computed action (if None, calls backend.decide())

        Returns:
            ExecutionResult with trace explaining what happened
        """
        # Step 1: Get action from backend if not provided
        if action is None:
            if hasattr(self.backend, 'decide'):
                action = self.backend.decide(context)
            elif hasattr(self.backend, 'step'):
                action = self.backend.step(context)
            elif callable(self.backend):
                action = self.backend(context)
            else:
                raise ValueError(
                    "Backend must have 'decide', 'step' method or be callable"
                )

        original_action = action.copy()

        # Step 2: Extract current state
        state = self.state_fn(self.backend)

        # Step 3: Run through interceptors
        final_trace = GovernanceTrace(
            valid=True,
            rule_id="none",
            rule_message="No rules applied",
        )

        for interceptor in self.interceptors:
            trace = interceptor.intercept(action, state)

            if not trace.valid:
                # Action blocked
                final_trace = trace

                # Call on_block callback if provided
                if self.on_block:
                    modified_action = self.on_block(trace)
                    if modified_action:
                        action = modified_action
                        # Re-check with modified action
                        trace = interceptor.intercept(action, state)
                        if trace.valid:
                            final_trace = trace
                            continue

                # Log if audit enabled
                if self._audit_writer:
                    self._audit_writer.log(
                        action=original_action,
                        state=state,
                        trace=final_trace,
                        modified_action=action if action != original_action else None
                    )

                break

        # Step 4: Build result
        result = ExecutionResult(
            action=action,
            trace=final_trace,
            was_modified=(action != original_action),
            original_action=original_action if action != original_action else None
        )

        # Log successful action
        if final_trace.valid and self._audit_writer:
            self._audit_writer.log(
                action=action,
                state=state,
                trace=final_trace
            )

        return result

    def get_state(self) -> Dict[str, Any]:
        """Get current state from backend."""
        return self.state_fn(self.backend)


class CognitiveInterceptor:
    """
    Placeholder interceptor for cognitive governance.

    Full implementation depends on PolicyEngine (Phase 2).
    """

    def __init__(self, mode: str = "LogicalConsistency"):
        self.mode = mode
        self._engine = None  # Will be set when PolicyEngine is available

    def intercept(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any]
    ) -> GovernanceTrace:
        """
        Intercept and validate action.

        Currently returns pass-through until PolicyEngine is implemented.
        """
        if self._engine is None:
            # Pass-through mode until engine is configured
            return GovernanceTrace(
                valid=True,
                rule_id="passthrough",
                rule_message="No policy engine configured",
                evaluated_state=state
            )

        # Will be implemented in Phase 2
        return self._engine.verify(action, state, {})
```

### 3. `audit/replay.py` - Audit Writer

```python
"""
JSONL Audit Writer with replay support.

Adapted from: broker/components/audit_writer.py (lines 70-255)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from governed_ai_sdk.v1_prototype.types import GovernanceTrace


class AuditWriter:
    """
    Writes governance audit logs in JSONL format.

    Features:
        - Append-only JSONL for reliability
        - Replay metadata for debugging
        - Buffered writes for performance
    """

    def __init__(
        self,
        output_path: str = "audit.jsonl",
        buffer_size: int = 10,
        include_timestamp: bool = True
    ):
        self.output_path = Path(output_path)
        self.buffer_size = buffer_size
        self.include_timestamp = include_timestamp
        self._buffer: list = []
        self._sequence_num = 0

        # Ensure parent directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any],
        trace: GovernanceTrace,
        modified_action: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a governance event.

        Args:
            action: The action that was evaluated
            state: The state at evaluation time
            trace: The governance trace result
            modified_action: Modified action if changed by on_block callback
            metadata: Additional metadata to include
        """
        self._sequence_num += 1

        record = {
            "seq": self._sequence_num,
            "action": action,
            "state": state,
            "trace": {
                "valid": trace.valid,
                "rule_id": trace.rule_id,
                "rule_message": trace.rule_message,
                "state_delta": trace.state_delta,
                "entropy_friction": trace.entropy_friction,
            },
        }

        if self.include_timestamp:
            record["timestamp"] = datetime.now().isoformat()

        if modified_action:
            record["modified_action"] = modified_action
            record["was_modified"] = True

        if metadata:
            record["metadata"] = metadata

        self._buffer.append(record)

        if len(self._buffer) >= self.buffer_size:
            self.flush()

    def flush(self) -> None:
        """Write buffered records to file."""
        if not self._buffer:
            return

        with open(self.output_path, "a", encoding="utf-8") as f:
            for record in self._buffer:
                f.write(json.dumps(record, default=str) + "\n")

        self._buffer.clear()

    def close(self) -> None:
        """Flush and close the writer."""
        self.flush()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AuditReader:
    """
    Reads and replays audit logs.
    """

    def __init__(self, input_path: str):
        self.input_path = Path(input_path)

    def read_all(self) -> list:
        """Read all records from audit file."""
        records = []
        with open(self.input_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def filter_blocked(self) -> list:
        """Return only blocked actions."""
        return [r for r in self.read_all() if not r["trace"]["valid"]]

    def filter_by_rule(self, rule_id: str) -> list:
        """Return records matching a specific rule."""
        return [r for r in self.read_all() if r["trace"]["rule_id"] == rule_id]
```

### 4. `demo_sdk_usage.py` - Validation Script

```python
"""
Demo script to validate SDK skeleton works.

Run: python governed_ai_sdk/demo_sdk_usage.py
"""

from governed_ai_sdk.v1_prototype import (
    GovernanceTrace,
    PolicyRule,
)
from governed_ai_sdk.v1_prototype.core.wrapper import (
    GovernedAgent,
    CognitiveInterceptor,
    AuditConfig,
)


class MockHouseholdAgent:
    """Mock agent for testing."""

    def __init__(self, savings: int = 300):
        self.savings = savings
        self.insurance_status = "none"

    def decide(self, context):
        return {"action": "buy_insurance", "premium": 100}


def main():
    print("=== GovernedAI SDK Demo ===\n")

    # 1. Create mock agent
    agent = MockHouseholdAgent(savings=300)
    print(f"1. Created agent with savings=${agent.savings}")

    # 2. Define state mapping function
    def state_fn(a):
        return {
            "savings": a.savings,
            "insurance_status": a.insurance_status
        }

    # 3. Wrap with governance
    governed = GovernedAgent(
        backend=agent,
        interceptors=[CognitiveInterceptor(mode="LogicalConsistency")],
        state_mapping_fn=state_fn,
        audit_config=AuditConfig(enabled=True, output_path="demo_audit.jsonl")
    )
    print("2. Wrapped agent with GovernedAgent")

    # 4. Execute action
    result = governed.execute(context={})
    print(f"3. Executed action: {result.action}")
    print(f"   Trace valid: {result.trace.valid}")
    print(f"   Trace message: {result.trace.rule_message}")

    # 5. Get current state
    state = governed.get_state()
    print(f"4. Current state: {state}")

    # 6. Verify types work
    rule = PolicyRule(
        id="min_savings",
        param="savings",
        operator=">=",
        value=500,
        message="Need $500 minimum",
        level="ERROR"
    )
    print(f"5. Created rule: {rule.id} ({rule.param} {rule.operator} {rule.value})")

    print("\n=== Demo Complete ===")
    print("All SDK skeleton components working!")
    print("\nNext: Phase 2 (Gemini CLI) will implement PolicyEngine")


if __name__ == "__main__":
    main()
```

---

## Verification Commands

```bash
# 1. Verify protocols import
python -c "from governed_ai_sdk.v1_prototype.interfaces.protocols import EnvironmentAdapter, PolicyEngine; print('OK')"

# 2. Verify wrapper import
python -c "from governed_ai_sdk.v1_prototype.core.wrapper import GovernedAgent, CognitiveInterceptor; print('OK')"

# 3. Verify audit import
python -c "from governed_ai_sdk.v1_prototype.audit.replay import AuditWriter, AuditReader; print('OK')"

# 4. Run demo script
python governed_ai_sdk/demo_sdk_usage.py

# 5. Run all SDK tests
pytest governed_ai_sdk/tests/ -v
```

---

## Test Cases (Create in `tests/test_wrapper.py`)

```python
def test_governed_agent_passthrough():
    """Test that GovernedAgent passes actions through without engine."""
    ...

def test_governed_agent_state_extraction():
    """Test state mapping function works."""
    ...

def test_audit_writer_creates_file():
    """Test audit writer creates JSONL file."""
    ...

def test_audit_reader_filters():
    """Test audit reader can filter by rule."""
    ...
```

---

## Success Criteria

1. All imports work without errors
2. `demo_sdk_usage.py` runs successfully
3. At least 4 new tests pass in `test_wrapper.py`
4. No changes to existing broker code

---

## Handoff Checklist

- [ ] `interfaces/protocols.py` created
- [ ] `core/wrapper.py` created with GovernedAgent class
- [ ] `audit/replay.py` created with AuditWriter/AuditReader
- [ ] `demo_sdk_usage.py` created and runs
- [ ] `tests/test_wrapper.py` created with passing tests
- [ ] All verification commands pass
- [ ] Update `.tasks/handoff/current-session.md` with progress

---

## References

- Plan: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md` (Phase 1 section)
- SDK Handover: `.tasks/SDK_Handover_Plan.md` (Appendix A)
- Existing Audit: `broker/components/audit_writer.py` (reference only)
