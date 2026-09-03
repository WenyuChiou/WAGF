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
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from broker.utils.logging import logger

# ──────────────────────────────────────────────────────────────────────
# PR-6 P1-a: world-rule EVALUABILITY tally
# ──────────────────────────────────────────────────────────────────────
# A world-grounded rule whose variable the environment never published does not
# fire — the safe direction, and the documented one. But a run where that is
# true of EVERY grounded rule on EVERY row is not a run in which the world
# agreed with the model; it is a run in which the grounded profile was
# decorative, and the audit CSV of that run is identical to a clean one.
#
# Counted per audit ROW (not per validation pass, which would over-count
# retries), incremented from the same place the grounding columns are computed,
# and reported in run_integrity.json. Process-global with a lock for the same
# reason as the uncategorised-rule tally: audit rows are built concurrently when
# a run sets workers > 1, and a bare += loses updates in the one number that
# exists to say "this evidence is not there".
_WORLD_EVALUABILITY_LOCK = threading.Lock()
_WORLD_GROUNDED_ROWS = 0
_WORLD_UNEVALUABLE_ROWS = 0


def note_world_grounded_row(unevaluable: bool) -> None:
    """Record one audit row written under a world-grounded profile. Never raises."""
    global _WORLD_GROUNDED_ROWS, _WORLD_UNEVALUABLE_ROWS
    with _WORLD_EVALUABILITY_LOCK:
        _WORLD_GROUNDED_ROWS += 1
        if unevaluable:
            _WORLD_UNEVALUABLE_ROWS += 1


def get_world_rule_evaluability() -> Dict[str, int]:
    """The tally, for ``run_integrity.json``."""
    with _WORLD_EVALUABILITY_LOCK:
        return {
            "world_grounded_rows": _WORLD_GROUNDED_ROWS,
            "world_rules_unevaluable_rows": _WORLD_UNEVALUABLE_ROWS,
        }


def reset_world_rule_evaluability() -> None:
    """Clear the tally. Called from ``SkillBrokerEngine.__init__`` and by tests."""
    global _WORLD_GROUNDED_ROWS, _WORLD_UNEVALUABLE_ROWS
    with _WORLD_EVALUABILITY_LOCK:
        _WORLD_GROUNDED_ROWS = 0
        _WORLD_UNEVALUABLE_ROWS = 0


# ──────────────────────────────────────────────────────────────────────
# PR-8: rows per decider
# ──────────────────────────────────────────────────────────────────────
# A mixed-population run is a claim about composition: so many agents
# decided by rule, so many by a model. The claim is checkable only if the
# run says how many rows each actually produced — a config can declare a
# rule-based arm that, because of an agent-type name that never matched,
# contributed zero rows, and the CSV of that run looks exactly like a
# correctly-composed one until someone groups by `decider` and finds a
# category missing.
#
# Counted per audit ROW from the same place the decider columns are
# computed, so the census and the columns can never disagree. Same lock
# rationale as the tally above: rows are built concurrently at workers > 1.
_DECIDER_ROWS_LOCK = threading.Lock()
_DECIDER_ROWS: Dict[str, int] = {}
# Rows whose decider fell back to its declared `default_action` because no
# rule matched, and rows written by an aborted-step sentinel. Both are
# subsets of _DECIDER_ROWS, kept apart because both are ways for an arm to
# produce a full row count while producing no rule-driven decision at all.
_RULE_DEFAULT_ROWS: Dict[str, int] = {}
_DECIDER_ABORTED_ROWS: Dict[str, int] = {}
# Rule ids that fired, per agent type. A firing is a DECISION, not a row:
# a governance retry re-walks the table and counts again. Reported so a
# table's shape is checkable against the artifact rather than against the
# config that was supposed to produce it.
_RULE_FIRINGS: Dict[str, Dict[str, int]] = {}
# Rule fields nothing in scope carried, per agent type. Each one is a
# condition that can never hold, so the rule can never fire.
_RULE_FIELD_UNRESOLVED: Dict[str, Dict[str, int]] = {}
# Decider names the CONFIG declared, recorded at engine construction. The
# census can only see arms that produced a row; this is how it knows about
# the arm that produced none.
_DECLARED_DECIDERS: List[str] = []


def note_decider_row(decider: str, path: Optional[str] = None) -> None:
    """Record one audit row produced by ``decider``. Never raises.

    ``path`` is the row's ``decider_path``, so the sub-censuses below are
    incremented from the SAME call that increments the main one and the
    three cannot drift apart.
    """
    name = str(decider or "llm")
    key = str(path or "")
    with _DECIDER_ROWS_LOCK:
        _DECIDER_ROWS[name] = _DECIDER_ROWS.get(name, 0) + 1
        if key == "rule_default":
            _RULE_DEFAULT_ROWS[name] = _RULE_DEFAULT_ROWS.get(name, 0) + 1
        elif key == "aborted":
            _DECIDER_ABORTED_ROWS[name] = _DECIDER_ABORTED_ROWS.get(name, 0) + 1


def note_rule_firing(agent_type: str, rule_id: str) -> None:
    """Record one firing of one rule id, for the rule-level census."""
    atype, rid = str(agent_type or "?"), str(rule_id or "?")
    with _DECIDER_ROWS_LOCK:
        per_type = _RULE_FIRINGS.setdefault(atype, {})
        per_type[rid] = per_type.get(rid, 0) + 1


def note_rule_field_unresolved(agent_type: str, field_name: str) -> None:
    """Record one evaluation of a rule field nothing in scope carried."""
    atype, fname = str(agent_type or "?"), str(field_name)
    with _DECIDER_ROWS_LOCK:
        per_type = _RULE_FIELD_UNRESOLVED.setdefault(atype, {})
        per_type[fname] = per_type.get(fname, 0) + 1


def set_declared_deciders(names) -> None:
    """Record the decider names the active config declares."""
    with _DECIDER_ROWS_LOCK:
        _DECLARED_DECIDERS[:] = sorted({str(n) for n in (names or [])})


def get_declared_deciders() -> List[str]:
    with _DECIDER_ROWS_LOCK:
        return list(_DECLARED_DECIDERS)


def get_decider_row_counts() -> Dict[str, int]:
    """The per-decider census, for ``run_integrity.json``."""
    with _DECIDER_ROWS_LOCK:
        return dict(sorted(_DECIDER_ROWS.items()))


def get_rule_default_row_counts() -> Dict[str, int]:
    with _DECIDER_ROWS_LOCK:
        return dict(sorted(_RULE_DEFAULT_ROWS.items()))


def get_decider_aborted_row_counts() -> Dict[str, int]:
    with _DECIDER_ROWS_LOCK:
        return dict(sorted(_DECIDER_ABORTED_ROWS.items()))


def get_rule_firings() -> Dict[str, Dict[str, int]]:
    with _DECIDER_ROWS_LOCK:
        return {k: dict(sorted(v.items())) for k, v in sorted(_RULE_FIRINGS.items())}


def get_rule_field_unresolved() -> Dict[str, Dict[str, int]]:
    with _DECIDER_ROWS_LOCK:
        return {k: dict(sorted(v.items()))
                for k, v in sorted(_RULE_FIELD_UNRESOLVED.items())}


def reset_decider_row_counts() -> None:
    """Clear every decider census. From ``SkillBrokerEngine.__init__`` and tests."""
    with _DECIDER_ROWS_LOCK:
        _DECIDER_ROWS.clear()
        _RULE_DEFAULT_ROWS.clear()
        _DECIDER_ABORTED_ROWS.clear()
        _RULE_FIRINGS.clear()
        _RULE_FIELD_UNRESOLVED.clear()
        _DECLARED_DECIDERS.clear()
    try:
        from broker.agents.deciders import reset_unresolved_field_warnings

        reset_unresolved_field_warnings()
    except Exception as exc:  # noqa: BLE001 — a log memo, never fatal
        logger.debug(f"[Integrity] unresolved-field memo reset skipped: {exc}")

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

    # PR-6 P1-a: how many rows ran under a world-grounded profile, and on how
    # many of them EVERY grounded rule was unevaluable because the environment
    # did not publish its variable.
    world_eval = get_world_rule_evaluability()
    audit.update(world_eval)
    _wg_rows = world_eval["world_grounded_rows"]
    _wu_rows = world_eval["world_rules_unevaluable_rows"]
    # The denominator is the tally itself, `_wg_rows` — NOT `audit_rows` from
    # the CSV. `note_world_grounded_row()` is only called from
    # `AuditMixin._write_audit_trace`; an aborted sentinel row (status
    # ABORTED / ABORTED_EXCEPTION, written by `_write_aborted_trace` when a
    # step raises) bypasses that call site entirely and never reaches the
    # tally. `audit_rows` counts the sentinel row anyway, so using it as the
    # denominator inflates the count past what the tally actually saw — one
    # aborted agent-year was enough to make `_wu_rows == _denominator` false
    # even when EVERY row the tally did see was unevaluable, silently
    # disabling the flag. The tally's own row count is the only denominator
    # that answers "was the grounded rule ever in a position to say
    # anything, among the rows this tally actually counted?".
    _denominator = _wg_rows
    world_rules_never_evaluable = bool(_wu_rows) and _wu_rows == _denominator

    # Separately: rows that finished normally (not aborted) but still never
    # reached the tally are a coverage hole worth naming on their own — some
    # code path wrote a completed row without calling
    # `note_world_grounded_row()`. Null when the CSV-side counts are not
    # available (coverage unmeasured / no CSV yet), OR when `_wg_rows == 0` —
    # verified empirically (2026-09, a plain default-profile flood run):
    # `note_world_grounded_row()` is called only from the ONE call site gated
    # by `AgentTypeConfig.get_audit_grounding_columns()`
    # (`broker/core/_audit_helpers.py`), which is OFF for every non-grounded
    # profile. On such a run `_wg_rows` is 0 for its entire duration BY
    # DESIGN, not because of a coverage hole, so comparing it against
    # `audit_rows` would report every ordinary row as "missing" and warn on
    # every default-profile run in the fleet — the same false-alarm shape the
    # uncategorised-rule tally's C1 fix (this module's sibling in
    # `broker/validators/governance/__init__.py`) already exists to avoid.
    # `_wg_rows > 0` is the cheapest available signal that the tally was
    # actually live for this run, so the gap is only measured then.
    _audit_rows = audit.get("audit_rows")
    _audit_aborted_rows = audit.get("audit_aborted_rows")
    if _wg_rows > 0 and isinstance(_audit_rows, int) and isinstance(_audit_aborted_rows, int):
        world_grounded_coverage_gap = (_audit_rows - _audit_aborted_rows) - _wg_rows
    else:
        world_grounded_coverage_gap = None
    audit["world_grounded_coverage_gap"] = world_grounded_coverage_gap
    if world_grounded_coverage_gap:
        logger.warning(
            "[Integrity] %d completed (non-aborted) row(s) ran without "
            "reaching the world-grounded-evaluability tally — a coverage "
            "hole: some path wrote a finished audit row without calling "
            "note_world_grounded_row(). audit_rows=%s audit_aborted_rows=%s "
            "world_grounded_rows=%s.",
            world_grounded_coverage_gap, _audit_rows, _audit_aborted_rows, _wg_rows,
        )

    # PR-8: how many audit rows each decider produced. Recorded only when
    # the decider columns are on, so a plain all-LLM run leaves the key
    # absent rather than asserting a one-entry census that says nothing.
    decider_rows = get_decider_row_counts()
    declared_deciders = get_declared_deciders()
    if decider_rows or declared_deciders:
        audit["decider_rows"] = decider_rows
        audit["decider_rows_total"] = sum(decider_rows.values())
        audit["decider_declared"] = declared_deciders
        _seen = sorted(decider_rows)
        if len(_seen) == 1 and _seen[0] != "llm":
            logger.warning(
                "[Integrity] every audit row was produced by '%s' — this run "
                "declared a non-default decider but holds no mixed population, "
                "so nothing in it can be compared against a model-driven "
                "agent. Check that the agent types you meant to leave on 'llm' "
                "are named as they are in the config.",
                _seen[0],
            )

        # P1-b: an arm that produced NO rows. The warning above only fires
        # when exactly one arm produced rows, so a config with three
        # declared arms and one silently empty passed it — and a CSV
        # missing one `decider` category looks exactly like a correct one
        # until somebody groups by it. A domain that REPLACED a built-in
        # writes `<name>@<domain>` in the column, so compare on the bare
        # name (see DeciderRegistry.audit_label).
        _seen_bare = {k.split("@", 1)[0] for k in decider_rows}
        zero_row_arms = sorted(set(declared_deciders) - _seen_bare)
        audit["decider_arms_with_zero_rows"] = zero_row_arms
        if zero_row_arms:
            logger.warning(
                "[Integrity] the config declared decider(s) %s and NOT ONE "
                "audit row came from them. The arm is missing from this run, "
                "not merely small: check that the agent types naming those "
                "deciders exist, are populated, and are spelled as the loader "
                "spells them. Rows seen: %s.",
                zero_row_arms, decider_rows,
            )

        # P1-b (code-reviewer focus 3): does the census account for every
        # row the CSV holds? Compared as TOTALS — decider_rows_total
        # against audit_rows — rather than each side's completed-row
        # remainder after subtracting its own aborted count.
        #
        # The subtraction used to false-positive with
        # audit.corrected_status_columns OFF: the F1 exception sentinel's
        # CSV `status` cell then reads UNKNOWN, not ABORTED_EXCEPTION
        # (docs/AUDIT_SCHEMA.md), because `approved_skill` — the column
        # `trace_to_csv_row` actually reads `status` off — is only
        # populated for that sentinel under the flag (see
        # `ExperimentRunner._write_aborted_trace`). So `audit_aborted_rows`
        # (read from that CSV column) MISSES the row, while
        # `decider_aborted_rows` (recorded at write time by
        # `_decider_audit_extra(..., path="aborted")`, gated on the
        # decider-columns flag only — never on corrected_status_columns)
        # still counts it. Subtracting each side's aborted count then
        # left the CSV side one row HIGHER than the census side for every
        # such run, and warned that some path skipped the decider column
        # builder — when the row HAD gone through it; only the CSV
        # status-column detector was blind to it.
        #
        # `decider_rows_total` and `audit_rows` are both un-subtracted
        # totals: every row this run wrote, both sentinel classes
        # included, land in each one the same way regardless of the
        # corrected_status_columns flag — so comparing them sidesteps
        # that flag-dependent blind spot entirely.
        aborted_by_decider = get_decider_aborted_row_counts()
        audit["decider_aborted_rows"] = aborted_by_decider
        if isinstance(_audit_rows, int):
            _decider_rows_total = audit["decider_rows_total"]
            if _decider_rows_total != _audit_rows:
                logger.warning(
                    "[Integrity] the per-decider census counted %d row(s) "
                    "total and the audit CSV holds %d — some path wrote a "
                    "row without going through the decider column builder, "
                    "so `decider_rows` under-reports whichever arm produced "
                    "them. audit_rows=%s decider_rows=%s.",
                    _decider_rows_total, _audit_rows, _audit_rows, decider_rows,
                )

        # P1-a: an arm whose every row was its `default_action` fall-through
        # is a CONSTANT, whatever its rule table says. Reported per decider
        # and warned about when it is the whole arm.
        rule_default_rows = get_rule_default_row_counts()
        if rule_default_rows:
            audit["rule_default_rows"] = rule_default_rows
            for _name, _count in sorted(rule_default_rows.items()):
                if _count and _count == decider_rows.get(_name):
                    logger.warning(
                        "[Integrity] every one of '%s''s %d row(s) fell "
                        "through to its declared default_action — no rule in "
                        "its table ever matched, so this arm is a constant "
                        "and not a rule-based model. Check "
                        "`rule_field_unresolved` below: the usual cause is a "
                        "field name the agents do not carry, which makes "
                        "every condition about it permanently false.",
                        _name, _count,
                    )

        # P1-a: the fields that made it so.
        unresolved = get_rule_field_unresolved()
        if unresolved:
            audit["rule_field_unresolved"] = unresolved
        firings = get_rule_firings()
        if firings:
            audit["rule_firings"] = firings

    if extra:
        audit.update(extra)

    # mismatch = a humancentric memory engine produced no reflection entries
    # (refl_count <= 0 also catches the -1 "exists but unreadable" sentinel — the
    # conservative direction: flag rather than silently pass).
    mismatch = reflection_expected and refl_count <= 0
    audit["integrity_ok"] = not (mismatch or world_rules_never_evaluable)

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
        if world_rules_never_evaluable:
            print("\n" + "!" * 72)
            print(" [INTEGRITY GUARDRAIL] a world-grounded governance profile was "
                  "active,")
            print(f" but on ALL {_wu_rows} of {_denominator} row(s) every grounded "
                  "rule was")
            print(" unevaluable — the environment never published the variable it "
                  "reads.")
            print(" The rules did not agree with the world; they never saw it. This "
                  "run's")
            print(" audit CSV is indistinguishable from a self-report-only run.")
            print(" Check the domain publishes the variable, and the rule's `scope:`.")
            print("!" * 72 + "\n")
        if mismatch:
            print("\n" + "!" * 72)
            print(" [INTEGRITY GUARDRAIL] humancentric memory engine but "
                  "reflection_log.jsonl")
            print(f" has {refl_count} entries at {output_dir}. Reflection did NOT run —")
            print(" this run is NOT comparable to reflection-on runs (the 2026-05-30")
            print(" data-defect failure mode).")
            print("!" * 72 + "\n")
        if not (mismatch or world_rules_never_evaluable):
            engine = effective_type or memory_engine_class or "unknown"
            print(f" [Integrity] reflection={refl_count} entries | engine={engine} | "
                  f"mode={governance_mode} | OK")
    return audit
