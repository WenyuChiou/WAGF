# Task-058D: Saga Transaction Coordinator

> **Assigned to:** ~~Gemini~~ → COMPLETED by Claude (generalized architecture)
> **Priority:** P1
> **Status:** ✅ COMPLETE — Generic `SagaCoordinator` in broker/, flood saga definitions in `ma_saga_definitions.py`. Tests: 15 pass.
> **Depends on:** 058-A (uses artifacts for saga step context)
> **Branch:** `feat/memory-embedding-retrieval`

---

## Objective

Implement a Saga pattern for multi-step workflows (subsidy application, insurance claim, elevation grant) with compensatory rollback on failure.

## Literature Reference

- **SagaLLM** (Zotero: `7G736VMQ`): Transaction guarantees and compensatory rollback for LLM agents

## File 1: `broker/components/saga_coordinator.py` (NEW, ~130 lines)

### Dataclasses

```python
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import uuid


class SagaStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class SagaStep:
    name: str
    execute: Callable[[Dict], Any]         # Takes context dict, returns result
    compensate: Callable[[Dict], Any]      # Rollback function (takes context dict)
    timeout_steps: int = 1                 # Max simulation steps before timeout


@dataclass
class SagaDefinition:
    name: str
    steps: List[SagaStep]
    description: str = ""


@dataclass
class SagaExecution:
    saga_id: str
    definition_name: str
    context: Dict[str, Any]               # Shared context across steps
    status: SagaStatus = SagaStatus.PENDING
    current_step: int = 0
    completed_steps: List[str] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    started_at_step: int = 0              # Simulation step when started
    error: Optional[str] = None


@dataclass
class SagaResult:
    saga_id: str
    definition_name: str
    status: SagaStatus
    steps_completed: int
    steps_total: int
    error: Optional[str] = None
```

### Class: `SagaCoordinator`

```python
class SagaCoordinator:
    def __init__(self):
        self.definitions: Dict[str, SagaDefinition] = {}
        self.active: Dict[str, SagaExecution] = {}
        self.completed: List[SagaResult] = []

    def register_saga(self, definition: SagaDefinition) -> None:
        """Register a saga definition by name."""

    def start_saga(self, name: str, context: Dict[str, Any], current_step: int = 0) -> str:
        """Start a new saga execution. Returns saga_id."""

    def advance(self, saga_id: str, current_step: int = 0) -> SagaStatus:
        """Execute the next step in the saga.
        - If step succeeds: move to next step, store result in context
        - If step fails: trigger rollback
        - If all steps done: mark completed, move to self.completed
        """

    def rollback(self, saga_id: str) -> None:
        """Compensate all completed steps in reverse order.
        - Call compensate() for each completed step, reverse order
        - Mark saga as ROLLED_BACK
        - Move to self.completed
        """

    def check_timeouts(self, current_step: int) -> List[str]:
        """Check all active sagas for timeouts.
        - If current_step - started_at_step > sum of timeout_steps: mark TIMED_OUT
        - Returns list of timed-out saga_ids
        """

    def get_active_sagas(self) -> Dict[str, SagaExecution]:
        """Return all active saga executions."""

    def summary(self) -> Dict[str, Any]:
        """Return audit statistics."""
        return {
            "registered_sagas": len(self.definitions),
            "active": len(self.active),
            "completed": len([r for r in self.completed if r.status == SagaStatus.COMPLETED]),
            "rolled_back": len([r for r in self.completed if r.status == SagaStatus.ROLLED_BACK]),
            "timed_out": len([r for r in self.completed if r.status == SagaStatus.TIMED_OUT]),
        }
```

## File 2: `broker/components/saga_definitions.py` (NEW, ~80 lines)

Pre-built saga definitions for the flood domain:

```python
from broker.components.saga_coordinator import SagaStep, SagaDefinition


def _household_applies_subsidy(context: dict):
    """Step 1: Household applies for subsidy."""
    context["application_status"] = "pending"
    return {"status": "applied", "agent_id": context.get("agent_id")}

def _government_evaluates_subsidy(context: dict):
    """Step 2: Government evaluates application."""
    budget = context.get("budget_remaining", 0)
    cost = context.get("subsidy_cost", 5000)
    if budget >= cost:
        context["approved"] = True
        return {"status": "approved"}
    context["approved"] = False
    raise ValueError(f"Budget insufficient: {budget} < {cost}")

def _budget_deducted(context: dict):
    """Step 3: Deduct from government budget."""
    if not context.get("approved"):
        raise ValueError("Cannot deduct: not approved")
    context["budget_remaining"] = context.get("budget_remaining", 0) - context.get("subsidy_cost", 5000)
    return {"status": "deducted", "remaining": context["budget_remaining"]}

def _refund_budget(context: dict):
    """Compensate: Refund deducted budget."""
    context["budget_remaining"] = context.get("budget_remaining", 0) + context.get("subsidy_cost", 5000)

def _undo_approval(context: dict):
    """Compensate: Undo approval."""
    context["approved"] = False

def _cancel_application(context: dict):
    """Compensate: Cancel application."""
    context["application_status"] = "cancelled"


SUBSIDY_APPLICATION_SAGA = SagaDefinition(
    name="subsidy_application",
    description="Household applies for subsidy -> Government evaluates -> Budget deducted",
    steps=[
        SagaStep("household_applies", _household_applies_subsidy, _cancel_application),
        SagaStep("government_evaluates", _government_evaluates_subsidy, _undo_approval),
        SagaStep("budget_deducted", _budget_deducted, _refund_budget),
    ],
)

# Similarly define INSURANCE_CLAIM_SAGA and ELEVATION_GRANT_SAGA
# (Follow same pattern: 3 steps + 3 compensations each)
```

## Test File: `tests/test_saga_coordinator.py` (NEW)

Write tests for:
1. `register_saga()` — definition stored correctly
2. `start_saga()` — returns unique saga_id, creates active execution
3. `advance()` — happy path, all 3 steps complete successfully
4. `advance()` — step 2 fails, triggers rollback of step 1
5. `rollback()` — compensations called in reverse order
6. `check_timeouts()` — saga exceeds timeout, marked as TIMED_OUT
7. `summary()` — correct counts for completed/rolled_back/timed_out
8. Concurrent sagas — two active sagas don't interfere
9. Edge case: advance on non-existent saga_id
10. Integration test: SUBSIDY_APPLICATION_SAGA happy path with sufficient budget

## DO NOT

- Do NOT modify `broker/components/coordinator.py` (that's 058-F)
- Do NOT modify `broker/components/phase_orchestrator.py` (that's 058-F)
- Do NOT import DriftDetector or CrossAgentValidator

## Verification

```bash
pytest tests/test_saga_coordinator.py -v
```

---

## Completion (Codex takeover)

- Status: ✅ Completed
- Commit: `b62cc6b`
- Tests: `pytest tests/test_saga_coordinator.py -v`

### Files Added
- `broker/components/saga_coordinator.py`
- `examples/multi_agent/ma_saga_definitions.py`
- `tests/test_saga_coordinator.py`
