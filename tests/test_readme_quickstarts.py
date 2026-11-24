"""Run the two commands users copy from the front page with isolated outputs."""
import csv
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("examples/single_agent/run_flood.py", "household_governance_audit.csv", 2, "do_nothing"),
    ("examples/irrigation_abm/run_experiment.py", "irrigation_farmer_governance_audit.csv", 4,
     "maintain_demand"),
]


def _quickstart_command(path, entrypoint):
    text = path.read_text(encoding="utf-8")
    commands = re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL)
    matches = [command for command in commands if command.startswith(f"python {entrypoint} ")]
    assert len(matches) == 1, f"Expected one quickstart command for {entrypoint} in {path}"
    return matches[0]


@pytest.mark.parametrize("entrypoint,audit_name,expected_rows,expected_default", CASES,
                         ids=["flood", "irrigation"])
def test_readme_quickstart(entrypoint, audit_name, expected_rows, expected_default, tmp_path):
    command = shlex.split(_quickstart_command(ROOT / "README.md", entrypoint))
    assert command[command.index("--model") + 1] == "mock"
    output = tmp_path / "run"
    command[0] = sys.executable
    command[command.index("--output") + 1] = str(output)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                            encoding="utf-8", timeout=120)
    console = result.stdout + result.stderr  # Governance logging uses stderr.
    assert result.returncode == 0, console
    assert "[Governance:Retry]" in console
    assert f"Executing '{expected_default}'" in console
    with (output / audit_name).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == expected_rows
    assert all(row["executed_skill"] for row in rows)
    assert (output / "simulation_log.csv").stat().st_size > 0
    assert (output / "run_integrity.json").stat().st_size > 0


@pytest.mark.parametrize("entrypoint", [case[0] for case in CASES], ids=["flood", "irrigation"])
def test_quickstart_commands_match(entrypoint):
    paths = [
        ROOT / "README.md",
        ROOT / "examples/README.md",
        ROOT / "docs/tutorial/01-first-run.md",
    ]
    commands = [_quickstart_command(path, entrypoint) for path in paths]
    assert commands[1:] == commands[:-1]


# --- Tutorial chapter 4 needs CRSS data that is not distributed ------------------------------
CH4 = ROOT / "docs/tutorial/04-water-model.md"


def _ch4_real_command():
    text = CH4.read_text(encoding="utf-8")
    for match in re.finditer(r"```bash\n(.*?)\n```", text, flags=re.DOTALL):
        if match.group(1).startswith("python examples/irrigation_abm/run_experiment.py") \
                and "--real" in match.group(1):
            return text, match.group(1), match.start()
    raise AssertionError("chapter 4 has no --real irrigation command")


def test_ch4_tells_reader_about_crss_before_the_command():
    text, _command, start = _ch4_real_command()
    before = text[:start].lower()
    assert "crss" in before and "not distributed" in before
    assert "data.md" in before


@pytest.mark.parametrize("path", ["README.md", "examples/README.md", "docs/tutorial/01-first-run.md"])
def test_pages_that_point_to_ch4_name_the_crss_requirement(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    # Look at the paragraph that links chapter 4.
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if "04-water-model.md" in p]
    assert paragraphs, f"{path} no longer links chapter 4"
    assert all("CRSS" in p and "DATA.md" in p for p in paragraphs), path


def test_ch4_command_fails_on_missing_crss_with_the_path_the_docs_name(tmp_path):
    """With ref/CRSS_DB hidden (a clean clone), the failure names the folder DATA.md describes."""
    if (ROOT / "ref" / "CRSS_DB").exists():
        pytest.skip("CRSS_DB is present here; the clean-clone case cannot be shown")
    _text, command, _start = _ch4_real_command()
    argv = shlex.split(command)
    argv[0] = sys.executable
    argv[argv.index("--output") + 1] = str(tmp_path / "ch4")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True,
                            encoding="utf-8", timeout=120)
    assert result.returncode != 0
    assert "CRSS_DB" in result.stdout + result.stderr
    assert "ref/CRSS_DB/CRSS_DB" in (ROOT / "DATA.md").read_text(encoding="utf-8")


# --- The first-run demo: README's first command, and the places that repeat it ----------------
RESERVOIR = "examples/reservoir_control/run_reservoir_ops.py"


def test_readme_first_run_shows_block_reason_repair_and_effect(tmp_path):
    command = shlex.split(_quickstart_command(ROOT / "README.md", RESERVOIR))
    assert command[command.index("--model") + 1] == "mock"
    command[0] = sys.executable
    command[command.index("--output") + 1] = str(tmp_path / "run")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                            encoding="utf-8", timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = result.stdout.split("Block and repair in this run:")[1]
    assert "BLOCKED:" in summary and "breaks dead_pool_violation" in summary
    assert "APPROVED:" in summary
    assert "toy reservoir release target:" in summary


def test_first_run_command_is_the_same_everywhere():
    readme = _quickstart_command(ROOT / "README.md", RESERVOIR)
    for path in ["examples/reservoir_control/README.md"]:
        assert _quickstart_command(ROOT / path, RESERVOIR) == readme, path
    for path in [".claude/skills/wagf-quickstart/SKILL.md",
                 ".claude/skills/wagf-quickstart/references/smoke_test_recipe.md"]:
        assert readme in (ROOT / path).read_text(encoding="utf-8"), path
    zh = (ROOT / "README_zh.md").read_text(encoding="utf-8")
    assert readme in zh
