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
from typing import Dict, List, Optional, cast

from broker.domains.default import DefaultDomainPack
from broker.domains.protocol import (
    DomainPack,
    EventPack,
    GovernancePack,
    MemoryPack,
    PerceptionPack,
    ReflectionPack,
    SetupPack,
    SkillPack,
)

logger = logging.getLogger(__name__)


class DomainPackRegistry:
    """Registry of :class:`DomainPack` implementations keyed by domain name."""

    _packs: Dict[str, DomainPack] = {}
    _default = DefaultDomainPack()
    _missing_warned: set = set()

    # Phase 6Q-D-5 (2026-05-26): the subset of DomainPack methods
    # we sanity-check at registration time. Selected because they
    # are (a) called on the hot validator-dispatch path or (b)
    # called by reflection / event manager / memory infrastructure
    # — methods whose broken state would surface as a confusing
    # crash much later in the simulation. We DO NOT call every
    # ~30 DomainPack methods (too expensive); these 3 are
    # representative of the broken-pack failure mode.
    _SMOKE_METHODS: tuple = (
        "psychological_framework",
        "extreme_actions",
        "memory_policy",
    )

    @classmethod
    def _smoke_test_pack(cls, name: str, pack: DomainPack) -> None:
        """Phase 6Q-D-5: call a small set of DomainPack methods at
        registration time to surface broken packs early. Pre-fix
        a partially-imported pack (e.g. circular import that left
        a method bound to a half-initialised class) would only
        surface much later when a hot-path consumer called the
        broken method — boundary audit Pair #5 (MED-HIGH).

        Pure log-and-continue: any failure logs a WARNING with the
        method name + the exception type, but the pack is STILL
        registered. Rationale: Phase 6Q-D-4 already wraps
        ``build_domain_validators`` with graceful-fallback guards,
        so a broken pack-in-the-registry doesn't crash the
        validator dispatch path; this smoke just surfaces the
        problem earlier (at module-import time, where the trace
        points at the registration call site) instead of later
        (during a multi-hour experiment run).
        """
        for method_name in cls._SMOKE_METHODS:
            method = getattr(pack, method_name, None)
            if method is None:
                logger.warning(
                    "[DomainPack:%s] missing method %r at registration "
                    "time. Hot-path consumers may crash. Check that your "
                    "pack subclasses DefaultDomainPack OR implements the "
                    "full DomainPack Protocol surface.",
                    name, method_name,
                )
                continue
            try:
                method()
            except Exception as exc:  # noqa: BLE001 — registration-time smoke
                logger.warning(
                    "[DomainPack:%s] %s() raised %s at registration time: "
                    "%r. Pack registered anyway (graceful-fallback in "
                    "consumers will catch downstream calls), but you "
                    "should fix the pack — see %s.%s for the contract.",
                    name, method_name, type(exc).__name__, exc,
                    type(pack).__module__, type(pack).__name__,
                )

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
        # Phase 6Q-D-5: smoke-test the pack before registration so
        # broken methods surface at module-import time, not during
        # a multi-hour experiment run.
        cls._smoke_test_pack(name, pack)
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
        misconfigurations surface quickly.
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

    # ─────────────────────────────────────────────────────────────────
    # Typed sub-protocol accessors (Phase 6R-D-3, 2026-05-26)
    # ─────────────────────────────────────────────────────────────────
    # Consumer subsystems that only need a slice of the DomainPack
    # surface use these accessors to get a type-narrowed view. The
    # underlying pack is the same; the typed return value just helps
    # callers (and type-checkers) reason about which methods are in
    # scope. Each accessor delegates to :meth:`get_or_default` and
    # casts the result — Python's @runtime_checkable composite
    # DomainPack inherits from all 7 sub-protocols, so the cast is
    # structurally safe.
    #
    # Phase 6R-D-4 (next sub-phase) migrates broker consumer call sites
    # to use these typed accessors (e.g. reflection.py calls
    # ``get_reflection_pack(domain)`` instead of
    # ``get_or_default(domain)``). Until then these accessors are
    # zero-impact additions.
    # ─────────────────────────────────────────────────────────────────

    @classmethod
    def get_reflection_pack(cls, name: Optional[str]) -> ReflectionPack:
        """Return the pack for ``name`` typed as :class:`ReflectionPack`.

        Consumer-narrowed accessor for reflection-prompt builders
        (``broker/components/cognitive/reflection.py``). Backed by
        :meth:`get_or_default` — same fallback semantics.
        """
        return cast(ReflectionPack, cls.get_or_default(name))

    @classmethod
    def get_memory_pack(cls, name: Optional[str]) -> MemoryPack:
        """Return the pack for ``name`` typed as :class:`MemoryPack`.

        Consumer-narrowed accessor for memory-engine subsystems
        (``broker/components/memory/{policy_classifier,initial_loader,universal}.py``).
        """
        return cast(MemoryPack, cls.get_or_default(name))

    @classmethod
    def get_skill_pack(cls, name: Optional[str]) -> SkillPack:
        """Return the pack for ``name`` typed as :class:`SkillPack`.

        Consumer-narrowed accessor for skill-emotion / extreme-actions /
        taxonomy / affordability consumers
        (``broker/core/experiment_runner.py``,
        ``broker/validators/agent/agent_validator.py``).
        """
        return cast(SkillPack, cls.get_or_default(name))

    @classmethod
    def get_event_pack(cls, name: Optional[str]) -> EventPack:
        """Return the pack for ``name`` typed as :class:`EventPack`.

        Consumer-narrowed accessor for the multi-agent event manager
        (``broker/components/events/ma_manager.py``).
        """
        return cast(EventPack, cls.get_or_default(name))

    @classmethod
    def get_perception_pack(cls, name: Optional[str]) -> PerceptionPack:
        """Return the pack for ``name`` typed as :class:`PerceptionPack`.

        Consumer-narrowed accessor for the perception filter chain
        (``broker/components/social/perception.py``).
        """
        return cast(PerceptionPack, cls.get_or_default(name))

    @classmethod
    def get_governance_pack(cls, name: Optional[str]) -> GovernancePack:
        """Return the pack for ``name`` typed as :class:`GovernancePack`.

        Consumer-narrowed accessor for validator dispatch + policy
        threshold consumers (``broker/components/governance/*``,
        ``broker/validators/*``, ``broker/tools/validate_prompt.py``).
        """
        return cast(GovernancePack, cls.get_or_default(name))

    @classmethod
    def get_setup_pack(cls, name: Optional[str]) -> SetupPack:
        """Return the pack for ``name`` typed as :class:`SetupPack`.

        Consumer-narrowed accessor for agent initialisation +
        orchestration (``broker/core/agent_initializer.py``,
        ``broker/components/orchestration/phases.py``).
        """
        return cast(SetupPack, cls.get_or_default(name))
