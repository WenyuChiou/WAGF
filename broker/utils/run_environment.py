"""Run-environment facts for the reproducibility manifest.

Small pure functions. None of them raises: a failed lookup is recorded as text in
the returned dict so a manifest write never fails because of it. Error text is an
exception TYPE NAME only, because a message can carry a path or a URL with
credentials.
"""
from __future__ import annotations

import importlib.metadata as importlib_metadata
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

import requests

from broker.utils.llm_utils import get_ollama_base_url, is_cloud_provider_model, is_mock_model

NOT_OLLAMA = "not an Ollama model"
_DIST_NAME = "water-agent-governance-framework"
_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _parse_project_table(text: str) -> dict:
    """Read ``version`` and ``dependencies`` from the ``[project]`` table (Python 3.10 fallback)."""
    in_project = False
    name = None
    version = None
    deps: list = []
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if in_deps:
            if stripped.startswith("]"):
                in_deps = False
                continue
            deps.extend(re.findall(r'"([^"]*)"', stripped.split("#", 1)[0]))
            continue
        if stripped.startswith("["):
            in_project = stripped == "[project]"
            continue
        if not in_project:
            continue
        match = re.match(r'version\s*=\s*"([^"]*)"', stripped)
        name_match = re.match(r'name\s*=\s*"([^"]*)"', stripped)
        if name_match:
            name = name_match.group(1)
        elif match:
            version = match.group(1)
        elif re.match(r"dependencies\s*=\s*\[", stripped):
            rest = stripped.split("[", 1)[1].split("#", 1)[0]
            deps.extend(re.findall(r'"([^"]*)"', rest))
            in_deps = "]" not in rest
    return {"name": name, "version": version, "dependencies": deps}


def _read_pyproject(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib
    except ImportError:  # Python 3.10
        return _parse_project_table(text)
    project = tomllib.loads(text).get("project", {})
    deps = project.get("dependencies", [])
    return {"name": project.get("name"), "version": project.get("version"), "dependencies": [d for d in deps if isinstance(d, str)]}


def _dependency_list() -> tuple:
    """Return (wagf_version, source, requirement strings).

    pyproject.toml next to the imported package comes first: on the owner's machine
    the editable install's metadata is stale (it reports 0.2.0 while pyproject says
    0.6.0), so the installed metadata is only the fallback.
    """
    import broker

    pyproject = Path(broker.__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject.is_file():
        data = _read_pyproject(pyproject)
        if data.get("name") == _DIST_NAME:  # not some other project's pyproject.toml
            return data["version"], "pyproject.toml", list(data["dependencies"])
    try:
        version = importlib_metadata.version(_DIST_NAME)
        requires = importlib_metadata.requires(_DIST_NAME) or []
    except importlib_metadata.PackageNotFoundError:
        return None, None, []
    return version, "installed metadata", [r for r in requires if "extra ==" not in r]


def package_versions() -> dict:
    result: dict = {"wagf_version": None, "wagf_version_source": None, "packages": {}, "error": None}
    try:
        version, source, requirements = _dependency_list()
        result["wagf_version"], result["wagf_version_source"] = version, source
        if source is None:
            result["error"] = "dependency list unavailable"
            return result
        for requirement in requirements:
            match = _NAME_RE.match(requirement)
            if not match:
                continue
            name = match.group(1)
            try:
                result["packages"][name] = importlib_metadata.version(name)
            except importlib_metadata.PackageNotFoundError:
                result["packages"][name] = None
    except Exception as exc:
        result["error"] = type(exc).__name__
    return result


def os_info() -> dict:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }


def ollama_server_version(base_url: str, timeout: float = 2.0) -> dict:
    try:
        half = min(timeout, 2.0) / 2  # connect + read together stay within 2 s
        response = requests.get(f"{base_url.rstrip('/')}/api/version", timeout=(half, half))
        if not 200 <= response.status_code < 300:
            return {"version": None, "error": f"HTTP {response.status_code}"}
        body = response.json()
        version = body.get("version") if isinstance(body, dict) else None
        if isinstance(version, str) and version:
            return {"version": version, "error": None}
        return {"version": None, "error": "response had no version"}
    except Exception as exc:
        return {"version": None, "error": type(exc).__name__}


def wagf_source_git(root: "Path | None" = None) -> "dict | None":
    """Commit and dirty state of the WAGF source tree; None when it is not a git checkout.

    ``.git`` is tested with ``exists()`` because a worktree has a ``.git`` file.
    The error is the exception type name only.
    """
    result: dict = {"commit": None, "dirty": None, "dirty_count": None, "error": None}
    try:
        if root is None:
            import broker
            root = Path(broker.__file__).resolve().parents[1]
        if not (root / ".git").exists():
            return None
        run = dict(capture_output=True, text=True, timeout=10, check=True)
        result["commit"] = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], **run).stdout.strip()
        lines = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], **run).stdout.splitlines()
        result["dirty"], result["dirty_count"] = bool(lines), len(lines)
    except Exception as exc:
        result["error"] = type(exc).__name__
    return result


def collect_run_environment(model: Any, captured_at: str) -> dict:
    errors: dict = {}
    packages: dict = {"wagf_version": None, "wagf_version_source": None, "packages": {}, "error": None}
    try:
        packages = package_versions()
    except Exception as exc:
        packages["error"] = type(exc).__name__
    if packages.get("error"):
        errors["packages"] = packages["error"]
    try:
        os_part = os_info()
    except Exception as exc:
        os_part = {}
        errors["os"] = type(exc).__name__
    ollama: dict = {"version": None, "error": NOT_OLLAMA}
    try:
        if isinstance(model, str) and not is_mock_model(model) and not is_cloud_provider_model(model):
            ollama = ollama_server_version(get_ollama_base_url())
            if ollama.get("error"):
                errors["ollama_server_version"] = ollama["error"]
    except Exception as exc:
        ollama = {"version": None, "error": type(exc).__name__}
        errors["ollama_server_version"] = ollama["error"]
    source_git = None
    try:
        source_git = wagf_source_git()
        if source_git and source_git.get("error"):
            errors["wagf_source_git"] = source_git["error"]
    except Exception as exc:
        source_git = {"commit": None, "dirty": None, "dirty_count": None, "error": type(exc).__name__}
        errors["wagf_source_git"] = source_git["error"]
    return {
        "captured_at": captured_at,
        "wagf_version": packages.get("wagf_version"),
        "wagf_version_source": packages.get("wagf_version_source"),
        "packages": packages.get("packages", {}),
        "os": os_part,
        "ollama_server_version": ollama,
        "wagf_source_git": source_git,
        "errors": errors,
    }
