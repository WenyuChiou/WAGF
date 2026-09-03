"""PR-6: world-grounded rules, framework-aware labels, and the soft-rule channel.

Three audit findings sit behind these tests, and each one is the kind that a
green suite hides rather than catches.

**F1 — self-appraisal circularity.** Every binding ERROR thinking rule in every
shipped domain conditions only on a label the model emitted in the same
generation. The rule checks one JSON object against itself: an agent that rates
the threat low is never contradicted, however often the simulated world says
otherwise. The `variable` / `expression` / `precondition` condition types
existed but no shipped rule used them, and in the AgentValidator — the only
validator the two reference domains actually run — they were not evaluated at
all. Tests here pin that a world-grounded rule fires when the world contradicts
the self-report and stays silent when the two agree.

**F2 — genericity that stops at enforcement.** `AgentValidator.get_label`
normalised every label through a hardcoded five-level alphabet and, on a miss,
truncated to two characters. Registration is generic — the frameworks registry
maps AGGRESSIVE to "A" — but enforcement was not: "AGGRESSIVE" became "AG",
matched nothing, and every `financial` rule silently never fired. A rule that
never fires and a rule that never triggers are indistinguishable in the audit
trail, which is why this survived. `test_financial_labels_truncate_and_never_
fire_with_flag_off` pins the defect deliberately, so flag-OFF reproduction of
the published corpora stays exact.

**F3 — a soft layer with no channel.** WARNING findings do not block (by
design) and did not reach the model or the audit row either, so the advisory
layer could not change anything and could not be shown to have failed to.

Every ON test is written to FAIL against pre-PR-6 code.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from broker.core._advise import (
    build_intervention_reports,
    collect_soft_findings,
    soft_finding_ids,
)
from broker.interfaces.skill_types import ValidationResult
from broker.tools.validate_prompt import check_global_config_keys
from broker.utils.agent_config import (
    AgentTypeConfig,
    resolve_rule_grounding,
    world_condition_target,
)
from broker.validators.agent.agent_validator import AgentValidator
from broker.validators.governance.thinking_validator import ThinkingValidator


# ---------------------------------------------------------------------------
# Fixtures — hand-built configs, no YAML on disk
# ---------------------------------------------------------------------------

def _config(agent_types: dict, global_config: dict | None = None) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = dict(agent_types)
    cfg._config["global_config"] = global_config or {}
    return cfg


def _validator(config: AgentTypeConfig) -> AgentValidator:
    v = AgentValidator.__new__(AgentValidator)
    v.config = config
    v.errors = []
    v.warnings = []
    from broker.utils.agent_config import GovernanceAuditor
    v.auditor = GovernanceAuditor()
    v.enable_financial_constraints = False
    getter = getattr(config, "get_validators_framework_aware_labels", None)
    v.framework_aware_labels = bool(getter()) if callable(getter) else False
    return v


# A generic hazard domain: one construct label, one world variable. Named so
# nothing here reads as a water token — broker/ tests must not smuggle a domain
# vocabulary in through their fixtures.
GROUNDED_RULE = {
    "id": "observed_event_low_appraisal_inaction",
    "grounding": "world",
    "conditions": [
        {"variable": "event_observed", "scope": "env", "operator": "is_true"},
        {"construct": "PRIMARY_LABEL", "values": ["VL", "L"]},
    ],
    "blocked_skills": ["stand_by"],
    "level": "ERROR",
    "message": "Inaction blocked: the event happened and your appraisal does not account for it.",
}

SELF_REPORT_RULE = {
    "id": "high_appraisal_no_inaction",
    "conditions": [{"construct": "PRIMARY_LABEL", "values": ["H", "VH"]}],
    "blocked_skills": ["stand_by"],
    "level": "ERROR",
}


def _grounded_config(global_config: dict | None = None) -> AgentTypeConfig:
    return _config(
        {"operator_agent": {
            "psychological_framework": "generic",
            "governance": {"default": {"thinking_rules": [GROUNDED_RULE, SELF_REPORT_RULE]}},
        }},
        global_config,
    )


def _run(validator, decision, reasoning, state=None, env=None,
         agent_type="operator_agent"):
    """Drive the thinking tier the way the broker drives it."""
    state = state or {}
    full_context = {"agent_state": {"state": state}, "env_state": env or {},
                    "agent_type": agent_type, **state, **(env or {})}
    return validator.validate_thinking(
        agent_type, "A1", decision, state, reasoning, full_context=full_context,
    )


def _ids(results):
    out = []
    for r in results:
        for h in (r.metadata.get("rules_hit") or []):
            out.append(h)
    return out


# ---------------------------------------------------------------------------
# 1. Grounding classification
# ---------------------------------------------------------------------------

def test_world_condition_target_recognises_both_yaml_shapes():
    assert world_condition_target({"variable": "x"}) == ("x", "auto")
    assert world_condition_target({"variable": "x", "scope": "state"}) == ("x", "state")
    assert world_condition_target(
        {"type": "precondition", "field": "at_capacity"}) == ("at_capacity", "auto")
    assert world_condition_target(
        {"type": "social", "field": "adoption_rate"}) == ("adoption_rate", "social")


def test_a_construct_condition_is_never_a_world_condition():
    """The self-report path must keep its exact pre-PR-6 evaluation, or every
    frozen baseline moves."""
    assert world_condition_target({"construct": "PRIMARY_LABEL", "values": ["H"]}) == (None, "")
    assert world_condition_target({"type": "construct", "field": "PRIMARY_LABEL"}) == (None, "")


def test_grounding_is_inferred_from_conditions_and_overridable():
    assert resolve_rule_grounding(SELF_REPORT_RULE) == "self_report"
    assert resolve_rule_grounding({"conditions": [{"variable": "x"}]}) == "world"
    # Prose is not an antecedent: a rule that only mentions the world in its
    # message stays self-report.
    assert resolve_rule_grounding(
        {"conditions": [{"construct": "PRIMARY_LABEL"}],
         "message": "the world flooded"}) == "self_report"
    assert resolve_rule_grounding(
        {"grounding": "self_report", "conditions": [{"variable": "x"}]}) == "self_report"


def test_config_stamps_grounding_onto_the_loaded_rules():
    rules = _grounded_config().get_thinking_rules("operator_agent")
    by_id = {r.id: r for r in rules}
    assert by_id["observed_event_low_appraisal_inaction"].grounding == "world"
    assert by_id["high_appraisal_no_inaction"].grounding == "self_report"


# ---------------------------------------------------------------------------
# 2. The grounded rule fires on contradiction, not on agreement
# ---------------------------------------------------------------------------

def test_grounded_rule_fires_when_the_world_contradicts_the_self_report():
    v = _validator(_grounded_config())
    results = _run(v, "stand_by", {"PRIMARY_LABEL": "VL"}, env={"event_observed": True})
    blocking = [r for r in results if not r.valid]
    assert [r.metadata["rule_id"] for r in blocking] == ["observed_event_low_appraisal_inaction"]
    assert blocking[0].metadata["grounding"] == "world"


def test_grounded_rule_is_silent_when_world_and_self_report_agree():
    """No event, same low appraisal, same action: nothing to contradict."""
    v = _validator(_grounded_config())
    results = _run(v, "stand_by", {"PRIMARY_LABEL": "VL"}, env={"event_observed": False})
    assert [r for r in results if not r.valid] == []


def test_grounded_rule_is_silent_when_the_appraisal_already_matches_the_world():
    """Event observed, but the agent rated the threat high — the self-report is
    not contradicted, so the grounded rule has nothing to say. The self-report
    rule handles that case, and does."""
    v = _validator(_grounded_config())
    results = _run(v, "stand_by", {"PRIMARY_LABEL": "H"}, env={"event_observed": True})
    ids = [r.metadata["rule_id"] for r in results if not r.valid]
    assert ids == ["high_appraisal_no_inaction"]
    assert [r for r in results if not r.valid][0].metadata["grounding"] == "self_report"


def test_grounded_rule_does_not_fire_when_the_world_variable_is_unreadable():
    """Fails CLOSED in the safe direction: a rule whose world antecedent cannot
    be read must not block. Blocking on evidence nobody has is worse than
    missing a violation."""
    v = _validator(_grounded_config())
    results = _run(v, "stand_by", {"PRIMARY_LABEL": "VL"}, env={})
    assert [r for r in results if not r.valid] == []


def test_an_unreadable_world_variable_is_recorded_not_silent():
    """P1-a. "Did not fire because the world says no" and "did not fire because
    the variable was never published" are the same row otherwise — and the
    second one means the grounded rule was decorative for that decision."""
    from broker.core._audit_helpers import _safe_rules_by_grounding

    v = _validator(_grounded_config())
    results = _run(v, "stand_by", {"PRIMARY_LABEL": "VL"}, env={})
    assert [r for r in results if not r.valid] == [], "unreadable must never block"
    missing = [r for r in results
               if r.metadata.get("rule_id") == "world_variable_missing"]
    assert len(missing) == 1
    assert missing[0].valid is True
    assert missing[0].metadata["field"] == "event_observed"
    assert missing[0].metadata["source_rule_id"] == "observed_event_low_appraisal_inaction"
    assert missing[0].metadata["grounding"] == "world"
    world, _self_report = _safe_rules_by_grounding([results])
    assert "world_variable_missing" in world


def test_a_readable_world_variable_records_no_missing_finding():
    v = _validator(_grounded_config())
    results = _run(v, "stand_by", {"PRIMARY_LABEL": "VL"},
                   env={"event_observed": True})
    assert [r.metadata.get("rule_id") for r in results] == [
        "observed_event_low_appraisal_inaction"]


def test_a_row_is_unevaluable_only_when_no_grounded_rule_could_be_read():
    """P1-a. A row where one grounded rule fired and another was unreadable is a
    row with a gap, not an unevaluable row. Only a row where NO grounded rule
    could be evaluated is indistinguishable from a self-report-only run's."""
    from broker.core._audit_helpers import _row_world_rules_unevaluable

    v = _validator(_grounded_config())
    unevaluable = _run(v, "stand_by", {"PRIMARY_LABEL": "VL"}, env={})
    assert _row_world_rules_unevaluable([unevaluable]) is True
    readable = _run(v, "stand_by", {"PRIMARY_LABEL": "VL"},
                    env={"event_observed": True})
    assert _row_world_rules_unevaluable([readable]) is False
    assert _row_world_rules_unevaluable([]) is False


def test_a_missing_world_variable_on_the_thinkingvalidator_plane_warns_once(caplog):
    """P2 (PR-6 review). ``ThinkingValidator`` (reached only through
    ``validate_all`` / ``build_domain_validators`` — "available architecture,
    not the production default") gets none of the AgentValidator plane's
    grounding-observability apparatus: no ``world_variable_missing`` finding,
    no run-integrity census entry. A missing world variable there silently
    makes the condition not match, same as before P1-a existed on the other
    plane. DECISION: not a second census — a deduped ``logger.warning`` at the
    miss site instead, firing once per ``(rule_id, variable)`` per process."""
    import logging

    from broker.validators.governance import thinking_validator as tv_module

    tv = tv_module.ThinkingValidator(framework="", builtin_checks=[])
    cond = {"variable": "event_observed", "scope": "env", "operator": "is_true"}
    context = {"env_state": {}, "state": {}, "social_context": {}}

    key_a = ("observed_event_rule", "event_observed")
    key_b = ("observed_event_rule", "other_var")
    tv_module._WARNED_MISSING_WORLD_VARIABLE.discard(key_a)
    tv_module._WARNED_MISSING_WORLD_VARIABLE.discard(key_b)
    try:
        with caplog.at_level(logging.WARNING, logger=tv_module.__name__):
            matched = tv._evaluate_single_condition(
                cond, reasoning={}, context=context, framework="",
                rule_id="observed_event_rule")
            assert matched is False, "unreadable must never match (fail closed)"
            first = [r for r in caplog.records if "event_observed" in r.getMessage()]
            assert len(first) == 1

            caplog.clear()
            tv._evaluate_single_condition(
                cond, reasoning={}, context=context, framework="",
                rule_id="observed_event_rule")
            repeat = [r for r in caplog.records if "event_observed" in r.getMessage()]
            assert repeat == [], "dedup must suppress the repeat warning"

            # A different (rule_id, variable) key is not deduped against the first.
            caplog.clear()
            tv._evaluate_single_condition(
                {"variable": "other_var", "scope": "env", "operator": "is_true"},
                reasoning={}, context=context, framework="",
                rule_id="observed_event_rule")
            different_key = [r for r in caplog.records if "other_var" in r.getMessage()]
            assert len(different_key) == 1
    finally:
        tv_module._WARNED_MISSING_WORLD_VARIABLE.discard(key_a)
        tv_module._WARNED_MISSING_WORLD_VARIABLE.discard(key_b)


def test_a_run_whose_world_rules_were_never_evaluable_is_flagged(tmp_path):
    """P1-a. Such a run's audit CSV is identical to a self-report-only run's, so
    without the guardrail nothing anywhere says the grounded profile was
    decorative."""
    from broker.core.run_integrity import (
        note_world_grounded_row, record_run_integrity,
        reset_world_rule_evaluability,
    )

    reset_world_rule_evaluability()
    try:
        for _ in range(3):
            note_world_grounded_row(True)
        audit = record_run_integrity(tmp_path, verbose=False)
        assert audit["world_grounded_rows"] == 3
        assert audit["world_rules_unevaluable_rows"] == 3
        assert audit["integrity_ok"] is False
    finally:
        reset_world_rule_evaluability()


def test_a_run_with_one_evaluable_row_is_not_flagged(tmp_path):
    from broker.core.run_integrity import (
        note_world_grounded_row, record_run_integrity,
        reset_world_rule_evaluability,
    )

    reset_world_rule_evaluability()
    try:
        note_world_grounded_row(True)
        note_world_grounded_row(True)
        note_world_grounded_row(False)
        audit = record_run_integrity(tmp_path, verbose=False)
        assert audit["world_rules_unevaluable_rows"] == 2
        assert audit["integrity_ok"] is True
    finally:
        reset_world_rule_evaluability()


def test_aborted_sentinel_rows_do_not_mask_the_guardrail(tmp_path):
    """P1-a falsification. The denominator must be the world-grounded TALLY
    (`world_grounded_rows`), not `audit_rows` from the CSV — an aborted
    sentinel row (status ABORTED / ABORTED_EXCEPTION, written by
    `ExperimentRunner._write_aborted_trace` when a step raises) bypasses
    `AuditMixin._write_audit_trace` entirely and never reaches
    `note_world_grounded_row()`. 9 rows go through the tally, all
    unevaluable; a 10th row is an aborted sentinel the tally never saw
    (`audit_rows == 10`). Before the fix, `_denominator = audit.get(
    "audit_rows") or _wg_rows` picked 10, and `9 == 10` is False — a single
    aborted agent-year silently disabled the flag even though every row the
    tally DID see was unevaluable."""
    import csv as csv_module

    from broker.core.run_integrity import (
        note_world_grounded_row, record_run_integrity,
        reset_world_rule_evaluability,
    )

    csv_path = tmp_path / "household_governance_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv_module.DictWriter(fh, fieldnames=["agent_id", "year", "status"])
        writer.writeheader()
        for i in range(9):
            writer.writerow({"agent_id": f"H{i:04d}", "year": 1, "status": "APPROVED"})
        writer.writerow({"agent_id": "H0009", "year": 1, "status": "ABORTED_EXCEPTION"})

    reset_world_rule_evaluability()
    try:
        for _ in range(9):
            note_world_grounded_row(True)
        audit = record_run_integrity(tmp_path, verbose=False)
        assert audit["audit_rows"] == 10
        assert audit["audit_aborted_rows"] == 1
        assert audit["world_grounded_rows"] == 9
        assert audit["world_rules_unevaluable_rows"] == 9

        # Falsify against the PRE-FIX line: `audit.get("audit_rows") or
        # _wg_rows` resolves to 10 (truthy), and 9 == 10 is False — the
        # guardrail would NOT have fired on this exact data.
        _pre_fix_denominator = audit.get("audit_rows") or audit["world_grounded_rows"]
        assert _pre_fix_denominator == 10
        _pre_fix_flagged = bool(audit["world_rules_unevaluable_rows"]) and (
            audit["world_rules_unevaluable_rows"] == _pre_fix_denominator
        )
        assert _pre_fix_flagged is False

        # POST-FIX: the denominator is the tally itself, so the guardrail
        # correctly fires, and the coverage gap is 0 (the one non-tallied
        # row is fully explained by the aborted-sentinel exclusion).
        assert audit["integrity_ok"] is False
        assert audit["world_grounded_coverage_gap"] == 0
    finally:
        reset_world_rule_evaluability()


def test_coverage_gap_is_null_not_a_false_alarm_on_a_non_grounded_run(tmp_path):
    """P1-a. ``note_world_grounded_row()`` is called from exactly one site
    (``broker/core/_audit_helpers.py``), gated behind
    ``AgentTypeConfig.get_audit_grounding_columns()`` — OFF for every
    non-grounded (default) profile. On such a run ``world_grounded_rows`` is
    0 for its ENTIRE duration by design, not because of a coverage hole.
    Comparing it against ``audit_rows`` without accounting for this would
    report every ordinary completed row as "missing" and warn on every
    default-profile run in the fleet — verified against a real flood run
    with the flag off before this gate was added. The gap must read ``None``
    (unmeasured), not the row count, whenever the tally never ran at all."""
    import csv as csv_module

    from broker.core.run_integrity import (
        record_run_integrity, reset_world_rule_evaluability,
    )

    csv_path = tmp_path / "household_governance_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv_module.DictWriter(fh, fieldnames=["agent_id", "year", "status"])
        writer.writeheader()
        for i in range(15):
            writer.writerow({"agent_id": f"H{i:04d}", "year": 1, "status": "APPROVED"})

    reset_world_rule_evaluability()
    try:
        # No note_world_grounded_row() calls at all — the non-grounded-profile
        # shape. world_grounded_rows stays 0 for the whole run.
        audit = record_run_integrity(tmp_path, verbose=False)
        assert audit["world_grounded_rows"] == 0
        assert audit["audit_rows"] == 15
        assert audit["world_grounded_coverage_gap"] is None, (
            "must not report all 15 ordinary rows as a coverage hole merely "
            "because grounding columns were off for this run"
        )
        assert audit["integrity_ok"] is True
    finally:
        reset_world_rule_evaluability()


def test_grounded_rule_only_blocks_the_skills_it_names():
    v = _validator(_grounded_config())
    results = _run(v, "take_action", {"PRIMARY_LABEL": "VL"}, env={"event_observed": True})
    assert [r for r in results if not r.valid] == []


@pytest.mark.parametrize("operator,value,actual,expected_block", [
    (">", 0.4, 0.9, True),
    (">", 0.4, 0.1, False),
    ("<=", 0.4, 0.4, True),
    ("in", None, "severe", True),
    ("not_in", None, "severe", False),
    ("==", 3, 3, True),
    ("!=", 3, 3, False),
])
def test_world_condition_operators(operator, value, actual, expected_block):
    cond = {"variable": "load", "scope": "env", "operator": operator}
    if operator in ("in", "not_in"):
        cond["values"] = ["severe", "extreme"]
    else:
        cond["value"] = value
    rule = {"id": "r", "grounding": "world", "conditions": [cond],
            "blocked_skills": ["stand_by"], "level": "ERROR"}
    v = _validator(_config({"operator_agent": {
        "governance": {"default": {"thinking_rules": [rule]}}}}))
    results = _run(v, "stand_by", {"PRIMARY_LABEL": "M"}, env={"load": actual})
    assert bool([r for r in results if not r.valid]) is expected_block


def test_a_boolean_flag_is_not_matched_by_a_numeric_one():
    """`== true` against a numeric 1.0 must NOT match, or a rule written to read
    a flag silently starts reading a magnitude."""
    rule = {"id": "r", "conditions": [
        {"variable": "flag", "scope": "env", "operator": "==", "value": True}],
        "blocked_skills": ["stand_by"], "level": "ERROR"}
    v = _validator(_config({"operator_agent": {
        "governance": {"default": {"thinking_rules": [rule]}}}}))
    assert [r for r in _run(v, "stand_by", {}, env={"flag": 1.0}) if not r.valid] == []
    assert [r for r in _run(v, "stand_by", {}, env={"flag": True}) if not r.valid] != []


def test_scope_disambiguates_a_name_carried_by_both_planes():
    """The broker builds its validation context as {**agent_state, **env}, so a
    name in both resolves to the env copy and the agent's own value becomes
    unreachable. `scope:` is the fix, and this pins it."""
    def rule_for(scope):
        return {"id": f"r_{scope}", "conditions": [
            {"variable": "level", "scope": scope, "operator": ">", "value": 5}],
            "blocked_skills": ["stand_by"], "level": "ERROR"}

    v = _validator(_config({"operator_agent": {"governance": {"default": {
        "thinking_rules": [rule_for("state")]}}}}))
    blocked = [r for r in _run(v, "stand_by", {}, state={"level": 9},
                               env={"level": 1}) if not r.valid]
    assert [r.metadata["rule_id"] for r in blocked] == ["r_state"]

    v = _validator(_config({"operator_agent": {"governance": {"default": {
        "thinking_rules": [rule_for("env")]}}}}))
    assert [r for r in _run(v, "stand_by", {}, state={"level": 9},
                            env={"level": 1}) if not r.valid] == []


def test_missing_full_context_leaves_the_grounded_rule_inert():
    """Direct callers that predate PR-6 pass no context. The rule must go quiet,
    not raise inside a validator and take a whole batch down."""
    v = _validator(_grounded_config())
    results = v.validate_thinking(
        "operator_agent", "A1", "stand_by", {}, {"PRIMARY_LABEL": "VL"})
    assert [r for r in results if not r.valid] == []


# ---------------------------------------------------------------------------
# 3. The shipped strict profiles are untouched by the grounded profile
# ---------------------------------------------------------------------------

FROZEN_STRICT_RULE_SHAPES = {
    "examples/single_agent/agent_types.yaml": (
        "household",
        [("extreme_threat_block", "ERROR", "self_report"),
         ("low_coping_block", "WARNING", "self_report"),
         ("relocation_threat_low", "ERROR", "self_report"),
         ("elevation_threat_low", "ERROR", "self_report")],
    ),
    "examples/irrigation_abm/config/agent_types.yaml": (
        "irrigation_farmer",
        [("high_threat_no_maintain", "WARNING", "self_report"),
         ("low_threat_no_increase", "ERROR", "self_report"),
         ("high_threat_high_cope_no_increase", "ERROR", "self_report")],
    ),
}


@pytest.mark.parametrize("path", sorted(FROZEN_STRICT_RULE_SHAPES))
def test_strict_profile_rule_set_is_unchanged_by_the_grounded_addition(path, monkeypatch):
    """The grounded profile is ADDITIVE. If adding it had edited `strict` — the
    profile every published run used — the corpora would silently stop
    reproducing, and the CSV would not say so."""
    from pathlib import Path
    agent_type, expected = FROZEN_STRICT_RULE_SHAPES[path]
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("GOVERNANCE_PROFILE", "strict")
    config = AgentTypeConfig.load(str(repo_root / path))
    rules = config.get_thinking_rules(agent_type)
    assert [(r.id, r.level, r.grounding) for r in rules] == expected


@pytest.mark.parametrize("path", sorted(FROZEN_STRICT_RULE_SHAPES))
def test_grounded_profile_adds_exactly_one_world_grounded_rule(path, monkeypatch):
    from pathlib import Path
    agent_type, strict_expected = FROZEN_STRICT_RULE_SHAPES[path]
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("GOVERNANCE_PROFILE", "grounded_v1")
    config = AgentTypeConfig.load(str(repo_root / path))
    rules = config.get_thinking_rules(agent_type)
    world = [r for r in rules if r.grounding == "world"]
    assert len(world) == 1
    assert world[0].level == "ERROR"
    # every strict rule survives, verbatim
    shapes = [(r.id, r.level, r.grounding) for r in rules]
    assert shapes[:len(strict_expected)] == strict_expected
    assert config.get_audit_grounding_columns() is True


@pytest.mark.parametrize("path", sorted(FROZEN_STRICT_RULE_SHAPES))
def test_strict_profile_gains_no_grounding_columns(path, monkeypatch):
    """The auto-on rule must stay off for a self-report-only profile — that is
    what keeps the frozen CSVs byte-identical without a second flag."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("GOVERNANCE_PROFILE", "strict")
    config = AgentTypeConfig.load(str(repo_root / path))
    assert config.get_audit_grounding_columns() is False


# ---------------------------------------------------------------------------
# 4. F2 — framework-aware labels
# ---------------------------------------------------------------------------

FINANCIAL_RULE = {
    "id": "aggressive_no_hold",
    "conditions": [{"construct": "RISK_APPETITE", "values": ["AGGRESSIVE"]}],
    "blocked_skills": ["hold_position"],
    "level": "ERROR",
}


def _financial_config(flag: bool) -> AgentTypeConfig:
    return _config(
        {"trader": {
            "psychological_framework": "financial",
            "governance": {"default": {"thinking_rules": [FINANCIAL_RULE]}},
        }},
        {"validators": {"framework_aware_labels": flag}} if flag else {},
    )


def test_financial_labels_truncate_and_never_fire_with_flag_off():
    """PINS THE DEFECT. "AGGRESSIVE" is normalised to "AG", which is in no
    registered alphabet, so the rule cannot fire. Deliberate: flag-OFF must
    reproduce the published behaviour exactly, defects included."""
    v = _validator(_financial_config(False))
    results = v.validate_thinking(
        "trader", "T1", "hold_position", {}, {"RISK_APPETITE": "AGGRESSIVE"},
        full_context={},
    )
    assert [r for r in results if not r.valid] == []


def test_financial_labels_match_under_the_flag():
    v = _validator(_financial_config(True))
    results = v.validate_thinking(
        "trader", "T1", "hold_position", {}, {"RISK_APPETITE": "AGGRESSIVE"},
        full_context={},
    )
    assert [r.metadata["rule_id"] for r in results if not r.valid] == ["aggressive_no_hold"]


def test_financial_conservative_label_does_not_match_the_aggressive_rule():
    """The flag must resolve the alphabet, not merely make everything match."""
    v = _validator(_financial_config(True))
    results = v.validate_thinking(
        "trader", "T1", "hold_position", {}, {"RISK_APPETITE": "CONSERVATIVE"},
        full_context={},
    )
    assert [r for r in results if not r.valid] == []


def test_five_level_domains_behave_identically_under_the_flag():
    """Turning the flag on must not move a PMT-style domain: the flag fixes a
    resolution bug, it does not redefine the common alphabet."""
    for flag in (False, True):
        cfg = _config(
            {"operator_agent": {
                "psychological_framework": "generic",
                "governance": {"default": {"thinking_rules": [SELF_REPORT_RULE]}},
            }},
            {"validators": {"framework_aware_labels": flag}},
        )
        v = _validator(cfg)
        blocked = [r for r in _run(v, "stand_by", {"PRIMARY_LABEL": "VERY HIGH"})
                   if not r.valid]
        assert [r.metadata["rule_id"] for r in blocked] == ["high_appraisal_no_inaction"]


# ---------------------------------------------------------------------------
# 5. Missing constructs — one documented rule under the flag
# ---------------------------------------------------------------------------

def test_missing_construct_is_silent_and_unrecorded_with_flag_off():
    """Legacy AgentValidator behaviour: `get_label` returns "", the rule does
    not fire, and the row is indistinguishable from one where the rule was
    evaluated and passed."""
    v = _validator(_grounded_config())
    results = _run(v, "stand_by", {"OTHER": "H"}, env={"event_observed": True})
    assert results == []


def test_missing_construct_does_not_fire_and_is_recorded_under_the_flag():
    v = _validator(_grounded_config({"validators": {"framework_aware_labels": True}}))
    results = _run(v, "stand_by", {"OTHER": "H"}, env={"event_observed": True})
    assert [r for r in results if not r.valid] == [], "a missing construct must never block"
    findings = [r for r in results if r.metadata.get("rule_id") == "construct_missing"]
    assert len(findings) == 1
    assert findings[0].valid is True
    assert findings[0].metadata["field"] == "PRIMARY_LABEL"
    assert "No middle value was assumed" in findings[0].warnings[0]


def test_blank_construct_counts_as_missing_under_the_flag():
    v = _validator(_grounded_config({"validators": {"framework_aware_labels": True}}))
    results = _run(v, "stand_by", {"PRIMARY_LABEL": "   "}, env={"event_observed": True})
    assert [r for r in results if not r.valid] == []
    assert [r.metadata["rule_id"] for r in results] == ["construct_missing"]


def _yaml_rule(rule_id="medium_blocks"):
    """A YAML-shaped rule: dict conditions, which is what `_validate_yaml_rules`
    reads. Exercised directly rather than through `validate`, whose step-1 path
    evaluates the same rule again through a different evaluator."""
    return SimpleNamespace(
        id=rule_id, category="thinking", subcategory="", framework=None,
        blocked_skills=["stand_by"], level="ERROR", message="blocked",
        conditions=[{"construct": "PRIMARY_LABEL", "operator": "in", "values": ["M"]}],
    )


def test_thinking_validator_fabricates_medium_with_flag_off():
    """PINS THE THIRD LEGACY SEMANTICS. An unreported construct is scored as
    MEDIUM, so a rule written for `values: ["M"]` FIRES on a decision whose
    construct the model never emitted. Published behaviour; stays reproducible."""
    tv = ThinkingValidator(framework="", builtin_checks=[])
    results = tv._validate_yaml_rules("stand_by", [_yaml_rule()], {"reasoning": {}}, "")
    assert [r.metadata["rule_id"] for r in results if not r.valid] == ["medium_blocks"]


def test_thinking_validator_records_construct_missing_under_the_flag():
    tv = ThinkingValidator(framework="", builtin_checks=[], framework_aware_labels=True)
    results = tv._validate_yaml_rules("stand_by", [_yaml_rule()], {"reasoning": {}}, "")
    assert [r for r in results if not r.valid] == []
    assert [r.metadata["rule_id"] for r in results] == ["construct_missing"]


def test_thinking_validator_stamps_grounding_on_a_world_conditioned_rule():
    rule = _yaml_rule("world_rule")
    rule.conditions = [{"variable": "event_observed", "scope": "env",
                        "operator": "==", "value": True}]
    tv = ThinkingValidator(framework="", builtin_checks=[])
    results = tv._validate_yaml_rules(
        "stand_by", [rule], {"reasoning": {}, "env_state": {"event_observed": True}}, "")
    assert [r.metadata["grounding"] for r in results] == ["world"]


def test_rule_condition_reads_the_env_plane():
    """`RuleCondition` already returned None -> no-fire for a missing value, so
    it needed no flag. It DID read only `context["state"]`, so a precondition
    naming an env variable resolved to None and the rule silently never fired."""
    from broker.governance.rule_types import RuleCondition
    cond = RuleCondition(type="precondition", field="event_observed",
                         operator="==", values=[True])
    assert cond.evaluate({"env_state": {"event_observed": True}, "state": {}}) is True
    assert cond.evaluate({"state": {}}) is False


# ---------------------------------------------------------------------------
# 6. F3 — the soft-rule channel
# ---------------------------------------------------------------------------

def _warning_result(rule_id="soft_rule", text="consider adapting"):
    return ValidationResult(
        valid=True, validator_name="AgentValidator:thinking_warning",
        errors=[], warnings=[text],
        metadata={"rule_id": rule_id, "rules_hit": [rule_id], "level": "WARNING"},
    )


def _error_result(rule_id="hard_rule"):
    return ValidationResult(
        valid=False, validator_name="AgentValidator:thinking_error",
        errors=["blocked"], warnings=[],
        metadata={"rule_id": rule_id, "rules_hit": [rule_id], "level": "ERROR"},
    )


def test_advise_mode_getter_default_and_values():
    assert _config({}).get_governance_advise_mode() == "off"
    assert _config({}, {"governance": {"advise_mode": "record"}}
                   ).get_governance_advise_mode() == "record"
    assert _config({}, {"governance": {"advise_mode": "FEEDBACK"}}
                   ).get_governance_advise_mode() == "feedback"


def test_advise_mode_refuses_an_unknown_value():
    """Reading a typo as `off` would produce a run with no soft-rule record and
    nothing anywhere saying the channel was requested."""
    with pytest.raises(ValueError, match="advise_mode"):
        _config({}, {"governance": {"advise_mode": "on"}}).get_governance_advise_mode()


def test_collect_soft_findings_ignores_blocking_and_demoted_results():
    demoted = _warning_result("demoted")
    demoted.metadata["disposition"] = "ADVISE"
    results = [_error_result(), _warning_result("soft_a"), demoted]
    assert soft_finding_ids(results) == ["thinking:soft_a"]
    assert len(collect_soft_findings(results)) == 1


def test_shadow_converted_results_are_never_soft_findings():
    """P0. Shadow mode converts a BLOCKING result into an observe-only one and
    records it in its own `shadow_blocked` column. Reading it here would show a
    rule the operator asked to merely observe as advice — and under `feedback`
    would feed a suppressed ENFORCEMENT rule back to the model, turning a shadow
    arm into a quiet advice arm with nothing in the row saying so."""
    shadow = _warning_result("shadow_rule", "would have blocked this")
    shadow.metadata["shadow_blocked"] = ["shadow_rule"]
    shadow.metadata["would_block_level"] = "ERROR"
    assert collect_soft_findings([shadow]) == []
    assert soft_finding_ids([shadow]) == []


def test_shadow_mode_plus_feedback_issues_no_advisory_call():
    e = _Engine("feedback")
    shadow = _warning_result("shadow_rule", "would have blocked this")
    shadow.metadata["shadow_blocked"] = ["shadow_rule"]
    _p, _r, _res, _v, info = _soft_call(e, [shadow])
    assert e.prompts == [], "a shadow arm must not become an advice arm"
    assert info["advise_shown"] is False
    assert "shadow_rule" not in info["advise_findings"]


def test_a_warning_with_no_rule_id_is_counted_not_shown():
    """C2. Including an id-less warning produced `advise_shown=True` with
    `advise_findings=""` — an advisory call was made, the model was told
    something, and the row named nothing."""
    anonymous = ValidationResult(
        valid=True, validator_name="AgentValidator:thinking_warning",
        errors=[], warnings=["a bound was exceeded"], metadata={"level": "WARNING"},
    )
    assert collect_soft_findings([anonymous]) == []
    e = _Engine("feedback")
    _p, _r, _res, _v, info = _soft_call(e, [anonymous])
    assert info["advise_findings"] == ""
    assert info["advise_shown"] is False
    assert info["soft_findings_unidentified"] == 1
    assert e.prompts == [], "nothing nameable to advise about means no call"


def test_findings_are_prefixed_with_their_validator_category():
    """P2. One cell carries findings from several tiers; without the prefix a
    reader cannot tell which layer produced which id."""
    social = _warning_result("norm_drift", "neighbours disagree")
    social.validator_name = "SocialValidator"
    missing = _warning_result("construct_missing", "not reported")
    missing.metadata["field"] = "TP_LABEL"
    assert soft_finding_ids([_warning_result("low_coping_block"), social, missing]) == [
        "construct_missing:TP_LABEL", "social:norm_drift", "thinking:low_coping_block",
    ]


def test_an_unrecognised_producer_is_named_unknown_not_guessed():
    odd = _warning_result("mystery_rule")
    odd.validator_name = "SomeThirdPartyValidator"
    assert soft_finding_ids([odd]) == ["unknown:mystery_rule"]


def test_warning_reports_carry_the_rule_text():
    reports = build_intervention_reports(
        [_warning_result("soft_a", "consider adapting")],
        SimpleNamespace(skill_name="stand_by"),
        source="warnings", severity="ADVICE",
    )
    assert [r.rule_id for r in reports] == ["soft_a"]
    assert reports[0].violation_summary == "consider adapting"
    assert reports[0].severity == "ADVICE"


class _Adapter:
    """Minimal ModelAdapter stand-in that records what it was asked to render."""

    def __init__(self):
        self.rendered = []

    def format_retry_prompt(self, prompt, reports, max_reports=None):
        text = prompt + "\n[ADVICE]\n" + "\n".join(
            getattr(r, "violation_summary", str(r)) for r in reports)
        self.rendered.append(text)
        return text

    def parse_output(self, raw, ctx):
        return SimpleNamespace(skill_name=raw, magnitude_pct=None, parameters={},
                               reasoning={}, parse_layer="test")


class _Engine:
    """The soft-rule pass, exercised on the mixin alone."""

    from broker.core._advise_pass import AdviseMixin
    _soft_rule_pass = AdviseMixin._soft_rule_pass

    def __init__(self, mode, revised="take_action"):
        self._soft_advise_mode = mode
        self._intervention_framing = "legacy"
        self.max_reports = 3
        self.model_adapter = _Adapter()
        self.prompts = []
        self.revised = revised
        self.revalidated = 0

    def _run_validators(self, proposal, context):
        self.revalidated += 1
        return []

    def llm_invoke(self, prompt):
        self.prompts.append(prompt)
        return self.revised


def _soft_call(engine, results, all_valid=True, proposal_name="stand_by",
               total_llm_stats=None, attempt_skills=None):
    proposal = SimpleNamespace(skill_name=proposal_name, magnitude_pct=None,
                               parameters={}, reasoning={})
    history = []
    engine.last_history = history
    engine.last_stats = {} if total_llm_stats is None else total_llm_stats
    engine.last_attempts = attempt_skills
    return engine._soft_rule_pass(
        all_valid=all_valid, skill_proposal=proposal, validation_results=results,
        all_validation_history=history, validation_context={},
        prompt="ORIGINAL PROMPT", llm_invoke=engine.llm_invoke, context={},
        agent_id="A1", agent_type="operator_agent", env_context={},
        raw_output="", total_llm_stats=engine.last_stats,
        attempt_skills=attempt_skills,
    )


def test_advise_mode_off_touches_nothing():
    e = _Engine("off")
    proposal, raw, results, all_valid, info = _soft_call(e, [_warning_result()])
    assert info == {}, "an off channel must add NO audit keys, or the CSV gains a column"
    assert e.prompts == []
    assert proposal.skill_name == "stand_by"


def test_advise_mode_record_audits_the_finding_and_never_calls_the_model():
    e = _Engine("record")
    proposal, raw, results, all_valid, info = _soft_call(e, [_warning_result("soft_a")])
    assert info["soft_advise_mode"] == "record"
    assert info["advise_findings"] == "thinking:soft_a"
    assert info["advise_shown"] is False
    assert info["advise_executed_stage"] == "pre"
    assert e.prompts == [], "record must be provably incapable of changing behaviour"
    assert proposal.skill_name == "stand_by"


def test_advise_mode_feedback_shows_the_advice_without_blocking():
    e = _Engine("feedback", revised="take_action")
    proposal, raw, results, all_valid, info = _soft_call(
        e, [_warning_result("soft_a", "consider adapting")])
    # (a) the proposal was never blocked
    assert all_valid is True
    # (b) the advice text reached the next prompt
    assert len(e.prompts) == 1
    assert "consider adapting" in e.prompts[0]
    assert e.prompts[0].startswith("ORIGINAL PROMPT")
    # (c) the audit columns say what happened
    assert info["advise_shown"] is True
    assert info["advise_reports_shown"] == 1
    assert info["advise_findings"] == "thinking:soft_a"
    assert info["advise_skill_before"] == "stand_by"
    assert info["advise_skill_after"] == "take_action"
    assert info["advise_executed_stage"] == "post"
    assert info["advise_post_validation_invalid"] is False
    assert proposal.skill_name == "take_action"


def test_advise_mode_feedback_records_but_does_not_show_when_a_hard_rule_blocks():
    """With an ERROR outstanding the retry loop is about to re-prompt anyway.
    Adding an advisory call first would mix the two channels inside one decision
    and make the contrast unreadable, so the finding is recorded and
    `advise_shown` says plainly that the model was not told."""
    e = _Engine("feedback")
    _p, _r, _res, _v, info = _soft_call(
        e, [_error_result(), _warning_result("soft_a")], all_valid=False)
    assert info["advise_findings"] == "thinking:soft_a"
    assert info["advise_shown"] is False
    assert e.prompts == []


def test_advise_mode_feedback_keeps_the_proposal_when_the_advice_is_unparsable():
    e = _Engine("feedback")
    e.model_adapter.parse_output = lambda raw, ctx: None
    proposal, _raw, _res, _valid, info = _soft_call(e, [_warning_result("soft_a")])
    assert proposal.skill_name == "stand_by"
    assert info["advise_shown"] is True, (
        "the model WAS shown the advice; that stays true whatever came back"
    )
    assert info["advise_skill_after"] == "stand_by"


class _Stats:
    """LLMStats stand-in carrying the fields the token accounting reads."""
    retries = 1
    success = True
    prompt_tokens = 120
    response_tokens = 40
    num_ctx = 8192
    context_utilization = 0.42


def test_advice_never_opens_the_retry_loop_even_when_the_reply_is_invalid():
    """W1. The soft channel must hold BLOCKING constant. Returning the
    post-advice `all_valid` would let a soft rule open the governance retry loop
    through the back door — the channel would block after all, on exactly the
    decisions where advice mattered most."""
    e = _Engine("feedback", revised="take_action")
    e._run_validators = lambda proposal, ctx: [_error_result("post_rule")]
    proposal, _raw, results, all_valid, info = _soft_call(e, [_warning_result("soft_a")])
    # status stays APPROVED: blocking is exactly what it would have been
    assert all_valid is True
    # the PRE-advice proposal executes, and the row says which stage that was
    assert proposal.skill_name == "stand_by"
    assert info["advise_executed_stage"] == "pre"
    assert info["advise_skill_before"] == "stand_by"
    assert info["advise_skill_after"] == "take_action"
    # ...and the discarded proposal's failure is recorded, not smoothed away
    assert info["advise_post_validation_invalid"] is True
    assert info["advise_post_validation_rules"] == "post_rule"
    # the executed proposal's own results come back, not the discarded ones
    assert [r.metadata["rule_id"] for r in results] == ["soft_a"]
    # the post-advice results are still in the decision's history
    assert [r.metadata["rule_id"] for r in e.last_history] == ["post_rule"]


def test_a_valid_post_advice_proposal_is_adopted_and_marked_post():
    e = _Engine("feedback", revised="take_action")
    proposal, _raw, _res, all_valid, info = _soft_call(e, [_warning_result("soft_a")])
    assert all_valid is True
    assert proposal.skill_name == "take_action"
    assert info["advise_executed_stage"] == "post"
    assert info["advise_post_validation_invalid"] is False
    assert info["advise_post_validation_rules"] == ""


def test_advise_shown_follows_the_renderer_not_the_intention():
    """P1-d. `advise_shown` was asserted True before delivery. An adapter that
    dropped every report sends a prompt carrying NO advice, and claiming the
    model was shown advice it never saw is the one thing this column exists to
    stop."""
    class _DropsEverything(_Adapter):
        def format_intervention_prompt(self, prompt, reports, max_reports=None,
                                       framing="legacy", include_reports=True):
            self.rendered.append(prompt)
            return prompt, 0

    e = _Engine("feedback")
    e.model_adapter = _DropsEverything()
    _p, _r, _res, _v, info = _soft_call(e, [_warning_result("soft_a")])
    assert info["advise_shown"] is False
    assert info["advise_reports_shown"] == 0
    assert e.prompts == ["ORIGINAL PROMPT"], "the call still happened"


def test_the_advisory_call_tokens_are_accounted():
    """P1-d. The advisory prompt is the LONGEST in the decision, so excluding it
    under-reports peak context pressure on precisely the decisions where advice
    fired — and under-reports the arm's token cost against the `record` arm it
    exists to be compared with."""
    e = _Engine("feedback")
    e.llm_invoke = lambda prompt: ("take_action", _Stats())
    stats = {"llm_calls": 0, "llm_retries": 0, "prompt_tokens": 5,
             "response_tokens": 2, "context_utilization": 0.1, "num_ctx": 4096}
    _soft_call(e, [_warning_result("soft_a")], total_llm_stats=stats)
    assert stats["llm_calls"] == 1
    assert stats["llm_retries"] == 1
    assert stats["prompt_tokens"] == 125
    assert stats["response_tokens"] == 42
    assert stats["num_ctx"] == 8192
    assert stats["context_utilization"] == 0.42


def test_a_raised_advisory_call_records_the_attempt_and_the_failure():
    """P1-d. The attempt HAPPENED; omitting it shortens `attempt_skills`, so a
    reader counting attempts under-counts exactly the decisions where the
    advisory call failed."""
    def _boom(prompt):
        raise RuntimeError("provider down")

    e = _Engine("feedback")
    e.llm_invoke = _boom
    attempts = ["stand_by"]
    proposal, _raw, _res, all_valid, info = _soft_call(
        e, [_warning_result("soft_a")], attempt_skills=attempts)
    assert attempts == ["stand_by", None]
    assert info["advise_parse_failed"] is True
    assert info["advise_executed_stage"] == "pre"
    assert proposal.skill_name == "stand_by"
    assert all_valid is True


def test_an_unparsable_reply_sets_the_parse_failed_flag():
    e = _Engine("feedback")
    e.model_adapter.parse_output = lambda raw, ctx: None
    _p, _r, _res, _v, info = _soft_call(e, [_warning_result("soft_a")])
    assert info["advise_parse_failed"] is True
    assert info["advise_executed_stage"] == "pre"


def test_soft_info_key_does_not_collide_with_the_p0_1c_arm_payload():
    """Both dicts are spread into the same trace. A shared `advise_mode` key
    would let this channel overwrite the arm's recorded mode — the one column an
    analyst uses to tell the arms apart."""
    from broker.core._advise_pass import _blank_info, _blank_soft_info
    assert set(_blank_info()) & set(_blank_soft_info("record")) == set()


def test_the_flag_reaches_BOTH_condition_evaluators(monkeypatch):
    """P1-b. The flag was half-wired: AgentValidator read it from its own
    config, the dispatcher never passed it. Under the flag the two then answered
    a missing construct DIFFERENTLY on the same decision — one recorded
    `construct_missing` and did not fire, the other assumed "M" and fired."""
    from broker.components.governance.domain_validator_dispatch import (
        build_domain_validators,
    )

    cfg = _financial_config(True)
    monkeypatch.setattr(AgentTypeConfig, "_instance", cfg, raising=False)
    thinking = [v for v in build_domain_validators(None)
                if isinstance(v, ThinkingValidator)]
    assert thinking, "the dispatcher must build a ThinkingValidator"
    assert all(t.framework_aware_labels is True for t in thinking)
    assert _validator(cfg).framework_aware_labels is True


def test_the_flag_defaults_off_in_the_dispatcher(monkeypatch):
    from broker.components.governance.domain_validator_dispatch import (
        build_domain_validators,
    )

    monkeypatch.setattr(AgentTypeConfig, "_instance", _financial_config(False),
                        raising=False)
    thinking = [v for v in build_domain_validators(None)
                if isinstance(v, ThinkingValidator)]
    assert all(t.framework_aware_labels is False for t in thinking)


def test_an_explicit_dispatcher_flag_beats_the_ambient_config(monkeypatch):
    """A caller holding the run's own config must be able to say so, rather than
    depend on which config was loaded last in the process."""
    from broker.components.governance.domain_validator_dispatch import (
        build_domain_validators,
    )

    monkeypatch.setattr(AgentTypeConfig, "_instance", _financial_config(False),
                        raising=False)
    thinking = [v for v in build_domain_validators(None, framework_aware_labels=True)
                if isinstance(v, ThinkingValidator)]
    assert all(t.framework_aware_labels is True for t in thinking)


def test_build_domain_validators_config_beats_a_mid_run_reload(monkeypatch):
    """P2 (PR-6 review). `AgentTypeConfig._instance` is the most-recently-
    loaded config PROCESS-WIDE — `broker/components/context/tiered.py` and
    `broker/components/response_format.py` both call
    `load_agent_config(other_path)` on paths unrelated to the run in
    progress. Two distinct configs loaded, in order: the run's own engine is
    built on config_a (first); a mid-run reload on an unrelated path then
    makes config_b the ambient global. The engine's own AgentValidator reads
    config_a directly and is unaffected; the dispatcher must see config_a too
    when handed it explicitly, not silently read whichever config happens to
    be loaded last."""
    from broker.components.governance.domain_validator_dispatch import (
        build_domain_validators,
    )

    config_a = _financial_config(True)   # what the run's engine was built on
    config_b = _financial_config(False)  # loaded LATER, by an unrelated path

    monkeypatch.setattr(AgentTypeConfig, "_instance", config_b, raising=False)

    # Both evaluators see the FIRST config's flag value (True), not the
    # ambient global's (False).
    assert _validator(config_a).framework_aware_labels is True
    thinking = [v for v in build_domain_validators(None, config=config_a)
                if isinstance(v, ThinkingValidator)]
    assert thinking, "the dispatcher must build a ThinkingValidator"
    assert all(t.framework_aware_labels is True for t in thinking)

    # Falsification: omitting config= (the pre-fix call shape) resolves
    # against the ambient global instead, and disagrees.
    pre_fix_thinking = [v for v in build_domain_validators(None)
                         if isinstance(v, ThinkingValidator)]
    assert all(t.framework_aware_labels is False for t in pre_fix_thinking)


def test_validate_all_threads_config_through_to_the_dispatcher(monkeypatch):
    """P2. `validate_all` must pass its own `config` argument down to
    `build_domain_validators` rather than dropping it — the same class of
    silent-drop the Phase 6T-B fix already closed for `agent_type`. Verified
    by spying on the dispatcher import site itself (`validate_all` imports
    `build_domain_validators` function-locally, so the spy is installed on
    the dispatch module, not on `broker.validators.governance`)."""
    import broker.components.governance.domain_validator_dispatch as dispatch_module
    from broker.governance.rule_types import GovernanceRule
    from broker.validators.governance import validate_all

    config_a = _financial_config(True)
    captured: dict = {}
    real_build = dispatch_module.build_domain_validators

    def _spy(*args, **kwargs):
        captured["kwargs"] = kwargs
        return real_build(*args, **kwargs)

    monkeypatch.setattr(dispatch_module, "build_domain_validators", _spy)

    validate_all(
        "hold_position", [GovernanceRule.from_dict(FINANCIAL_RULE)],
        {"reasoning": {"RISK_APPETITE": "AGGRESSIVE"}, "state": {}, "social_context": {}},
        domain=None, config=config_a,
    )

    assert captured["kwargs"].get("config") is config_a


def test_an_unresolvable_framework_fails_loud_under_the_flag():
    """P2. The old `except Exception: framework = ""` ran every label rule
    against the generic alphabet instead, so rules written for the framework's
    labels matched nothing — and a rule that never fires leaves the same audit
    trail as a rule that is never violated."""
    cfg = _financial_config(True)

    def _boom(agent_type):
        raise KeyError("psychological_framework")

    cfg.get_framework_for_agent_type = _boom
    v = _validator(cfg)
    with pytest.raises(ValueError, match="framework_aware_labels"):
        v.validate_thinking("trader", "T1", "hold_position", {},
                            {"RISK_APPETITE": "AGGRESSIVE"}, full_context={})


def test_an_unresolvable_framework_is_harmless_with_the_flag_off():
    """The fail-loud is scoped to the opt-in flag: a frozen run must keep
    reproducing whatever its config accessor does."""
    cfg = _financial_config(False)

    def _boom(agent_type):
        raise KeyError("psychological_framework")

    cfg.get_framework_for_agent_type = _boom
    v = _validator(cfg)
    assert v.validate_thinking("trader", "T1", "hold_position", {},
                               {"RISK_APPETITE": "AGGRESSIVE"}, full_context={}) == []


# ---------------------------------------------------------------------------
# 5b. Identity rules are world-grounded (P1-f)
# ---------------------------------------------------------------------------

IDENTITY_RULE = {
    "id": "already_done",
    "precondition": "action_already_taken",
    "blocked_skills": ["take_action"],
    "level": "ERROR",
    "message": "Already taken.",
}


def test_identity_rules_are_classified_world_grounded(monkeypatch):
    """P1-f. An identity rule tests simulator state the model cannot author, so
    it always was world-grounded — nothing stamped it, and every identity block
    landed in `rules_self_report`, where a count of self-report blocks silently
    included physical constraints.

    The profile is pinned because ``get_identity_rules`` — unlike
    ``get_thinking_rules`` — has NO fallback to the ``default`` block, so it
    returns nothing at all under a leaked ``GOVERNANCE_PROFILE``.
    """
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    assert resolve_rule_grounding(IDENTITY_RULE) == "world"
    cfg = _config({"operator_agent": {
        "governance": {"default": {"identity_rules": [IDENTITY_RULE]}}}})
    assert cfg.get_identity_rules("operator_agent")[0].grounding == "world"


def test_a_fired_identity_rule_lands_in_the_world_grounded_column(monkeypatch):
    from broker.core._audit_helpers import _safe_rules_by_grounding

    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    cfg = _config({"operator_agent": {
        "governance": {"default": {"identity_rules": [IDENTITY_RULE]}}}})
    v = _validator(cfg)
    results = v.validate_identity("operator_agent", "A1", "take_action",
                                  {"action_already_taken": True})
    assert [r.metadata["rule_id"] for r in results] == ["already_done"]
    assert results[0].metadata["grounding"] == "world"
    assert _safe_rules_by_grounding([results]) == (["already_done"], [])


def test_grounding_metadata_reaches_no_existing_audit_column():
    """Flag-OFF byte identity: `grounding` is additive metadata. The CSV plane
    reads rule ids, and the JSONL issue block copies only the terminal-taxonomy
    subset, so a stamped result must not gain a cell anywhere."""
    from broker.components.analytics.audit import trace_to_csv_row

    base = {"step_id": "1", "agent_id": "A1", "skill_proposal": None,
            "approved_skill": None, "llm_stats": {}}
    row = trace_to_csv_row(base)
    assert not [k for k in row if "grounding" in k]


# ---------------------------------------------------------------------------
# 6b. Config-time and runtime scope handling (W5) + memoisation (W6)
# ---------------------------------------------------------------------------

def _scoped_rule(scope):
    return {"id": "r", "conditions": [
        {"variable": "event_observed", "scope": scope, "operator": "is_true"}],
        "blocked_skills": ["stand_by"], "level": "ERROR"}


def test_validate_prompt_rejects_an_unrecognised_condition_scope():
    """W5. An unrecognised scope is COERCED to `auto`, which searches env first —
    so `scope: environment` appears to work until the agent's own state carries
    the same name, and then the rule reads the wrong plane in silence."""
    from broker.tools.validate_prompt import check_world_condition_scopes

    cfg = {"operator_agent": {"governance": {
        "default": {"thinking_rules": [_scoped_rule("environment")]}}}}
    issues = check_world_condition_scopes(cfg)
    assert [i.severity for i in issues] == ["ERROR"]
    assert "environment" in issues[0].message


def test_validate_prompt_accepts_every_documented_scope():
    from broker.tools.validate_prompt import check_world_condition_scopes
    from broker.utils.agent_config import WORLD_CONDITION_SCOPES

    for scope in sorted(WORLD_CONDITION_SCOPES):
        cfg = {"operator_agent": {"governance": {
            "default": {"thinking_rules": [_scoped_rule(scope)]}}}}
        assert check_world_condition_scopes(cfg) == []


def test_the_shipped_configs_declare_only_recognised_scopes():
    from pathlib import Path

    import yaml

    from broker.tools.validate_prompt import (
        check_rule_shapes, check_world_condition_scopes,
    )
    repo_root = Path(__file__).resolve().parents[2]
    for path in sorted(FROZEN_STRICT_RULE_SHAPES):
        cfg = yaml.safe_load((repo_root / path).read_text(encoding="utf-8"))
        assert check_world_condition_scopes(cfg) == [], path
        # The PR-6 condition keys must not read as silently-dead YAML either.
        assert check_rule_shapes(cfg) == [], path


def test_scope_coercion_warns_once(caplog):
    import logging

    from broker.utils import agent_config as ac

    ac._WARNED_UNKNOWN_SCOPES.clear()
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert world_condition_target(
                {"variable": "event_observed", "scope": "environment"}
            ) == ("event_observed", "auto")
    hits = [r for r in caplog.records if "not one of" in r.getMessage()]
    assert len(hits) == 1, "per-condition per-step warning would be pure noise"
    ac._WARNED_UNKNOWN_SCOPES.clear()


def test_has_world_grounded_rules_is_memoised_per_profile(monkeypatch):
    """W6. Called once per audit ROW on the frozen default path, and each call
    re-parsed every thinking rule of every agent type."""
    cfg = _grounded_config()
    calls = []
    original = cfg.get_thinking_rules

    def _counting(agent_type):
        calls.append(agent_type)
        return original(agent_type)

    cfg.get_thinking_rules = _counting
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    assert cfg.has_world_grounded_rules() is True
    first = len(calls)
    assert first >= 1
    for _ in range(20):
        assert cfg.has_world_grounded_rules() is True
    assert len(calls) == first, "the answer cannot change while the profile does not"
    # A different profile is a different answer, so it must re-scan.
    monkeypatch.setenv("GOVERNANCE_PROFILE", "other")
    cfg.has_world_grounded_rules()
    assert len(calls) > first


def test_declared_governance_profiles_reads_both_shapes_and_skips_global_config():
    """P1-e's helper. `global_config` carries a `governance:` block of SETTINGS,
    not profiles — counting its keys would offer `max_retries` as an arm."""
    from broker.utils.agent_config import declared_governance_profiles

    cfg = {
        "global_config": {"governance": {"max_retries": 3}},
        "operator_agent": {"governance": {"strict": {}, "grounded_v1": {}}},
        "governance": {"top_level_profile": {"operator_agent": {}}},
    }
    assert declared_governance_profiles(cfg, "operator_agent") == {
        "strict", "grounded_v1", "top_level_profile"}
    assert declared_governance_profiles(cfg, "someone_else") == set()
    assert declared_governance_profiles(None) == set()


@pytest.mark.parametrize("path", sorted(FROZEN_STRICT_RULE_SHAPES))
def test_the_shipped_configs_declare_the_profiles_their_runners_offer(path):
    """The runner assertion is only as good as this: a config that stopped
    declaring `grounded_v1` would make every `--governance-mode grounded_v1`
    invocation refuse to start, which is the point."""
    from pathlib import Path

    import yaml

    from broker.utils.agent_config import declared_governance_profiles
    agent_type, _ = FROZEN_STRICT_RULE_SHAPES[path]
    repo_root = Path(__file__).resolve().parents[2]
    cfg = yaml.safe_load((repo_root / path).read_text(encoding="utf-8"))
    declared = declared_governance_profiles(cfg, agent_type)
    assert {"strict", "grounded_v1", "disabled"} <= declared


# ---------------------------------------------------------------------------
# 7. Audit plumbing
# ---------------------------------------------------------------------------

def test_grounding_split_separates_world_from_self_report():
    from broker.core._audit_helpers import _safe_rules_by_grounding
    world = ValidationResult(
        valid=False, validator_name="v", errors=["x"],
        metadata={"rules_hit": ["grounded_rule"], "grounding": "world"})
    plain = ValidationResult(
        valid=False, validator_name="v", errors=["x"],
        metadata={"rules_hit": ["label_rule"], "grounding": "self_report"})
    unmarked = ValidationResult(
        valid=False, validator_name="v", errors=["x"],
        metadata={"rules_hit": ["legacy_rule"]})
    assert _safe_rules_by_grounding([[world, plain, unmarked]]) == (
        ["grounded_rule"], ["label_rule", "legacy_rule"])


def test_grounding_split_never_raises():
    from broker.core._audit_helpers import _safe_rules_by_grounding
    assert _safe_rules_by_grounding(None) == ([], [])
    assert _safe_rules_by_grounding([[object()]]) == ([], [])


def test_grounding_columns_appear_only_when_the_key_is_present():
    """Key-gated exactly like every other opt-in column group: no key, no
    column, so a flag-OFF trace keeps the frozen fieldname set."""
    from broker.components.analytics.audit import trace_to_csv_row
    base = {"step_id": "1", "agent_id": "A1", "skill_proposal": None,
            "approved_skill": None, "llm_stats": {}}
    assert "rules_world_grounded" not in trace_to_csv_row(base)
    row = trace_to_csv_row({**base, "rules_world_grounded": "r1",
                            "rules_self_report": "r2"})
    assert row["rules_world_grounded"] == "r1"
    assert row["rules_self_report"] == "r2"


def test_soft_advise_columns_appear_only_when_the_key_is_present():
    from broker.components.analytics.audit import trace_to_csv_row
    base = {"step_id": "1", "agent_id": "A1", "skill_proposal": None,
            "approved_skill": None, "llm_stats": {}}
    assert "advise_findings" not in trace_to_csv_row(base)
    from broker.core._advise_pass import _blank_soft_info
    row = trace_to_csv_row({**base, **_blank_soft_info("record"),
                            "advise_findings": "thinking:soft_a"})
    assert row["advise_findings"] == "thinking:soft_a"
    assert row["soft_advise_mode"] == "record"
    # Every key the channel emits must reach a column, or a reader loses the
    # column that tells them what happened to the advice.
    for key in _blank_soft_info("record"):
        assert key in row, f"{key} is emitted by the channel but has no column"


# ---------------------------------------------------------------------------
# 8. Config-time checks
# ---------------------------------------------------------------------------

def _issues(global_config):
    return check_global_config_keys({"global_config": global_config})


def test_validate_prompt_accepts_the_new_keys():
    issues = _issues({
        "validators": {"framework_aware_labels": True},
        "governance": {"advise_mode": "feedback"},
        "audit": {"grounding_columns": True},
    })
    assert [i for i in issues] == []


def test_validate_prompt_warns_on_a_typo_in_each_new_block():
    assert any("framework_aware_label" in i.message
               for i in _issues({"validators": {"framework_aware_label": True}}))
    assert any("advise_modes" in i.message
               for i in _issues({"governance": {"advise_modes": "record"}}))
    assert any("grounding_column" in i.message
               for i in _issues({"audit": {"grounding_column": True}}))


def test_validate_prompt_rejects_an_unknown_advise_mode():
    issues = _issues({"governance": {"advise_mode": "on"}})
    assert any(i.severity == "ERROR" and "advise_mode" in i.message for i in issues)
