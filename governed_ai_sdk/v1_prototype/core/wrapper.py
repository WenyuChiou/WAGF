"""
GovernedAgent - Universal wrapper for any agent framework.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

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
    """

    def __init__(
        self,
        backend: Any,
        interceptors: List[Interceptor],
        state_mapping_fn: Callable[[Any], Dict[str, Any]],
        audit_config: Optional[AuditConfig] = None,
        on_block: Optional[Callable[[GovernanceTrace], Dict[str, Any]]] = None,
    ):
        self.backend = backend
        self.interceptors = interceptors
        self.state_fn = state_mapping_fn
        self.audit_config = audit_config
        self.on_block = on_block

        self._audit_writer = None
        if audit_config and audit_config.enabled:
            from governed_ai_sdk.v1_prototype.audit.replay import AuditWriter

            self._audit_writer = AuditWriter(audit_config.output_path)

    def execute(
        self,
        context: Dict[str, Any],
        action: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        if action is None:
            if hasattr(self.backend, "decide"):
                action = self.backend.decide(context)
            elif hasattr(self.backend, "step"):
                action = self.backend.step(context)
            elif callable(self.backend):
                action = self.backend(context)
            else:
                raise ValueError(
                    "Backend must have 'decide', 'step' method or be callable"
                )

        original_action = action.copy()
        state = self.state_fn(self.backend)

        final_trace = GovernanceTrace(
            valid=True,
            rule_id="none",
            rule_message="No rules applied",
        )

        for interceptor in self.interceptors:
            trace = interceptor.intercept(action, state)

            if not trace.valid:
                final_trace = trace

                if self.on_block:
                    modified_action = self.on_block(trace)
                    if modified_action:
                        action = modified_action
                        trace = interceptor.intercept(action, state)
                        if trace.valid:
                            final_trace = trace
                            continue

                if self._audit_writer:
                    self._audit_writer.log(
                        action=original_action,
                        state=state,
                        trace=final_trace,
                        modified_action=action if action != original_action else None,
                    )

                break

        result = ExecutionResult(
            action=action,
            trace=final_trace,
            was_modified=(action != original_action),
            original_action=original_action if action != original_action else None,
        )

        if final_trace.valid and self._audit_writer:
            self._audit_writer.log(
                action=action,
                state=state,
                trace=final_trace,
            )

        return result

    def get_state(self) -> Dict[str, Any]:
        return self.state_fn(self.backend)


class CognitiveInterceptor:
    """
    Placeholder interceptor for cognitive governance.
    """

    def __init__(self, mode: str = "LogicalConsistency"):
        self.mode = mode
        self._engine = None

    def intercept(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any],
    ) -> GovernanceTrace:
        if self._engine is None:
            return GovernanceTrace(
                valid=True,
                rule_id="passthrough",
                rule_message="No policy engine configured",
                evaluated_state=state,
            )

        return self._engine.verify(action, state, {})
