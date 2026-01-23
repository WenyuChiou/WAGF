"""
GovernedAI SDK Type Definitions

Critical dataclasses for the SDK. These MUST be defined before any other
components can be implemented (Gap #1 Resolution from plan).

Reference: .tasks/SDK_Handover_Plan.md and plan file cozy-roaming-perlis.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class RuleOperator(str, Enum):
    """Supported rule operators for policy evaluation."""
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="
    IN = "in"
    NOT_IN = "not_in"


class RuleLevel(str, Enum):
    """Rule severity levels."""
    ERROR = "ERROR"      # Blocks action
    WARNING = "WARNING"  # Logs but allows


class CounterFactualStrategy(Enum):
    """XAI explanation strategies for different rule types."""
    NUMERIC = "numeric_delta"          # Simple threshold diff
    CATEGORICAL = "categorical_flip"   # Suggest valid category
    COMPOSITE = "multi_objective"      # Relax easiest constraint first


@dataclass
class PolicyRule:
    """
    Generic rule definition supporting numeric, categorical, and composite operators.

    Examples:
        - Numeric: PolicyRule(id="min_savings", param="savings", operator=">=", value=500, ...)
        - Categorical: PolicyRule(id="valid_status", param="status", operator="in", value=["elevated", "insured"], ...)
    """
    id: str
    param: str
    operator: str  # One of RuleOperator values
    value: Any
    message: str
    level: str = "ERROR"  # One of RuleLevel values
    xai_hint: Optional[str] = None  # Suggested counter-action (e.g., "recommend_grant")

    def __post_init__(self):
        # Validate operator
        valid_ops = [op.value for op in RuleOperator]
        if self.operator not in valid_ops:
            raise ValueError(f"Invalid operator '{self.operator}'. Must be one of {valid_ops}")

        # Validate level
        valid_levels = [lvl.value for lvl in RuleLevel]
        if self.level not in valid_levels:
            raise ValueError(f"Invalid level '{self.level}'. Must be one of {valid_levels}")


@dataclass
class GovernanceTrace:
    """
    Result of policy verification.

    Captures whether an action passed/failed and provides XAI explanations
    for blocked actions.
    """
    valid: bool
    rule_id: str
    rule_message: str
    blocked_action: Optional[Dict[str, Any]] = None
    state_delta: Optional[Dict[str, float]] = None  # For XAI: what change would make it pass
    entropy_friction: Optional[float] = None  # Governance impact metric

    # Additional context for debugging
    evaluated_state: Optional[Dict[str, Any]] = None
    policy_id: Optional[str] = None

    def explain(self) -> str:
        """Generate human-readable explanation."""
        if self.valid:
            return f"✓ Action ALLOWED by rule '{self.rule_id}'"

        lines = [
            f"✗ Action BLOCKED by rule '{self.rule_id}'",
            f"  Reason: {self.rule_message}",
        ]

        if self.state_delta:
            changes = ", ".join(f"{k}: +{v}" for k, v in self.state_delta.items())
            lines.append(f"  To pass: {changes}")

        if self.entropy_friction is not None:
            lines.append(f"  Entropy friction: {self.entropy_friction:.2f}")

        return "\n".join(lines)


@dataclass
class CounterFactualResult:
    """
    XAI explanation output from counterfactual analysis.

    Answers: "What minimal change to state would make the action pass?"
    """
    passed: bool
    delta_state: Dict[str, Any]  # Minimal change to pass (e.g., {"savings": 200})
    explanation: str  # Human-readable (e.g., "If savings were +$200, action would pass")
    feasibility_score: float  # 0-1: how achievable is the change?
    strategy_used: CounterFactualStrategy = CounterFactualStrategy.NUMERIC

    # Additional metadata
    original_state: Optional[Dict[str, Any]] = None
    failed_rule: Optional[PolicyRule] = None

    def __post_init__(self):
        # Validate feasibility score
        if not 0.0 <= self.feasibility_score <= 1.0:
            raise ValueError(f"feasibility_score must be 0-1, got {self.feasibility_score}")


@dataclass
class EntropyFriction:
    """
    Entropy measurement output for governance calibration.

    Measures whether governance is over-restricting or under-restricting
    agent action diversity using Shannon entropy.

    Formulas:
        - Shannon Entropy: H = -Σ p(x) * log2(p(x))
        - Friction Ratio: S_raw / max(S_governed, 1e-6)

    Interpretation:
        - friction_ratio ≈ 1.0: Governance has minimal impact (balanced)
        - friction_ratio > 2.0: OVER-GOVERNED (excessive restriction)
        - friction_ratio < 0.8: UNDER-GOVERNED (rules too permissive)
    """
    S_raw: float            # Shannon entropy of raw (intended) actions
    S_governed: float       # Shannon entropy of allowed actions
    friction_ratio: float   # S_raw / max(S_governed, 1e-6)
    kl_divergence: float = 0.0  # KL(raw || governed) for distribution comparison
    is_over_governed: bool = False  # friction_ratio > 2.0
    interpretation: str = "Balanced"  # "Balanced" | "Over-Governed" | "Under-Governed"

    # Batch statistics
    raw_action_count: int = 0
    governed_action_count: int = 0
    blocked_action_count: int = 0

    def __post_init__(self):
        # Auto-compute interpretation if not set
        if self.friction_ratio > 2.0:
            self.is_over_governed = True
            self.interpretation = "Over-Governed"
        elif self.friction_ratio < 0.8:
            self.interpretation = "Under-Governed"
        else:
            self.interpretation = "Balanced"

    def explain(self) -> str:
        """Generate human-readable entropy report."""
        lines = [
            "=== Entropy Friction Report ===",
            f"Raw Actions Entropy (S_raw):      {self.S_raw:.3f}",
            f"Governed Actions Entropy (S_gov): {self.S_governed:.3f}",
            f"Friction Ratio:                   {self.friction_ratio:.2f}",
            f"KL Divergence:                    {self.kl_divergence:.3f}",
            f"",
            f"Interpretation: {self.interpretation}",
        ]

        if self.is_over_governed:
            lines.append("⚠️  WARNING: Governance may be too restrictive!")

        if self.blocked_action_count > 0:
            block_rate = self.blocked_action_count / max(self.raw_action_count, 1)
            lines.append(f"Block Rate: {block_rate:.1%} ({self.blocked_action_count}/{self.raw_action_count})")

        return "\n".join(lines)


# Type aliases for cleaner function signatures
State = Dict[str, Any]
Action = Dict[str, Any]
Policy = Dict[str, Any]


__all__ = [
    # Enums
    "RuleOperator",
    "RuleLevel",
    "CounterFactualStrategy",
    # Dataclasses
    "PolicyRule",
    "GovernanceTrace",
    "CounterFactualResult",
    "EntropyFriction",
    # Type aliases
    "State",
    "Action",
    "Policy",
]
