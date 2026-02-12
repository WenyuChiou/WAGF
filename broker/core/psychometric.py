"""
Psychometric Framework — Psychological assessment frameworks for agent validation.

This module provides the abstract base class and registry for psychological
frameworks.  Concrete implementations live in domain packs under
``broker/domains/`` (e.g., ``broker.domains.water.pmt.PMTFramework``).

The ``get_framework()`` / ``register_framework()`` registry allows domain
packs to self-register at import time so that callers need not know where
concrete classes reside.

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


# ---------------------------------------------------------------------------
# Framework registry
# ---------------------------------------------------------------------------

_FRAMEWORKS: Dict[str, type] = {}


def get_framework(name: str) -> PsychologicalFramework:
    """
    Factory function to get a psychological framework by name.

    Args:
        name: Framework name (e.g., "pmt", "utility", "financial")

    Returns:
        Instance of the requested framework

    Raises:
        ValueError: If framework name is unknown

    Example:
        >>> framework = get_framework("pmt")
        >>> constructs = framework.get_constructs()
    """
    # Ensure domain packs are loaded (lazy trigger)
    if not _FRAMEWORKS:
        try:
            import broker.domains  # noqa: F401
        except ImportError:
            pass

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
    # Ensure domain packs are loaded
    if not _FRAMEWORKS:
        try:
            import broker.domains  # noqa: F401
        except ImportError:
            pass
    return list(_FRAMEWORKS.keys())


# ---------------------------------------------------------------------------
# Backward-compatibility shim
# ---------------------------------------------------------------------------
# Concrete framework classes were moved to broker.domains.water in v0.3.
# This __getattr__ allows old imports like:
#     from broker.core.psychometric import PMTFramework
# to continue working with a deprecation warning.

_MOVED_CLASSES = {
    "PMTFramework": "broker.domains.water.pmt",
    "UtilityFramework": "broker.domains.water.utility",
    "FinancialFramework": "broker.domains.water.financial",
    "PMT_LABEL_ORDER": "broker.domains.water.pmt",
}


def __getattr__(name: str):
    if name in _MOVED_CLASSES:
        import importlib
        import warnings
        module_path = _MOVED_CLASSES[name]
        warnings.warn(
            f"{name} has moved to {module_path}. "
            f"Update your import to: from {module_path} import {name}",
            DeprecationWarning,
            stacklevel=2,
        )
        mod = importlib.import_module(module_path)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
