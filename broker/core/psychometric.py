"""
Psychometric Framework - Psychological assessment frameworks for agent validation.

This module provides psychological framework implementations for different agent types:
- PMTFramework: Protection Motivation Theory for household agents
- UtilityFramework: Utility Theory for government agents
- FinancialFramework: Financial Risk Theory for insurance agents

Each framework defines:
- Constructs: The measurable dimensions (e.g., TP_LABEL, CP_LABEL for PMT)
- Coherence validation: Checking if appraisals are internally consistent
- Expected behavior mapping: What actions are expected given appraisals

Part of Task-040: SA/MA Unified Architecture (Part 14.5)
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ConstructDef:
    """
    Definition of a psychological construct.

    Constructs are the measurable dimensions used in psychological frameworks.
    For example, in PMT: Threat Perception (TP), Coping Perception (CP).

    Attributes:
        name: Human-readable name of the construct
        values: List of valid values for this construct
        required: Whether this construct must be present in appraisals
        description: Optional description of the construct
    """
    name: str
    values: List[str] = field(default_factory=list)
    required: bool = True
    description: str = ""

    def validate_value(self, value: Any) -> bool:
        """
        Check if a value is valid for this construct.

        Args:
            value: The value to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.values:
            return True  # No constraint
        return str(value).upper() in [v.upper() for v in self.values]


@dataclass
class ValidationResult:
    """
    Result from a coherence validation check.

    Attributes:
        valid: Whether the appraisals are coherent
        errors: List of error messages for coherence violations
        warnings: List of warning messages
        rule_violations: List of rule IDs that were violated
        metadata: Additional context about the validation
    """
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rule_violations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "rule_violations": self.rule_violations,
            "metadata": self.metadata,
        }


class PsychologicalFramework(ABC):
    """
    Base class for psychological assessment frameworks.

    This abstract class defines the interface for psychological frameworks
    that can be used to validate agent behavior and reasoning.

    Subclasses must implement:
    - get_constructs(): Return the constructs for this framework
    - validate_coherence(): Check if appraisals are internally coherent
    - get_expected_behavior(): Return expected skills given appraisals
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this framework."""
        ...

    @abstractmethod
    def get_constructs(self) -> Dict[str, ConstructDef]:
        """
        Return construct definitions for this framework.

        Returns:
            Dictionary mapping construct keys to ConstructDef objects
        """
        ...

    @abstractmethod
    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        """
        Validate that appraisals are internally coherent.

        This checks for logical consistency in the agent's appraisals.
        For example, in PMT: High threat + High coping should lead to action.

        Args:
            appraisals: Dictionary of construct values (e.g., {"TP_LABEL": "H", "CP_LABEL": "H"})

        Returns:
            ValidationResult with coherence check results
        """
        ...

    @abstractmethod
    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        """
        Return expected skills given these appraisals.

        Based on the psychological framework, determines what behaviors
        would be expected given the current appraisals.

        Args:
            appraisals: Dictionary of construct values

        Returns:
            List of skill names that would be expected
        """
        ...

    def validate_required_constructs(self, appraisals: Dict[str, str]) -> ValidationResult:
        """
        Validate that all required constructs are present.

        Args:
            appraisals: Dictionary of construct values

        Returns:
            ValidationResult indicating if required constructs are present
        """
        constructs = self.get_constructs()
        missing = []

        for key, construct in constructs.items():
            if construct.required and key not in appraisals:
                missing.append(key)

        if missing:
            return ValidationResult(
                valid=False,
                errors=[f"Missing required constructs: {', '.join(missing)}"],
                metadata={"missing_constructs": missing}
            )

        return ValidationResult(valid=True)

    def validate_construct_values(self, appraisals: Dict[str, str]) -> ValidationResult:
        """
        Validate that construct values are within allowed ranges.

        Args:
            appraisals: Dictionary of construct values

        Returns:
            ValidationResult indicating if values are valid
        """
        constructs = self.get_constructs()
        invalid = []

        for key, value in appraisals.items():
            if key in constructs:
                if not constructs[key].validate_value(value):
                    invalid.append(f"{key}={value} (allowed: {constructs[key].values})")

        if invalid:
            return ValidationResult(
                valid=False,
                errors=[f"Invalid construct values: {'; '.join(invalid)}"],
                metadata={"invalid_values": invalid}
            )

        return ValidationResult(valid=True)

    def get_construct_keys(self) -> List[str]:
        """Return list of construct keys for this framework."""
        return list(self.get_constructs().keys())

    def get_required_construct_keys(self) -> List[str]:
        """Return list of required construct keys."""
        return [k for k, v in self.get_constructs().items() if v.required]


# PMT Label ordering for comparison
PMT_LABEL_ORDER = {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4}


class PMTFramework(PsychologicalFramework):
    """
    Protection Motivation Theory framework for household agents.

    PMT models protective behavior through two cognitive processes:
    - Threat Appraisal (TP): Perceived severity and vulnerability
    - Coping Appraisal (CP): Self-efficacy and response efficacy

    Key coherence rules:
    - High TP + High CP should not result in do_nothing
    - Low TP should not justify extreme actions
    - VH TP requires protective action

    Optional constructs:
    - Stakeholder Perception (SP): Trust in external actors

    Domain-specific skill names (extreme_actions, complex_actions,
    expected_skill_map) are configurable via constructor. Defaults
    are flood-domain for backward compatibility.
    """

    def __init__(
        self,
        extreme_actions: Optional[set] = None,
        complex_actions: Optional[set] = None,
    ):
        self._extreme_actions = extreme_actions or {
            "relocate", "elevate_house", "buyout_program"
        }
        self._complex_actions = complex_actions or {
            "elevate_house", "relocate", "buyout_program"
        }

    @property
    def name(self) -> str:
        return "Protection Motivation Theory (PMT)"

    def get_constructs(self) -> Dict[str, ConstructDef]:
        """Return PMT constructs: TP, CP, and optional SP."""
        return {
            "TP_LABEL": ConstructDef(
                name="Threat Perception",
                values=["VL", "L", "M", "H", "VH"],
                required=True,
                description="Perceived severity and vulnerability to threat"
            ),
            "CP_LABEL": ConstructDef(
                name="Coping Perception",
                values=["VL", "L", "M", "H", "VH"],
                required=True,
                description="Perceived ability to cope with threat"
            ),
            "SP_LABEL": ConstructDef(
                name="Stakeholder Perception",
                values=["VL", "L", "M", "H", "VH"],
                required=False,
                description="Perceived support from stakeholders (government, insurance)"
            ),
        }

    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        """
        Validate PMT coherence rules.

        Rules:
        1. High TP + High CP should not do_nothing
        2. VH TP requires action
        3. Low TP should not justify extreme measures

        Args:
            appraisals: Dictionary with TP_LABEL, CP_LABEL, and optional SP_LABEL

        Returns:
            ValidationResult with any coherence violations
        """
        errors = []
        warnings = []
        violations = []

        tp = self._normalize_label(appraisals.get("TP_LABEL", "M"))
        cp = self._normalize_label(appraisals.get("CP_LABEL", "M"))

        # First, check required constructs
        required_check = self.validate_required_constructs(appraisals)
        if not required_check.valid:
            return required_check

        # Check construct values
        value_check = self.validate_construct_values(appraisals)
        if not value_check.valid:
            return value_check

        # PMT-specific coherence rules are about action consistency,
        # not appraisal consistency. The coherence check itself is valid
        # as long as values are in range.

        # However, we can flag combinations that typically require action
        if tp in ("H", "VH") and cp in ("H", "VH"):
            warnings.append("High threat + high coping typically leads to protective action")

        if tp == "VH":
            warnings.append("Very high threat typically requires protective action")

        return ValidationResult(
            valid=True,  # Appraisals themselves are coherent
            errors=errors,
            warnings=warnings,
            rule_violations=violations,
            metadata={
                "tp_label": tp,
                "cp_label": cp,
                "sp_label": appraisals.get("SP_LABEL", ""),
            }
        )

    def validate_action_coherence(
        self,
        appraisals: Dict[str, str],
        proposed_skill: str
    ) -> ValidationResult:
        """
        Validate that a proposed action is coherent with PMT appraisals.

        This is the main PMT validation used in governance rules.

        Args:
            appraisals: Dictionary with TP_LABEL, CP_LABEL
            proposed_skill: The skill being proposed

        Returns:
            ValidationResult indicating if action is coherent with appraisals
        """
        errors = []
        warnings = []
        violations = []

        tp = self._normalize_label(appraisals.get("TP_LABEL", "M"))
        cp = self._normalize_label(appraisals.get("CP_LABEL", "M"))

        # Rule 1: High TP + High CP should not do_nothing
        if tp in ("H", "VH") and cp in ("H", "VH"):
            if proposed_skill == "do_nothing":
                errors.append("High threat + high coping should lead to protective action")
                violations.append("high_tp_high_cp_should_act")

        # Rule 2: VH TP requires action
        if tp == "VH":
            if proposed_skill == "do_nothing":
                errors.append("Very high threat perception requires protective action")
                violations.append("extreme_threat_requires_action")

        # Rule 3: Low TP should not justify extreme measures
        if tp in ("VL", "L"):
            if proposed_skill in self._extreme_actions:
                errors.append(f"Low threat ({tp}) does not justify extreme measure: {proposed_skill}")
                violations.append("low_tp_blocks_extreme_action")

        # Rule 4: Low CP limits complex actions
        if cp == "VL":
            if proposed_skill in self._complex_actions:
                warnings.append(f"Very low coping may limit ability to execute: {proposed_skill}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            rule_violations=violations,
            metadata={
                "tp_label": tp,
                "cp_label": cp,
                "proposed_skill": proposed_skill,
            }
        )

    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        """
        Return expected skills given PMT appraisals.

        Based on threat and coping levels, determines expected behaviors:
        - High TP + High CP: Active protection (elevate, insurance, relocate)
        - High TP + Low CP: Basic protection or seek help (insurance)
        - Low TP + Any CP: Status quo acceptable (do_nothing, insurance)

        Args:
            appraisals: Dictionary with TP_LABEL, CP_LABEL

        Returns:
            List of expected skill names
        """
        tp = self._normalize_label(appraisals.get("TP_LABEL", "M"))
        cp = self._normalize_label(appraisals.get("CP_LABEL", "M"))

        expected = []

        # High threat + High coping: Active protection measures
        if tp in ("H", "VH") and cp in ("H", "VH"):
            expected = ["elevate_house", "buy_insurance", "buyout_program", "relocate"]

        # High threat + Medium/Low coping: Seek external help
        elif tp in ("H", "VH") and cp in ("VL", "L", "M"):
            expected = ["buy_insurance", "buyout_program"]

        # Medium threat: Moderate protection
        elif tp == "M":
            expected = ["buy_insurance", "do_nothing"]

        # Low threat: Status quo is acceptable
        else:  # tp in ("VL", "L")
            expected = ["do_nothing", "buy_insurance"]

        return expected

    def get_blocked_skills(self, appraisals: Dict[str, str]) -> List[str]:
        """
        Return skills that should be blocked given PMT appraisals.

        Args:
            appraisals: Dictionary with TP_LABEL, CP_LABEL

        Returns:
            List of skill names that should be blocked
        """
        tp = self._normalize_label(appraisals.get("TP_LABEL", "M"))
        cp = self._normalize_label(appraisals.get("CP_LABEL", "M"))

        blocked = []

        # High TP + High CP: Block inaction
        if tp in ("H", "VH") and cp in ("H", "VH"):
            blocked.append("do_nothing")

        # VH TP alone blocks inaction
        if tp == "VH":
            if "do_nothing" not in blocked:
                blocked.append("do_nothing")

        # Low TP blocks extreme measures
        if tp in ("VL", "L"):
            blocked.extend(self._extreme_actions)

        return list(set(blocked))  # Remove duplicates

    def _normalize_label(self, label: Optional[str]) -> str:
        """Normalize PMT label to standard format."""
        if not label:
            return "M"  # Default to Medium
        label = str(label).upper().strip()
        mappings = {
            "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
            "LOW": "L",
            "MEDIUM": "M", "MED": "M", "MODERATE": "M",
            "HIGH": "H",
            "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH"
        }
        return mappings.get(label, label)

    def compare_labels(self, label1: str, label2: str) -> int:
        """
        Compare two PMT labels.

        Args:
            label1: First label
            label2: Second label

        Returns:
            -1 if label1 < label2, 0 if equal, 1 if label1 > label2
        """
        order1 = PMT_LABEL_ORDER.get(self._normalize_label(label1), 2)
        order2 = PMT_LABEL_ORDER.get(self._normalize_label(label2), 2)
        if order1 < order2:
            return -1
        elif order1 > order2:
            return 1
        return 0


class UtilityFramework(PsychologicalFramework):
    """
    Utility Theory framework for government agents.

    Government agents evaluate policies based on:
    - Budget Utility: Fiscal impact (deficit, neutral, surplus)
    - Equity Gap: Socioeconomic equity assessment
    - Adoption Rate: Policy adoption among constituents

    Coherence rules:
    - High deficit with high spending programs is inconsistent
    - High equity gap should prioritize equity-focused actions
    """

    @property
    def name(self) -> str:
        return "Utility Theory"

    def get_constructs(self) -> Dict[str, ConstructDef]:
        """Return Utility Theory constructs for government agents."""
        return {
            "BUDGET_UTIL": ConstructDef(
                name="Budget Utility",
                values=["DEFICIT", "NEUTRAL", "SURPLUS"],
                required=True,
                description="Current budget impact assessment"
            ),
            "EQUITY_GAP": ConstructDef(
                name="Equity Gap",
                values=["HIGH", "MEDIUM", "LOW"],
                required=True,
                description="Socioeconomic equity assessment"
            ),
            "ADOPTION_RATE": ConstructDef(
                name="Adoption Rate",
                values=["LOW", "MEDIUM", "HIGH"],
                required=False,
                description="Current policy adoption rate"
            ),
        }

    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        """
        Validate Utility Theory coherence.

        Args:
            appraisals: Dictionary with BUDGET_UTIL, EQUITY_GAP, ADOPTION_RATE

        Returns:
            ValidationResult with coherence assessment
        """
        errors = []
        warnings = []

        # Check required constructs
        required_check = self.validate_required_constructs(appraisals)
        if not required_check.valid:
            return required_check

        # Check value validity
        value_check = self.validate_construct_values(appraisals)
        if not value_check.valid:
            return value_check

        budget = appraisals.get("BUDGET_UTIL", "NEUTRAL").upper()
        equity = appraisals.get("EQUITY_GAP", "MEDIUM").upper()

        # Coherence warnings
        if budget == "DEFICIT" and equity == "HIGH":
            warnings.append("Budget deficit with high equity gap may require careful prioritization")

        return ValidationResult(
            valid=True,
            errors=errors,
            warnings=warnings,
            metadata={
                "budget_util": budget,
                "equity_gap": equity,
                "adoption_rate": appraisals.get("ADOPTION_RATE", ""),
            }
        )

    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        """
        Return expected government actions given utility appraisals.

        Args:
            appraisals: Dictionary with BUDGET_UTIL, EQUITY_GAP

        Returns:
            List of expected action/skill names
        """
        budget = appraisals.get("BUDGET_UTIL", "NEUTRAL").upper()
        equity = appraisals.get("EQUITY_GAP", "MEDIUM").upper()

        expected = []

        # High equity gap prioritizes equity-focused actions
        if equity == "HIGH":
            expected = ["increase_subsidy", "targeted_assistance", "outreach_program"]

        # Budget surplus allows more spending
        elif budget == "SURPLUS":
            expected = ["increase_subsidy", "infrastructure_improvement", "expand_program"]

        # Budget deficit requires cost control
        elif budget == "DEFICIT":
            expected = ["reduce_subsidy", "cost_optimization", "maintain_current"]

        else:
            expected = ["maintain_current", "incremental_improvement"]

        return expected


class FinancialFramework(PsychologicalFramework):
    """
    Financial Risk Theory framework for insurance agents.

    Insurance agents evaluate decisions based on:
    - Loss Ratio: Claims vs premiums (high, medium, low)
    - Solvency: Financial stability (at_risk, stable, strong)
    - Market Share: Competitive position

    Coherence rules:
    - High loss ratio with strong solvency may indicate pricing issues
    - At-risk solvency should prioritize conservative actions
    """

    @property
    def name(self) -> str:
        return "Financial Risk Theory"

    def get_constructs(self) -> Dict[str, ConstructDef]:
        """Return Financial constructs for insurance agents."""
        return {
            "LOSS_RATIO": ConstructDef(
                name="Loss Ratio",
                values=["HIGH", "MEDIUM", "LOW"],
                required=True,
                description="Claims to premiums ratio assessment"
            ),
            "SOLVENCY": ConstructDef(
                name="Solvency",
                values=["AT_RISK", "STABLE", "STRONG"],
                required=True,
                description="Financial stability status"
            ),
            "MARKET_SHARE": ConstructDef(
                name="Market Share",
                values=["DECLINING", "STABLE", "GROWING"],
                required=False,
                description="Competitive market position"
            ),
        }

    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        """
        Validate Financial Theory coherence.

        Args:
            appraisals: Dictionary with LOSS_RATIO, SOLVENCY, MARKET_SHARE

        Returns:
            ValidationResult with coherence assessment
        """
        errors = []
        warnings = []

        # Check required constructs
        required_check = self.validate_required_constructs(appraisals)
        if not required_check.valid:
            return required_check

        # Check value validity
        value_check = self.validate_construct_values(appraisals)
        if not value_check.valid:
            return value_check

        loss = appraisals.get("LOSS_RATIO", "MEDIUM").upper()
        solvency = appraisals.get("SOLVENCY", "STABLE").upper()

        # Coherence warnings
        if loss == "HIGH" and solvency == "STRONG":
            warnings.append("High loss ratio with strong solvency may indicate pricing inefficiency")

        if solvency == "AT_RISK":
            warnings.append("At-risk solvency requires conservative decision-making")

        return ValidationResult(
            valid=True,
            errors=errors,
            warnings=warnings,
            metadata={
                "loss_ratio": loss,
                "solvency": solvency,
                "market_share": appraisals.get("MARKET_SHARE", ""),
            }
        )

    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        """
        Return expected insurance actions given financial appraisals.

        Args:
            appraisals: Dictionary with LOSS_RATIO, SOLVENCY

        Returns:
            List of expected action/skill names
        """
        loss = appraisals.get("LOSS_RATIO", "MEDIUM").upper()
        solvency = appraisals.get("SOLVENCY", "STABLE").upper()

        expected = []

        # At-risk solvency: Conservative actions
        if solvency == "AT_RISK":
            expected = ["raise_premium", "limit_coverage", "reduce_exposure"]

        # High loss ratio: Corrective actions
        elif loss == "HIGH":
            expected = ["raise_premium", "adjust_coverage", "increase_deductible"]

        # Strong position: Growth actions
        elif solvency == "STRONG" and loss == "LOW":
            expected = ["expand_coverage", "competitive_pricing", "new_product"]

        else:
            expected = ["maintain_pricing", "standard_renewal"]

        return expected


# Framework registry
_FRAMEWORKS: Dict[str, type] = {
    "pmt": PMTFramework,
    "utility": UtilityFramework,
    "financial": FinancialFramework,
}


def get_framework(name: str) -> PsychologicalFramework:
    """
    Factory function to get a psychological framework by name.

    Args:
        name: Framework name ("pmt", "utility", "financial")

    Returns:
        Instance of the requested framework

    Raises:
        ValueError: If framework name is unknown

    Example:
        >>> framework = get_framework("pmt")
        >>> constructs = framework.get_constructs()
    """
    name_lower = name.lower().strip()

    if name_lower not in _FRAMEWORKS:
        available = ", ".join(_FRAMEWORKS.keys())
        raise ValueError(f"Unknown framework: '{name}'. Available: {available}")

    return _FRAMEWORKS[name_lower]()


def register_framework(name: str, framework_class: type) -> None:
    """
    Register a custom psychological framework.

    Args:
        name: Framework name for lookup
        framework_class: Class implementing PsychologicalFramework

    Raises:
        TypeError: If framework_class doesn't inherit from PsychologicalFramework
    """
    if not issubclass(framework_class, PsychologicalFramework):
        raise TypeError(f"{framework_class} must inherit from PsychologicalFramework")

    _FRAMEWORKS[name.lower()] = framework_class


def list_frameworks() -> List[str]:
    """Return list of available framework names."""
    return list(_FRAMEWORKS.keys())
