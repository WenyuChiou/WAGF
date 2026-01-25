"""
Extensible operator registry for rule evaluation.

Provides a registry pattern for custom rule operators, allowing users
to extend the SDK without modifying core engine code.

Example:
    >>> from governed_ai_sdk.v1_prototype.core.operators import OperatorRegistry
    >>>
    >>> class FuzzyEqualEvaluator:
    ...     def evaluate(self, value, target, context=None):
    ...         return abs(value - target) < 0.1
    ...     def explain(self, value, target):
    ...         return f"{value} ~= {target}"
    >>>
    >>> OperatorRegistry.register("fuzzy_eq", FuzzyEqualEvaluator())
"""
from typing import Any, Dict, Optional, Protocol, runtime_checkable, List


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
    def list_operators(cls) -> List[str]:
        """List all registered operator names."""
        return list(cls._operators.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all operators (useful for testing)."""
        cls._operators.clear()


# =============================================================================
# Built-in Operators
# =============================================================================

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


# =============================================================================
# Register Default Operators
# =============================================================================

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

    # Aliases for compatibility
    OperatorRegistry.register("gt", GreaterThanEvaluator())
    OperatorRegistry.register("gte", GreaterThanOrEqualEvaluator())
    OperatorRegistry.register("lt", LessThanEvaluator())
    OperatorRegistry.register("lte", LessThanOrEqualEvaluator())
    OperatorRegistry.register("eq", EqualEvaluator())
    OperatorRegistry.register("ne", NotEqualEvaluator())


# Auto-register on import
_register_defaults()


__all__ = [
    "RuleEvaluator",
    "OperatorRegistry",
    "GreaterThanEvaluator",
    "GreaterThanOrEqualEvaluator",
    "LessThanEvaluator",
    "LessThanOrEqualEvaluator",
    "EqualEvaluator",
    "NotEqualEvaluator",
    "InSetEvaluator",
    "NotInSetEvaluator",
    "BetweenEvaluator",
]
