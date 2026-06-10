"""G1 — the audit conservation invariant (2026-06-10 audit/validator review).

THE denominator guard at the RUNNER plane: pins that process_step is called
EXACTLY agents x steps times (and that failures surface as ABORTED results,
never silent drops). CSV-file-level conservation is covered by the
producer-roundtrip + e2e mock suites — this harness uses a scripted broker,
so it locks runner control flow, not file contents.
Case history: F1 (2026-04-07, exceptions dropped agents
from results), F4 (parse-abort rows), and the Cognitive-cache hit hole found
2026-06-10 (hits bypassed process_step -> no CSV row; cache is now opt-in
default-OFF, and THIS test forces a hit with the cache ON to pin the hole's
boundary — currently the hit path still writes no row, so the cache-ON case
asserts the documented deficit until the audit-row fix lands).

Also locks F4 itself: default OFF (runner.efficiency is None), opt-in via
ExperimentConfig/builder, and OFF-path produces byte-stable row counts with a
forced REJECTED + a forced exception in the mix.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from broker.components.governance.registry import SkillRegistry
from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner
from broker.interfaces.skill_types import (
    ApprovedSkill,
    ExecutionResult,
    SkillBrokerResult,
    SkillOutcome,
    SkillProposal,
)


class _Agent:
    def __init__(self, agent_id: str, agent_type: str = "agent"):
        self.id = agent_id
        self.agent_id = agent_id
        self.name = agent_id
        self.agent_type = agent_type
        self.is_active = True
        self.memory: list = []
        self.dynamic_state: Dict[str, Any] = {}

    def apply_delta(self, changes: Dict[str, Any]):
        self.dynamic_state.update(changes)


class _ScriptedBroker:
    """Stands in for SkillBrokerEngine: writes ONE audit row per process_step
    call (the real engine's contract) and follows a per-agent script:
    'approve' / 'reject' / 'raise'."""

    def __init__(self, script: Dict[str, str], audit_rows: List[Dict[str, Any]]):
        self.script = script
        self.audit_rows = audit_rows
        self.skill_registry = SkillRegistry()
        self.context_builder = MagicMock()
        self.context_builder.build.return_value = {"state": {}, "personal": {}}
        self.model_adapter = MagicMock()
        self.audit_writer = MagicMock()  # receives the F1 ABORTED sentinels
        self.log_prompt = False
        self.config = None
        self._model_name = ""

    def _run_validators(self, proposal, context):  # cache replay path
        return []

    def process_step(self, agent_id: str, step_id: int, run_id: str, seed: int,
                     llm_invoke: Any, agent_type: str, env_context: Dict) -> SkillBrokerResult:
        action = self.script.get(agent_id, "approve")
        if action == "raise":
            raise RuntimeError(f"forced failure for {agent_id}")
        # the engine's contract: every completed process_step emits a trace row
        self.audit_rows.append({"agent_id": agent_id, "step_id": step_id})
        outcome = SkillOutcome.APPROVED if action == "approve" else SkillOutcome.REJECTED
        proposal = SkillProposal(skill_name="act", agent_id=agent_id, reasoning={"r": 1},
                                 agent_type=agent_type)
        return SkillBrokerResult(
            outcome=outcome,
            skill_proposal=proposal,
            approved_skill=ApprovedSkill(skill_name="act", agent_id=agent_id,
                                         approval_status="APPROVED" if action == "approve" else "REJECTED"),
            execution_result=ExecutionResult(success=True, state_changes={}),
            validation_errors=[],
            retry_count=0,
        )


def _runner(tmp_path: Path, agents: Dict[str, _Agent], script: Dict[str, str],
            audit_rows: List[Dict[str, Any]], years: int = 2,
            enable_cache: bool = False, workers: int = 1) -> ExperimentRunner:
    cfg = ExperimentConfig(model="mock", num_years=years, output_dir=tmp_path,
                           seed=42, workers=workers,
                           enable_cognitive_cache=enable_cache)
    broker = _ScriptedBroker(script, audit_rows)
    runner = ExperimentRunner(broker=broker, sim_engine=None, agents=agents, config=cfg)
    # silence finalize-time manifest noise paths that need a real broker
    runner._finalize_experiment = lambda *a, **k: None
    return runner


def _aborted_sentinels(runner: ExperimentRunner) -> int:
    # the runner writes ABORTED sentinels through the broker's audit writer;
    # our scripted broker has no writer, so count via the F1 result objects
    return 0


# ---------------------------------------------------------------------------
# F4 flag semantics
# ---------------------------------------------------------------------------
def test_cache_default_off(tmp_path):
    runner = _runner(tmp_path, {"A": _Agent("A")}, {}, [])
    assert runner.efficiency is None  # F4: opt-in, default OFF


def test_cache_opt_in_constructs(tmp_path):
    runner = _runner(tmp_path, {"A": _Agent("A")}, {}, [], enable_cache=True)
    assert runner.efficiency is not None


def test_builder_exposes_with_cognitive_cache():
    from broker.core.experiment_builder import ExperimentBuilder

    b = ExperimentBuilder()
    assert b.with_cognitive_cache() is b
    assert b._enable_cognitive_cache is True


def test_cache_off_skips_early_context_build(tmp_path):
    """F4 bonus: with the cache off, the runner must NOT build context early
    (the double-context-build the architecture review flagged)."""
    rows: list = []
    agents = {"A": _Agent("A")}
    runner = _runner(tmp_path, agents, {"A": "approve"}, rows, years=1)
    runner.run()
    runner.broker.context_builder.build.assert_not_called()


# ---------------------------------------------------------------------------
# G1 — conservation: process_step rows == agents x years (cache OFF)
# ---------------------------------------------------------------------------
def test_conservation_rows_equal_agents_times_years(tmp_path):
    """approve + reject agents both produce exactly one row per year; a raising
    agent is excluded from broker rows but MUST surface as an ABORTED result
    (the F1 contract) so the step is never silently lost."""
    rows: list = []
    agents = {f"A{i}": _Agent(f"A{i}") for i in range(3)}
    script = {"A0": "approve", "A1": "reject", "A2": "raise"}
    runner = _runner(tmp_path, agents, script, rows, years=2)
    collected: list = []
    runner.hooks = {"post_step": lambda agent, result: collected.append((agent.id, result.outcome))}
    runner.run()

    # broker-side rows: 2 healthy agents x 2 years
    assert len(rows) == 4, rows
    # F1 contract: the raiser yields ABORTED results, one per year — visible, not dropped
    aborted = [a for a, o in collected if o == SkillOutcome.ABORTED]
    assert aborted == ["A2", "A2"]
    # total surfaced results == agents x years (conservation at the result plane)
    assert len(collected) == 3 * 2


def test_conservation_holds_in_parallel_mode(tmp_path):
    rows: list = []
    agents = {f"A{i}": _Agent(f"A{i}") for i in range(4)}
    script = {"A3": "raise"}
    runner = _runner(tmp_path, agents, script, rows, years=2, workers=3)
    collected: list = []
    runner.hooks = {"post_step": lambda agent, result: collected.append((agent.id, result.outcome))}
    runner.run()
    assert len(rows) == 3 * 2  # healthy agents x years
    assert len(collected) == 4 * 2  # conservation incl. ABORTED
    assert sum(1 for a, o in collected if o == SkillOutcome.ABORTED) == 2


# ---------------------------------------------------------------------------
# G1 boundary: the cache-ON hit hole, pinned explicitly
# ---------------------------------------------------------------------------
def test_cache_hit_skips_process_step_documented_deficit(tmp_path):
    """With the cache ON, only year 1 is a cache MISS; years 2-3 hit because
    compute_hash is stable over the constant scripted context (state {} /
    personal {} / no env key -> identical md5 every call) and hits bypass
    process_step entirely — the documented audit-row deficit that motivated
    default-OFF. This pins the boundary: rows == agents x 1. If the future
    audit-row-on-hit fix lands, UPDATE this test to assert full conservation
    instead."""
    rows: list = []
    agents = {"A": _Agent("A")}
    runner = _runner(tmp_path, agents, {"A": "approve"}, rows, years=3, enable_cache=True)
    runner.run()
    assert len(rows) == 1, (
        f"expected the year-1-only deficit (cache hit bypasses process_step); got {len(rows)} rows"
    )
