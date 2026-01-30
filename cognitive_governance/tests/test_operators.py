"""
Tests for operator registry and custom operators (Phase 3).
"""
import pytest
from cognitive_governance.v1_prototype.core.operators import (
    OperatorRegistry,
    RuleEvaluator,
    GreaterThanEvaluator,
    BetweenEvaluator,
)
from cognitive_governance.v1_prototype.types import CompositeRule, PolicyRule, TemporalRule
from cognitive_governance.v1_prototype.core.engine import PolicyEngine


class TestOperatorRegistry:
    """Tests for OperatorRegistry."""

    def test_builtin_operators(self):
        """Built-in operators are registered."""
        assert OperatorRegistry.has(">")
        assert OperatorRegistry.has(">=")
        assert OperatorRegistry.has("<")
        assert OperatorRegistry.has("<=")
        assert OperatorRegistry.has("==")
        assert OperatorRegistry.has("!=")
        assert OperatorRegistry.has("in")
        assert OperatorRegistry.has("not_in")
        assert OperatorRegistry.has("between")

    def test_aliases_registered(self):
        """Operator aliases are registered."""
        assert OperatorRegistry.has("gt")
        assert OperatorRegistry.has("gte")
        assert OperatorRegistry.has("lt")
        assert OperatorRegistry.has("lte")
        assert OperatorRegistry.has("eq")
        assert OperatorRegistry.has("ne")

    def test_get_operator(self):
        """Can retrieve and use operators."""
        gt = OperatorRegistry.get(">")
        assert gt.evaluate(10, 5) is True
        assert gt.evaluate(5, 10) is False
        assert gt.evaluate(5, 5) is False

    def test_greater_than_or_equal(self):
        """Greater than or equal operator."""
        gte = OperatorRegistry.get(">=")
        assert gte.evaluate(10, 5) is True
        assert gte.evaluate(5, 5) is True
        assert gte.evaluate(4, 5) is False

    def test_less_than(self):
        """Less than operator."""
        lt = OperatorRegistry.get("<")
        assert lt.evaluate(5, 10) is True
        assert lt.evaluate(10, 5) is False
        assert lt.evaluate(5, 5) is False

    def test_less_than_or_equal(self):
        """Less than or equal operator."""
        lte = OperatorRegistry.get("<=")
        assert lte.evaluate(5, 10) is True
        assert lte.evaluate(5, 5) is True
        assert lte.evaluate(10, 5) is False

    def test_equal(self):
        """Equality operator."""
        eq = OperatorRegistry.get("==")
        assert eq.evaluate(5, 5) is True
        assert eq.evaluate("a", "a") is True
        assert eq.evaluate(5, 10) is False

    def test_not_equal(self):
        """Inequality operator."""
        ne = OperatorRegistry.get("!=")
        assert ne.evaluate(5, 10) is True
        assert ne.evaluate(5, 5) is False

    def test_in_operator(self):
        """In operator works with collections."""
        in_op = OperatorRegistry.get("in")
        assert in_op.evaluate("A", ["A", "B", "C"]) is True
        assert in_op.evaluate("D", ["A", "B", "C"]) is False
        assert in_op.evaluate(1, {1, 2, 3}) is True

    def test_not_in_operator(self):
        """Not in operator works with collections."""
        not_in = OperatorRegistry.get("not_in")
        assert not_in.evaluate("D", ["A", "B", "C"]) is True
        assert not_in.evaluate("A", ["A", "B", "C"]) is False

    def test_between_operator(self):
        """Between operator works with ranges."""
        between = OperatorRegistry.get("between")
        assert between.evaluate(5, [1, 10]) is True
        assert between.evaluate(1, [1, 10]) is True  # Inclusive
        assert between.evaluate(10, [1, 10]) is True  # Inclusive
        assert between.evaluate(15, [1, 10]) is False
        assert between.evaluate(0, [1, 10]) is False

    def test_list_operators(self):
        """Can list all registered operators."""
        ops = OperatorRegistry.list_operators()
        assert ">" in ops
        assert ">=" in ops
        assert "between" in ops


class TestCustomOperators:
    """Tests for custom operator registration."""

    def test_custom_operator(self):
        """Can register custom operators."""
        class FuzzyEqualEvaluator:
            def __init__(self, tolerance: float = 0.1):
                self.tolerance = tolerance

            def evaluate(self, value, target, context=None):
                return abs(value - target) <= self.tolerance

            def explain(self, value, target):
                return f"{value} ~= {target} (tolerance: {self.tolerance})"

        OperatorRegistry.register("fuzzy_eq", FuzzyEqualEvaluator(tolerance=0.05))

        fuzzy = OperatorRegistry.get("fuzzy_eq")
        assert fuzzy.evaluate(1.0, 1.03) is True
        assert fuzzy.evaluate(1.0, 1.1) is False

    def test_custom_operator_with_context(self):
        """Custom operator can use context."""
        class PercentageChangeEvaluator:
            def evaluate(self, value, target, context=None):
                if context and "previous" in context:
                    change = (value - context["previous"]) / context["previous"]
                    return change >= target
                return False

            def explain(self, value, target):
                return f"percentage change >= {target}"

        OperatorRegistry.register("pct_change", PercentageChangeEvaluator())

        pct = OperatorRegistry.get("pct_change")
        assert pct.evaluate(110, 0.1, context={"previous": 100}) is True
        assert pct.evaluate(105, 0.1, context={"previous": 100}) is False


class TestEngineWithRegistry:
    """Tests for PolicyEngine using OperatorRegistry."""

    def test_engine_uses_registry(self):
        """Engine uses registered operators."""
        engine = PolicyEngine()
        policy = {
            "rules": [{
                "id": "r1",
                "param": "x",
                "operator": ">=",
                "value": 10,
                "message": "x must be >= 10",
                "level": "ERROR"
            }]
        }

        result = engine.verify({}, {"x": 15}, policy)
        assert result.valid is True

        result = engine.verify({}, {"x": 5}, policy)
        assert result.valid is False

    def test_engine_with_between(self):
        """Engine works with between operator."""
        engine = PolicyEngine()
        policy = {
            "rules": [{
                "id": "r1",
                "param": "age",
                "operator": "between",
                "value": [18, 65],
                "message": "Age must be 18-65",
                "level": "ERROR"
            }]
        }

        result = engine.verify({}, {"age": 30}, policy)
        assert result.valid is True

        result = engine.verify({}, {"age": 10}, policy)
        assert result.valid is False


class TestCompositeRule:
    """Tests for CompositeRule."""

    def test_composite_and(self):
        """AND composite rule creation."""
        rule = CompositeRule(
            id="test",
            logic="AND",
            rules=[
                PolicyRule(id="r1", param="x", operator=">=", value=10, message="x >= 10", level="ERROR"),
                PolicyRule(id="r2", param="y", operator="<=", value=5, message="y <= 5", level="ERROR"),
            ],
            message="Both must pass"
        )
        assert rule.logic == "AND"
        assert len(rule.rules) == 2

    def test_composite_or(self):
        """OR composite rule creation."""
        rule = CompositeRule(
            id="test",
            logic="OR",
            rules=[
                PolicyRule(id="r1", param="x", operator=">=", value=10, message="x >= 10", level="ERROR"),
                PolicyRule(id="r2", param="y", operator=">=", value=10, message="y >= 10", level="ERROR"),
            ],
            message="At least one must pass"
        )
        assert rule.logic == "OR"

    def test_at_least_n_requires_threshold(self):
        """AT_LEAST_N requires threshold."""
        with pytest.raises(ValueError, match="requires threshold"):
            CompositeRule(
                id="test",
                logic="AT_LEAST_N",
                rules=[],
                message="test"
            )

    def test_at_least_n_with_threshold(self):
        """AT_LEAST_N with threshold."""
        rule = CompositeRule(
            id="test",
            logic="AT_LEAST_N",
            rules=[
                PolicyRule(id="r1", param="x", operator=">=", value=10, message="x", level="ERROR"),
                PolicyRule(id="r2", param="y", operator=">=", value=10, message="y", level="ERROR"),
                PolicyRule(id="r3", param="z", operator=">=", value=10, message="z", level="ERROR"),
            ],
            threshold=2,
            message="At least 2 must pass"
        )
        assert rule.threshold == 2

    def test_if_then_requires_condition(self):
        """IF_THEN requires condition_rule."""
        with pytest.raises(ValueError, match="requires condition_rule"):
            CompositeRule(
                id="test",
                logic="IF_THEN",
                rules=[],
                message="test"
            )

    def test_if_then_with_condition(self):
        """IF_THEN with condition."""
        condition = PolicyRule(id="cond", param="is_premium", operator="==", value=True, message="cond", level="ERROR")
        rule = CompositeRule(
            id="test",
            logic="IF_THEN",
            rules=[
                PolicyRule(id="r1", param="discount", operator=">=", value=0.1, message="discount", level="ERROR"),
            ],
            condition_rule=condition,
            message="If premium, then discount >= 10%"
        )
        assert rule.condition_rule is not None


class TestTemporalRule:
    """Tests for TemporalRule."""

    def test_temporal_rule_creation(self):
        """Can create temporal rules."""
        rule = TemporalRule(
            id="savings_trend",
            param="savings",
            operator=">=",
            aggregation="trend",
            window=5,
            value=0.0,
            message="Savings must not be declining"
        )
        assert rule.aggregation == "trend"
        assert rule.window == 5

    def test_temporal_aggregations(self):
        """All aggregation types work."""
        for agg in ["mean", "max", "min", "delta", "trend"]:
            rule = TemporalRule(
                id=f"test_{agg}",
                param="value",
                operator=">=",
                aggregation=agg,
                window=3,
                value=0.0,
                message=f"Test {agg}"
            )
            assert rule.aggregation == agg


class TestExplainMethods:
    """Tests for explain methods on operators."""

    def test_greater_than_explain(self):
        """Greater than explain."""
        gt = OperatorRegistry.get(">")
        assert gt.explain(10, 5) == "10 > 5"

    def test_between_explain(self):
        """Between explain."""
        between = OperatorRegistry.get("between")
        assert between.explain(5, [1, 10]) == "1 <= 5 <= 10"

    def test_in_explain(self):
        """In explain."""
        in_op = OperatorRegistry.get("in")
        assert "in" in in_op.explain("A", ["A", "B", "C"])
