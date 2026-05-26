"""Phase 6R-D-3 regression — DomainPackRegistry typed sub-protocol accessors.

After Phase 6R-D-1 split `DomainPack` into 7 sub-protocols
(``ReflectionPack`` / ``MemoryPack`` / ``SkillPack`` / ``EventPack`` /
``PerceptionPack`` / ``GovernancePack`` / ``SetupPack``), this
sub-phase adds typed accessors on ``DomainPackRegistry`` that return
the registered pack narrowed to the relevant sub-protocol.

Consumer subsystems will migrate to these accessors in Phase 6R-D-4
(e.g. ``reflection.py`` calls ``get_reflection_pack(domain)`` instead
of ``get_or_default(domain)``). Until then these accessors are
additive — every existing call site keeps working unchanged.

Tests:
1. All 7 typed accessors exist on the registry class.
2. Each returns the same underlying object as ``get_or_default``
   (just type-narrowed via ``cast``).
3. Each accessor's return satisfies the sub-protocol's
   ``runtime_checkable`` ``isinstance`` check.
4. Missing-domain fallback (``DefaultDomainPack``) also satisfies
   every sub-protocol.
"""
from __future__ import annotations

import pytest

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
from broker.domains.registry import DomainPackRegistry


# ---------------------------------------------------------------------------
# Accessor existence + signature
# ---------------------------------------------------------------------------

_ACCESSORS = [
    ("get_reflection_pack", ReflectionPack),
    ("get_memory_pack", MemoryPack),
    ("get_skill_pack", SkillPack),
    ("get_event_pack", EventPack),
    ("get_perception_pack", PerceptionPack),
    ("get_governance_pack", GovernancePack),
    ("get_setup_pack", SetupPack),
]


class TestAccessorExistence:
    @pytest.mark.parametrize("method_name, _proto", _ACCESSORS, ids=lambda v: v if isinstance(v, str) else v.__name__)
    def test_accessor_exists(self, method_name, _proto):
        assert hasattr(DomainPackRegistry, method_name), (
            f"DomainPackRegistry missing typed accessor {method_name!r}"
        )
        method = getattr(DomainPackRegistry, method_name)
        assert callable(method)

    def test_exactly_7_typed_accessors(self):
        """Sanity: there's one accessor per sub-protocol, no more, no less."""
        public_get_methods = {
            name for name in dir(DomainPackRegistry)
            if name.startswith("get_") and name.endswith("_pack")
            and callable(getattr(DomainPackRegistry, name))
        }
        assert public_get_methods == {name for name, _ in _ACCESSORS}


# ---------------------------------------------------------------------------
# Fallback semantics — DefaultDomainPack returned for missing/None
# ---------------------------------------------------------------------------

class TestAccessorFallback:
    """Missing or None domain → DefaultDomainPack, typed as the
    relevant sub-protocol. Confirms accessors don't bypass
    ``get_or_default``."""

    @pytest.mark.parametrize("method_name, _proto", _ACCESSORS, ids=lambda v: v if isinstance(v, str) else v.__name__)
    def test_none_domain_returns_default(self, method_name, _proto):
        pack = getattr(DomainPackRegistry, method_name)(None)
        assert isinstance(pack, DefaultDomainPack)

    @pytest.mark.parametrize("method_name, _proto", _ACCESSORS, ids=lambda v: v if isinstance(v, str) else v.__name__)
    def test_unregistered_domain_returns_default(self, method_name, _proto):
        pack = getattr(DomainPackRegistry, method_name)("__nonexistent_domain_xyz__")
        assert isinstance(pack, DefaultDomainPack)


# ---------------------------------------------------------------------------
# Sub-protocol satisfaction — registered pack accepted by every accessor
# ---------------------------------------------------------------------------

class TestRegisteredPackSatisfiesSubProtocol:
    """A registered pack returned via the typed accessor must
    structurally satisfy the corresponding sub-protocol (the cast is
    not just syntactic — Python's @runtime_checkable verifies the
    method set is present)."""

    @pytest.fixture(autouse=True)
    def _register_flood_pack(self):
        import examples.governed_flood  # noqa: F401

    @pytest.mark.parametrize("method_name, proto", _ACCESSORS, ids=lambda v: v if isinstance(v, str) else v.__name__)
    def test_flood_pack_via_accessor_satisfies_protocol(self, method_name, proto):
        pack = getattr(DomainPackRegistry, method_name)("flood")
        assert isinstance(pack, proto), (
            f"{method_name}('flood') returned pack that does not "
            f"satisfy {proto.__name__}"
        )

    @pytest.mark.parametrize("method_name, _proto", _ACCESSORS, ids=lambda v: v if isinstance(v, str) else v.__name__)
    def test_accessor_returns_same_underlying_object_as_get_or_default(
        self, method_name, _proto,
    ):
        """Typed accessor MUST be a thin cast — same instance returned
        as ``get_or_default``. Confirms the accessor doesn't accidentally
        wrap or copy the pack."""
        from_get = DomainPackRegistry.get_or_default("flood")
        from_typed = getattr(DomainPackRegistry, method_name)("flood")
        assert from_get is from_typed


# ---------------------------------------------------------------------------
# Default pack satisfies all 7 sub-protocols
# ---------------------------------------------------------------------------

class TestDefaultPackSatisfiesAllSubProtocols:
    """``DefaultDomainPack()`` — returned by every accessor when the
    domain is missing — must satisfy every sub-protocol. Otherwise
    the fallback path would be broken for consumers that use
    typed accessors."""

    @pytest.mark.parametrize(
        "proto",
        [proto for _, proto in _ACCESSORS],
        ids=lambda v: v.__name__,
    )
    def test_default_pack_satisfies(self, proto):
        assert isinstance(DefaultDomainPack(), proto), (
            f"DefaultDomainPack does not satisfy {proto.__name__}; "
            "typed accessor fallback would be broken."
        )

    def test_default_pack_satisfies_composite(self):
        assert isinstance(DefaultDomainPack(), DomainPack)
