"""
PolicyEngine - Stateless rule verifier.

Ported from: validators/agent_validator.py (lines 333-455)
Enhanced in Phase 3 with OperatorRegistry support.
"""

from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from governed_ai_sdk.v1_prototype.types import (
    GovernanceTrace,
    PolicyRule,
    RuleOperator,
    RuleLevel,
)
from .operators import OperatorRegistry
from .policy_cache import PolicyCache


class PolicyEngine:
    """
    Stateless rule verification engine.

    Evaluates actions against policy rules and returns traces
    explaining pass/fail status.
    """

    def __init__(self, strict_mode: bool = True, cache_size: int = 100):
        """
        Initialize engine.

        Args:
            strict_mode: If True, ERROR rules block. If False, all are warnings.
        """
        self.strict_mode = strict_mode
        self._cache = PolicyCache(max_size=cache_size)

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
        rules = policy.get("rules", [])
        if rules and all(isinstance(r, PolicyRule) for r in rules):
            return list(rules)
        return self._cache.get_or_compile(policy)

    def batch_verify(
        self,
        requests,
        policy,
        parallel: bool = True,
        max_workers: int = 4
    ) -> List[GovernanceTrace]:
        """
        Verify multiple action-state pairs efficiently.

        Args:
            requests: List of (action, state) tuples
            policy: Policy configuration
            parallel: Whether to use parallel processing
            max_workers: Number of parallel workers

        Returns:
            List of GovernanceTrace results
        """
        if parallel and len(requests) > 10:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                return list(executor.map(
                    lambda req: self.verify(req[0], req[1], policy),
                    requests
                ))
        return [self.verify(action, state, policy) for action, state in requests]

    def _evaluate_rule(self, rule: PolicyRule, state: Dict[str, Any]) -> bool:
        """
        Evaluate a single rule against state using OperatorRegistry.

        Supports all registered operators (default: >, <, >=, <=, ==, !=, in, not_in, between)
        Custom operators can be registered via OperatorRegistry.register().
        """
        value = state.get(rule.param)

        if value is None:
            # Missing param - fail rule for safety
            return False

        op = rule.operator
        target = rule.value

        # Try to use registered operator first
        evaluator = OperatorRegistry.get(op)
        if evaluator is not None:
            return evaluator.evaluate(value, target, context=state)

        # Fallback to legacy hardcoded operators for backwards compatibility
        return self._legacy_evaluate(op, value, target)

    def _legacy_evaluate(self, op: str, value: Any, target: Any) -> bool:
        """Legacy operator evaluation for backwards compatibility."""
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
