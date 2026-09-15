"""Thread-safety of IrrigationEnvironment.execute_skill's magnitude sampling.

``broker/core/experiment_runner.py::_run_agents_parallel`` submits one agent
per task to a ``ThreadPoolExecutor`` under ``--workers N``; each task reaches
``SkillBrokerEngine.process_step`` → ``sim_engine.execute_skill``. If the
magnitude draw inside ``execute_skill`` comes from ONE environment-level
generator shared by every thread, *which agent consumes which draw* is decided
by thread scheduling, so the same seed produces a different agent→magnitude
assignment under ``--workers 4`` than under ``--workers 1`` — and a different
one again between two ``--workers 4`` runs.

These tests pin the property the fix restores: the magnitude an agent receives
is a function of ``(seed, year, agent_id, skill)`` only, never of how many
threads happened to be running or in what order they got scheduled.

They FAIL against the pre-fix shared-``self.rng`` code (2026-09-15: 13 of 16
agents diverged between workers-4 and workers-1 in one measured pair, 9 of 16
in another — the exact count moves with scheduling, the property does not).

This file lives in ``tests/`` rather than beside the domain because CI runs
``pytest tests/ broker/`` and ``pyproject.toml`` sets ``testpaths = ["tests"]``;
under ``examples/irrigation_abm/tests/`` the guard would be gated by nothing
but someone typing the path by hand.
"""
from __future__ import annotations

import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from broker.interfaces.skill_types import ApprovedSkill  # noqa: E402
from examples.irrigation_abm.irrigation_env import (  # noqa: E402
    IrrigationEnvironment,
    WaterSystemConfig,
)

N_AGENTS = 16
SEED = 42
# Non-zero, so the ε-exploration COIN FLIP is drawn and each call consumes two
# values rather than one — which is what makes the ordering bug visible in a
# second way. It is deliberately NOT enough to take the exploration arm: at
# these keys the smallest coin flip is 0.118, so `_build_env` always lands in
# the ordinary arm. `_build_exploring_env` below covers the arm itself.
EXPLORATION_RATE = 0.05
# Above every coin flip in the fixture, so the exploration arm always runs.
FORCED_EXPLORATION_RATE = 0.99


def _agent_id(i: int) -> str:
    return f"Agent_{i:03d}"


def _build_env() -> IrrigationEnvironment:
    """An env whose agents all take the v17 per-skill Gaussian branch."""
    env = IrrigationEnvironment(WaterSystemConfig(seed=SEED))
    for i in range(N_AGENTS):
        env._agents[_agent_id(i)] = {
            "basin": "upper_basin",
            "diversion": 80_000.0,
            "request": 80_000.0,
            "water_right": 100_000.0,
            "curtailment_ratio": 0.0,
            "at_allocation_cap": False,
            "has_efficient_system": False,
            "below_minimum_utilisation": False,
            "cluster": "aggressive",
            "persona_scale": 1.0,
            "skill_magnitude": {
                "increase_small": {"mu": 4.0, "sigma": 1.5, "min": 1.0, "max": 8.0},
            },
            "magnitude_default": 10.0,
            "magnitude_sigma": 0.0,
            "magnitude_min": 1.0,
            "magnitude_max": 30.0,
            "exploration_rate": EXPLORATION_RATE,
        }
    return env


def _build_legacy_env() -> IrrigationEnvironment:
    """An env whose agents take the v12 legacy per-persona fallback branch
    (no ``skill_magnitude`` block), which draws from its own code path."""
    env = _build_env()
    for agent in env._agents.values():
        agent["skill_magnitude"] = {}
        agent["magnitude_sigma"] = 3.5
    return env


def _build_exploring_env() -> IrrigationEnvironment:
    """An env whose agents always take the ε-exploration arm — the branch that
    widens sigma, clips to [0.5, 100.0] and sets ``is_exploration``. It draws
    the same two values from the same generator, so it must be just as
    order-independent, and without it that arm is dead in this file."""
    env = _build_env()
    for agent in env._agents.values():
        agent["exploration_rate"] = FORCED_EXPLORATION_RATE
    return env


def _explored(env: IrrigationEnvironment, agent_id: str) -> bool:
    result = env.execute_skill(_skill(agent_id))
    return bool(result.state_changes.get("is_exploration"))


def _skill(agent_id: str, name: str = "increase_small") -> ApprovedSkill:
    return ApprovedSkill(
        skill_name=name,
        agent_id=agent_id,
        approval_status="APPROVED",
        execution_mapping="sim.increase_small",
    )


def _run_sequential(env: IrrigationEnvironment, skill: str) -> dict:
    """The ``--workers 1`` shape: one agent at a time, fixed order."""
    out = {}
    for i in range(N_AGENTS):
        aid = _agent_id(i)
        result = env.execute_skill(_skill(aid, skill))
        out[aid] = result.state_changes.get("magnitude_pct_applied")
    return out


def _run_threaded(env: IrrigationEnvironment, skill: str, workers: int = 4) -> dict:
    """The ``--workers N`` shape: submission order fixed (as
    ``_run_agents_parallel`` submits), completion order left to the scheduler.

    A short bounded jitter before each call forces real interleaving rather
    than a pool that happens to drain almost sequentially. It uses
    ``SystemRandom`` so it cannot perturb any seeded stream under test.
    """
    jitter = random.SystemRandom()
    out = {}

    def work(aid: str):
        time.sleep(jitter.uniform(0, 0.003))
        result = env.execute_skill(_skill(aid, skill))
        return aid, result.state_changes.get("magnitude_pct_applied")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, _agent_id(i)) for i in range(N_AGENTS)]
        for fut in as_completed(futures):
            aid, value = fut.result()
            out[aid] = value
    return out


def _assert_same(label_a: str, a: dict, label_b: str, b: dict) -> None:
    assert set(a) == set(b)
    mismatched = {
        aid: (a[aid], b[aid])
        for aid in sorted(a)
        if a[aid] is None or b[aid] is None or abs(a[aid] - b[aid]) > 1e-12
    }
    assert not mismatched, (
        f"{len(mismatched)}/{N_AGENTS} agents got a different magnitude between "
        f"{label_a} and {label_b}; execute_skill's draw is still order-dependent. "
        f"First few: {dict(list(mismatched.items())[:4])}"
    )


@pytest.mark.parametrize(
    "builder, branch",
    [
        (_build_env, "v17 per-skill Gaussian"),
        (_build_legacy_env, "v12 legacy persona"),
        (_build_exploring_env, "v17 epsilon-exploration arm"),
    ],
)
def test_magnitude_is_independent_of_worker_count(builder, branch):
    """Sequential and two independent 4-thread passes must agree per agent."""
    sequential = _run_sequential(builder(), "increase_small")
    threaded_a = _run_threaded(builder(), "increase_small")
    threaded_b = _run_threaded(builder(), "increase_small")

    assert all(v is not None for v in sequential.values()), (
        f"{branch}: the magnitude branch did not run — the test fixture is wrong, "
        "not the code under test."
    )
    _assert_same("workers=1", sequential, "workers=4 (run A)", threaded_a)
    _assert_same("workers=4 (run A)", threaded_a, "workers=4 (run B)", threaded_b)


def test_exploration_arm_is_actually_reached_and_not_reached():
    """Pin which arm each fixture takes, so neither can quietly stop covering
    what its name claims.

    `_build_env`'s rate of 0.05 sits below every coin flip at these keys, so it
    always takes the ordinary arm; `_build_exploring_env`'s 0.99 sits above
    every one, so it always takes the exploration arm. If a future edit to the
    fixture's seed or agent ids moved a coin flip across either threshold, this
    test says so instead of silently hollowing out the parametrisation above.
    """
    ordinary = _build_env()
    assert not any(_explored(ordinary, _agent_id(i)) for i in range(N_AGENTS)), (
        "EXPLORATION_RATE is no longer below every coin flip — the "
        "'v17 per-skill Gaussian' case is now testing the exploration arm."
    )

    exploring = _build_exploring_env()
    assert all(_explored(exploring, _agent_id(i)) for i in range(N_AGENTS)), (
        "FORCED_EXPLORATION_RATE is no longer above every coin flip — the "
        "'v17 epsilon-exploration arm' case is not reaching that arm."
    )


def test_magnitude_is_reproducible_across_environments():
    """Two freshly-seeded environments must hand each agent the same value."""
    _assert_same(
        "env #1", _run_sequential(_build_env(), "increase_small"),
        "env #2", _run_sequential(_build_env(), "increase_small"),
    )


def test_magnitude_depends_on_agent_and_year_not_on_call_order():
    """The draw is keyed on (seed, year, agent, skill), so re-executing the
    same agent in the same year repeats the value, and advancing the year
    changes it — neither depends on how many other agents ran first."""
    env = _build_env()
    first = _run_sequential(env, "increase_small")
    repeat = _run_sequential(env, "increase_small")
    _assert_same("year 1 pass 1", first, "year 1 pass 2", repeat)

    env.advance_year()
    later = _run_sequential(env, "increase_small")
    changed = sum(1 for aid in first if abs(first[aid] - later[aid]) > 1e-12)
    assert changed == N_AGENTS, (
        "advancing the year must re-key every agent's draw; "
        f"only {changed}/{N_AGENTS} agents changed."
    )


def test_seeds_differ_across_agents_and_seeds():
    """Different agents in the same year, and the same agents under a
    different seed, must not collapse onto one shared value."""
    env = _build_env()
    values = _run_sequential(env, "increase_small")
    assert len(set(round(v, 9) for v in values.values())) > 1, (
        "every agent drew the same magnitude — the per-agent key is not varying."
    )

    other = IrrigationEnvironment(WaterSystemConfig(seed=SEED + 1))
    other._agents = _build_env()._agents
    other_values = _run_sequential(other, "increase_small")
    differing = sum(
        1 for aid in values if abs(values[aid] - other_values[aid]) > 1e-12
    )
    assert differing == N_AGENTS, (
        f"changing the config seed changed only {differing}/{N_AGENTS} agents' "
        "magnitudes; the draw is not seed-derived."
    )
