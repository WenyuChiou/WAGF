"""Tests for ReflectionEngine.compute_dynamic_importance.

Phase 6H Item 9: the legacy flood-keyword importance fallback
(``IMPORTANCE_PROFILES``) was removed. Importance now resolves via an
attached DomainReflectionAdapter → the first registered DomainPack that
exposes ``compute_importance`` → the generic ``base_importance``.
"""
import pytest

from broker.components.cognitive.reflection import (
    ReflectionEngine,
    AgentReflectionContext,
)


@pytest.fixture
def engine():
    return ReflectionEngine()


@pytest.fixture
def no_packs():
    """Run with an empty DomainPackRegistry, restored afterwards.

    Snapshots and restores the pack OBJECTS directly (not via re-import),
    so the teardown is correct regardless of import ordering — unlike a
    fixture that relies on `import` to re-register, which cannot re-fire
    once the module is in sys.modules."""
    from broker.domains.registry import DomainPackRegistry
    saved_packs = dict(DomainPackRegistry._packs)
    saved_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    yield
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._packs.update(saved_packs)
    DomainPackRegistry._missing_warned.clear()
    DomainPackRegistry._missing_warned.update(saved_warned)


class TestDynamicImportance:
    def test_no_domain_returns_base(self, engine, no_packs):
        """No adapter and no pack → the generic base score, rounded."""
        ctx = AgentReflectionContext(agent_id="H1", agent_type="household")
        assert engine.compute_dynamic_importance(ctx, base_importance=0.9) == 0.9
        assert engine.compute_dynamic_importance(ctx, base_importance=0.42) == 0.42

    def test_no_domain_score_clamped(self, engine, no_packs):
        """The base score is clamped to [0.0, 1.0]."""
        ctx = AgentReflectionContext(agent_id="H1", agent_type="household")
        assert engine.compute_dynamic_importance(ctx, base_importance=5.0) == 1.0
        assert engine.compute_dynamic_importance(ctx, base_importance=-1.0) == 0.0

    def test_no_flood_keyword_scoring(self, engine, no_packs):
        """A flood-flagged context no longer changes the score — the
        hardcoded flood-keyword block was removed (Phase 6H Item 9)."""
        flagged = AgentReflectionContext(
            agent_id="H1", agent_type="household", mg_status=True,
            recent_decision="elevate_house",
            custom_traits={"flood_count": 5},
        )
        plain = AgentReflectionContext(agent_id="H2", agent_type="household")
        assert (
            engine.compute_dynamic_importance(flagged, base_importance=0.5)
            == engine.compute_dynamic_importance(plain, base_importance=0.5)
            == 0.5
        )

    def test_registered_pack_delegates(self, engine, no_packs):
        """With a DomainPack registered, compute_dynamic_importance
        delegates to pack.compute_importance. (Generic single-pack
        registration — the FloodDomainPack delegation path is covered
        by test_domain_reflection_adapter.py.)"""
        from broker.domains.registry import DomainPackRegistry

        class _Pack:
            name = "t9"

            def compute_importance(self, context, base=0.9):
                return 0.42

        DomainPackRegistry.register("t9", _Pack())
        ctx = AgentReflectionContext(agent_id="H1", agent_type="household")
        assert engine.compute_dynamic_importance(ctx) == 0.42

    def test_pack_path_normalises_dataclass_context(self, engine, no_packs):
        """A dict-only pack.compute_importance receives a normalised dict
        even when the caller passes an AgentReflectionContext dataclass —
        the pack-scan path normalises like the adapter path. Was a latent
        AttributeError (IrrigationAdapter calls context.get(...))."""
        from broker.domains.registry import DomainPackRegistry

        class _DictPack:
            name = "dict_pack"

            def compute_importance(self, context, base=0.9):
                # .get() raises on a raw dataclass, works on a dict
                traits = context.get("custom_traits") or {}
                return traits.get("flood_count", 0) * 0.1

        DomainPackRegistry.register("dict_pack", _DictPack())
        ctx = AgentReflectionContext(
            agent_id="H1", agent_type="household",
            custom_traits={"flood_count": 3},
        )
        assert engine.compute_dynamic_importance(ctx) == 0.3
