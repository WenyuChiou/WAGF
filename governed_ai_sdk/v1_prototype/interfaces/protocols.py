"""
Protocol definitions for SDK interfaces.

Reference: .tasks/SDK_Handover_Plan.md Appendix A
"""

from typing import Any, Dict, Protocol

from governed_ai_sdk.v1_prototype.types import GovernanceTrace, PolicyRule


class EnvironmentAdapter(Protocol):
    """
    Maps your simulation object to a standard dict.
    """

    def get_state(self, internal_agent: Any) -> Dict[str, Any]:
        """Extract state from any agent object."""
        ...


class PolicyEngine(Protocol):
    """
    Stateless rule verifier.
    """

    def verify(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any],
        policy: Dict[str, Any],
    ) -> GovernanceTrace:
        """Evaluate rules against state."""
        ...


class CounterFactualEngine(Protocol):
    """
    Generates XAI explanations for failed rules.
    """

    def explain(self, failed_rule: PolicyRule, state: Dict[str, Any]) -> str:
        """Return a counterfactual explanation."""
        ...


class Interceptor(Protocol):
    """
    Base interceptor interface for governance layers.
    """

    def intercept(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any],
    ) -> GovernanceTrace:
        """Intercept and validate an action."""
        ...
