"""Integration tests: the parallel-workers feature (ExperimentRunner.
_run_agents_parallel returning SUBMISSION order; audit CSV sorted by
step_id -- feat/v3-parallel-determinism) and the crash-resume journal
(broker/utils/llm_journal.py, examples/irrigation_abm/run_experiment.py
--llm-journal / --resume-from -- feat/broker-llm-journal) were built on
separate branches. This file is their join point.

test_llm_journal_resume.py's own docstring scopes itself to workers=1 and
says so explicitly: "workers>1 crash-resume interaction is explicitly out
of scope: ExperimentRunner._run_agents_parallel is owned by another branch
and was not touched by this feature (see that method's own
JournalReplayDivergence handling gap, noted in this feature's delivery
report)." This file closes that gap: a run that crashes mid-year under
workers=4 must resume -- at workers=4, and separately at workers=1 -- to
output identical to an uninterrupted workers=1 run. It also unit-tests the
handling gap itself: _run_agents_parallel must not let a
JournalReplayDivergence or JournalWriteError raised inside a worker thread
get swallowed by its own broad ``except Exception`` and turned into one
more ABORTED row.

Drives the REAL CLI entry point (examples.irrigation_abm.run_experiment.main)
as a subprocess, through fixtures/journal_resume_jitter_driver.py (a hash-
of-prompt + 0-20ms-jitter mock combined with the crash-resume driver's own
crash hook -- see that file's docstring for why the jitter matters here:
without it, every call still completes in essentially submission order
even at workers=4, never exercising a genuinely different thread-
completion order for replay to be robust against).

Never contacts Ollama or any live model: --model mock, and the driver's
own test invoke never makes a network call.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from examples.irrigation_abm.analysis import v3_metrics as vm

from broker.tools.compare_audit_csv import compare as compare_audit_csv

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DRIVER = Path(__file__).resolve().parent / "fixtures" / "journal_resume_jitter_driver.py"
_AUDIT_CSV_NAME = "irrigation_farmer_governance_audit.csv"
_YEARS = 5
_CRASH_AT_STEP = 3
_CRASH_AFTER_CALLS = 20

# Mirrors test_llm_journal_resume.py's own _VOLATILE_KEYS / _strip_volatile /
# _assert_json_matches: wall-clock timestamps and git-dirty state differ
# between ANY two separate process runs (not only a resume), so every JSON
# comparison in this file needs the same stripping, not only the
# resume-specific ones.
_VOLATILE_KEYS = {
    "timestamp", "git_commit", "git_dirty",
    "git_commit_at_finalize", "git_dirty_at_finalize", "finalized_at",
}


def _strip_volatile(obj):
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v) for k, v in obj.items()
            if k not in _VOLATILE_KEYS and "timestamp" not in k.lower()
        }
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def _assert_json_matches(path_a: Path, path_b: Path) -> None:
    a = _strip_volatile(json.loads(path_a.read_text(encoding="utf-8")))
    b = _strip_volatile(json.loads(path_b.read_text(encoding="utf-8")))
    assert a == b, f"{path_a} vs {path_b} differ (volatile keys excluded)"


def _run(output_dir: Path, *, workers: int, resume_from=None, llm_journal=True,
         crash_at_step=0, seed=42, years=_YEARS) -> subprocess.CompletedProcess:
    args = [
        sys.executable, str(_DRIVER),
        "--model", "mock", "--real", "--years", str(years),
        "--governance-mode", "strict", "--workers", str(workers),
        "--seed", str(seed), "--memory-seed", str(seed),
        "--output", str(output_dir),
    ]
    if llm_journal:
        args.append("--llm-journal")
    if resume_from is not None:
        args += ["--resume-from", str(resume_from)]
    env = dict(os.environ)
    env["WAGF_TEST_CRASH_AT_STEP"] = str(crash_at_step)
    env["WAGF_TEST_CRASH_AFTER_CALLS_IN_STEP"] = str(_CRASH_AFTER_CALLS)
    return subprocess.run(
        args, cwd=str(_REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=300,
    )


def _load_manifest(output_dir: Path) -> dict:
    return json.loads((output_dir / "reproducibility_manifest.json").read_text(encoding="utf-8"))


def _assert_matches_run_a(base_dir: Path, other_dir: Path, label: str) -> None:
    """The four artifacts task item 3 requires to equal run A: simulation_log.csv
    byte for byte, the governance audit CSV after compare_audit_csv's own
    column-aware normalisation, governance_summary.json, and run_integrity.json
    (the last two with volatile keys stripped -- see _strip_volatile).
    reproducibility_manifest.json is deliberately NOT compared here: its
    `workers` field (and its journal-provenance fields) legitimately differ
    between run A and a resumed run by construction -- see
    test_resumed_manifest_records_workers_and_provenance below instead."""
    sim_a = (base_dir / "simulation_log.csv").read_bytes()
    sim_b = (other_dir / "simulation_log.csv").read_bytes()
    assert sim_a == sim_b, f"simulation_log.csv is not byte-identical {label}"

    rc = compare_audit_csv(base_dir / _AUDIT_CSV_NAME, other_dir / _AUDIT_CSV_NAME)
    assert rc == 0, f"{_AUDIT_CSV_NAME} differs {label}"

    _assert_json_matches(
        base_dir / "governance_summary.json", other_dir / "governance_summary.json",
    )
    _assert_json_matches(
        base_dir / "run_integrity.json", other_dir / "run_integrity.json",
    )


class TestWorkersAndJournalResumeCompose:
    """Run A: uninterrupted, workers=1, with the journal. Run B: workers=4,
    with the journal, crashed during year _CRASH_AT_STEP. Resumed from B's
    own journal twice, independently: once at workers=4 into a new
    directory, and once at workers=1 (from a COPY of B's journal file, not
    the original path -- proving --resume-from needs nothing else from the
    crashed run's directory) into another new directory. Both resumes must
    match run A."""

    @pytest.fixture(scope="class")
    def run_a(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("run_a_w1")
        result = _run(out, workers=1, llm_journal=True, crash_at_step=0)
        assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
        return out

    @pytest.fixture(scope="class")
    def crashed_b(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("run_b_w4_crashed")
        result = _run(out, workers=4, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        # Exactly the simulated crash (os._exit(70) in
        # journal_resume_driver.py's _maybe_crash), not some other failure
        # that also happens to exit non-zero: a precise returncode plus the
        # driver's own stderr marker is what distinguishes "the crash fired
        # as intended" from "the run broke for an unrelated reason."
        assert result.returncode == 70, (
            "expected the simulated hard crash (os._exit(70)); adjust "
            f"_CRASH_AFTER_CALLS if not -- got returncode={result.returncode}:\n"
            + result.stdout[-4000:] + result.stderr[-4000:]
        )
        assert "WAGF_TEST_CRASH" in result.stderr, (
            f"expected the driver's own crash marker in stderr:\n{result.stderr[-4000:]}"
        )
        return out

    @pytest.fixture(scope="class")
    def resumed_b_workers4(self, tmp_path_factory, crashed_b):
        out = tmp_path_factory.mktemp("run_b_resumed_w4")
        result = _run(
            out, workers=4, resume_from=crashed_b / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0,
        )
        assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
        return out

    @pytest.fixture(scope="class")
    def resumed_b_workers1(self, tmp_path_factory, crashed_b):
        # A COPY of B's journal, at a path distinct from the crashed run's
        # own output directory: --resume-from must work from just the
        # journal file's content, nothing else crashed_b/ holds.
        journal_copy_dir = tmp_path_factory.mktemp("run_b_journal_copy")
        journal_copy = journal_copy_dir / "llm_journal.jsonl"
        shutil.copy2(crashed_b / "llm_journal.jsonl", journal_copy)

        out = tmp_path_factory.mktemp("run_b_resumed_w1")
        result = _run(
            out, workers=1, resume_from=journal_copy,
            llm_journal=True, crash_at_step=0,
        )
        assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
        return out

    def test_resumed_workers4_matches_run_a(self, run_a, resumed_b_workers4):
        _assert_matches_run_a(
            run_a, resumed_b_workers4, "between run A (workers=1) and B resumed at workers=4",
        )

    def test_resumed_workers1_matches_run_a(self, run_a, resumed_b_workers1):
        _assert_matches_run_a(
            run_a, resumed_b_workers1,
            "between run A (workers=1) and B resumed at workers=1 (from a copy of B's journal)",
        )

    def test_run_a_manifest_records_workers(self, run_a):
        manifest = _load_manifest(run_a)
        assert manifest["workers"] == 1
        # Never resumed: no resume-provenance keys at all, source_workers
        # included (broker.utils.llm_journal.LLMJournalManager.
        # provenance_metadata returns None for a non-resumed run).
        assert "source_workers" not in manifest

    def test_resumed_workers4_manifest_records_workers_and_provenance(self, resumed_b_workers4):
        manifest = _load_manifest(resumed_b_workers4)
        assert manifest["workers"] == 4
        assert manifest["source_workers"] == 4  # resumed at the SAME worker count as the crash
        assert manifest["replayed_steps"] == _CRASH_AT_STEP - 1
        assert manifest["replayed_calls"] > 0
        assert manifest["source_journal_sha256"]

    def test_resumed_workers1_manifest_records_workers_and_provenance(self, resumed_b_workers1):
        manifest = _load_manifest(resumed_b_workers1)
        assert manifest["workers"] == 1
        assert manifest["source_workers"] == 4  # resumed at a DIFFERENT worker count than the crash
        assert manifest["replayed_steps"] == _CRASH_AT_STEP - 1
        assert manifest["replayed_calls"] > 0
        assert manifest["source_journal_sha256"]

    def test_mixed_worker_history_is_refused_by_the_metrics_guard(self, run_a, resumed_b_workers1):
        """Opus review follow-up item 1: resumed_b_workers1's OWN `workers`
        is 1, same as run_a's -- the plain `workers` field alone would pool
        the two without complaint. But resumed_b_workers1's REPLAYED years
        actually came from the workers=4 crash (source_workers=4, asserted
        above), so its output is not equivalent provenance to a run that
        was workers=1 from year 1. check_provenance must refuse this pool
        even though the two manifests' own `workers` values agree."""
        a = vm.read_run_info(run_a)
        b = vm.read_run_info(resumed_b_workers1)
        with pytest.raises(vm.ProvenanceError, match="workers"):
            vm.check_provenance([a, b])
        record = vm.check_provenance([a, b], allow_mixed=True)
        assert any("workers" in d for d in record["differences"])


# ---------------------------------------------------------------------------
# Unit test: _run_agents_parallel must not swallow the journal exceptions.
# ---------------------------------------------------------------------------

from broker.core.experiment_runner import ExperimentRunner  # noqa: E402
from broker.interfaces.skill_types import SkillBrokerResult, SkillOutcome  # noqa: E402
from broker.utils.llm_journal import JournalReplayDivergence, JournalWriteError  # noqa: E402


def _make_agent(agent_id: str, agent_type: str = "household"):
    agent = MagicMock()
    agent.id = agent_id
    agent.agent_type = agent_type
    return agent


def _make_runner(workers: int, raise_exc: BaseException, raise_for: str) -> ExperimentRunner:
    """A minimal ExperimentRunner for calling _run_agents_parallel directly,
    the same ExperimentRunner.__new__ pattern tests/test_parallel_determinism.py
    and broker/tests/test_llm_safeguard.py's TestRunnerDoesNotSwallowTheAbortException
    already use for this exact method -- generalised here to raise an
    arbitrary exception (JournalReplayDivergence / JournalWriteError) for one
    agent_id instead of a hardcoded RuntimeError."""
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
            raise raise_exc
        return SkillBrokerResult(
            outcome=SkillOutcome.APPROVED,
            skill_proposal=None,
            approved_skill=None,
            execution_result=None,
        )

    runner.broker.process_step = MagicMock(side_effect=_process_step)
    return runner


class TestParallelPathDoesNotSwallowJournalExceptions:
    """Mirrors broker/tests/test_llm_safeguard.py's
    TestRunnerDoesNotSwallowTheAbortException for the two crash-resume
    journal exceptions: a JournalReplayDivergence or JournalWriteError
    raised inside a worker thread's process_step call must propagate out of
    _run_agents_parallel, never get caught by its broad `except Exception`
    and turned into one more ABORTED row (task item 1 of this change: the
    new except clause placed before that broad handler)."""

    def test_journal_replay_divergence_propagates(self):
        err = JournalReplayDivergence(
            "no matching recorded call left in the source journal",
            step=3, agent_type="farmer", prompt_sha256="a" * 64,
        )
        runner = _make_runner(workers=2, raise_exc=err, raise_for="A0")
        agents = [_make_agent("A0"), _make_agent("A1")]

        with pytest.raises(JournalReplayDivergence):
            runner._run_agents_parallel(
                agents, run_id="r", llm_invoke=lambda *a, **kw: None,
                env={"current_year": 1},
            )

    def test_journal_write_error_propagates(self):
        err = JournalWriteError("failed to write a call record: disk full")
        runner = _make_runner(workers=2, raise_exc=err, raise_for="A0")
        agents = [_make_agent("A0"), _make_agent("A1")]

        with pytest.raises(JournalWriteError):
            runner._run_agents_parallel(
                agents, run_id="r", llm_invoke=lambda *a, **kw: None,
                env={"current_year": 1},
            )

    def test_cancels_queued_futures_before_reraising(self):
        """Same spy-on-shutdown technique as test_llm_safeguard.py's
        test_parallel_path_cancels_queued_futures_before_reraising: a REAL
        ThreadPoolExecutor subclass (not a mock), so the run still behaves
        normally except for recording each shutdown() call's arguments."""
        import broker.core.experiment_runner as experiment_runner_module
        from concurrent.futures import ThreadPoolExecutor

        shutdown_calls = []

        class _SpyExecutor(ThreadPoolExecutor):
            def shutdown(self, wait=True, *, cancel_futures=False):
                shutdown_calls.append({"wait": wait, "cancel_futures": cancel_futures})
                super().shutdown(wait=wait, cancel_futures=cancel_futures)

        err = JournalReplayDivergence(
            "no matching recorded call left in the source journal",
            step=1, agent_type="farmer", prompt_sha256="b" * 64,
        )
        runner = _make_runner(workers=2, raise_exc=err, raise_for="A0")
        agents = [_make_agent("A0"), _make_agent("A1")]

        with patch.object(experiment_runner_module, "ThreadPoolExecutor", _SpyExecutor):
            with pytest.raises(JournalReplayDivergence):
                runner._run_agents_parallel(
                    agents, run_id="r", llm_invoke=lambda *a, **kw: None,
                    env={"current_year": 1},
                )

        assert any(
            call["cancel_futures"] is True and call["wait"] is True
            for call in shutdown_calls
        ), f"expected an explicit shutdown(wait=True, cancel_futures=True) call, got {shutdown_calls}"


# ---------------------------------------------------------------------------
# check_provenance's workers/source_workers comparison (Opus review of WP7
# launcher, item 4(b), bug fix). Minimal synthetic RunInfo objects, not full
# mock-driven runs: this exercises check_provenance's own logic in isolation.
# ---------------------------------------------------------------------------

def _llm_water_system_fields() -> dict:
    """Every ``_LLM_WATER_KEYS`` path, nested the way
    ``_record_water_system_config_provenance`` actually writes them
    (``coupling_retrofit_metadata.water_system_<name>`` for some keys, top
    level for others), filled in from ``_analysis_water_expectations()`` so
    these synthetic fixtures equal whatever this module's own water-system
    constants currently are, rather than guessing numbers that would drift
    out of sync with them."""
    expectations = vm._analysis_water_expectations()
    fields: dict = {}
    for key, path in vm._LLM_WATER_KEYS.items():
        if key in ("hold_requests_fixed", "paper_water_margin"):
            continue  # set separately: not in _analysis_water_expectations()
        node = fields
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = expectations[key]
    return fields


_BASE_PROVENANCE_MANIFEST = {
    "git_commit": "deadbeefcafe00",
    "git_dirty": False,
    "model": "gemma3:4b",
    "memory_seed": 42,
    "governance_profile": "strict",
    "governance_profile_resolved": "strict",
    "retry_feedback_mode": None,
    "appraisal_freeze_resolved": True,
    "hold_requests_fixed": False,
    "step_bin_source": ["hy2021_grid"],
    **vm.SPEC_72_VALUES,
    **_llm_water_system_fields(),
}


def _synthetic_llm_run(seed: int, workers, source_workers=None) -> "vm.RunInfo":
    manifest = dict(_BASE_PROVENANCE_MANIFEST)
    manifest["seed"] = seed
    manifest["workers"] = workers
    if source_workers is not None:
        manifest["source_workers"] = source_workers
    return vm.RunInfo(Path(f"/fake/run_seed{seed}"), "llm", "strict", seed, manifest)


class TestCheckProvenanceWorkersBugFix:
    """Before the fix, `check_provenance` compared the raw
    ``(workers, source_workers)`` tuple across runs, e.g. a fresh run's
    ``(4, None)`` against a same-workers RESUMED run's ``(4, 4)`` -- two
    different tuples, so EVERY resumed run was refused as "mixed" even when
    the whole pool, resumed or not, was consistently at one workers value.
    Fixed rule: per run, the set of distinct values among {workers} and
    source_workers (when present) must itself be a singleton (catches a run
    whose OWN history touched two worker counts); only then are the
    per-run singleton values compared ACROSS the pool."""

    def test_resumed_at_same_workers_as_a_fresh_run_passes(self):
        fresh = _synthetic_llm_run(43, workers=4)
        resumed_same_workers = _synthetic_llm_run(44, workers=4, source_workers=4)
        vm.check_provenance([fresh, resumed_same_workers])  # must not raise

    def test_crashed_at_4_resumed_at_1_is_refused(self):
        resumed_mismatched = _synthetic_llm_run(45, workers=1, source_workers=4)
        with pytest.raises(vm.ProvenanceError, match="workers"):
            vm.check_provenance([resumed_mismatched])

    def test_crashed_at_4_resumed_at_1_refused_even_pooled_only_against_workers_1(self):
        """The scenario the original comment described: a run resumed at a
        DIFFERENT worker count than its own crash must be refused even when
        every other run in the pool already sits at the resume's value."""
        resumed_mismatched = _synthetic_llm_run(45, workers=1, source_workers=4)
        plain_workers_1 = _synthetic_llm_run(46, workers=1)
        with pytest.raises(vm.ProvenanceError, match="workers"):
            vm.check_provenance([resumed_mismatched, plain_workers_1])

    def test_two_fresh_runs_at_different_workers_is_refused(self):
        a = _synthetic_llm_run(43, workers=4)
        b = _synthetic_llm_run(44, workers=1)
        with pytest.raises(vm.ProvenanceError, match="workers"):
            vm.check_provenance([a, b])

    def test_mixed_allowed_with_allow_mixed_provenance(self):
        a = _synthetic_llm_run(43, workers=4)
        b = _synthetic_llm_run(44, workers=1)
        record = vm.check_provenance([a, b], allow_mixed=True)
        assert any("workers" in d for d in record["differences"])
