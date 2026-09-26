"""HumanCentricMemoryEngine ``reserve_types``: a reserved retrieval slot for a
memory type (weighted mode). Default None must leave retrieval unchanged."""
from types import SimpleNamespace

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine


def _engine(**kw):
    return HumanCentricMemoryEngine(
        ranking_mode="weighted", W_recency=0.3, W_importance=0.5, W_context=0.2,
        consolidation_prob=0.0, seed=1, **kw,
    )


def _fill(engine, agent_id="A1", years=30):
    """Per year: one high-importance outcome line (0.90) and one reflection
    (0.55), the shape that pushed reflections out of the top 3."""
    for y in range(1, years + 1):
        engine.add_memory(agent_id, f"Year {y}: outcome line", {"importance": 0.90, "type": "outcome"})
        engine.add_memory(agent_id, f"Consolidated Reflection {y}", {"importance": 0.55, "type": "reflection"})


def _agent(agent_id="A1"):
    return SimpleNamespace(id=agent_id, memory=[])


def test_default_none_matches_unreserved_ranking():
    a, b = _engine(), _engine(reserve_types=None)
    _fill(a)
    _fill(b)
    assert a.retrieve(_agent(), top_k=3) == b.retrieve(_agent(), top_k=3)
    assert all("reserved" not in m for m in a.retrieve(_agent(), top_k=3))


def test_reserve_on_equals_off_when_no_swap_is_needed():
    """With the option ON but nothing to swap (reflection already in the
    top-k, or no memory of that type), the result equals the option OFF."""
    for fill in ("reflection_on_top", "no_reflection"):
        off, on = _engine(), _engine(reserve_types={"reflection": 1})
        for e in (off, on):
            for i in range(6):
                e.add_memory("A1", f"line {i}", {"importance": 0.5, "type": "outcome"})
            if fill == "reflection_on_top":
                e.add_memory("A1", "Consolidated Reflection x", {"importance": 0.99, "type": "reflection"})
        assert off.retrieve(_agent(), top_k=3) == on.retrieve(_agent(), top_k=3)


def test_string_and_multiple_types_and_large_top_k():
    assert HumanCentricMemoryEngine._normalise_reserve_types("reflection") == {"reflection": 1}
    e = _engine(reserve_types={"reflection": 1, "plan": 1})
    _fill(e)
    e.add_memory("A1", "plan one", {"importance": 0.2, "type": "plan"})
    e.add_memory("A1", "late line", {"importance": 0.9, "type": "outcome"})
    top = e.retrieve(_agent(), top_k=3)
    kinds = sorted(m["content"].split()[0] for m in top)
    assert kinds == ["Consolidated", "Year", "plan"] or kinds == ["Consolidated", "late", "plan"]
    assert sum(1 for m in top if m.get("reserved")) >= 1
    small = _engine(reserve_types={"reflection": 1})
    small.add_memory("A1", "a", {"importance": 0.9, "type": "outcome"})
    small.add_memory("A1", "b", {"importance": 0.1, "type": "reflection"})
    assert all("reserved" not in m for m in small.retrieve(_agent(), top_k=10))


def test_legacy_mode_ignores_reserve_types():
    a = HumanCentricMemoryEngine(ranking_mode="legacy", consolidation_prob=0.0, seed=1)
    b = HumanCentricMemoryEngine(ranking_mode="legacy", consolidation_prob=0.0, seed=1,
                                 reserve_types={"reflection": 1})
    for e in (a, b):
        _fill(e, years=5)
    assert a.retrieve(_agent(), top_k=3) == b.retrieve(_agent(), top_k=3)


def test_without_reserve_reflection_is_crowded_out():
    """Reproduces the audit's H1: no reflection in the top 3."""
    e = _engine()
    _fill(e)
    top = e.retrieve(_agent(), top_k=3)
    assert not any(m["content"].startswith("Consolidated Reflection") for m in top)


def test_reserve_keeps_exactly_one_reflection_in_top3():
    for spec in ({"reflection": 1}, ["reflection"]):
        e = _engine(reserve_types=spec)
        _fill(e)
        top = e.retrieve(_agent(), top_k=3)
        refl = [m for m in top if m["content"].startswith("Consolidated Reflection")]
        assert len(top) == 3
        assert len(refl) == 1
        assert refl[0]["reserved"] is True
        # the newest reflection is the best-scoring one of its type
        assert refl[0]["content"] == "Consolidated Reflection 30"
        scores = [m["final_score"] for m in top]
        assert scores == sorted(scores, reverse=True)


def test_reserve_is_noop_when_type_already_selected_or_absent():
    e = _engine(reserve_types={"reflection": 1})
    e.add_memory("A1", "Consolidated Reflection 1", {"importance": 0.99, "type": "reflection"})
    e.add_memory("A1", "line", {"importance": 0.1, "type": "outcome"})
    top = e.retrieve(_agent(), top_k=3)
    assert all("reserved" not in m for m in top)

    e2 = _engine(reserve_types={"reflection": 1})
    for i in range(5):
        e2.add_memory("A1", f"line {i}", {"importance": 0.9, "type": "outcome"})
    top2 = e2.retrieve(_agent(), top_k=3)
    assert len(top2) == 3 and all("reserved" not in m for m in top2)
