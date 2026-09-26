"""AuditMixin — audit trace writing and state management helpers.

Extracted from SkillBrokerEngine to reduce file size.  These methods
access ``self.*`` attributes defined on SkillBrokerEngine; this is the
standard Python mixin pattern where the mixin is always combined with
the host class via multiple inheritance.
"""
from typing import Any, Dict, List, Optional
import hashlib
import json

from ..interfaces.skill_types import (
    ExecutionResult, SkillOutcome, ValidationResult,
)
from ..utils.logging import logger


def _classify_decision_source(approved_skill, skill_proposal=None) -> str:
    """Classify how the final action was determined.

    PR-4 (audit finding #4): this never consulted ``skill_proposal.parse_layer``,
    so a proposal the PARSER substituted because nothing else parsed
    (``parse_layer == "default"``) that happened to pass governance was
    classified ``"llm_reasoned"`` — indistinguishable in the JSONL from a
    genuine model decision. When the hardened layers applied, an APPROVED
    proposal whose ``parse_layer`` is/contains ``"default"`` is reclassified
    ``"default_substituted"`` instead.

    PR-4 (D5): whether they applied is read off the PROPOSAL
    (``strict_layers_applied``, stamped by ``UnifiedAdapter.parse_output``),
    not re-derived from this object's config. The earlier draft read
    ``global_config.parsing.strict_layers`` off the ENGINE's config while the
    parser read it off the ADAPTER's config — the same object in production,
    routinely different objects in tests and in any embedding that builds them
    separately, so a proposal parsed under the flag could be classified as
    though it had not been. The parser is the single source of truth; a
    proposal parsed with the flag OFF (and every proposal from a non-WAGF
    adapter) simply has no such attribute and ``getattr`` resolves False, which
    is byte-for-byte the pre-PR-4 classification.
    """
    if approved_skill is None:
        return "parse_failure"
    status = approved_skill.approval_status
    if status == "APPROVED" and getattr(skill_proposal, "strict_layers_applied", False):
        parse_layer = str(getattr(skill_proposal, "parse_layer", "") or "")
        if "default" in parse_layer.lower():
            return "default_substituted"
    if status == "APPROVED":
        return "llm_reasoned"
    elif status == "REJECTED_FALLBACK":
        return "fallback_default"
    elif status == "REJECTED":
        return "validator_rejected"
    return "unknown"


def _safe_rule_breakdown(
    all_validation_history, allow_metadata_fallback: bool = False
) -> Dict[str, int]:
    """Compute rule-category hit counts safely.

    Phase 6C W8: previously the audit trace omitted ``rule_breakdown``
    entirely, so audit CSV ``rules_*_hit`` columns were silent
    placeholders. We now populate from the validation history. Lazy
    import of ``get_rule_breakdown`` avoids a startup circular import
    between ``broker.core`` and ``broker.validators.governance``.

    ``allow_metadata_fallback`` (PR-3, set only when
    ``global_config.audit.corrected_status_columns`` is ON) lets the
    breakdown infer a category from ``metadata["tier"]`` / validator name /
    rule id — without it, every production run through ``AgentValidator``
    reports zero for four of the five buckets no matter how many rules
    fired. Default OFF keeps flag-OFF runs byte-identical.

    Falls back to a zeroed dict if anything goes wrong, so a producer
    error never breaks the audit write path.
    """
    try:
        from ..validators.governance import get_rule_breakdown
        results = []
        for v in all_validation_history or []:
            results.extend(v if isinstance(v, list) else [v])
        return get_rule_breakdown(
            results, allow_metadata_fallback=allow_metadata_fallback
        )
    except Exception as exc:
        logger.warning(f"[Audit] rule_breakdown computation failed: {exc}")
        return {"personal": 0, "social": 0, "thinking": 0, "physical": 0, "semantic": 0}


def _safe_triggered_rules(all_validation_history) -> List[str]:
    """Collect rule IDs that fired (either BLOCKING or WARNING).

    Phase 6Q-D-3 (2026-05-26): wires the previously-aspirational
    ``triggered_rules`` trace key. Pre-fix the audit CSV
    ``rules_triggered`` column read ``t.get("triggered_rules", [])``
    but no producer ever wrote it — Task-041 Phase 3 left the schema
    + reader in place without populating the producer. (Distinct
    from ``failed_rules``, which lists ONLY blocking-result rule_ids
    via ``validation_issues``; this new field gives a unified
    BLOCK+WARN view.)

    Sources rule_ids from each :class:`ValidationResult` in the
    history's ``.metadata.rule_id`` (single) + ``.metadata.rules_hit``
    (list, used by validator bundles). Dedupes + sorts. Returns
    ``[]`` on any error (the audit write path must never crash).
    """
    try:
        rule_ids: set = set()
        for batch in all_validation_history or []:
            results = batch if isinstance(batch, list) else [batch]
            for r in results:
                if not hasattr(r, "metadata"):
                    continue
                meta = r.metadata or {}
                rid = meta.get("rule_id")
                if rid:
                    rule_ids.add(str(rid))
                hits = meta.get("rules_hit", []) or []
                for h in hits:
                    if h:
                        rule_ids.add(str(h))
        return sorted(rule_ids)
    except Exception as exc:
        logger.warning(f"[Audit] triggered_rules computation failed: {exc}")
        return []


def _safe_rules_by_grounding(all_validation_history):
    """PR-6: split the rule ids that fired into (world-grounded, self-report).

    Reads ``metadata["grounding"]``, which the validators stamp per FIRING. A
    result without the key counts as self-report — the honest default: a rule
    is not world-grounded until something says it read the world.

    Returns ``([], [])`` on any error. The audit write path must never be the
    thing that ends a run.
    """
    try:
        world, self_report = set(), set()
        for batch in all_validation_history or []:
            results = batch if isinstance(batch, list) else [batch]
            for r in results:
                meta = getattr(r, "metadata", None) or {}
                ids = set()
                if meta.get("rule_id"):
                    ids.add(str(meta["rule_id"]))
                for h in (meta.get("rules_hit") or []):
                    if h:
                        ids.add(str(h))
                if not ids:
                    continue
                bucket = world if meta.get("grounding") == "world" else self_report
                bucket |= ids
        # A rule id that fired both ways in one decision (a retry re-derived it
        # from a different condition) is reported as world-grounded, because the
        # stronger claim is the one a reader must be able to check.
        return sorted(world), sorted(self_report - world)
    except Exception as exc:
        logger.warning(f"[Audit] grounding split failed: {exc}")
        return [], []


def _row_world_rules_unevaluable(all_validation_history) -> bool:
    """PR-6 P1-a: True iff every world-grounded rule was unreadable on this row.

    Reads the per-pass census the AgentValidator stamps on each
    ``world_variable_missing`` finding. A row where one grounded rule fired and
    another was unreadable is NOT unevaluable — it is a row with a gap. Only a
    row where no grounded rule could be evaluated at all counts, because that is
    the row whose CSV is indistinguishable from a self-report-only run's.

    Returns ``False`` on any error: this feeds a side-artifact tally, and a
    tally must never be the thing that ends a run.
    """
    try:
        saw_pass = False
        for batch in all_validation_history or []:
            results = batch if isinstance(batch, list) else [batch]
            for r in results:
                meta = getattr(r, "metadata", None) or {}
                if "world_rules_unevaluable_pass" not in meta:
                    continue
                if not meta.get("world_rules_unevaluable_pass"):
                    return False
                saw_pass = True
        return saw_pass
    except Exception as exc:
        logger.warning(f"[Audit] world-rule evaluability tally failed: {exc}")
        return False


def _note_world_grounded_row(unevaluable: bool) -> None:
    """Increment the process-global evaluability tally. Never raises.

    Lazily imported for the same reason the uncategorised-rule tally is: the
    module it lives in reaches back into the analytics package, and a
    module-level import here would close a startup cycle.
    """
    try:
        from broker.core.run_integrity import note_world_grounded_row

        note_world_grounded_row(bool(unevaluable))
    except Exception as exc:  # noqa: BLE001 — side-artifact tally only
        logger.debug(f"[Audit] world-rule evaluability tally skipped: {exc}")


def _note_decider_row(decider: str, path: str = "") -> None:
    """PR-8: increment the per-decider row census. Never raises.

    ``path`` rides along so the ``rule_default`` and ``aborted``
    sub-censuses are incremented from the same call as the main one and
    the three cannot drift apart.

    Lazily imported for the same startup-cycle reason as the tally above.
    """
    try:
        from broker.core.run_integrity import note_decider_row

        note_decider_row(decider, path)
    except Exception as exc:  # noqa: BLE001 — side-artifact census only
        logger.debug(f"[Audit] decider row census skipped: {exc}")


def _sanitize_audit_segment(value) -> str:
    """P0-1a: make a value safe to embed in a ``|``/``=`` delimited audit field.

    The separators are replaced, NOT dropped, so a downstream ``.split("|")`` /
    ``.split("=")`` can never mis-parse a record. This matters because
    ``normalize_construct_value`` (broker/utils/normalization.py) returns the
    RAW LLM string unchanged whenever it fails to match the canonical VL..VH
    vocabulary, a custom mapping, or the regex-derived allowed values — so an
    off-vocabulary label can carry arbitrary characters straight through to
    here. Silent ambiguity in exactly the columns that exist to make the
    "governance changed the action" metric trustworthy would be the worst
    possible failure mode, hence substitution rather than best-effort joining.
    """
    return str(value).replace("|", "/").replace("=", ":")


def _extract_construct_labels(skill_proposal) -> str:
    """P0-1a: pipe-joined ``KEY=VALUE`` of a proposal's ``*_LABEL`` reasoning keys.

    Used to snapshot the FIRST attempt's appraisal labels before the governance
    retry loop reassigns ``skill_proposal``, so appraisal drift across retries
    is measurable. Returns "" for a missing proposal, missing/invalid reasoning,
    or a proposal carrying no ``_LABEL`` keys — never raises, because this runs
    on the audit path where a failure must not lose the decision record.

    Key order follows the reasoning dict (insertion-ordered from the parser),
    matching how ``_LABEL`` keys are surfaced elsewhere in the audit trace.
    Keys and values are separator-sanitized (see ``_sanitize_audit_segment``).
    """
    if skill_proposal is None:
        return ""
    reasoning = getattr(skill_proposal, "reasoning", None)
    if not isinstance(reasoning, dict):
        return ""
    return "|".join(
        f"{_sanitize_audit_segment(k)}={_sanitize_audit_segment(v)}"
        for k, v in reasoning.items()
        if isinstance(k, str) and k.endswith("_LABEL")
    )


def _label_drift(initial_labels: str, final_labels: str) -> str:
    """Per-construct change between two ``KEY=VALUE|...`` label strings (as
    written by ``_extract_construct_labels``), in first-attempt key order:
    ``"A_LABEL:H>M|B_LABEL:H>VH"``. A key present on one side only shows its
    missing side as empty (``"A_LABEL:H>"``). "" when nothing changed."""
    def parse(text: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for part in (text or "").split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = v
        return out

    first, last = parse(initial_labels), parse(final_labels)
    keys = list(first) + [k for k in last if k not in first]
    return "|".join(
        f"{k}:{first.get(k, '')}>{last.get(k, '')}"
        for k in keys
        if first.get(k, "") != last.get(k, "")
    )


def _safe_social_audit(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured social-context audit fields from a prompt context.

    The social pipeline feeds neighbor observations, gossip, visible actions,
    and communication messages into prompts through ``context["local"]``. This
    helper mirrors that data into the audit trace so MA social-behavior analyses
    can read structured columns instead of reverse-parsing prompt text.
    """
    try:
        local = context.get("local", {}) if isinstance(context, dict) else {}
        if not isinstance(local, dict):
            return {}

        spatial = local.get("spatial", {}) if isinstance(local.get("spatial", {}), dict) else {}
        social = local.get("social", [])
        if isinstance(social, str):
            gossip_received = [social] if social else []
        elif isinstance(social, list):
            gossip_received = [str(item) for item in social if item]
        else:
            gossip_received = []

        visible_counts: Dict[str, int] = {}
        visible_actions = local.get("visible_actions", [])
        if isinstance(visible_actions, list):
            for action in visible_actions:
                if not isinstance(action, dict):
                    continue
                action_id = action.get("action") or action.get("skill") or action.get("decision")
                if action_id:
                    visible_counts[str(action_id)] = visible_counts.get(str(action_id), 0) + 1

        audit = {
            "gossip_received": gossip_received,
            "neighbor_count": spatial.get("neighbor_count", local.get("neighbor_count", 0)),
            "network_density": spatial.get("network_density", local.get("network_density", 0.0)),
            "visible_actions": visible_counts,
        }

        for key in ("observable_attrs", "neighbor_action_summary", "messages"):
            if key in local:
                audit[key] = local[key]
        if "messages" in context:
            audit["messages"] = context["messages"]
        return audit
    except Exception as exc:
        logger.warning(f"[Audit] social_audit extraction failed: {exc}")
        return {}


# PR-3: the value written to ``mem_top_emotion`` / ``mem_top_source`` when the
# retrieved memory record carries no such key. The pre-PR-3 literals
# ("neutral" / "personal") are indistinguishable in the CSV from a genuine
# unanimous mode, which is the 2026-04-19 NW-flood failure class; this marker
# is not, and it is what ``detect_audit_sentinels`` would rather see.
UNOBSERVED = "unobserved"


#: The four token columns ``trace_to_csv_row`` fills with 0 / 0.0 when the
#: producing stats dict has no such key. On an ordinary row that default is
#: harmless (the run genuinely reported no tokens); on the ABORTED sentinel it
#: would be a fabricated measurement of a call that DID happen, so the sentinel
#: writes "" for each key its stats dict does not carry.
#:
#: The 2026-09-15 cost columns (`llm_calls_total`, `llm_latency_ms`,
#: `tokens_per_second`, `prompt_tokens_total`, `response_tokens_total`)
#: deliberately do NOT join this list. Those keys are KEY-GATED in
#: `trace_to_csv_row`, so blanking an absent one here would CREATE the column on
#: the sentinel row alone — and CSV fieldnames are the union over rows, so one
#: sentinel would widen the header for the whole run. That is the exact failure
#: `test_aborted_sentinel_introduces_no_new_columns` exists to catch.
#:
#: Leaving them out is also the honest reading, though not for the reason it
#: would be tempting to write. A sentinel CAN lack them while its neighbours
#: carry them — if `llm_invoke` raised on every attempt of one step, that
#: step's dict never reached `accumulate_llm_stats`. What happens then is that
#: `DictWriter` restval-fills the cell with "", which is the same "" this
#: blanking would have produced. The gap is marked either way; only the header
#: differs, and the narrower header is the correct one.
_TOKEN_STAT_KEYS = ("prompt_tokens", "response_tokens", "num_ctx",
                    "context_utilization")


def _sentinel_llm_stats(stats: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The real LLM stats for an aborted step, with gaps marked as gaps.

    ``llm_success`` is left exactly as the retry loop reported it — on a parse
    failure the CALL usually succeeded and only the PARSE failed, and those are
    different facts. What is missing stays "" rather than becoming a zero
    someone can average.
    """
    out: Dict[str, Any] = dict(stats or {})
    if "llm_success" not in out:
        out["llm_success"] = ""
    for key in _TOKEN_STAT_KEYS:
        if key not in out:
            out[key] = ""
    return out


#: One warning per (reason, config class) per process. A raising or non-bool
#: getter is a property of the CONFIG OBJECT, not of the row being written, so
#: warning per call would emit the same line thousands of times per run and
#: train the operator to filter it out — which is how the silent failure this
#: warning exists to surface gets re-buried.
#:
#: PR-4: the key is the REASON TOKEN, never the exception's message. Keying on
#: the message (as this did) lets a getter whose text carries anything variable
#: — an agent id, a path — mint a fresh key on every call, so the set grows
#: without bound and the "once" never holds. Same defect, same fix, as
#: ``broker/utils/parsing/unified_adapter.py::_PARSING_FLAG_WARNED``. Log-only:
#: no audit value depends on it.
_FLAG_WARNED: set = set()


def _warn_once(reason: str, detail: str, config) -> None:
    key = (reason, type(config).__name__)
    if key in _FLAG_WARNED:
        return
    _FLAG_WARNED.add(key)
    logger.warning(
        "[Audit] audit.corrected_status_columns is being read OFF: %s "
        "(config type %s). The audit CSV will carry the UNCORRECTED columns — "
        "`fallback_activated` from the blocked proposal, `rules_*_hit` "
        "structurally zero, no `execution_path`, no row for aborted steps. "
        "If you meant to enable the flag, this run did not.",
        detail, type(config).__name__,
    )


def _corrected_status_flag(config) -> bool:
    """True iff this run opted into ``audit.corrected_status_columns``.

    Coerced to a real ``bool``, never truth-tested raw: tests build engines
    with ``MagicMock`` configs, and ``bool(MagicMock())`` is True — a bare
    truth test would silently switch the corrected semantics on in every
    mock-config run and change values nobody asked to change.

    Every way of failing to read the flag resolves it OFF, which is the safe
    direction for byte identity but the WRONG direction for someone who set it
    in YAML and expects corrected columns. So each such path says so once
    (PR-3 review item P1e): a flag that fails closed in silence is
    indistinguishable from a flag nobody set.
    """
    getter = getattr(config, "get_audit_corrected_status_columns", None)
    if not callable(getter):
        # Not a warning: a config object predating the flag (or a narrow test
        # double) legitimately has no such getter, and OFF is then correct.
        return False
    try:
        value = getter()
    except (AttributeError, TypeError, ValueError) as exc:
        # Narrow on purpose. A KeyboardInterrupt / SystemExit / genuine bug in
        # the config layer must propagate rather than be recorded as "OFF".
        _warn_once("getter_raised",
                   f"the getter raised {type(exc).__name__}: {exc}", config)
        return False
    if isinstance(value, bool):
        return value
    _warn_once("getter_non_bool",
               f"the getter returned {type(value).__name__} rather than a bool",
               config)
    return False


#: PR-4 (D5): there is deliberately NO parsing-flag resolver here. The parser
#: resolves ``global_config.parsing.strict_layers`` once per parse call
#: (``broker/utils/parsing/unified_adapter.py::resolve_strict_layers_flag``,
#: which owns the fail-closed-with-one-warning discipline) and stamps the
#: answer on the proposal. The audit layer reads the proposal, never the
#: config: two independent reads of one flag is how the two sides come to
#: disagree.


class AuditMixin:
    """Mixin providing audit trace writing and state management helpers."""

    # ------------------------------------------------------------------
    # PR-8: decider provenance
    # ------------------------------------------------------------------
    def _decider_audit_extra(
        self, decider: Optional[str], *, path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """The two gated decider columns for one row, or ``{}`` when off.

        ``decider`` names WHAT decided (``llm`` / ``rule_based`` /
        ``hybrid`` / a domain's own). ``decider_path`` names WHICH WAY
        that thing went on this particular decision, which only differs
        from the name for a hybrid — and for a hybrid it is the whole
        point, since a hybrid run without it is indistinguishable in the
        CSV from either pure run.

        ``path`` FORCES the recorded path. The aborted-step sentinels
        pass ``"aborted"``: the row exists because the step crashed or
        never parsed, so there is no completed decision path to report,
        and letting the sentinel inherit a decider's default path would
        put a row in the census as if it had decided something. The
        thread-local slot is popped either way, so a value recorded by
        the call that then crashed cannot leak into the NEXT row.

        Returns ``{}`` unless the flag is on, so a config where every
        agent type is (or defaults to) ``llm`` adds no row keys, gains
        no CSV columns, and reruns byte-identically. Every failure here
        also returns ``{}``: a provenance column is worth having, and
        never worth aborting a decision for.
        """
        get_flag = getattr(self.config, "get_audit_decider_columns", None)
        if not callable(get_flag):
            return {}
        try:
            if not get_flag():
                return {}
        except Exception:  # noqa: BLE001
            return {}
        name = str(decider or "llm")
        # P1-d: a domain that deliberately replaced a built-in writes
        # `<name>@<domain>`; the built-in default path is keyed on the
        # bare name, so look it up on the bare name.
        bare = name.split("@", 1)[0]
        try:
            from broker.agents.deciders import BUILTIN_DEFAULT_PATHS, take_decider_path
            recorded = take_decider_path(BUILTIN_DEFAULT_PATHS.get(bare, bare))
        except Exception as exc:  # noqa: BLE001
            logger.debug("[Audit] decider path unavailable: %s", exc)
            recorded = bare
        resolved = str(path) if path else recorded
        _note_decider_row(name, resolved)
        return {"decider": name, "decider_path": resolved}

    # ------------------------------------------------------------------
    # Audit trace
    # ------------------------------------------------------------------
    def _write_aborted_sentinel_trace(
        self, *, agent_type: str, run_id: str, step_id: Any, timestamp: str,
        env_context: Optional[Dict], seed: Any, agent_id: str,
        raw_output: str, format_retry_count: int,
        llm_stats: Optional[Dict[str, Any]] = None,
        memory_pre: Optional[List] = None,
        prompt: str = "",
        parsing_warnings: Optional[List[str]] = None,
        decider: Optional[str] = None,
    ) -> None:
        """PR-3: emit one audit row for a step that returned ``ABORTED``.

        A step whose LLM output never parses returns from ``process_step``
        BEFORE the single ``_write_audit_trace`` call site, so it reaches
        neither the JSONL nor the CSV. The arm with more parse failures then
        has FEWER audit rows than its counterpart, and the asymmetry is
        invisible unless someone cross-checks the row count against the
        agent x year grid. This sentinel conserves the count.

        Written only under ``audit.corrected_status_columns`` — it adds a row
        to the CSV, which no frozen corpus may gain. Caller checks the flag.

        The row carries ``status=ABORTED``, an empty ``executed_skill`` and
        ``execution_path=aborted``: nothing ran, and the row says so rather
        than leaving a gap that looks like a step that never happened.

        ``llm_stats`` / ``memory_pre`` / ``prompt`` are the REAL values live at
        the call site (PR-3 review item P1b). Omitting them was not neutral:
        ``trace_to_csv_row`` defaults a missing ``llm_stats`` to
        ``llm_success=True, prompt_tokens=0, context_utilization=0.0`` and a
        missing ``memory_audit`` to ``mem_retrieved_count=0``, so a row created
        to make a failure visible instead asserted a successful zero-token call
        that retrieved nothing. A sentinel that lies about the call it records
        is worse than the missing row it replaces. Whatever genuinely was not
        measured is written as ``""`` — never as 0, never as True.

        ``parsing_warnings`` (PR-4 D6) carries the warnings the parser
        collected on the attempt that returned ``None``. They are the only
        record of WHY this step aborted — which candidate digits were
        suppressed, which JSON error was hit — and without them they die with
        the discarded proposal. Populated only under
        ``parsing.strict_layers``; when empty, ``skill_proposal`` stays
        ``None`` exactly as before, so the row is byte-identical to PR-3's.
        The dict form repeats ``raw_output`` because ``trace_to_csv_row`` reads
        that column off ``skill_proposal`` first and would otherwise blank it.
        """
        try:
            agent_type_final = agent_type or "default"
            log_fields = self.config.get_log_fields(agent_type_final)
            memory_pre = list(memory_pre or [])
            self.audit_writer.write_trace(agent_type_final, {
                "run_id": run_id,
                "step_id": step_id,
                "timestamp": timestamp,
                "year": env_context.get("current_year") if env_context else None,
                "seed": seed,
                "agent_id": agent_id,
                "model": getattr(self, "_model_name", "unknown"),
                "decision_source": "parse_failure",
                "validated": False,
                "fallback_activated": False,
                "_audit_priority": [f"reason_{f.lower()}" for f in log_fields],
                "raw_output": raw_output,
                "input": prompt,
                "llm_stats": _sentinel_llm_stats(llm_stats),
                "skill_proposal": (
                    {"parsing_warnings": list(parsing_warnings),
                     "raw_output": raw_output}
                    if parsing_warnings else None
                ),
                # trace_to_csv_row reads status off approved_skill; an empty
                # skill_name keeps final_skill blank, which is the truth here.
                "approved_skill": {
                    "skill_name": "", "status": "ABORTED", "mapping": "",
                },
                "execution_result": None,
                "outcome": SkillOutcome.ABORTED.value,
                "retry_count": 0,
                "format_retries": format_retry_count,
                # Retrieval DID happen before the parse failed, so the count is
                # a measurement. The memory bodies are omitted (the row is a
                # sentinel, not a decision record) and `retrieval_mode` says so
                # rather than reading as an ordinary retrieval. `surprise_value`
                # is "" because nothing computed it — 0.0 would be a number
                # someone could average.
                "memory_audit": {
                    "retrieved_count": len(memory_pre),
                    "memories": [],
                    "retrieval_mode": "aborted",
                    "surprise_value": "",
                },
                "social_audit": {},
                "rule_breakdown": {},
                "executed_skill": "",
                "executed_via_fallback": False,
                "execution_path": "aborted",
                # PR-8: same gated keys as every other row, so a
                # mixed-population CSV has ONE column set. The PATH is
                # forced to "aborted" (review P1-c): this row exists
                # because nothing parsed after the retries, so the
                # decider produced no decision whose path could be
                # reported, and the census must not count it as one.
                **self._decider_audit_extra(decider, path="aborted"),
            }, [
                # Passed, rather than None, for two reasons. ``write_trace``
                # forces ``validated=True`` when it receives no validation
                # results, which on an aborted step would be a plain untruth.
                # And a row that records the failure without recording WHY
                # sends the reader back to the JSONL; this puts the reason in
                # ``failed_rules`` / ``error_messages`` where every other
                # blocked decision already carries it.
                ValidationResult(
                    valid=False,
                    validator_name="SkillBrokerEngine:parse",
                    errors=["Parse error after retries"],
                    metadata={"rule_id": "parse_failure_terminal",
                              "rules_hit": ["parse_failure_terminal"],
                              "expected_terminal": True,
                              "constraint_type": "hard"},
                ),
            ])
        except Exception as exc:
            # An audit-writer failure must never convert a parse failure into
            # a crashed run; the original ABORTED result still returns.
            #
            # P2d: but a log line alone is invisible to anyone reading the
            # artifacts afterwards, and this failure is precisely a row that
            # should have existed and does not — the same denominator hole the
            # sentinel exists to close. Count it so `run_integrity.json` can
            # report it as `audit_sentinel_write_failures`.
            self._audit_sentinel_write_failures = (
                getattr(self, "_audit_sentinel_write_failures", 0) + 1
            )
            logger.error(
                f"[Audit] ABORTED sentinel write failed for {agent_id}: {exc}",
                exc_info=True,
            )

    def _write_audit_trace(
        self, *, agent_type: str, context: Dict, run_id: str,
        step_id: str, timestamp: str, env_context: Optional[Dict],
        seed: Any, agent_id: str, all_valid: bool, prompt: str,
        raw_output: str, context_hash: str, memory_pre: list,
        memory_post: list, skill_proposal, approved_skill,
        execution_result, outcome: SkillOutcome, retry_count: int,
        format_retry_count: int, total_llm_stats: Dict,
        all_validation_history: List,
        executed_skill: Optional[str] = None,
        executed_via_fallback: bool = False,
        execution_path: Optional[str] = None,
        initial_skill: Optional[str] = None,
        initial_labels: str = "",
        attempt_skills: Optional[List] = None,
        advise_info: Optional[Dict[str, Any]] = None,
        soft_advise_info: Optional[Dict[str, Any]] = None,
        decider: Optional[str] = None,
        feasible_by_attempt: Optional[List] = None,
    ) -> None:
        """Write full audit trace to audit_writer."""
        # Robust agent_type extraction (Tiered or Flat)
        agent_type_final = agent_type
        if "personal" in context and isinstance(context["personal"], dict):
            agent_type_final = context["personal"].get("agent_type", agent_type_final)
        elif "agent_type" in context:
            agent_type_final = context.get("agent_type", agent_type_final)

        # Extract audit priority fields from config
        log_fields = self.config.get_log_fields(agent_type_final)
        audit_priority = [f"reason_{f.lower()}" for f in log_fields]

        # PR-3: with corrected_status_columns ON, an ABSENT emotion/source is
        # marked as such instead of borrowing the "neutral"/"personal"
        # literals. Observed values are untouched either way — only the
        # missing-key default changes, so a run whose memory records DO carry
        # these keys reads identically under both settings.
        #
        # P2-2: ONE resolution point per run. The engine resolves the flag once
        # in __init__ (and logs the resolved value); re-reading the config here
        # per row meant a config whose getter changed mid-run — or a test double
        # that swapped it — could write some rows under one contract and some
        # under the other, in one CSV, with nothing recording the split. The
        # per-row helper stays as the fallback for a host with no engine
        # attribute (the AuditMixin test hosts, and any caller that mixes the
        # mixin into something other than SkillBrokerEngine).
        corrected = getattr(self, "_corrected_status_columns", None)
        if not isinstance(corrected, bool):
            corrected = _corrected_status_flag(self.config)
        _emotion_default = UNOBSERVED if corrected else "neutral"
        _source_default = UNOBSERVED if corrected else "personal"

        # Build memory_audit from pre-retrieval data for audit CSV
        normalized_memories = []
        for memory in memory_pre:
            if isinstance(memory, dict):
                normalized_memories.append(
                    {
                        "content": memory.get("content", ""),
                        "emotion": memory.get("emotion", _emotion_default),
                        "importance": memory.get("importance", 0.0),
                        "source": memory.get("source", _source_default),
                        "timestamp": memory.get("timestamp"),
                        "final_score": memory.get("final_score"),
                    }
                )
            else:
                normalized_memories.append(
                    {"content": memory, "emotion": _emotion_default,
                     "importance": 0.0, "source": _source_default}
                )

        memory_audit = {
            "retrieved_count": len(memory_pre),
            "memories": normalized_memories,
            "retrieval_mode": "humancentric" if memory_pre else "",
        }

        # F3 (2026-06-10 audit review): EXECUTED-stage truth, OPT-IN via
        # global_config.audit.executed_skill_columns (default OFF). Key-gated
        # by construction: when OFF the keys never enter the trace, so neither
        # the JSONL nor the row-key-derived CSV fieldnames change — frozen
        # v21 / paper-3 mock reruns stay byte-identical.
        executed_extra: Dict[str, Any] = {}
        get_flag = getattr(self.config, "get_audit_executed_columns", None)
        if (callable(get_flag) and get_flag()) or corrected:
            executed_extra = {
                "executed_skill": executed_skill,
                "executed_via_fallback": bool(executed_via_fallback),
            }
        # PR-3: `execution_path` names the remap rule that produced
        # `executed_skill` (approved / approved_no_engine / rejected_default /
        # rejected_proposal / fallback / aborted / not_executed / unknown), so
        # the row states it instead of
        # an analyst re-deriving it from `status` plus the domain's
        # `on_retry_exhausted` policy — which the CSV does not carry.
        # S2: an absent path is "unknown", not "". A blank cell reads as "this
        # column does not apply here"; the truth is that a caller reached the
        # audit writer without stating which branch ran, and the analyst should
        # be able to filter those rows out by name. "unknown" is part of the
        # documented enum for exactly that reason.
        if corrected:
            executed_extra["execution_path"] = execution_path or "unknown"

        # 6W-B6: PROPOSED-parameter columns, OPT-IN via
        # global_config.audit.param_columns (default OFF). Same key-gated
        # discipline as executed_extra: flag-OFF (or a proposal with no
        # parameters, i.e. every frozen domain) emits nothing -> no row key ->
        # no new CSV fieldname -> byte-identical. proposed_param_<name> is the
        # PROPOSAL-stage value, kept distinct from the commit-stage world_<name>
        # columns so EXECUTED-ONLY analysis never conflates them. The legacy
        # magnitude scalars are skipped (already covered elsewhere).
        # P0-1a: FIRST-ATTEMPT proposal columns, OPT-IN via
        # global_config.audit.initial_proposal_columns (default OFF). Same
        # key-gated discipline as executed_extra: flag-OFF emits no key -> no
        # row key -> no new CSV fieldname -> frozen baselines byte-identical.
        # Closes the proposal-stage gap: `skill_proposal` is reassigned on every
        # governance retry, so proposed_skill/final_skill record the LAST
        # attempt and compare equal on 100% of shipped rows. Pair with
        # executed_skill_columns to measure initial -> executed.
        initial_extra: Dict[str, Any] = {}
        get_iflag = getattr(self.config, "get_audit_initial_proposal_columns", None)
        if callable(get_iflag) and get_iflag():
            initial_extra = {
                "initial_skill": initial_skill,
                "initial_labels": initial_labels,
                # "" marks an unparsable attempt; order is attempt 0..N.
                # Sanitized: skill_name is whatever the PARSER produced, which
                # is not yet registry-validated at this point, so it is not
                # guaranteed separator-free even though every shipped registry
                # id is.
                "attempt_skills": "|".join(
                    _sanitize_audit_segment(s) if s else ""
                    for s in (attempt_skills or [])
                ),
            }
            # Appraisal drift across retries, same gate: the final attempt's
            # labels, the per-construct change from the first attempt ("" when
            # none, or when the decision was never retried), and a bool.
            _final_labels = _extract_construct_labels(skill_proposal)
            _retried = len(attempt_skills or []) > 1
            # Only when both ends carry labels: an unparsed final attempt (or
            # a default-substituted one with no labels) is not a relabel.
            _drift = (_label_drift(initial_labels, _final_labels)
                      if _retried and _final_labels and initial_labels else "")
            initial_extra["final_labels"] = _final_labels
            initial_extra["appraisal_drift"] = _drift
            initial_extra["appraisal_drifted"] = bool(_drift)
        # Feasible set, one group per retry prompt that carried the feasible
        # line (i.e. per retry answering a parsed ERROR attempt), in order;
        # attempts that were unparsable, and the last failed attempt, have no
        # group. Key-gated by the list itself: the engine passes a list only
        # when feasible_set_feedback is on, so an off run adds no key and no
        # column. Groups are "|"-separated, skills within a group
        # ","-separated; an empty group means no skill passed.
        if feasible_by_attempt is not None:
            initial_extra["feasible_by_attempt"] = "|".join(
                ",".join(_sanitize_audit_segment(x).replace(",", ";") for x in grp)
                for grp in feasible_by_attempt
            )

        # P0-1c: ADVISORY columns, OPT-IN via global_config.audit.advise_columns
        # (default OFF). Same key-gated discipline: flag-OFF emits no key -> no row
        # key -> no new CSV fieldname -> frozen baselines byte-identical.
        advise_extra: Dict[str, Any] = {}
        get_aflag = getattr(self.config, "get_audit_advise_columns", None)
        if callable(get_aflag) and get_aflag() and advise_info:
            advise_extra = dict(advise_info)

        # PR-6: the SOFT-RULE columns. Key-gated by the channel itself rather
        # than by a second flag — `_soft_rule_pass` returns {} when the channel
        # is off, so an off run adds no keys, gains no columns, and stays
        # byte-identical without an operator having to remember two switches.
        soft_extra: Dict[str, Any] = dict(soft_advise_info or {})

        # PR-6: the GROUNDING columns. ON when the active profile declares a
        # world-grounded rule (or when the operator forces them), so a reader of
        # a grounded run can tell which of the rules that fired read the world
        # and which read the model's own labels — a distinction `rules_triggered`
        # cannot carry, since it lists ids only.
        grounding_extra: Dict[str, Any] = {}
        get_gflag = getattr(self.config, "get_audit_grounding_columns", None)
        if callable(get_gflag):
            try:
                _gon = bool(get_gflag())
            except Exception:
                _gon = False
            if _gon:
                _world, _self_report = _safe_rules_by_grounding(all_validation_history)
                grounding_extra = {
                    "rules_world_grounded": "|".join(_world),
                    "rules_self_report": "|".join(_self_report),
                }
                # PR-6 P1-a: one tally per ROW (this function runs once per audit
                # row), not per validation pass — a decision that retried three
                # times must not count three times against the row total the
                # guardrail compares with.
                _note_world_grounded_row(
                    _row_world_rules_unevaluable(all_validation_history))

        # PR-8: the DECIDER columns. ON when any agent type in the active
        # config declares a non-`llm` decider (or when forced), because at
        # that moment the CSV holds rows produced by different things and
        # nothing else in it says which is which.
        decider_extra = self._decider_audit_extra(decider)

        param_extra: Dict[str, Any] = {}
        get_pflag = getattr(self.config, "get_audit_param_columns", None)
        if (callable(get_pflag) and get_pflag()
                and skill_proposal and getattr(skill_proposal, "parameters", None)):
            for _pk, _pv in skill_proposal.parameters.items():
                if _pk in ("magnitude_pct", "magnitude_fallback"):
                    continue
                param_extra[f"proposed_param_{_pk}"] = _pv

        self.audit_writer.write_trace(agent_type_final, {
            "run_id": run_id,
            "step_id": step_id,
            "timestamp": timestamp,
            "year": env_context.get("current_year") if env_context else None,
            "seed": seed,
            "agent_id": agent_id,
            "model": getattr(self, '_model_name', 'unknown'),
            "decision_source": _classify_decision_source(approved_skill, skill_proposal),
            "validated": all_valid,
            # Phase 6G #4a: write fallback_activated at source so the audit
            # row-builder reads it directly instead of inferring from the
            # status string. REJECTED_FALLBACK = retries exhausted and the
            # registry default skill executed (genuine fallback activation).
            #
            # PR-3: that test reads the BLOCKED skill's approval status, so a
            # plain-REJECTED row records False even though the registry
            # default is precisely what the engine ran. Under
            # corrected_status_columns the flag is derived from what
            # EXECUTED, which is the question the column name asks.
            "fallback_activated": (
                bool(executed_via_fallback) if corrected else (
                    approved_skill is not None
                    and approved_skill.approval_status == "REJECTED_FALLBACK"
                )
            ),
            "_audit_priority": audit_priority,
            "input": prompt,
            "raw_output": raw_output,
            "context_hash": context_hash,
            "memory_pre": memory_pre,
            "memory_post": memory_post,
            "memory_audit": memory_audit,
            "social_audit": _safe_social_audit(context),
            # Phase 6C W8: populate rule_breakdown so audit CSV's rules_*_hit
            # columns carry real validator-category counts instead of placeholder
            # zeros. Imported lazily here to avoid a startup-time circular
            # import (governance pkg imports core types).
            # PR-3: `allow_metadata_fallback` under corrected_status_columns —
            # the production AgentValidator sets metadata["tier"], never
            # metadata["category"], so without it four of the five
            # rules_*_hit columns are zero on every row by construction.
            "rule_breakdown": _safe_rule_breakdown(
                all_validation_history, allow_metadata_fallback=corrected
            ),
            # Phase 6Q-D-3 (2026-05-26): populate `triggered_rules` so the
            # audit CSV column of the same name carries a deduped list of
            # rule IDs that fired (BLOCK + WARN). Pre-fix the schema +
            # reader existed but no producer wrote the key — `triggered_rules`
            # was always empty in the CSV. Distinct from `failed_rules`
            # which is BLOCK-only.
            "triggered_rules": _safe_triggered_rules(all_validation_history),
            "environment_context": env_context or {},
            "state_before": context.get("state", {}),
            "state_after": self._merge_state_after(context.get("state", {}), execution_result),
            "skill_proposal": skill_proposal.to_dict() if skill_proposal else None,
            "approved_skill": {
                "skill_name": approved_skill.skill_name,
                "status": approved_skill.approval_status,
                "mapping": approved_skill.execution_mapping,
            } if approved_skill else None,
            "execution_result": execution_result.__dict__ if execution_result else None,
            "outcome": outcome.value,
            "retry_count": retry_count,
            "format_retries": format_retry_count,
            "llm_stats": total_llm_stats,
            # Spread LAST (review W3): in a dict literal the last entry wins,
            # so the gated executed-truth keys take precedence — a future
            # accidental named "executed_skill" key above cannot silently
            # shadow them (spread-first would lose that collision).
            **executed_extra,
            # 6W-B6: proposed-parameter columns, spread last (same rationale).
            # compute_csv_fieldnames appends these sorted-after-priority, so the
            # frozen column order is never reordered.
            **param_extra,
            # P0-1a: first-attempt columns, spread last (same rationale).
            **initial_extra,
            # P0-1c: advisory columns, spread last (same rationale).
            **advise_extra,
            # PR-6: soft-rule + grounding columns, spread last (same rationale).
            **soft_extra,
            **grounding_extra,
            # PR-8: decider provenance, spread last (same rationale).
            **decider_extra,
        }, all_validation_history)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _merge_state_after(self, state_before: Dict[str, Any], execution_result: Optional[ExecutionResult]) -> Dict[str, Any]:
        """Approximate state-after snapshot using execution_result state changes."""
        merged = dict(state_before) if isinstance(state_before, dict) else {}
        if execution_result and getattr(execution_result, "state_changes", None):
            merged.update(execution_result.state_changes)
        return merged

    def _get_memory_snapshot(self, agent_id: str) -> List[Dict[str, Any]]:
        """Extract a structured memory snapshot for audit traces."""
        mem_engine = getattr(self.context_builder, "memory_engine", None)
        if not mem_engine and hasattr(self.context_builder, "hub"):
            mem_engine = getattr(self.context_builder.hub, "memory_engine", None)
        if not mem_engine:
            return []

        # HumanCentricMemoryEngine
        if hasattr(mem_engine, "working") and hasattr(mem_engine, "longterm"):
            working = mem_engine.working.get(agent_id, [])
            longterm = mem_engine.longterm.get(agent_id, [])
            return [m for m in working + longterm if isinstance(m, dict)]

        # WindowMemoryEngine
        if hasattr(mem_engine, "storage"):
            items = mem_engine.storage.get(agent_id, [])
            snapshot = []
            for item in items:
                if isinstance(item, dict):
                    snapshot.append(item)
                else:
                    content = str(item)
                    source = "reflection" if content.lower().startswith("reflection") else "memory"
                    snapshot.append({"content": content, "source": source})
            return snapshot

        # HierarchicalMemoryEngine
        if hasattr(mem_engine, "episodic"):
            items = mem_engine.episodic.get(agent_id, [])
            snapshot = []
            for item in items:
                if isinstance(item, dict):
                    entry = dict(item)
                    entry.setdefault("source", "episodic")
                    snapshot.append(entry)
                else:
                    snapshot.append({"content": str(item), "source": "episodic"})
            return snapshot

        return []

    def _hash_context(self, context: Dict) -> str:
        """Create hash of context for audit."""
        return hashlib.md5(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()[:16]
