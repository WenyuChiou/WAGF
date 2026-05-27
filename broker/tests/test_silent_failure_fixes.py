"""
Regression tests for the three silent-failure findings (F1 / F2 / F3)
surfaced by the swarmlab integration audit (silent-failure-hunter-py
2026-05-27) and fixed in the post-Phase-6T patch commit.

Findings recap:

- **F1 (P0)** ``broker/core/experiment_runner.py:541-543`` — sequential
  agent-step ``except Exception`` logs but does not append to
  ``results``. Failed agent contributes zero rows to audit CSV — the
  v0.88.15-class denominator-shrink bug.
- **F2 (P1)** ``broker/components/analytics/audit.py:756-759`` — JSONL
  flush final-failure path logs but does not clear
  ``_jsonl_buffer[agent_type]``. Next flush re-appends the same lines,
  producing duplicate JSONL rows that inflate IBR + decision counts.
- **F3 (P1)** ``broker/core/experiment_runner.py:243-345`` — unwrapped
  manifest ``json.dump`` can raise mid-finalize, skipping
  ``auditor.save_summary()`` and leaving ``governance_summary.json``
  missing.

Each test pins the fixed behaviour so a future refactor cannot
silently re-introduce the bug. The tests use minimal in-memory
mocks rather than full experiment runs — the contracts being tested
are surgical.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from broker.components.analytics.audit import GenericAuditWriter
from broker.interfaces.skill_types import SkillBrokerResult, SkillOutcome


# ─────────────────────────────────────────────────────────────────────
# F1 — agent-step exception preserves audit row
# ─────────────────────────────────────────────────────────────────────


class TestF1FailedAgentStepProducesAuditRow:
    """F1 (P0): when an agent's step raises, the agent MUST still
    appear in ``results`` (as an ``ABORTED`` SkillBrokerResult) AND
    the audit writer MUST receive a sentinel trace so the failure
    is visible in ``<agent_type>_governance_audit.csv``.

    Pre-fix path silently dropped the agent — denominator shrinks
    without signal."""

    def _make_runner_with_mocks(self, raising_agent_id: str = "Agent_FAIL"):
        """Build a minimal ExperimentRunner with mocked broker so
        we can inject a raising ``process_step`` without standing
        up real LLM / memory infrastructure."""
        from broker.core.experiment_runner import ExperimentRunner
        from broker.core.experiment import ExperimentConfig

        # Real ExperimentRunner requires substantial setup; mock the
        # parts that are not under test.
        runner = ExperimentRunner.__new__(ExperimentRunner)
        runner.broker = MagicMock()
        runner.broker.audit_writer = MagicMock()
        runner.step_counter = 5
        runner.config = MagicMock()
        runner.config.seed = 42
        runner._model_name = "test_model"
        runner.efficiency = MagicMock()
        runner.efficiency.compute_hash = MagicMock(return_value="hash_x")
        runner.efficiency.get = MagicMock(return_value=None)  # always cache miss
        runner.efficiency.put = MagicMock()
        runner.broker.context_builder = MagicMock()
        runner.broker.context_builder.build = MagicMock(return_value={"state": {}})
        # Stub get_llm_invoke so the sequential loop reaches process_step.
        runner.get_llm_invoke = MagicMock(return_value=lambda *a, **kw: None)

        # process_step raises for the target agent, returns valid
        # result for others.
        def _process_step(agent_id, **kwargs):
            if agent_id == raising_agent_id:
                raise RuntimeError("simulated LLM provider timeout")
            return SkillBrokerResult(
                outcome=SkillOutcome.APPROVED,
                skill_proposal=None,
                approved_skill=None,
                execution_result=None,
            )

        runner.broker.process_step = MagicMock(side_effect=_process_step)
        return runner

    def _make_agent(self, agent_id: str, agent_type: str = "household"):
        agent = MagicMock()
        agent.id = agent_id
        agent.agent_type = agent_type
        return agent

    def test_failed_agent_appears_in_results_with_aborted_outcome(self):
        """Pre-fix the failed agent vanished from results. Post-fix
        it must be present as ABORTED."""
        runner = self._make_runner_with_mocks()
        agents = [
            self._make_agent("Agent_OK"),
            self._make_agent("Agent_FAIL"),
            self._make_agent("Agent_OK2"),
        ]
        env = {"current_year": 3}

        results = runner._run_agents_sequential(
            agents, run_id="run_x", llm_invoke=lambda *a, **kw: None, env=env,
        )

        # All 3 agents must appear:
        assert len(results) == 3
        result_by_id = {agent.id: result for agent, result in results}
        assert result_by_id["Agent_OK"].outcome == SkillOutcome.APPROVED
        assert result_by_id["Agent_OK2"].outcome == SkillOutcome.APPROVED
        # Failed agent:
        assert result_by_id["Agent_FAIL"].outcome == SkillOutcome.ABORTED
        assert any(
            "agent_step_exception" in err
            and "RuntimeError" in err
            and "simulated LLM provider timeout" in err
            for err in result_by_id["Agent_FAIL"].validation_errors
        )

    def test_failed_agent_writes_sentinel_audit_trace(self):
        """The audit writer must receive a trace for the failed
        agent with the canonical sentinel fields."""
        runner = self._make_runner_with_mocks()
        agents = [self._make_agent("Agent_FAIL")]
        env = {"current_year": 7}

        runner._run_agents_sequential(
            agents, run_id="run_x", llm_invoke=lambda *a, **kw: None, env=env,
        )

        # Audit writer received at least one trace call:
        assert runner.broker.audit_writer.write_trace.called
        # Inspect the call args:
        call_args = runner.broker.audit_writer.write_trace.call_args
        agent_type_arg = call_args[0][0]
        trace_arg = call_args[0][1]
        assert agent_type_arg == "household"
        assert trace_arg["agent_id"] == "Agent_FAIL"
        assert trace_arg["outcome"] == "ABORTED"
        assert trace_arg["status"] == "ABORTED_EXCEPTION"
        assert trace_arg["validated"] is False
        assert trace_arg["fallback_activated"] is False
        assert trace_arg["decision_source"] == "exception"
        assert trace_arg["year"] == 7
        assert any(
            "RuntimeError" in err and "simulated LLM provider timeout" in err
            for err in trace_arg["validation_errors"]
        )

    def test_secondary_audit_writer_failure_does_not_mask_original(self):
        """If the audit writer itself raises while emitting the
        sentinel trace, the original step exception's record (the
        ABORTED result tuple) must still be appended to results."""
        runner = self._make_runner_with_mocks()
        runner.broker.audit_writer.write_trace.side_effect = (
            OSError("disk full while writing sentinel")
        )
        agents = [self._make_agent("Agent_FAIL")]
        env = {"current_year": 1}

        results = runner._run_agents_sequential(
            agents, run_id="run_x", llm_invoke=lambda *a, **kw: None, env=env,
        )

        # Even though audit_writer raised, the ABORTED result must
        # still appear in results so the caller's downstream loop
        # iterates over it (post_step hook, denominator count, etc.).
        assert len(results) == 1
        assert results[0][1].outcome == SkillOutcome.ABORTED


# ─────────────────────────────────────────────────────────────────────
# F2 — JSONL flush final-failure clears buffer + counts lost events
# ─────────────────────────────────────────────────────────────────────


class TestF2JsonlFlushFinalFailureDiscardsBuffer:
    """F2 (P1): on terminal flush failure (max retries exhausted),
    the buffer MUST be cleared to prevent duplicate-write on the
    next flush. The number of lost events MUST be recorded in
    ``summary['jsonl_events_lost']`` for downstream detection.

    Pre-fix the buffer was left intact, so the next flush
    re-appended the same lines → duplicate JSONL rows + inflated
    IBR / decision counts."""

    def _make_writer(self, tmp_path: Path) -> GenericAuditWriter:
        from broker.utils.agent_config import GovernanceAuditor

        config = MagicMock()
        config.experiment_name = "test_f2"
        config.output_dir = tmp_path
        writer = GenericAuditWriter.__new__(GenericAuditWriter)
        writer.config = config
        writer.output_dir = tmp_path
        writer._files = {}
        writer._run_metadata = {}
        writer._trace_buffer = {}
        writer._jsonl_buffer = {}
        writer._jsonl_buffer_size = 1
        import threading
        writer._write_lock = threading.Lock()
        writer._expected_aggregates = {}
        writer._startup_warned = True
        writer.summary = {
            "experiment_name": "test_f2",
            "agent_types": {},
            "total_traces": 0,
            "validation_errors": 0,
            "validation_warnings": 0,
            "structural_faults_fixed": 0,
            "total_format_retries": 0,
            "validator_health": {},
            "jsonl_events_lost": 0,
        }
        return writer

    def test_terminal_failure_clears_buffer(self, tmp_path):
        """After max retries on a persistent OSError, the buffer
        entry for the agent_type must be empty."""
        writer = self._make_writer(tmp_path)
        writer._jsonl_buffer["household"] = [
            '{"step": 1}\n', '{"step": 2}\n', '{"step": 3}\n',
        ]

        # Patch builtins.open to always raise within audit module:
        with patch(
            "broker.components.analytics.audit.open",
            side_effect=OSError("persistent disk error"),
            create=True,
        ):
            with patch("time.sleep") as sleep_mock:
                writer._flush_jsonl_buffer("household", tmp_path / "h.jsonl")

        # Buffer must be empty (no re-append on next flush).
        assert writer._jsonl_buffer["household"] == []
        # Max retries = 3 → sleep called 2 times between attempts.
        assert sleep_mock.call_count == 2

    def test_terminal_failure_increments_jsonl_events_lost(self, tmp_path):
        """The summary counter must reflect the number of lost
        events so downstream consumers can detect partial runs."""
        writer = self._make_writer(tmp_path)
        writer._jsonl_buffer["household"] = [f'{{"step": {i}}}\n' for i in range(5)]

        with patch(
            "broker.components.analytics.audit.open",
            side_effect=OSError("disk full"),
            create=True,
        ):
            with patch("time.sleep"):
                writer._flush_jsonl_buffer("household", tmp_path / "h.jsonl")

        assert writer.summary["jsonl_events_lost"] == 5

    def test_successful_flush_does_not_change_lost_counter(self, tmp_path):
        """A normal flush (no retries needed) must NOT increment
        the lost-events counter."""
        writer = self._make_writer(tmp_path)
        writer._jsonl_buffer["household"] = ['{"step": 1}\n']

        writer._flush_jsonl_buffer("household", tmp_path / "h.jsonl")

        assert writer._jsonl_buffer["household"] == []
        assert writer.summary["jsonl_events_lost"] == 0
        # File should have the line.
        assert (tmp_path / "h.jsonl").exists()


# ─────────────────────────────────────────────────────────────────────
# F3 — manifest-write failure does not skip summary save
# ─────────────────────────────────────────────────────────────────────


class TestF3SummaryWriteIndependentOfManifestWrite:
    """F3 (P1): if the reproducibility_manifest.json write fails
    (disk full, read-only path), the auditor's save_summary() MUST
    still run. Pre-fix path was a single uncaught json.dump, which
    propagated out of _finalize_experiment before save_summary
    could fire — leaving governance_summary.json missing without
    signal to downstream consumers."""

    def _make_runner_with_mocks(self, tmp_path: Path, manifest_fails: bool):
        """Build a minimal runner where the manifest write is
        forced to fail (or not), and observe whether save_summary
        is invoked."""
        from broker.core.experiment_runner import ExperimentRunner

        runner = ExperimentRunner.__new__(ExperimentRunner)
        runner.broker = MagicMock()
        runner.broker.audit_writer = MagicMock()
        runner.broker.audit_writer.finalize = MagicMock()
        runner.broker.auditor = MagicMock()
        runner.broker.auditor.save_summary = MagicMock()
        runner.broker.model_adapter = MagicMock()
        runner.broker.model_adapter.config_path = None
        runner.memory_engine = MagicMock()
        runner.config = MagicMock()
        runner.config.model = "test_model"
        runner.config.seed = 42
        runner.config.governance_profile = "strict"
        runner.config.output_dir = tmp_path
        runner._collect_reproducibility_metadata = MagicMock(return_value={})
        runner._manifest_fails = manifest_fails
        return runner

    def test_save_summary_runs_when_manifest_write_succeeds(self, tmp_path):
        """Sanity check: happy path still works."""
        runner = self._make_runner_with_mocks(tmp_path, manifest_fails=False)

        runner._finalize_experiment(iterations=1)

        assert runner.broker.auditor.save_summary.called
        manifest_path = tmp_path / "reproducibility_manifest.json"
        assert manifest_path.exists()
        # Content is valid JSON:
        assert "model" in json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_save_summary_runs_when_manifest_write_fails(self, tmp_path):
        """The critical invariant: even if the manifest write
        raises OSError, save_summary must still be called."""
        runner = self._make_runner_with_mocks(tmp_path, manifest_fails=True)

        # Force the manifest open() to raise. We patch the json
        # module's dump as the simplest injection point that
        # mimics a write-time disk failure (open succeeded but
        # write didn't).
        with patch(
            "broker.core.experiment_runner.json.dump",
            side_effect=OSError("disk full mid-write"),
        ):
            runner._finalize_experiment(iterations=1)

        # save_summary MUST still have been called.
        assert runner.broker.auditor.save_summary.called

    def test_save_summary_failure_does_not_mask_manifest_success(self, tmp_path):
        """Even if save_summary raises, the manifest write that
        already succeeded must remain on disk (no rollback)."""
        runner = self._make_runner_with_mocks(tmp_path, manifest_fails=False)
        runner.broker.auditor.save_summary.side_effect = OSError(
            "summary write failed"
        )

        # Should not raise:
        runner._finalize_experiment(iterations=1)

        manifest_path = tmp_path / "reproducibility_manifest.json"
        assert manifest_path.exists()
