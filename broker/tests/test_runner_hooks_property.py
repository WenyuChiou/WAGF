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
