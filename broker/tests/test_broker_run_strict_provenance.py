"""broker.run launch checks and --strict-provenance. Every network call is faked."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from broker.core.experiment_runner import ExperimentRunner
from broker.run import main
from broker.run._provenance import launch_checks, manifest_problem

ROOT = Path(__file__).resolve().parents[2]


def _load_check_share():
    spec = importlib.util.spec_from_file_location("check_share", ROOT / "reproduction" / "check_share.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_yaml(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.fixture
def case(tmp_path, monkeypatch):
    """A minimal default-agent case (same shape as test_broker_run.py), outside the git repo."""
    folder = tmp_path / "cases" / f"case_{uuid4().hex}"
    config_path = folder / "config" / "agent_types.yaml"
    config_path.parent.mkdir(parents=True)
    _write_yaml(config_path.with_name("skill_registry.yaml"), {
        "default_skill": "wait",
        "skills": [{"skill_id": "wait", "description": "Wait for the next year"},
                   {"skill_id": "inspect", "description": "Inspect the site"}],
    })
    data = {
        "global_config": {},
        "agent": {
            "psychological_framework": "generic",
            "prompt_template": "Available actions\n{options_text}\n\n{response_format}",
            "actions": [{"id": "wait", "aliases": ["1"]}, {"id": "inspect", "aliases": ["2"]}],
            "parsing": {"skill_map": {"1": "wait", "2": "inspect"}},
            "response_format": {
                "delimiter_start": "<<<DECISION_START>>>",
                "delimiter_end": "<<<DECISION_END>>>",
                "fields": [{"key": "decision", "type": "choice", "required": True}],
            },
        },
    }
    _write_yaml(config_path, data)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    return config_path


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway git repo that is the current directory."""
    root = tmp_path / "repo"
    root.mkdir()
    for cmd in (["git", "init", "-q"], ["git", "config", "user.name", "t"],
                ["git", "config", "user.email", "t@example.invalid"]):
        subprocess.run(cmd, cwd=root, check=True)
    (root / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=root, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "init"], cwd=root, check=True)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(root)
    return root


CLEAN_SOURCE = {"commit": "abc", "dirty": False, "dirty_count": 0, "error": None}


@pytest.fixture(autouse=True)
def _wagf_source_clean(monkeypatch):
    """The WAGF checkout running the tests may itself be dirty; pin it clean unless a test says otherwise."""
    monkeypatch.setattr("broker.utils.run_environment.wagf_source_git", lambda root=None: dict(CLEAN_SOURCE))


def _record(output):
    return json.loads((output / "broker_run.json").read_text(encoding="utf-8"))


def _argv(config, output, *extra, model="mock"):
    return [str(config), "--model", model, "--years", "1", "--agents", "1", "--output", str(output), *extra]


def test_clean_mock_run_passes_every_check(case, repo, tmp_path):
    output = tmp_path / "out"
    assert main(_argv(case, output, "--strict-provenance")) == 0
    record = _record(output)
    assert record["status"] == "completed" and record["strict_provenance"] is True
    assert record["provenance_checks"] == {
        "clean_tree": "pass", "model_digest": "not applicable: mock model",
        "metadata_queries": "pass", "manifest_write": "pass"}
    assert record["provenance_problems"] == []
    manifest = json.loads((output / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    env = manifest["run_environment"]
    assert env["captured_at"] == "launch"
    assert env["ollama_server_version"]["error"] == "not an Ollama model"


def test_dirty_tree_is_refused_only_with_the_flag(case, repo, tmp_path, capsys):
    (repo / "untracked.txt").write_text("x", encoding="utf-8")
    output = tmp_path / "out"
    assert main(_argv(case, output, "--strict-provenance")) == 2
    assert "uncommitted changes" in capsys.readouterr().err
    assert not (output / "reproducibility_manifest.json").exists()
    assert _record(output)["status"] == "refused_provenance"

    loose = tmp_path / "loose"
    assert main(_argv(case, loose)) == 0
    record = _record(loose)
    assert record["strict_provenance"] is False
    assert record["provenance_checks"]["clean_tree"] == "fail"


def test_missing_digest_refuses_before_the_run(case, repo, tmp_path, monkeypatch, capsys):
    def no_digest(self, _attempt=0):
        self._model_metadata_at_launch = {"model_digest": None, "model_digest_error": "fake"}

    started = []
    monkeypatch.setattr(ExperimentRunner, "_capture_model_metadata_at_launch", no_digest)
    monkeypatch.setattr("broker.utils.run_environment.ollama_server_version",
                        lambda url, timeout=2.0: {"version": "0.23.0", "error": None})
    monkeypatch.setattr(ExperimentRunner, "run", lambda self, *a, **k: started.append(1))
    output = tmp_path / "out"
    assert main(_argv(case, output, "--strict-provenance", model="gemma3:4b")) == 2
    assert "no model digest for gemma3:4b" in capsys.readouterr().err
    assert started == []
    record = _record(output)
    assert record["status"] == "refused_provenance"
    assert record["provenance_checks"]["model_digest"] == "fail"


def test_unreadable_git_state_is_refused(case, tmp_path, monkeypatch, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(plain)
    output = tmp_path / "out"
    assert main(_argv(case, output, "--strict-provenance")) == 2
    assert "git state could not be read" in capsys.readouterr().err
    assert _record(output)["provenance_checks"]["metadata_queries"] == "fail"


def test_environment_errors_fail_metadata_queries():
    runner = SimpleNamespace(
        _git_dirty_at_launch=False, _git_commit_at_launch="abc", _git_dirty_files_at_launch=[],
        _run_environment_at_launch={"errors": {"ollama_server_version": "ConnectionError"}})
    checks, problems = launch_checks(runner, "mock")
    assert checks["metadata_queries"] == "fail"
    assert any("ollama_server_version" in p for p in problems)


def test_cloud_model_has_no_digest_problem():
    runner = SimpleNamespace(
        _git_dirty_at_launch=False, _git_commit_at_launch="abc", _git_dirty_files_at_launch=[],
        _run_environment_at_launch={"errors": {}}, _model_metadata_at_launch={"model_digest": None})
    checks, problems = launch_checks(runner, "openai:gpt-5")
    assert checks["model_digest"] == "not applicable: cloud model"
    assert problems == []


def _failing_manifest_dump(monkeypatch):
    import broker.core.experiment_runner as er
    real = er.json.dump

    def dump(obj, fp, *a, **k):
        if str(getattr(fp, "name", "")).endswith("reproducibility_manifest.json"):
            raise OSError("disk full")
        return real(obj, fp, *a, **k)

    monkeypatch.setattr(er.json, "dump", dump)


def test_failed_manifest_write_is_exit_1_with_the_flag(case, repo, tmp_path, monkeypatch, capsys):
    _failing_manifest_dump(monkeypatch)
    output = tmp_path / "out"
    assert main(_argv(case, output, "--strict-provenance")) == 1
    assert "--strict-provenance:" in capsys.readouterr().err
    record = _record(output)
    assert record["status"] == "provenance_failed"
    assert record["provenance_checks"]["manifest_write"] == "fail"


def test_failed_manifest_write_is_recorded_without_the_flag(case, repo, tmp_path, monkeypatch):
    _failing_manifest_dump(monkeypatch)
    output = tmp_path / "out"
    assert main(_argv(case, output)) == 0
    record = _record(output)
    assert record["status"] == "completed"
    assert record["provenance_checks"]["manifest_write"] == "fail"


def test_dirty_wagf_source_is_refused_with_clean_cwd(case, repo, tmp_path, monkeypatch, capsys):
    dirty = {"commit": "abc", "dirty": True, "dirty_count": 7, "error": None}
    monkeypatch.setattr("broker.utils.run_environment.wagf_source_git", lambda root=None: dict(dirty))
    output = tmp_path / "out"
    assert main(_argv(case, output, "--strict-provenance")) == 2
    err = capsys.readouterr().err
    assert "7 uncommitted changes in the WAGF source tree" in err
    assert "current directory" not in err
    assert _record(output)["provenance_checks"]["clean_tree"] == "fail"


def test_same_tree_is_reported_once(case, repo, monkeypatch):
    root = repo  # pretend the WAGF source root is the current directory's repo
    monkeypatch.setattr("broker.run._provenance._cwd_inside_wagf_source", lambda: True)
    runner = SimpleNamespace(
        _git_dirty_at_launch=True, _git_commit_at_launch="abc", _git_dirty_files_at_launch=["?? a", "?? b"],
        _run_environment_at_launch={"errors": {}, "wagf_source_git": {"dirty": True, "dirty_count": 2}},
        _model_metadata_at_launch={})
    checks, problems = launch_checks(runner, "mock")
    assert checks["clean_tree"] == "fail"
    assert len(problems) == 1 and "current directory" in problems[0]
    assert root.exists()


def test_not_a_checkout_passes_the_source_check():
    runner = SimpleNamespace(
        _git_dirty_at_launch=False, _git_commit_at_launch="abc", _git_dirty_files_at_launch=[],
        _run_environment_at_launch={"errors": {}, "wagf_source_git": None})
    checks, problems = launch_checks(runner, "mock")
    assert checks["clean_tree"] == "pass" and problems == []


def test_truncated_dirty_count_is_shown_as_200_plus():
    runner = SimpleNamespace(
        _git_dirty_at_launch=True, _git_commit_at_launch="abc", _git_dirty_files_at_launch=["x"] * 200,
        _git_dirty_files_truncated_at_launch=True, _run_environment_at_launch={"errors": {}})
    _, problems = launch_checks(runner, "mock")
    assert problems[0].startswith("200+ uncommitted changes")


def test_problems_are_printed_without_the_flag(case, repo, tmp_path, capsys):
    (repo / "untracked.txt").write_text("x", encoding="utf-8")
    assert main(_argv(case, tmp_path / "out")) == 0
    err = capsys.readouterr().err
    assert "broker.run: provenance check: " in err
    assert "(add --strict-provenance to refuse)" in err


def test_manifest_problem_is_printed_without_the_flag(case, repo, tmp_path, monkeypatch, capsys):
    _failing_manifest_dump(monkeypatch)
    assert main(_argv(case, tmp_path / "out")) == 0
    assert "provenance check: reproducibility_manifest.json" in capsys.readouterr().err


def test_manifest_problem_survives_an_unreadable_path(tmp_path, monkeypatch):
    def boom(self):
        raise PermissionError("denied")
    monkeypatch.setattr(Path, "is_file", boom)
    assert manifest_problem(tmp_path) == "reproducibility_manifest.json could not be read"


def test_manifest_problem_texts(tmp_path):
    assert "not written" in manifest_problem(tmp_path)
    (tmp_path / "reproducibility_manifest.json").write_text("{", encoding="utf-8")
    assert "not valid JSON" in manifest_problem(tmp_path)
    (tmp_path / "reproducibility_manifest.json").write_text("{}", encoding="utf-8")
    assert "no run_environment" in manifest_problem(tmp_path)
    (tmp_path / "reproducibility_manifest.json").write_text('{"run_environment": {}}', encoding="utf-8")
    assert manifest_problem(tmp_path) is None


def test_share_step_stages_a_broker_run_folder(case, repo, tmp_path):
    output = tmp_path / "out"
    assert main(_argv(case, output)) == 0
    dest = tmp_path / "share"
    assert _load_check_share().main(["--stage", str(dest), str(output)]) == 0
    staged = dest / output.name
    assert (staged / "broker_run.json").is_file()
    assert (staged / "reproducibility_manifest.json").is_file()
    assert not (staged / "raw").exists()
    text = (staged / "broker_run.json").read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z]:[\\/]", text)
    assert "Users" not in text
