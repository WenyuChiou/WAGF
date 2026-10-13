"""CI smoke coverage for the standalone governed-flood runner (mock only)."""

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "examples/governed_flood/run_experiment.py"
PROFILES = ROOT / "examples/single_agent/agent_initial_profiles.csv"


def run_mock(output, *extra_args):
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--model", "mock", "--years", "2",
         "--seed", "42", "--output", str(output), *extra_args],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    (output.parent / "runner.stdout.log").write_text(result.stdout, encoding="utf-8")
    (output.parent / "runner.stderr.log").write_text(result.stderr, encoding="utf-8")
    return result


def test_mock_run_from_repo_root_writes_five_agents_two_years(tmp_path):
    output = tmp_path / "results"
    result = run_mock(output, "--agents", "5")
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"[Inputs] Household profiles: {PROFILES}" in result.stdout
    assert f"[Inputs] Flood years: {PROFILES.with_name('flood_years.csv')}" in result.stdout
    with (output / "simulation_log.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 10
    assert {(row["agent_id"], int(row["year"])) for row in rows} == {
        (f"Agent_{agent}", year) for agent in range(1, 6) for year in (1, 2)
    }


def test_agent_count_exceeding_profiles_fails_at_startup(tmp_path):
    with PROFILES.open(encoding="utf-8", newline="") as stream:
        count = len(list(csv.DictReader(stream)))
    output = tmp_path / "results"
    result = run_mock(output, "--initial-agents", str(PROFILES),
                      "--agents", str(count + 1))
    assert result.returncode != 0
    assert f"--agents {count + 1}" in result.stderr
    assert f"only {count} household profiles" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("flag, filename", [
    ("--initial-agents", "missing_profiles.csv"),
    ("--flood-years", "missing_flood_years.csv"),
])
def test_missing_input_names_file_and_default_source(tmp_path, flag, filename):
    missing = tmp_path / filename
    output = tmp_path / "results"
    result = run_mock(output, flag, str(missing), "--agents", "5")
    assert result.returncode != 0
    assert str(missing) in result.stderr
    assert "Default inputs" in result.stderr
    assert "single_agent" in result.stderr
    assert not output.exists()


def test_agent_selection_uses_natural_ids_and_preserves_omitted_limit():
    from examples.governed_flood.run_experiment import _limit_agents_for_run

    agents = {"Agent_10": object(), "Agent_2": object(), "Agent_1": object()}
    assert list(_limit_agents_for_run(agents, 2)) == ["Agent_1", "Agent_2"]
    assert _limit_agents_for_run(agents, None) is agents
    with pytest.raises(SystemExit, match="positive"):
        _limit_agents_for_run(agents, 0)


def test_input_resolution_prefers_override_then_local_then_tracked(tmp_path):
    from examples.governed_flood.run_experiment import resolve_input_path

    local = tmp_path / "local.csv"
    tracked = tmp_path / "tracked.csv"
    override = tmp_path / "override.csv"
    tracked.write_text("tracked", encoding="utf-8")
    assert resolve_input_path(None, local, tracked) == tracked
    local.write_text("local", encoding="utf-8")
    assert resolve_input_path(None, local, tracked) == local
    override.write_text("override", encoding="utf-8")
    assert resolve_input_path(override, local, tracked) == override
    with pytest.raises(SystemExit, match="Default inputs"):
        resolve_input_path(tmp_path / "missing.csv", local, tracked)
