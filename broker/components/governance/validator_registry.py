"""ValidatorRegistry — plugin-style registration for domain-specific
builtin validator checks.

The previous implementation in `broker/domains/water/validator_bundles.py`
imported from `examples.irrigation_abm.*` and `examples.governed_flood.*`
inside `build_domain_validators()`, violating the "examples plug into
broker, not the reverse" architectural rule.

This registry inverts the dependency: example packages register their
checks at their own `__init__.py` import time. The broker then looks up
checks by `(domain, slot)` without ever importing example modules.

Pattern matches `SkillRegistry` in `broker/components/governance/registry.py`
and `EventManager` in `broker/components/events/manager.py`.
"""
from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Slot taxonomy — one bucket per validator class that accepts builtin checks.
VALID_SLOTS = ("physical", "personal", "social", "semantic", "temporal", "behavioural")


class ValidatorRegistry:
    """Plugin registry mapping (domain, slot) -> list of builtin check callables.

    Example packages register at import time:
        from broker.components.governance.validator_registry import ValidatorRegistry
        ValidatorRegistry.register("irrigation", "physical", [check_a, check_b])

    Broker code looks up at validator-build time:
        checks = ValidatorRegistry.get_checks("irrigation", "physical")
    """
    _registry: Dict[str, Dict[str, list]] = {}
    _missing_warned: set = set()  # one-time-warning tracking per (domain, slot)

    @classmethod
    def register(cls, domain: str, slot: str, checks: list) -> None:
        """Register a list of builtin checks for a (domain, slot) pair.

        Idempotent: re-registering the same (domain, slot) overwrites
        previous entries. This makes test fixtures and reload-style
        development simple.
        """
        if not domain or not isinstance(domain, str):
            raise ValueError(f"ValidatorRegistry.register: domain must be a non-empty string, got {domain!r}")
        if slot not in VALID_SLOTS:
            raise ValueError(f"ValidatorRegistry.register: slot must be one of {VALID_SLOTS}, got {slot!r}")
        d = domain.strip().lower()
        cls._registry.setdefault(d, {})[slot] = list(checks)

    @classmethod
    def get_checks(cls, domain: str, slot: str) -> list:
        """Return the registered list of checks for (domain, slot).

        If domain is unknown OR slot is empty for that domain, returns []
        and emits a one-time warning (per (domain, slot)) so silent
        flood-domain fallbacks become visible to non-water domain authors.
        """
        d = (domain or "").strip().lower() or "default"
        bucket = cls._registry.get(d, {}).get(slot, [])
        if not bucket and d != "default":
            key = (d, slot)
            if key not in cls._missing_warned:
                logger.warning(
                    "ValidatorRegistry: no checks registered for domain=%r slot=%r. "
                    "Registered domains: %s. Did the example package's __init__.py import?",
                    d, slot, sorted(cls._registry.keys()),
                )
                cls._missing_warned.add(key)
        return list(bucket)

    @classmethod
    def domains(cls) -> List[str]:
        """List all currently-registered domain names."""
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """Reset registry. Tests use this between fixtures."""
        cls._registry.clear()
        cls._missing_warned.clear()
