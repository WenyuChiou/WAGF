"""ExperimentRunner-level wiring tests for the crash-resume LLM-call journal
(broker/utils/llm_journal.py).

Uses a mocked SkillBrokerEngine, the same isolation pattern as
tests/core/test_experiment_runner.py, so these tests exercise
ExperimentRunner.get_llm_invoke / run() / _build_llm_journal_manager /
_collect_reproducibility_metadata wiring without any domain stack. Unlike
that file's own broker fixture, the one here ACTUALLY calls the
llm_invoke it is handed -- otherwise nothing would ever reach the journal.
"""
import json
from unittest.mock import MagicMock

import pytest

import broker.utils.llm_utils as llm_utils_mod
from broker.agents import AgentConfig, BaseAgent
from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner
from broker.interfaces.skill_types import (
    ApprovedSkill, ExecutionResult, SkillBrokerResult, SkillOutcome, SkillProposal,
)
from broker.utils.llm_journal import JournalReplayDivergence


def _make_agent(agent_id: str) -> BaseAgent:
    config = AgentConfig(
        name=agent_id, agent_type="household", state_params=[],
        objectives=[], constraints=[], skills=[],
    )
    return BaseAgent(config)


def _approved(agent_id: str) -> SkillBrokerResult:
    return SkillBrokerResult(
        outcome=SkillOutcome.APPROVED,
        skill_proposal=SkillProposal(skill_name="do_nothing", agent_id=agent_id, reasoning={}),
        approved_skill=ApprovedSkill(
            skill_name="do_nothing", agent_id=agent_id,
            approval_status="APPROVED", execution_mapping="sim.noop",
        ),
        execution_result=ExecutionResult(success=True, state_changes={}),
        validation_errors=[], retry_count=0,
    )


def _make_broker_that_calls_llm_invoke():
    """A mocked SkillBrokerEngine whose process_step ACTUALLY calls the
    llm_invoke it is handed. One call per (agent, year), prompt text tied
    to the agent id and the simulated year so the journal's per-step
    matching has something meaningful to key on.
    """
    broker = MagicMock()
    broker.log_prompt = False
    broker.audit_writer = MagicMock()
    broker.auditor = MagicMock()
    broker.model_adapter = MagicMock()
    broker.model_adapter.agent_config = None
    # Explicit, JSON-safe values: an unconfigured MagicMock attribute would
    # auto-vivify as another MagicMock, and _collect_reproducibility_
    # metadata's retry_feedback_mode field (unlike its isinstance-guarded
    # siblings) assigns it straight into the manifest with no type check,
    # which fails json.dump and (per _finalize_experiment's own guarded
    # except) silently skips writing reproducibility_manifest.json
    # entirely -- these tests need that file to exist and be readable.
    broker._retry_feedback_mode = "full"
    ctx_builder = MagicMock()
    ctx_builder.build.side_effect = lambda agent_id, **kw: {"state": {}, "agent_id": agent_id}
    broker.context_builder = ctx_builder
    broker.config = MagicMock()
    broker.config.get_llm_params.return_value = {}

    def process_step_side_effect(agent_id, **kwargs):
        invoke = kwargs["llm_invoke"]
        year = kwargs["env_context"]["current_year"]
        invoke(f"prompt for {agent_id} at year {year}")
        return _approved(agent_id)

    broker.process_step.side_effect = process_step_side_effect
    return broker


class _FakeSimEngine:
    """A plain class, not a MagicMock: MagicMock auto-vivifies ANY
    attribute (including advance_step), which would silently take
    ExperimentRunner.run()'s advance_step/advance_year branch the wrong
    way. This engine has advance_year only, matching a real domain engine
    that never implements advance_step.
    """

    def __init__(self):
        self.year = 0

    def advance_year(self):
        self.year += 1
        return {"current_year": self.year}


def _load_manifest(output_dir) -> dict:
    return json.loads((output_dir / "reproducibility_manifest.json").read_text(encoding="utf-8"))


class TestDefaultOff:
    def test_no_journal_config_means_no_journal_and_no_new_manifest_keys(self, tmp_path):
        config = ExperimentConfig(model="mock", num_years=1, output_dir=tmp_path)
        assert config.llm_journal_path is None
        assert config.resume_journal_path is None
        runner = ExperimentRunner(
            broker=_make_broker_that_calls_llm_invoke(), sim_engine=_FakeSimEngine(),
            agents={"a1": _make_agent("a1")}, config=config,
        )
        runner.run()

        assert getattr(runner, "_llm_journal", None) is None
        assert not (tmp_path / "llm_journal.jsonl").exists()
        manifest = _load_manifest(tmp_path)
        for key in ("resumed_from", "source_journal_sha256", "replayed_steps", "replayed_calls"):
            assert key not in manifest


class TestRecording:
    def test_journal_file_has_header_calls_and_step_end_markers(self, tmp_path):
        journal_path = tmp_path / "llm_journal.jsonl"
        config = ExperimentConfig(
            model="mock", num_years=2, output_dir=tmp_path, llm_journal_path=journal_path,
        )
        runner = ExperimentRunner(
            broker=_make_broker_that_calls_llm_invoke(), sim_engine=_FakeSimEngine(),
            agents={"a1": _make_agent("a1"), "a2": _make_agent("a2")}, config=config,
        )
        runner.run()

        lines = [json.loads(l) for l in journal_path.read_text(encoding="utf-8").splitlines()]
        assert lines[0]["type"] == "header"
        assert lines[0]["model"] == "mock"
        step_ends = [l["step"] for l in lines if l["type"] == "step_end"]
        assert step_ends == [1, 2]
        calls = [l for l in lines if l["type"] == "call"]
        assert len(calls) == 4  # 2 agents x 2 years
        assert {c["step"] for c in calls} == {1, 2}
        assert all(c["agent_type"] == "household" for c in calls)

        manifest = _load_manifest(tmp_path)
        for key in ("resumed_from", "source_journal_sha256", "replayed_steps", "replayed_calls"):
            assert key not in manifest  # recording only, never resumed


class TestResume:
    def test_replayed_steps_never_call_the_live_invoke(self, tmp_path, monkeypatch):
        live_calls = {"n": 0}
        real_create = llm_utils_mod.create_llm_invoke

        def counting_create(model, verbose=False, overrides=None):
            inner = real_create(model, verbose=verbose, overrides=overrides)

            def counted(prompt, *a, **k):
                live_calls["n"] += 1
                return inner(prompt, *a, **k)

            return counted

        monkeypatch.setattr(llm_utils_mod, "create_llm_invoke", counting_create)

        orig_dir = tmp_path / "orig"
        orig_dir.mkdir()
        journal_path = orig_dir / "llm_journal.jsonl"
        config = ExperimentConfig(
            model="mock", num_years=3, output_dir=orig_dir, llm_journal_path=journal_path,
        )
        runner = ExperimentRunner(
            broker=_make_broker_that_calls_llm_invoke(), sim_engine=_FakeSimEngine(),
            agents={"a1": _make_agent("a1")}, config=config,
        )
        runner.run()
        assert live_calls["n"] == 3  # one per year, one agent

        resumed_dir = tmp_path / "resumed"
        resumed_dir.mkdir()
        resumed_config = ExperimentConfig(
            model="mock", num_years=3, output_dir=resumed_dir,
            llm_journal_path=resumed_dir / "llm_journal.jsonl",
            resume_journal_path=journal_path,
        )
        resumed_runner = ExperimentRunner(
            broker=_make_broker_that_calls_llm_invoke(), sim_engine=_FakeSimEngine(),
            agents={"a1": _make_agent("a1")}, config=resumed_config,
        )
        resumed_runner.run()
        # All 3 years were already complete in the source journal, so the
        # resumed run replays every one of them: the live invoke gains NO
        # new calls.
        assert live_calls["n"] == 3

        manifest = _load_manifest(resumed_dir)
        assert manifest["resumed_from"] == str(journal_path)
        assert manifest["replayed_steps"] == 3
        assert manifest["replayed_calls"] == 3
        assert "source_journal_sha256" in manifest

    def test_partial_resume_goes_live_past_the_source_run(self, tmp_path, monkeypatch):
        """The source journal only covers 2 of 3 years (simulating the
        source process having crashed before year 3's step_end); the
        resumed run replays years 1-2 and makes a LIVE call for year 3.
        """
        live_calls = {"n": 0}
        real_create = llm_utils_mod.create_llm_invoke

        def counting_create(model, verbose=False, overrides=None):
            inner = real_create(model, verbose=verbose, overrides=overrides)

            def counted(prompt, *a, **k):
                live_calls["n"] += 1
                return inner(prompt, *a, **k)

            return counted

        monkeypatch.setattr(llm_utils_mod, "create_llm_invoke", counting_create)

        orig_dir = tmp_path / "orig"
        orig_dir.mkdir()
        journal_path = orig_dir / "llm_journal.jsonl"
        config = ExperimentConfig(
            model="mock", num_years=2, output_dir=orig_dir, llm_journal_path=journal_path,
        )
        runner = ExperimentRunner(
            broker=_make_broker_that_calls_llm_invoke(), sim_engine=_FakeSimEngine(),
            agents={"a1": _make_agent("a1")}, config=config,
        )
        runner.run()
        assert live_calls["n"] == 2

        resumed_dir = tmp_path / "resumed"
        resumed_dir.mkdir()
        resumed_config = ExperimentConfig(
            model="mock", num_years=3, output_dir=resumed_dir,
            llm_journal_path=resumed_dir / "llm_journal.jsonl",
            resume_journal_path=journal_path,
        )
        resumed_runner = ExperimentRunner(
            broker=_make_broker_that_calls_llm_invoke(), sim_engine=_FakeSimEngine(),
            agents={"a1": _make_agent("a1")}, config=resumed_config,
        )
        resumed_runner.run()
        # years 1-2 replayed (no new live calls); year 3 is new and live.
        assert live_calls["n"] == 3

        manifest = _load_manifest(resumed_dir)
        assert manifest["replayed_steps"] == 2
        assert manifest["replayed_calls"] == 2

    def test_divergence_propagates_out_of_run_not_swallowed(self, tmp_path):
        """A resumed run whose rebuilt prompt stream does not match the
        source (here: a different agent population renders a different
        prompt) must raise JournalReplayDivergence out of run(), not
        silently record an ABORTED row and keep going.
        """
        orig_dir = tmp_path / "orig"
        orig_dir.mkdir()
        journal_path = orig_dir / "llm_journal.jsonl"
        config = ExperimentConfig(
            model="mock", num_years=1, output_dir=orig_dir, llm_journal_path=journal_path,
        )
        runner = ExperimentRunner(
            broker=_make_broker_that_calls_llm_invoke(), sim_engine=_FakeSimEngine(),
            agents={"a1": _make_agent("a1")}, config=config,
        )
        runner.run()

        resumed_dir = tmp_path / "resumed"
        resumed_dir.mkdir()
        resumed_config = ExperimentConfig(
            model="mock", num_years=1, output_dir=resumed_dir,
            resume_journal_path=journal_path,
        )
        resumed_runner = ExperimentRunner(
            broker=_make_broker_that_calls_llm_invoke(), sim_engine=_FakeSimEngine(),
            agents={"different_agent": _make_agent("different_agent")}, config=resumed_config,
        )
        with pytest.raises(JournalReplayDivergence):
            resumed_runner.run()
