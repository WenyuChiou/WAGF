"""Tests for ReflectionOrchestrator + tick_label threading (Wave 3 item 3-5).

Locks: (1) the collect->batch->prompt->parse->store loop works end-to-end with
the REAL ReflectionEngine primitives (fake LLM, no GPU); (2) eligibility filter
+ batch partitioning + fail-soft batch errors; (3) tick_label default "Year"
keeps every prompt builder BYTE-IDENTICAL to pre-3-5 while "Day" renders
sub-annual vocabulary; (4) with_reflection_engine gives the runner the
reflection seat (the previously-dead Invariant-6 hasattr branch).
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from broker.components.cognitive.reflection import ReflectionEngine
from broker.components.cognitive.reflection_orchestrator import ReflectionOrchestrator


class _Agent:
    def __init__(self, agent_id: str, relocated: bool = False):
        self.id = agent_id
        self.agent_id = agent_id
        self.relocated = relocated
        self.memory: list = []


class _FakeMemoryEngine:
    """Minimal engine: canned retrieval + recorded writes."""

    def __init__(self, mems_by_agent: Dict[str, list]):
        self._mems = mems_by_agent
        self.written: list = []

    def retrieve(self, agent: Any, top_k: int = 10, **kw):
        return self._mems.get(agent.id, [])

    def add_memory(self, agent_id: str, content: str, metadata=None):
        self.written.append((agent_id, content, metadata))


def _fake_llm_factory(calls: list):
    """LLM that answers the engine's batch format: 'AGENT <id>: <insight>'."""

    def fake_llm(prompt: str) -> str:
        calls.append(prompt)
        # answer for every agent id mentioned in the prompt's Agent Data
        lines = []
        for token in ("H1", "H2", "H3", "H4", "H5"):
            if token in prompt:
                lines.append(f"AGENT {token}: Learned to prepare earlier.")
        return "\n".join(lines)

    return fake_llm


def _orchestrator(agents_mems, calls, **kw):
    engine = ReflectionEngine(reflection_interval=1)
    mem = _FakeMemoryEngine(agents_mems)
    return ReflectionOrchestrator(
        reflection_engine=engine,
        memory_engine=mem,
        llm_invoke=_fake_llm_factory(calls),
        **kw,
    ), mem


def test_end_to_end_insights_stored_and_written_back():
    agents = {f"H{i}": _Agent(f"H{i}") for i in (1, 2, 3)}
    mems = {a: [f"{a} memory one", f"{a} memory two"] for a in agents}
    calls: list = []
    orch, mem = _orchestrator(mems, calls, batch_size=10)
    stored = orch.run_period(1, agents)
    assert stored == 3
    assert {w[0] for w in mem.written} == {"H1", "H2", "H3"}
    assert all(w[1].startswith("Consolidated Reflection:") for w in mem.written)
    assert all(w[2]["emotion"] == "major" for w in mem.written)
    assert len(calls) == 1  # one batch


def test_batching_and_eligibility():
    agents = {f"H{i}": _Agent(f"H{i}", relocated=(i == 5)) for i in (1, 2, 3, 4, 5)}
    mems = {a: [f"{a} memory"] for a in agents}
    calls: list = []
    orch, _ = _orchestrator(
        mems, calls, batch_size=2,
        eligible=lambda agent: not agent.relocated,
    )
    stored = orch.run_period(2, agents)
    assert stored == 4          # H5 relocated -> skipped
    assert len(calls) == 2      # 4 candidates / batch_size 2


def test_agents_without_memories_are_skipped():
    agents = {"H1": _Agent("H1"), "H2": _Agent("H2")}
    calls: list = []
    orch, mem = _orchestrator({"H1": ["only H1 remembers"]}, calls)
    stored = orch.run_period(1, agents)
    assert stored == 1
    assert {w[0] for w in mem.written} == {"H1"}


def test_batch_failure_is_fail_soft():
    """One exploding batch must not void the other batches (legacy posture)."""
    agents = {f"H{i}": _Agent(f"H{i}") for i in (1, 2)}
    mems = {a: [f"{a} memory"] for a in agents}
    n = {"calls": 0}

    def exploding_llm(prompt):
        n["calls"] += 1
        if n["calls"] == 1:
            raise RuntimeError("LLM down")
        who = "H1" if "H1" in prompt else "H2"
        return f"AGENT {who}: Recovered."

    engine = ReflectionEngine(reflection_interval=1)
    mem = _FakeMemoryEngine(mems)
    orch = ReflectionOrchestrator(engine, mem, exploding_llm, batch_size=1)
    stored = orch.run_period(1, agents)
    assert stored == 1  # second batch survived the first one's failure


def test_cadence_respected():
    engine = ReflectionEngine(reflection_interval=2)  # reflect every 2 periods
    mem = _FakeMemoryEngine({"H1": ["m"]})
    orch = ReflectionOrchestrator(engine, mem, lambda p: "AGENT H1: x")
    assert orch.run_period(1, {"H1": _Agent("H1")}) == 0  # off-cadence
    assert orch.run_period(2, {"H1": _Agent("H1")}) == 1


# ---------------------------------------------------------------------------
# tick_label byte-identity (the 3-5 byte-safety contract)
# ---------------------------------------------------------------------------
def test_tick_label_default_is_byte_identical_year():
    engine = ReflectionEngine(reflection_interval=1)
    batch = [{"agent_id": "H1", "memories": ["m1"]}]
    default = engine.generate_batch_reflection_prompt(batch, 3)
    explicit = engine.generate_batch_reflection_prompt(batch, 3, tick_label="Year")
    assert default == explicit
    assert "(Year 3)" in default
    solo = engine.generate_reflection_prompt("H1", ["m1"], 3)
    assert "past 1 year(s)" in solo


def test_tick_label_day_renders_subannual_vocabulary():
    engine = ReflectionEngine(reflection_interval=1)
    batch = [{"agent_id": "H1", "memories": ["m1"]}]
    p = engine.generate_batch_reflection_prompt(batch, 47, tick_label="Day")
    assert "(Day 47)" in p and "Year" not in p
    solo = engine.generate_reflection_prompt("H1", ["m1"], 47, tick_label="Day")
    assert "past 1 day(s)" in solo


def test_orchestrator_threads_tick_label_into_prompts():
    agents = {"H1": _Agent("H1")}
    calls: list = []
    orch, _ = _orchestrator({"H1": ["m"]}, calls, tick_label="Day")
    orch.run_period(7, agents)
    assert len(calls) == 1 and "(Day 7)" in calls[0]


# ---------------------------------------------------------------------------
# Builder reflection seat (with_reflection_engine)
# ---------------------------------------------------------------------------
def test_builder_with_reflection_engine_sets_runner_seat():
    from broker.core.experiment_builder import ExperimentBuilder

    engine = ReflectionEngine(reflection_interval=1)
    b = ExperimentBuilder().with_reflection_engine(engine)
    assert b.reflection_engine is engine
    # fluent
    assert b.with_reflection_engine(engine) is b
