"""
PolicyEngine - Stateless rule verifier.

Ported from: validators/agent_validator.py (lines 333-455)
"""

from typing import Any, Dict, List, Optional
from governed_ai_sdk.v1_prototype.types import (
    GovernanceTrace,
    PolicyRule,
    RuleOperator,
    RuleLevel,
)


class PolicyEngine:
    """
    Stateless rule verification engine.

    Evaluates actions against policy rules and returns traces
    explaining pass/fail status.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize engine.

        Args:
            strict_mode: If True, ERROR rules block. If False, all are warnings.
        """
        self.strict_mode = strict_mode

    def verify(
        self,
        action: Dict[str, Any],
        state: Dict[str, Any],
        policy: Dict[str, Any]
    ) -> GovernanceTrace:
        """
        Verify action against policy rules.

        Args:
            action: The action to verify (e.g., {"action": "buy", "amount": 100})
            state: Current state (e.g., {"savings": 300, "status": "normal"})
            policy: Policy dict with "rules" key containing PolicyRule-like dicts

        Returns:
            GovernanceTrace with pass/fail status and reasoning
        """
        rules = self._load_rules(policy)

        for rule in rules:
            passed = self._evaluate_rule(rule, state)

            if not passed:
                # Calculate state delta for XAI
                delta = self._calculate_delta(rule, state)

                return GovernanceTrace(
                    valid=False,
                    rule_id=rule.id,
                    rule_message=rule.message,
                    blocked_action=action,
                    state_delta=delta,
                    evaluated_state=state,
                    policy_id=policy.get("id", "unknown"),
                )

        # All rules passed
        return GovernanceTrace(
            valid=True,
            rule_id="all_passed",
            rule_message="All policy rules satisfied",
            evaluated_state=state,
            policy_id=policy.get("id", "unknown"),
        )

    def _load_rules(self, policy: Dict[str, Any]) -> List[PolicyRule]:
        """Convert policy dict to PolicyRule objects."""
        rules = []
        for r in policy.get("rules", []):
            if isinstance(r, PolicyRule):
                rules.append(r)
            elif isinstance(r, dict):
                rules.append(PolicyRule(**r))
        return rules

    def _evaluate_rule(self, rule: PolicyRule, state: Dict[str, Any]) -> bool:
        """
        Evaluate a single rule against state.

        Supports operators: >, <, >=, <=, ==, !=, in, not_in
        """
        value = state.get(rule.param)

        if value is None:
            # Missing param - fail rule for safety
            return False

        op = rule.operator
        target = rule.value

        # Numeric comparisons
        if op == ">":
            return value > target
        elif op == "<":
            return value < target
        elif op == ">=":
            return value >= target
        elif op == "<=":
            return value <= target
        elif op == "==":
            return value == target
        elif op == "!=":
            return value != target
        # Categorical comparisons
        elif op == "in":
            return value in target
        elif op == "not_in":
            return value not in target

        # Unknown operator - fail for safety
        return False

    def _calculate_delta(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> Optional[Dict[str, float]]:
        """
        Calculate minimal state change to pass the rule (for XAI).

        Only works for numeric rules.
        """
        if rule.operator not in (">", "<", ">=", "<="):
            return None

        current = state.get(rule.param, 0)
        target = rule.value

        if rule.operator in (">", ">="):
            delta = target - current
            if rule.operator == ">":
                delta += 0.01  # Need strictly greater
            return {rule.param: delta} if delta > 0 else None

        elif rule.operator in ("<", "<="):
            delta = current - target
            if rule.operator == "<":
                delta += 0.01
            return {rule.param: -delta} if delta > 0 else None

        return None


def create_engine(strict_mode: bool = True) -> PolicyEngine:
    """Factory function for creating PolicyEngine."""
    return PolicyEngine(strict_mode=strict_mode)
