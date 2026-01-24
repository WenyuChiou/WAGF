# Task-033 Phase 3: Extensibility - Operator Registry

**Assignee**: Gemini CLI
**Branch**: `task-033-phase3-extensibility` (create from `task-033-phase1-types` after Phase 1 merges)
**Dependencies**: Phase 1 must be complete first

---

## Objective

Create an extensible operator registry pattern so users can register custom rule operators without modifying core engine code.

---

## Deliverables

### 3.1 Operator Protocol and Registry

**File**: `governed_ai_sdk/v1_prototype/core/operators.py`

```python
"""Extensible operator registry for rule evaluation."""
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class RuleEvaluator(Protocol):
    """Protocol for custom rule evaluators."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Evaluate if value satisfies the condition against target.

        Args:
            value: Current value from state
            target: Target value from rule
            context: Optional additional context (full state, etc.)

        Returns:
            True if condition is satisfied
        """
        ...

    def explain(self, value: Any, target: Any) -> str:
        """
        Generate human-readable explanation of the comparison.

        Args:
            value: Current value
            target: Target value

        Returns:
            Explanation string like "500 >= 300"
        """
        ...


class OperatorRegistry:
    """Global registry for rule operators."""

    _operators: Dict[str, RuleEvaluator] = {}

    @classmethod
    def register(cls, name: str, evaluator: RuleEvaluator) -> None:
        """Register an operator evaluator."""
        cls._operators[name] = evaluator

    @classmethod
    def get(cls, name: str) -> Optional[RuleEvaluator]:
        """Get operator by name."""
        return cls._operators.get(name)

    @classmethod
    def has(cls, name: str) -> bool:
        """Check if operator exists."""
        return name in cls._operators

    @classmethod
    def list_operators(cls) -> list[str]:
        """List all registered operator names."""
        return list(cls._operators.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all operators (useful for testing)."""
        cls._operators.clear()


# ============================================================
# Built-in Operators
# ============================================================

class GreaterThanEvaluator:
    """Greater than operator (>)."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        return value > target

    def explain(self, value: Any, target: Any) -> str:
        return f"{value} > {target}"


class GreaterThanOrEqualEvaluator:
    """Greater than or equal operator (>=)."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        return value >= target

    def explain(self, value: Any, target: Any) -> str:
        return f"{value} >= {target}"


class LessThanEvaluator:
    """Less than operator (<)."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        return value < target

    def explain(self, value: Any, target: Any) -> str:
        return f"{value} < {target}"


class LessThanOrEqualEvaluator:
    """Less than or equal operator (<=)."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        return value <= target

    def explain(self, value: Any, target: Any) -> str:
        return f"{value} <= {target}"


class EqualEvaluator:
    """Equality operator (==)."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        return value == target

    def explain(self, value: Any, target: Any) -> str:
        return f"{value} == {target}"


class NotEqualEvaluator:
    """Inequality operator (!=)."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        return value != target

    def explain(self, value: Any, target: Any) -> str:
        return f"{value} != {target}"


class InSetEvaluator:
    """Membership operator (in)."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        if isinstance(target, (list, tuple, set)):
            return value in target
        return value == target

    def explain(self, value: Any, target: Any) -> str:
        return f"{value} in {target}"


class NotInSetEvaluator:
    """Non-membership operator (not_in)."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        if isinstance(target, (list, tuple, set)):
            return value not in target
        return value != target

    def explain(self, value: Any, target: Any) -> str:
        return f"{value} not in {target}"


class BetweenEvaluator:
    """Range operator (between). Target should be [min, max]."""

    def evaluate(self, value: Any, target: Any, context: Optional[Dict] = None) -> bool:
        if isinstance(target, (list, tuple)) and len(target) == 2:
            return target[0] <= value <= target[1]
        return False

    def explain(self, value: Any, target: Any) -> str:
        if isinstance(target, (list, tuple)) and len(target) == 2:
            return f"{target[0]} <= {value} <= {target[1]}"
        return f"{value} between {target}"


# ============================================================
# Register Default Operators
# ============================================================

def _register_defaults():
    """Register all built-in operators."""
    OperatorRegistry.register(">", GreaterThanEvaluator())
    OperatorRegistry.register(">=", GreaterThanOrEqualEvaluator())
    OperatorRegistry.register("<", LessThanEvaluator())
    OperatorRegistry.register("<=", LessThanOrEqualEvaluator())
    OperatorRegistry.register("==", EqualEvaluator())
    OperatorRegistry.register("!=", NotEqualEvaluator())
    OperatorRegistry.register("in", InSetEvaluator())
    OperatorRegistry.register("not_in", NotInSetEvaluator())
    OperatorRegistry.register("between", BetweenEvaluator())

    # Aliases
    OperatorRegistry.register("gt", GreaterThanEvaluator())
    OperatorRegistry.register("gte", GreaterThanOrEqualEvaluator())
    OperatorRegistry.register("lt", LessThanEvaluator())
    OperatorRegistry.register("lte", LessThanOrEqualEvaluator())
    OperatorRegistry.register("eq", EqualEvaluator())
    OperatorRegistry.register("ne", NotEqualEvaluator())


# Auto-register on import
_register_defaults()
```

### 3.2 Composite Rule Support

**File**: `governed_ai_sdk/v1_prototype/types.py` (add to existing)

```python
from typing import List, Optional


@dataclass
class CompositeRule:
    """
    Multi-constraint rule supporting AND/OR/IF-THEN logic.

    Examples:
        - AND: All sub-rules must pass
        - OR: At least one sub-rule must pass
        - AT_LEAST_N: At least N sub-rules must pass
        - IF_THEN: If condition rule passes, then consequent must pass
    """
    id: str
    logic: str  # "AND", "OR", "AT_LEAST_N", "IF_THEN"
    rules: List["PolicyRule"]
    threshold: Optional[int] = None  # For "AT_LEAST_N"
    condition_rule: Optional["PolicyRule"] = None  # For "IF_THEN"
    message: str = ""
    level: str = "ERROR"

    def __post_init__(self):
        if self.logic == "AT_LEAST_N" and self.threshold is None:
            raise ValueError("AT_LEAST_N logic requires threshold")
        if self.logic == "IF_THEN" and self.condition_rule is None:
            raise ValueError("IF_THEN logic requires condition_rule")


@dataclass
class TemporalRule:
    """
    Time-series rule for rate of change, rolling averages, trends.

    Aggregations:
        - mean: Rolling mean over window
        - max: Maximum value in window
        - min: Minimum value in window
        - delta: Change from start to end of window
        - trend: Linear trend coefficient
    """
    id: str
    param: str
    operator: str
    aggregation: str  # "mean", "max", "min", "delta", "trend"
    window: int  # Number of time steps
    value: float
    message: str
    level: str = "ERROR"
```

### 3.3 Update Engine to Use Registry

**File**: `governed_ai_sdk/v1_prototype/core/engine.py` (modify)

Update the `_check_rule` method to use the operator registry:

```python
from .operators import OperatorRegistry

def _check_rule(self, rule: PolicyRule, state: Dict[str, Any]) -> bool:
    """Check if a rule passes using the operator registry."""
    value = state.get(rule.param)
    if value is None:
        return True  # Missing params pass by default

    evaluator = OperatorRegistry.get(rule.operator)
    if evaluator is None:
        # Fallback to legacy behavior for backwards compatibility
        return self._legacy_check(rule.operator, value, rule.value)

    return evaluator.evaluate(value, rule.value, context=state)

def _legacy_check(self, operator: str, value: Any, target: Any) -> bool:
    """Legacy operator checking (backwards compatibility)."""
    ops = {
        ">": lambda v, t: v > t,
        ">=": lambda v, t: v >= t,
        "<": lambda v, t: v < t,
        "<=": lambda v, t: v <= t,
        "==": lambda v, t: v == t,
        "!=": lambda v, t: v != t,
    }
    return ops.get(operator, lambda v, t: True)(value, target)
```

---

## Tests

**File**: `governed_ai_sdk/tests/test_operators.py`

```python
"""Tests for operator registry and custom operators."""
import pytest
from governed_ai_sdk.v1_prototype.core.operators import (
    OperatorRegistry,
    RuleEvaluator,
    GreaterThanEvaluator,
    BetweenEvaluator,
)
from governed_ai_sdk.v1_prototype.types import CompositeRule, PolicyRule, TemporalRule


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
        assert OperatorRegistry.has("between")

    def test_get_operator(self):
        """Can retrieve and use operators."""
        gt = OperatorRegistry.get(">")
        assert gt.evaluate(10, 5) is True
        assert gt.evaluate(5, 10) is False

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

    def test_between_operator(self):
        """Between operator works with ranges."""
        between = OperatorRegistry.get("between")
        assert between.evaluate(5, [1, 10]) is True
        assert between.evaluate(15, [1, 10]) is False

    def test_in_operator(self):
        """In operator works with collections."""
        in_op = OperatorRegistry.get("in")
        assert in_op.evaluate("A", ["A", "B", "C"]) is True
        assert in_op.evaluate("D", ["A", "B", "C"]) is False


class TestCompositeRule:
    """Tests for CompositeRule."""

    def test_composite_and(self):
        """AND composite requires all rules."""
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

    def test_at_least_n_requires_threshold(self):
        """AT_LEAST_N requires threshold."""
        with pytest.raises(ValueError, match="requires threshold"):
            CompositeRule(
                id="test",
                logic="AT_LEAST_N",
                rules=[],
                message="test"
            )

    def test_if_then_requires_condition(self):
        """IF_THEN requires condition_rule."""
        with pytest.raises(ValueError, match="requires condition_rule"):
            CompositeRule(
                id="test",
                logic="IF_THEN",
                rules=[],
                message="test"
            )


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
```

---

## Verification

```bash
# Create branch
git checkout task-033-phase1-types
git pull
git checkout -b task-033-phase3-extensibility

# Run tests
python -m pytest governed_ai_sdk/tests/test_operators.py -v

# Verify custom operator registration
python -c "
from governed_ai_sdk.v1_prototype.core.operators import OperatorRegistry

class PercentageChangeEvaluator:
    def evaluate(self, value, target, context=None):
        if context and 'previous' in context:
            change = (value - context['previous']) / context['previous']
            return change >= target
        return False
    def explain(self, value, target):
        return f'percentage change >= {target}'

OperatorRegistry.register('pct_change', PercentageChangeEvaluator())
print('Custom operator registered:', OperatorRegistry.list_operators())
"
```

---

## Report Format

After completion, add to `.tasks/handoff/current-session.md`:

```
---
REPORT
agent: Gemini CLI
task_id: task-033-phase3
scope: governed_ai_sdk/v1_prototype/core
status: done
changes:
- governed_ai_sdk/v1_prototype/core/operators.py (created)
- governed_ai_sdk/v1_prototype/types.py (added CompositeRule, TemporalRule)
- governed_ai_sdk/v1_prototype/core/engine.py (updated to use registry)
tests: pytest governed_ai_sdk/tests/test_operators.py -v (X passed)
artifacts: none
issues: <any issues encountered>
next: merge into task-033-phase1-types
---
```
