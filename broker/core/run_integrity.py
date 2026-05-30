"""Run-integrity provenance contract — Invariant 6.

Records the RUNTIME instantiation of a run (which memory engine was actually
wired, whether the reflection engine exists, how many reflection entries were
written) as a side artifact (``run_integrity.json``), and FLAGS — never aborts —
when the runtime contradicts the config (e.g. ``memory_engine_type='humancentric'``
but reflection never ran).

Why record-and-FLAG, never raise: this runs on the paper-3 / v21 byte-identity-
locked path. ``run_integrity.json`` is a *side* artifact; it never touches the
byte-locked simulation outputs (``simulation_log.csv`` / ``*_audit.csv``). A
guardrail that aborted a 24-hour real-LLM run because a *log file* looked short
would be worse than the defect it guards against.

Motivating defect (2026-05-30): ``config_snapshot.yaml`` records CONFIG, not
RUNTIME. A no-validator flood batch ran with ``memory_engine_type='humancentric'``
in its config but the reflection engine stayed ``None``, so reflection never ran.
The config looked correct; the runtime silently diverged; the gov-vs-noval
comparison gained a reflection confound that no artifact surfaced. This contract
makes the runtime instantiation a first-class, inspectable artifact.

See broker/INVARIANTS.md Invariant 6.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

# Sentinel for ``reflection_engine``: distinguishes "the caller did not pass a
# reflection engine object" (leave unset) from "reflection exists and is None".
# It controls only the informational ``reflection_engine_wired`` field — whether
# reflection is *expected* is driven by the memory engine being humancentric (below),
# so the ExperimentRunner path (which passes the engine object, not the type string,
# and holds no reflection engine) is still judged.
_UNSET = object()

# Memory engine classes that imply reflection should run. When a caller passes the
# instantiated ``memory_engine`` (ExperimentRunner) instead of the ``memory_engine_type``
# string (run_flood), the class name is mapped back to the type so the same
# config/runtime divergence is detectable on both paths. Only humancentric implies
# reflection; window / importance / hierarchical engines do not (kept out of the map
# so they never false-flag).
_MEM_CLASS_TO_TYPE = {
    "HumanCentricMemoryEngine": "humancentric",
}


def count_reflection_entries(output_dir) -> Tuple[bool, int]:
    """Return ``(exists, n_entries)`` for ``reflection_log.jsonl`` in ``output_dir``.

    ``n_entries`` is ``-1`` when the file exists but cannot be read. Callers treat
    ``-1`` the same as ``0`` for mismatch detection (``refl_count <= 0``) — the
    conservative direction: an unreadable reflection log is flagged, not trusted.
    """
    rl = Path(output_dir) / "reflection_log.jsonl"
    if not rl.exists():
        return False, 0
    try:
        with rl.open(encoding="utf-8") as fh:
            return True, sum(1 for _ in fh)
    except OSError:
        return True, -1


def record_run_integrity(
    output_dir,
    *,
    memory_engine_type: Optional[str] = None,
    memory_engine=None,
    reflection_engine=_UNSET,
    governance_mode: Optional[str] = None,
    seed=None,
    extra: Optional[dict] = None,
    verbose: bool = True,
) -> dict:
    """Write ``run_integrity.json`` recording runtime instantiation; never raises.

    Pass ``memory_engine_type`` (the requested type string) on paths that hold it
    explicitly (single-agent flood). Pass the instantiated ``memory_engine`` object
    on paths that construct it elsewhere (``ExperimentRunner``) so its class is
    recorded — this is the net for the silent ``WindowMemoryEngine`` fallback. Pass
    ``reflection_engine`` only on paths where reflection is a concept; leaving it
    unset means reflection parity is not asserted for this run (no false alarm).

    Returns the audit dict (also embedded in the reproducibility manifest by callers
    that have one).
    """
    output_dir = Path(output_dir)
    reflection_tracked = reflection_engine is not _UNSET
    refl_exists, refl_count = count_reflection_entries(output_dir)
    memory_engine_class = type(memory_engine).__name__ if memory_engine is not None else None

    # Resolve the effective memory engine type: the explicit string if the caller
    # passed it (run_flood), else inferred from the instantiated class (ExperimentRunner).
    # Reflection is expected whenever the memory engine is humancentric — independent of
    # whether a reflection_engine object was passed — so both run paths are judged.
    effective_type = memory_engine_type or _MEM_CLASS_TO_TYPE.get(memory_engine_class)
    reflection_expected = (effective_type == "humancentric")

    audit = {
        "memory_engine_type": memory_engine_type,
        "memory_engine_class": memory_engine_class,
        "effective_memory_engine_type": effective_type,
        "reflection_tracked": reflection_tracked,
        "reflection_expected": reflection_expected,
        "reflection_engine_wired": (reflection_engine is not None) if reflection_tracked else None,
        "reflection_log_exists": refl_exists,
        "reflection_log_entries": refl_count,
        "governance_mode": governance_mode,
        "seed": seed,
    }
    if extra:
        audit.update(extra)

    # mismatch = a humancentric memory engine produced no reflection entries
    # (refl_count <= 0 also catches the -1 "exists but unreadable" sentinel — the
    # conservative direction: flag rather than silently pass).
    mismatch = reflection_expected and refl_count <= 0
    audit["integrity_ok"] = not mismatch

    try:
        # default=str so a non-JSON-serializable value in ``extra`` (e.g. numpy int,
        # Path) degrades to its repr instead of raising — the never-raises contract is
        # unconditional. The except still widens to TypeError/ValueError as a backstop.
        (output_dir / "run_integrity.json").write_text(
            json.dumps(audit, indent=2, default=str), encoding="utf-8"
        )
    except (OSError, TypeError, ValueError) as exc:
        if verbose:
            print(f" [Integrity] WARNING: could not write run_integrity.json ({exc})")

    if verbose:
        if mismatch:
            print("\n" + "!" * 72)
            print(" [INTEGRITY GUARDRAIL] humancentric memory engine but "
                  "reflection_log.jsonl")
            print(f" has {refl_count} entries at {output_dir}. Reflection did NOT run —")
            print(" this run is NOT comparable to reflection-on runs (the 2026-05-30")
            print(" data-defect failure mode).")
            print("!" * 72 + "\n")
        else:
            engine = effective_type or memory_engine_class or "unknown"
            print(f" [Integrity] reflection={refl_count} entries | engine={engine} | "
                  f"mode={governance_mode} | OK")
    return audit
