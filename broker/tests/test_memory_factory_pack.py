"""Tests for MemoryPack hooks -> create_memory_engine (Wave 3 item 3-4).

Closes the declaration-consumption gap from the 2026-06-09 architecture review
(memory-cognition P1): retrieval_weights/emotional_keywords were declared on
the DomainPack Protocol with ZERO factory consumers. Locks:
(1) pack hooks reach the engine as DEFAULTS; (2) explicit config wins over the
pack; (3) NO pack -> byte-identical pre-3-4 construction; (4) the registry
factory no longer swallows engine-supported kwargs (the silent-swallow bug);
(5) window engine is unaffected; (6) broken pack hooks degrade, never raise.
"""
from __future__ import annotations

import pytest

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from broker.components.memory.engines.window import WindowMemoryEngine
from broker.components.memory.factory import _pack_memory_defaults, create_memory_engine


class _DroughtPack:
    """Minimal MemoryPack-shaped stand-in for a new water domain."""

    def retrieval_weights(self):
        return {"W_recency": 0.40, "W_importance": 0.40, "W_context": 0.20}

    def emotional_keywords(self):
        # pack shape: {keyword: emotion} (vaccination_pack.py idiom)
        return {
            "allocation cut": "critical",
            "curtailment": "critical",
            "surplus": "positive",
        }


def test_pack_defaults_reach_engine():
    eng = create_memory_engine("humancentric", pack=_DroughtPack())
    assert isinstance(eng, HumanCentricMemoryEngine)
    assert eng.W_recency == pytest.approx(0.40)
    assert eng.W_importance == pytest.approx(0.40)
    assert eng.W_context == pytest.approx(0.20)
    # inverted into the engine's {emotion: [keywords]} lexicon shape
    assert sorted(eng.emotion_keywords["critical"]) == ["allocation cut", "curtailment"]
    assert eng.emotion_keywords["positive"] == ["surplus"]


def test_explicit_config_wins_over_pack():
    eng = create_memory_engine(
        "humancentric", config={"W_recency": 0.9}, pack=_DroughtPack())
    assert eng.W_recency == pytest.approx(0.9)   # YAML tuning wins
    assert eng.W_importance == pytest.approx(0.40)  # rest still pack-supplied


def test_no_pack_reproduces_pre_change_defaults():
    """The byte-identity guarantee: omitting pack -> the exact pre-3-4 engine
    (default weights 0.3/0.5/0.2 + the generic emotion bank)."""
    eng = create_memory_engine("humancentric")
    assert eng.W_recency == pytest.approx(0.3)
    assert eng.W_importance == pytest.approx(0.5)
    assert eng.W_context == pytest.approx(0.2)
    assert "failure" in eng.emotion_keywords["critical"]  # generic bank intact


def test_factory_kwargs_no_longer_swallowed():
    """Regression lock for the silent-swallow bug: an engine-supported kwarg
    passed through create_memory_engine must reach the engine."""
    eng = create_memory_engine("humancentric", W_recency=0.7, ranking_mode="weighted")
    assert eng.W_recency == pytest.approx(0.7)
    assert eng.ranking_mode == "weighted"


def test_unknown_kwargs_still_tolerated():
    eng = create_memory_engine("humancentric", some_future_knob=1)  # ignored, no raise
    assert isinstance(eng, HumanCentricMemoryEngine)


def test_window_engine_unaffected_by_pack():
    eng = create_memory_engine("window", config={"window_size": 4}, pack=_DroughtPack())
    assert isinstance(eng, WindowMemoryEngine)
    assert eng.window_size == 4


def test_partial_retrieval_weights_not_adopted():
    """A pack declaring only SOME weight keys is a pack bug — adopt none
    rather than mixing a partial declaration with engine defaults."""
    class PartialPack(_DroughtPack):
        def retrieval_weights(self):
            return {"W_recency": 0.9}  # missing the other two

    eng = create_memory_engine("humancentric", pack=PartialPack())
    assert eng.W_recency == pytest.approx(0.3)  # engine default, not 0.9


def test_broken_pack_hooks_degrade_not_raise():
    class BrokenPack:
        def retrieval_weights(self):
            raise RuntimeError("boom")

        def emotional_keywords(self):
            raise RuntimeError("boom")

    eng = create_memory_engine("humancentric", pack=BrokenPack())
    assert eng.W_recency == pytest.approx(0.3)  # degraded to defaults


def test_pack_defaults_helper_shapes():
    d = _pack_memory_defaults(_DroughtPack())
    assert set(d) == {"W_recency", "W_importance", "W_context", "emotion_keywords"}
