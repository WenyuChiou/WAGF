"""
Water-domain validator bundle adapters.

This module isolates water-specific builtin validator wiring from the generic
governance entrypoint so `broker.validators.governance` does not import
example packages directly.

Phase 6B-1 (2026-05-04): domain-specific check tuples come from the
`ValidatorRegistry` plugin registry. Example packages register their
checks at their own `validators/__init__.py` import time.

Phase 6J-D (2026-05-22): removed the legacy ``_ensure_*_registered``
lazy fallback that reverse-imported from ``examples/*/validators`` —
``broker/domains/water/`` must not import from ``examples/``. Each
example package ``__init__.py`` now imports its ``validators``
submodule on import, and every ``run_*.py`` entrypoint imports the
example package early. A domain whose checks have not been registered
by the time ``build_domain_validators`` runs returns
``_empty_validators()`` (the YAML rule path is unaffected).
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


def build_domain_validators(domain: Optional[str]) -> list:
    """Return builtin validator instances for any registered domain.

    Phase 6C-v2 (2026-05-10): the ``if domain == "irrigation"/"flood"``
    chain is replaced with a registry-driven query. Domain-specific
    ``extreme_actions`` come from the registered ``DomainPack`` so the
    irrigation/flood branches no longer need to be hardcoded here.

    Phase 6J-D (2026-05-22): the reverse-importing ``_ensure_*_registered``
    fallbacks were removed. Each example package's ``__init__.py``
    imports its ``validators`` submodule on import, and each
    ``run_*.py`` entrypoint imports the example package early — so by
    the time this function runs, the requested domain's checks are
    already registered. An empty domain returns ``_empty_validators()``.
    """
    resolved = (domain or "").strip().lower() or None

    if resolved is None:
        return _empty_validators()

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
