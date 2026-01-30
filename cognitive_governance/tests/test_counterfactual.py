"""
Tests for Phase 4A: Counterfactual XAI Engine.

Verifies CounterfactualEngine generates correct explanations for all rule types.
"""

import pytest
from cognitive_governance.v1_prototype.types import (
    PolicyRule,
    CounterFactualResult,
    CounterFactualStrategy,
)
from cognitive_governance.v1_prototype.xai.counterfactual import (
    CounterfactualEngine,
    explain_blocked_action,
)


class TestNumericExplanations:
    """Test numeric delta calculations (>, <, >=, <=)."""

    def test_greater_than_or_equal(self):
        """Test >= operator."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="min_savings",
            param="savings",
            operator=">=",
            value=500,
            message="Need $500 minimum",
            level="ERROR"
        )

        result = engine.explain(rule, {"savings": 300})

        assert result.passed is False
        assert result.delta_state["savings"] == 200
        assert result.strategy_used == CounterFactualStrategy.NUMERIC
        assert "200" in result.explanation or "+200" in result.explanation

    def test_greater_than(self):
        """Test > operator."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="r1", param="x", operator=">",
            value=100, message="", level="ERROR"
        )

        result = engine.explain(rule, {"x": 100})

        assert result.passed is False
        assert result.delta_state["x"] > 0  # Need to be above 100
        assert result.strategy_used == CounterFactualStrategy.NUMERIC

    def test_less_than_or_equal(self):
        """Test <= operator."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="max_debt", param="debt", operator="<=",
            value=1000, message="Debt too high", level="ERROR"
        )

        result = engine.explain(rule, {"debt": 1500})

        assert result.passed is False
        assert result.delta_state["debt"] == -500  # Need to decrease by 500
        assert result.strategy_used == CounterFactualStrategy.NUMERIC

    def test_less_than(self):
        """Test < operator."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="r1", param="risk", operator="<",
            value=0.5, message="", level="ERROR"
        )

        result = engine.explain(rule, {"risk": 0.5})

        assert result.passed is False
        assert result.delta_state["risk"] < 0  # Need to be below 0.5
        assert result.strategy_used == CounterFactualStrategy.NUMERIC

    def test_missing_state_param(self):
        """Missing state parameter defaults to 0."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="r1", param="savings", operator=">=",
            value=100, message="", level="ERROR"
        )

        result = engine.explain(rule, {})  # No savings in state

        assert result.delta_state["savings"] == 100  # 100 - 0 = 100

    def test_feasibility_score(self):
        """Larger deltas should have lower feasibility."""
        engine = CounterfactualEngine()

        # Small delta
        rule1 = PolicyRule(
            id="r1", param="x", operator=">=",
            value=110, message="", level="ERROR"
        )
        result1 = engine.explain(rule1, {"x": 100})

        # Large delta
        rule2 = PolicyRule(
            id="r2", param="x", operator=">=",
            value=10000, message="", level="ERROR"
        )
        result2 = engine.explain(rule2, {"x": 100})

        assert result1.feasibility_score > result2.feasibility_score


class TestCategoricalExplanations:
    """Test categorical constraint suggestions (in, not_in)."""

    def test_in_operator(self):
        """Test 'in' operator."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="valid_status", param="status", operator="in",
            value=["elevated", "insured"], message="Invalid status", level="ERROR"
        )

        result = engine.explain(rule, {"status": "normal"})

        assert result.passed is False
        assert result.delta_state["status"] in ["elevated", "insured"]
        assert result.strategy_used == CounterFactualStrategy.CATEGORICAL
        assert "elevated" in result.explanation or "insured" in result.explanation

    def test_not_in_operator(self):
        """Test 'not_in' operator."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="no_blacklist", param="category", operator="not_in",
            value=["banned", "suspended"], message="", level="ERROR"
        )

        result = engine.explain(rule, {"category": "banned"})

        assert result.passed is False
        assert result.strategy_used == CounterFactualStrategy.CATEGORICAL
        assert "not in" in result.explanation.lower()

    def test_categorical_feasibility(self):
        """Categorical changes have fixed feasibility (0.5)."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="r1", param="status", operator="in",
            value=["active"], message="", level="ERROR"
        )

        result = engine.explain(rule, {"status": "inactive"})

        assert result.feasibility_score == 0.5


class TestEqualityExplanations:
    """Test equality constraint explanations (==, !=)."""

    def test_equals_operator(self):
        """Test == operator."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="exact_match", param="code", operator="==",
            value="ABC123", message="Code mismatch", level="ERROR"
        )

        result = engine.explain(rule, {"code": "XYZ999"})

        assert result.passed is False
        assert result.delta_state["code"] == "ABC123"
        assert "ABC123" in result.explanation

    def test_not_equals_operator(self):
        """Test != operator."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="not_banned", param="type", operator="!=",
            value="banned", message="", level="ERROR"
        )

        result = engine.explain(rule, {"type": "banned"})

        assert result.passed is False
        assert "except" in result.explanation.lower() or "not_banned" in str(result.delta_state)


class TestCompositeExplanations:
    """Test composite/unknown rule explanations."""

    def test_unknown_operator(self):
        """Unknown operators fall back to composite strategy."""
        engine = CounterfactualEngine()
        # Manually bypass validation for test
        rule = PolicyRule.__new__(PolicyRule)
        rule.id = "r1"
        rule.param = "x"
        rule.operator = "custom_op"
        rule.value = 100
        rule.message = "Custom rule"
        rule.level = "ERROR"
        rule.xai_hint = None

        result = engine.explain(rule, {"x": 50})

        assert result.passed is False
        assert result.strategy_used == CounterFactualStrategy.COMPOSITE
        assert result.feasibility_score == 0.3  # Low for composite


class TestConvenienceFunction:
    """Test explain_blocked_action convenience function."""

    def test_with_default_engine(self):
        """Use default engine instance."""
        rule = PolicyRule(
            id="r1", param="savings", operator=">=",
            value=500, message="", level="ERROR"
        )

        result = explain_blocked_action(rule, {"savings": 300})

        assert result.delta_state["savings"] == 200

    def test_with_custom_engine(self):
        """Use provided engine instance."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="r1", param="x", operator=">=",
            value=100, message="", level="ERROR"
        )

        result = explain_blocked_action(rule, {"x": 50}, engine=engine)

        assert result.delta_state["x"] == 50


class TestCounterFactualResult:
    """Test CounterFactualResult dataclass from types."""

    def test_valid_result(self):
        """Create valid result."""
        result = CounterFactualResult(
            passed=False,
            delta_state={"savings": 200},
            explanation="Need +$200",
            feasibility_score=0.8,
            strategy_used=CounterFactualStrategy.NUMERIC
        )
        assert result.feasibility_score == 0.8

    def test_invalid_feasibility_raises(self):
        """Invalid feasibility score should raise."""
        with pytest.raises(ValueError):
            CounterFactualResult(
                passed=False,
                delta_state={},
                explanation="",
                feasibility_score=1.5,  # Invalid: > 1.0
                strategy_used=CounterFactualStrategy.NUMERIC
            )

        with pytest.raises(ValueError):
            CounterFactualResult(
                passed=False,
                delta_state={},
                explanation="",
                feasibility_score=-0.1,  # Invalid: < 0.0
                strategy_used=CounterFactualStrategy.NUMERIC
            )

    def test_with_metadata(self):
        """Result with optional metadata."""
        rule = PolicyRule(
            id="r1", param="x", operator=">=",
            value=100, message="", level="ERROR"
        )
        result = CounterFactualResult(
            passed=False,
            delta_state={"x": 50},
            explanation="Need +50",
            feasibility_score=0.9,
            strategy_used=CounterFactualStrategy.NUMERIC,
            original_state={"x": 50},
            failed_rule=rule
        )
        assert result.original_state == {"x": 50}
        assert result.failed_rule.id == "r1"
