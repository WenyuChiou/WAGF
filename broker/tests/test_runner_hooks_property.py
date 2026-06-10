"""Regression tests for ExperimentRunner.hooks assignment diagnostics."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

from broker.agents import AgentConfig, BaseAgent
from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner


def _make_runner(tmp_path):
    broker = MagicMock()
    broker.log_prompt = False
    return ExperimentRunner(
        broker=broker,
        sim_engine=MagicMock(),
        agents={
            "agent_1": BaseAgent(
                AgentConfig(
                    name="agent_1",
                    agent_type="agent",
                    state_params=[],
                    objectives=[],
                    constraints=[],
                    skills=[],
                )
            )
        },
        config=ExperimentConfig(output_dir=tmp_path),
    )


def test_wholesale_hook_assignment_warns_on_wrong_signature(tmp_path, caplog):
    runner = _make_runner(tmp_path)

    def invalid_pre_year(year):
        return None

    with caplog.at_level(logging.WARNING):
        runner.hooks = {"pre_year": invalid_pre_year}

    assert "Hook 'pre_year' does not match" in caplog.text
    assert runner.hooks["pre_year"] is invalid_pre_year


def test_valid_wholesale_hook_assignment_does_not_warn(tmp_path, caplog):
    runner = _make_runner(tmp_path)

    def valid_pre_year(year, env, agents):
        return None

    with caplog.at_level(logging.WARNING):
        runner.hooks = {"pre_year": valid_pre_year}

    assert "Hook 'pre_year' does not match" not in caplog.text
    assert runner.hooks["pre_year"] is valid_pre_year


def test_dict_update_path_remains_unvalidated_and_non_breaking(tmp_path):
    runner = _make_runner(tmp_path)

    def invalid_pre_year(year):
        return None

    runner.hooks.update({"pre_year": invalid_pre_year})
    assert runner.hooks["pre_year"] is invalid_pre_year


# ---------------------------------------------------------------------------
# F7 hook hardening (2026-06-10 audit review)
# ---------------------------------------------------------------------------

def test_unknown_hook_name_raises(tmp_path):
    """F7a: a misspelled hook name must RAISE at assignment, never silently
    register-and-never-fire (the silent-feature-loss class)."""
    import pytest as _pytest

    runner = _make_runner(tmp_path)
    with _pytest.raises(ValueError, match="Unknown lifecycle hook"):
        runner.hooks = {"post_year_end": lambda step, agents: None}  # typo


def test_known_hooks_still_accepted(tmp_path):
    runner = _make_runner(tmp_path)
    runner.hooks = {"pre_year": lambda step, env, agents: None,
                    "post_step_end": lambda step, agents: None}
    assert set(runner.hooks) == {"pre_year", "post_step_end"}


def test_builder_with_lifecycle_hooks_validates_names():
    """F7c (review C1): the PRIMARY registration API — the builder's
    with_lifecycle_hooks — must route through the same name guard as the
    runner's hooks setter; otherwise the most natural call path stays a
    silent-feature-loss hole."""
    import pytest as _pytest

    from broker.core.experiment_builder import ExperimentBuilder

    b = ExperimentBuilder()
    with _pytest.raises(ValueError, match="Unknown lifecycle hook"):
        b.with_lifecycle_hooks(post_year_end=lambda step, agents: None)  # typo
    # canonical names still chain fluently
    assert b.with_lifecycle_hooks(
        pre_year=lambda y, env, agents: None) is b
    assert "pre_year" in b.hooks


def test_raising_hook_logs_name_and_reraises(tmp_path, caplog):
    """F7b: a raising hook must surface WITH ITS NAME + year in the log and
    re-raise (no silent swallow; finalize is covered by run()'s finally)."""
    import logging

    import pytest as _pytest

    runner = _make_runner(tmp_path)
    runner.hooks = {"pre_year": lambda step, env, agents: (_ for _ in ()).throw(RuntimeError("boom"))}
    with caplog.at_level(logging.ERROR):
        with _pytest.raises(RuntimeError, match="boom"):
            runner.run()
    assert any("hook 'pre_year'" in r.message for r in caplog.records)


def test_partition_unmatched_agent_types_warn(tmp_path, caplog):
    """F7c: phase_order typos surface as a loud warning naming the types."""
    import logging

    runner = _make_runner(tmp_path)
    runner.config.phase_order = [["goverment"]]  # deliberate typo
    with caplog.at_level(logging.WARNING):
        phases = runner._partition_by_phase(list(runner.agents.values()))
    assert any("TRAILING phase" in r.message for r in caplog.records)
    assert phases[-1]  # unmatched agents still run
