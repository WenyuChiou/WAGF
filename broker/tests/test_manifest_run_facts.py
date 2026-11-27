"""Manifest run facts: decoding values sent, no home path, call-seed formula, machine facts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

from broker.core.experiment_runner import ExperimentRunner
from broker.utils import llm_call_log as cl
from broker.utils import llm_utils
from broker.utils import run_environment as env


def _runner(tmp_path: Path, resolved) -> ExperimentRunner:
    r = ExperimentRunner.__new__(ExperimentRunner)
    r.broker = MagicMock()
    r.broker.model_adapter.config_path = None
    r.memory_engine = MagicMock()
    r.agents = {}
    r.sim_engine = MagicMock()
    r.config = MagicMock()
    r.config.model = "mock"
    r.config.verbose = False
    r.config.seed = 42
    r.config.governance_profile = "strict"
    r.config.output_dir = tmp_path
    r._llm_resolved_params = resolved
    return r


def test_top_level_decoding_matches_values_sent(monkeypatch, tmp_path):
    # LLM_CONFIG says 2048 / no sampling; the type actually sent 4096 / 1.0 / 0.95 / 64.
    monkeypatch.setattr(llm_utils, "LLM_CONFIG", llm_utils.LLMConfig(num_predict=2048, num_ctx=8192))
    sent = {"num_predict": 4096, "num_ctx": 8192, "temperature": 1.0, "top_p": 0.95,
            "top_k": 64, "model": "mock"}
    md = _runner(tmp_path, {"household": dict(sent)})._collect_reproducibility_metadata()
    assert (md["temperature"], md["top_p"], md["top_k"]) == (1.0, 0.95, 64)
    assert (md["num_ctx"], md["num_predict"]) == (8192, 4096)


def test_top_level_decoding_null_when_types_differ(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_utils, "LLM_CONFIG", llm_utils.LLMConfig(num_predict=2048, num_ctx=8192))
    res = {"a": {"num_predict": 4096, "num_ctx": 8192, "temperature": 0.5, "model": "mock"},
           "b": {"num_predict": 1024, "num_ctx": 8192, "temperature": 0.9, "model": "mock"}}
    md = _runner(tmp_path, res)._collect_reproducibility_metadata()
    assert md["temperature"] is None and md["num_predict"] is None
    assert md["num_ctx"] == 8192
    assert "differs" in md["llm_decoding_top_level_source"]


def test_launch_command_and_config_path_carry_no_home(tmp_path):
    home = str(Path.home())
    r = _runner(tmp_path, {})
    r._launch_command = f"run.py --output {home}/x/out"
    r._launch_argv = ["run.py", "--output", f"{home}/x/out"]
    r.broker.model_adapter.config_path = Path(home) / "elsewhere" / "agent_types.yaml"
    assert home.lower() not in r._collect_reproducibility_metadata()["launch_command"].lower()
    assert home.lower() not in r._agent_types_config_recorded().lower()
    assert r._agent_types_config_recorded().startswith("~")


def test_scrub_home_paths_nested_and_leaves_lookalikes():
    home = str(Path.home())
    bs = chr(92)
    out = env.scrub_home_paths({"a": [f"{home}{bs}x", f"{home.replace(bs, '/')}/y"],
                                "b": {"c": home + "X/z"}, "n": 3})
    assert out["a"] == [f"~{bs}x", "~/y"] and out["b"]["c"] == home + "X/z" and out["n"] == 3


def test_collapse_home_before_punctuation():
    home = str(Path.home())
    for tail in (".", ";", ")", ",", ":", "]", "="):
        assert env.collapse_home_in_text(f"error at {home}{tail}") == f"error at ~{tail}"
    assert env.collapse_home_in_text(f"a;{home};b") == "a;~;b"
    assert env.collapse_home_in_text(home + "_old/x") == home + "_old/x"


def test_finalize_scrub_removes_home_and_names_package_file(tmp_path, monkeypatch):
    home = str(Path.home())
    r = _runner(tmp_path, {})
    out = r._add_package_file_and_scrub({"a": f"{home}/x", "b": [{"c": f"see {home}."}]})
    assert home.lower() not in json.dumps(out).lower()
    assert out["python_packages_file"]["file"] == "python_packages.txt"
    assert (tmp_path / "python_packages.txt").exists()
    assert not (tmp_path / "python_packages.txt.tmp").exists()
    # A failing package write still leaves the scrub in place.
    monkeypatch.setattr(env, "write_installed_packages",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    out2 = r._add_package_file_and_scrub({"a": f"{home}/x"})
    assert out2["a"] == "~/x" and out2["python_packages_file"]["error"] == "RuntimeError"


def test_decoding_type_without_values_turns_value_null(monkeypatch, tmp_path):
    # A type whose invoke was built but sent no top_k: top-level top_k is null, others kept.
    monkeypatch.setattr(llm_utils, "LLM_CONFIG", llm_utils.LLMConfig(num_predict=2048, num_ctx=8192))
    res = {"a": {"num_predict": 4096, "num_ctx": 8192, "top_k": 64, "model": "mock"},
           "b": {"num_predict": 4096, "num_ctx": 8192, "model": "mock"}}
    md = _runner(tmp_path, res)._collect_reproducibility_metadata()
    assert md["top_k"] is None and md["num_predict"] == 4096


def test_call_seed_formula_reproduces_derive_call_seed():
    d = cl.describe_call_seed("per_call", 42)
    assert d["base_seed"] == 42 and d["mode"] == "per_call"
    assert d["inputs"] == ["base_seed", "agent_ids", "year", "kind", "attempt"]
    # Re-derive by hand from the described formula.
    key = "42|A1,A2|3|decision|1"
    expect = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") % 2 ** 31
    assert expect == cl.derive_call_seed(42, ["A2", "A1"], 3, "decision", 1)
    assert "sha256" in d["formula"] and "2**31" in d["formula"]


def test_manifest_has_seed_derivation(tmp_path):
    r = _runner(tmp_path, {})
    r._llm_sampling_seed_mode = "per_call"
    md = r._collect_reproducibility_metadata()
    assert md["llm_call_seed_derivation"]["base_seed"] == 42


def test_ram_cuda_and_packages_never_raise(monkeypatch, tmp_path):
    assert env.ram_total_bytes() is None or env.ram_total_bytes() > 0
    def boom(*a, **k):
        raise FileNotFoundError("no nvidia-smi")
    monkeypatch.setattr(env.subprocess, "run", boom)
    c = env.cuda_version()
    assert c["version"] is None and c["error"] == "FileNotFoundError"
    assert env.gpu_info() is None
    rec = env.collect_run_environment("mock", "t")
    assert "ram_total_bytes" in rec and rec["cuda_version"] is None
    assert rec["cuda_version_error"] == "FileNotFoundError"


def test_cuda_version_parses_header(monkeypatch):
    out = MagicMock(returncode=0, stdout="| NVIDIA-SMI 1  Driver Version: 5   CUDA Version: 12.4 |")
    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: out)
    assert env.cuda_version() == {"version": "12.4", "error": None}
    out.stdout = "| KMD Version: 610.88   CUDA UMD Version: 13.3 |"
    assert env.cuda_version()["version"] == "13.3"


def test_installed_packages_file(tmp_path, monkeypatch):
    rec = env.write_installed_packages(tmp_path)
    assert rec["error"] is None and rec["count"] > 0
    data = (tmp_path / rec["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == rec["sha256"]
    lines = data.decode().splitlines()
    assert len(lines) == rec["count"] and all("==" in ln for ln in lines)
    monkeypatch.setattr(env, "installed_packages", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    bad = env.write_installed_packages(tmp_path)
    assert bad["file"] is None and bad["error"].startswith("RuntimeError")
