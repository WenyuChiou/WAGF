"""feat/v3-parallel-determinism: ExperimentRunner._run_agents_parallel must
return results in SUBMISSION order, not thread-completion order.

run()'s apply loop (_apply_state_changes + the post_step hook, per agent)
reads this return value in list order; a shared-state read or write inside
that loop (e.g. HumanCentricMemoryEngine._add_memory_internal's one shared
random.Random draw on consolidation) is deterministic across worker counts
only if that order matches --workers 1's sequential order, regardless of
which worker thread happens to finish first. This test stubs process_step
with per-agent sleeps chosen so completion order is the exact reverse of
submission order, then asserts the returned order is still submission order.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

from broker.core.experiment_runner import ExperimentRunner
from broker.interfaces.skill_types import SkillBrokerResult, SkillOutcome


def _make_agent(agent_id: str, agent_type: str = "household"):
    agent = MagicMock()
    agent.id = agent_id
    agent.agent_type = agent_type
    return agent


def _make_runner(delays_by_agent_id: dict, workers: int, raise_for: str | None = None):
    """A minimal ExperimentRunner (``ExperimentRunner.__new__``, the same
    pattern ``broker/tests/test_silent_failure_fixes.py``'s
    ``TestF4ParallelFailedAgentProducesAuditRow`` and
    ``broker/tests/test_llm_safeguard.py`` already use to exercise
    ``_run_agents_parallel``) whose ``process_step`` sleeps
    ``delays_by_agent_id[agent_id]`` seconds before returning, so completion
    order can be forced independently of submission order. ``raise_for``,
    when given, makes that ONE agent_id's call raise instead of sleeping
    (no sleep: the exception should surface as fast as possible, the worst
    case for landing anywhere other than its submission position).
    """
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.broker = MagicMock()
    runner.broker.audit_writer = MagicMock()
    runner.step_counter = 0
    runner.config = MagicMock()
    runner.config.seed = 42
    runner.config.workers = workers
    runner._model_name = "test_model"
    runner.efficiency = None  # cache disabled: hash/get/put are skipped
    runner.broker.context_builder = MagicMock()
    runner.broker.context_builder.build = MagicMock(return_value={"state": {}})
    runner.get_llm_invoke = MagicMock(return_value=lambda *a, **kw: None)

    def _process_step(agent_id, **kwargs):
        if agent_id == raise_for:
            raise RuntimeError("simulated parallel-path crash")
        time.sleep(delays_by_agent_id.get(agent_id, 0.0))
        return SkillBrokerResult(
            outcome=SkillOutcome.APPROVED,
            skill_proposal=None,
            approved_skill=None,
            execution_result=None,
        )

    runner.broker.process_step = MagicMock(side_effect=_process_step)
    return runner


def test_run_agents_parallel_returns_submission_order_despite_reversed_completion():
    # Submitted A0..A4; A0 sleeps longest and A4 does not sleep at all, so
    # completion order (pre-fix) is the exact reverse: A4, A3, A2, A1, A0.
    # workers=5 so all five start at once (no ThreadPoolExecutor queueing),
    # which keeps the reversal unambiguous.
    agent_ids = [f"A{i}" for i in range(5)]
    agents = [_make_agent(aid) for aid in agent_ids]
    delays = {aid: 0.08 * (len(agent_ids) - i) for i, aid in enumerate(agent_ids)}
    runner = _make_runner(delays, workers=5)

    results = runner._run_agents_parallel(
        agents, run_id="run_reverse", llm_invoke=lambda *a, **kw: None,
        env={"current_year": 1},
    )

    assert [agent.id for agent, _ in results] == agent_ids, (
        "results must be in SUBMISSION order regardless of which thread "
        "finished first"
    )
    assert all(r.outcome == SkillOutcome.APPROVED for _, r in results)


def test_run_agents_parallel_aborted_result_lands_at_submission_position():
    """An agent whose process_step raises must still land at its
    SUBMISSION index in the returned list, as an ABORTED SkillBrokerResult,
    not wherever as_completed() happened to observe the exception. F4
    (broker/tests/test_silent_failure_fixes.py) already proved the row is
    never DROPPED; this proves it is not MISPLACED either."""
    agent_ids = [f"C{i}" for i in range(5)]
    agents = [_make_agent(aid) for aid in agent_ids]
    # C2 raises immediately (no sleep); C0/C1/C3/C4 sleep in a pattern
    # that completes them in reverse-ish order, so pre-fix this would land
    # C2's ABORTED row wherever as_completed() happened to observe the
    # exception, not at submission index 2.
    delays = {"C0": 0.16, "C1": 0.12, "C3": 0.08, "C4": 0.04}
    runner = _make_runner(delays, workers=5, raise_for="C2")

    results = runner._run_agents_parallel(
        agents, run_id="run_abort", llm_invoke=lambda *a, **kw: None,
        env={"current_year": 1},
    )

    assert [agent.id for agent, _ in results] == agent_ids, (
        "an ABORTED result must still land at its agent's SUBMISSION "
        "position, not wherever as_completed() observed the exception"
    )
    result_by_id = {agent.id: result for agent, result in results}
    assert result_by_id["C2"].outcome == SkillOutcome.ABORTED
    assert all(
        result_by_id[aid].outcome == SkillOutcome.APPROVED
        for aid in agent_ids if aid != "C2"
    )


def test_run_agents_parallel_workers_1_is_already_submission_order():
    """Sanity companion: at workers=1 there is no completion-order question
    at all (process_agent calls are made one at a time by the single
    worker), so this must hold trivially both before and after the fix."""
    agent_ids = [f"B{i}" for i in range(4)]
    agents = [_make_agent(aid) for aid in agent_ids]
    runner = _make_runner({}, workers=1)

    results = runner._run_agents_parallel(
        agents, run_id="run_single", llm_invoke=lambda *a, **kw: None,
        env={"current_year": 1},
    )

    assert [agent.id for agent, _ in results] == agent_ids
