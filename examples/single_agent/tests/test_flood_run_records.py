"""Flood case: what a mock run leaves behind for a reviewer (model-call log, manifest fields).

One 2-year, 3-agent mock run in a subprocess; the checks read its files. No Ollama.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "examples" / "single_agent" / "run_flood.py"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("records") / "flood"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--model", "mock", "--years", "2", "--agents", "3",
         "--seed", "42", "--output", str(out)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr[-1500:]
    manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    calls = [json.loads(x) for x in
             (out / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    traces = [json.loads(x) for f in (out / "raw").glob("*_traces.jsonl")
              for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out, manifest, calls, [t for t in traces if "agent_id" in t]


def test_every_call_line_has_the_fields(run):
    _, _, calls, _ = run
    assert calls
    for i, row in enumerate(calls, 1):
        assert row["call_index"] == i
        assert set(row) >= {"agent_ids", "agent_type", "year", "kind", "attempt", "prompt",
                            "prompt_sha256", "reply", "options", "prompt_eval_count", "eval_count",
                            "done_reason", "wall_seconds", "started_at_utc", "error"}
        assert row["prompt_sha256"] == hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest()
        assert set(row["options"]) == {"model", "temperature", "top_p", "top_k", "num_ctx",
                                       "num_predict", "think", "seed"}
        assert row["options"]["model"] == "mock"
        assert isinstance(row["options"]["seed"], int)  # sampling_seed: per_call in the config
        assert row["agent_type"] == "household" and row["agent_ids"]
        assert row["reply"] is not None
    kinds = {r["kind"] for r in calls}
    assert {"decision", "decision_retry", "reflection"} <= kinds <= {
        "decision", "decision_retry", "reflection", "reflection_retry", "other"}


def test_logged_decision_prompts_are_the_prompts_in_the_traces(run):
    _, _, calls, traces = run
    first = {(c["agent_ids"][0], c["year"]): c["prompt"]
             for c in calls if c["kind"] == "decision" and c["attempt"] == 1}
    assert traces
    for t in traces:
        assert first[(t["agent_id"], t["year"])] == t["input"]
    retry_prompts = {c["prompt"] for c in calls if c["kind"] == "decision_retry"}
    for t in traces:
        for prompt in t.get("retry_prompts") or []:
            assert prompt in retry_prompts


def test_manifest_times_files_and_environment(run):
    out, m, calls, _ = run
    assert m["started_at_utc"].endswith("Z") and m["finished_at_utc"].endswith("Z")
    assert m["wall_seconds"] >= 0 and "timestamp" in m
    block = m["llm_call_log"]
    assert block["calls_logged"] == len(calls)
    assert block["file_sha256"] == hashlib.sha256((out / "llm_calls.jsonl").read_bytes()).hexdigest()
    assert m["run_integrity"]["llm_call_log"]["calls_logged"] == len(calls)
    ri = json.loads((out / "run_integrity.json").read_text(encoding="utf-8"))
    assert ri["llm_call_log"]["calls_logged"] == len(calls)
    assert m["run_environment"]["captured_at"] == "launch"
    assert m["run_environment_at_finalize"]["captured_at"] == "finalize"
    assert m["run_environment_changed"] == []
    for key in ("gpu", "cpu", "python_executable"):
        assert key in m["run_environment"]
    assert m["allow_dirty_tree"] is False and m["clean_tree_check"]["checked"] is False
    assert m["agent_types_config_repo_relative"] == "examples/single_agent/agent_types.yaml"
    assert m["launch_command_script_repo_relative"] == "examples/single_agent/run_flood.py"
    assert m["llm_sampling_seeded"] is True and m["llm_sampling_seed_mode"] == "per_call"


def test_flood_inputs_block(run):
    _, m, _, _ = run
    block = m["flood_inputs"]
    profiles = ROOT / "examples" / "single_agent" / "agent_initial_profiles.csv"
    years = ROOT / "examples" / "single_agent" / "flood_years.csv"
    inputs = m["input_files"]
    assert inputs["agent_profiles"]["sha256"] == hashlib.sha256(profiles.read_bytes()).hexdigest()
    assert inputs["flood_years"]["sha256"] == hashlib.sha256(years.read_bytes()).hexdigest()
    assert inputs["agent_profiles"]["path_repo_relative"] == "examples/single_agent/agent_initial_profiles.csv"
    assert "profile_file" not in block and "flood_years_file" not in block
    assert block["flood_mode"] == "fixed" and block["n_agents"] == 3 and block["n_years"] == 2
    assert block["flood_years_scheduled"] == [3, 4, 9]
    assert block["flood_years_used"] == []  # none of 3, 4, 9 falls in a 2-year run
    assert "profile_source" in block


def test_flood_years_used_follows_the_run_length():
    import examples.single_agent.run_flood as rf

    block = rf._flood_inputs_block(
        profile_source="csv", profile_path=ROOT / "examples" / "single_agent" / "agent_initial_profiles.csv",
        flood_years_path=ROOT / "examples" / "single_agent" / "flood_years.csv",
        flood_years_scheduled=[3, 4, 9], flood_mode="fixed", seed=1, years=5, n_agents=3)
    assert block["flood_years_used"] == [3, 4]
    prob = rf._flood_inputs_block(
        profile_source="csv", profile_path=ROOT / "examples" / "single_agent" / "agent_initial_profiles.csv",
        flood_years_path=ROOT / "examples" / "single_agent" / "flood_years.csv",
        flood_years_scheduled=[3, 4, 9], flood_mode="prob", seed=1, years=20, n_agents=3)
    again = rf._flood_inputs_block(
        profile_source="csv", profile_path=ROOT / "examples" / "single_agent" / "agent_initial_profiles.csv",
        flood_years_path=ROOT / "examples" / "single_agent" / "flood_years.csv",
        flood_years_scheduled=[3, 4, 9], flood_mode="prob", seed=1, years=20, n_agents=3)
    assert prob["flood_years_used"] == again["flood_years_used"]


def test_flood_inputs_report_whether_they_reached_the_manifest(tmp_path):
    import examples.single_agent.run_flood as rf

    block = {"flood_mode": "fixed", "n_agents": 3}
    assert rf._record_flood_inputs_provenance(tmp_path, block) is False  # no manifest yet
    (tmp_path / "reproducibility_manifest.json").write_text("{not json", encoding="utf-8")
    assert rf._record_flood_inputs_provenance(tmp_path, block) is False  # unreadable
    (tmp_path / "reproducibility_manifest.json").write_text('{"model": "mock"}', encoding="utf-8")
    assert rf._record_flood_inputs_provenance(tmp_path, block) is True
    saved = json.loads((tmp_path / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert saved["flood_inputs"] == block and saved["model"] == "mock"


def test_a_dirty_tree_stops_a_real_model_before_anything_is_written(tmp_path, monkeypatch):
    import examples.single_agent.run_flood as rf
    from broker.utils import run_environment as renv

    monkeypatch.setattr(renv, "wagf_source_git", lambda *a, **k: {
        "commit": "c", "dirty": True, "dirty_count": 4, "error": None})
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as exc:
        rf.run_parity_benchmark(model="gemma3:4b", years=1, agents_count=1, custom_output=str(out))
    assert "4 uncommitted" in str(exc.value)
    assert not out.exists()


def test_the_cli_accepts_allow_dirty_tree():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"--allow-dirty-tree"' in text and "allow_dirty_tree=args.allow_dirty_tree" in text


def test_manifest_has_roles_order_and_resolution_blocks(run):
    _, m, calls, _ = run
    roles = m["model_roles"]
    assert {"decision", "reflection"} <= set(roles)
    assert sum(r["calls"] for r in roles.values()) == len(calls)
    entry = roles["decision"]["entries"][0]
    assert entry["model"] == "mock" and entry["endpoint"] == "mock"
    assert entry["adaptation"] == "none (off the shelf)"
    order = m["execution_order"]
    assert order["workers"] == 1 and order["agents_shuffled"] is False
    assert order["agent_ids_count"] == 3 and len(order["agent_ids_in_order"]) == 3
    policy = m["resolution_policy"]
    assert policy["max_governance_retries"] == m["max_retries_resolved"]
    assert policy["on_retry_exhausted"] in ("default", "keep_proposal")
    assert policy["counts"]["rows"] > 0
    assert m["run_environment"]["ollama_loaded_model"]["loaded"] is None  # mock: no Ollama


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
