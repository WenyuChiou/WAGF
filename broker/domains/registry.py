"""
DomainPackRegistry — discovery and lookup for :class:`DomainPack`
implementations.

Phase 6C-v2 (2026-05-10): single registration point for all
domain-specific behavior. Mirrors the Phase 6B plugin pattern used by
:class:`broker.components.governance.validator_registry.ValidatorRegistry`
and :class:`broker.components.social.filter_registry.FilterRegistry`.

Usage
=====
Registration (inside a domain example's ``__init__.py``)::

    from broker.domains.registry import DomainPackRegistry
    from .vaccination_pack import VaccinationDomainPack
    DomainPackRegistry.register("vaccination", VaccinationDomainPack())

Lookup (inside broker pipeline code)::

    from broker.domains.registry import DomainPackRegistry
    pack = DomainPackRegistry.get_or_default(domain_name)
    status = pack.reflection_status_text(context)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from broker.domains.default import DefaultDomainPack
from broker.domains.protocol import DomainPack

logger = logging.getLogger(__name__)


class DomainPackRegistry:
    """Registry of :class:`DomainPack` implementations keyed by domain name."""

    _packs: Dict[str, DomainPack] = {}
    _default = DefaultDomainPack()
    _missing_warned: set = set()

    @classmethod
    def register(cls, name: str, pack: DomainPack) -> None:
        """Register a pack for ``name``. Re-registering the same name
        replaces the previous binding silently — useful for tests."""
        if not name:
            raise ValueError("Domain name must be non-empty")
        if not hasattr(pack, "name"):
            raise TypeError(
                f"Pack for '{name}' missing required 'name' attribute "
                f"(got {type(pack).__name__})"
            )
        cls._packs[name] = pack

    @classmethod
    def get(cls, name: str) -> Optional[DomainPack]:
        """Return the registered pack or ``None`` if absent.

        Use :meth:`get_or_default` if you want a guaranteed-non-None
        return so callers don't have to guard.
        """
        return cls._packs.get(name)

    @classmethod
    def get_or_default(cls, name: Optional[str]) -> DomainPack:
        """Return the registered pack for ``name`` or a no-op
        :class:`DefaultDomainPack` if absent or ``name is None``.

        Emits a one-time WARNING per unknown name so silent
        misconfigurations surface quickly. Mirrors the ``warn-once``
        pattern from ``SkillRegistry.get_default_skill()`` (Phase 6A).
        """
        if not name:
            return cls._default
        pack = cls._packs.get(name)
        if pack is None:
            if name not in cls._missing_warned:
                logger.warning(
                    "[DomainPack] No pack registered for domain '%s'; "
                    "falling back to DefaultDomainPack (no-op). Register "
                    "via DomainPackRegistry.register('%s', YourPack()) "
                    "in your example package's __init__.py.",
                    name, name,
                )
                cls._missing_warned.add(name)
            return cls._default
        return pack

    @classmethod
    def domains(cls) -> List[str]:
        """List names of registered domains. Order is insertion order."""
        return list(cls._packs.keys())

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls._packs

    @classmethod
    def clear(cls) -> None:
        """Reset registry — for tests only. Production code should never
        call this."""
        cls._packs.clear()
        cls._missing_warned.clear()
