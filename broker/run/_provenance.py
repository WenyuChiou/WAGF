"""Launch-time provenance checks for ``python -m broker.run``."""
from __future__ import annotations

import json
from pathlib import Path

from broker.utils.llm_utils import is_cloud_provider_model, is_mock_model
from broker.utils.run_environment import collect_run_environment


def capture_launch_environment(runner) -> dict:
    """Record the run environment now; the runner replays it into the manifest."""
    model = getattr(getattr(runner, "config", None), "model", None)
    env = collect_run_environment(model, captured_at="launch")
    runner._run_environment_at_launch = env
    # The clean-tree decision belongs to launch_checks (refuses under --strict-provenance,
    # records otherwise); the runner must not add a second, different refusal.
    if not isinstance(getattr(runner, "_clean_tree_check", None), dict):
        runner._clean_tree_check = {
            "checked": False, "dirty": None, "dirty_count": None,
            "allow_dirty_tree": False, "overridden": False,
            "handled_by": "broker.run launch_checks (--strict-provenance)"}
    return env


def _cwd_inside_wagf_source() -> bool:
    try:
        import broker
        root = Path(broker.__file__).resolve().parents[1]
        return Path.cwd().resolve().is_relative_to(root)
    except Exception:
        return False


def launch_checks(runner, model) -> tuple:
    """Return ``(checks, problems)``; the checks are always recorded, problems only refuse under --strict-provenance."""
    checks: dict = {}
    problems: list = []
    dirty = getattr(runner, "_git_dirty_at_launch", None)
    commit = getattr(runner, "_git_commit_at_launch", "unavailable")

    env = getattr(runner, "_run_environment_at_launch", None)
    tree_ok = dirty is False
    if dirty:  # None is reported under metadata_queries instead
        if getattr(runner, "_git_dirty_files_truncated_at_launch", False):
            count = "200+"
        else:
            count = len(getattr(runner, "_git_dirty_files_at_launch", None) or [])
        problems.append(f"{count} uncommitted changes in the git working tree of the current directory")
    source = env.get("wagf_source_git") if isinstance(env, dict) else None
    if isinstance(source, dict) and source.get("dirty") is True:
        tree_ok = False
        if not (dirty and _cwd_inside_wagf_source()):  # else it is the tree already reported
            problems.append(f"{source.get('dirty_count')} uncommitted changes in the WAGF source tree")
    checks["clean_tree"] = "pass" if tree_ok else "fail"

    if isinstance(model, str) and is_mock_model(model):
        checks["model_digest"] = "not applicable: mock model"
    elif isinstance(model, str) and is_cloud_provider_model(model):
        checks["model_digest"] = "not applicable: cloud model"
    else:
        meta = getattr(runner, "_model_metadata_at_launch", None)
        digest = meta.get("model_digest") if isinstance(meta, dict) else None
        if isinstance(digest, str) and digest.strip():
            checks["model_digest"] = "pass"
        else:
            checks["model_digest"] = "fail"
            problems.append(f"no model digest for {model}")

    env_errors = env.get("errors") if isinstance(env, dict) else None
    git_unreadable = commit == "unavailable" or dirty is None
    if git_unreadable or env_errors:
        checks["metadata_queries"] = "fail"
        if git_unreadable:
            problems.append("git state could not be read in the current directory")
        if env_errors:
            problems.append(f"run environment lookup failed: {', '.join(env_errors)}")
    else:
        checks["metadata_queries"] = "pass"

    checks["manifest_write"] = "not run"
    return checks, problems


def manifest_problem(output_dir) -> "str | None":
    """None when the manifest exists, parses as an object and has ``run_environment``."""
    path = Path(output_dir) / "reproducibility_manifest.json"
    try:
        exists = path.is_file()
    except OSError:
        return "reproducibility_manifest.json could not be read"
    if not exists:
        return "reproducibility_manifest.json was not written"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return "reproducibility_manifest.json could not be read"
    except ValueError:
        return "reproducibility_manifest.json is not valid JSON"
    if not isinstance(data, dict):
        return "reproducibility_manifest.json is not a JSON object"
    if "run_environment" not in data:
        return "reproducibility_manifest.json has no run_environment"
    return None
