"""
Counterfactual XAI Engine for SDK.

Provides explainable AI through counterfactual analysis:
"What minimal change would make this blocked action pass?"

Three strategies:
- NUMERIC: Delta calculation for threshold rules
- CATEGORICAL: Suggest valid category for membership rules (with domain-aware feasibility)
- COMPOSITE: Multi-objective relaxation for compound rules

Phase 4 Enhancement: Domain-aware categorical feasibility scoring.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..types import PolicyRule, CounterFactualResult, CounterFactualStrategy, CompositeRule

if TYPE_CHECKING:
    from .feasibility import CategoricalFeasibilityScorer


class CounterfactualEngine:
    """
    Generate XAI explanations for blocked actions.

    For each failed rule, generates a CounterFactualResult explaining
    the minimal state change needed to pass the rule.

    Phase 4 Enhancement: Supports domain-aware categorical feasibility scoring
    via CategoricalFeasibilityScorer.

    Example:
        >>> engine = CounterfactualEngine()
        >>> rule = PolicyRule(
        ...     id="min_savings", param="savings", operator=">=",
        ...     value=500, message="Need $500", level="ERROR"
        ... )
        >>> result = engine.explain(rule, {"savings": 300})
        >>> print(result.explanation)
        "If savings were +200 (>=500), action would pass."

        # With feasibility scorer:
        >>> from cognitive_governance.v1_prototype.xai.feasibility import create_default_scorer
        >>> engine = CounterfactualEngine(feasibility_scorer=create_default_scorer())
        >>> result = engine.explain(categorical_rule, state)
        >>> print(result.feasibility_score)  # Domain-aware score instead of 0.5
    """

    def __init__(
        self,
        feasibility_scorer: Optional["CategoricalFeasibilityScorer"] = None,
    ):
        """
        Initialize CounterfactualEngine.

        Args:
            feasibility_scorer: Optional scorer for domain-aware categorical
                               feasibility. If None, uses fixed 0.5 score.
        """
        self.feasibility_scorer = feasibility_scorer

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

        Phase 4 Enhancement: Uses CategoricalFeasibilityScorer for domain-aware
        feasibility scoring instead of fixed 0.5.
        """
        current = state.get(rule.param)
        valid_options = rule.value if isinstance(rule.value, list) else [rule.value]

        # Get domain from rule (Phase 1 enhancement)
        domain = getattr(rule, "domain", "generic")

        if rule.operator == "in":
            # Need to be IN the valid options
            if self.feasibility_scorer and current:
                # Use scorer to rank options by feasibility
                ranked = self.feasibility_scorer.rank_options(
                    rule.param, current, valid_options, domain
                )
                if ranked:
                    best = ranked[0]
                    suggested = best.to_value
                    feasibility = best.feasibility
                    rationale = best.rationale
                else:
                    suggested = valid_options[0] if valid_options else None
                    feasibility = 0.5
                    rationale = None
            else:
                suggested = valid_options[0] if valid_options else None
                feasibility = 0.5
                rationale = None

            if rationale:
                explanation = f"Change {rule.param} from '{current}' to '{suggested}' ({rationale}) [feasibility: {feasibility:.0%}]"
            else:
                explanation = f"Change {rule.param} from '{current}' to '{suggested}' [feasibility: {feasibility:.0%}]"

        else:  # not_in
            # Need to NOT be in the invalid options
            suggested = f"not_{current}"  # Placeholder - actual value depends on domain
            feasibility = 0.4  # Default for not_in
            explanation = f"Change {rule.param} from '{current}' to any value not in {valid_options}"

        return CounterFactualResult(
            passed=False,
            delta_state={rule.param: suggested},
            explanation=explanation,
            feasibility_score=feasibility,
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

    def explain_composite_rule(
        self,
        rule: CompositeRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Explain a CompositeRule by finding the easiest path to satisfaction.

        Phase 4 Enhancement: Analyzes sub-rules and suggests the most feasible
        change path based on individual rule feasibility scores.

        Args:
            rule: CompositeRule with multiple sub-rules
            state: Current state dict

        Returns:
            CounterFactualResult with the easiest path explanation
        """
        if not rule.rules:
            return CounterFactualResult(
                passed=True,
                delta_state={},
                explanation="No sub-rules to evaluate.",
                feasibility_score=1.0,
                strategy_used=CounterFactualStrategy.COMPOSITE
            )

        # Explain each sub-rule
        sub_results = [self.explain(sub, state) for sub in rule.rules]

        if rule.logic == "OR":
            # For OR: find the easiest single change
            easiest = max(sub_results, key=lambda r: r.feasibility_score)
            return CounterFactualResult(
                passed=False,
                delta_state=easiest.delta_state,
                explanation=f"Easiest path (OR): {easiest.explanation}",
                feasibility_score=easiest.feasibility_score,
                strategy_used=CounterFactualStrategy.COMPOSITE
            )

        elif rule.logic == "AND":
            # For AND: all changes needed, feasibility is product
            combined_delta = {}
            explanations = []
            feasibility = 1.0

            for result in sub_results:
                combined_delta.update(result.delta_state)
                explanations.append(result.explanation)
                feasibility *= result.feasibility_score

            return CounterFactualResult(
                passed=False,
                delta_state=combined_delta,
                explanation=f"All required (AND): {'; '.join(explanations)}",
                feasibility_score=feasibility,
                strategy_used=CounterFactualStrategy.COMPOSITE
            )

        elif rule.logic == "IF_THEN":
            # For IF_THEN: if condition met, explain consequent
            # Check for condition_rule attribute (proper IF_THEN structure)
            condition_rule = getattr(rule, "condition_rule", None)

            if condition_rule:
                condition_result = self.explain(condition_rule, state)
                # If we have consequent rules, explain them
                if sub_results:
                    consequent_result = sub_results[0]
                    return CounterFactualResult(
                        passed=False,
                        delta_state=consequent_result.delta_state,
                        explanation=f"Condition '{condition_rule.param}': {consequent_result.explanation}",
                        feasibility_score=consequent_result.feasibility_score,
                        strategy_used=CounterFactualStrategy.COMPOSITE
                    )

            elif len(rule.rules) >= 2:
                # Legacy format: first rule is condition, rest are consequents
                condition_result = sub_results[0]
                consequent_result = sub_results[1]

                # Check if condition would pass
                if condition_result.feasibility_score > 0.5:
                    return CounterFactualResult(
                        passed=False,
                        delta_state=consequent_result.delta_state,
                        explanation=f"Since condition met, required: {consequent_result.explanation}",
                        feasibility_score=consequent_result.feasibility_score,
                        strategy_used=CounterFactualStrategy.COMPOSITE
                    )
                else:
                    return CounterFactualResult(
                        passed=True,
                        delta_state={},
                        explanation="Condition not met, consequent not required.",
                        feasibility_score=1.0,
                        strategy_used=CounterFactualStrategy.COMPOSITE
                    )

        # Fallback for unknown logic
        return CounterFactualResult(
            passed=False,
            delta_state={},
            explanation=f"Composite rule '{rule.id}' with logic '{rule.logic}': analyze sub-rules individually.",
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
