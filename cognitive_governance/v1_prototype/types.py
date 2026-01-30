"""
GovernedAI SDK Type Definitions

Critical dataclasses for the SDK. These MUST be defined before any other
components can be implemented (Gap #1 Resolution from plan).

Reference: .tasks/SDK_Handover_Plan.md and plan file cozy-roaming-perlis.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from datetime import datetime


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
    BETWEEN = "between"  # Phase 3: range operator


class RuleLevel(str, Enum):
    """Rule severity levels."""
    ERROR = "ERROR"      # Blocks action
    WARNING = "WARNING"  # Logs but allows


class CounterFactualStrategy(Enum):
    """XAI explanation strategies for different rule types."""
    NUMERIC = "numeric_delta"          # Simple threshold diff
    CATEGORICAL = "categorical_flip"   # Suggest valid category
    COMPOSITE = "multi_objective"      # Relax easiest constraint first


class ParamType(str, Enum):
    """Parameter data types for rule evaluation and XAI."""
    NUMERIC = "numeric"        # Continuous values (savings, income)
    CATEGORICAL = "categorical"  # Unordered categories (status, type)
    ORDINAL = "ordinal"        # Ordered categories (education_level)
    TEMPORAL = "temporal"      # Time-based values
    BOOLEAN = "boolean"        # True/False flags


class Domain(str, Enum):
    """Supported research domains."""
    GENERIC = "generic"
    FLOOD = "flood"
    FINANCE = "finance"
    EDUCATION = "education"
    HEALTH = "health"
    ENVIRONMENTAL = "environmental"
    SOCIAL = "social"


@dataclass
class PolicyRule:
    """
    Generic rule definition supporting numeric, categorical, and composite operators.

    Examples:
        - Numeric: PolicyRule(id="min_savings", param="savings", operator=">=", value=500, ...)
        - Categorical: PolicyRule(id="valid_status", param="status", operator="in", value=["elevated", "insured"], ...)

    Domain Metadata (v2):
        - domain: Research domain this rule applies to
        - param_type: Data type for XAI calculations
        - severity_score: 0-1 criticality weight for prioritization
        - literature_ref: Academic citation for threshold justification
    """
    id: str
    param: str
    operator: str  # One of RuleOperator values
    value: Any
    message: str
    level: str = "ERROR"  # One of RuleLevel values
    xai_hint: Optional[str] = None  # Suggested counter-action (e.g., "recommend_grant")

    # NEW v2: Domain context
    domain: str = "generic"  # One of Domain values
    param_type: str = "numeric"  # One of ParamType values
    param_unit: Optional[str] = None  # "USD", "percentage", "meters"
    severity_score: float = 1.0  # 0-1: how critical is violation?

    # NEW v2: Research metadata for academic traceability
    literature_ref: Optional[str] = None  # Citation for threshold (e.g., "FEMA 2022")
    rationale: Optional[str] = None  # Why this rule exists

    def __post_init__(self):
        # Validate operator
        valid_ops = [op.value for op in RuleOperator]
        if self.operator not in valid_ops:
            raise ValueError(f"Invalid operator '{self.operator}'. Must be one of {valid_ops}")

        # Validate level
        valid_levels = [lvl.value for lvl in RuleLevel]
        if self.level not in valid_levels:
            raise ValueError(f"Invalid level '{self.level}'. Must be one of {valid_levels}")

        # Validate severity_score
        if not 0.0 <= self.severity_score <= 1.0:
            raise ValueError(f"severity_score must be 0-1, got {self.severity_score}")


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


# =============================================================================
# NEW v2: Universal Sensor Schema
# =============================================================================

@dataclass
class SensorConfig:
    """
    Domain-agnostic sensor configuration for extracting state variables.

    Defines how to extract, quantize, and document a variable from any environment.
    Enables consistent data collection across domains (flood, finance, education, etc.)

    Example (Flood):
        SensorConfig(
            domain="flood",
            variable_name="savings_ratio",
            sensor_name="SAVINGS",
            path="agent.finances.savings_to_income",
            data_type="numeric",
            quantization_type="threshold_bins",
            bins=[{"label": "LOW", "max": 0.3}, {"label": "HIGH", "max": 1.0}],
            bin_rationale="US CFPB emergency fund guidelines",
        )
    """
    domain: str  # Research domain (flood, finance, education, health)
    variable_name: str  # Variable identifier in state dict
    sensor_name: str  # Human-readable name (e.g., "SAVINGS", "FLOOD_RISK")
    path: str  # Dot-notation path to extract value (e.g., "agent.savings")
    data_type: str = "numeric"  # One of ParamType values

    # Units and scaling
    units: Optional[str] = None  # "USD", "%", "meters"
    scale_factor: float = 1.0  # Multiplier for normalization

    # Quantization (for symbolic representation)
    quantization_type: str = "threshold_bins"  # "threshold_bins", "percentile", "none"
    bins: Optional[List[Dict[str, Any]]] = None  # [{"label": "LOW", "max": 0.3}, ...]
    categories: Optional[List[str]] = None  # For categorical data

    # Documentation
    bin_rationale: Optional[str] = None  # Why these bin boundaries?
    literature_reference: Optional[str] = None  # Academic citation
    description: Optional[str] = None  # Human-readable description

    def quantize(self, value: Any) -> str:
        """
        Quantize a raw value into a symbolic label.

        Args:
            value: Raw numeric or categorical value

        Returns:
            Symbolic label (e.g., "LOW", "MEDIUM", "HIGH")
        """
        # Handle categorical validation first (before checking quantization_type)
        if self.data_type == "categorical" and self.categories:
            return value if value in self.categories else "UNKNOWN"

        if self.quantization_type == "none":
            return str(value)

        if self.bins and self.data_type in ("numeric", "ordinal"):
            scaled = float(value) * self.scale_factor
            for bin_def in self.bins:
                if scaled <= bin_def.get("max", float("inf")):
                    return bin_def["label"]
            return self.bins[-1]["label"] if self.bins else "UNKNOWN"

        return str(value)


# =============================================================================
# NEW v2: Research Trace for Academic Reproducibility
# =============================================================================

@dataclass
class ResearchTrace:
    """
    Extended trace for academic reproducibility.

    Captures all metadata needed to reproduce findings in a research paper,
    including treatment groups, effect sizes, and sensor configurations.

    Inherits core fields from GovernanceTrace pattern but adds research context.
    """
    # Core trace fields (from GovernanceTrace pattern)
    trace_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    valid: bool = True
    decision: str = "allow"  # "allow", "block", "warn"
    blocked_by: Optional[str] = None  # Rule ID that blocked

    # Action and state context
    action: Optional[Dict[str, Any]] = None
    state: Optional[Dict[str, Any]] = None

    # Research context
    domain: Optional[str] = None  # "flood", "finance", "education"
    research_phase: str = "main_study"  # "calibration", "pilot", "main_study", "validation"
    treatment_group: Optional[str] = None  # "control", "treatment_A", "treatment_B"

    # Statistical context
    effect_size: Optional[float] = None  # Cohen's d or similar
    confidence_interval: Optional[Tuple[float, float]] = None
    baseline_surprise: Optional[float] = None  # Information surprise metric

    # Counterfactual result (if computed)
    counterfactual: Optional["CounterFactualResult"] = None

    # Sensor documentation
    sensor_configs: Optional[Dict[str, Dict[str, Any]]] = None

    def to_research_dict(self) -> Dict[str, Any]:
        """
        Export as flat dictionary for statistical analysis (R, Python, Stata).

        Returns:
            Flat dictionary suitable for CSV/DataFrame conversion
        """
        result = {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "valid": self.valid,
            "decision": self.decision,
            "blocked_by": self.blocked_by,
            "domain": self.domain,
            "research_phase": self.research_phase,
            "treatment_group": self.treatment_group,
            "effect_size": self.effect_size,
            "baseline_surprise": self.baseline_surprise,
        }

        # Flatten confidence interval
        if self.confidence_interval:
            result["ci_lower"] = self.confidence_interval[0]
            result["ci_upper"] = self.confidence_interval[1]

        # Flatten counterfactual
        if self.counterfactual:
            result["cf_feasibility"] = self.counterfactual.feasibility_score
            result["cf_strategy"] = self.counterfactual.strategy_used.value

        return result


# =============================================================================
# NEW v2 Phase 3: Composite and Temporal Rules
# =============================================================================

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


# Type aliases for cleaner function signatures
State = Dict[str, Any]
Action = Dict[str, Any]
Policy = Dict[str, Any]


__all__ = [
    # Enums
    "RuleOperator",
    "RuleLevel",
    "CounterFactualStrategy",
    "ParamType",
    "Domain",
    # Dataclasses
    "PolicyRule",
    "GovernanceTrace",
    "CounterFactualResult",
    "EntropyFriction",
    "SensorConfig",
    "ResearchTrace",
    "CompositeRule",
    "TemporalRule",
    # Type aliases
    "State",
    "Action",
    "Policy",
]
