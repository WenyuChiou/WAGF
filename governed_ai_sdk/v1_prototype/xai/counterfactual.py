"""
Counterfactual XAI Engine for SDK.

Provides explainable AI through counterfactual analysis:
"What minimal change would make this blocked action pass?"

Three strategies:
- NUMERIC: Delta calculation for threshold rules
- CATEGORICAL: Suggest valid category for membership rules
- COMPOSITE: Multi-objective relaxation for compound rules
"""

from typing import Any, Dict, Optional

from ..types import PolicyRule, CounterFactualResult, CounterFactualStrategy


class CounterfactualEngine:
    """
    Generate XAI explanations for blocked actions.

    For each failed rule, generates a CounterFactualResult explaining
    the minimal state change needed to pass the rule.

    Example:
        >>> engine = CounterfactualEngine()
        >>> rule = PolicyRule(
        ...     id="min_savings", param="savings", operator=">=",
        ...     value=500, message="Need $500", level="ERROR"
        ... )
        >>> result = engine.explain(rule, {"savings": 300})
        >>> print(result.explanation)
        "If savings were +200 (>=500), action would pass."
    """

    def explain(
        self,
        failed_rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Generate counterfactual explanation for a failed rule.

        Args:
            failed_rule: The PolicyRule that blocked the action
            state: Current state dict

        Returns:
            CounterFactualResult with delta_state and explanation
        """
        if failed_rule.operator in (">", "<", ">=", "<="):
            return self._explain_numeric(failed_rule, state)
        elif failed_rule.operator in ("in", "not_in"):
            return self._explain_categorical(failed_rule, state)
        elif failed_rule.operator in ("==", "!="):
            return self._explain_equality(failed_rule, state)
        else:
            return self._explain_composite(failed_rule, state)

    def _explain_numeric(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Numeric delta calculation for threshold rules.

        Handles: >, <, >=, <=
        """
        current = state.get(rule.param, 0)

        # Calculate required delta based on operator
        if rule.operator in (">=", ">"):
            # Need to increase to meet threshold
            if rule.operator == ">=":
                delta = rule.value - current
            else:  # >
                delta = rule.value - current + 0.01  # Slightly above
        else:  # <= or <
            # Need to decrease to meet threshold
            if rule.operator == "<=":
                delta = rule.value - current
            else:  # <
                delta = rule.value - current - 0.01  # Slightly below

        # Feasibility: larger changes are harder
        feasibility = 1.0 / (1 + abs(delta) / 1000) if delta != 0 else 1.0

        return CounterFactualResult(
            passed=False,
            delta_state={rule.param: delta},
            explanation=f"If {rule.param} were {'+' if delta >= 0 else ''}{delta:.2f} ({rule.operator}{rule.value}), action would pass.",
            feasibility_score=feasibility,
            strategy_used=CounterFactualStrategy.NUMERIC
        )

    def _explain_categorical(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Categorical constraint suggestion for membership rules.

        Handles: in, not_in
        """
        current = state.get(rule.param)
        valid_options = rule.value if isinstance(rule.value, list) else [rule.value]

        if rule.operator == "in":
            # Need to be IN the valid options
            suggested = valid_options[0] if valid_options else None
            explanation = f"Change {rule.param} from '{current}' to one of {valid_options}"
        else:  # not_in
            # Need to NOT be in the invalid options
            suggested = f"not_{current}"  # Placeholder - actual value depends on domain
            explanation = f"Change {rule.param} from '{current}' to any value not in {valid_options}"

        return CounterFactualResult(
            passed=False,
            delta_state={rule.param: suggested},
            explanation=explanation,
            feasibility_score=0.5,  # Binary: can or can't change category
            strategy_used=CounterFactualStrategy.CATEGORICAL
        )

    def _explain_equality(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Equality constraint explanation.

        Handles: ==, !=
        """
        current = state.get(rule.param)

        if rule.operator == "==":
            # Need exact match
            delta_value = rule.value
            explanation = f"Change {rule.param} from '{current}' to exactly '{rule.value}'"
        else:  # !=
            # Need to be different
            delta_value = f"not_{rule.value}"
            explanation = f"Change {rule.param} from '{current}' to any value except '{rule.value}'"

        return CounterFactualResult(
            passed=False,
            delta_state={rule.param: delta_value},
            explanation=explanation,
            feasibility_score=0.7,
            strategy_used=CounterFactualStrategy.CATEGORICAL
        )

    def _explain_composite(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Multi-constraint relaxation for compound rules.

        Falls back to generic explanation when rule type is unknown.
        """
        return CounterFactualResult(
            passed=False,
            delta_state={},
            explanation=f"Composite rule '{rule.id}': multiple changes may be needed. Check rule '{rule.param}' with operator '{rule.operator}'.",
            feasibility_score=0.3,
            strategy_used=CounterFactualStrategy.COMPOSITE
        )


def explain_blocked_action(
    rule: PolicyRule,
    state: Dict[str, Any],
    engine: Optional[CounterfactualEngine] = None
) -> CounterFactualResult:
    """
    Convenience function for single-rule explanation.

    Args:
        rule: The failed PolicyRule
        state: Current state dict
        engine: Optional engine instance (creates new if None)

    Returns:
        CounterFactualResult with explanation
    """
    if engine is None:
        engine = CounterfactualEngine()
    return engine.explain(rule, state)
