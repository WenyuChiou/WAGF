"""Phase 6R-F regression — pin the Phase 6R-D-5/6 sub-pack
decomposition pattern.

After Phase 6R-D-5 (FloodDomainPack) + 6R-D-6 (Irrigation +
Vaccination), each production example pack splits its class body into
sub-pack mixin classes corresponding to the Phase 6R-D-1 sub-protocols.
The pattern is:

    class FooReflectionMixin: ...
    class FooMemoryMixin: ...
    # ... more mixins per sub-protocol the pack overrides
    class FooDomainPack(FooReflectionMixin, FooMemoryMixin, ..., DefaultDomainPack):
        name = "foo"

This gate prevents a future contributor from accidentally reverting
the decomposition (e.g. by collapsing all methods back into a single
``FooDomainPack`` class body during a "simplification" pass — losing
the type-narrowing + cohesion benefits the 6R-D refactor established).

Scope: ONLY production paper-1b example packs (Flood / Irrigation /
Vaccination). The FakeTraffic test fixture is intentionally exempt
— per the Phase 6R-D-6 CHANGELOG entry, splitting its 115-LOC body
into mixins would add ~30 LOC of structural overhead with zero
functional benefit (the fixture only overrides 7 methods across 4
sub-protocols).
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

import pytest


# Production packs that MUST follow the mixin decomposition pattern.
# (path relative to repo root, name of the composite class).
_GUARDED_PACKS: List[Tuple[str, str]] = [
    (
        "examples/governed_flood/adapters/flood_pack.py",
        "FloodDomainPack",
    ),
    (
        "examples/irrigation_abm/adapters/irrigation_pack.py",
        "IrrigationDomainPack",
    ),
    (
        "examples/vaccination_demo/adapters/vaccination_pack.py",
        "VaccinationDomainPack",
    ),
]

# Sub-pack mixin class names follow the convention
# ``<Domain><SubProto>Mixin`` where <SubProto> is one of the seven
# Phase 6R-D-1 sub-protocol names (without the ``Pack`` suffix).
_SUB_PROTO_NAMES = (
    "Reflection",
    "Memory",
    "Skill",
    "Event",
    "Perception",
    "Governance",
    "Setup",
)


def _classes_in(path: Path) -> List[str]:
    """Return the names of all top-level class definitions in ``path``."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return [
        node.name for node in tree.body
        if isinstance(node, ast.ClassDef)
    ]


def _composite_bases(path: Path, composite_name: str) -> List[str]:
    """Return the base-class names (as strings) of the composite
    class declared at the top level of ``path``. Returns ``[]`` if
    the composite isn't found."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == composite_name:
            bases: List[str] = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)
            return bases
    return []


class TestSubPackMixinDecomposition:
    """Each production pack file must declare at least one sub-pack
    mixin AND the composite class must inherit from at least one
    of those mixins."""

    @pytest.mark.parametrize(
        "rel_path, composite_name",
        _GUARDED_PACKS,
        ids=lambda v: v.rsplit("/", 1)[-1] if isinstance(v, str) and "/" in v else v,
    )
    def test_pack_declares_at_least_one_mixin(
        self, rel_path: str, composite_name: str,
    ):
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / rel_path
        assert path.exists(), f"guarded pack file missing: {rel_path}"
        classes = _classes_in(path)
        # Extract the domain prefix from the composite name (e.g.,
        # "FloodDomainPack" → "Flood").
        if not composite_name.endswith("DomainPack"):
            pytest.fail(
                f"unexpected composite name {composite_name!r} — "
                f"expected '<Domain>DomainPack'"
            )
        domain_prefix = composite_name[: -len("DomainPack")]
        mixin_candidates = [
            f"{domain_prefix}{proto}Mixin" for proto in _SUB_PROTO_NAMES
        ]
        found = [m for m in mixin_candidates if m in classes]
        assert found, (
            f"{rel_path} declares NO sub-pack mixin classes. "
            f"Phase 6R-D-5/6 established the mixin decomposition "
            f"pattern (e.g. ``{domain_prefix}ReflectionMixin``, "
            f"``{domain_prefix}MemoryMixin``, ...). A future "
            f"contributor must keep at least one mixin to preserve "
            f"the sub-protocol composition; otherwise the type-"
            f"narrowing + cohesion benefits of 6R-D are lost. "
            f"Candidates checked: {mixin_candidates}"
        )

    @pytest.mark.parametrize(
        "rel_path, composite_name",
        _GUARDED_PACKS,
        ids=lambda v: v.rsplit("/", 1)[-1] if isinstance(v, str) and "/" in v else v,
    )
    def test_composite_inherits_from_at_least_one_mixin(
        self, rel_path: str, composite_name: str,
    ):
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / rel_path
        bases = _composite_bases(path, composite_name)
        assert bases, (
            f"composite class {composite_name!r} not found at top "
            f"level of {rel_path}"
        )
        domain_prefix = composite_name[: -len("DomainPack")]
        mixin_bases = [
            b for b in bases if b.endswith("Mixin")
            and b.startswith(domain_prefix)
        ]
        assert mixin_bases, (
            f"{composite_name} in {rel_path} inherits from "
            f"{bases} — none of which are Phase 6R-D-5/6 mixins. "
            f"Expected at least one base matching "
            f"``{domain_prefix}<SubProto>Mixin``. If you intentionally "
            f"collapsed the mixins back into the composite body, "
            f"the type-narrowing + cohesion benefits of 6R-D are "
            f"lost — re-evaluate the simplification."
        )

    @pytest.mark.parametrize(
        "rel_path, composite_name",
        _GUARDED_PACKS,
        ids=lambda v: v.rsplit("/", 1)[-1] if isinstance(v, str) and "/" in v else v,
    )
    def test_composite_inherits_from_default_domain_pack(
        self, rel_path: str, composite_name: str,
    ):
        """The composite must also inherit from ``DefaultDomainPack``
        as the final base so unoverridden Protocol methods fall
        through to the no-op default."""
        repo_root = Path(__file__).resolve().parents[2]
        path = repo_root / rel_path
        bases = _composite_bases(path, composite_name)
        assert "DefaultDomainPack" in bases, (
            f"{composite_name} in {rel_path} must inherit from "
            f"DefaultDomainPack (the fallback for un-overridden "
            f"DomainPack methods). Current bases: {bases}"
        )


class TestProductionPacksSatisfyAllSubProtocols:
    """End-to-end isinstance check: each production pack instance
    satisfies all 7 sub-protocols + the composite. Companion to the
    AST-level mixin-presence gates above — even if the AST gate
    passes, this confirms the resulting class hierarchy structurally
    satisfies the Protocols."""

    @pytest.fixture(autouse=True)
    def _register_packs(self):
        # Importing each example package registers its pack.
        import examples.governed_flood  # noqa: F401
        import examples.irrigation_abm  # noqa: F401
        import examples.vaccination_demo  # noqa: F401

    @pytest.mark.parametrize(
        "domain_name",
        ["flood", "irrigation", "vaccination"],
    )
    def test_each_production_pack_satisfies_all_7_sub_protocols(
        self, domain_name: str,
    ):
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

        pack = DomainPackRegistry.get(domain_name)
        assert pack is not None, f"{domain_name} pack not registered"
        for proto in (
            ReflectionPack, MemoryPack, SkillPack, EventPack,
            PerceptionPack, GovernancePack, SetupPack, DomainPack,
        ):
            assert isinstance(pack, proto), (
                f"{type(pack).__name__} does NOT satisfy {proto.__name__}"
            )
