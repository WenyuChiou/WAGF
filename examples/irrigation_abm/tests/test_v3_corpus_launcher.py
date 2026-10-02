"""Tests for examples/irrigation_abm/tools/v3_corpus_launcher.py (spec WP7
Launch, 7.1-7.6).

Every subprocess that would actually run an experiment or contact Ollama is
mocked: `_popen_detached` (the one function that ever spawns the detached
chain-runner process) and `subprocess.Popen` / `subprocess.run` (used for
each chained command, each `v3_metrics.py` call, and `is_pid_alive`'s
`tasklist` check) are patched in every test that reaches them. An autouse
fixture (`_guard_real_subprocess_calls`) additionally makes ANY
unmocked `subprocess.Popen` / `subprocess.run` call raise, UNLESS it is one
of the two real, local, no-network commands this suite deliberately lets
through: `git` (the preflight tests' throwaway temp repos) and `tasklist`
(`is_pid_alive`'s liveness check -- reading the local process table, never
touching Ollama or the network). No test starts `run_fql_baseline.py`,
`run_experiment.py`, or `v3_metrics.py` for real, and none imports or
touches Ollama.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from examples.irrigation_abm.tools import v3_corpus_launcher as launcher

_REAL_SUBPROCESS_RUN = subprocess.run
_REAL_SUBPROCESS_POPEN = subprocess.Popen
_ALLOWED_REAL_COMMANDS = ("git", "tasklist")


@pytest.fixture(autouse=True)
def _guard_real_subprocess_calls(monkeypatch):
    """Safety net (Opus review item 15): a test that forgets to mock
    `subprocess.Popen` / `subprocess.run` must fail loudly, not silently
    launch something real. `git` and `tasklist` are allowed through to the
    real implementation (see module docstring); a test that needs to mock
    one of THOSE specifically (none currently do) can still
    `monkeypatch.setattr` it again inside the test, which simply shadows
    this fixture's patch for that test's duration."""

    def _guard_popen(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] in _ALLOWED_REAL_COMMANDS:
            return _REAL_SUBPROCESS_POPEN(cmd, *a, **kw)
        raise AssertionError(f"unmocked subprocess.Popen call in a test: {cmd!r}")

    def _guard_run(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] in _ALLOWED_REAL_COMMANDS:
            return _REAL_SUBPROCESS_RUN(cmd, *a, **kw)
        raise AssertionError(f"unmocked subprocess.run call in a test: {cmd!r}")

    monkeypatch.setattr(launcher.subprocess, "Popen", _guard_popen)
    monkeypatch.setattr(launcher.subprocess, "run", _guard_run)
    yield


def _fake_v3_metrics_run(calls, returncode_for=None, on_call=None):
    """A `subprocess.run` fake for `cmd_gate` tests: records every
    v3_metrics.py call into `calls` and returns 0 (or whatever
    `returncode_for(cmd)` says), while letting `git` (cmd_gate's own
    preflight) pass through to the real implementation -- same pattern the
    autouse guard above uses."""
    returncode_for = returncode_for or (lambda cmd: 0)

    def _run(cmd, cwd=None, check=False, **kwargs):
        if cmd and cmd[0] == "git":
            return _REAL_SUBPROCESS_RUN(cmd, cwd=cwd, **kwargs)
        calls.append(cmd)
        if on_call:
            on_call(cmd)
        return types.SimpleNamespace(returncode=returncode_for(cmd))

    return _run


class _FakePopen:
    """Stand-in for `subprocess.Popen` used by `run_chain` tests: `.wait()`
    returns a pre-set returncode instead of actually running anything."""

    def __init__(self, pid, returncode):
        self.pid = pid
        self._returncode = returncode

    def wait(self):
        return self._returncode


def _fake_chain_popen(returncodes, calls=None, pid_start=1000):
    """Returns a `subprocess.Popen` fake for `run_chain`: the Nth call gets
    `returncodes[N]` (or 0 if the list is exhausted) and a distinct pid."""
    state = {"n": 0}

    def _popen(cmd, cwd=None, stdout=None, stderr=None, stdin=None, creationflags=None):
        if calls is not None:
            calls.append(cmd)
        idx = state["n"]
        state["n"] += 1
        rc = returncodes[idx] if idx < len(returncodes) else 0
        return _FakePopen(pid_start + idx, rc)

    return _popen


def _mock_liveness(monkeypatch, alive_pids_and_needles):
    """Mocks the ONE function that shells out for a liveness check
    (`_process_command_line`), per the module's own "mockable" contract
    (item 4). `alive_pids_and_needles` maps a pid to the substring its
    fake command line contains (e.g. an output dir, or "_run-chain"); any
    other pid reports as not found (dead / never existed)."""

    def _fake(pid, timeout=10.0):
        needle = alive_pids_and_needles.get(pid)
        if needle is None:
            return None
        return f"python.exe ...{needle}..."

    monkeypatch.setattr(launcher, "_process_command_line", _fake)


def _mock_all_dead(monkeypatch):
    monkeypatch.setattr(launcher, "_process_command_line", lambda pid, timeout=10.0: None)


def _done_run_integrity() -> dict:
    """The run_integrity.json content item 3(b)'s stricter "done" check
    accepts for an LLM run when no launcher-recorded exit 0 is available."""
    return {"audit_rows_missing_vs_configured_grid": 0, "audit_years": 42}


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def git_repo(tmp_path):
    """A minimal real git repo with one commit tagged "v-test"."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def _git(*args):
        result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
        assert result.returncode == 0, f"git {args} failed: {result.stderr}"
        return result.stdout.strip()

    _git("init")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git("add", "README.md")
    _git("commit", "-m", "initial")
    _git("tag", "v-test")
    return repo, _git


# =============================================================================
# build_plan: ordering, counts, commands, output-dir naming
# =============================================================================

class TestBuildPlan:
    def test_total_count_and_phase_counts(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        assert len(plan) == 32
        phases = [r.phase for r in plan]
        assert phases.count("fql") == 10
        assert phases.count("replays") == 1
        assert phases.count("pilot") == 2
        assert phases.count("corpus") == 19

    def test_order_fql_then_replays_then_pilot_then_corpus(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        assert [r.phase for r in plan[:10]] == ["fql"] * 10
        assert plan[10].phase == "replays"
        assert plan[10].label == "replays_ab"
        assert [r.label for r in plan[11:13]] == ["pilot_strict_42", "pilot_disabled_42"]
        assert all(r.phase == "corpus" for r in plan[13:])
        assert len(plan[13:]) == 19

    def test_fql_seeds_42_to_51_in_order(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        fql_seeds = [int(r.label.replace("fql_seed", "")) for r in plan if r.phase == "fql"]
        assert fql_seeds == list(range(42, 52))

    def test_corpus_labels_match_spec_item_16(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        corpus_labels = [r.label for r in plan if r.phase == "corpus"]
        assert corpus_labels == [
            "strict_43", "strict_44", "strict_45", "strict_46",
            "disabled_43", "disabled_44", "disabled_45", "disabled_46",
            "placebo_42", "placebo_43", "placebo_44", "placebo_45", "placebo_46",
            "silent_42", "silent_43", "silent_44", "silent_45", "silent_46",
            "feasibility_only_42",
        ]

    def test_all_labels_unique(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        labels = [r.label for r in plan]
        assert len(labels) == len(set(labels))

    def test_fql_command_matches_spec_7_5(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        run = next(r for r in plan if r.label == "fql_seed42")
        assert run.command[:2] == [launcher._PYTHON, "examples/irrigation_abm/run_fql_baseline.py"]
        for token in ("--real", "--no-governance", "--fql-init", "calibrated", "--years", "42"):
            assert token in run.command
        assert run.command[run.command.index("--seed") + 1] == "42"
        assert "--output" in run.command
        assert not run.is_llm

    def test_fql_command_never_carries_llm_only_flags(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        for run in (r for r in plan if r.phase in ("fql", "replays")):
            assert "--llm-journal" not in run.command
            assert "--workers" not in run.command
            assert "--governance-mode" not in run.command

    def test_replay_command_writes_both_a_and_b_from_one_call(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        run = next(r for r in plan if r.label == "replays_ab")
        assert run.command[:3] == [
            launcher._PYTHON, "examples/irrigation_abm/analysis/v3_metrics.py", "replay",
        ]
        assert "--real" in run.command
        assert run.command[run.command.index("--seed") + 1] == "42"
        assert run.output_dir.name == "v3_replays_deadbeef"
        assert not run.is_llm

    def test_pilot_commands_use_seed_42_strict_and_disabled(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        strict = next(r for r in plan if r.label == "pilot_strict_42")
        disabled = next(r for r in plan if r.label == "pilot_disabled_42")
        assert strict.command[strict.command.index("--governance-mode") + 1] == "strict"
        assert disabled.command[disabled.command.index("--governance-mode") + 1] == "disabled"
        for run in (strict, disabled):
            assert run.command[run.command.index("--seed") + 1] == "42"
            assert "--retry-feedback-mode" not in run.command
            assert run.is_llm

    def test_llm_runs_carry_llm_journal_and_given_workers(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 7)
        for run in plan:
            if run.is_llm:
                assert "--llm-journal" in run.command
                assert run.command[run.command.index("--workers") + 1] == "7"
                assert run.command[run.command.index("--model") + 1] == "gemma3:4b"
                assert run.command[run.command.index("--years") + 1] == "42"

    def test_placebo_and_silent_are_strict_governance_with_retry_feedback_mode(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 1)
        placebo = next(r for r in plan if r.label == "placebo_44")
        assert placebo.command[placebo.command.index("--governance-mode") + 1] == "strict"
        assert placebo.command[placebo.command.index("--retry-feedback-mode") + 1] == "placebo"
        silent = next(r for r in plan if r.label == "silent_44")
        assert silent.command[silent.command.index("--governance-mode") + 1] == "strict"
        assert silent.command[silent.command.index("--retry-feedback-mode") + 1] == "silent"

    def test_feasibility_only_uses_its_own_governance_mode_and_no_retry_feedback_mode(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 1)
        run = next(r for r in plan if r.label == "feasibility_only_42")
        assert run.command[run.command.index("--governance-mode") + 1] == "feasibility_only"
        assert "--retry-feedback-mode" not in run.command

    def test_output_dir_naming_matches_spec_7_5(self):
        plan = launcher.build_plan(Path("R"), "ab12cd34", 1)
        strict43 = next(r for r in plan if r.label == "strict_43")
        assert strict43.output_dir.name == "v3_strict_42yr_gemma3_4b_ab12cd34_seed43"
        fo = next(r for r in plan if r.label == "feasibility_only_42")
        assert fo.output_dir.name == "v3_feasibility_only_42yr_gemma3_4b_ab12cd34_seed42"

    def test_results_root_is_used_directly_not_nested_under_repo(self):
        root = Path("C:/somewhere/else")
        plan = launcher.build_plan(root, "deadbeef", 1)
        for run in plan:
            assert launcher._REPO_ROOT not in run.output_dir.parents
            assert str(run.output_dir).startswith(str(root))

    def test_workers_placeholder_string_is_accepted_for_display(self):
        """cmd_plan passes a descriptive placeholder, not an int, when no
        workers value is known yet (item 12). build_plan must accept it
        without error, embedding it verbatim."""
        plan = launcher.build_plan(Path("R"), "deadbeef", "N (set at the first GPU launch)")
        llm_run = next(r for r in plan if r.is_llm)
        assert llm_run.command[llm_run.command.index("--workers") + 1] == "N (set at the first GPU launch)"


class TestCommandsUseSysExecutable:
    """Opus review item 9: every generated command must use sys.executable
    (the launcher's own interpreter), never the bare string "python"."""

    def test_every_command_starts_with_sys_executable(self):
        plan = launcher.build_plan(Path("R"), "deadbeef", 4)
        for run in plan:
            assert run.command[0] == launcher._PYTHON
            assert run.command[0] == sys.executable
            assert run.command[0] != "python"


# =============================================================================
# Python interpreter version guard (item 9)
# =============================================================================

class TestPythonVersionGuard:
    def test_passes_on_the_real_interpreter_this_suite_runs_under(self):
        # This suite itself only runs under the corpus interpreter (3.14),
        # so this must never raise here.
        launcher.assert_correct_interpreter()

    def test_refuses_when_required_python_does_not_match_actual(self, monkeypatch):
        monkeypatch.setattr(launcher, "_REQUIRED_PYTHON", (3, 99))
        with pytest.raises(SystemExit, match=r"Python 3\.99"):
            launcher.assert_correct_interpreter()

    def test_run_refuses_before_anything_else_on_wrong_interpreter(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        monkeypatch.setattr(launcher, "_REQUIRED_PYTHON", (3, 99))
        with pytest.raises(SystemExit, match=r"Python 3\.99"):
            launcher.main([
                "run", "fql", "--tag", "v-test",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_state_records_interpreter_path_and_version(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        state_dir = tmp_path / "state"
        monkeypatch.setattr(
            launcher, "_popen_detached",
            lambda argv, *, cwd, log_path: types.SimpleNamespace(pid=1),
        )
        launcher.main([
            "run", "fql", "--tag", "v-test",
            "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
        ])
        state = launcher.load_state(state_dir)
        assert state["python_executable"] == sys.executable
        assert state["python_version"] == f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"


# =============================================================================
# run_status_for_dir / run_status_for_plan_entry
# =============================================================================

class TestRunStatus:
    def test_pending_when_dir_missing(self, tmp_path):
        assert launcher.run_status_for_dir(tmp_path / "nope") == "pending"

    def test_pending_when_dir_empty(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert launcher.run_status_for_dir(d) == "pending"

    def test_done_when_manifest_present_and_run_status_absent_not_llm(self, tmp_path):
        """Non-LLM (FQL / replay) runs keep the simple manifest-only check:
        they never write run_integrity.json, so item 3(b)'s stricter rule
        does not apply to them."""
        d = tmp_path / "run"
        d.mkdir()
        (d / "reproducibility_manifest.json").write_text(json.dumps({"seed": 42}), encoding="utf-8")
        assert launcher.run_status_for_dir(d, is_llm=False) == "done"

    @pytest.mark.parametrize("status", [
        "aborted_llm_failure_rate", "aborted_journal_divergence",
        "aborted_journal_write_error", "aborted_exception",
    ])
    def test_crashed_when_manifest_run_status_aborted(self, tmp_path, status):
        d = tmp_path / "run"
        d.mkdir()
        (d / "reproducibility_manifest.json").write_text(json.dumps({"run_status": status}), encoding="utf-8")
        assert launcher.run_status_for_dir(d) == "crashed"
        assert launcher.run_status_for_dir(d, is_llm=True) == "crashed"

    def test_crashed_when_journal_present_but_no_manifest_and_no_record(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        assert launcher.run_status_for_dir(d) == "crashed"

    def test_crashed_when_partial_output_but_no_manifest_or_journal(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "simulation_log.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        assert launcher.run_status_for_dir(d) == "crashed"

    def test_crashed_when_manifest_malformed(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "reproducibility_manifest.json").write_text("{not valid json", encoding="utf-8")
        assert launcher.run_status_for_dir(d) == "crashed"


class TestRunStatusLlmStrictDone:
    """Opus review item 3(b): an LLM run's manifest alone (clean
    run_status) is not enough for "done" -- _finalize_experiment writes it
    unconditionally in a `finally` on any exit path. Needs EITHER this
    launcher's own recorded exit 0, OR run_integrity.json showing every
    configured row and year actually written."""

    def _clean_manifest_dir(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "reproducibility_manifest.json").write_text(json.dumps({"seed": 42}), encoding="utf-8")
        return d

    def test_clean_manifest_alone_is_not_done_for_an_llm_run(self, tmp_path):
        d = self._clean_manifest_dir(tmp_path)
        assert launcher.run_status_for_dir(d, is_llm=True) == "crashed"

    def test_done_via_recorded_exit_zero(self, tmp_path):
        d = self._clean_manifest_dir(tmp_path)
        record = {"pid": 123, "returncode": 0}
        assert launcher.run_status_for_dir(d, is_llm=True, record=record) == "done"

    def test_not_done_via_recorded_nonzero_exit_even_with_clean_manifest(self, tmp_path):
        d = self._clean_manifest_dir(tmp_path)
        record = {"pid": 123, "returncode": 1}
        assert launcher.run_status_for_dir(d, is_llm=True, record=record) == "crashed"

    def test_done_via_run_integrity_when_no_record_available(self, tmp_path):
        d = self._clean_manifest_dir(tmp_path)
        (d / "run_integrity.json").write_text(
            json.dumps({"audit_rows_missing_vs_configured_grid": 0, "audit_years": 42}),
            encoding="utf-8",
        )
        assert launcher.run_status_for_dir(d, is_llm=True, record=None) == "done"

    def test_not_done_when_run_integrity_shows_missing_rows(self, tmp_path):
        d = self._clean_manifest_dir(tmp_path)
        (d / "run_integrity.json").write_text(
            json.dumps({"audit_rows_missing_vs_configured_grid": 42, "audit_years": 9}),
            encoding="utf-8",
        )
        assert launcher.run_status_for_dir(d, is_llm=True, record=None) == "crashed"

    def test_not_done_when_run_integrity_missing_entirely(self, tmp_path):
        d = self._clean_manifest_dir(tmp_path)
        assert launcher.run_status_for_dir(d, is_llm=True, record=None) == "crashed"


class TestRunStatusRunning:
    """Opus review item 2 + item 4: a run with a journal but no manifest
    yet is "running" (not "crashed") when the launcher's own record shows
    a PID that is a live python.exe naming this run's own --output dir
    (mocked via `_process_command_line`, item 4's one shell-out point)."""

    def test_running_when_pid_is_alive_and_no_exit_recorded(self, monkeypatch, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        _mock_liveness(monkeypatch, {4242: str(d)})
        record = {"pid": 4242, "returncode": None}
        assert launcher.run_status_for_dir(d, is_llm=True, record=record) == "running"

    def test_crashed_when_recorded_pid_is_not_alive(self, monkeypatch, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        _mock_all_dead(monkeypatch)
        record = {"pid": 999999999, "returncode": None}
        assert launcher.run_status_for_dir(d, is_llm=True, record=record) == "crashed"

    def test_crashed_when_pid_alive_but_command_line_names_a_different_dir(self, monkeypatch, tmp_path):
        """Item 4: a bare PID match is not enough -- Windows recycles
        PIDs, so a live python.exe that does NOT name THIS run's own
        --output directory must not count as this run being alive."""
        d = tmp_path / "run"
        d.mkdir()
        (d / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        _mock_liveness(monkeypatch, {4242: str(tmp_path / "some_other_run")})
        record = {"pid": 4242, "returncode": None}
        assert launcher.run_status_for_dir(d, is_llm=True, record=record) == "crashed"

    def test_crashed_once_exit_is_recorded_even_if_pid_reused_by_something_else(self, monkeypatch, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        _mock_liveness(monkeypatch, {4242: str(d)})
        record = {"pid": 4242, "returncode": 1}
        assert launcher.run_status_for_dir(d, is_llm=True, record=record) == "crashed"


class TestReplayPlanEntryStatus:
    def _replay_run(self, out_dir):
        return launcher.PlannedRun("replays_ab", "replays", [], out_dir, False)

    def test_pending_when_neither_a_nor_b_started(self, tmp_path):
        run = self._replay_run(tmp_path / "replays")
        assert launcher.run_status_for_plan_entry(run) == "pending"

    def test_crashed_when_only_a_is_done(self, tmp_path):
        out = tmp_path / "replays"
        (out / "A").mkdir(parents=True)
        (out / "A" / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
        run = self._replay_run(out)
        assert launcher.run_status_for_plan_entry(run) == "crashed"

    def test_done_when_both_a_and_b_are_done(self, tmp_path):
        out = tmp_path / "replays"
        for kind in ("A", "B"):
            (out / kind).mkdir(parents=True)
            (out / kind / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
        run = self._replay_run(out)
        assert launcher.run_status_for_plan_entry(run) == "done"


class TestResumeChainAwareStatus:
    """Opus review item 4(a): an LLM plan entry's status is resolved
    against the LATEST attempt in its own resume chain, so a finished
    `_resumeN` directory counts as the run's own completion."""

    def _llm_run(self, out_dir):
        return launcher.PlannedRun("strict_43", "corpus", [], out_dir, True)

    def test_done_when_base_crashed_but_resume1_is_done(self, tmp_path, state_dir=None):
        state_dir = tmp_path / "state"
        base = tmp_path / "results" / "v3_strict_run"
        base.mkdir(parents=True)
        (base / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        resume1 = base.parent / f"{base.name}_resume1"
        resume1.mkdir()
        (resume1 / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
        launcher.write_run_record(state_dir, "strict_43_resume1", {"pid": 1, "returncode": 0})

        run = self._llm_run(base)
        assert launcher.run_status_for_plan_entry(run, state_dir) == "done"

    def test_crashed_points_at_latest_attempt_not_the_original(self, monkeypatch, tmp_path):
        """base is crashed AND resume1 is ALSO crashed: the overall status
        must still read "crashed" (from resume1, the latest attempt), not
        accidentally read the base's own status in a way that would hide
        resume1 ever having been attempted."""
        state_dir = tmp_path / "state"
        base = tmp_path / "results" / "v3_strict_run"
        base.mkdir(parents=True)
        (base / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        resume1 = base.parent / f"{base.name}_resume1"
        resume1.mkdir()
        (resume1 / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        launcher.write_run_record(state_dir, "strict_43_resume1", {"pid": 999999999, "returncode": None})
        _mock_all_dead(monkeypatch)

        run = self._llm_run(base)
        assert launcher.run_status_for_plan_entry(run, state_dir) == "crashed"

    def test_running_when_resume1_is_live(self, monkeypatch, tmp_path):
        state_dir = tmp_path / "state"
        base = tmp_path / "results" / "v3_strict_run"
        base.mkdir(parents=True)
        (base / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        resume1 = base.parent / f"{base.name}_resume1"
        resume1.mkdir()
        (resume1 / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        launcher.write_run_record(state_dir, "strict_43_resume1", {"pid": 4242, "returncode": None})
        _mock_liveness(monkeypatch, {4242: str(resume1)})

        run = self._llm_run(base)
        assert launcher.run_status_for_plan_entry(run, state_dir) == "running"


# =============================================================================
# Workers-consistency guard
# =============================================================================

class TestWorkersGuard:
    def test_first_call_records(self):
        state = {}
        launcher.check_and_record_workers(state, 4)
        assert state["workers"] == 4

    def test_matching_call_is_a_noop(self):
        state = {"workers": 4}
        launcher.check_and_record_workers(state, 4)
        assert state["workers"] == 4

    def test_mismatch_is_refused(self):
        state = {"workers": 4}
        with pytest.raises(SystemExit, match="workers"):
            launcher.check_and_record_workers(state, 1)


class TestPilotPairManifestWorkers:
    """Opus review item 6: cross-checks --workers against the pilot pair's
    OWN recorded workers, independent of (and in addition to) state.json."""

    def _write_pilot_manifest(self, results_root, sha8, label, workers):
        plan = launcher.build_plan(results_root, sha8, 1)
        run = next(r for r in plan if r.label == label)
        run.output_dir.mkdir(parents=True, exist_ok=True)
        (run.output_dir / "reproducibility_manifest.json").write_text(
            json.dumps({"workers": workers}), encoding="utf-8",
        )
        # Item 3: pilot_pair_manifest_workers now resolves through
        # latest_done_attempt_dir, which (for an LLM run, item 3(b)) needs
        # run_integrity.json too, not only a clean manifest.
        (run.output_dir / "run_integrity.json").write_text(
            json.dumps(_done_run_integrity()), encoding="utf-8",
        )

    def test_none_when_neither_pilot_manifest_exists(self, tmp_path):
        assert launcher.pilot_pair_manifest_workers(tmp_path / "results", "deadbeef") is None

    def test_reads_the_common_value_when_both_agree(self, tmp_path):
        results_root = tmp_path / "results"
        self._write_pilot_manifest(results_root, "deadbeef", "pilot_strict_42", 4)
        self._write_pilot_manifest(results_root, "deadbeef", "pilot_disabled_42", 4)
        assert launcher.pilot_pair_manifest_workers(results_root, "deadbeef") == 4

    def test_raises_when_the_pilot_pair_disagrees_with_itself(self, tmp_path):
        results_root = tmp_path / "results"
        self._write_pilot_manifest(results_root, "deadbeef", "pilot_strict_42", 4)
        self._write_pilot_manifest(results_root, "deadbeef", "pilot_disabled_42", 1)
        with pytest.raises(SystemExit, match="disagree"):
            launcher.pilot_pair_manifest_workers(results_root, "deadbeef")


# =============================================================================
# Git preflight (real throwaway temp repos; no Ollama, no network)
# =============================================================================

class TestPreflight:
    def test_passes_on_clean_tree_at_tag(self, git_repo):
        repo, _git = git_repo
        sha8 = launcher.preflight_for_tag("v-test", repo)
        assert len(sha8) == 8

    def test_refuses_dirty_tree(self, git_repo):
        repo, _git = git_repo
        (repo / "dirty.txt").write_text("x", encoding="utf-8")
        with pytest.raises(SystemExit, match="porcelain"):
            launcher.preflight_for_tag("v-test", repo)

    def test_refuses_head_not_at_tag(self, git_repo):
        repo, _git = git_repo
        (repo / "two.txt").write_text("x", encoding="utf-8")
        _git("add", "two.txt")
        _git("commit", "-m", "second")
        with pytest.raises(SystemExit, match="does not match tag"):
            launcher.preflight_for_tag("v-test", repo)

    def test_refuses_unknown_tag(self, git_repo):
        repo, _git = git_repo
        with pytest.raises(SystemExit, match="did not resolve"):
            launcher.preflight_for_tag("no-such-tag", repo)

    def test_run_subcommand_refuses_on_dirty_tree(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        (repo / "dirty.txt").write_text("x", encoding="utf-8")
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="porcelain"):
            launcher.main([
                "run", "fql", "--tag", "v-test",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_gate_subcommand_refuses_on_dirty_tree(self, monkeypatch, tmp_path, git_repo):
        """Opus review item 10: gate must preflight too, not only run/resume."""
        repo, _git = git_repo
        (repo / "dirty.txt").write_text("x", encoding="utf-8")
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="porcelain"):
            launcher.main([
                "gate", "--tag", "v-test",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])


# =============================================================================
# Detached process launching: assert the creationflags, never a real spawn
# =============================================================================

class TestPopenDetached:
    def test_uses_detached_process_only_never_new_process_group(self, monkeypatch, tmp_path):
        captured = {}

        def _fake_popen(argv, **kwargs):
            captured["argv"] = argv
            captured.update(kwargs)
            return types.SimpleNamespace(pid=999)

        monkeypatch.setattr(launcher.subprocess, "Popen", _fake_popen)
        proc = launcher._popen_detached(
            [launcher._PYTHON, "-c", "pass"], cwd=tmp_path, log_path=tmp_path / "logs" / "x.log",
        )

        assert proc.pid == 999
        flags = captured["creationflags"]
        assert flags & launcher.subprocess.DETACHED_PROCESS
        new_group = getattr(launcher.subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        assert new_group == 0 or not (flags & new_group)
        assert captured["stdin"] == launcher.subprocess.DEVNULL
        assert captured["stderr"] == launcher.subprocess.STDOUT
        assert captured["close_fds"] is True

    def test_log_parent_directory_is_created(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            launcher.subprocess, "Popen",
            lambda *a, **kw: types.SimpleNamespace(pid=1),
        )
        log_path = tmp_path / "nested" / "dir" / "x.log"
        launcher._popen_detached([launcher._PYTHON, "-c", "pass"], cwd=tmp_path, log_path=log_path)
        assert log_path.parent.is_dir()


# =============================================================================
# run_chain: sequential execution, stop at first failure, no retry, and
# per-run PID/exit records (item 2), CREATE_NO_WINDOW (item 7)
# =============================================================================

class TestRunChain:
    def _write_spec(self, tmp_path, state_dir, runs):
        spec = {
            "chain": "corpus", "cwd": str(tmp_path),
            "log": str(state_dir / "logs" / "chain.log"),
            "state_dir": str(state_dir),
            "runs": runs,
        }
        spec_path = tmp_path / "spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        return spec_path

    def _entries(self, tmp_path, labels):
        return [
            {"label": label, "command": [launcher._PYTHON, "-c", "pass"], "output_dir": str(tmp_path / label)}
            for label in labels
        ]

    def test_stops_at_first_failure_never_runs_later_commands(self, monkeypatch, tmp_path):
        state_dir = tmp_path / "state"
        spec_path = self._write_spec(tmp_path, state_dir, self._entries(tmp_path, ["a", "b", "c"]))
        calls = []
        monkeypatch.setattr(launcher.subprocess, "Popen", _fake_chain_popen([0, 1], calls))

        rc = launcher.run_chain(spec_path)

        assert rc == 1
        assert len(calls) == 2

    def test_all_succeed_returns_zero(self, monkeypatch, tmp_path):
        state_dir = tmp_path / "state"
        spec_path = self._write_spec(tmp_path, state_dir, self._entries(tmp_path, ["a", "b"]))
        calls = []
        monkeypatch.setattr(launcher.subprocess, "Popen", _fake_chain_popen([0, 0], calls))

        assert launcher.run_chain(spec_path) == 0
        assert len(calls) == 2

    def test_children_use_create_no_window(self, monkeypatch, tmp_path):
        state_dir = tmp_path / "state"
        spec_path = self._write_spec(tmp_path, state_dir, self._entries(tmp_path, ["a"]))
        captured = {}

        def _popen(cmd, cwd=None, stdout=None, stderr=None, stdin=None, creationflags=None):
            captured["creationflags"] = creationflags
            captured["stderr"] = stderr
            return _FakePopen(1, 0)

        monkeypatch.setattr(launcher.subprocess, "Popen", _popen)
        launcher.run_chain(spec_path)

        assert captured["creationflags"] == getattr(launcher.subprocess, "CREATE_NO_WINDOW", 0)
        assert captured["stderr"] == launcher.subprocess.STDOUT

    def test_writes_pid_before_wait_and_exit_code_after(self, monkeypatch, tmp_path):
        state_dir = tmp_path / "state"
        spec_path = self._write_spec(tmp_path, state_dir, self._entries(tmp_path, ["strict_43"]))
        monkeypatch.setattr(launcher.subprocess, "Popen", _fake_chain_popen([0]))

        launcher.run_chain(spec_path)

        record = launcher.read_run_record(state_dir, "strict_43")
        assert record["pid"] == 1000
        assert record["returncode"] == 0
        assert "started_at" in record
        assert "exited_at" in record

    def test_failed_run_record_shows_nonzero_returncode(self, monkeypatch, tmp_path):
        state_dir = tmp_path / "state"
        spec_path = self._write_spec(tmp_path, state_dir, self._entries(tmp_path, ["strict_43"]))
        monkeypatch.setattr(launcher.subprocess, "Popen", _fake_chain_popen([1]))

        launcher.run_chain(spec_path)

        record = launcher.read_run_record(state_dir, "strict_43")
        assert record["returncode"] == 1

    def test_failure_message_says_resume_not_retag(self, monkeypatch, tmp_path):
        """Opus review item 11: a crashed RUN is resumed; re-tagging is
        only for a failed GATE."""
        state_dir = tmp_path / "state"
        spec_path = self._write_spec(tmp_path, state_dir, self._entries(tmp_path, ["strict_43"]))
        monkeypatch.setattr(launcher.subprocess, "Popen", _fake_chain_popen([1]))

        launcher.run_chain(spec_path)

        log_text = (state_dir / "logs" / "chain.log").read_text(encoding="utf-8")
        assert "resume strict_43" in log_text
        assert "FAILED pilot-gate" in log_text


# =============================================================================
# Resume: dir naming + command substitution
# =============================================================================

class TestResumeHelpers:
    def test_resume_chain_dirs_starts_with_just_base(self, tmp_path):
        base = tmp_path / "run_dir"
        assert launcher.resume_chain_dirs(base) == [base]

    def test_resume_chain_dirs_grows_with_each_existing_resume(self, tmp_path):
        base = tmp_path / "run_dir"
        base.mkdir()
        assert launcher.resume_chain_dirs(base) == [base]
        (tmp_path / "run_dir_resume1").mkdir()
        assert launcher.resume_chain_dirs(base) == [base, tmp_path / "run_dir_resume1"]
        (tmp_path / "run_dir_resume2").mkdir()
        assert launcher.resume_chain_dirs(base) == [
            base, tmp_path / "run_dir_resume1", tmp_path / "run_dir_resume2",
        ]

    def test_record_label_for_attempt(self):
        assert launcher.record_label_for_attempt("strict_43", 0) == "strict_43"
        assert launcher.record_label_for_attempt("strict_43", 1) == "strict_43_resume1"
        assert launcher.record_label_for_attempt("strict_43", 2) == "strict_43_resume2"

    def test_build_resume_command_substitutes_output_and_workers_and_appends_resume_from(self):
        original = [
            launcher._PYTHON, "examples/irrigation_abm/run_experiment.py", "--real",
            "--model", "gemma3:4b", "--output", "OLDDIR", "--llm-journal", "--workers", "4",
        ]
        crashed = Path("OLDDIR")
        new_out = Path("OLDDIR_resume1")

        cmd = launcher.build_resume_command(original, crashed_dir=crashed, new_output=new_out, workers=2)

        assert cmd[cmd.index("--output") + 1] == str(new_out)
        assert cmd[cmd.index("--workers") + 1] == "2"
        assert cmd[-2:] == ["--resume-from", str(crashed)]
        # original list is untouched
        assert original[original.index("--output") + 1] == "OLDDIR"
        assert original[original.index("--workers") + 1] == "4"


class TestCmdResume:
    def _seed_crashed_run(self, results_root, sha8, label="strict_43", workers=4):
        plan = launcher.build_plan(results_root, sha8, workers)
        run = next(r for r in plan if r.label == label)
        run.output_dir.mkdir(parents=True)
        (run.output_dir / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        return run

    def test_resume_launches_into_new_dir_and_never_touches_crashed_dir(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]

        crashed = self._seed_crashed_run(results_root, sha8)
        launcher.save_state(state_dir, {
            "workers": 4, "tag": "v-test", "sha8": sha8,
            "pilot_gate": {"passed": True, "sha8": sha8},
        })

        captured = {}

        def _fake_popen_detached(argv, *, cwd, log_path):
            captured["argv"] = argv
            captured["cwd"] = cwd
            return types.SimpleNamespace(pid=4242)

        monkeypatch.setattr(launcher, "_popen_detached", _fake_popen_detached)

        rc = launcher.main([
            "resume", "strict_43", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        assert rc == 0
        # the crashed directory must contain exactly what it did before: resume
        # never writes into it.
        assert {p.name for p in crashed.output_dir.iterdir()} == {"llm_journal.jsonl"}

        spec_path = Path(captured["argv"][-1])
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        assert len(spec["runs"]) == 1
        resumed_cmd = spec["runs"][0]["command"]
        assert resumed_cmd[resumed_cmd.index("--resume-from") + 1] == str(crashed.output_dir)
        new_out = Path(resumed_cmd[resumed_cmd.index("--output") + 1])
        assert new_out == crashed.output_dir.parent / f"{crashed.output_dir.name}_resume1"
        assert spec["runs"][0]["label"] == "strict_43_resume1"

    def test_resume_refuses_a_run_that_is_pending(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        launcher.save_state(state_dir, {"workers": 4, "pilot_gate": {"passed": True, "sha8": sha8}})
        # strict_43's output dir does not exist at all: no journal anywhere
        # in its resume chain (item 2(d)).

        with pytest.raises(SystemExit, match="no journal"):
            launcher.main([
                "resume", "strict_43", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(results_root), "--state-dir", str(state_dir),
            ])

    def test_resume_refuses_a_run_that_is_still_running(self, monkeypatch, tmp_path, git_repo):
        """Opus review item 2: a live process (journal, no manifest, a
        recorded PID that is still alive) must never be resumed, which
        would start a second GPU process on the same output dir."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        crashed = self._seed_crashed_run(results_root, sha8)  # really "running" once recorded below
        launcher.write_run_record(state_dir, "strict_43", {"pid": 4242, "returncode": None})
        _mock_liveness(monkeypatch, {4242: str(crashed.output_dir)})
        launcher.save_state(state_dir, {"workers": 4, "pilot_gate": {"passed": True, "sha8": sha8}})

        with pytest.raises(SystemExit, match="running"):
            launcher.main([
                "resume", "strict_43", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(results_root), "--state-dir", str(state_dir),
            ])

    def test_second_resume_starts_from_the_latest_crashed_dir_not_the_original(
        self, monkeypatch, tmp_path, git_repo,
    ):
        """Opus review item 4(a): resuming a run that has ALREADY been
        resumed once (and crashed again) must relaunch from THAT latest
        crashed attempt, landing in _resume2, never go back to the
        original directory or overwrite _resume1."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]

        base = self._seed_crashed_run(results_root, sha8)
        resume1 = base.output_dir.parent / f"{base.output_dir.name}_resume1"
        resume1.mkdir()
        (resume1 / "llm_journal.jsonl").write_text('{"call": 1}\n', encoding="utf-8")
        launcher.write_run_record(state_dir, "strict_43_resume1", {"pid": 999999999, "returncode": None})
        _mock_all_dead(monkeypatch)
        launcher.save_state(state_dir, {"workers": 4, "pilot_gate": {"passed": True, "sha8": sha8}})

        captured = {}
        monkeypatch.setattr(
            launcher, "_popen_detached",
            lambda argv, *, cwd, log_path: (captured.setdefault("argv", argv), types.SimpleNamespace(pid=1))[1],
        )

        rc = launcher.main([
            "resume", "strict_43", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        assert rc == 0
        spec = json.loads(Path(captured["argv"][-1]).read_text(encoding="utf-8"))
        resumed_cmd = spec["runs"][0]["command"]
        assert resumed_cmd[resumed_cmd.index("--resume-from") + 1] == str(resume1)
        new_out = Path(resumed_cmd[resumed_cmd.index("--output") + 1])
        assert new_out == base.output_dir.parent / f"{base.output_dir.name}_resume2"
        # base (the original) must be completely untouched.
        assert {p.name for p in base.output_dir.iterdir()} == {"llm_journal.jsonl"}

    def test_resume_refuses_a_non_llm_label(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="not an LLM run"):
            launcher.main([
                "resume", "fql_seed42", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_resume_refuses_without_confirm_gpu(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="confirm-gpu"):
            launcher.main([
                "resume", "strict_43", "--tag", "v-test", "--workers", "4",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_resume_refuses_workers_mismatch_against_state(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        state_dir = tmp_path / "s"
        launcher.save_state(state_dir, {"workers": 1})
        with pytest.raises(SystemExit, match="workers"):
            launcher.main([
                "resume", "strict_43", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
            ])

    def test_resume_refuses_workers_mismatch_against_pilot_pair_manifest(
        self, monkeypatch, tmp_path, git_repo,
    ):
        """Opus review item 6: state.json alone is not authoritative --
        the pilot pair's OWN recorded workers is cross-checked too, for
        resume as well as 'run corpus'."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        plan = launcher.build_plan(results_root, sha8, 1)
        for label in ("pilot_strict_42", "pilot_disabled_42"):
            run = next(r for r in plan if r.label == label)
            run.output_dir.mkdir(parents=True)
            (run.output_dir / "reproducibility_manifest.json").write_text(
                json.dumps({"workers": 4}), encoding="utf-8",
            )
            (run.output_dir / "run_integrity.json").write_text(
                json.dumps(_done_run_integrity()), encoding="utf-8",
            )
        self._seed_crashed_run(results_root, sha8)
        # state.json has no prior "workers" at all, so check_and_record_workers
        # alone would happily accept 1 -- the manifest cross-check must still catch it.
        launcher.save_state(state_dir, {"pilot_gate": {"passed": True, "sha8": sha8}})

        with pytest.raises(SystemExit, match="workers"):
            launcher.main([
                "resume", "strict_43", "--tag", "v-test", "--workers", "1", "--confirm-gpu",
                "--results-root", str(results_root), "--state-dir", str(state_dir),
            ])


# =============================================================================
# run <phase>: refusals
# =============================================================================

class TestCmdRunRefusals:
    def test_pilot_refuses_without_confirm_gpu(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="confirm-gpu"):
            launcher.main([
                "run", "pilot", "--tag", "v-test", "--workers", "4",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_pilot_refuses_without_workers(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="workers"):
            launcher.main([
                "run", "pilot", "--tag", "v-test", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_pilot_refuses_when_fql_or_replays_not_done(self, monkeypatch, tmp_path, git_repo):
        """Opus review item 5."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="not done yet"):
            launcher.main([
                "run", "pilot", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_corpus_refuses_without_passing_gate(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="gate"):
            launcher.main([
                "run", "corpus", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_corpus_refuses_when_gate_passed_for_a_different_commit(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        state_dir = tmp_path / "s"
        launcher.save_state(state_dir, {"workers": 4, "pilot_gate": {"passed": True, "sha8": "stalecommit"}})
        with pytest.raises(SystemExit, match="gate"):
            launcher.main([
                "run", "corpus", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
            ])

    def test_corpus_refuses_workers_mismatch_against_state(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        state_dir = tmp_path / "s"
        launcher.save_state(state_dir, {"workers": 1})
        with pytest.raises(SystemExit, match="workers"):
            launcher.main([
                "run", "corpus", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
            ])

    def test_corpus_refuses_workers_mismatch_against_pilot_pair_manifest(
        self, monkeypatch, tmp_path, git_repo,
    ):
        """Opus review item 6, for 'run corpus' (mirrors the resume test)."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        plan = launcher.build_plan(results_root, sha8, 1)
        for label in ("pilot_strict_42", "pilot_disabled_42"):
            run = next(r for r in plan if r.label == label)
            run.output_dir.mkdir(parents=True)
            (run.output_dir / "reproducibility_manifest.json").write_text(
                json.dumps({"workers": 4}), encoding="utf-8",
            )
            (run.output_dir / "run_integrity.json").write_text(
                json.dumps(_done_run_integrity()), encoding="utf-8",
            )
        launcher.save_state(state_dir, {"pilot_gate": {"passed": True, "sha8": sha8}})

        with pytest.raises(SystemExit, match="workers"):
            launcher.main([
                "run", "corpus", "--tag", "v-test", "--workers", "1", "--confirm-gpu",
                "--results-root", str(results_root), "--state-dir", str(state_dir),
            ])

    def test_fql_and_replays_need_neither_confirm_gpu_nor_workers(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        monkeypatch.setattr(
            launcher, "_popen_detached",
            lambda argv, *, cwd, log_path: types.SimpleNamespace(pid=1),
        )
        for phase in ("fql", "replays"):
            rc = launcher.main([
                "run", phase, "--tag", "v-test",
                "--results-root", str(tmp_path / f"r_{phase}"), "--state-dir", str(tmp_path / f"s_{phase}"),
            ])
            assert rc == 0


# =============================================================================
# run <phase>: happy paths (fully mocked launch)
# =============================================================================

class TestCmdRunHappyPaths:
    def _seed_fql_and_replays_done(self, results_root, sha8, state_dir):
        plan = launcher.build_plan(results_root, sha8, 1)
        for run in plan:
            if run.phase == "fql":
                run.output_dir.mkdir(parents=True, exist_ok=True)
                (run.output_dir / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
            if run.label == "replays_ab":
                for kind in ("A", "B"):
                    (run.output_dir / kind).mkdir(parents=True, exist_ok=True)
                    (run.output_dir / kind / "reproducibility_manifest.json").write_text(
                        "{}", encoding="utf-8",
                    )

    def test_run_fql_launches_all_ten_and_records_state(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"

        captured = {}

        def _fake_popen_detached(argv, *, cwd, log_path):
            captured["argv"] = argv
            captured["cwd"] = cwd
            return types.SimpleNamespace(pid=12345)

        monkeypatch.setattr(launcher, "_popen_detached", _fake_popen_detached)

        rc = launcher.main([
            "run", "fql", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        assert rc == 0
        assert captured["argv"][0] == sys.executable
        assert captured["argv"][1] == str(launcher._THIS_FILE)
        assert captured["argv"][2] == "_run-chain"
        spec = json.loads(Path(captured["argv"][-1]).read_text(encoding="utf-8"))
        assert len(spec["runs"]) == 10

        state = launcher.load_state(state_dir)
        assert state["tag"] == "v-test"
        assert len(state["sha8"]) == 8
        assert state["launches"][0]["phase"] == "fql"
        assert state["launches"][0]["pid"] == 12345

    def test_run_pilot_records_workers_and_launches_two(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "r"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        self._seed_fql_and_replays_done(results_root, sha8, state_dir)

        captured = {}
        monkeypatch.setattr(
            launcher, "_popen_detached",
            lambda argv, *, cwd, log_path: (captured.setdefault("argv", argv), types.SimpleNamespace(pid=1))[1],
        )

        rc = launcher.main([
            "run", "pilot", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        assert rc == 0
        spec = json.loads(Path(captured["argv"][-1]).read_text(encoding="utf-8"))
        assert len(spec["runs"]) == 2
        assert launcher.load_state(state_dir)["workers"] == 4

    def test_run_corpus_succeeds_after_a_passing_gate_for_the_same_commit(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        state_dir = tmp_path / "state"
        launcher.save_state(state_dir, {
            "workers": 4, "tag": "v-test", "sha8": sha8,
            "pilot_gate": {"passed": True, "sha8": sha8},
        })
        captured = {}
        monkeypatch.setattr(
            launcher, "_popen_detached",
            lambda argv, *, cwd, log_path: (captured.setdefault("argv", argv), types.SimpleNamespace(pid=1))[1],
        )

        rc = launcher.main([
            "run", "corpus", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
            "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
        ])

        assert rc == 0
        spec = json.loads(Path(captured["argv"][-1]).read_text(encoding="utf-8"))
        assert len(spec["runs"]) == 19

    def test_run_skips_done_and_crashed_and_running_entries_launching_only_pending(
        self, monkeypatch, tmp_path, git_repo, capsys,
    ):
        """Opus review item 1: a done/crashed/running entry must never be
        relaunched; only PENDING entries go into the chain, and the
        skipped ones are printed with why."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]

        plan = launcher.build_plan(results_root, sha8, 1)
        fql_runs = [r for r in plan if r.phase == "fql"]
        done_run = fql_runs[0]
        done_run.output_dir.mkdir(parents=True)
        (done_run.output_dir / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
        crashed_run = fql_runs[1]
        crashed_run.output_dir.mkdir(parents=True)
        (crashed_run.output_dir / "llm_journal.jsonl").write_text("{}\n", encoding="utf-8")

        captured = {}
        monkeypatch.setattr(
            launcher, "_popen_detached",
            lambda argv, *, cwd, log_path: (captured.setdefault("argv", argv), types.SimpleNamespace(pid=1))[1],
        )

        rc = launcher.main([
            "run", "fql", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        assert rc == 0
        spec = json.loads(Path(captured["argv"][-1]).read_text(encoding="utf-8"))
        assert len(spec["runs"]) == 8  # 10 - done - crashed
        launched_labels = {r["label"] for r in spec["runs"]}
        assert done_run.label not in launched_labels
        assert crashed_run.label not in launched_labels

        out = capsys.readouterr().out
        assert f"skipping {done_run.label}" in out
        assert f"skipping {crashed_run.label}" in out

    def test_run_prints_nothing_pending_and_launches_nothing_when_all_done(
        self, monkeypatch, tmp_path, git_repo,
    ):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]

        plan = launcher.build_plan(results_root, sha8, 1)
        for run in plan:
            if run.phase == "fql":
                run.output_dir.mkdir(parents=True)
                (run.output_dir / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")

        def _fail_if_called(*a, **kw):
            raise AssertionError("_popen_detached must not be called when nothing is pending")

        monkeypatch.setattr(launcher, "_popen_detached", _fail_if_called)

        rc = launcher.main([
            "run", "fql", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])
        assert rc == 0


# =============================================================================
# gate
# =============================================================================

class TestCmdGate:
    def _mark_done(self, run):
        run.output_dir.mkdir(parents=True, exist_ok=True)
        (run.output_dir / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
        if run.is_llm:
            # Item 3(b): an LLM run needs run_integrity (or a recorded exit
            # 0) to count as "done", not only a clean manifest.
            (run.output_dir / "run_integrity.json").write_text(
                json.dumps({"audit_rows_missing_vs_configured_grid": 0, "audit_years": 42}),
                encoding="utf-8",
            )

    def _seed_prereqs_done(self, results_root, sha8, workers=4):
        plan = launcher.build_plan(results_root, sha8, workers)
        for run in plan:
            if run.label in ("pilot_strict_42", "pilot_disabled_42") or run.phase == "fql":
                self._mark_done(run)
            if run.label == "replays_ab":
                for kind in ("A", "B"):
                    (run.output_dir / kind).mkdir(parents=True, exist_ok=True)
                    (run.output_dir / kind / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
        return plan

    def test_gate_refuses_when_pilot_pair_not_done(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        with pytest.raises(SystemExit, match="not done yet"):
            launcher.main([
                "gate", "--tag", "v-test",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(tmp_path / "s"),
            ])

    def test_gate_refuses_when_fql_or_replays_not_done(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        plan = launcher.build_plan(results_root, sha8, 4)
        for run in plan:
            if run.label in ("pilot_strict_42", "pilot_disabled_42"):
                self._mark_done(run)
        # fql / replays deliberately left undone.
        with pytest.raises(SystemExit, match="not done yet"):
            launcher.main([
                "gate", "--tag", "v-test",
                "--results-root", str(results_root), "--state-dir", str(tmp_path / "s"),
            ])

    def test_gate_runs_p5c_sample_then_pilot_gate_and_records_pass(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        self._seed_prereqs_done(results_root, sha8)
        launcher.save_state(state_dir, {"workers": 4})

        calls = []
        monkeypatch.setattr(launcher.subprocess, "run", _fake_v3_metrics_run(calls))

        rc = launcher.main([
            "gate", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        assert rc == 0
        assert len(calls) == 2
        assert calls[0][2] == "p5c-sample"
        assert calls[1][2] == "pilot-gate"
        state = launcher.load_state(state_dir)
        assert state["pilot_gate"]["passed"] is True
        assert state["pilot_gate"]["sha8"] == sha8

    def test_gate_records_results_root_in_state(self, monkeypatch, tmp_path, git_repo):
        """Opus review item 10."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        self._seed_prereqs_done(results_root, sha8)
        launcher.save_state(state_dir, {"workers": 4})
        monkeypatch.setattr(launcher.subprocess, "run", _fake_v3_metrics_run([]))

        launcher.main([
            "gate", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        state = launcher.load_state(state_dir)
        assert state["pilot_gate"]["results_root"] == str(results_root)

    def test_gate_records_failure_and_returns_nonzero(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        self._seed_prereqs_done(results_root, sha8)
        launcher.save_state(state_dir, {"workers": 4})

        calls = []
        monkeypatch.setattr(
            launcher.subprocess, "run",
            _fake_v3_metrics_run(calls, returncode_for=lambda cmd: 1 if cmd[2] == "pilot-gate" else 0),
        )

        rc = launcher.main([
            "gate", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        assert rc == 1
        assert launcher.load_state(state_dir)["pilot_gate"]["passed"] is False

    def test_gate_prints_notice_when_p5c_review_missing(self, monkeypatch, tmp_path, git_repo, capsys):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        self._seed_prereqs_done(results_root, sha8)
        launcher.save_state(state_dir, {"workers": 4})
        monkeypatch.setattr(launcher.subprocess, "run", _fake_v3_metrics_run([]))

        launcher.main([
            "gate", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        out = capsys.readouterr().out
        assert "P5(c) human review record needed" in out

    def test_gate_passes_p5c_review_through_when_present(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        self._seed_prereqs_done(results_root, sha8)
        launcher.save_state(state_dir, {"workers": 4})

        p5c_dir = results_root / f"v3_pilot_p5c_{sha8}"
        review_path = p5c_dir / "p5c_review.json"

        calls = []

        def _on_call(cmd):
            if cmd[2] == "p5c-sample":
                # p5c-sample itself would create the output dir; the review
                # file is the human's own later addition, created here to
                # simulate "already filled in and saved".
                p5c_dir.mkdir(parents=True, exist_ok=True)
                review_path.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(launcher.subprocess, "run", _fake_v3_metrics_run(calls, on_call=_on_call))

        launcher.main([
            "gate", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        gate_call = calls[1]
        assert "--p5c-review" in gate_call
        assert gate_call[gate_call.index("--p5c-review") + 1] == str(review_path)


# =============================================================================
# Outputs stay outside the worktree
# =============================================================================

class TestOutputsOutsideWorktree:
    def test_default_results_root_is_not_under_the_launcher_repo(self):
        assert launcher._REPO_ROOT not in launcher._DEFAULT_RESULTS_ROOT.parents
        assert "wagf-persona" not in str(launcher._DEFAULT_RESULTS_ROOT).lower()

    def test_default_state_dir_is_the_users_home_not_the_repo(self):
        assert launcher._DEFAULT_STATE_DIR == Path.home() / ".wagf_launcher"
        assert launcher._REPO_ROOT not in launcher._DEFAULT_STATE_DIR.parents

    def test_chain_spec_and_logs_are_written_under_state_dir_not_repo(self, tmp_path):
        plan = launcher.build_plan(tmp_path / "results", "deadbeef", 1)
        log_path = tmp_path / "state" / "logs" / "fql_1.log"
        spec_path = launcher._write_chain_spec(tmp_path / "state", "fql", plan[:2], log_path)
        assert str(spec_path).startswith(str(tmp_path / "state"))
        assert launcher._REPO_ROOT not in spec_path.parents
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        assert spec["log"] == str(log_path)
        assert spec["state_dir"] == str(tmp_path / "state")

    def test_run_records_are_written_under_state_dir(self, tmp_path):
        launcher.write_run_record(tmp_path / "state", "strict_43", {"pid": 1, "returncode": 0})
        path = launcher._run_record_path(tmp_path / "state", "strict_43")
        assert str(path).startswith(str(tmp_path / "state"))
        assert launcher._REPO_ROOT not in path.parents


# =============================================================================
# Round-2 review: 4 new blocking edge cases
# =============================================================================

class TestLivenessCheck:
    """Opus review item 4: a PID counts as the run only if it is a live
    python.exe whose command line contains the needle; the one function
    that shells out (`_process_command_line`) is mockable and timeout-
    bounded."""

    def test_process_command_line_returns_none_on_timeout(self, monkeypatch):
        def _raise_timeout(*a, **kw):
            raise launcher.subprocess.TimeoutExpired(cmd="powershell", timeout=10)
        monkeypatch.setattr(launcher.subprocess, "run", _raise_timeout)
        assert launcher._process_command_line(12345, timeout=0.01) is None

    def test_process_command_line_passes_the_timeout_through(self, monkeypatch):
        captured = {}

        def _fake_run(cmd, capture_output=None, timeout=None):
            captured["timeout"] = timeout
            return types.SimpleNamespace(returncode=0, stdout=b"")

        monkeypatch.setattr(launcher.subprocess, "run", _fake_run)
        launcher._process_command_line(123, timeout=5.0)
        assert captured["timeout"] == 5.0

    def test_process_command_line_none_on_nonzero_returncode(self, monkeypatch):
        monkeypatch.setattr(
            launcher.subprocess, "run",
            lambda *a, **kw: types.SimpleNamespace(returncode=1, stdout=b""),
        )
        assert launcher._process_command_line(123) is None

    def test_is_process_alive_for_requires_python_exe(self, monkeypatch):
        monkeypatch.setattr(launcher, "_process_command_line", lambda pid, timeout=10.0: "notepad.exe something")
        assert launcher.is_process_alive_for(123, "something") is False

    def test_is_process_alive_for_requires_the_needle(self, monkeypatch):
        monkeypatch.setattr(launcher, "_process_command_line", lambda pid, timeout=10.0: "python.exe other_stuff")
        assert launcher.is_process_alive_for(123, "something") is False

    def test_is_process_alive_for_true_when_both_match(self, monkeypatch):
        monkeypatch.setattr(launcher, "_process_command_line", lambda pid, timeout=10.0: "python.exe something")
        assert launcher.is_process_alive_for(123, "something") is True

    def test_is_process_alive_for_false_without_a_pid(self):
        assert launcher.is_process_alive_for(None, "anything") is False
        assert launcher.is_process_alive_for(0, "anything") is False

    def test_is_run_process_alive_uses_the_output_dir_as_needle(self, monkeypatch, tmp_path):
        d = tmp_path / "v3_strict_run"
        monkeypatch.setattr(
            launcher, "_process_command_line",
            lambda pid, timeout=10.0: f"python.exe run_experiment.py --output {d}",
        )
        assert launcher.is_run_process_alive(999, d) is True
        assert launcher.is_run_process_alive(999, tmp_path / "some_other_dir") is False

    def test_is_chain_alive_uses_run_chain_as_needle(self, monkeypatch):
        monkeypatch.setattr(
            launcher, "_process_command_line",
            lambda pid, timeout=10.0: "python.exe v3_corpus_launcher.py _run-chain --spec x.json",
        )
        assert launcher.is_chain_alive(999) is True

    def test_is_chain_alive_false_for_an_unrelated_python_process(self, monkeypatch):
        monkeypatch.setattr(
            launcher, "_process_command_line",
            lambda pid, timeout=10.0: "python.exe examples/irrigation_abm/run_experiment.py --output X",
        )
        assert launcher.is_chain_alive(999) is False


class TestLiveChainLock:
    """Opus review item 1: refuse `run pilot`, `run corpus` and `resume`
    while ANY chain PID recorded in state["launches"] is alive -- entries
    queued later in that chain have no attempt dir or record yet and would
    otherwise look "pending" to a second invocation."""

    def test_live_chain_launch_none_when_nothing_recorded(self):
        assert launcher.live_chain_launch({}) is None

    def test_live_chain_launch_none_when_recorded_pid_is_dead(self, monkeypatch):
        _mock_all_dead(monkeypatch)
        state = {"launches": [{"phase": "fql", "pid": 111}]}
        assert launcher.live_chain_launch(state) is None

    def test_live_chain_launch_finds_the_alive_one(self, monkeypatch):
        _mock_liveness(monkeypatch, {222: "_run-chain"})
        state = {"launches": [{"phase": "fql", "pid": 111}, {"phase": "pilot", "pid": 222}]}
        live = launcher.live_chain_launch(state)
        assert live is not None and live["pid"] == 222

    def test_run_pilot_refuses_while_a_chain_is_alive(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        state_dir = tmp_path / "state"
        launcher.save_state(state_dir, {"launches": [{"phase": "fql", "pid": 222, "log": "x.log"}]})
        _mock_liveness(monkeypatch, {222: "_run-chain"})

        with pytest.raises(SystemExit, match="still running"):
            launcher.main([
                "run", "pilot", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
            ])

    def test_run_corpus_refuses_while_a_chain_is_alive(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        state_dir = tmp_path / "state"
        launcher.save_state(state_dir, {"launches": [{"phase": "pilot", "pid": 222, "log": "x.log"}]})
        _mock_liveness(monkeypatch, {222: "_run-chain"})

        with pytest.raises(SystemExit, match="still running"):
            launcher.main([
                "run", "corpus", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
            ])

    def test_resume_refuses_while_a_chain_is_alive(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        state_dir = tmp_path / "state"
        launcher.save_state(state_dir, {"launches": [{"phase": "corpus", "pid": 222, "log": "x.log"}]})
        _mock_liveness(monkeypatch, {222: "_run-chain"})

        with pytest.raises(SystemExit, match="still running"):
            launcher.main([
                "resume", "strict_43", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
                "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
            ])

    def test_run_fql_is_not_blocked_by_a_live_chain(self, monkeypatch, tmp_path, git_repo):
        """Item 1 scopes the lock to pilot/corpus/resume; fql and replays
        are CPU-only and deliberately not covered."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        state_dir = tmp_path / "state"
        launcher.save_state(state_dir, {"launches": [{"phase": "pilot", "pid": 222, "log": "x.log"}]})
        _mock_liveness(monkeypatch, {222: "_run-chain"})
        monkeypatch.setattr(
            launcher, "_popen_detached",
            lambda argv, *, cwd, log_path: types.SimpleNamespace(pid=1),
        )

        rc = launcher.main([
            "run", "fql", "--tag", "v-test",
            "--results-root", str(tmp_path / "r"), "--state-dir", str(state_dir),
        ])
        assert rc == 0

    def test_run_pilot_proceeds_once_the_old_chain_has_exited(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "r"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        plan = launcher.build_plan(results_root, sha8, 1)
        for run in plan:
            if run.phase == "fql":
                run.output_dir.mkdir(parents=True)
                (run.output_dir / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
            if run.label == "replays_ab":
                for kind in ("A", "B"):
                    (run.output_dir / kind).mkdir(parents=True)
                    (run.output_dir / kind / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
        launcher.save_state(state_dir, {"launches": [{"phase": "fql", "pid": 222, "log": "x.log"}]})
        _mock_all_dead(monkeypatch)  # the old fql chain has since exited
        monkeypatch.setattr(
            launcher, "_popen_detached",
            lambda argv, *, cwd, log_path: types.SimpleNamespace(pid=999),
        )

        rc = launcher.main([
            "run", "pilot", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])
        assert rc == 0


class TestEmptyAttemptNeverHidesTheCrash:
    """Opus review item 2(b): mirrors the reviewer's own probe
    (probe_round2.py) -- an empty `_resume1` (a resume that died at
    startup, before writing anything, but WAS recorded with a failed
    exit) must not make the overall plan-entry status read "pending"; it
    must read "crashed", from the record, not from disk content."""

    def test_empty_resume1_with_a_failed_record_reads_crashed_not_pending(self, tmp_path):
        state_dir = tmp_path / "state"
        plan = launcher.build_plan(tmp_path / "results", "deadbeef", 4)
        run = next(r for r in plan if r.label == "strict_43")
        run.output_dir.mkdir(parents=True)
        (run.output_dir / "llm_journal.jsonl").write_text('{"type": "header"}\n', encoding="utf-8")
        launcher.write_run_record(state_dir, "strict_43", {"pid": 999999999, "returncode": 1})
        (run.output_dir.parent / f"{run.output_dir.name}_resume1").mkdir()
        launcher.write_run_record(state_dir, "strict_43_resume1", {"pid": 999999999, "returncode": 1})

        assert launcher.run_status_for_plan_entry(run, state_dir) == "crashed"

    def test_queued_entry_with_nothing_recorded_still_reads_pending(self, tmp_path):
        """Sanity check alongside the above (probe_round2.py part 3): a
        truly untouched entry (no dir, no record at all) must still read
        "pending" -- the fix must not make every entry read as crashed."""
        state_dir = tmp_path / "state"
        plan = launcher.build_plan(tmp_path / "results", "deadbeef", 4)
        queued = next(r for r in plan if r.label == "strict_44")
        assert launcher.run_status_for_plan_entry(queued, state_dir) == "pending"

    def test_run_never_relaunches_a_label_with_an_attempt_dir(self, monkeypatch, tmp_path, git_repo):
        """Item 2(c): `run` launches only labels with NO attempt dir at
        all -- an empty, recorded _resume1 must not be (re)launched as a
        FRESH base-dir run either."""
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]
        sha8_plan = launcher.build_plan(results_root, sha8, 4)
        run = next(r for r in sha8_plan if r.label == "strict_43")
        run.output_dir.mkdir(parents=True)
        (run.output_dir / "llm_journal.jsonl").write_text('{"type": "header"}\n', encoding="utf-8")
        launcher.write_run_record(state_dir, "strict_43", {"pid": 999999999, "returncode": 1})
        launcher.save_state(state_dir, {
            "workers": 4, "pilot_gate": {"passed": True, "sha8": sha8},
        })

        captured = {}

        def _spy(argv, *, cwd, log_path):
            captured["argv"] = argv
            return types.SimpleNamespace(pid=1)

        monkeypatch.setattr(launcher, "_popen_detached", _spy)
        launcher.main([
            "run", "corpus", "--tag", "v-test", "--workers", "4", "--confirm-gpu",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])
        spec = json.loads(Path(captured["argv"][-1]).read_text(encoding="utf-8"))
        launched_labels = {r["label"] for r in spec["runs"]}
        assert "strict_43" not in launched_labels


class TestGatePassesLatestDoneAttempt:
    """Opus review item 3: mirrors the reviewer's own probe
    (probe_gate_resumed.py) -- when a pilot run's BASE dir crashed but its
    `_resume1` is done, `cmd_gate` must pass the `_resume1` dir to
    p5c-sample and pilot-gate, never the crashed base dir."""

    def test_gate_passes_the_resumed_dir_not_the_crashed_base(self, monkeypatch, tmp_path, git_repo):
        repo, _git = git_repo
        monkeypatch.setattr(launcher, "_REPO_ROOT", repo)
        results_root = tmp_path / "results"
        state_dir = tmp_path / "state"
        sha8 = launcher.resolve_commit("v-test", repo)[:8]

        plan = launcher.build_plan(results_root, sha8, 4)
        for run in plan:
            if run.phase == "fql":
                run.output_dir.mkdir(parents=True)
                (run.output_dir / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
            if run.label == "replays_ab":
                for kind in ("A", "B"):
                    (run.output_dir / kind).mkdir(parents=True)
                    (run.output_dir / kind / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
            if run.label == "pilot_disabled_42":
                run.output_dir.mkdir(parents=True)
                (run.output_dir / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
                (run.output_dir / "run_integrity.json").write_text(
                    json.dumps(_done_run_integrity()), encoding="utf-8",
                )

        strict_run = next(r for r in plan if r.label == "pilot_strict_42")
        strict_base = strict_run.output_dir
        strict_base.mkdir(parents=True)
        (strict_base / "llm_journal.jsonl").write_text("{}\n", encoding="utf-8")
        strict_resume1 = strict_base.parent / f"{strict_base.name}_resume1"
        strict_resume1.mkdir()
        (strict_resume1 / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
        (strict_resume1 / "run_integrity.json").write_text(
            json.dumps(_done_run_integrity()), encoding="utf-8",
        )

        assert launcher.run_status_for_plan_entry(strict_run, state_dir) == "done"

        calls = []
        monkeypatch.setattr(launcher.subprocess, "run", _fake_v3_metrics_run(calls))

        rc = launcher.main([
            "gate", "--tag", "v-test",
            "--results-root", str(results_root), "--state-dir", str(state_dir),
        ])

        assert rc == 0
        assert len(calls) == 2
        for cmd in calls:
            i = cmd.index("--runs")
            runs_args = cmd[i + 1:i + 3]
            assert str(strict_resume1) in runs_args, f"expected the resumed dir in --runs, got {runs_args}"
            assert str(strict_base) not in runs_args, f"must never pass the crashed base dir, got {runs_args}"

    def test_pilot_pair_manifest_workers_reads_the_resumed_dir(self, tmp_path):
        results_root = tmp_path / "results"
        sha8 = "deadbeef"
        plan = launcher.build_plan(results_root, sha8, 4)

        disabled_run = next(r for r in plan if r.label == "pilot_disabled_42")
        disabled_run.output_dir.mkdir(parents=True)
        (disabled_run.output_dir / "reproducibility_manifest.json").write_text(
            json.dumps({"workers": 4}), encoding="utf-8",
        )
        (disabled_run.output_dir / "run_integrity.json").write_text(
            json.dumps(_done_run_integrity()), encoding="utf-8",
        )

        strict_run = next(r for r in plan if r.label == "pilot_strict_42")
        strict_run.output_dir.mkdir(parents=True)
        (strict_run.output_dir / "llm_journal.jsonl").write_text("{}\n", encoding="utf-8")
        strict_resume1 = strict_run.output_dir.parent / f"{strict_run.output_dir.name}_resume1"
        strict_resume1.mkdir()
        (strict_resume1 / "reproducibility_manifest.json").write_text(
            json.dumps({"workers": 4}), encoding="utf-8",
        )
        (strict_resume1 / "run_integrity.json").write_text(
            json.dumps(_done_run_integrity()), encoding="utf-8",
        )

        assert launcher.pilot_pair_manifest_workers(results_root, sha8, None) == 4
