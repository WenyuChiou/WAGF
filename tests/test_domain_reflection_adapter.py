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
        flood_count=flood_count,
        mg_status=mg_status,
        recent_decision=recent_decision,
    )


def _legacy_importance(ctx: AgentReflectionContext, base: float) -> float:
    engine = ReflectionEngine()
    engine._legacy_importance_warned = True
    return engine.compute_dynamic_importance(ctx, base_importance=base)


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

            assert pack.compute_importance(ctx, base) == _legacy_importance(ctx, base)


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


def test_no_registered_pack_uses_legacy_fallback_and_warns_once(caplog):
    ctx = _context(1, False, "")

    with isolated_domain_packs():
        engine = ReflectionEngine()
        caplog.set_level(
            logging.WARNING,
            logger="broker.components.cognitive.reflection",
        )

        first = engine.compute_dynamic_importance(ctx)
        second = engine.compute_dynamic_importance(ctx)

    assert first == 0.95
    assert second == 0.95
    assert caplog.text.count(LEGACY_WARNING) == 1


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
