"""
Water-domain validator bundle adapters.

This module isolates water-specific builtin validator wiring from the generic
governance entrypoint so `broker.validators.governance` does not import
example packages directly.

Phase 6B-1 (2026-05-04): domain-specific check tuples now come from the
`ValidatorRegistry` plugin registry. Example packages register their
checks at their own `validators/__init__.py` import time. To preserve
backward compatibility with entrypoints that don't pre-import the
example's validators package, this module retains a one-time legacy
fallback that lazy-imports the example's checks IF the registry is
empty for the requested domain. Once a domain's `validators/__init__.py`
runs (which it will, because run_experiment.py or its imports trigger
it), the registry is populated and subsequent calls skip the fallback.
"""

from typing import List, Optional

from broker.components.governance.validator_registry import ValidatorRegistry
from broker.validators.governance.base_validator import BuiltinCheck
from broker.validators.governance.personal_validator import PersonalValidator
from broker.validators.governance.social_validator import SocialValidator
from broker.validators.governance.thinking_validator import ThinkingValidator
from broker.validators.governance.physical_validator import PhysicalValidator
from broker.validators.governance.semantic_validator import SemanticGroundingValidator


def _empty_validators() -> list:
    no_builtins: List[BuiltinCheck] = []
    return [
        PersonalValidator(builtin_checks=no_builtins),
        PhysicalValidator(builtin_checks=no_builtins),
        ThinkingValidator(builtin_checks=no_builtins),
        SocialValidator(builtin_checks=no_builtins),
        SemanticGroundingValidator(builtin_checks=no_builtins),
    ]


def _ensure_irrigation_registered() -> None:
    """Legacy fallback: if irrigation registry is empty, import the
    example's validators package to trigger its registration side-effect.
    Future code should make example imports happen at startup, not via
    this fallback."""
    if not ValidatorRegistry.get_checks("irrigation", "physical"):
        try:
            import examples.irrigation_abm.validators  # noqa: F401 -- side-effect
        except ImportError:
            pass


def _ensure_flood_registered() -> None:
    """Same as _ensure_irrigation_registered but for flood."""
    if not ValidatorRegistry.get_checks("flood", "physical"):
        try:
            import examples.governed_flood.validators  # noqa: F401 -- side-effect
        except ImportError:
            pass


def build_domain_validators(domain: Optional[str]) -> list:
    """Return builtin validator instances for a water-domain name.

    Domain-specific checks come from the ValidatorRegistry plugin
    registry. The flood-specific ThinkingValidator extreme_actions
    parameter is preserved here because it is a validator-class kwarg
    rather than a check-list import.
    """
    resolved = (domain or "").strip().lower() or None

    if resolved == "irrigation":
        _ensure_irrigation_registered()
        return [
            PersonalValidator(builtin_checks=[]),
            PhysicalValidator(builtin_checks=ValidatorRegistry.get_checks("irrigation", "physical")),
            ThinkingValidator(builtin_checks=[]),
            SocialValidator(builtin_checks=ValidatorRegistry.get_checks("irrigation", "social")),
            SemanticGroundingValidator(builtin_checks=[]),
        ]

    if resolved == "flood":
        _ensure_flood_registered()
        return [
            PersonalValidator(builtin_checks=ValidatorRegistry.get_checks("flood", "personal")),
            PhysicalValidator(builtin_checks=ValidatorRegistry.get_checks("flood", "physical")),
            ThinkingValidator(extreme_actions={"relocate", "elevate_house"}),
            SocialValidator(builtin_checks=ValidatorRegistry.get_checks("flood", "social")),
            SemanticGroundingValidator(builtin_checks=ValidatorRegistry.get_checks("flood", "semantic")),
        ]

    return _empty_validators()
