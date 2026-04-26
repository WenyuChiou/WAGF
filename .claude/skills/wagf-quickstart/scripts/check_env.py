#!/usr/bin/env python3
"""WAGF environment validator (Phase 1 of wagf-quickstart).

Validates that the user's machine can run any WAGF script. Emits a
GREEN / YELLOW / RED verdict plus a numbered remediation list.

Usage:
    python .claude/skills/wagf-quickstart/scripts/check_env.py
"""
from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Ensure UTF-8 stdout on Windows (cp950 / cp1252) so sigils render.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[4]
STATUS_FILE = REPO / ".wagf-quickstart-status.json"

REQUIRED_MODULES = ["numpy", "pandas", "scipy", "yaml", "ollama"]
RECOMMENDED_MODEL = "gemma3:4b"
SUPPORTED_MODELS = [
    "gemma3:4b", "gemma3:12b", "gemma3:27b",
    "gemma4:e2b", "gemma4:e4b", "gemma4:26b",
    "ministral-3:3b", "ministral-3:8b", "ministral-3:14b",
]


def check_python() -> Tuple[str, str]:
    v = sys.version_info
    if v.major == 3 and v.minor >= 10:
        return "GREEN", f"Python {v.major}.{v.minor}.{v.micro}"
    return "RED", (
        f"Python {v.major}.{v.minor}.{v.micro} is too old. "
        f"WAGF requires >= 3.10. Install via pyenv or conda."
    )


def check_imports() -> Tuple[str, str]:
    missing = []
    for mod in REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(mod)
    if not missing:
        return "GREEN", f"All required modules importable: {', '.join(REQUIRED_MODULES)}"
    return "YELLOW", (
        f"Missing modules: {', '.join(missing)}. "
        f"Run: pip install -r requirements.txt"
    )


def check_ollama_daemon() -> Tuple[str, str]:
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/version", timeout=3) as r:
            if r.status == 200:
                body = json.loads(r.read())
                return "GREEN", f"Ollama daemon reachable (version {body.get('version', '?')})"
    except Exception as e:
        pass
    return "RED", (
        "Ollama daemon not reachable at http://localhost:11434. "
        "Install: https://ollama.com/download. "
        "On macOS/Linux, run `ollama serve &`. "
        "On Windows, open the Ollama app."
    )


def check_model() -> Tuple[str, str]:
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            body = json.loads(r.read())
            tags = [m["name"] for m in body.get("models", [])]
        if RECOMMENDED_MODEL in tags:
            return "GREEN", f"Recommended model present: {RECOMMENDED_MODEL}"
        present_supported = [t for t in tags if t in SUPPORTED_MODELS]
        if present_supported:
            return "YELLOW", (
                f"Recommended {RECOMMENDED_MODEL} not pulled, but other supported "
                f"models present: {', '.join(present_supported)}. "
                f"For best onboarding: ollama pull {RECOMMENDED_MODEL}"
            )
        return "YELLOW", (
            f"No supported model pulled. "
            f"Run: ollama pull {RECOMMENDED_MODEL} (~2.4 GB download)"
        )
    except Exception:
        return "RED", "Cannot reach Ollama tags endpoint (daemon issue)."


def check_disk() -> Tuple[str, str]:
    free_gb = shutil.disk_usage(str(REPO)).free / 1024**3
    if free_gb >= 10:
        return "GREEN", f"Disk free: {free_gb:.1f} GB"
    return "YELLOW", (
        f"Only {free_gb:.1f} GB free under repo. "
        f"WAGF runs accumulate ~50 MB per long irrigation run. "
        f"Recommend >= 10 GB free."
    )


def check_gpu() -> Tuple[str, str]:
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=3,
            )
            if r.returncode == 0 and r.stdout.strip():
                return "INFO", f"GPU: {r.stdout.strip().splitlines()[0]}"
        except Exception:
            pass
    return "INFO", "No NVIDIA GPU detected (CPU-only inference will be slow)."


def overall(results: List[Tuple[str, str, str]]) -> str:
    if any(s == "RED" for _, s, _ in results):
        return "RED"
    if any(s == "YELLOW" for _, s, _ in results):
        return "YELLOW"
    return "GREEN"


def write_status(verdict: str) -> None:
    if STATUS_FILE.exists():
        try:
            data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    data["phase_1_env"] = {
        "completed": True,
        "verdict": verdict,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> int:
    print("=" * 60)
    print("WAGF environment check (Phase 1 of wagf-quickstart)")
    print("=" * 60)
    print()

    checks: List[Tuple[str, str, str]] = []
    for name, fn in [
        ("Python version", check_python),
        ("Required imports", check_imports),
        ("Ollama daemon", check_ollama_daemon),
        ("Recommended model", check_model),
        ("Disk space", check_disk),
        ("GPU (informational)", check_gpu),
    ]:
        sev, msg = fn()
        checks.append((name, sev, msg))
        sigil = {"GREEN": "✓", "YELLOW": "⚠", "RED": "✗", "INFO": "·"}.get(sev, "?")
        print(f"  {sigil} {name:25s}  {sev:6s}  {msg}")
    print()

    verdict = overall(checks)
    print("=" * 60)
    print(f"Overall verdict: {verdict}")
    print("=" * 60)

    if verdict != "GREEN":
        print("\nRemediation list:")
        n = 0
        for name, sev, msg in checks:
            if sev in ("RED", "YELLOW"):
                n += 1
                print(f"  {n}. {name}: {msg}")

    print(f"\nStatus written to {STATUS_FILE.relative_to(REPO)}")
    write_status(verdict)
    return 0 if verdict == "GREEN" else (1 if verdict == "YELLOW" else 2)


if __name__ == "__main__":
    sys.exit(main())
