"""The LLM backend is an OPTIONAL dependency, so every path that needs one
must fail loudly when it is missing.

``langchain-ollama`` lives in the ``[llm]`` extra. CI installs
``requirements.txt`` + ``.[dev,web]``, so on CI it is genuinely absent — which
makes CI the one place these tests are not a simulation.

Until 2026-08-06 ``create_llm_invoke`` caught the ImportError and returned
``lambda p: ('{"decision": 1}', LLMStats())``. That is not a fallback to the
mock model: the requested-mock branch parses the prompt and selects an option,
while this constant answered every prompt in a run identically. A 42-year,
78-agent experiment would complete, write 3,276 rows, pass its row-count and
join checks, and be indistinguishable from a real run in every artifact it
produced. It now raises instead. These tests pin that direction so it cannot
regress silently — nothing else in the suite asserts it.

They are deliberately environment-independent: the absence of the backend is
simulated, so they assert the same thing on CI (where it is absent) and on a
developer box that installed ``.[llm]`` (where it is present).
"""
import builtins
import sys

import pytest
from unittest.mock import MagicMock

from broker.core.experiment import ExperimentRunner, ExperimentConfig
from broker.agents import BaseAgent, AgentConfig, StateParam
from broker.interfaces.skill_types import (
    SkillProposal, ApprovedSkill, SkillBrokerResult,
    SkillOutcome, ExecutionResult,
)


# A model name that is NOT a mock, so it must go down the real-backend path.
REAL_MODEL = "gemma3:4b"


@pytest.fixture
def no_llm_backend(monkeypatch):
    """Make ``import langchain_ollama`` fail regardless of what is installed.

    Reproduces the CI environment on a developer box, and is a no-op change of
    behaviour on CI itself, so both give the same verdict.
    """
    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "langchain_ollama" or name.startswith("langchain_ollama."):
            raise ImportError("No module named 'langchain_ollama'")
        return real_import(name, *args, **kwargs)

    for mod in [m for m in list(sys.modules)
                if m == "langchain_ollama" or m.startswith("langchain_ollama.")]:
        monkeypatch.delitem(sys.modules, mod, raising=False)
    monkeypatch.setattr(builtins, "__import__", _blocked)


def _make_agent(agent_id: str, agent_type: str = "household") -> BaseAgent:
    return BaseAgent(AgentConfig(
        name=agent_id,
        agent_type=agent_type,
        state_params=[StateParam(name="savings", raw_range=(0, 100000),
                                 initial_raw=50000)],
        objectives=[], constraints=[], skills=[],
    ))


def _make_mock_broker():
    broker = MagicMock()
    broker.config = MagicMock()
    broker.config.get_llm_params.return_value = {}
    broker.process_step.side_effect = lambda agent_id, **kw: SkillBrokerResult(
        outcome=SkillOutcome.APPROVED,
        skill_proposal=SkillProposal(skill_name="do_nothing", agent_id=agent_id,
                                     reasoning={}),
        approved_skill=ApprovedSkill(skill_name="do_nothing", agent_id=agent_id,
                                     approval_status="APPROVED",
                                     execution_mapping="sim.noop"),
        execution_result=ExecutionResult(success=True, state_changes={}),
        validation_errors=[], retry_count=0,
    )
    return broker


def _make_runner(tmp_path, model=REAL_MODEL):
    broker = _make_mock_broker()
    runner = ExperimentRunner(
        broker=broker,
        sim_engine=MagicMock(advance_year=lambda: {"current_year": 1}),
        agents={"a1": _make_agent("a1")},
        config=ExperimentConfig(model=model, num_years=1, output_dir=tmp_path),
    )
    return runner, broker


class TestCreateLlmInvokeRefuses:

    def test_raises_when_the_backend_is_missing(self, no_llm_backend):
        from broker.utils.llm_utils import create_llm_invoke
        with pytest.raises(RuntimeError, match="Cannot construct an LLM"):
            create_llm_invoke(REAL_MODEL)

    def test_the_error_names_the_model_and_the_way_out(self, no_llm_backend):
        """An operator reading only the traceback must know what to do."""
        from broker.utils.llm_utils import create_llm_invoke
        with pytest.raises(RuntimeError) as exc:
            create_llm_invoke(REAL_MODEL)
        message = str(exc.value)
        assert REAL_MODEL in message
        assert "langchain-ollama" in message
        assert "mock" in message

    def test_mock_models_still_work_without_the_backend(self, no_llm_backend):
        """The escape hatch the error message advertises has to be real."""
        from broker.utils.llm_utils import create_llm_invoke
        invoke = create_llm_invoke("mock")

        content, stats = invoke("Choose:\n1. do_nothing\n2. take_action")
        assert stats.success
        assert content == '{"decision": 1}'

        # Prompt-dependent, unlike the constant this replaced: a mock run
        # still varies with what the agent was asked.
        other, _ = invoke("Choose:\n7. relocate\n8. elevate")
        assert other == '{"decision": 7}'


class TestRunRefusesInsteadOfWritingACorpus:
    """The property the raise exists to buy, asserted at the runner level.

    A construction failure must surface BEFORE the agent loop. The loop's
    per-agent ``except Exception`` catches anything raised inside it, writes an
    ABORTED trace and continues — so a failure that reaches the loop lets the
    run COMPLETE and exit 0, leaving a full-row-count audit CSV whose rows
    carry ``llm_success=True`` and a ``run_integrity.json`` saying
    ``integrity_ok: true``. Measured, not hypothesised: deferring construction
    past this point turns a refused run into 8 artifact files and 4/4 rows.
    """

    def test_run_raises_when_no_invoke_is_supplied(self, no_llm_backend, tmp_path):
        runner, broker = _make_runner(tmp_path)
        with pytest.raises(RuntimeError, match="Cannot construct an LLM"):
            runner.run()
        assert broker.process_step.call_count == 0

    def test_run_raises_even_when_the_caller_supplies_an_invoke(
            self, no_llm_backend, tmp_path):
        """``run(llm_invoke=...)`` is accepted but does NOT stop the loop from
        building its own per-agent-type invokes, so supplying one must not
        downgrade the refusal into a completed run."""
        runner, broker = _make_runner(tmp_path)
        with pytest.raises(RuntimeError, match="Cannot construct an LLM"):
            runner.run(llm_invoke=MagicMock())
        assert broker.process_step.call_count == 0

    def test_run_writes_no_artifacts_when_it_refuses(self, no_llm_backend, tmp_path):
        """No output directory contents means nothing downstream can mistake a
        refused run for a real one."""
        runner, _ = _make_runner(tmp_path)
        with pytest.raises(RuntimeError, match="Cannot construct an LLM"):
            runner.run()
        assert [p for p in tmp_path.rglob("*") if p.is_file()] == []

    def test_a_mock_run_is_unaffected(self, no_llm_backend, tmp_path):
        """The refusal must be specific to needing a backend that is absent —
        a declared mock run still completes with the backend uninstalled."""
        runner, broker = _make_runner(tmp_path, model="mock")
        runner.run()
        assert broker.process_step.call_count == 1
