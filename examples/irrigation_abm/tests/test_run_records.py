"""Irrigation case: what a mock run leaves behind for a reviewer (model-call log, manifest fields).

One 2-year mock run of the simple_executed variant in a subprocess; the checks read its files.
Needs the optional CRSS bundle (ref/CRSS_DB/CRSS_DB). No Ollama.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "examples" / "irrigation_abm" / "run_experiment.py"
CRSS = ROOT / "ref" / "CRSS_DB" / "CRSS_DB"

pytestmark = pytest.mark.skipif(not CRSS.is_dir(), reason="ref/CRSS_DB/CRSS_DB is absent")


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("records") / "irrigation"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--model", "mock", "--real", "--years", "2", "--seed", "42",
         "--memory-seed", "42", "--paper-water-margin", "0.4", "--cluster-method", "hy2021",
         "--governance-mode", "strict", "--config-dir",
         "examples/irrigation_abm/config_variants/simple_executed", "--workers", "1",
         "--output", str(out)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=900)
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr[-1500:]
    manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    calls = [json.loads(x) for x in
             (out / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    traces = [json.loads(x) for f in (out / "raw").glob("*_traces.jsonl")
              for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out, manifest, calls, [t for t in traces if "agent_id" in t]


def test_call_log_fields_and_kinds(run):
    _, _, calls, _ = run
    assert calls
    for i, row in enumerate(calls, 1):
        assert row["call_index"] == i
        assert row["prompt_sha256"] == hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest()
        assert row["agent_type"] == "irrigation_farmer" and row["agent_ids"]
        assert row["options"]["model"] == "mock" and row["year"] in (1, 2)
    kinds = {r["kind"] for r in calls}
    assert {"decision", "decision_retry", "reflection"} <= kinds


def test_decision_prompts_match_the_traces_and_reflection_prompts_match_their_file(run):
    out, _, calls, traces = run
    first = {(c["agent_ids"][0], c["year"]): c["prompt"]
             for c in calls if c["kind"] == "decision" and c["attempt"] == 1}
    for t in traces:
        assert first[(t["agent_id"], t["year"])] == t["input"]
    # reflection_prompts.jsonl stays as it was; the call log holds the same prompts.
    old = [json.loads(x) for x in
           (out / "reflection_prompts.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    logged = [c["prompt"] for c in calls if c["kind"] in ("reflection", "reflection_retry")]
    assert [o["prompt"] for o in old] == logged


def test_retry_prompts_are_kept_in_the_raw_traces(run):
    _, _, calls, traces = run
    retried = [t for t in traces if t.get("retry_prompts")]
    assert retried, "retry_prompt_columns is off in the executed variant"
    logged = {c["prompt"] for c in calls if c["kind"] == "decision_retry"}
    for t in retried:
        for prompt in t["retry_prompts"]:
            assert prompt in logged


def test_manifest_times_environment_paths_and_inputs(run):
    out, m, calls, _ = run
    assert m["started_at_utc"].endswith("Z") and m["finished_at_utc"].endswith("Z")
    assert m["wall_seconds"] >= 0
    assert m["llm_call_log"]["calls_logged"] == len(calls)
    assert m["run_integrity"]["llm_call_log"]["calls_logged"] == len(calls)
    assert m["run_environment"]["captured_at"] == "launch"
    assert m["run_environment_at_finalize"]["captured_at"] == "finalize"
    assert m["allow_dirty_tree"] is False
    assert m["llm_sampling_seeded"] is True and all(
        isinstance(c["options"]["seed"], int) for c in calls)
    assert m["agent_types_config_repo_relative"] == (
        "examples/irrigation_abm/config_variants/simple_executed/agent_types.yaml")
    assert m["launch_command_script_repo_relative"] == "examples/irrigation_abm/run_experiment.py"
    config = ROOT / m["agent_types_config_repo_relative"]
    assert m["agent_types_config_sha256"] == hashlib.sha256(config.read_bytes()).hexdigest()
    inputs = m["input_files"]
    assert set(inputs) == {
        "abm_params_csv", "ub_discrete_states_csv", "lb_discrete_states_csv",
        "ub_groups_and_agents_csv", "lb_historical_annual_diversion_csv",
        "ub_historical_annual_depletion_csv", "precip_projection_csv"}
    for rec in inputs.values():
        assert rec["present"] is True and len(rec["sha256"]) == 64
        assert hashlib.sha256((ROOT / rec["path_repo_relative"]).read_bytes()).hexdigest() == rec["sha256"]


def test_input_file_list_follows_the_flags():
    import argparse
    from examples.irrigation_abm.run_experiment import _irrigation_input_files

    ref = ROOT / "ref"
    assert _irrigation_input_files(argparse.Namespace(real=False, hindcast=False), ref) == {}
    hind = _irrigation_input_files(argparse.Namespace(real=True, hindcast=True), ref)
    assert "precip_projection_csv" not in hind and len(hind) == 6


def test_a_dirty_tree_stops_a_real_model_before_anything_is_written(tmp_path, monkeypatch):
    from broker.utils import run_environment as renv
    from examples.irrigation_abm import run_experiment

    monkeypatch.setattr(renv, "wagf_source_git", lambda *a, **k: {
        "commit": "c", "dirty": True, "dirty_count": 4, "error": None})
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "--model", "gemma3:4b", "--years", "1",
                                      "--output", str(out)])
    with pytest.raises(SystemExit) as exc:
        run_experiment.main()
    assert "4 uncommitted" in str(exc.value)
    assert not out.exists()


def test_manifest_has_roles_order_and_resolution_blocks(run):
    _, m, calls, _ = run
    assert sum(r["calls"] for r in m["model_roles"].values()) == len(calls)
    assert m["model_roles"]["decision"]["entries"][0]["agent_type"] == "irrigation_farmer"
    assert m["execution_order"]["workers"] == 1 and m["execution_order"]["agent_ids_count"] > 0
    assert m["resolution_policy"]["counts"]["rows"] > 0


def test_records_are_complete_and_a_mock_run_is_not_submission_ready(run):
    out, m, _, _ = run
    integrity = json.loads((out / "run_integrity.json").read_text(encoding="utf-8"))
    for doc in (m, integrity):
        assert doc["provenance_complete"] is True and doc["provenance_missing"] == []
        assert doc["submission_ready"] is False and "mock model" in doc["submission_blockers"]


def test_a_missing_record_makes_the_exit_non_zero(run, tmp_path):
    import shutil
    from broker.utils.provenance_requirements import enforce_complete

    out, _, _, _ = run
    enforce_complete(out)  # complete: no exit
    broken = tmp_path / "broken"
    shutil.copytree(out, broken)
    (broken / "llm_calls.jsonl").unlink()
    manifest = json.loads((broken / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    manifest.pop("model_roles")
    (broken / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        enforce_complete(broken)
    assert exc.value.code == 3
