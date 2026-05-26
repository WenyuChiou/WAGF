"""Domain-validator dispatch (relocated 2026-05-25, Phase 6P-A).

Phase 6P-A moves the previously-water-housed builder here so that the
generic governance entrypoint (`broker/validators/governance/__init__.py`)
no longer has to reach into `broker.domains.water.*` to dispatch
validators for ANY domain. The function body itself has been
registry-driven since Phase 6C-v2 (2026-05-10) — only its address
moves. `broker/domains/water/validator_bundles.py` keeps a 3-line
re-export shim so any third-party caller that still imports from the
old path keeps working.

Phase 6B-1 (2026-05-04): domain-specific check tuples come from the
`ValidatorRegistry` plugin registry. Example packages register their
checks at their own `validators/__init__.py` import time.

Phase 6J-D (2026-05-22): removed the legacy ``_ensure_*_registered``
lazy fallback that reverse-imported from ``examples/*/validators`` —
generic broker code must not import from ``examples/``. Each example
package's ``__init__.py`` imports its ``validators`` submodule on
import, and every ``run_*.py`` entrypoint imports the example package
early. A domain whose checks have not been registered by the time
``build_domain_validators`` runs returns ``_empty_validators()`` (the
YAML rule path is unaffected).
"""

import logging
from typing import List, Optional, Set, Tuple

from broker.components.governance.validator_registry import ValidatorRegistry
from broker.validators.governance.base_validator import BuiltinCheck
from broker.validators.governance.personal_validator import PersonalValidator
from broker.validators.governance.social_validator import SocialValidator
from broker.validators.governance.thinking_validator import ThinkingValidator
from broker.validators.governance.physical_validator import PhysicalValidator
from broker.validators.governance.semantic_validator import SemanticGroundingValidator

logger = logging.getLogger(__name__)

# Phase 6Q-D-4 (2026-05-26): warn-once dedup set for unregistered-
# framework downgrade events at dispatch time. Keyed by (domain,
# framework_string). Same pattern as
# unified_context_builder._WARNED_UNDECLARED_FRAMEWORK.
_WARNED_UNREGISTERED_FRAMEWORK: Set[Tuple[str, str]] = set()


def _empty_validators() -> list:
    from broker.validators.governance.thinking_validator import (
        FRAMEWORK_ESCAPE_HATCH,
    )
    no_builtins: List[BuiltinCheck] = []
    return [
        PersonalValidator(builtin_checks=no_builtins),
        PhysicalValidator(builtin_checks=no_builtins),
        # Phase 6Q-D (2026-05-26): pass the blessed escape-hatch
        # sentinel — explicit no-metadata signal, generic 5-level
        # VL/L/M/H/VH ordering. Empty domain by definition has no
        # registered framework.
        ThinkingValidator(framework=FRAMEWORK_ESCAPE_HATCH, builtin_checks=no_builtins),
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
        return _empty_validators()

    extreme: set = set()
    framework: str = ""
    try:
        from broker.domains.registry import DomainPackRegistry
        # Phase 6R-D-4 (2026-05-26): narrowed to GovernancePack —
        # validator dispatch only needs psychological_framework /
        # extreme_actions / builtin_checks, all owned by GovernancePack.
        pack = DomainPackRegistry.get_governance_pack(resolved)
        # Phase 6Q-D-4 (2026-05-26): each DomainPack accessor wrapped
        # in its own try/except. A custom pack with a broken method
        # (typo'd attribute, missing import, runtime error in a
        # subclass) used to crash the entire governance pipeline via
        # an unhandled exception bubbling out of build_domain_validators
        # → validate_all. Now: log + fall back to a benign default so
        # the validator graph still builds with reduced fidelity.
        try:
            extreme = pack.extreme_actions()
        except Exception as exc:  # noqa: BLE001 — graceful boundary
            logger.warning(
                "[DomainPack:%s] extreme_actions() raised %r; falling back "
                "to empty set. Custom DomainPack contract is broken — fix "
                "the pack OR override extreme_actions() to return set().",
                resolved, exc,
            )
            extreme = set()
        try:
            framework = pack.psychological_framework()
        except Exception as exc:  # noqa: BLE001 — graceful boundary
            logger.warning(
                "[DomainPack:%s] psychological_framework() raised %r; "
                "falling back to FRAMEWORK_ESCAPE_HATCH. Custom DomainPack "
                "contract is broken — fix the pack OR override the method "
                "to return one of: pmt / cognitive_appraisal / hbm / "
                "utility / financial / \"\".",
                resolved, exc,
            )
            from broker.validators.governance.thinking_validator import (
                FRAMEWORK_ESCAPE_HATCH,
            )
            framework = FRAMEWORK_ESCAPE_HATCH
    except ImportError:
        if resolved == "flood":
            extreme = {"relocate", "elevate_house"}
            framework = "pmt"

    # Phase 6Q-D-4 (2026-05-26): pre-construction framework-registry
    # check. Pre-fix the dispatcher passed `framework` straight to
    # `ThinkingValidator(framework=...)`, which raises ValueError if
    # the framework is non-empty AND not in FRAMEWORK_LABEL_ORDERS.
    # The cascade: pack returns a typo'd / unregistered framework
    # string → ThinkingValidator raises → validate_all crashes →
    # SkillBrokerEngine retry loop crashes → entire agent decision
    # lost. The boundary-audit subagent flagged this as the HIGHEST-
    # leverage failure point in the governance subsystem (Phase 6Q-D-3
    # follow-up audit). Defense: downgrade to escape hatch + warn-
    # once per (domain, framework) so the broker keeps running with
    # generic label-ordering instead of dying.
    if framework:
        from broker.validators.governance.thinking_validator import (
            FRAMEWORK_ESCAPE_HATCH,
            FRAMEWORK_LABEL_ORDERS,
        )
        if framework.lower() not in FRAMEWORK_LABEL_ORDERS:
            key = (resolved, framework)
            if key not in _WARNED_UNREGISTERED_FRAMEWORK:
                _WARNED_UNREGISTERED_FRAMEWORK.add(key)
                logger.warning(
                    "[DomainPack:%s] psychological_framework() returned "
                    "%r which is not in FRAMEWORK_LABEL_ORDERS (registered: "
                    "%s). Downgrading to FRAMEWORK_ESCAPE_HATCH so the "
                    "governance pipeline stays alive — fix the pack: "
                    "call register_framework_metadata(%r, ...) at import "
                    "time, OR change psychological_framework() to return "
                    "one of the registered names.",
                    resolved, framework,
                    sorted(FRAMEWORK_LABEL_ORDERS.keys()), framework,
                )
            framework = FRAMEWORK_ESCAPE_HATCH

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
            framework=framework,
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
