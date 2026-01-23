"""
Test suite for PolicyEngine.

Run: pytest governed_ai_sdk/tests/test_policy_engine.py -v
"""

import pytest
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader, load_policy
from governed_ai_sdk.v1_prototype.types import PolicyRule, GovernanceTrace


class TestPolicyEngine:
    """Tests for PolicyEngine class."""

    def test_numeric_rule_pass(self):
        """Test that sufficient savings passes."""
        engine = PolicyEngine()
        policy = {
            "rules": [
                {"id": "min_savings", "param": "savings", "operator": ">=",
                 "value": 500, "message": "Need $500", "level": "ERROR"}
            ]
        }

        trace = engine.verify(
            action={"action": "buy"},
            state={"savings": 600},
            policy=policy
        )

        assert trace.valid is True
        assert trace.rule_id == "all_passed"

    def test_numeric_rule_fail(self):
        """Test that insufficient savings fails."""
        engine = PolicyEngine()
        policy = {
            "rules": [
                {"id": "min_savings", "param": "savings", "operator": ">=",
                 "value": 500, "message": "Need $500", "level": "ERROR"}
            ]
        }

        trace = engine.verify(
            action={"action": "buy"},
            state={"savings": 300},
            policy=policy
        )

        assert trace.valid is False
        assert trace.rule_id == "min_savings"
        assert trace.state_delta is not None
        assert trace.state_delta["savings"] == 200  # Need +200 to reach 500

    def test_categorical_rule_pass(self):
        """Test categorical IN rule passes."""
        engine = PolicyEngine()
        policy = {
            "rules": [
                {"id": "valid_status", "param": "status", "operator": "in",
                 "value": ["active", "pending"], "message": "Invalid status", "level": "ERROR"}
            ]
        }

        trace = engine.verify(
            action={"action": "renew"},
            state={"status": "active"},
            policy=policy
        )

        assert trace.valid is True

    def test_categorical_rule_fail(self):
        """Test categorical IN rule fails."""
        engine = PolicyEngine()
        policy = {
            "rules": [
                {"id": "valid_status", "param": "status", "operator": "in",
                 "value": ["active", "pending"], "message": "Invalid status", "level": "ERROR"}
            ]
        }

        trace = engine.verify(
            action={"action": "renew"},
            state={"status": "expired"},
            policy=policy
        )

        assert trace.valid is False
        assert trace.rule_id == "valid_status"

    def test_multiple_rules_first_fail(self):
        """Test that first failing rule is reported."""
        engine = PolicyEngine()
        policy = {
            "rules": [
                {"id": "rule1", "param": "a", "operator": ">=",
                 "value": 10, "message": "a too low", "level": "ERROR"},
                {"id": "rule2", "param": "b", "operator": ">=",
                 "value": 20, "message": "b too low", "level": "ERROR"},
            ]
        }

        trace = engine.verify(
            action={},
            state={"a": 5, "b": 5},  # Both fail
            policy=policy
        )

        assert trace.valid is False
        assert trace.rule_id == "rule1"  # First rule reported

    def test_missing_param_fails(self):
        """Test that missing param in state fails rule."""
        engine = PolicyEngine()
        policy = {
            "rules": [
                {"id": "r1", "param": "missing", "operator": ">=",
                 "value": 100, "message": "Missing param", "level": "ERROR"}
            ]
        }

        trace = engine.verify(
            action={},
            state={"other": 500},
            policy=policy
        )

        assert trace.valid is False


class TestPolicyLoader:
    """Tests for PolicyLoader class."""

    def test_from_dict(self):
        """Test loading from dict."""
        policy = PolicyLoader.from_dict({
            "id": "test",
            "rules": [
                {"id": "r1", "param": "x", "operator": ">=",
                 "value": 10, "message": "x too low", "level": "ERROR"}
            ]
        })

        assert policy["id"] == "test"
        assert len(policy["rules"]) == 1

    def test_from_rules(self):
        """Test creating policy from PolicyRule objects."""
        rules = [
            PolicyRule(id="r1", param="savings", operator=">=",
                      value=500, message="Need $500", level="ERROR")
        ]

        policy = PolicyLoader.from_rules(rules, policy_id="inline_test")

        assert policy["id"] == "inline_test"
        assert len(policy["_validated_rules"]) == 1

    def test_invalid_rule_raises(self):
        """Test that invalid rule raises ValueError."""
        with pytest.raises(ValueError):
            PolicyLoader.from_dict({
                "rules": [
                    {"id": "bad", "param": "x", "operator": "INVALID",
                     "value": 1, "message": "", "level": "ERROR"}
                ]
            })
