"""Pins five WRR26-fidelity behaviours of `run_flood.py`'s runner against
synthetic fixtures (no LLM, no Ollama): insurance lapses only on
``do_nothing``; the neighbour-observation memory is two separate lines, not
one combined sentence; the neighbour-trust update in `post_year` reads the
community action rate as it stood BEFORE the year's decisions, not after;
each event line becomes its own `add_memory` call, not one `" | "`-joined
line; and the "Year t: You chose to X." own-action memory line is gone.

Every fixture is a plain object, not a real BaseAgent/ExperimentRunner --
`ResearchSimulation.execute_skill` and `FinalParityHook.pre_year`/
`post_year` only read the attributes named below, by duck typing (confirmed
by reading both methods in full before writing these tests).
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_flood as run_flood_mod  # noqa: E402

ResearchSimulation = run_flood_mod.ResearchSimulation
FinalParityHook = run_flood_mod.FinalParityHook


class _FakeApprovedSkill:
    def __init__(self, agent_id, skill_name):
        self.agent_id = agent_id
        self.skill_name = skill_name


class _FakeAgent:
    def __init__(self, agent_id, elevated=False, has_insurance=False,
                 relocated=False, flood_threshold=0.0):
        self.id = agent_id
        self.elevated = elevated
        self.has_insurance = has_insurance
        self.relocated = relocated
        self.flood_threshold = flood_threshold
        self.flood_history = []
        self.trust_in_insurance = 0.5
        self.trust_in_neighbors = 0.5
        self.is_active = True


class _RecordingMemoryEngine:
    def __init__(self):
        self.calls = []

    def add_memory(self, agent_id, content, metadata):
        self.calls.append((agent_id, content, metadata))

    def retrieve(self, agent, top_k=5):
        # post_year's logging-only retrieve (broker/INVARIANTS.md Invariant
        # 1: retrieve() returns List[Dict]); not under test here, so a
        # trivial empty result is enough to let post_year finish its loop.
        return []


def _make_sim(agents, flood_event=False, grant_available=False):
    sim = ResearchSimulation(agents=agents, governance_mode="strict")
    sim.flood_event = flood_event
    sim.grant_available = grant_available
    sim.current_year = 1
    return sim


def _make_hook(sim):
    runner = types.SimpleNamespace(memory_engine=_RecordingMemoryEngine())
    return FinalParityHook(sim=sim, runner=runner, reflection_engine=None, output_dir=None)


# ---------------------------------------------------------------------------
# 1. Insurance lapses only on do_nothing (flood design record row C2).
# ---------------------------------------------------------------------------

def test_insurance_lapses_only_on_do_nothing():
    agent = _FakeAgent("H0001", has_insurance=True)
    sim = _make_sim({"H0001": agent})

    result = sim.execute_skill(_FakeApprovedSkill("H0001", "do_nothing"))
    assert result.success is True
    assert result.state_changes.get("has_insurance") is False


def test_insurance_untouched_on_elevate():
    """WRR26's own code never assigns has_insurance on elevate -- an
    elevated household's existing policy must carry forward, not cancel."""
    agent = _FakeAgent("H0001", has_insurance=True)
    sim = _make_sim({"H0001": agent})

    result = sim.execute_skill(_FakeApprovedSkill("H0001", "elevate_house"))
    assert result.success is True
    assert "has_insurance" not in result.state_changes
    assert result.state_changes.get("elevated") is True


def test_insurance_untouched_on_relocate():
    agent = _FakeAgent("H0001", has_insurance=True)
    sim = _make_sim({"H0001": agent})

    result = sim.execute_skill(_FakeApprovedSkill("H0001", "relocate"))
    assert result.success is True
    assert "has_insurance" not in result.state_changes
    assert result.state_changes.get("relocated") is True


def test_insurance_set_true_on_buy_insurance():
    agent = _FakeAgent("H0001", has_insurance=False)
    sim = _make_sim({"H0001": agent})

    result = sim.execute_skill(_FakeApprovedSkill("H0001", "buy_insurance"))
    assert result.state_changes.get("has_insurance") is True


# ---------------------------------------------------------------------------
# 2. Two separate neighbour-observation memory lines (flood design record
#    row E3), not one combined sentence.
# ---------------------------------------------------------------------------

def test_two_separate_neighbour_lines_not_one_combined_sentence(monkeypatch):
    monkeypatch.setattr(run_flood_mod.random, "random", lambda: 1.0)  # never recall
    agents = {
        "H0001": _FakeAgent("H0001", elevated=False),
        "H0002": _FakeAgent("H0002", elevated=True),
        "H0003": _FakeAgent("H0003", relocated=True),
    }
    sim = _make_sim(agents, flood_event=False, grant_available=False)
    hook = _make_hook(sim)

    hook.pre_year(year=1, env=None, agents=None)

    lines = [content for agent_id, content, _ in hook.runner.memory_engine.calls
             if agent_id == "H0001"]
    neighbour_lines = [line for line in lines if "I observe" in line]
    assert len(neighbour_lines) == 2
    assert any("elevated homes" in line for line in neighbour_lines)
    assert any("relocated" in line for line in neighbour_lines)
    # Never the old combined sentence.
    assert not any("elevated and" in line for line in lines)


# ---------------------------------------------------------------------------
# 3. post_year's neighbour-trust update reads the community action rate as
#    it stood BEFORE this year's decisions (captured in pre_year), not
#    recomputed AFTER them (flood design record row E3, item 1).
# ---------------------------------------------------------------------------

def test_community_rate_used_in_post_year_is_the_pre_decision_one(monkeypatch):
    monkeypatch.setattr(run_flood_mod.random, "random", lambda: 1.0)
    agents = {
        "H0001": _FakeAgent("H0001", elevated=False),
        "H0002": _FakeAgent("H0002", elevated=False),
    }
    sim = _make_sim(agents, flood_event=False, grant_available=False)
    hook = _make_hook(sim)

    hook.pre_year(year=1, env=None, agents=None)
    # Pre-decision: nobody elevated/relocated yet -> rate 0.0.
    assert hook._pre_decision_community_rate == pytest.approx(0.0)

    # Simulate "this year's decisions": both agents now elevated, which
    # would make the AFTER-decision rate 1.0 if post_year recomputed it.
    for agent in agents.values():
        agent.elevated = True
        agent.flood_history.append(False)

    hook.post_year(year=1, agents=agents)

    # trust_in_neighbors only rises (+0.04) when community_action_rate >
    # 0.30; using the stale PRE-decision rate (0.0, not > 0.30) must leave
    # it on the "last_flood is False" branch (-0.01), not the high-rate
    # branch -- proving post_year used the captured pre-decision rate, not
    # a recompute off the now-fully-elevated `agents`.
    for agent in agents.values():
        assert agent.trust_in_neighbors == pytest.approx(0.49)


# ---------------------------------------------------------------------------
# 4. Each event line is its own add_memory call, not one " | "-joined line
#    per year (flood design record row F2).
# ---------------------------------------------------------------------------

def test_one_memory_item_per_event_line_not_one_joined_line(monkeypatch):
    monkeypatch.setattr(run_flood_mod.random, "random", lambda: 1.0)  # never recall
    agent = _FakeAgent("H0001", elevated=False)
    sim = _make_sim({"H0001": agent}, flood_event=False, grant_available=True)
    hook = _make_hook(sim)

    hook.pre_year(year=1, env=None, agents=None)

    calls = [c for c in hook.runner.memory_engine.calls if c[0] == "H0001"]
    # flood-outcome line (1) + grant line (1); num_others == 0 here (one
    # agent total), so the neighbour lines are skipped -- 2 calls expected.
    assert len(calls) == 2
    for _, content, _ in calls:
        assert " | " not in content, "each event must be its own memory item, never joined"


# ---------------------------------------------------------------------------
# 5. The "Year t: You chose to X." own-action memory line is gone (flood
#    design record row F3, not in WRR26).
# ---------------------------------------------------------------------------

def test_no_own_action_memory_line(monkeypatch):
    monkeypatch.setattr(run_flood_mod.random, "random", lambda: 1.0)
    agent = _FakeAgent("H0001", elevated=False)
    sim = _make_sim({"H0001": agent}, flood_event=False, grant_available=False)
    hook = _make_hook(sim)

    hook.pre_year(year=1, env=None, agents=None)

    lines = [content for agent_id, content, _ in hook.runner.memory_engine.calls
             if agent_id == "H0001"]
    assert not any("you chose to" in line.lower() for line in lines)
