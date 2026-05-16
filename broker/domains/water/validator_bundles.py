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


def _with_registered_mode(validator, domain: str, slot: str):
    validator.set_mode(ValidatorRegistry.get_validator_mode(domain, slot))
    return validator


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
    """Return builtin validator instances for any registered domain.

    Phase 6C-v2 (2026-05-10): the ``if domain == "irrigation"/"flood"``
    chain is replaced with a registry-driven query. Domain-specific
    ``extreme_actions`` come from the registered ``DomainPack`` so the
    irrigation/flood branches no longer need to be hardcoded here.

    The lazy ``_ensure_*_registered`` helpers are kept for backward
    compatibility with entrypoints that don't pre-import the example
    package (Phase 6B-1 fallback). They remain water-specific because
    they target ``examples.irrigation_abm.validators`` and
    ``examples.governed_flood.validators`` directly.
    """
    resolved = (domain or "").strip().lower() or None

    if resolved is None:
        return _empty_validators()

    # Backward-compat: if domain matches a known water example whose
    # validators package hasn't been imported yet, trigger the lazy
    # import so the registry is populated before we query it.
    if resolved == "irrigation":
        _ensure_irrigation_registered()
    elif resolved == "flood":
        _ensure_flood_registered()

    if not ValidatorRegistry.has_domain(resolved):
        # Unknown domain — return empty validators (broker continues
        # with YAML rules only). DefaultDomainPack would do the same.
        return _empty_validators()

    # Pull extreme_actions from the registered DomainPack (replaces
    # the irrigation/flood branch difference).
    extreme: set = set()
    try:
        from broker.domains.registry import DomainPackRegistry
        pack = DomainPackRegistry.get_or_default(resolved)
        extreme = pack.extreme_actions()
    except ImportError:
        # Pre-Phase-6C-v2 fallback: hardcode flood's extreme_actions.
        if resolved == "flood":
            extreme = {"relocate", "elevate_house"}

    return [
        _with_registered_mode(
            PersonalValidator(builtin_checks=ValidatorRegistry.get_checks(resolved, "personal")),
            resolved,
            "personal",
        ),
        _with_registered_mode(
            PhysicalValidator(builtin_checks=ValidatorRegistry.get_checks(resolved, "physical")),
            resolved,
            "physical",
        ),
        _with_registered_mode(ThinkingValidator(
            builtin_checks=ValidatorRegistry.get_checks(resolved, "thinking"),
            extreme_actions=extreme,
        ), resolved, "thinking"),
        _with_registered_mode(
            SocialValidator(builtin_checks=ValidatorRegistry.get_checks(resolved, "social")),
            resolved,
            "social",
        ),
        _with_registered_mode(
            SemanticGroundingValidator(builtin_checks=ValidatorRegistry.get_checks(resolved, "semantic")),
            resolved,
            "semantic",
        ),
    ]
