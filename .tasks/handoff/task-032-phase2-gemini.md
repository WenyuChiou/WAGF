# Task-032 Phase 2: Policy Engine (Gemini CLI)

**Status**: 🔲 Ready for Implementation
**Assignee**: Gemini CLI
**Effort**: 4-5 hours
**Priority**: HIGH
**Prerequisite**: Phase 0 ✅ COMPLETE, Phase 1 (Codex skeleton)

---

## Git Branch

```bash
# Wait for Phase 1 to complete, then:
git checkout task-032-phase1
git checkout -b task-032-phase2

# Or if Phase 1 is not done yet, start from base:
git checkout task-032-sdk-base
git checkout -b task-032-phase2
```

**Stacked PR Structure**:
```
main
 └── task-032-sdk-base (Phase 0)
      └── task-032-phase1 (Codex)
           └── task-032-phase2 (this branch) ← YOUR WORK HERE
```

---

## Objective

Port the rule evaluation logic from `validators/agent_validator.py` to create a clean, stateless `PolicyEngine` class that supports numeric, categorical, and composite rules.

---

## Prerequisite Verification

Before starting, verify Phase 0 is complete:

```bash
cd c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework
python -c "from governed_ai_sdk.v1_prototype.types import GovernanceTrace, PolicyRule, RuleOperator; print('Phase 0 OK')"
```

---

## Source → Destination Mapping

| Source | Lines | Destination | Action |
|--------|-------|-------------|--------|
| `validators/agent_validator.py` | 333-455 | `core/engine.py` | Extract `_run_rule_set` |
| `broker/utils/agent_config.py` | 50-150 | `core/policy_loader.py` | Simplify (Dict/YAML only) |

---

## Remove These Dependencies

When porting, DO NOT include:
- ❌ CSV loading (use Dict/YAML only)
- ❌ GovernanceAuditor integration (SDK has own audit)
- ❌ ResponseFormatBuilder (SDK handles separately)
- ❌ InteractionHub references
- ❌ Any pandas/DataFrame usage

---

## Deliverables

### 1. `core/engine.py` - PolicyEngine Class

```python
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
```

### 2. `core/policy_loader.py` - Policy Loading

```python
"""
PolicyLoader - Load policies from Dict or YAML.

Simplified from: broker/utils/agent_config.py
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from governed_ai_sdk.v1_prototype.types import PolicyRule


class PolicyLoader:
    """
    Load and parse policy definitions.

    Supports:
        - Direct Dict input
        - YAML file loading
        - Inline rule definition
    """

    @staticmethod
    def from_dict(policy_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load policy from a dictionary.

        Expected format:
            {
                "id": "financial_prudence",
                "rules": [
                    {"id": "min_savings", "param": "savings", "operator": ">=", ...}
                ]
            }
        """
        # Validate structure
        if "rules" not in policy_dict:
            policy_dict["rules"] = []

        # Convert rule dicts to PolicyRule objects for validation
        validated_rules = []
        for r in policy_dict["rules"]:
            if isinstance(r, dict):
                # This will raise ValueError if invalid
                rule = PolicyRule(**r)
                validated_rules.append(rule)
            elif isinstance(r, PolicyRule):
                validated_rules.append(r)

        policy_dict["_validated_rules"] = validated_rules
        return policy_dict

    @staticmethod
    def from_yaml(yaml_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load policy from YAML file.

        Expected YAML format:
            id: financial_prudence
            rules:
              - id: min_savings
                param: savings
                operator: ">="
                value: 500
                message: "Insufficient savings"
                level: ERROR
        """
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            policy_dict = yaml.safe_load(f)

        return PolicyLoader.from_dict(policy_dict)

    @staticmethod
    def from_rules(rules: List[PolicyRule], policy_id: str = "inline") -> Dict[str, Any]:
        """
        Create policy from a list of PolicyRule objects.

        Useful for programmatic rule definition.
        """
        return {
            "id": policy_id,
            "rules": [
                {
                    "id": r.id,
                    "param": r.param,
                    "operator": r.operator,
                    "value": r.value,
                    "message": r.message,
                    "level": r.level,
                    "xai_hint": r.xai_hint,
                }
                for r in rules
            ],
            "_validated_rules": rules,
        }


def load_policy(source: Union[str, Path, Dict]) -> Dict[str, Any]:
    """
    Convenience function to load policy from any source.

    Args:
        source: YAML path, or policy dict

    Returns:
        Validated policy dictionary
    """
    if isinstance(source, dict):
        return PolicyLoader.from_dict(source)
    elif isinstance(source, (str, Path)):
        path = Path(source)
        if path.suffix in (".yaml", ".yml"):
            return PolicyLoader.from_yaml(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")
```

### 3. Example Policy File

Create `governed_ai_sdk/policies/financial_prudence.yaml`:

```yaml
# Example policy for flood ABM household agents
id: financial_prudence
description: "Ensures agents maintain financial stability before major purchases"

rules:
  - id: min_savings
    param: savings
    operator: ">="
    value: 500
    message: "Insufficient savings for this action"
    level: ERROR
    xai_hint: recommend_grant

  - id: debt_ratio
    param: debt_to_income
    operator: "<="
    value: 0.4
    message: "Debt-to-income ratio too high"
    level: ERROR

  - id: valid_insurance_status
    param: insurance_status
    operator: in
    value: ["none", "pending", "active", "lapsed"]
    message: "Invalid insurance status"
    level: WARNING
```

---

## Update `core/__init__.py`

```python
"""
Core SDK components.
"""

from .engine import PolicyEngine, create_engine
from .policy_loader import PolicyLoader, load_policy

__all__ = [
    "PolicyEngine",
    "create_engine",
    "PolicyLoader",
    "load_policy",
]
```

---

## Test Cases (Create `tests/test_policy_engine.py`)

```python
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
```

---

## Verification Commands

```bash
# 1. Verify engine imports
python -c "from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine; print('OK')"

# 2. Verify policy loader imports
python -c "from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader, load_policy; print('OK')"

# 3. Run engine tests
pytest governed_ai_sdk/tests/test_policy_engine.py -v

# 4. Integration test
python -c "
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine

engine = PolicyEngine()
policy = {
    'rules': [
        {'id': 'min_savings', 'param': 'savings', 'operator': '>=',
         'value': 500, 'message': 'Need \$500', 'level': 'ERROR'}
    ]
}

# Test pass
trace = engine.verify({}, {'savings': 600}, policy)
assert trace.valid, 'Should pass with 600'

# Test fail
trace = engine.verify({}, {'savings': 300}, policy)
assert not trace.valid, 'Should fail with 300'
assert trace.state_delta['savings'] == 200, 'Delta should be 200'

print('Integration test PASSED')
"

# 5. Run all SDK tests
pytest governed_ai_sdk/tests/ -v
```

---

## Success Criteria

1. PolicyEngine.verify() works for numeric rules (>, <, >=, <=)
2. PolicyEngine.verify() works for categorical rules (in, not_in)
3. State delta calculation works for XAI explanations
4. PolicyLoader can load from dict and YAML
5. At least 8 tests pass in test_policy_engine.py
6. Integration test passes

---

## Handoff Checklist

- [ ] `core/engine.py` created with PolicyEngine class
- [ ] `core/policy_loader.py` created with PolicyLoader class
- [ ] `policies/financial_prudence.yaml` example created
- [ ] `core/__init__.py` updated with exports
- [ ] `tests/test_policy_engine.py` created with 8+ tests
- [ ] All verification commands pass
- [ ] Update `.tasks/handoff/current-session.md` with progress

---

## References

- Plan: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md` (Phase 2 section)
- Source: `validators/agent_validator.py:333-455` (rule evaluation logic)
- Source: `broker/utils/agent_config.py` (config loading pattern)
- Types: `governed_ai_sdk/v1_prototype/types.py` (PolicyRule, GovernanceTrace)
