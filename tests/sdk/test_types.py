"""
Test suite for GovernedAI SDK type definitions.

Run: pytest cognitive_governance/tests/test_types.py -v
"""

import pytest
from cognitive_governance.v1_prototype.types import (
    PolicyRule,
    GovernanceTrace,
    CounterFactualResult,
    EntropyFriction,
    CounterFactualStrategy,
    RuleOperator,
    RuleLevel,
)


class TestPolicyRule:
    """Tests for PolicyRule dataclass."""

    def test_numeric_rule_creation(self):
        """Test creating a numeric threshold rule."""
        rule = PolicyRule(
            id="min_savings",
            param="savings",
            operator=">=",
            value=500,
            message="Insufficient savings for this action",
            level="ERROR",
        )
        assert rule.id == "min_savings"
        assert rule.param == "savings"
        assert rule.operator == ">="
        assert rule.value == 500
        assert rule.level == "ERROR"

    def test_categorical_rule_creation(self):
        """Test creating a categorical IN rule."""
        rule = PolicyRule(
            id="valid_status",
            param="status",
            operator="in",
            value=["elevated", "insured"],
            message="Status must be elevated or insured",
            level="WARNING",
        )
        assert rule.operator == "in"
        assert "elevated" in rule.value
        assert rule.level == "WARNING"

    def test_invalid_operator_raises(self):
        """Test that invalid operators raise ValueError."""
        with pytest.raises(ValueError, match="Invalid operator"):
            PolicyRule(
                id="bad",
                param="x",
                operator="INVALID",
                value=1,
                message="",
                level="ERROR",
            )

    def test_invalid_level_raises(self):
        """Test that invalid levels raise ValueError."""
        with pytest.raises(ValueError, match="Invalid level"):
            PolicyRule(
                id="bad",
                param="x",
                operator=">=",
                value=1,
                message="",
                level="CRITICAL",  # Invalid
            )

    def test_xai_hint(self):
        """Test XAI hint field."""
        rule = PolicyRule(
            id="r1",
            param="savings",
            operator=">=",
            value=500,
            message="",
            level="ERROR",
            xai_hint="recommend_grant",
        )
        assert rule.xai_hint == "recommend_grant"


class TestGovernanceTrace:
    """Tests for GovernanceTrace dataclass."""

    def test_valid_trace(self):
        """Test trace for allowed action."""
        trace = GovernanceTrace(
            valid=True,
            rule_id="min_savings",
            rule_message="Savings check passed",
        )
        assert trace.valid is True
        assert "ALLOWED" in trace.explain()

    def test_blocked_trace(self):
        """Test trace for blocked action."""
        trace = GovernanceTrace(
            valid=False,
            rule_id="min_savings",
            rule_message="Insufficient savings",
            state_delta={"savings": 200},
        )
        assert trace.valid is False
        explanation = trace.explain()
        assert "BLOCKED" in explanation
        assert "min_savings" in explanation
        assert "savings" in explanation

    def test_trace_with_entropy(self):
        """Test trace with entropy friction."""
        trace = GovernanceTrace(
            valid=False,
            rule_id="r1",
            rule_message="Test",
            entropy_friction=1.5,
        )
        assert trace.entropy_friction == 1.5
        assert "friction" in trace.explain().lower()


class TestCounterFactualResult:
    """Tests for CounterFactualResult dataclass."""

    def test_numeric_counterfactual(self):
        """Test numeric strategy counterfactual."""
        cf = CounterFactualResult(
            passed=False,
            delta_state={"savings": 200},
            explanation="If savings were +200, action would pass",
            feasibility_score=0.8,
            strategy_used=CounterFactualStrategy.NUMERIC,
        )
        assert cf.passed is False
        assert cf.delta_state["savings"] == 200
        assert cf.feasibility_score == 0.8
        assert cf.strategy_used == CounterFactualStrategy.NUMERIC

    def test_categorical_counterfactual(self):
        """Test categorical strategy counterfactual."""
        cf = CounterFactualResult(
            passed=False,
            delta_state={"status": "elevated"},
            explanation="Change status to 'elevated'",
            feasibility_score=0.5,
            strategy_used=CounterFactualStrategy.CATEGORICAL,
        )
        assert cf.strategy_used == CounterFactualStrategy.CATEGORICAL

    def test_invalid_feasibility_raises(self):
        """Test that feasibility outside 0-1 raises ValueError."""
        with pytest.raises(ValueError, match="feasibility_score must be 0-1"):
            CounterFactualResult(
                passed=False,
                delta_state={},
                explanation="",
                feasibility_score=1.5,  # Invalid
            )


class TestEntropyFriction:
    """Tests for EntropyFriction dataclass."""

    def test_over_governed(self):
        """Test over-governed scenario detection."""
        ef = EntropyFriction(
            S_raw=2.5,
            S_governed=1.0,
            friction_ratio=2.5,
            kl_divergence=0.8,
        )
        assert ef.is_over_governed is True
        assert ef.interpretation == "Over-Governed"

    def test_balanced(self):
        """Test balanced governance detection."""
        ef = EntropyFriction(
            S_raw=1.5,
            S_governed=1.4,
            friction_ratio=1.07,
            kl_divergence=0.1,
        )
        assert ef.is_over_governed is False
        assert ef.interpretation == "Balanced"

    def test_under_governed(self):
        """Test under-governed scenario detection."""
        ef = EntropyFriction(
            S_raw=1.0,
            S_governed=1.5,
            friction_ratio=0.67,
            kl_divergence=0.05,
        )
        assert ef.is_over_governed is False
        assert ef.interpretation == "Under-Governed"

    def test_explain_method(self):
        """Test explain() generates readable output."""
        ef = EntropyFriction(
            S_raw=2.0,
            S_governed=1.0,
            friction_ratio=2.0,
            kl_divergence=0.5,
            raw_action_count=100,
            governed_action_count=60,
            blocked_action_count=40,
        )
        explanation = ef.explain()
        assert "Entropy" in explanation
        assert "Friction" in explanation


class TestEnums:
    """Tests for enum classes."""

    def test_rule_operators(self):
        """Test RuleOperator enum values."""
        assert RuleOperator.GT.value == ">"
        assert RuleOperator.LTE.value == "<="
        assert RuleOperator.IN.value == "in"

    def test_rule_levels(self):
        """Test RuleLevel enum values."""
        assert RuleLevel.ERROR.value == "ERROR"
        assert RuleLevel.WARNING.value == "WARNING"

    def test_counterfactual_strategies(self):
        """Test CounterFactualStrategy enum values."""
        assert CounterFactualStrategy.NUMERIC.value == "numeric_delta"
        assert CounterFactualStrategy.CATEGORICAL.value == "categorical_flip"
        assert CounterFactualStrategy.COMPOSITE.value == "multi_objective"
