"""Run-environment facts for the reproducibility manifest.

Small pure functions. None of them raises: a failed lookup is recorded as text in
the returned dict so a manifest write never fails because of it. Error text is an
exception TYPE NAME only, because a message can carry a path or a URL with
credentials.
"""
from __future__ import annotations

import importlib.metadata as importlib_metadata
import os
import platform
import re
import subprocess
import sys
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


def ollama_loaded_model(model: Any, base_url: str, timeout: float = 2.0) -> dict:
    """What Ollama reports (``/api/ps``) for ``model``: loaded size, GPU share, context length.

    ``cpu_offload`` is True when part of the loaded model sits outside GPU memory
    (``size_vram < size``), False when all of it is on the GPU, None when it cannot be told.
    ``loaded`` is False when the server answers but the model is not in memory (a launch reading
    taken before the first call). Never raises.
    """
    out = {"loaded": None, "name": None, "size": None, "size_vram": None,
           "context_length": None, "cpu_offload": None, "error": None}
    try:
        half = min(timeout, 2.0) / 2
        response = requests.get(f"{base_url.rstrip('/')}/api/ps", timeout=(half, half))
        if not 200 <= response.status_code < 300:
            out["error"] = f"HTTP {response.status_code}"
            return out
        body = response.json()
        entries = body.get("models") if isinstance(body, dict) else None
        if not isinstance(entries, list):
            out["error"] = "response had no models list"
            return out
        wanted = {model, model if ":" in str(model) else f"{model}:latest"}
        match = next((e for e in entries if isinstance(e, dict)
                      and (e.get("name") in wanted or e.get("model") in wanted)), None)
        if match is None:
            out["loaded"] = False
            return out
        out["loaded"] = True
        out["name"] = match.get("name") or match.get("model")
        for key in ("size", "size_vram", "context_length"):
            value = match.get(key)
            out[key] = value if isinstance(value, int) and not isinstance(value, bool) else None
        if out["size"] and out["size_vram"] is not None:
            out["cpu_offload"] = out["size_vram"] < out["size"]
        return out
    except Exception as exc:  # noqa: BLE001
        out["error"] = type(exc).__name__
        return out


def endpoint_for_model(model: Any) -> str:
    """Where a model's calls go: ``mock``, a cloud provider's name, or the Ollama ``host:port``.

    Never a key and never a URL with credentials.
    """
    if not isinstance(model, str) or is_mock_model(model):
        return "mock"
    if is_cloud_provider_model(model):
        return model.split(":", 1)[0].lower()
    try:
        from urllib.parse import urlparse
        parsed = urlparse(get_ollama_base_url())
        host = parsed.hostname or "unknown"
        return f"ollama@{host}:{parsed.port}" if parsed.port else f"ollama@{host}"
    except Exception:  # noqa: BLE001
        return "ollama"


def model_identity(model: Any, refresh: bool = False) -> dict:
    """Digest, quantization, family and parameter size of an Ollama model; None for mock/cloud.

    Never raises.
    """
    out = {"digest": None, "quantization": None, "family": None, "parameter_size": None,
           "error": None}
    try:
        if not isinstance(model, str) or is_mock_model(model) or is_cloud_provider_model(model):
            return out
        from broker.utils.llm_utils import get_ollama_show_metadata
        endpoint = get_ollama_base_url().rstrip("/")
        info = get_ollama_show_metadata(model, base_url=endpoint, refresh=refresh)
        info = info if isinstance(info, dict) else {}
        details = info.get("details") if isinstance(info.get("details"), dict) else {}
        digest = info.get("digest")
        if not isinstance(digest, str) or not digest.strip():
            # Ollama versions whose show response has no digest: take it from /api/tags.
            tags = requests.get(f"{endpoint}/api/tags", timeout=5).json()
            names = (model, model if ":" in model else f"{model}:latest")
            entry = next((m for m in (tags.get("models") or []) if isinstance(m, dict)
                          and m.get("name", m.get("model")) in names), None)
            digest = entry.get("digest") if entry else None
        out["digest"] = digest.strip() if isinstance(digest, str) and digest.strip() else None
        out["quantization"] = details.get("quantization_level")
        out["family"] = details.get("family")
        out["parameter_size"] = details.get("parameter_size")
    except Exception as exc:  # noqa: BLE001
        out["error"] = type(exc).__name__
    return out


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


_GPU_QUERY = ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]


def gpu_info(timeout: float = 5.0) -> "list | None":
    """One ``{name, driver_version, memory_total}`` per NVIDIA GPU; None when there is none.

    Never raises: no ``nvidia-smi``, a failing ``nvidia-smi`` or output that does not parse
    all answer None.
    """
    try:
        proc = subprocess.run(_GPU_QUERY, capture_output=True, text=True, timeout=timeout, check=False)
        if proc.returncode != 0:
            return None
        gpus = []
        for line in proc.stdout.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[0]:
                gpus.append({"name": parts[0], "driver_version": parts[1],
                             "memory_total": ",".join(parts[2:])})
        return gpus or None
    except Exception:
        return None


def home_collapsed(path: Any) -> "str | None":
    """``path`` with the user's home folder written as ``~``, so a published manifest carries
    no user name. Other paths are returned as given. Never raises."""
    try:
        if not path:
            return None
        text = str(path)
        home = str(Path.home())
        norm_text, norm_home = os.path.normcase(text), os.path.normcase(home)
        if home and (norm_text == norm_home or norm_text.startswith(norm_home + os.sep)):
            return "~" + text[len(home):]
        return text
    except Exception:
        return None


def collapse_home_in_text(text: str) -> str:
    """Replace the user's home folder anywhere in ``text`` with ``~`` (either slash style;
    any case on Windows only). A match must not run on into a longer name (``home + "X"``
    stays as it is). Never raises; returns ``text`` unchanged on failure."""
    try:
        home = str(Path.home())
        if not home or not isinstance(text, str):
            return text
        variants = {home, home.replace("\\", "/"), home.replace("/", "\\")}
        flags = re.IGNORECASE if sys.platform == "win32" else 0
        for v in sorted(variants, key=len, reverse=True):
            text = re.sub(re.escape(v) + r"(?![A-Za-z0-9_-])", "~", text, flags=flags)
        return text
    except Exception:
        return text


def scrub_home_paths(obj: Any) -> Any:
    """Copy of a JSON-like structure with the home folder written as ``~`` in every string.

    Keys are left alone. Never raises (the input is returned on failure)."""
    try:
        if isinstance(obj, str):
            return collapse_home_in_text(obj)
        if isinstance(obj, dict):
            return {k: scrub_home_paths(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [scrub_home_paths(v) for v in obj]
        if isinstance(obj, tuple):
            return [scrub_home_paths(v) for v in obj]
        return obj
    except Exception:
        return obj


def ram_total_bytes() -> "int | None":
    """Total physical memory in bytes; None when it cannot be read. Never raises."""
    try:
        try:
            import psutil  # type: ignore
            return int(psutil.virtual_memory().total)
        except ImportError:
            pass
        if sys.platform == "win32":
            import ctypes

            class _MemStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = _MemStatus()
            status.dwLength = ctypes.sizeof(_MemStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
            return None
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except Exception:
        return None


def cuda_version(timeout: float = 5.0) -> dict:
    """``{"version": "12.x" | None, "error": None | reason}`` from the ``nvidia-smi`` header.

    No GPU, no ``nvidia-smi`` or an unparsable header give ``version`` None with the reason.
    Never raises.
    """
    try:
        proc = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=timeout,
                              check=False)
        if proc.returncode != 0:
            return {"version": None, "error": f"nvidia-smi exit {proc.returncode}"}
        match = re.search(r"CUDA (?:UMD )?Version:\s*([0-9.]+)", proc.stdout)
        if not match:
            return {"version": None, "error": "no CUDA version in nvidia-smi output"}
        return {"version": match.group(1), "error": None}
    except Exception as exc:
        return {"version": None, "error": type(exc).__name__}


def installed_packages() -> "list":
    """Every installed distribution as sorted ``name==version`` lines (raises on failure)."""
    seen = {}
    for dist in importlib_metadata.distributions():
        name = dist.metadata["Name"] if dist.metadata else None
        if name:
            seen.setdefault(name.lower(), (name, dist.version))
    return [f"{n}=={v}" for _, (n, v) in sorted(seen.items())]


def write_installed_packages(output_dir: Any, filename: str = "python_packages.txt") -> dict:
    """Write the full ``name==version`` list to ``output_dir/filename`` and describe it.

    ``{"file", "count", "sha256", "error"}``; on failure ``error`` carries the exception type
    and the other fields are None. Never raises.
    """
    out = {"file": None, "count": None, "sha256": None, "error": None}
    try:
        import hashlib
        lines = installed_packages()
        data = ("\n".join(lines) + "\n").encode("utf-8")
        target = Path(output_dir) / filename
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        out.update(file=filename, count=len(lines), sha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {home_collapsed(str(exc))}"
    return out


def cpu_info() -> "str | None":
    try:
        return platform.processor() or None
    except Exception:
        return None


def wagf_repo_root() -> "Path | None":
    try:
        import broker
        return Path(broker.__file__).resolve().parents[1]
    except Exception:
        return None


def repo_relative(path: Any) -> "str | None":
    """``path`` relative to the WAGF repo root (forward slashes); None when it lies outside.

    A relative path is taken against the current directory first. Never raises.
    """
    try:
        root = wagf_repo_root()
        if root is None or path is None:
            return None
        resolved = Path(str(path)).resolve()
        return resolved.relative_to(root).as_posix()
    except Exception:
        return None


def launch_command_repo_relative(argv: "list | None" = None) -> "dict | None":
    """The launch command with every path inside the WAGF repo made repo-relative.

    ``{"script": ..., "command": ...}``; ``script`` is None when argv[0] is outside the
    repo. Arguments outside the repo (an output folder, say) keep their path with the home
    folder written as ``~``.
    """
    try:
        argv = list(sys.argv if argv is None else argv)
        if not argv:
            return None
        rel_script = repo_relative(argv[0])
        parts = ["python", rel_script or home_collapsed(argv[0]) or argv[0]]
        for arg in argv[1:]:
            rel = repo_relative(arg) if (isinstance(arg, str) and (":" in arg or "/" in arg or "\\" in arg)
                                         and Path(arg).is_absolute()) else None
            # A path outside the repo (an output folder, say) keeps no user name either.
            parts.append(rel or (home_collapsed(arg) if isinstance(arg, str) else arg) or arg)
        return {"script": rel_script, "command": " ".join(parts)}
    except Exception:
        return None


def file_input_record(path: Any) -> dict:
    """``{file, path_repo_relative, present, bytes, sha256}`` for one input file; never raises.

    The absolute path is not recorded: ``path_repo_relative`` is None for a file outside the
    WAGF repo, and ``file`` is then the only name kept. A missing or unreadable file has
    ``sha256`` None, so the gap shows in the manifest instead of vanishing.
    """
    record: dict = {"file": None, "path_repo_relative": None, "present": False,
                    "bytes": None, "sha256": None}
    try:
        p = Path(str(path))
        record["file"] = p.name
        record["path_repo_relative"] = repo_relative(p)
        if p.is_file():
            import hashlib
            digest = hashlib.sha256()
            size = 0
            with p.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(chunk)
                    size += len(chunk)
            record.update(present=True, bytes=size, sha256=digest.hexdigest())
    except Exception as exc:
        record["error"] = type(exc).__name__
    return record


def require_clean_wagf_tree(model: Any, allow_dirty_tree: bool = False) -> dict:
    """Refuse a non-mock run whose WAGF source tree has uncommitted changes.

    Returns the record the manifest keeps: ``{"checked", "dirty", "dirty_count",
    "allow_dirty_tree", "overridden"}``. Raises ``SystemExit`` with the reason when the tree
    is dirty, the model is not a mock and ``allow_dirty_tree`` is False. Mock runs are not
    checked. A tree whose state cannot be read is reported, not refused.
    """
    record = {"checked": False, "dirty": None, "dirty_count": None,
              "allow_dirty_tree": bool(allow_dirty_tree), "overridden": False}
    if isinstance(model, str) and is_mock_model(model):
        return record
    state = wagf_source_git()
    if state is None or state.get("error"):
        record["checked"] = False
        return record
    record["checked"] = True
    record["dirty"] = state.get("dirty")
    record["dirty_count"] = state.get("dirty_count")
    if state.get("dirty"):
        if allow_dirty_tree:
            record["overridden"] = True
            return record
        raise SystemExit(
            f"Refusing to start: the WAGF source tree has {state.get('dirty_count')} uncommitted "
            "change(s) (git status --porcelain), so the manifest could not name the code that "
            "ran. Commit or stash them, or pass --allow-dirty-tree to run anyway; the manifest "
            "then records allow_dirty_tree=true.")
    return record


def _flatten(prefix: str, value: Any, out: dict) -> None:
    if isinstance(value, dict):
        for key in value:
            _flatten(f"{prefix}.{key}" if prefix else str(key), value[key], out)
    else:
        out[prefix] = value


def environment_changed(launch: Any, finalize: Any) -> list:
    """Sorted dotted keys whose value differs between two ``collect_run_environment`` dicts.

    ``captured_at`` and ``errors`` are not compared. Never raises.
    """
    try:
        a: dict = {}
        b: dict = {}
        _flatten("", {k: v for k, v in (launch or {}).items() if k not in ("captured_at", "errors")}, a)
        _flatten("", {k: v for k, v in (finalize or {}).items() if k not in ("captured_at", "errors")}, b)
        return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    except Exception:
        return ["_comparison_failed"]


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
    loaded: dict = {"loaded": None, "error": NOT_OLLAMA}
    try:
        if isinstance(model, str) and not is_mock_model(model) and not is_cloud_provider_model(model):
            loaded = ollama_loaded_model(model, get_ollama_base_url())
            if loaded.get("error"):
                errors["ollama_loaded_model"] = loaded["error"]
    except Exception as exc:  # noqa: BLE001
        loaded = {"loaded": None, "error": type(exc).__name__}
        errors["ollama_loaded_model"] = loaded["error"]
    source_git = None
    try:
        source_git = wagf_source_git()
        if source_git and source_git.get("error"):
            errors["wagf_source_git"] = source_git["error"]
    except Exception as exc:
        source_git = {"commit": None, "dirty": None, "dirty_count": None, "error": type(exc).__name__}
        errors["wagf_source_git"] = source_git["error"]
    gpu = None
    try:
        gpu = gpu_info()
    except Exception:
        gpu = None
    ram = None
    try:
        ram = ram_total_bytes()
        if ram is None:
            errors["ram_total_bytes"] = "unavailable"
    except Exception as exc:
        errors["ram_total_bytes"] = type(exc).__name__
    cuda: dict = {"version": None, "error": "unavailable"}
    try:
        cuda = cuda_version()
    except Exception as exc:
        cuda = {"version": None, "error": type(exc).__name__}
    return {
        "captured_at": captured_at,
        "wagf_version": packages.get("wagf_version"),
        "wagf_version_source": packages.get("wagf_version_source"),
        "packages": packages.get("packages", {}),
        "os": os_part,
        "cpu": cpu_info(),
        "gpu": gpu,
        "ram_total_bytes": ram,
        "cuda_version": cuda.get("version"),
        "cuda_version_error": cuda.get("error"),
        "python_version": platform.python_version(),
        "python_executable": home_collapsed(sys.executable),
        "ollama_server_version": ollama,
        "ollama_loaded_model": loaded,
        "wagf_source_git": source_git,
        "errors": errors,
    }
