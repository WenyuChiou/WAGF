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
from typing import Any, Dict, Optional, Tuple

from broker.utils.logging import logger

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


def configured_grid_expectation(agents, iterations) -> Dict[str, Any]:
    """What a run was CONFIGURED to write: agents per type x iterations.

    Returns ``{"expected_agents": {agent_type: n}, "expected_rows":
    {agent_type: n * iterations}, "expected_years": iterations}``, or an empty
    dict when the agent set or the iteration count cannot be read.

    ``agents`` is a mapping of agent objects (``ExperimentRunner.agents``,
    ``run_flood``'s ``agents``) or any iterable of them; each object's
    ``agent_type`` attribute keys the counts, defaulting to ``"default"``.

    Per agent TYPE, because each type gets its own audit CSV and pooling them
    multiplies one type's agents by another type's years — an expectation no
    run could meet.

    S2: this lives here, not on ``ExperimentRunner``, so the single-agent
    ``run_flood`` path computes the same number the same way instead of
    carrying a second inline copy that could drift. It NEVER raises: both
    callers run it after the experiment is finished, and a helper that computed
    a side-artifact number must not be able to abort a completed run.

    A shortfall against this number is a NUMBER TO EXPLAIN, not a verdict — a
    flood household that relocates legitimately stops producing rows. Nothing
    here subtracts exits on the domain's behalf; doing so would hide the
    truncation case this exists to catch.
    """
    try:
        values = agents.values() if hasattr(agents, "values") else (agents or [])
        per_type: Dict[str, int] = {}
        for agent in values:
            atype = str(getattr(agent, "agent_type", None) or "default")
            per_type[atype] = per_type.get(atype, 0) + 1
        if not per_type or not isinstance(iterations, int) or iterations <= 0:
            return {}
        return {
            "expected_agents": per_type,
            "expected_rows": {k: v * iterations for k, v in per_type.items()},
            "expected_years": iterations,
        }
    except Exception as exc:
        logger.debug(f"[Integrity] configured expectation unavailable: {exc}")
        return {}


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
    expected_rows=None,
    expected_agents=None,
    expected_years: Optional[int] = None,
    corrected_status_columns: Optional[bool] = None,
    sentinel_write_failures: Optional[int] = None,
    extra: Optional[dict] = None,
    verbose: bool = True,
) -> dict:
    """Write ``run_integrity.json`` recording runtime instantiation; never raises.

    ``expected_rows`` / ``expected_agents`` are what the RUNNER was configured
    to produce — an ``int`` total, or a mapping keyed by agent type — and
    ``expected_years`` the configured iteration count. They are the only way
    the coverage block can see a run that stopped early: everything else it
    knows comes from the rows that exist. Omit them and the configured-grid
    keys stay ``None`` rather than being guessed from the output.

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

    # PR-3: framework + audit-schema provenance, and audit-CSV coverage.
    # ADDITIVE ONLY, and only into run_integrity.json (a side artifact) —
    # no CSV byte is touched, so this needs no flag. It answers, from the
    # artifact alone, "which framework wrote this, under which audit schema,
    # and did every agent-year reach the CSV" — questions that previously
    # needed the source tree plus a hand count.
    # (``governance_mode`` above IS the governance-profile provenance — the
    # profile name the run resolved, not the YAML's requested one.)
    coverage: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}
    corrected_schema_version: Optional[str] = None
    try:
        from broker.components.analytics.audit import (
            AUDIT_SCHEMA_VERSION_CORRECTED, audit_coverage, audit_run_metadata,
        )

        corrected_schema_version = AUDIT_SCHEMA_VERSION_CORRECTED
        provenance = audit_run_metadata()
        coverage = audit_coverage(
            output_dir,
            expected_rows=expected_rows,
            expected_agents=expected_agents,
            expected_years=expected_years,
        )
    except Exception as exc:
        # W3: previously `except Exception: coverage = {}` — an import error, a
        # bug in audit_coverage and a run with genuinely nothing to count all
        # produced the same empty block. Record WHICH, so a plausible zero is
        # never mistaken for a measurement.
        logger.warning(
            "[Integrity] audit coverage unavailable (%s: %s) — run_integrity.json "
            "records the failure rather than an empty coverage block.",
            type(exc).__name__, exc,
        )
        audit["audit_coverage_error"] = f"{type(exc).__name__}: {exc}"
    if provenance:
        audit["framework_provenance"] = provenance
    if coverage:
        audit.update(coverage)

    # P1d: which audit-schema contract the CSVs in this directory follow. The
    # corrected column set is schema "3" — same fieldname detection the sidecar
    # uses, so provenance and sidecar cannot disagree.
    if (
        provenance
        and corrected_schema_version
        and coverage.get("audit_corrected_status_columns")
    ):
        audit["framework_provenance"]["audit_schema_version"] = corrected_schema_version

    # P1d: the RESOLVED flag, recorded unconditionally. `audit_coverage` can
    # only detect it from a CSV that exists; the engine knows it even when the
    # run wrote nothing, and the two disagreeing is itself worth seeing.
    audit["audit_corrected_status_columns_resolved"] = (
        corrected_status_columns if isinstance(corrected_status_columns, bool)
        else None
    )

    # P2d: sentinel rows the writer failed to write. Each one is a row that
    # should exist and does not — the exact denominator hole the sentinel was
    # added to close, previously visible only in the console log.
    if isinstance(sentinel_write_failures, int):
        audit["audit_sentinel_write_failures"] = sentinel_write_failures

    # P1c: rules that fired but reached no breakdown bucket. Reported here and
    # logged once per run rather than per row. A zero in every `rules_*_hit`
    # column alongside a non-zero total here means the rules fired and their
    # category could not be named — NOT that governance was quiet.
    #
    # C1: the tally is kept only on the INFERENCE path, so with the flag OFF it
    # is 0 and this warning does not fire at all. That is deliberate: with no
    # inference running, every AgentValidator result is uncategorised, and
    # saying so once per run would be re-announcing a documented structural
    # property of the flag-OFF column set rather than reporting a finding.
    try:
        from broker.validators.governance import get_uncategorised_rules

        uncat = get_uncategorised_rules()
        audit.update(uncat)
        if uncat.get("rules_uncategorised_total"):
            if audit.get("audit_corrected_status_columns_resolved") is False:
                # Not reachable through the normal path (the flag was OFF, so
                # nothing should have been tallied). If it happens, the INFERRED
                # explanation below would be a lie about this run, so say only
                # what is true: something recorded into the tally outside the
                # inference path.
                logger.warning(
                    "[Integrity] %d validator result(s) are recorded as "
                    "uncategorised on a run with audit.corrected_status_columns "
                    "OFF, where the tally is not kept. Rule ids: %s. Treat the "
                    "count as untrusted and check for a second engine in this "
                    "process.",
                    uncat["rules_uncategorised_total"],
                    uncat["rules_uncategorised_ids"],
                )
            else:
                logger.warning(
                    "[Integrity] %d validator result(s) reached no rules_*_hit "
                    "bucket; their rule ids: %s. Under "
                    "audit.corrected_status_columns the buckets are INFERRED "
                    "from tier / validator name / rule id, so only categories "
                    "the producer's tiers can express are populated — identity "
                    "and other precondition rules are reported here instead of "
                    "being filed under a plausible bucket.",
                    uncat["rules_uncategorised_total"],
                    uncat["rules_uncategorised_ids"],
                )
    except Exception as exc:
        logger.debug(f"[Integrity] uncategorised-rule tally skipped: {exc}")

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
