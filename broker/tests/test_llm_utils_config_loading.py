import os
import subprocess
import sys
from pathlib import Path


def test_llm_utils_import_without_default_agent_types_uses_defaults_quietly(tmp_path: Path):
    """Importing llm_utils from a generic cwd should not warn about config."""
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "ignore",
            "-c",
            "import broker.utils.llm_utils",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "Agent type configuration not found" not in combined
