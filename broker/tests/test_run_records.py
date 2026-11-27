"""The records a run leaves for a reviewer: model-call log, truncation counts, environment,
clean-tree gate, times, input digests, repo-relative paths, optional per-call seed.

Mock model and a faked HTTP layer only; no Ollama is started.
"""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from broker.core.experiment_runner import ExperimentRunner
from broker.utils import llm_call_log as cl
from broker.utils import llm_utils
from broker.utils import run_environment as renv


@pytest.fixture(autouse=True)
def _clean_state():
    cl.deactivate()
    cl.configure_sampling_seed("off", None)
    yield
    cl.deactivate()
    cl.configure_sampling_seed("off", None)


def _lines(path: Path) -> list:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


# ------------------------------------------------------------------ context and log file

def test_call_context_merges_onto_the_outer_context_and_restores():
    with cl.call_context(agent_id="A1", agent_type="farmer", year=3, kind="decision", attempt=1):
        with cl.call_context(kind="decision_retry", attempt=2):
            inner = cl.current_context()
        outer = cl.current_context()
    assert inner["agent_ids"] == ["A1"] and inner["year"] == 3
    assert inner["kind"] == "decision_retry" and inner["attempt"] == 2
    assert outer["kind"] == "decision" and outer["attempt"] == 1
    assert cl.current_context() == {}


def test_call_context_rejects_an_unknown_kind():
    with pytest.raises(ValueError):
        with cl.call_context(kind="mystery"):
            pass


def test_year_of_reads_current_year_only():
    assert cl.year_of({"current_year": 4}) == 4
    assert cl.year_of({"year": 4}) is None
    assert cl.year_of(None) is None


def test_every_field_is_written_and_flushed_per_line(tmp_path):
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)
    with cl.call_context(agent_ids=["A1", "A2"], agent_type="household", year=2,
                         kind="reflection", attempt=1):
        cl.record_llm_call(
            prompt="the prompt", reply="the reply",
            options={"model": "gemma3:4b", "temperature": 1.0, "top_p": 0.95, "top_k": 64,
                     "num_ctx": 8192, "num_predict": 4096, "think": False, "seed": 7},
            prompt_eval_count=10, eval_count=3, done_reason="stop", wall_seconds=0.5)
    # Read while the file is still open: the line must already be on disk.
    rows = _lines(log.path)
    assert len(rows) == 1
    row = rows[0]
    assert row["call_index"] == 1
    assert row["agent_ids"] == ["A1", "A2"] and row["agent_type"] == "household"
    assert row["year"] == 2 and row["kind"] == "reflection" and row["attempt"] == 1
    assert row["prompt"] == "the prompt" and row["reply"] == "the reply"
    import hashlib
    assert row["prompt_sha256"] == hashlib.sha256(b"the prompt").hexdigest()
    assert row["options"] == {"model": "gemma3:4b", "temperature": 1.0, "top_p": 0.95, "top_k": 64,
                              "num_ctx": 8192, "num_predict": 4096, "think": False, "seed": 7}
    assert (row["prompt_eval_count"], row["eval_count"], row["done_reason"]) == (10, 3, "stop")
    assert row["wall_seconds"] == 0.5 and row["error"] is None
    assert row["started_at_utc"].endswith("Z")
    log.close()


def test_a_call_with_no_context_is_kind_other(tmp_path):
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)
    cl.record_llm_call(prompt="p", reply="r")
    log.close()
    row = _lines(log.path)[0]
    assert row["kind"] == "other" and row["agent_ids"] == [] and row["year"] is None


def test_a_resumed_run_appends_and_keeps_counting(tmp_path):
    path = tmp_path / "llm_calls.jsonl"
    first = cl.LLMCallLog(path)
    cl.activate(first)
    cl.record_llm_call(prompt="a", reply="b")
    first.close()
    second = cl.LLMCallLog(path)
    cl.activate(second)
    cl.record_llm_call(prompt="c", reply="d")
    second.close()
    assert [r["call_index"] for r in _lines(path)] == [1, 2]


def test_no_active_log_means_no_file_and_no_error(tmp_path):
    cl.record_llm_call(prompt="p", reply="r")  # must not raise
    assert not list(tmp_path.iterdir())


def test_a_failed_write_is_counted_not_raised(tmp_path):
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)
    log._fh = MagicMock()
    log._fh.write.side_effect = OSError("disk full")
    cl.record_llm_call(prompt="p", reply="r")
    assert log.write_failures == 1 and log.summary()["write_failures"] == 1


# ------------------------------------------------------------------ the wrapper

def test_wrapper_logs_a_mock_call_and_returns_the_reply_untouched(tmp_path):
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)
    stats = llm_utils.LLMStats()
    reply = ('{"decision": 1}', stats)
    wrapped = cl.wrap_invoke_with_call_log(
        lambda prompt: reply, model="mock", agent_type="household",
        resolved={"model": "mock", "temperature": 1.0})
    with cl.call_context(agent_id="A1", year=1, kind="decision", attempt=2):
        out = wrapped("PROMPT")
    assert out is reply
    row = _lines(log.path)[0]
    assert row["prompt"] == "PROMPT" and row["reply"] == '{"decision": 1}'
    assert row["agent_type"] == "household" and row["kind"] == "decision" and row["attempt"] == 2
    assert row["options"]["model"] == "mock" and row["options"]["temperature"] == 1.0
    assert row["done_reason"] is None and row["prompt_eval_count"] is None
    log.close()


def test_wrapper_does_not_log_a_call_the_inner_layer_already_logged(tmp_path):
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)

    def inner(prompt):
        cl.record_llm_call(prompt=prompt, reply="x", options={"model": "m"}, done_reason="stop")
        return "x", llm_utils.LLMStats()

    cl.wrap_invoke_with_call_log(inner, model="m", agent_type="t")("P")
    log.close()
    rows = _lines(log.path)
    assert len(rows) == 1 and rows[0]["done_reason"] == "stop"


def test_wrapper_logs_a_raising_call_and_reraises(tmp_path):
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)

    def boom(prompt):
        raise RuntimeError("no")

    with pytest.raises(RuntimeError):
        cl.wrap_invoke_with_call_log(boom, model="m", agent_type="t")("P")
    log.close()
    row = _lines(log.path)[0]
    assert row["error"] == "RuntimeError" and row["reply"] is None


def test_wrapper_without_an_active_log_just_calls_through():
    wrapped = cl.wrap_invoke_with_call_log(lambda p: p + "!", model="m", agent_type="t")
    assert wrapped("hi") == "hi!"


# ------------------------------------------------------------------ Ollama layer

class _Resp:
    status_code = 200

    def __init__(self, body):
        self._body = body
        self.text = ""

    def json(self):
        return self._body


@pytest.fixture()
def fake_ollama(monkeypatch):
    import requests

    fake = ModuleType("langchain_ollama")

    class _Stub:
        def __init__(self, model, **params):
            self.model = model

    fake.ChatOllama = _Stub
    fake.OllamaLLM = _Stub
    monkeypatch.setitem(sys.modules, "langchain_ollama", fake)
    monkeypatch.setattr(llm_utils, "LLM_CONFIG", llm_utils.LLMConfig(num_ctx=100, num_predict=50))
    sent = []
    state = {"body": {"response": "ok", "prompt_eval_count": 40, "eval_count": 5,
                      "done_reason": "stop"}}

    def post(url, **kwargs):
        if url.endswith("/api/show"):
            show = MagicMock(status_code=200)
            show.json.return_value = {"capabilities": ["completion"]}
            return show
        sent.append(kwargs["json"])
        return _Resp(state["body"])

    monkeypatch.setattr(requests, "post", post)
    return state, sent


def test_ollama_call_is_logged_with_options_counts_and_done_reason(tmp_path, fake_ollama):
    state, sent = fake_ollama
    state["body"] = {"response": "cut off", "prompt_eval_count": 100, "eval_count": 50,
                     "done_reason": "length"}
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)
    invoke = llm_utils.create_llm_invoke("gemma3:4b")
    with cl.call_context(agent_id="A1", agent_type="household", year=2, kind="decision", attempt=1):
        reply, stats = invoke("Q?")
    log.close()
    assert reply == "cut off" and stats.done_reason == "length"
    row = _lines(log.path)[0]
    assert row["prompt"] == "Q?" and row["reply"] == "cut off"
    assert row["done_reason"] == "length" and row["prompt_eval_count"] == 100
    assert row["eval_count"] == 50
    assert row["options"]["model"] == "gemma3:4b"
    assert row["options"]["num_ctx"] == 100 and row["options"]["num_predict"] == 50
    assert row["options"]["seed"] is None
    assert row["wall_seconds"] is not None and row["error"] is None
    # What the log says was sent is what was sent.
    assert sent[0]["options"]["num_ctx"] == row["options"]["num_ctx"]
    assert sent[0]["prompt"] == "Q?"


def test_truncation_counts_are_reported_not_judged(tmp_path, fake_ollama):
    state, _ = fake_ollama
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)
    invoke = llm_utils.create_llm_invoke("gemma3:4b")
    for body in (
        {"response": "a", "prompt_eval_count": 40, "eval_count": 5, "done_reason": "stop"},
        {"response": "b", "prompt_eval_count": 100, "eval_count": 5, "done_reason": "length"},
        {"response": "c", "prompt_eval_count": 120, "eval_count": 5, "done_reason": "stop"},
    ):
        state["body"] = body
        invoke("p")
    log.close()
    summary = log.summary()
    assert summary["calls_logged"] == 3
    assert summary["calls_done_reason_length"] == 1
    assert summary["calls_prompt_eval_count_ge_num_ctx"] == 2
    assert summary["max_prompt_eval_count"] == 120
    assert summary["calls_with_done_reason"] == 3 and summary["calls_with_prompt_eval_count"] == 3


def test_a_timeout_is_logged_as_an_error_line(tmp_path, monkeypatch, fake_ollama):
    import requests

    def post(url, **kwargs):
        if url.endswith("/api/show"):
            show = MagicMock(status_code=200)
            show.json.return_value = {"capabilities": ["completion"]}
            return show
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(requests, "post", post)
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)
    reply, stats = llm_utils._invoke_ollama_direct("gemma3:4b", "p", {}, False)
    log.close()
    assert reply == "" and stats.success is False
    assert _lines(log.path)[0]["error"] == "Timeout"


# ------------------------------------------------------------------ optional per-call seed

def test_seed_is_off_by_default_and_not_sent(tmp_path, fake_ollama):
    _, sent = fake_ollama
    llm_utils.create_llm_invoke("gemma3:4b")("p")
    assert "seed" not in sent[0]["options"]
    assert llm_utils.ollama_sampling_is_seeded() is False


def test_per_call_seed_is_sent_logged_and_makes_the_manifest_flag_true(tmp_path, fake_ollama):
    _, sent = fake_ollama
    cl.configure_sampling_seed("per_call", 42)
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    cl.activate(log)
    invoke = llm_utils.create_llm_invoke("gemma3:4b")
    with cl.call_context(agent_id="A1", year=3, kind="decision", attempt=1):
        invoke("p")
        invoke("p")
    with cl.call_context(agent_id="A1", year=3, kind="decision_retry", attempt=1):
        invoke("p")
    log.close()
    seeds = [s["options"]["seed"] for s in sent]
    assert seeds[0] == seeds[1] == cl.derive_call_seed(42, ["A1"], 3, "decision", 1)
    assert seeds[2] == cl.derive_call_seed(42, ["A1"], 3, "decision_retry", 1) != seeds[0]
    assert [r["options"]["seed"] for r in _lines(log.path)] == seeds
    assert llm_utils.ollama_sampling_is_seeded() is True


def test_derived_seed_depends_on_each_part_and_is_stable():
    base = cl.derive_call_seed(42, ["A1"], 3, "decision", 1)
    assert base == cl.derive_call_seed(42, ["A1"], 3, "decision", 1)
    assert 0 <= base < 2 ** 31
    for other in (cl.derive_call_seed(43, ["A1"], 3, "decision", 1),
                  cl.derive_call_seed(42, ["A2"], 3, "decision", 1),
                  cl.derive_call_seed(42, ["A1"], 4, "decision", 1),
                  cl.derive_call_seed(42, ["A1"], 3, "reflection", 1),
                  cl.derive_call_seed(42, ["A1"], 3, "decision", 2)):
        assert other != base


def test_sampling_seed_values():
    assert cl.normalise_seed_mode(None) == "off"
    assert cl.normalise_seed_mode("off") == "off"
    assert cl.normalise_seed_mode("per_call") == "per_call"
    with pytest.raises(ValueError):
        cl.normalise_seed_mode("always")


def test_agent_config_reads_the_seed_switch_and_the_runner_drops_it():
    from broker.utils.agent_config import AgentTypeConfig

    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": {"llm": {"sampling_seed": "per_call", "temperature": 1.0}}}
    assert cfg.get_llm_sampling_seed_mode() == "per_call"
    cfg._config = {"global_config": {"llm": {}}}
    assert cfg.get_llm_sampling_seed_mode() == "off"

    class _Cfg:
        def get_llm_params(self, agent_type):
            return {"sampling_seed": "per_call", "temperature": 1.0}

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = MagicMock(model="mock", verbose=False)
    runner._llm_cache = {}
    runner._llm_resolved_params = {}
    runner.broker = MagicMock()
    runner.broker.config = _Cfg()
    runner.get_llm_invoke("household")
    assert "sampling_seed" not in runner._llm_resolved_params["household"]


# ------------------------------------------------------------------ environment

def _run_result(code, out):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=out, stderr="")


def test_gpu_info_parses_every_gpu(monkeypatch):
    monkeypatch.setattr(renv.subprocess, "run", lambda *a, **k: _run_result(
        0, "NVIDIA GeForce RTX 4080 SUPER, 610.88, 16376 MiB\nNVIDIA T4, 535.1, 15360 MiB\n"))
    assert renv.gpu_info() == [
        {"name": "NVIDIA GeForce RTX 4080 SUPER", "driver_version": "610.88", "memory_total": "16376 MiB"},
        {"name": "NVIDIA T4", "driver_version": "535.1", "memory_total": "15360 MiB"}]


@pytest.mark.parametrize("failure", ["missing", "exit", "garbage", "timeout"])
def test_gpu_info_is_none_and_never_raises(monkeypatch, failure):
    def run(*a, **k):
        if failure == "missing":
            raise FileNotFoundError("nvidia-smi")
        if failure == "timeout":
            raise subprocess.TimeoutExpired("nvidia-smi", 5)
        if failure == "exit":
            return _run_result(9, "")
        return _run_result(0, "no gpus here\n")

    monkeypatch.setattr(renv.subprocess, "run", run)
    assert renv.gpu_info() is None


def test_run_environment_carries_gpu_cpu_and_interpreter(monkeypatch):
    monkeypatch.setattr(renv, "gpu_info", lambda *a, **k: None)
    env = renv.collect_run_environment("mock", captured_at="launch")
    assert env["gpu"] is None
    assert env["cpu"] == (renv.platform.processor() or None)
    assert env["python_executable"] == renv.home_collapsed(sys.executable)


def test_interpreter_path_carries_no_user_name(monkeypatch, tmp_path):
    home = tmp_path / "home" / "someone"
    monkeypatch.setattr(renv.Path, "home", classmethod(lambda cls: home))
    inside = str(home / "venv" / "python.exe")
    assert renv.home_collapsed(inside) == "~" + inside[len(str(home)):]
    assert "someone" not in renv.home_collapsed(inside)
    outside = str(tmp_path / "opt" / "python.exe")
    assert renv.home_collapsed(outside) == outside
    # A sibling folder whose name only starts with the home folder's name is not inside it.
    sibling = str(tmp_path / "home" / "someone-else" / "python.exe")
    assert renv.home_collapsed(sibling) == sibling
    assert renv.home_collapsed(None) is None


def test_environment_changed_lists_the_keys_that_differ():
    launch = {"captured_at": "launch", "errors": {}, "wagf_source_git": {"commit": "a", "dirty": False},
              "ollama_server_version": {"version": "0.23", "error": None},
              "packages": {"requests": "2.0", "numpy": "2.4"}}
    final = {"captured_at": "finalize", "errors": {"x": "y"},
             "wagf_source_git": {"commit": "a", "dirty": True},
             "ollama_server_version": {"version": "0.24", "error": None},
             "packages": {"requests": "2.1", "numpy": "2.4"}}
    assert renv.environment_changed(launch, final) == [
        "ollama_server_version.version", "packages.requests", "wagf_source_git.dirty"]
    assert renv.environment_changed(launch, launch) == []


def test_repo_relative_paths():
    root = renv.wagf_repo_root()
    assert renv.repo_relative(root / "examples" / "single_agent" / "agent_types.yaml") == \
        "examples/single_agent/agent_types.yaml"
    assert renv.repo_relative(Path(root.anchor) / "elsewhere" / "x.csv") is None
    rel = renv.launch_command_repo_relative(
        [str(root / "examples" / "single_agent" / "run_flood.py"), "--model", "mock",
         "--config-root", str(root / "examples" / "single_agent")])
    assert rel["script"] == "examples/single_agent/run_flood.py"
    assert rel["command"] == ("python examples/single_agent/run_flood.py --model mock "
                              "--config-root examples/single_agent")


def test_file_input_record(tmp_path):
    f = tmp_path / "in.csv"
    f.write_bytes(b"a,b\n1,2\n")
    rec = renv.file_input_record(f)
    import hashlib
    assert rec["present"] is True and rec["bytes"] == 8
    assert rec["sha256"] == hashlib.sha256(b"a,b\n1,2\n").hexdigest()
    assert rec["file"] == "in.csv" and rec["path_repo_relative"] is None
    missing = renv.file_input_record(tmp_path / "nope.csv")
    assert missing["present"] is False and missing["sha256"] is None


# ------------------------------------------------------------------ clean-tree gate

def _tree(monkeypatch, dirty=True, error=None):
    monkeypatch.setattr(renv, "wagf_source_git", lambda *a, **k: {
        "commit": "c", "dirty": dirty, "dirty_count": 3 if dirty else 0, "error": error})


def test_mock_runs_are_not_checked(monkeypatch):
    _tree(monkeypatch, dirty=True)
    rec = renv.require_clean_wagf_tree("mock", False)
    assert rec["checked"] is False and rec["allow_dirty_tree"] is False


def test_a_dirty_tree_refuses_a_real_model_and_says_why(monkeypatch):
    _tree(monkeypatch, dirty=True)
    with pytest.raises(SystemExit) as exc:
        renv.require_clean_wagf_tree("gemma3:4b", False)
    assert "3 uncommitted" in str(exc.value) and "--allow-dirty-tree" in str(exc.value)


def test_the_flag_overrides_and_is_recorded(monkeypatch):
    _tree(monkeypatch, dirty=True)
    rec = renv.require_clean_wagf_tree("gemma3:4b", True)
    assert rec == {"checked": True, "dirty": True, "dirty_count": 3,
                   "allow_dirty_tree": True, "overridden": True}


def test_a_clean_tree_passes(monkeypatch):
    _tree(monkeypatch, dirty=False)
    rec = renv.require_clean_wagf_tree("gemma3:4b", False)
    assert rec["checked"] is True and rec["dirty"] is False and rec["overridden"] is False


def test_an_unreadable_tree_is_reported_not_refused(monkeypatch):
    _tree(monkeypatch, dirty=None, error="CalledProcessError")
    assert renv.require_clean_wagf_tree("gemma3:4b", False)["checked"] is False


# ------------------------------------------------------------------ manifest fields

def _finalize_runner(tmp_path):
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.broker = MagicMock()
    runner.broker.model_adapter = MagicMock()
    runner.broker.model_adapter.config_path = None
    runner.memory_engine = MagicMock()
    runner.agents = {}
    runner.sim_engine = MagicMock()
    runner.config = MagicMock()
    runner.config.model = "mock"
    runner.config.verbose = False
    runner.config.seed = 42
    runner.config.governance_profile = "strict"
    runner.config.output_dir = tmp_path
    runner._llm_resolved_params = {}
    return runner


def test_manifest_keeps_launch_env_adds_finalize_env_and_what_changed(tmp_path):
    runner = _finalize_runner(tmp_path)
    runner._run_environment_at_launch = {
        "captured_at": "launch", "errors": {}, "wagf_source_git": {"commit": "a", "dirty": False},
        "ollama_server_version": {"version": "0.23", "error": None}}
    runner._run_environment_at_finalize = {
        "captured_at": "finalize", "errors": {}, "wagf_source_git": {"commit": "b", "dirty": False},
        "ollama_server_version": {"version": "0.23", "error": None}}
    meta = runner._collect_reproducibility_metadata()
    assert meta["run_environment"]["captured_at"] == "launch"
    assert meta["run_environment_at_finalize"]["captured_at"] == "finalize"
    assert meta["run_environment_changed"] == ["wagf_source_git.commit"]


def test_manifest_without_a_launch_reading_uses_the_finalize_one_for_both(tmp_path):
    meta = _finalize_runner(tmp_path)._collect_reproducibility_metadata()
    assert meta["run_environment"]["captured_at"] == "finalize"
    assert meta["run_environment_changed"] == []


def test_manifest_times_tree_flag_and_call_log_block(tmp_path):
    runner = _finalize_runner(tmp_path)
    runner._begin_run_records()
    with cl.call_context(agent_id="A1", year=1, kind="decision", attempt=1):
        cl.record_llm_call(prompt="p", reply="r", options={"num_ctx": 10},
                           prompt_eval_count=12, done_reason="length")
    runner._clean_tree_check = {"checked": True, "dirty": True, "dirty_count": 2,
                                "allow_dirty_tree": True, "overridden": True}
    runner._finish_run_records()
    meta = runner._collect_reproducibility_metadata()
    assert meta["started_at_utc"].endswith("Z") and meta["finished_at_utc"].endswith("Z")
    assert meta["finished_at_utc"] >= meta["started_at_utc"]
    assert isinstance(meta["wall_seconds"], float) and meta["wall_seconds"] >= 0
    assert "timestamp" in meta
    assert meta["allow_dirty_tree"] is True and meta["clean_tree_check"]["overridden"] is True
    block = meta["llm_call_log"]
    assert block["file"] == "llm_calls.jsonl" and block["calls_logged"] == 1
    assert block["calls_done_reason_length"] == 1
    assert block["calls_prompt_eval_count_ge_num_ctx"] == 1 and block["max_prompt_eval_count"] == 12
    import hashlib
    assert block["file_sha256"] == hashlib.sha256(
        (tmp_path / "llm_calls.jsonl").read_bytes()).hexdigest()
    # The same counts sit in run_integrity.json, and integrity_ok is not touched by them.
    ri = json.loads((tmp_path / "run_integrity.json").read_text(encoding="utf-8"))
    assert ri["llm_call_log"]["calls_done_reason_length"] == 1
    assert meta["run_integrity"]["integrity_ok"] == ri["integrity_ok"]
    assert cl.active_log() is None


def test_manifest_carries_repo_relative_paths(tmp_path):
    runner = _finalize_runner(tmp_path)
    root = renv.wagf_repo_root()
    runner.broker.model_adapter.config_path = root / "examples" / "single_agent" / "agent_types.yaml"
    runner._launch_argv = [str(root / "examples" / "single_agent" / "run_flood.py"), "--model", "mock"]
    meta = runner._collect_reproducibility_metadata()
    assert runner._repo_relative_config_path() == "examples/single_agent/agent_types.yaml"
    assert meta["launch_command_script_repo_relative"] == "examples/single_agent/run_flood.py"
    assert meta["launch_command_repo_relative"] == "python examples/single_agent/run_flood.py --model mock"
    assert len(meta["agent_types_config_sha256"]) == 64
    assert meta["config_hash"] == meta["agent_types_config_sha256"][:12]


# ------------------------------------------------------------------ generic runner behaviour

class _ProvCfg:
    def __init__(self, files=None, allow=False):
        self._v = {"input_files": files or {}, "allow_dirty_tree": allow}

    def get_provenance_config(self):
        return self._v


def _begin(tmp_path, model="mock", files=None, allow_cfg=False, allow_flag=False):
    runner = _finalize_runner(tmp_path)
    runner.config.model = model
    runner.config.allow_dirty_tree = allow_flag
    runner.broker.config = _ProvCfg(files, allow_cfg)
    return runner


def test_the_runner_refuses_a_real_model_on_a_dirty_tree(tmp_path, monkeypatch):
    _tree(monkeypatch, dirty=True)
    with pytest.raises(SystemExit) as exc:
        _begin(tmp_path, model="gemma3:4b")._begin_run_records()
    assert "uncommitted" in str(exc.value)
    assert not (tmp_path / "llm_calls.jsonl").exists()


@pytest.mark.parametrize("how", ["constructor", "config"])
def test_the_runner_override_is_recorded(tmp_path, monkeypatch, how):
    _tree(monkeypatch, dirty=True)
    runner = _begin(tmp_path, model="gemma3:4b",
                    allow_flag=how == "constructor", allow_cfg=how == "config")
    runner._begin_run_records()
    try:
        meta = runner._collect_reproducibility_metadata()
    finally:
        runner._finish_run_records()
    assert meta["allow_dirty_tree"] is True and meta["clean_tree_check"]["overridden"] is True


def test_an_entry_point_check_is_not_repeated_or_contradicted(tmp_path, monkeypatch):
    _tree(monkeypatch, dirty=True)
    runner = _begin(tmp_path, model="gemma3:4b")
    runner._clean_tree_check = {"checked": False, "handled_by": "broker.run launch_checks"}
    runner._begin_run_records()  # no SystemExit
    try:
        assert runner._clean_tree_check["handled_by"] == "broker.run launch_checks"
    finally:
        runner._finish_run_records()


def test_broker_run_launch_capture_presets_the_clean_tree_record():
    from broker.run._provenance import capture_launch_environment

    runner = SimpleNamespace(_clean_tree_check=None)
    capture_launch_environment(runner)
    assert runner._clean_tree_check["handled_by"].startswith("broker.run")


def test_builder_carries_the_dirty_tree_override():
    from broker.core.experiment_builder import ExperimentBuilder

    assert ExperimentBuilder().with_allow_dirty_tree(True)._allow_dirty_tree is True
    assert ExperimentBuilder()._allow_dirty_tree is False


def test_input_files_come_from_the_config_and_from_declare(tmp_path):
    import hashlib
    cfg_file = tmp_path / "from_config.csv"
    cfg_file.write_bytes(b"x\n")
    code_file = tmp_path / "declared.csv"
    code_file.write_bytes(b"y\n")
    runner = _begin(tmp_path, files={"from_config": str(cfg_file)})
    runner.declare_input_files({"declared": code_file})
    runner._begin_run_records()
    try:
        meta = runner._collect_reproducibility_metadata()
    finally:
        runner._finish_run_records()
    assert meta["input_files"]["from_config"]["sha256"] == hashlib.sha256(b"x\n").hexdigest()
    assert meta["input_files"]["declared"]["sha256"] == hashlib.sha256(b"y\n").hexdigest()


def test_a_missing_declared_file_is_recorded_as_absent(tmp_path):
    runner = _begin(tmp_path)
    runner.declare_input_files({"gone": tmp_path / "nope.csv"})
    runner._begin_run_records()
    try:
        assert runner._collect_reproducibility_metadata()["input_files"]["gone"]["present"] is False
    finally:
        runner._finish_run_records()


def test_provenance_config_block_is_validated():
    from broker.utils.agent_config import AgentTypeConfig

    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": {}}
    assert cfg.get_provenance_config() == {"input_files": {}, "allow_dirty_tree": False}
    cfg._config = {"global_config": {"provenance": {
        "input_files": {"a": "x.csv"}, "allow_dirty_tree": True}}}
    assert cfg.get_provenance_config() == {"input_files": {"a": "x.csv"}, "allow_dirty_tree": True}
    cfg._config = {"global_config": {"provenance": {"input_files": ["x.csv"]}}}
    with pytest.raises(ValueError):
        cfg.get_provenance_config()
    cfg._config = {"global_config": {"provenance": {"allow_dirty_tree": "yes"}}}
    with pytest.raises(ValueError):
        cfg.get_provenance_config()


# ------------------------------------------------------------------ ODD+LLM records (runtime state, roles, order, resolution)

class _Resp:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


def test_ollama_loaded_model_flags_cpu_offload(monkeypatch):
    body = {"models": [{"name": "gemma3:4b", "size": 100, "size_vram": 60, "context_length": 8192}]}
    monkeypatch.setattr(renv.requests, "get", lambda *a, **k: _Resp(body))
    rec = renv.ollama_loaded_model("gemma3:4b", "http://localhost:11434")
    assert rec["loaded"] is True and rec["cpu_offload"] is True
    assert rec["size"] == 100 and rec["size_vram"] == 60 and rec["context_length"] == 8192
    body["models"][0]["size_vram"] = 100
    assert renv.ollama_loaded_model("gemma3:4b", "http://x")["cpu_offload"] is False


def test_ollama_loaded_model_not_loaded_and_errors_never_raise(monkeypatch):
    monkeypatch.setattr(renv.requests, "get", lambda *a, **k: _Resp({"models": []}))
    rec = renv.ollama_loaded_model("gemma3:4b", "http://x")
    assert rec["loaded"] is False and rec["cpu_offload"] is None and rec["error"] is None

    def boom(*a, **k):
        raise ConnectionError("down")

    monkeypatch.setattr(renv.requests, "get", boom)
    rec = renv.ollama_loaded_model("gemma3:4b", "http://x")
    assert rec["loaded"] is None and rec["error"] == "ConnectionError"
    monkeypatch.setattr(renv.requests, "get", lambda *a, **k: _Resp({}, status=500))
    assert renv.ollama_loaded_model("gemma3:4b", "http://x")["error"] == "HTTP 500"


def test_the_environment_carries_the_loaded_model_and_a_change_is_listed(monkeypatch):
    mock_env = renv.collect_run_environment("mock", captured_at="launch")
    assert mock_env["ollama_loaded_model"]["loaded"] is None
    launch = {"ollama_loaded_model": {"loaded": False, "size_vram": None}}
    final = {"ollama_loaded_model": {"loaded": True, "size_vram": 5}}
    assert renv.environment_changed(launch, final) == [
        "ollama_loaded_model.loaded", "ollama_loaded_model.size_vram"]


def test_endpoint_names_hide_keys_and_urls(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://user:secret@gpu-box:11434")
    assert renv.endpoint_for_model("mock") == "mock"
    assert renv.endpoint_for_model("openai:gpt-6.1-sol") == "openai"
    ep = renv.endpoint_for_model("gemma3:4b")
    assert "secret" not in ep and "user" not in ep and ep.startswith("ollama@gpu-box")


def test_model_identity_is_empty_for_mock_and_cloud():
    assert renv.model_identity("mock")["digest"] is None
    assert renv.model_identity("openai:gpt-6.1-sol")["quantization"] is None


def test_the_call_log_tallies_roles(tmp_path):
    log = cl.LLMCallLog(tmp_path / "llm_calls.jsonl")
    for kind, atype, model in (("decision", "household", "m"), ("decision_retry", "household", "m"),
                               ("reflection", "household", "m"), ("other", "gov", "n")):
        with cl.call_context(agent_id="A", agent_type=atype, year=1, kind=kind, attempt=1):
            log.record(prompt="p", reply="r", options={"model": model})
    roles = log.roles_used()
    assert roles["decision"]["calls"] == 2 and roles["reflection"]["calls"] == 1
    assert roles["other"]["agent_type_models"] == [("gov", "n", 1)]
    assert set(roles) == {"decision", "reflection", "other"}
    log.close()


def _provenance_runner(tmp_path):
    runner = _finalize_runner(tmp_path)
    runner.broker.config = _ProvCfg()
    runner.broker.max_retries = 3
    runner.broker._intervention_framing = "plain"
    runner.broker._on_retry_exhausted = "default"
    runner.broker.skill_registry.get_default_skill.return_value = "do_nothing"
    runner.config.workers = 2
    runner.config.phase_order = None
    runner.agents = {"B": object(), "A": object()}
    return runner


def test_model_roles_block_has_one_entry_per_role_used(tmp_path):
    runner = _provenance_runner(tmp_path)
    runner._llm_resolved_params = {"household": {"temperature": 1.0, "top_p": 0.95, "top_k": 64,
                                                 "num_ctx": 8192, "num_predict": 4096}}
    runner._llm_sampling_seed_mode = "per_call"
    runner._llm_roles_used = {
        "decision": {"calls": 5, "agent_type_models": [("household", "mock", 5)]},
        "reflection": {"calls": 1, "agent_type_models": [("household", "mock", 1)]}}
    block = runner._model_roles_block()
    assert set(block) == {"decision", "reflection"}
    entry = block["decision"]["entries"][0]
    assert entry["model"] == "mock" and entry["endpoint"] == "mock"
    assert entry["adaptation"] == "none (off the shelf)" and entry["sampling_seed"] == "per_call"
    assert entry["decoding_options"]["num_ctx"] == 8192 and entry["calls"] == 5
    assert {"digest", "quantization"} <= set(entry)


def test_execution_order_block_reads_the_runner(tmp_path):
    import hashlib
    block = _provenance_runner(tmp_path)._execution_order_block()
    assert block["workers"] == 2 and block["agents_shuffled"] is False
    assert block["agent_shuffle_seed"] is None
    assert block["agent_ids_in_order"] == ["B", "A"] and block["agent_ids_count"] == 2
    assert block["agent_ids_sha256"] == hashlib.sha256(b"B" + bytes([10]) + b"A").hexdigest()
    assert block["results_applied_in"] == "submission order"


def test_resolution_policy_block_counts_from_the_audit_csv(tmp_path):
    csv_text = "\n".join([
        "agent_id,year,status,format_retries,parse_layer",
        "A,1,APPROVED,0,json",
        "A,2,APPROVED,1,json",
        "A,3,REJECTED_FALLBACK,0,json",
        "A,4,REJECTED,0,json",
        "A,5,ABORTED,2,",
        "A,6,APPROVED,0,default_fallback",
        "A,7,APPROVED,0,json", "A,8,APPROVED,0,json", "A,9,APPROVED,0,json", "A,10,APPROVED,0,json"])
    (tmp_path / "household_governance_audit.csv").write_text(csv_text, encoding="utf-8")
    block = _provenance_runner(tmp_path)._resolution_policy_block()
    assert block["max_governance_retries"] == 3 and block["max_format_attempts"] == 2
    assert block["retry_framing"] == "plain" and block["on_retry_exhausted"] == "default"
    assert block["default_skill"] == "do_nothing"
    c = block["counts"]
    assert c["rows"] == 10
    assert c["parse_failure_rows"] == 3 and c["parse_failure_rate"] == 0.3
    assert c["parse_failure_unrecovered_rows"] == 1
    assert c["parse_failure_recovered_by_format_retry_rows"] == 1
    assert c["retry_exhausted_rows"] == 2 and c["retry_exhausted_rate"] == 0.2


def test_resolution_counts_are_empty_without_an_audit_csv(tmp_path):
    from broker.components.analytics.audit import audit_resolution_counts
    assert audit_resolution_counts(tmp_path) == {}
    assert _provenance_runner(tmp_path)._resolution_policy_block()["counts"] is None


def test_manifest_has_the_new_blocks(tmp_path):
    runner = _provenance_runner(tmp_path)
    runner._run_environment_at_launch = {"captured_at": "launch", "errors": {},
        "ollama_loaded_model": {"loaded": False, "cpu_offload": None}}
    runner._run_environment_at_finalize = {"captured_at": "finalize", "errors": {},
        "ollama_loaded_model": {"loaded": True, "cpu_offload": True, "size": 10, "size_vram": 5}}
    meta = runner._collect_reproducibility_metadata()
    assert meta["ollama_loaded_model_at_launch"]["loaded"] is False
    assert meta["ollama_loaded_model_at_finalize"]["cpu_offload"] is True
    assert meta["ollama_cpu_offload"] is True
    assert "ollama_loaded_model.loaded" in meta["run_environment_changed"]
    for key in ("model_roles", "execution_order", "resolution_policy"):
        assert key in meta


# ------------------------------------------------------------------ mandatory records

import json as _json

from broker.utils import provenance_requirements as pr


def _good_manifest(**over):
    m = {
        "model": "gemma3:4b", "started_at_utc": "t0", "finished_at_utc": "t1", "wall_seconds": 1.0,
        "run_environment": {"captured_at": "launch", "wagf_source_git": {"dirty": False},
                            "ollama_server_version": {"version": "0.23.0"}},
        "run_environment_at_finalize": {"captured_at": "finalize",
                                        "ollama_server_version": {"version": "0.23.0"}},
        "run_environment_changed": [], "allow_dirty_tree": False, "input_files": {},
        "llm_call_log": {"calls_logged": 3, "calls_done_reason_length": 0,
                         "calls_prompt_eval_count_ge_num_ctx": 0, "max_prompt_eval_count": 100,
                         "write_failures": 0, "file_sha256": "abc"},
        "model_roles": {"decision": {}}, "execution_order": {"workers": 1},
        "resolution_policy": {"max_governance_retries": 3},
        "agent_types_config_repo_relative": "a.yaml", "agent_types_config_sha256": "x",
        "launch_command_script_repo_relative": "run.py",
        "clean_tree_check": {"checked": True, "dirty": False},
        "ollama_loaded_model_at_launch": {"loaded": False},
        "ollama_loaded_model_at_finalize": {"loaded": True, "cpu_offload": False},
        "ollama_cpu_offload": False, "llm_sampling_seed_mode": "per_call",
        "model_digest": "sha256:1", "model_digest_at_finalize": "sha256:1",
        "model_digest_changed": False,
    }
    m.update(over)
    return m


def _files(tmp_path, skip=()):
    for name in pr.REQUIRED_FILES:
        if name not in skip:
            (tmp_path / name).write_text("{}", encoding="utf-8")


def test_a_complete_real_run_is_submission_ready(tmp_path):
    _files(tmp_path)
    m = _good_manifest()
    fields = pr.seal(m, tmp_path)
    assert fields["provenance_complete"] is True and fields["provenance_missing"] == []
    # the manifest file is written after the seal, so it is not checked there
    assert fields["submission_blockers"] == [] and fields["submission_ready"] is True


def test_a_mock_run_is_never_submission_ready(tmp_path):
    _files(tmp_path)
    fields = pr.seal(_good_manifest(model="mock"), tmp_path)
    assert fields["provenance_complete"] is True
    assert fields["submission_ready"] is False and "mock model" in fields["submission_blockers"]


@pytest.mark.parametrize("key", list(pr.REQUIRED_MANIFEST_KEYS) + list(pr.REQUIRED_PRESENT_KEYS))
def test_every_required_manifest_key_is_checked(tmp_path, key):
    _files(tmp_path)
    m = _good_manifest()
    m.pop(key)
    fields = pr.seal(m, tmp_path)
    assert fields["provenance_complete"] is False
    assert f"manifest:{key}" in fields["provenance_missing"]
    assert fields["submission_ready"] is False and "provenance incomplete" in fields["submission_blockers"]


@pytest.mark.parametrize("name", [n for n in pr.REQUIRED_FILES if n != "reproducibility_manifest.json"])
def test_every_required_file_is_checked(tmp_path, name):
    _files(tmp_path, skip=(name,))
    fields = pr.seal(_good_manifest(), tmp_path)
    assert fields["provenance_complete"] is False and f"file:{name}" in fields["provenance_missing"]


def test_lost_call_log_lines_make_the_records_incomplete(tmp_path):
    _files(tmp_path)
    m = _good_manifest()
    m["llm_call_log"]["write_failures"] = 2
    assert pr.seal(m, tmp_path)["provenance_complete"] is False


def test_a_launch_reading_that_was_not_taken_at_launch_is_incomplete(tmp_path):
    _files(tmp_path)
    m = _good_manifest(run_environment={"captured_at": "finalize"})
    assert pr.seal(m, tmp_path)["provenance_complete"] is False


@pytest.mark.parametrize("over,item", [
    # What _collect_reproducibility_metadata stores when a block builder raises.
    ({"model_roles": {"error": "KeyError"}}, "manifest:model_roles (could not be built"),
    ({"execution_order": {"error": "TypeError"}}, "manifest:execution_order (could not be built"),
    ({"resolution_policy": {"error": "OSError"}}, "manifest:resolution_policy (could not be built"),
    # What it stores when an environment reading raises.
    ({"run_environment_at_finalize": {"errors": {"_collection": "OSError"}}},
     "manifest:run_environment_at_finalize.captured_at"),
    ({"run_environment_at_finalize": {"captured_at": "finalize",
                                      "errors": {"_collection": "OSError"}}},
     "manifest:run_environment_at_finalize (reading failed"),
    ({"run_environment": {"captured_at": "launch", "errors": {"_collection": "OSError"}}},
     "manifest:run_environment (reading failed"),
    ({"run_environment_at_finalize": {"captured_at": "launch"}},
     "manifest:run_environment_at_finalize.captured_at"),
    # A declared input file missing or unreadable at launch.
    ({"input_files": {"flood_years": {"file": "flood_years.csv", "present": False,
                                      "sha256": None}}}, "manifest:input_files.flood_years"),
    ({"input_files": {"crss": {"file": "x.csv", "present": True, "sha256": None,
                               "error": "PermissionError"}}}, "manifest:input_files.crss"),
    ({"input_files": ["not", "a", "mapping"]}, "manifest:input_files (not a mapping)"),
])
def test_a_record_that_failed_to_build_is_not_counted_as_present(tmp_path, over, item):
    _files(tmp_path)
    fields = pr.seal(_good_manifest(**over), tmp_path)
    assert fields["provenance_complete"] is False
    assert any(m.startswith(item) for m in fields["provenance_missing"]), fields["provenance_missing"]
    assert "provenance incomplete" in fields["submission_blockers"]


def test_the_reviewers_all_stubs_manifest_is_incomplete(tmp_path):
    # Every fallback at once: the case a completeness check must not pass.
    _files(tmp_path)
    m = _good_manifest(
        model_roles={"error": "KeyError"}, execution_order={"error": "KeyError"},
        resolution_policy={"error": "KeyError"},
        run_environment_at_finalize={"errors": {"_collection": "OSError"}},
        ollama_loaded_model_at_launch={"loaded": None, "error": "ConnectionError"},
        ollama_loaded_model_at_finalize={"loaded": None, "error": "ConnectionError"})
    fields = pr.seal(m, tmp_path)
    assert fields["provenance_complete"] is False and len(fields["provenance_missing"]) >= 4
    assert any("loaded-model reading failed" in b for b in fields["submission_blockers"])


def test_a_present_input_file_with_a_digest_is_complete(tmp_path):
    _files(tmp_path)
    m = _good_manifest(input_files={"flood_years": {"file": "flood_years.csv", "present": True,
                                                    "bytes": 10, "sha256": "ab" * 32}})
    assert pr.seal(m, tmp_path)["provenance_complete"] is True


def test_worker_threads_keep_their_own_call_context(tmp_path):
    import threading
    log = cl.LLMCallLog(tmp_path / "calls.jsonl")
    cl.activate(log)
    barrier = threading.Barrier(2)

    def worker(agent):
        with cl.call_context(agent_id=agent, year=3, kind="decision", attempt=1):
            barrier.wait()  # both contexts are set before either call is recorded
            cl.record_llm_call(prompt=f"prompt for {agent}", reply="ok")

    try:
        threads = [threading.Thread(target=worker, args=(a,)) for a in ("A1", "A2")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
    finally:
        cl.deactivate(log)
        log.close()
    rows = _lines(tmp_path / "calls.jsonl")
    assert sorted((r["agent_ids"], r["prompt"]) for r in rows) == [
        (["A1"], "prompt for A1"), (["A2"], "prompt for A2")]
    assert cl.current_context() == {}


@pytest.mark.parametrize("over,blocker", [
    ({"allow_dirty_tree": True}, "dirty tree"),
    ({"clean_tree_check": {"checked": True, "dirty": True}}, "dirty tree"),
    ({"llm_call_log": {**_good_manifest()["llm_call_log"], "calls_done_reason_length": 2}}, "truncated"),
    ({"llm_call_log": {**_good_manifest()["llm_call_log"],
                       "calls_prompt_eval_count_ge_num_ctx": 1}}, "num_ctx"),
    ({"ollama_cpu_offload": True}, "cpu_offload"),
    ({"ollama_loaded_model_at_finalize": {"loaded": True, "cpu_offload": True}}, "cpu_offload"),
    ({"run_environment_changed": ["wagf_source_git.commit"]}, "WAGF commit changed"),
    ({"run_environment_changed": ["ollama_server_version.version"]}, "Ollama version changed"),
    ({"model_digest_changed": True}, "model digest changed"),
    ({"model_digest_at_finalize": None}, "model digest unavailable"),
    ({"run_status": "aborted_exception"}, "did not finish"),
    ({"run_environment": {"captured_at": "launch", "ollama_server_version": {"version": None}},
      "run_environment_at_finalize": {"captured_at": "finalize",
                                      "ollama_server_version": {"version": None}}},
     "Ollama server version unavailable"),
    ({"ollama_loaded_model_at_finalize": {"loaded": None, "error": "ConnectionError"}},
     "loaded-model reading failed"),
    ({"ollama_loaded_model_at_finalize": {"loaded": False}}, "model not loaded at finalize"),
    ({"ollama_loaded_model_at_finalize": {"loaded": True, "cpu_offload": None}},
     "GPU / CPU split unknown at finalize"),
])
def test_each_submission_blocker_fires(tmp_path, over, blocker):
    _files(tmp_path)
    fields = pr.seal(_good_manifest(**over), tmp_path)
    assert fields["submission_ready"] is False
    assert any(blocker in b for b in fields["submission_blockers"]), fields["submission_blockers"]


def _write_finished(tmp_path, manifest_over=None, integrity_over=None):
    _files(tmp_path)
    m = _good_manifest()
    fields = pr.seal(m, tmp_path)
    m.update(manifest_over or {})
    (tmp_path / "reproducibility_manifest.json").write_text(_json.dumps(m), encoding="utf-8")
    (tmp_path / "run_integrity.json").write_text(
        _json.dumps({**fields, **(integrity_over or {})}), encoding="utf-8")
    return m


def test_enforce_complete_passes_a_complete_run(tmp_path):
    _write_finished(tmp_path)
    assert pr.enforce_complete(tmp_path)["provenance_complete"] is True


def test_enforce_complete_exits_non_zero_when_incomplete(tmp_path):
    _write_finished(tmp_path, manifest_over={"provenance_complete": False,
                                              "provenance_missing": ["manifest:model_roles"]})
    with pytest.raises(SystemExit) as exc:
        pr.enforce_complete(tmp_path)
    assert exc.value.code == 3


def test_enforce_complete_exits_when_run_integrity_lacks_the_verdict(tmp_path):
    _write_finished(tmp_path)
    (tmp_path / "run_integrity.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        pr.enforce_complete(tmp_path)
    assert exc.value.code == 3


def test_enforce_complete_exits_when_the_manifest_is_missing(tmp_path):
    with pytest.raises(SystemExit) as exc:
        pr.enforce_complete(tmp_path)
    assert exc.value.code == 3


def test_a_run_that_cannot_open_its_call_log_does_not_start(tmp_path):
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("x", encoding="utf-8")
    runner = _begin(blocker / "out")
    with pytest.raises(pr.RunRecordsError, match="model-call log"):
        runner._begin_run_records()


def test_a_run_without_an_output_folder_does_not_start(tmp_path):
    runner = _begin(tmp_path)
    runner.config.output_dir = None
    with pytest.raises(pr.RunRecordsError):
        runner._begin_run_records()


def test_a_line_that_cannot_be_written_stops_the_run_at_the_step_end(tmp_path, monkeypatch):
    runner = _begin(tmp_path)
    runner._begin_run_records()
    try:
        log = runner._llm_call_log

        def broken(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "open", broken)
        with cl.call_context(agent_id="A1", year=1, kind="decision", attempt=1):
            cl.record_llm_call(prompt="p", reply="r", options={})  # no exception inside the call
        monkeypatch.undo()
        assert log.failure and "disk full" in log.failure and log.write_failures == 1
        with pytest.raises(pr.RunRecordsError, match="disk full"):
            runner._raise_if_records_failed()
    finally:
        runner._finish_run_records()


def test_finalize_raises_when_a_record_failed_and_writes_what_it_can(tmp_path):
    runner = _provenance_runner(tmp_path)
    runner.config.model = "mock"
    runner._begin_run_records()
    runner._llm_call_log.failure = "could not write llm_calls.jsonl: OSError: disk full"
    runner._llm_call_log.write_failures = 1
    runner.broker.audit_writer = MagicMock()
    runner._configured_grid_expectation = lambda iterations: {}
    with pytest.raises(pr.RunRecordsError, match="disk full"):
        runner._finalize_experiment(iterations=1)
    fields = runner._provenance_fields  # what the manifest and run_integrity.json were given
    assert fields["provenance_complete"] is False
    assert any("write_failures" in item for item in fields["provenance_missing"])


@pytest.mark.parametrize("abort_attr", ["_llm_safeguard_abort", "_llm_journal_abort",
                                        "_generic_abort"])
def test_finalize_keeps_the_error_a_run_is_already_stopping_on(tmp_path, abort_attr):
    # finalize runs in run()'s finally: raising there would replace the run's own error.
    runner = _provenance_runner(tmp_path)
    runner.config.model = "mock"
    runner._begin_run_records()
    runner._llm_call_log.failure = "could not write llm_calls.jsonl: OSError: disk full"
    runner._llm_call_log.write_failures = 1
    runner.broker.audit_writer = MagicMock()
    runner._configured_grid_expectation = lambda iterations: {}
    if abort_attr == "_llm_safeguard_abort":
        from broker.utils.llm_safeguard import LLMFailureRateAborted
        own_error = LLMFailureRateAborted(observed_rate=0.5, window=10, threshold=0.2,
                                          failed_count=5, decisions_in_window=10)
    elif abort_attr == "_llm_journal_abort":
        from broker.utils.llm_journal import JournalWriteError
        own_error = JournalWriteError("the run's own error")
    else:
        own_error = RuntimeError("the run's own error")
    setattr(runner, abort_attr, own_error)
    runner._finalize_experiment(iterations=1)  # does not raise
    assert runner._provenance_fields["provenance_complete"] is False
    assert any("disk full" in e for e in runner._records_errors)


def test_a_records_error_ends_the_run_through_the_existing_abort_path():
    from broker.utils.llm_journal import JournalWriteError
    assert issubclass(pr.RunRecordsError, JournalWriteError)


def test_no_setting_turns_the_records_off():
    from broker.utils.agent_config import AgentTypeConfig

    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    for key in ("enabled", "call_log", "llm_call_log", "records", "disable", "off", "manifest"):
        cfg._config = {"global_config": {"provenance": {key: False}}}
        with pytest.raises(ValueError, match="no setting turns them off"):
            cfg.get_provenance_config()
    import dataclasses
    from broker.core.experiment_runner import ExperimentConfig
    names = {f.name for f in dataclasses.fields(ExperimentConfig)}
    assert not {n for n in names if any(w in n for w in ("record", "provenance", "call_log", "manifest"))}


def test_the_runner_has_no_method_that_skips_the_records():
    import inspect
    src = inspect.getsource(ExperimentRunner.run)
    assert "self._begin_run_records()" in src


def test_every_runner_that_builds_an_experiment_checks_its_records():
    root = renv.wagf_repo_root()
    scripts = [
        "examples/single_agent/run_flood.py", "examples/irrigation_abm/run_experiment.py",
        "examples/multi_agent/flood/run_unified_experiment.py",
        "examples/governed_flood/run_experiment.py", "examples/cat_model/run_cat.py",
        "examples/cat_model/run_cat_ma.py", "examples/quickstart/01_barebone.py",
        "examples/quickstart/02_governance.py",
        "examples/reservoir_control_multidim/run_reservoir_multidim.py",
        "examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py",
        "broker/run/_entry.py",
    ]
    for rel in scripts:
        # python -m broker.run checks in broker/run/__main__.py, which reads _entry.LAST_RUN_OUTPUT
        checked = "broker/run/__main__.py" if rel == "broker/run/_entry.py" else rel
        assert "enforce_complete(" in (root / checked).read_text(encoding="utf-8"), rel
    # a script that builds an experiment but is not on the list above fails this test
    builders = [str(p.relative_to(root)).replace("\\", "/")
                for base in ("examples", "broker")
                for p in (root / base).rglob("*.py")
                if "ExperimentBuilder()" in p.read_text(encoding="utf-8", errors="replace")
                and "tests" not in p.parts and p.name != "experiment_builder.py"]
    unlisted = [b for b in builders if b not in scripts and not b.startswith("broker/core/")
                and not b.startswith("broker/experiments/")]
    assert not unlisted, unlisted


@pytest.mark.parametrize("key", list(pr.REQUIRED_NULLABLE_KEYS))
def test_a_path_key_must_be_present_and_none_only_blocks_submission(tmp_path, key):
    _files(tmp_path)
    m = _good_manifest()
    m.pop(key)
    assert f"manifest:{key}" in pr.seal(m, tmp_path)["provenance_missing"]
    m = _good_manifest(**{key: None})
    fields = pr.seal(m, tmp_path)
    assert fields["provenance_complete"] is True
    assert fields["submission_ready"] is False
    assert any("outside the WAGF repo" in b for b in fields["submission_blockers"])

