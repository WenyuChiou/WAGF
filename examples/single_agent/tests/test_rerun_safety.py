"""A flood run must preserve all artifacts when an output folder is reused."""

import hashlib
import json
from pathlib import Path
import sys

import pytest

from examples.single_agent import run_flood

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripted_mock_driver as mock_driver  # noqa: E402


def _snapshot(folder):
    """Compare the whole tree, including unrelated files and empty directories."""
    return {
        path.relative_to(folder).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns
        ) if path.is_file() else None
        for path in folder.rglob("*")
    }


@pytest.fixture
def mock_run(monkeypatch):
    calls = []
    invoke = mock_driver.scripted_mock_invoke

    def record_call(prompt):
        calls.append(prompt)
        return invoke(prompt)

    monkeypatch.setattr(mock_driver, "scripted_mock_invoke", record_call)

    def run(output):
        mock_driver.reset_state()
        mock_driver.run_scripted_mock(
            governance_mode="strict", output=str(output), agents=2, years=2, seed=42,
        )

    return run, calls


def _assert_refused_unchanged(output, run, calls):
    before = _snapshot(output)
    call_count = len(calls)
    try:
        with pytest.raises(ValueError) as refused:
            run(output)
        message = str(refused.value)
        assert str(output) in message
        assert "move" in message.lower()
        assert "--output" in message
    finally:
        assert _snapshot(output) == before
        assert len(calls) == call_count


def test_finished_mock_run_refuses_rerun_without_changing_any_file(tmp_path, mock_run):
    run, calls = mock_run
    output = tmp_path / "finished"
    run(output)
    assert (output / "reproducibility_manifest.json").is_file()
    assert json.loads((output / "run_integrity.json").read_text())["integrity_ok"] is True
    assert (output / "raw" / "household_traces.jsonl").is_file()
    assert (output / "reflection_log.jsonl").is_file()
    (output / "notes.txt").write_text("Preserve these user notes too.\n")
    _assert_refused_unchanged(output, run, calls)


def test_unfinished_run_refuses_rerun_without_changing_any_file(tmp_path, mock_run):
    run, calls = mock_run
    output = tmp_path / "unfinished"
    (output / "raw").mkdir(parents=True)
    (output / "raw" / "household_traces.jsonl").write_text('{"partial": true}\n')
    (output / "reflection_log.jsonl").write_text('{"prior_reflection": true}\n')
    (output / "reflection_checks.jsonl").write_text('{"prior_check": true}\n')
    _assert_refused_unchanged(output, run, calls)


@pytest.mark.parametrize("existing_empty_folder", [False, True], ids=["absent", "empty"])
def test_fresh_folder_completes_mock_run(tmp_path, mock_run, existing_empty_folder):
    run, calls = mock_run
    output = tmp_path / "fresh"
    if existing_empty_folder:
        output.mkdir()
    run(output)
    assert calls
    integrity = json.loads((output / "run_integrity.json").read_text())
    assert integrity["integrity_ok"] is True
    assert integrity["reflection_engine_wired"] is True
    assert len((output / "reflection_log.jsonl").read_text().splitlines()) == 4
    checks = [json.loads(line) for line in (output / "reflection_checks.jsonl").read_text().splitlines()]
    assert len(checks) == 5  # Four reflections, including one checked retry.
    assert {(check["agent_id"], check["period"]) for check in checks} == {
        (agent, year) for agent in ("Agent_1", "Agent_2") for year in (1, 2)
    }
    assert (output / "simulation_log.csv").is_file()


@pytest.mark.parametrize("artifact", [
    "reproducibility_manifest.json", "config_snapshot.yaml", "governance_summary.json",
    "run_integrity.json", "audit_summary.json", "household_governance_audit.csv",
    "household_governance_audit.schema.json", "raw/household_traces.jsonl",
    "validator_health.csv", "validator_health_by_agent_type.csv", "reflection_log.jsonl",
    "reflection_checks.jsonl", "adaptation_cumulative_state.png", "simulation_log.csv",
    "external_llm_stdout.log", "raw/",
])
def test_lone_artifact_refuses_before_setup_even_when_empty(tmp_path, monkeypatch, artifact):
    output = tmp_path / "prior"
    path = output / artifact
    if artifact.endswith("/"):
        path.mkdir(parents=True)
    else:
        path.parent.mkdir(parents=True)
        path.touch()

    def forbidden_setup(*args, **kwargs):
        pytest.fail("Existing output must be refused before registry/model setup")

    monkeypatch.setattr(run_flood, "SkillRegistry", forbidden_setup)
    _assert_refused_unchanged(
        output,
        lambda folder: run_flood.run_parity_benchmark(model="mock", custom_output=str(folder)),
        [],
    )


def test_wrapper_owned_files_alone_do_not_block_a_fresh_run(tmp_path, mock_run):
    """The batch script writes run.log (stdout redirect) and ollama_version.txt
    into the folder just before it starts the runner; those alone are allowed."""
    run, calls = mock_run
    output = tmp_path / "batch_fresh"
    output.mkdir()
    (output / "run.log").write_text("")
    (output / "ollama_version.txt").write_text("start attempt 1\nollama version is 0.40.3\n")
    run(output)
    assert calls
    assert json.loads((output / "run_integrity.json").read_text())["integrity_ok"] is True


@pytest.mark.parametrize("extra", ["notes.txt", "raw/"])
def test_wrapper_owned_files_do_not_hide_an_earlier_run(tmp_path, mock_run, extra):
    run, calls = mock_run
    output = tmp_path / "batch_prior"
    output.mkdir()
    (output / "run.log").write_text("old\n")
    (output / "ollama_version.txt").write_text("old\n")
    if extra.endswith("/"):
        (output / extra).mkdir()
    else:
        (output / extra).write_text("x\n")
    _assert_refused_unchanged(output, run, calls)


def test_a_directory_named_like_a_wrapper_file_is_refused(tmp_path, mock_run):
    run, calls = mock_run
    output = tmp_path / "odd"
    (output / "run.log").mkdir(parents=True)
    _assert_refused_unchanged(output, run, calls)


def test_output_path_that_is_a_file_is_refused_with_a_clear_message(tmp_path, mock_run):
    run, calls = mock_run
    output = tmp_path / "not_a_folder"
    output.write_text("x\n")
    with pytest.raises(ValueError, match="is a file"):
        run(output)
    assert output.read_text() == "x\n"
