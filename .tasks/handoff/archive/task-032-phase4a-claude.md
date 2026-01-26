# Task-032 Phase 4A: XAI Counterfactual Engine (Claude Code)

**Status**: 🔲 Blocked on Phase 2
**Assignee**: Claude Code
**Effort**: 5-6 hours
**Priority**: MEDIUM
**Prerequisite**: Phase 2 (Gemini CLI PolicyEngine) complete

---

## Git Branch

```bash
# After Phase 2 completes:
git checkout task-032-phase2
git checkout -b task-032-phase4a
```

**Stacked PR Structure**:
```
main
 └── task-032-sdk-base (Phase 0)
      └── task-032-phase1 (Codex)
           └── task-032-phase2 (Gemini)
                └── task-032-phase4a (this branch) ← YOUR WORK HERE
```

---

## Objective

Implement the CounterfactualEngine that generates XAI explanations for blocked actions. Must support THREE strategies for different rule types.

---

## Gap Analysis (Why This Is Needed)

Original SDK plan only had numeric example (`savings > 500`). Missing:
- Categorical constraints (`status in ["elevated", "insured"]`)
- Composite rules (`savings > 500 AND debt < income`)

---

## Deliverables

### 1. `xai/counterfactual.py`

```python
"""
Counterfactual Explanation Engine for XAI.

Generates explanations for blocked actions by computing the minimal
state change required to pass the rule.

Three Strategies:
1. NUMERIC: Threshold delta calculation
2. CATEGORICAL: Suggest valid category
3. COMPOSITE: Multi-objective relaxation
"""

from typing import Any, Dict, Optional
from governed_ai_sdk.v1_prototype.types import (
    PolicyRule,
    CounterFactualResult,
    CounterFactualStrategy,
)


class CounterfactualEngine:
    """
    Generate explanations for ALL rule types.

    Example:
        >>> engine = CounterfactualEngine()
        >>> result = engine.explain(
        ...     PolicyRule(id="r1", param="savings", operator=">=", value=500, ...),
        ...     state={"savings": 300}
        ... )
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
            failed_rule: The rule that blocked the action
            state: Current state when rule failed

        Returns:
            CounterFactualResult with delta_state and explanation
        """
        op = failed_rule.operator

        # Route to appropriate strategy
        if op in (">", "<", ">=", "<="):
            return self._explain_numeric(failed_rule, state)
        elif op in ("in", "not_in"):
            return self._explain_categorical(failed_rule, state)
        elif op in ("==", "!="):
            return self._explain_equality(failed_rule, state)
        else:
            return self._explain_composite(failed_rule, state)

    def _explain_numeric(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Strategy 1: Numeric delta calculation.

        Computes exact delta needed to pass threshold.
        """
        current = state.get(rule.param, 0)
        target = rule.value

        if rule.operator in (">", ">="):
            delta = target - current
            if rule.operator == ">":
                delta += 0.01  # Strictly greater

            if delta <= 0:
                # Already passes (shouldn't happen for failed rule)
                return CounterFactualResult(
                    passed=True,
                    delta_state={},
                    explanation="Rule already satisfied",
                    feasibility_score=1.0,
                    strategy_used=CounterFactualStrategy.NUMERIC,
                    original_state=state,
                    failed_rule=rule,
                )

            explanation = f"If {rule.param} were +{delta:.2f} ({rule.operator}{target}), action would pass."
            feasibility = self._compute_feasibility(delta, current)

        elif rule.operator in ("<", "<="):
            delta = current - target
            if rule.operator == "<":
                delta += 0.01

            if delta <= 0:
                return CounterFactualResult(
                    passed=True,
                    delta_state={},
                    explanation="Rule already satisfied",
                    feasibility_score=1.0,
                    strategy_used=CounterFactualStrategy.NUMERIC,
                )

            explanation = f"If {rule.param} were -{delta:.2f} ({rule.operator}{target}), action would pass."
            feasibility = self._compute_feasibility(delta, current)
            delta = -delta  # Negative change needed

        return CounterFactualResult(
            passed=False,
            delta_state={rule.param: delta},
            explanation=explanation,
            feasibility_score=feasibility,
            strategy_used=CounterFactualStrategy.NUMERIC,
            original_state=state,
            failed_rule=rule,
        )

    def _explain_categorical(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Strategy 2: Categorical constraint suggestion.

        Suggests the first valid option from allowed values.
        """
        current = state.get(rule.param)
        valid_options = rule.value  # e.g., ["elevated", "insured"]

        if rule.operator == "in":
            # Need to be IN the list
            suggested = valid_options[0] if valid_options else None
            explanation = f"Change {rule.param} from '{current}' to one of {valid_options}"
        else:  # not_in
            # Need to NOT be in the list - suggest anything else
            suggested = f"not_{current}"
            explanation = f"Change {rule.param} from '{current}' to any value not in {valid_options}"

        return CounterFactualResult(
            passed=False,
            delta_state={rule.param: suggested},
            explanation=explanation,
            feasibility_score=0.5,  # Binary: can or can't change category
            strategy_used=CounterFactualStrategy.CATEGORICAL,
            original_state=state,
            failed_rule=rule,
        )

    def _explain_equality(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Handle == and != operators.
        """
        current = state.get(rule.param)
        target = rule.value

        if rule.operator == "==":
            explanation = f"Change {rule.param} from '{current}' to '{target}'"
            suggested = target
        else:  # !=
            explanation = f"Change {rule.param} from '{current}' to anything except '{target}'"
            suggested = f"not_{target}"

        return CounterFactualResult(
            passed=False,
            delta_state={rule.param: suggested},
            explanation=explanation,
            feasibility_score=0.5,
            strategy_used=CounterFactualStrategy.CATEGORICAL,
            original_state=state,
            failed_rule=rule,
        )

    def _explain_composite(
        self,
        rule: PolicyRule,
        state: Dict[str, Any]
    ) -> CounterFactualResult:
        """
        Strategy 3: Multi-constraint relaxation.

        For complex rules, provides general guidance.
        TODO: Implement multi-objective optimization
        """
        return CounterFactualResult(
            passed=False,
            delta_state={},
            explanation=f"Composite rule '{rule.id}': multiple changes may be needed. Check: {rule.message}",
            feasibility_score=0.3,
            strategy_used=CounterFactualStrategy.COMPOSITE,
            original_state=state,
            failed_rule=rule,
        )

    def _compute_feasibility(self, delta: float, current: float) -> float:
        """
        Compute feasibility score based on relative change needed.

        Larger relative changes = lower feasibility.
        """
        if current == 0:
            return 0.5  # Can't compute relative change

        relative_change = abs(delta) / abs(current)

        # Feasibility decreases with larger changes
        # 10% change = 0.9 feasibility
        # 100% change = 0.5 feasibility
        # 500% change = 0.1 feasibility
        feasibility = 1.0 / (1.0 + relative_change)
        return max(0.1, min(1.0, feasibility))


def create_counterfactual_engine() -> CounterfactualEngine:
    """Factory function."""
    return CounterfactualEngine()
```

### 2. Update `xai/__init__.py`

```python
"""
Explainable AI (XAI) components.
"""

from .counterfactual import CounterfactualEngine, create_counterfactual_engine

__all__ = [
    "CounterfactualEngine",
    "create_counterfactual_engine",
]
```

---

## Test Cases (Create `tests/test_counterfactual.py`)

```python
"""
Test suite for CounterfactualEngine.

Run: pytest governed_ai_sdk/tests/test_counterfactual.py -v
"""

import pytest
from governed_ai_sdk.v1_prototype.types import PolicyRule, CounterFactualStrategy
from governed_ai_sdk.v1_prototype.xai.counterfactual import CounterfactualEngine


class TestNumericStrategy:
    """Tests for numeric counterfactual strategy."""

    def test_greater_than_equal(self):
        """Test >= rule counterfactual."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="min_savings", param="savings", operator=">=",
            value=500, message="Need $500", level="ERROR"
        )

        result = engine.explain(rule, {"savings": 300})

        assert result.passed is False
        assert result.delta_state["savings"] == 200
        assert result.strategy_used == CounterFactualStrategy.NUMERIC
        assert "200" in result.explanation

    def test_less_than(self):
        """Test < rule counterfactual."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="max_debt", param="debt", operator="<",
            value=1000, message="Debt too high", level="ERROR"
        )

        result = engine.explain(rule, {"debt": 1500})

        assert result.passed is False
        assert result.delta_state["debt"] < 0  # Need to decrease
        assert result.strategy_used == CounterFactualStrategy.NUMERIC

    def test_feasibility_small_change(self):
        """Test feasibility is high for small changes."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="r1", param="x", operator=">=",
            value=110, message="", level="ERROR"
        )

        result = engine.explain(rule, {"x": 100})  # 10% change needed

        assert result.feasibility_score > 0.8


class TestCategoricalStrategy:
    """Tests for categorical counterfactual strategy."""

    def test_in_operator(self):
        """Test IN rule suggests valid option."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="valid_status", param="status", operator="in",
            value=["elevated", "insured"], message="Invalid", level="ERROR"
        )

        result = engine.explain(rule, {"status": "normal"})

        assert result.passed is False
        assert result.delta_state["status"] in ["elevated", "insured"]
        assert result.strategy_used == CounterFactualStrategy.CATEGORICAL

    def test_not_in_operator(self):
        """Test NOT_IN rule."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="no_banned", param="type", operator="not_in",
            value=["banned", "blocked"], message="Banned type", level="ERROR"
        )

        result = engine.explain(rule, {"type": "banned"})

        assert result.passed is False
        assert result.strategy_used == CounterFactualStrategy.CATEGORICAL


class TestEqualityStrategy:
    """Tests for equality operators."""

    def test_equal_operator(self):
        """Test == rule."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="exact_match", param="code", operator="==",
            value="ABC", message="Must be ABC", level="ERROR"
        )

        result = engine.explain(rule, {"code": "XYZ"})

        assert result.delta_state["code"] == "ABC"

    def test_not_equal_operator(self):
        """Test != rule."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="not_default", param="mode", operator="!=",
            value="default", message="Can't be default", level="ERROR"
        )

        result = engine.explain(rule, {"mode": "default"})

        assert "default" not in str(result.delta_state["mode"]) or "not_" in str(result.delta_state["mode"])


class TestCompositeStrategy:
    """Tests for composite/unknown operators."""

    def test_unknown_operator(self):
        """Test unknown operator falls back to composite."""
        engine = CounterfactualEngine()
        rule = PolicyRule(
            id="complex", param="x", operator=">=",  # Will be modified
            value=100, message="Complex rule", level="ERROR"
        )
        rule.operator = "UNKNOWN"  # Force unknown

        result = engine.explain(rule, {"x": 50})

        assert result.strategy_used == CounterFactualStrategy.COMPOSITE
        assert result.feasibility_score == 0.3
```

---

## Verification Commands

```bash
# 1. Verify imports
python -c "from governed_ai_sdk.v1_prototype.xai.counterfactual import CounterfactualEngine; print('OK')"

# 2. Run XAI tests
pytest governed_ai_sdk/tests/test_counterfactual.py -v

# 3. Integration test
python -c "
from governed_ai_sdk.v1_prototype.types import PolicyRule
from governed_ai_sdk.v1_prototype.xai.counterfactual import CounterfactualEngine

engine = CounterfactualEngine()

# Numeric test
rule = PolicyRule(id='r1', param='savings', operator='>=', value=500, message='Need 500', level='ERROR')
result = engine.explain(rule, {'savings': 300})
print(f'Numeric: {result.explanation}')
print(f'Delta: {result.delta_state}')

# Categorical test
rule2 = PolicyRule(id='r2', param='status', operator='in', value=['active', 'elevated'], message='Bad status', level='ERROR')
result2 = engine.explain(rule2, {'status': 'inactive'})
print(f'Categorical: {result2.explanation}')
"
```

---

## Success Criteria

1. All 3 strategies (NUMERIC, CATEGORICAL, COMPOSITE) work
2. Numeric delta calculations are accurate
3. Categorical suggestions are from valid options
4. Feasibility scores are reasonable (0-1)
5. At least 10 tests pass

---

## Handoff Checklist

- [ ] `xai/counterfactual.py` created with CounterfactualEngine
- [ ] `xai/__init__.py` updated
- [ ] `tests/test_counterfactual.py` created
- [ ] All 3 strategies verified
- [ ] All verification commands pass
