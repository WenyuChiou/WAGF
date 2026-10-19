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
