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
import math
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from broker.utils.logging import logger

# ──────────────────────────────────────────────────────────────────────
# World-rule evaluability tally
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
# Per-decider census
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
# Rows where SkillBrokerEngine.process_step ran with render_check=False
# (broker/experiments/replay.py's documented opt-out from the
# options-text-parity POST-RENDER check). A replayed decision was previously
# distinguishable only by its `replay_` run_id prefix. Zero for live runs,
# so this stays absent from run_integrity.json outside replay runs.
_RENDER_CHECK_SKIPPED_ROWS = 0


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


def note_render_check_skipped() -> None:
    """Record one ``process_step`` call made with ``render_check=False``
    (round 6, 2026-09) — currently only ``broker/experiments/replay.py``.
    Never raises; reuses ``_DECIDER_ROWS_LOCK`` rather than a dedicated
    lock for one counter."""
    global _RENDER_CHECK_SKIPPED_ROWS
    with _DECIDER_ROWS_LOCK:
        _RENDER_CHECK_SKIPPED_ROWS += 1


def get_render_check_skipped_count() -> int:
    with _DECIDER_ROWS_LOCK:
        return _RENDER_CHECK_SKIPPED_ROWS


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
    global _RENDER_CHECK_SKIPPED_ROWS
    with _DECIDER_ROWS_LOCK:
        _DECIDER_ROWS.clear()
        _RULE_DEFAULT_ROWS.clear()
        _DECIDER_ABORTED_ROWS.clear()
        _RULE_FIRINGS.clear()
        _RULE_FIELD_UNRESOLVED.clear()
        _DECLARED_DECIDERS.clear()
        _RENDER_CHECK_SKIPPED_ROWS = 0
    try:
        from broker.agents.deciders import reset_unresolved_field_warnings

        reset_unresolved_field_warnings()
    except Exception as exc:  # noqa: BLE001 — a log memo, never fatal
        logger.debug(f"[Integrity] unresolved-field memo reset skipped: {exc}")

# Sentinel for ``reflection_engine``: distinguishes "the caller did not pass a
# reflection engine object" (leave unset) from "reflection exists and is None".
# It controls only the informational ``reflection_engine_wired`` field. Whether
# reflection is expected follows the resolved reflection_enabled flag when supplied,
# otherwise the humancentric memory default (below),
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

    Shared here rather than duplicated on ``ExperimentRunner`` so single-agent
    and multi-step runners compute configured expectations identically. Never
    raises: callers run it after the experiment finishes.

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


def scan_context_budget(output_dir) -> Dict[str, Any]:
    """Summarize near-limit and truncated LLM calls from ``raw/*_traces.jsonl``.

    Uses peak-first precedence (``prompt_tokens_peak`` / ``num_ctx_peak``,
    falling back to ``prompt_tokens`` / ``num_ctx``) and ignores rows where
    ``num_ctx <= 0`` (mock or cloud providers). Returns ``{}`` when no decision
    reached >= 90% of ``num_ctx``, keeping clean and mock ``run_integrity.json``
    files byte-identical. Never raises.
    """
    raw_dir = Path(output_dir) / "raw"
    try:
        if not raw_dir.is_dir():
            return {}
        trace_paths = sorted(raw_dir.glob("*_traces.jsonl"))
    except OSError as exc:
        logger.debug(f"[Integrity] context-budget trace scan skipped: {exc}")
        return {}
    near_limit = 0
    truncated = 0
    max_ratio = 0.0
    for trace_path in trace_paths:
        try:
            with trace_path.open("rb") as fh:
                for raw_line in fh:
                    try:
                        text = raw_line.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        continue
                    if not text:
                        continue
                    try:
                        row = json.loads(text)
                    except ValueError:
                        continue
                    if not isinstance(row, dict) or "_metadata" in row:
                        continue
                    stats = row.get("llm_stats") or {}
                    if not isinstance(stats, dict):
                        continue
                    pt = stats.get("prompt_tokens_peak") or stats.get("prompt_tokens") or 0
                    nc = stats.get("num_ctx_peak") or stats.get("num_ctx") or 0
                    if (
                        isinstance(pt, bool)
                        or isinstance(nc, bool)
                        or not isinstance(pt, (int, float))
                        or not isinstance(nc, (int, float))
                        or not (math.isfinite(pt) and math.isfinite(nc))
                    ):
                        continue
                    if nc <= 0 or pt <= 0:
                        continue
                    ratio = float(pt) / float(nc)
                    if ratio >= 0.90:
                        near_limit += 1
                        if ratio >= 1.0:
                            truncated += 1
                        if ratio > max_ratio:
                            max_ratio = ratio
        except OSError as exc:
            logger.debug(f"[Integrity] context-budget trace read skipped ({trace_path}): {exc}")
            continue
    if near_limit == 0:
        return {}
    return {
        "context_budget_near_limit_rows": near_limit,
        "context_budget_truncated_rows": truncated,
        "max_context_utilization": round(max_ratio, 4),
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
    reflection_enabled: Optional[bool] = None,
    governance_mode: Optional[str] = None,
    seed=None,
    expected_rows=None,
    expected_agents=None,
    expected_years: Optional[int] = None,
    corrected_status_columns: Optional[bool] = None,
    sentinel_write_failures: Optional[int] = None,
    extra: Optional[dict] = None,
    verbose: bool = True,
    no_appraisal: bool = False,
    governance_carryover: Optional[dict] = None,
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
    Pass the resolved ``reflection_enabled`` flag when the run enables or
    disables reflection independently of its memory engine. When absent,
    the existing expectation for humancentric memory is retained.

    ``no_appraisal`` (R5 walk finding 10): every agent in the run declares
    ``psychological_framework: none``. The uncategorised-rule explanation is then
    logged at debug level instead of as a warning; the counts are recorded the
    same way.

    ``governance_carryover`` (Invariant 7; ``python -m broker.run`` passes it):
    the keyword arguments of :func:`governance_carryover_block`. The block is
    written under the same key, and ``integrity_ok`` is False when its ``ok``
    is. Omitted, the run's key set is unchanged.

    Returns the audit dict (also embedded in the reproducibility manifest by callers
    that have one).
    """
    output_dir = Path(output_dir)
    reflection_tracked = reflection_engine is not _UNSET
    refl_exists, refl_count = count_reflection_entries(output_dir)
    memory_engine_class = type(memory_engine).__name__ if memory_engine is not None else None

    # Resolve the effective memory engine type: the explicit string if the caller
    # passed it (run_flood), else inferred from the instantiated class (ExperimentRunner).
    # The resolved reflection_enabled flag takes precedence over the legacy
    # humancentric memory default, independently of a reflection_engine object.
    effective_type = memory_engine_type or _MEM_CLASS_TO_TYPE.get(memory_engine_class)
    reflection_expected = (reflection_enabled if reflection_enabled is not None
                           else effective_type == "humancentric")

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

    # Framework + audit-schema provenance and audit-CSV coverage (additive into
    # run_integrity.json only; no CSV byte is touched). Answers from the
    # artifact alone which framework wrote the run, under which audit schema,
    # and whether every expected agent-year reached the CSV.
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
        # Distinguish coverage-calculation errors from genuinely empty runs so a
        # plausible zero is never mistaken for a measurement.
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

    # Match the CSV sidecar's corrected-column schema version ("3").
    if (
        provenance
        and corrected_schema_version
        and coverage.get("audit_corrected_status_columns")
    ):
        audit["framework_provenance"]["audit_schema_version"] = corrected_schema_version

    # Record resolved flag unconditionally (even if the run wrote no CSV).
    audit["audit_corrected_status_columns_resolved"] = (
        corrected_status_columns if isinstance(corrected_status_columns, bool)
        else None
    )

    # Sentinel rows the writer failed to write (highlights denominator holes).
    if isinstance(sentinel_write_failures, int):
        audit["audit_sentinel_write_failures"] = sentinel_write_failures

    # Rules that fired without matching a rules_*_hit bucket. Kept on the
    # inference path only so flag-OFF runs do not emit false warnings.
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
                (logger.debug if no_appraisal else logger.warning)(
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

    # World-grounded profile evaluability: count rows where every grounded rule
    # was unevaluable because the environment omitted its target variable.
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

    # Rows that finished normally (not aborted) without calling
    # note_world_grounded_row(). Only meaningful when _wg_rows > 0 so runs with
    # audit.grounding_columns disabled do not trigger false alarms.
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

    # Replay runs opting out of options-text parity checks record the skip count;
    # omitted when zero to preserve byte-identity on live runs.
    render_check_skipped = get_render_check_skipped_count()
    if render_check_skipped:
        audit["render_check_skipped_rows"] = render_check_skipped

    # Per-decider audit census; omitted on plain single-LLM runs when disabled.
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

        # Warn on any declared decider arm that produced zero audit rows. Domain
        # overrides appear as `<name>@<domain>`, so compare on the bare name.
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

        # Compare un-subtracted totals (decider_rows_total vs audit_rows) so
        # exception sentinels whose CSV status falls back to UNKNOWN under
        # corrected_status_columns=OFF do not cause a false remainder mismatch.
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

        # Warn if every row of a rule-based arm fell back to default_action.
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

        # Unresolved rule fields and rule firing tallies.
        unresolved = get_rule_field_unresolved()
        if unresolved:
            audit["rule_field_unresolved"] = unresolved
        firings = get_rule_firings()
        if firings:
            audit["rule_firings"] = firings

    if extra:
        audit.update(extra)

    ctx_budget = scan_context_budget(output_dir)
    if ctx_budget:
        audit.update(ctx_budget)
        if ctx_budget.get("context_budget_truncated_rows", 0) > 0:
            logger.warning(
                "[Integrity] %d decision(s) reached or exceeded num_ctx "
                "(max utilization %.1f%%) — local LLM servers such as Ollama "
                "silently truncate the prompt head when prompt_tokens >= num_ctx. "
                "Raise global_config.llm.num_ctx or trim prompt/memory content.",
                ctx_budget["context_budget_truncated_rows"],
                ctx_budget["max_context_utilization"] * 100.0,
            )

    carryover_ok = True
    if governance_carryover is not None:
        try:
            carryover = governance_carryover_block(output_dir, **governance_carryover)
        except Exception as exc:  # never raises (see docstring)
            carryover = {"error": f"{type(exc).__name__}: {exc}", "ok": False}
        audit["governance_carryover"] = carryover
        carryover_ok = bool(carryover.get("ok"))

    # mismatch = a run expecting reflection produced no reflection entries
    # (refl_count <= 0 also catches the -1 "exists but unreadable" sentinel — the
    # conservative direction: flag rather than silently pass).
    mismatch = reflection_expected and refl_count <= 0
    audit["integrity_ok"] = not (mismatch or world_rules_never_evaluable) and carryover_ok

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
        if ctx_budget.get("context_budget_truncated_rows", 0) > 0:
            print(
                f" [Integrity] WARNING: {ctx_budget['context_budget_truncated_rows']} "
                f"decision(s) reached/exceeded num_ctx (max utilization "
                f"{ctx_budget['max_context_utilization']:.1%}); raise global_config.llm.num_ctx."
            )
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
            expectation_source = (f"reflection_enabled={reflection_enabled!r}"
                                  if reflection_enabled is not None
                                  else "the humancentric memory default")
            print(f" [INTEGRITY GUARDRAIL] Reflection expected from {expectation_source}, but")
            print(" reflection_log.jsonl")
            print(f" has {refl_count} entries at {output_dir}. Reflection did NOT run —")
            print(" this run is NOT comparable to reflection-on runs (the 2026-05-30")
            print(" data-defect failure mode).")
            print("!" * 72 + "\n")
        if not (mismatch or world_rules_never_evaluable):
            engine = effective_type or memory_engine_class or "unknown"
            print(f" [Integrity] reflection={refl_count} entries | engine={engine} | "
                  f"mode={governance_mode} | OK")
    return audit


# --- Invariant 7: governance_carryover block (design 5.2) -------------------
# The framework's own wording for a rule that stepped in. A run whose memory
# style is ``executed`` should never hold these in memory or reflection.
GOVERNANCE_PHRASES = ("was rejected", "default action applied", "was applied under", "proposal to")
_MIN_TERM_LENGTH = 4


def _governance_terms(output_dir: Path, unreadable: List[str]) -> List[str]:
    """Rule ids and rule messages from the run's audit CSV, plus the phrases above.

    Taken from what the rules said in this run, not typed by hand. Terms
    shorter than four characters are left out (they match ordinary words).
    A CSV that cannot be read is added to ``unreadable``.
    """
    import csv

    terms = set(GOVERNANCE_PHRASES)
    for path in sorted(Path(output_dir).glob("*governance_audit.csv")):
        try:
            with open(path, encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    for rule in (row.get("failed_rules") or "").split("|"):
                        terms.add(rule.strip())
                    for issue in (row.get("error_messages") or "").split("|"):
                        for message in issue.split("; "):
                            terms.add(message.strip())
        except (OSError, csv.Error, UnicodeDecodeError):
            unreadable.append(path.name)
    terms.discard("Unknown")
    return sorted(t.lower() for t in terms if len(t.strip()) >= _MIN_TERM_LENGTH)


def _jsonl(path: Path, unreadable: List[str]) -> List[dict]:
    """Rows of a JSONL file. A file with a line that does not parse, or that
    cannot be read, is added to ``unreadable`` (a missing file is not)."""
    if not path.exists():
        return []
    rows = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        if path.name not in unreadable:
                            unreadable.append(path.name)
    except (OSError, UnicodeDecodeError):
        unreadable.append(path.name)
    return rows


def _line_shape(line: str, action: str, number: str) -> str:
    """The line without its number text, its action as ``<action>``, numeric spans as ``#``.

    The number text is dropped, not replaced: whether a line carries a number
    follows the action that ran (a default runs with none), not the rule.
    """
    shape = line
    if number:
        shape = shape.replace(number, "")
    if action:
        if action[0].isalnum() and action[-1].isalnum():
            shape = re.sub(rf"\b{re.escape(action)}\b", "<action>", shape)
        else:
            shape = shape.replace(action, "<action>")
    return re.sub(r"\d+(?:\.\d+)?", "#", shape)


def governance_carryover_block(
    output_dir,
    *,
    styles: Dict[str, str],
    agent_types: Dict[str, str],
    writes_by_origin: Optional[Dict[str, int]],
    decision_lines: List[dict],
) -> Dict[str, Any]:
    """Invariant 7 record for one run (``run_integrity.json``, design 5.2).

    ``styles``: memory line style per agent type; ``agent_types``: agent id to
    type; ``decision_lines``: what the runner wrote each decision, as
    ``{agent_id, period, intervened, default_ran, line, action, number}``
    (``intervened``: the row ended REJECTED or UNCERTAIN; ``default_ran``: the
    registry default ran in its place).

    Counts are over agent types whose style is ``executed`` (the other styles
    name the rule on purpose). ``ok`` is False when one of them is above 0,
    when ``memory_log.jsonl`` holds fewer rows than the write gate counted, or
    when a file the block reads cannot be read.
    A world rule shown in the prompt of both arms can trip the term counts,
    so they are a flag to read, not a proof; the proof is the twin run
    (``python -m broker.tools.check_governance_carryover``).
    """
    output_dir = Path(output_dir)
    checked = sorted(t for t, s in styles.items() if s == "executed")
    in_scope = lambda agent_id: agent_types.get(str(agent_id)) in checked
    unreadable: List[str] = []
    terms = _governance_terms(output_dir, unreadable)

    def hits(text: str) -> List[str]:
        low = (text or "").lower()
        return [t for t in terms if t in low]

    examples: List[dict] = []

    def count(entries, label, texts_of):
        n = 0
        for entry in entries:
            if not in_scope(entry.get("agent_id")):
                continue
            found = sorted({t for text in texts_of(entry) for t in hits(text)})
            if found:
                n += 1
                if len(examples) < 5:
                    examples.append({"where": label, "agent_id": entry.get("agent_id"),
                                     "period": next((entry[k] for k in ("period", "year", "year_created")
                                                     if entry.get(k) is not None), None),
                                     "terms": found})
        return n

    memory = _jsonl(output_dir / "memory_log.jsonl", unreadable)
    reflections = _jsonl(output_dir / "reflection_log.jsonl", unreadable)
    writes = sum((writes_by_origin or {}).values())
    memory_log_short = bool(checked) and len(memory) < writes
    in_memory = count(memory, "memory", lambda e: [str(e.get("content", ""))])
    in_input = count(reflections, "reflection_input",
                     lambda e: [str(x) for x in (e.get("reflection_input") or [])])
    in_output = count(reflections, "reflection_output", lambda e: [str(e.get("summary", ""))])

    scoped = [d for d in decision_lines if in_scope(d.get("agent_id"))]
    plain = {_line_shape(d["line"], d.get("action", ""), d.get("number", ""))
             for d in scoped if not d.get("intervened")}
    governed = [d for d in scoped if d.get("intervened")]
    if governed and plain:
        shapes = sum(1 for d in governed
                     if _line_shape(d["line"], d.get("action", ""), d.get("number", "")) not in plain)
    else:
        shapes = None  # nothing to compare against
    block = {
        "rejection_line_style": dict(styles),
        "checked_agent_types": checked,
        "memory_writes_by_origin": dict(writes_by_origin or {}),
        "memory_log_rows": len(memory),
        "memory_log_short": memory_log_short,
        "unreadable_files": unreadable,
        "decision_rows": len(decision_lines),
        "rejected_or_unreadable_rows": sum(1 for d in decision_lines if d.get("intervened")),
        "default_applied_rows": sum(1 for d in decision_lines if d.get("default_ran")),
        "line_shapes_compared": shapes is not None,
        "default_year_line_shapes_not_seen_in_approved_years": shapes,
        "governance_terms_checked": len(terms),
        "governance_terms_in_memory": in_memory,
        "governance_terms_in_reflection_input": in_input,
        "governance_terms_in_reflection_output": in_output,
        "examples": examples,
    }
    block["ok"] = not checked or not (
        (shapes or 0) or in_memory or in_input or in_output
        or memory_log_short or unreadable)
    return block
