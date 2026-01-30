"""
Generic saga transaction coordinator for multi-step agent workflows.

Provides:
- SagaStep: A single step in a saga with execute + compensate callables
- SagaDefinition: Named sequence of SagaSteps
- SagaExecution: Runtime state of a saga in progress
- SagaResult: Outcome of a completed saga
- SagaStatus: Enum for saga lifecycle states
- SagaCoordinator: Manages saga execution with compensatory rollback

Domain-specific saga definitions (e.g. SUBSIDY_APPLICATION_SAGA) should
live in the domain module (examples/multi_agent/ma_saga_definitions.py).

Reference: Task-058D (Saga Transaction Coordinator)
Literature: SagaLLM (Chang & Geng, 2025) — transaction guarantees
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SagaStatus(Enum):
    """Lifecycle state of a saga execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class SagaStep:
    """A single step in a saga workflow.

    Args:
        name: Human-readable step identifier
        execute: Callable(context: Dict) -> Dict  (returns updated context)
        compensate: Callable(context: Dict) -> None  (undo side effects)
    """
    name: str
    execute: Callable[[Dict[str, Any]], Dict[str, Any]]
    compensate: Callable[[Dict[str, Any]], None]


@dataclass
class SagaDefinition:
    """Named sequence of SagaSteps forming a complete workflow.

    Args:
        name: Unique saga identifier (e.g. "subsidy_application")
        steps: Ordered list of SagaStep objects
        timeout_steps: Max simulation steps before timeout (0 = no timeout)
    """
    name: str
    steps: List[SagaStep]
    timeout_steps: int = 0


@dataclass
class SagaExecution:
    """Runtime state of a saga in progress.

    Attributes:
        saga_id: Unique execution identifier
        definition: The saga definition being executed
        status: Current lifecycle state
        current_step_index: Index of the step currently executing
        context: Shared mutable context passed between steps
        completed_steps: Names of successfully completed steps
        error: Error message if failed
        started_at_step: Simulation step when saga started
    """
    saga_id: str
    definition: SagaDefinition
    status: SagaStatus = SagaStatus.PENDING
    current_step_index: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    completed_steps: List[str] = field(default_factory=list)
    error: str = ""
    started_at_step: int = 0


@dataclass
class SagaResult:
    """Outcome of a completed saga execution.

    Attributes:
        saga_id: Execution identifier
        saga_name: Definition name
        status: Final lifecycle state
        context: Final context after all steps (or rollback)
        completed_steps: Steps that completed successfully
        error: Error message if any
    """
    saga_id: str
    saga_name: str
    status: SagaStatus
    context: Dict[str, Any]
    completed_steps: List[str]
    error: str = ""


class SagaCoordinator:
    """Manages saga execution with compensatory rollback on failure.

    Usage:
        coordinator = SagaCoordinator()
        coordinator.register_saga(my_saga_definition)
        saga_id = coordinator.start_saga("my_saga", initial_context, step=0)
        # Each simulation step:
        coordinator.advance(saga_id)
        # Or advance all:
        coordinator.advance_all()

    Args:
        max_concurrent: Maximum number of concurrent saga executions (0 = unlimited)
    """

    def __init__(self, max_concurrent: int = 0):
        self.max_concurrent = max_concurrent
        self._definitions: Dict[str, SagaDefinition] = {}
        self._executions: Dict[str, SagaExecution] = {}
        self._results: List[SagaResult] = []
        self._next_id: int = 0

    def register_saga(self, definition: SagaDefinition) -> None:
        """Register a saga definition for later execution."""
        self._definitions[definition.name] = definition

    def start_saga(
        self,
        saga_name: str,
        context: Optional[Dict[str, Any]] = None,
        step: int = 0,
    ) -> str:
        """Start a new saga execution.

        Args:
            saga_name: Name of a registered SagaDefinition
            context: Initial context dict (will be mutated by steps)
            step: Current simulation step (for timeout tracking)

        Returns:
            saga_id: Unique execution identifier

        Raises:
            ValueError: If saga_name is not registered or max_concurrent reached
        """
        if saga_name not in self._definitions:
            raise ValueError(f"Unknown saga: '{saga_name}'. "
                             f"Registered: {list(self._definitions.keys())}")

        active = sum(1 for e in self._executions.values()
                     if e.status in (SagaStatus.PENDING, SagaStatus.RUNNING))
        if self.max_concurrent > 0 and active >= self.max_concurrent:
            raise ValueError(f"Max concurrent sagas ({self.max_concurrent}) reached.")

        self._next_id += 1
        saga_id = f"saga_{self._next_id}"
        execution = SagaExecution(
            saga_id=saga_id,
            definition=self._definitions[saga_name],
            status=SagaStatus.PENDING,
            context=dict(context or {}),
            started_at_step=step,
        )
        self._executions[saga_id] = execution
        return saga_id

    def advance(self, saga_id: str, current_step: int = 0) -> Optional[SagaResult]:
        """Advance a saga by executing the next step.

        Returns SagaResult if the saga completes (success or rollback),
        None if still in progress.

        Args:
            saga_id: Execution identifier
            current_step: Current simulation step (for timeout checks)
        """
        execution = self._executions.get(saga_id)
        if execution is None:
            return None

        # Already terminal
        if execution.status in (SagaStatus.COMPLETED, SagaStatus.FAILED,
                                SagaStatus.ROLLED_BACK):
            return None

        definition = execution.definition

        # Timeout check
        if (definition.timeout_steps > 0
                and (current_step - execution.started_at_step) > definition.timeout_steps):
            execution.error = f"Timeout after {definition.timeout_steps} steps"
            return self._rollback(execution)

        # Mark as running
        if execution.status == SagaStatus.PENDING:
            execution.status = SagaStatus.RUNNING

        # All steps completed?
        if execution.current_step_index >= len(definition.steps):
            execution.status = SagaStatus.COMPLETED
            result = SagaResult(
                saga_id=saga_id,
                saga_name=definition.name,
                status=SagaStatus.COMPLETED,
                context=dict(execution.context),
                completed_steps=list(execution.completed_steps),
            )
            self._results.append(result)
            return result

        # Execute current step
        step = definition.steps[execution.current_step_index]
        try:
            updated_context = step.execute(execution.context)
            execution.context = updated_context
            execution.completed_steps.append(step.name)
            execution.current_step_index += 1
            logger.debug(f"Saga {saga_id}: completed step '{step.name}'")
        except Exception as e:
            execution.error = f"Step '{step.name}' failed: {e}"
            logger.warning(f"Saga {saga_id}: {execution.error}")
            return self._rollback(execution)

        # Check if that was the last step
        if execution.current_step_index >= len(definition.steps):
            execution.status = SagaStatus.COMPLETED
            result = SagaResult(
                saga_id=saga_id,
                saga_name=definition.name,
                status=SagaStatus.COMPLETED,
                context=dict(execution.context),
                completed_steps=list(execution.completed_steps),
            )
            self._results.append(result)
            return result

        return None  # Still in progress

    def advance_all(self, current_step: int = 0) -> List[SagaResult]:
        """Advance all active sagas by one step each.

        Returns list of SagaResults for any that completed this tick.
        """
        completed: List[SagaResult] = []
        for saga_id in list(self._executions.keys()):
            result = self.advance(saga_id, current_step=current_step)
            if result is not None:
                completed.append(result)
        return completed

    def get_status(self, saga_id: str) -> Optional[SagaStatus]:
        """Get the current status of a saga execution."""
        execution = self._executions.get(saga_id)
        return execution.status if execution else None

    @property
    def results(self) -> List[SagaResult]:
        """Return all completed saga results."""
        return list(self._results)

    def _rollback(self, execution: SagaExecution) -> SagaResult:
        """Execute compensatory rollback for completed steps (reverse order)."""
        execution.status = SagaStatus.COMPENSATING
        definition = execution.definition

        # Compensate in reverse order
        for step_name in reversed(execution.completed_steps):
            step = next(
                (s for s in definition.steps if s.name == step_name), None
            )
            if step is not None:
                try:
                    step.compensate(execution.context)
                    logger.debug(f"Saga {execution.saga_id}: "
                                 f"compensated step '{step_name}'")
                except Exception as comp_err:
                    logger.error(f"Saga {execution.saga_id}: "
                                 f"compensation failed for '{step_name}': {comp_err}")

        execution.status = SagaStatus.ROLLED_BACK
        result = SagaResult(
            saga_id=execution.saga_id,
            saga_name=definition.name,
            status=SagaStatus.ROLLED_BACK,
            context=dict(execution.context),
            completed_steps=list(execution.completed_steps),
            error=execution.error,
        )
        self._results.append(result)
        return result
