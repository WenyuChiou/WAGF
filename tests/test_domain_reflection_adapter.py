from __future__ import annotations

import itertools
import logging
from contextlib import contextmanager

from broker.components.cognitive.reflection import (
    AgentReflectionContext,
    ReflectionEngine,
)
from broker.domains.registry import DomainPackRegistry
from examples.governed_flood.adapters.flood_pack import FloodDomainPack


LEGACY_WARNING = "falling back to flood-domain hardcoded importance scoring"


@contextmanager
def isolated_domain_packs():
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        yield
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def _context(
    flood_count: int,
    mg_status: bool,
    recent_decision: str,
) -> AgentReflectionContext:
    return AgentReflectionContext(
        agent_id="H1",
        agent_type="household",
        mg_status=mg_status,
        recent_decision=recent_decision,
        custom_traits={"flood_count": flood_count},
    )


def _expected_flood_matrix(ctx: AgentReflectionContext, base: float) -> float:
    """The flood importance matrix — was the broker `compute_dynamic_importance`
    legacy fallback, removed in Phase 6H Item 9. Inlined here so the
    FloodDomainPack byte-identical guard survives the fallback's removal."""
    imp = base
    flood_count = ctx.custom_traits.get("flood_count", 0)
    if flood_count == 1:
        imp = 0.95
    elif flood_count > 2:
        imp = 0.75
    if ctx.mg_status:
        imp = max(imp, 0.90)
    if ctx.recent_decision in ("elevate_house", "relocate", "buy_insurance"):
        imp = max(imp, 0.80)
    if (not ctx.mg_status and flood_count == 0
            and ctx.recent_decision in ("do_nothing", "")):
        imp = min(imp, 0.60)
    return round(min(1.0, max(0.0, imp)), 2)


def test_flood_domain_pack_importance_matches_legacy_matrix():
    pack = FloodDomainPack()
    base = 0.9

    with isolated_domain_packs():
        for flood_count, mg_status, recent_decision in itertools.product(
            [0, 1, 2, 3],
            [True, False],
            ["do_nothing", "elevate_house", "relocate", "buy_insurance", ""],
        ):
            ctx = _context(flood_count, mg_status, recent_decision)

            assert pack.compute_importance(ctx, base) == _expected_flood_matrix(ctx, base)


def test_registered_flood_pack_delegates_without_legacy_warning(caplog):
    ctx = _context(1, False, "")
    pack = FloodDomainPack()

    with isolated_domain_packs():
        DomainPackRegistry.register("flood", pack)
        engine = ReflectionEngine()

        caplog.set_level(
            logging.WARNING,
            logger="broker.components.cognitive.reflection",
        )
        result = engine.compute_dynamic_importance(ctx)

    assert result == pack.compute_importance(ctx)
    assert LEGACY_WARNING not in caplog.text
    assert not getattr(engine, "_legacy_importance_warned", False)


def test_no_registered_pack_returns_base_score(caplog):
    """Phase 6H Item 9: with no registered DomainPack and no adapter,
    compute_dynamic_importance returns the generic base score — the
    legacy flood-keyword fallback and its one-time warning were removed."""
    ctx = _context(1, False, "")

    with isolated_domain_packs():
        engine = ReflectionEngine()
        caplog.set_level(
            logging.WARNING,
            logger="broker.components.cognitive.reflection",
        )
        result = engine.compute_dynamic_importance(ctx, base_importance=0.7)

    assert result == 0.7
    assert LEGACY_WARNING not in caplog.text


def test_registered_generic_pack_compute_importance_is_used():
    class RadTestPack:
        name = "rad_test"

        def compute_importance(self, context, base=0.9):
            return 0.42

    with isolated_domain_packs():
        DomainPackRegistry.register("rad_test", RadTestPack())

        result = ReflectionEngine().compute_dynamic_importance(
            _context(3, False, "do_nothing")
        )

    assert result == 0.42


def test_compute_importance_reads_flood_count_from_custom_traits():
    """Phase 6H Item 9 L6: flood_count is routed through custom_traits,
    not a top-level dataclass field. compute_dynamic_importance asdict()s
    the context before dispatch, so FloodAdapter must read flood_count
    from the nested custom_traits dict -- regression guard for the L6
    'flood_count seen as 0' bug."""
    from examples.governed_flood.adapters.flood_adapter import FloodAdapter

    engine = ReflectionEngine(adapter=FloodAdapter())
    # flood_count lives in custom_traits only; the dataclass field is 0.
    ctx = AgentReflectionContext(
        agent_id="H1", agent_type="household",
        custom_traits={"flood_count": 1},
    )
    # flood_count == 1 -> the first_flood profile (0.95), not the base.
    assert engine.compute_dynamic_importance(ctx) == 0.95
