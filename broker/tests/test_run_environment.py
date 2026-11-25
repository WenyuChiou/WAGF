"""Run-environment capture: pure helpers and the manifest block. No real network."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from broker.core.experiment_runner import ExperimentRunner
from broker.utils import run_environment as re_mod


def _no_network(*args, **kwargs):
    raise AssertionError("requests.get must not be called")


def test_package_versions_lists_declared_packages():
    result = re_mod.package_versions()
    assert result["error"] is None
    assert result["packages"]
    assert all(v is None or isinstance(v, str) for v in result["packages"].values())
    assert result["wagf_version_source"] == "pyproject.toml"


def test_declared_package_that_is_not_installed_is_none(monkeypatch):
    monkeypatch.setattr(re_mod, "_dependency_list",
                        lambda: ("9.9", "pyproject.toml", ["no-such-dist-xyz>=1.0", "pyyaml>=6"]))
    result = re_mod.package_versions()
    assert result["packages"]["no-such-dist-xyz"] is None
    assert result["error"] is None


def test_no_dependency_list_is_an_error(monkeypatch):
    monkeypatch.setattr(re_mod, "_dependency_list", lambda: (None, None, []))
    result = re_mod.package_versions()
    assert result["packages"] == {} and result["error"] == "dependency list unavailable"


def test_fallback_parser_matches_tomllib():
    tomllib = pytest.importorskip("tomllib")
    path = Path(re_mod.__file__).resolve().parents[2] / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    expected = tomllib.loads(text)["project"]
    parsed = re_mod._parse_project_table(text)
    assert parsed["name"] == expected["name"]
    assert parsed["version"] == expected["version"]
    assert parsed["dependencies"] == expected["dependencies"]


def test_another_projects_pyproject_is_not_used(monkeypatch, tmp_path):
    other = tmp_path / "pyproject.toml"
    other.write_text("\n".join(['[project]', 'name = "something-else"', 'version = "1.0"',
                                'dependencies = ["pyyaml"]', '']), encoding="utf-8")
    monkeypatch.setattr(re_mod, "_read_pyproject", lambda path: re_mod._parse_project_table(other.read_text("utf-8")))
    version, source, _ = re_mod._dependency_list()
    assert source != "pyproject.toml" and version != "1.0"


def test_ollama_timeout_is_split_in_half(monkeypatch):
    seen = {}

    def fake_get(url, timeout=None):
        seen["timeout"] = timeout
        return _Resp(200, {"version": "1"})
    monkeypatch.setattr(re_mod.requests, "get", fake_get)
    re_mod.ollama_server_version("http://h:1", timeout=5.0)
    assert seen["timeout"] == (1.0, 1.0)


def _git(root, *args):
    import subprocess
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _make_repo(root):
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "user.email", "t@example.invalid")
    (root / "a.txt").write_text("a", encoding="utf-8")
    _git(root, "add", "a.txt")
    _git(root, "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "init")


def test_wagf_source_git_clean_dirty_and_not_a_checkout(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    repo = tmp_path / "repo"
    _make_repo(repo)
    clean = re_mod.wagf_source_git(repo)
    assert clean["dirty"] is False and clean["dirty_count"] == 0 and clean["error"] is None
    assert len(clean["commit"]) == 40
    (repo / "new.txt").write_text("x", encoding="utf-8")
    assert re_mod.wagf_source_git(repo)["dirty_count"] == 1
    plain = tmp_path / "plain"
    plain.mkdir()
    assert re_mod.wagf_source_git(plain) is None


def test_wagf_source_git_error_is_a_type_name(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    fake = tmp_path / "fake"
    (fake / ".git").mkdir(parents=True)  # exists, but not a real repository
    result = re_mod.wagf_source_git(fake)
    assert result["error"] == "CalledProcessError" and result["commit"] is None


def test_collect_records_source_git_error(monkeypatch):
    monkeypatch.setattr(re_mod, "wagf_source_git",
                        lambda root=None: {"commit": None, "dirty": None, "dirty_count": None, "error": "TimeoutExpired"})
    env = re_mod.collect_run_environment("mock", captured_at="launch")
    assert env["errors"]["wagf_source_git"] == "TimeoutExpired"


def test_os_info_has_four_strings():
    info = re_mod.os_info()
    assert set(info) == {"system", "release", "version", "machine"}
    assert all(isinstance(v, str) for v in info.values())


class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def test_ollama_version_ok(monkeypatch):
    monkeypatch.setattr(re_mod.requests, "get", lambda *a, **k: _Resp(200, {"version": "0.23.0"}))
    assert re_mod.ollama_server_version("http://h:1") == {"version": "0.23.0", "error": None}


def test_ollama_version_connection_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("cannot reach")
    monkeypatch.setattr(re_mod.requests, "get", boom)
    assert re_mod.ollama_server_version("http://h:1") == {"version": None, "error": "ConnectionError"}


def test_ollama_version_http_error(monkeypatch):
    monkeypatch.setattr(re_mod.requests, "get", lambda *a, **k: _Resp(500, {}))
    assert re_mod.ollama_server_version("http://h:1") == {"version": None, "error": "HTTP 500"}


def test_ollama_version_without_version_field(monkeypatch):
    monkeypatch.setattr(re_mod.requests, "get", lambda *a, **k: _Resp(200, {"other": 1}))
    assert re_mod.ollama_server_version("http://h:1")["error"] == "response had no version"


def test_ollama_error_never_carries_url(monkeypatch):
    def boom(url, **k):
        raise requests.ConnectionError(f"failed to reach {url}")
    monkeypatch.setattr(re_mod.requests, "get", boom)
    result = re_mod.ollama_server_version("http://user:secret@host:1")
    assert "secret" not in result["error"] and "host" not in result["error"]


@pytest.mark.parametrize("model", ["mock", "openai:gpt-5"])
def test_mock_and_cloud_skip_ollama(monkeypatch, model):
    monkeypatch.setattr(re_mod.requests, "get", _no_network)
    env = re_mod.collect_run_environment(model, captured_at="launch")
    assert env["captured_at"] == "launch"
    assert env["ollama_server_version"] == {"version": None, "error": "not an Ollama model"}
    assert env["errors"] == {}


def test_ollama_model_records_version_or_error(monkeypatch):
    monkeypatch.setattr(re_mod, "ollama_server_version", lambda url, timeout=2.0: {"version": "0.23.0", "error": None})
    env = re_mod.collect_run_environment("gemma3:4b", captured_at="launch")
    assert env["ollama_server_version"]["version"] == "0.23.0" and env["errors"] == {}
    monkeypatch.setattr(re_mod, "ollama_server_version",
                        lambda url, timeout=2.0: {"version": None, "error": "ConnectionError"})
    env = re_mod.collect_run_environment("gemma3:4b", captured_at="launch")
    assert env["errors"] == {"ollama_server_version": "ConnectionError"}


def _runner(model="mock"):
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = SimpleNamespace(model=model)
    return runner


def test_manifest_gets_finalize_environment():
    metadata = _runner()._collect_reproducibility_metadata()
    assert metadata["run_environment"]["captured_at"] == "finalize"


def test_manifest_replays_launch_environment():
    runner = _runner()
    preset = {"captured_at": "launch", "errors": {}}
    runner._run_environment_at_launch = preset
    assert runner._collect_reproducibility_metadata()["run_environment"] is preset
