"""Composed ("legacy") retrieval of HumanCentricMemoryEngine and the
MemoryProvider pass-through (2026-09-26): the window_size most recent
memories always, plus the top_k_significant long-term memories by decayed
importance (ties: earlier first), decayed importance <= 0.05 dropped.
Default provider behaviour (top_k=3, no pass-through) is unchanged.

Stores are built directly with fixed timestamps so consolidation (which is
stochastic) cannot decide the outcome."""
from types import SimpleNamespace

from broker.components.context.providers import MemoryProvider
from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine


def _engine(**kw):
    kw.setdefault("window_size", 5)
    kw.setdefault("top_k_significant", 2)
    return HumanCentricMemoryEngine(ranking_mode="legacy", seed=1, **kw)


def _item(content, ts, importance, **extra):
    return {"content": content, "timestamp": ts, "importance": importance,
            "emotion": "routine", "source": "personal", "consolidated": True, **extra}


def _agent(aid="A1", memory_config=None):
    return SimpleNamespace(id=aid, memory=[], memory_config=memory_config or {})


def _store(e, working, longterm):
    e.working["A1"] = working
    e.longterm["A1"] = longterm


def _standard(e, reflection_imp=0.95):
    working = [_item(f"line {i}", i, 0.3) for i in range(12)]
    longterm = [_item(f"line {i}", i, 0.3 + 0.01 * i) for i in range(12)]
    longterm[2] = _item("Consolidated Reflection 2", 2, reflection_imp, type="reflection")
    working[2] = dict(longterm[2])
    _store(e, working, longterm)


def test_five_recent_plus_two_significant():
    e = _engine()
    _standard(e)
    contents = [m["content"] for m in e.retrieve(_agent(), top_k=3)]
    assert len(contents) == 7
    assert contents[-5:] == [f"line {i}" for i in range(7, 12)]   # window, in order
    assert contents[0] == "Consolidated Reflection 2"               # highest decayed importance
    assert len(set(contents)) == 7                                   # no window item repeated


def test_reflection_lands_in_significant_slot_only_when_top_two():
    e = _engine()
    _standard(e, reflection_imp=0.2)
    contents = [m["content"] for m in e.retrieve(_agent())]
    assert "Consolidated Reflection 2" not in contents


def test_decayed_floor_drops_items():
    """An item above 0.05 when stored but decayed below it is dropped."""
    e = _engine(window_size=1, top_k_significant=2, decay_rate=0.1)
    working = [_item(f"w{i}", i, 0.1) for i in range(20)]
    longterm = [_item("old small", 0, 0.2), _item("old big", 1, 0.9)]
    _store(e, working, longterm)
    # age 20: "old small" 0.2 * exp(-0.095 * 20) = 0.030 < 0.05 (dropped);
    # age 19: "old big" 0.9 * exp(-0.095 * 19) = 0.148 (kept)
    contents = [m["content"] for m in e.retrieve(_agent())]
    assert "old small" not in contents and "old big" in contents
    assert contents[-1] == "w19"


def test_ties_keep_the_earlier_item_first():
    e = _engine(window_size=1, top_k_significant=1, decay_rate=0.0)
    _store(e, [_item("latest", 5, 0.1)],
           [_item("first", 1, 0.8), _item("second", 2, 0.8)])
    assert [m["content"] for m in e.retrieve(_agent())] == ["first", "latest"]


def test_per_call_overrides():
    e = _engine(window_size=2, top_k_significant=0)
    _standard(e)
    assert len(e.retrieve(_agent())) == 2
    assert len(e.retrieve(_agent(), window_size=5, top_k_significant=2)) == 7


def test_provider_default_is_flat_top3_and_passthrough_is_opt_in():
    calls = []

    class Spy:
        def __init__(self, mode):
            self.ranking_mode = mode

        def retrieve(self, agent, **kw):
            calls.append(kw)
            return []

    ctx = {}
    MemoryProvider(Spy("legacy")).provide("A1", {"A1": _agent(memory_config={"window_size": 5})}, ctx)
    assert calls[-1]["top_k"] == 3 and "window_size" not in calls[-1]
    cfg = {"composed_retrieval": True, "window_size": 5, "top_k_significant": 2, "retrieval_top_k": 7}
    MemoryProvider(Spy("legacy")).provide("A1", {"A1": _agent(memory_config=cfg)}, ctx)
    assert calls[-1]["top_k"] == 7
    assert calls[-1]["window_size"] == 5 and calls[-1]["top_k_significant"] == 2
    MemoryProvider(Spy("weighted")).provide("A1", {"A1": _agent(memory_config=cfg)}, ctx)
    assert "window_size" not in calls[-1] and "top_k_significant" not in calls[-1]


def test_provider_passthrough_reaches_engine_composition():
    e = _engine(window_size=2, top_k_significant=0)
    _standard(e)
    ctx = {}
    agent = _agent(memory_config={"composed_retrieval": True, "window_size": 5, "top_k_significant": 2})
    MemoryProvider(e).provide("A1", {"A1": agent}, ctx)
    assert len(ctx["memory"]) == 7
