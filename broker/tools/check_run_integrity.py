"""Generic run-integrity checker — Invariant 6 CLI.

Reads ``run_integrity.json`` in one or more run directories and reports whether the
runtime instantiation matched the config. Exits 1 if any run has
``integrity_ok=False`` (e.g. ``memory_engine_type='humancentric'`` but reflection
never ran). Domain-agnostic: the NW-paper-specific gov-vs-noval *pairwise* checker
lives at ``examples/single_agent/analysis/check_run_integrity.py``; this one judges a
single run dir against its own recorded contract and is reusable by any domain / CI.

Usage::

    python -m broker.tools.check_run_integrity <run_dir> [<run_dir> ...]
    python -m broker.tools.check_run_integrity --glob "examples/**/results/**/Run_*"
    python -m broker.tools.check_run_integrity --glob "results/*" --strict   # NO_MANIFEST fails too
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from broker.core.run_integrity import count_reflection_entries


def check_one(run_dir: Path):
    """Return ``(status, info)`` for a single run dir.

    status ∈ {OK, DEFECT, NO_MANIFEST}. ``NO_MANIFEST`` means the run predates the
    Invariant 6 contract (or used a runner that does not emit it); reflection state
    is recomputed directly from ``reflection_log.jsonl`` so the row is still useful.
    """
    integ = run_dir / "run_integrity.json"
    if integ.exists():
        try:
            d = json.loads(integ.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            d = None
        if isinstance(d, dict):
            return ("OK" if d.get("integrity_ok", True) else "DEFECT"), d
    exists, n = count_reflection_entries(run_dir)
    return "NO_MANIFEST", {"reflection_log_exists": exists, "reflection_log_entries": n}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Invariant 6 run-integrity checker")
    ap.add_argument("run_dirs", nargs="*", help="run output directories to check")
    ap.add_argument("--glob", help="glob pattern for run dirs (e.g. 'results/**/Run_*')")
    ap.add_argument("--strict", action="store_true",
                    help="also exit 1 when a run has no run_integrity.json (NO_MANIFEST)")
    args = ap.parse_args(argv)

    dirs = [Path(d) for d in args.run_dirs]
    if args.glob:
        dirs += sorted(p for p in Path().glob(args.glob) if p.is_dir())
    if not dirs:
        ap.error(f"provide at least one run_dir or --glob (cwd={Path().resolve()})")

    bad = 0
    print("=== Invariant 6 run-integrity check ===")
    for d in dirs:
        status, info = check_one(d)
        n = info.get("reflection_log_entries", "?")
        mem = info.get("memory_engine_type") or info.get("memory_engine_class") or "?"
        print(f"  {status:11} | reflection={str(n):>5} | mem={mem} | {d}")
        if status == "DEFECT" or (args.strict and status == "NO_MANIFEST"):
            bad += 1
    print(f"=== {bad} defect(s) over {len(dirs)} run dir(s) ===")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
