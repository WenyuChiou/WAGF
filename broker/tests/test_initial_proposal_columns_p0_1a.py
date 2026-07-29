"""P0-1a (2026-07-29): opt-in FIRST-ATTEMPT proposal audit columns.

The proposal-stage gap: ``skill_proposal`` is REASSIGNED on every governance
retry (``_retry_loop._governance_retry_loop``), so both the CSV's
``proposed_skill`` and the JSONL's ``skill_proposal`` record the LAST
(post-retry) attempt. Measured over the shipped corpus,
``proposed_skill == final_skill`` on 100% of rows in all three reference
domains despite heavy retrying — which makes any "governance changed the
action" metric defined as proposed != final identically zero.

The fix is three ADDITIVE columns — ``initial_skill`` / ``initial_labels`` /
``attempt_skills`` — gated by
``global_config.audit.initial_proposal_columns`` (default OFF).

Byte-safety contract under test: with the flag OFF (default), the keys never
enter the trace dict, so neither the JSONL nor the row-key-derived CSV
fieldnames change — frozen v21 / paper-3 mock reruns stay byte-identical.
"""
from __future__ import annotations

from types import SimpleNamespace

from broker.components.analytics.audit import (
    compute_csv_fieldnames,
    trace_to_csv_row,
)
from broker.core._audit_helpers import AuditMixin, _extract_construct_labels
from broker.interfaces.skill_types import SkillOutcome
from broker.utils.agent_config import AgentTypeConfig


# ---------------------------------------------------------------------------
# Config getter
# ---------------------------------------------------------------------------

def _cfg(global_config=None) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": global_config or {}}
    return cfg


def test_getter_default_off():
    assert _cfg().get_audit_initial_proposal_columns() is False
    assert _cfg({"audit": {}}).get_audit_initial_proposal_columns() is False


def test_getter_explicit_on():
    assert _cfg(
        {"audit": {"initial_proposal_columns": True}}
    ).get_audit_initial_proposal_columns() is True


def test_getter_non_dict_audit_block_is_off():
    # A malformed scalar block must read as OFF, never raise.
    assert _cfg({"audit": "yes"}).get_audit_initial_proposal_columns() is False


def test_getter_independent_of_executed_flag():
    # The two opt-ins are orthogonal; enabling one must not enable the other.
    cfg = _cfg({"audit": {"initial_proposal_columns": True}})
    assert cfg.get_audit_initial_proposal_columns() is True
    assert cfg.get_audit_executed_columns() is False


# ---------------------------------------------------------------------------
# Construct-label extraction
# ---------------------------------------------------------------------------

def test_extract_labels_picks_only_label_keys_in_order():
    proposal = SimpleNamespace(reasoning={
        "reasoning": "prose that must not appear",
        "WSA_LABEL": "H",
        "WSA_REASON": "also excluded",
        "ACA_LABEL": "VH",
    })
    assert _extract_construct_labels(proposal) == "WSA_LABEL=H|ACA_LABEL=VH"


def test_extract_labels_sanitizes_separators_in_values():
    """An off-vocabulary label value must not be able to corrupt the field.

    normalize_construct_value returns the RAW LLM string unchanged when it
    matches no known vocabulary, so a value containing '|' or '=' can reach the
    audit path. Substituting (not dropping) keeps the record unambiguous for a
    downstream .split('|') / .split('=').
    """
    proposal = SimpleNamespace(reasoning={
        "WSA_LABEL": "H|VH",          # pipe inside a value
        "ACA_LABEL": "score=0.8",     # equals inside a value
    })
    out = _extract_construct_labels(proposal)
    assert out == "WSA_LABEL=H/VH|ACA_LABEL=score:0.8"
    # The field still splits into exactly one pair per label.
    pairs = [seg.split("=") for seg in out.split("|")]
    assert [len(p) for p in pairs] == [2, 2]
    assert [p[0] for p in pairs] == ["WSA_LABEL", "ACA_LABEL"]


def test_attempt_skills_sanitizes_separators():
    # skill_name comes straight from the parser and is NOT registry-validated
    # at the point the audit row is built, so it is not guaranteed clean.
    trace = _write(
        _Host(flag=True),
        attempt_skills=["increase|large", "decrease_small"],
    )
    assert trace["attempt_skills"] == "increase/large|decrease_small"
    assert len(trace["attempt_skills"].split("|")) == 2


def test_extract_labels_degrades_quietly():
    # None proposal, non-dict reasoning, and a label-free proposal must all
    # return "" rather than raise — this runs on the audit path, where an
    # exception would lose the whole decision record.
    assert _extract_construct_labels(None) == ""
    assert _extract_construct_labels(SimpleNamespace(reasoning=None)) == ""
    assert _extract_construct_labels(SimpleNamespace(reasoning="oops")) == ""
    assert _extract_construct_labels(SimpleNamespace()) == ""
    assert _extract_construct_labels(SimpleNamespace(reasoning={"a": 1})) == ""


# ---------------------------------------------------------------------------
# Flattener key-gating (the byte-identity mechanism)
# ---------------------------------------------------------------------------

_BASE_TRACE = {
    "step_id": "Y1",
    "agent_id": "A1",
    "approved_skill": {"skill_name": "do_nothing", "status": "REJECTED"},
    "skill_proposal": {"skill_name": "elevate"},
}


def test_row_without_keys_has_no_initial_columns():
    row = trace_to_csv_row(dict(_BASE_TRACE))
    for col in ("initial_skill", "initial_labels", "attempt_skills"):
        assert col not in row
        assert col not in compute_csv_fieldnames([row])


def test_row_with_keys_carries_proposal_stage_truth():
    t = dict(_BASE_TRACE)
    t["initial_skill"] = "increase_large"
    t["initial_labels"] = "WSA_LABEL=H|ACA_LABEL=VH"
    t["attempt_skills"] = "increase_large|increase_small|decrease_small"
    row = trace_to_csv_row(t)
    assert row["initial_skill"] == "increase_large"
    assert row["initial_labels"] == "WSA_LABEL=H|ACA_LABEL=VH"
    assert row["attempt_skills"] == "increase_large|increase_small|decrease_small"
    fieldnames = compute_csv_fieldnames([row])
    for col in ("initial_skill", "initial_labels", "attempt_skills"):
        assert col in fieldnames


def test_the_defect_this_closes_is_visible_in_the_row():
    """Reproduce the shipped-corpus shape and show the new column recovers it.

    In every shipped run, ``skill_proposal`` has already been overwritten by
    the last retry, so the flattened row shows proposed_skill == final_skill
    even though the agent's FIRST choice was different and was blocked. That
    degenerate equality is what makes a proposed!=final intervention metric
    read as identically zero.
    """
    t = {
        "step_id": "Y1",
        "agent_id": "A1",
        # Post-retry state as actually recorded on disk: the proposal object
        # and the approved skill are the same, hence proposed == final.
        "skill_proposal": {"skill_name": "decrease_small"},
        "approved_skill": {"skill_name": "decrease_small", "status": "REJECTED"},
    }
    degenerate = trace_to_csv_row(dict(t))
    assert degenerate["proposed_skill"] == degenerate["final_skill"] == "decrease_small"

    # With the flag ON the first attempt survives, so the action change the
    # governance layer caused is measurable again.
    t["initial_skill"] = "increase_large"
    t["attempt_skills"] = "increase_large|increase_small|decrease_small"
    row = trace_to_csv_row(t)
    assert row["initial_skill"] == "increase_large"
    assert row["initial_skill"] != row["final_skill"]
    assert row["attempt_skills"].split("|")[0] == row["initial_skill"]
    assert row["attempt_skills"].split("|")[-1] == row["final_skill"]


# ---------------------------------------------------------------------------
# AuditMixin gating (trace-level: keys present IFF flag ON)
# ---------------------------------------------------------------------------

class _StubWriter:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history):
        self.traces.append((agent_type, trace))


class _Host(AuditMixin):
    def __init__(self, flag: bool):
        self.audit_writer = _StubWriter()
        self.config = SimpleNamespace(
            get_log_fields=lambda agent_type: [],
            get_audit_initial_proposal_columns=lambda: flag,
        )


def _write(host: _Host, **overrides) -> dict:
    approved = SimpleNamespace(
        skill_name="decrease_small",
        approval_status="REJECTED",
        execution_mapping={},
    )
    kwargs = dict(
        initial_skill="increase_large",
        initial_labels="WSA_LABEL=H|ACA_LABEL=VH",
        attempt_skills=["increase_large", "increase_small", "decrease_small"],
    )
    kwargs.update(overrides)
    host._write_audit_trace(
        agent_type="irrigation_farmer", context={}, run_id="r", step_id="Y1",
        timestamp="t", env_context={}, seed=42, agent_id="A1",
        all_valid=False, prompt="p", raw_output="o", context_hash="h",
        memory_pre=[], memory_post=[], skill_proposal=None,
        approved_skill=approved, execution_result=None,
        outcome=SkillOutcome.REJECTED, retry_count=3,
        format_retry_count=0, total_llm_stats={},
        all_validation_history=[],
        **kwargs,
    )
    assert len(host.audit_writer.traces) == 1
    return host.audit_writer.traces[0][1]


def test_mixin_flag_off_keys_absent_from_trace():
    trace = _write(_Host(flag=False))
    for col in ("initial_skill", "initial_labels", "attempt_skills"):
        assert col not in trace


def test_mixin_flag_on_keys_present_and_joined():
    trace = _write(_Host(flag=True))
    assert trace["initial_skill"] == "increase_large"
    assert trace["initial_labels"] == "WSA_LABEL=H|ACA_LABEL=VH"
    assert trace["attempt_skills"] == "increase_large|increase_small|decrease_small"


def test_mixin_flag_on_unparsable_attempt_marked_empty():
    # None entries (unparsable attempts) must survive as empty segments so the
    # index of each attempt is preserved, not silently compacted away.
    trace = _write(
        _Host(flag=True),
        attempt_skills=["increase_large", None, "decrease_small"],
    )
    assert trace["attempt_skills"] == "increase_large||decrease_small"


def test_mixin_flag_on_tolerates_missing_initial_proposal():
    trace = _write(
        _Host(flag=True),
        initial_skill=None, initial_labels="", attempt_skills=[None],
    )
    assert trace["initial_skill"] is None
    assert trace["initial_labels"] == ""
    assert trace["attempt_skills"] == ""


def test_mixin_host_without_getter_stays_off():
    # A config object predating this flag must not raise (getattr guard).
    host = _Host(flag=False)
    host.config = SimpleNamespace(get_log_fields=lambda agent_type: [])
    trace = _write(host)
    assert "initial_skill" not in trace


# ---------------------------------------------------------------------------
# END-TO-END: the wiring through a real process_step + governance retry.
# The unit tests above only prove the audit layer gates correctly; this proves
# the engine actually captures attempt 0 before _governance_retry_loop
# overwrites skill_proposal, which is the whole point of P0-1a.
# ---------------------------------------------------------------------------

def _e2e_engine(flag: bool, writer):
    from unittest.mock import MagicMock

    from broker.components.governance.registry import SkillRegistry
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.interfaces.skill_types import (
        SkillDefinition, SkillProposal, ValidationResult,
    )

    registry = SkillRegistry()
    for sid in ("increase_large", "decrease_small"):
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))

    # Attempt 0 proposes increase_large; every retry proposes decrease_small.
    proposals = iter([
        SkillProposal(skill_name="increase_large", agent_id="A1",
                      reasoning={"WSA_LABEL": "H", "ACA_LABEL": "VH"},
                      parse_layer="mock"),
        SkillProposal(skill_name="decrease_small", agent_id="A1",
                      reasoning={"WSA_LABEL": "H", "ACA_LABEL": "M"},
                      parse_layer="mock"),
    ])
    last = {"p": None}

    def _parse(_raw, _ctx):
        try:
            last["p"] = next(proposals)
        except StopIteration:
            pass
        return last["p"]

    adapter = MagicMock()
    adapter.parse_output.side_effect = _parse
    adapter.format_retry_prompt.return_value = "retry prompt"

    # Block exactly the first proposal, mirroring high_threat_high_cope_no_increase.
    def _validate(proposal, _ctx, _registry=None):
        blocked = getattr(proposal, "skill_name", None) == "increase_large"
        return ValidationResult(
            valid=not blocked,
            validator_name="thinking_error",
            errors=["Demand increase BLOCKED"] if blocked else [],
            metadata={"rules_hit": ["high_threat_high_cope_no_increase"]} if blocked else {},
        )

    validator = MagicMock()
    validator.validate.side_effect = _validate

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_audit_initial_proposal_columns.return_value = flag
    config.get_audit_executed_columns.return_value = flag
    config.get_multi_skill_config.return_value = {}
    config.get_governance_retries.return_value = 3
    config.get_governance_max_reports.return_value = 3

    engine = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=None, context_builder=MockCtx(), config=config,
    )
    engine.audit_writer = writer
    return engine


class MockCtx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "prompt"


def test_e2e_first_attempt_survives_the_retry_loop():
    writer = _StubWriter()
    engine = _e2e_engine(flag=True, writer=writer)
    engine.process_step(
        agent_id="A1", step_id=1, run_id="r", seed=42,
        llm_invoke=lambda p: "raw", agent_type="irrigation_farmer",
    )
    assert writer.traces, "no audit trace written"
    trace = writer.traces[0][1]

    # Attempt 0 is preserved even though skill_proposal was reassigned.
    assert trace["initial_skill"] == "increase_large"
    assert trace["initial_labels"] == "WSA_LABEL=H|ACA_LABEL=VH"
    # The recorded post-retry proposal is the LAST one — the degenerate signal.
    assert trace["skill_proposal"]["skill_name"] == "decrease_small"
    # ...so initial != final is now measurable, which it was not before.
    assert trace["initial_skill"] != trace["skill_proposal"]["skill_name"]
    # Every attempt is ordered, first-to-last.
    attempts = trace["attempt_skills"].split("|")
    assert attempts[0] == "increase_large"
    assert attempts[-1] == "decrease_small"
    assert len(attempts) == trace["retry_count"] + 1


def test_e2e_early_exit_preserves_the_index_invariant():
    """EarlyExit breaks out of the loop mid-iteration — the invariant must hold.

    When the same DETERMINISTIC rule set blocks two consecutive attempts the
    loop breaks early. The append happens before that break, so
    len(attempt_skills) == retry_count + 1 must still hold; if the append were
    ever moved after the branch, this test fails and the attempt index silently
    stops lining up with retry_count.
    """
    from unittest.mock import MagicMock

    from broker.components.governance.registry import SkillRegistry
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.interfaces.skill_types import (
        SkillDefinition, SkillProposal, ValidationResult,
    )

    registry = SkillRegistry()
    registry.register(SkillDefinition(
        skill_id="increase_large", description="x", eligible_agent_types=["*"],
        preconditions=[], institutional_constraints={},
        allowed_state_changes=[], implementation_mapping="increase_large",
    ))

    adapter = MagicMock()
    adapter.parse_output.side_effect = lambda *_a, **_k: SkillProposal(
        skill_name="increase_large", agent_id="A1",
        reasoning={"WSA_LABEL": "H"}, parse_layer="mock",
    )
    adapter.format_retry_prompt.return_value = "retry prompt"

    # Always blocked, always the SAME rule, flagged deterministic -> EarlyExit
    # fires on the first retry.
    validator = MagicMock()
    validator.validate.side_effect = lambda *_a, **_k: ValidationResult(
        valid=False, validator_name="affordability",
        errors=["cannot afford"],
        metadata={"rules_hit": ["affordability"], "deterministic": True},
    )

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_audit_initial_proposal_columns.return_value = True
    config.get_audit_executed_columns.return_value = False
    config.get_multi_skill_config.return_value = {}
    config.get_governance_retries.return_value = 3
    config.get_governance_max_reports.return_value = 3

    writer = _StubWriter()
    engine = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=None, context_builder=MockCtx(), config=config,
    )
    engine.audit_writer = writer
    engine.process_step(
        agent_id="A1", step_id=1, run_id="r", seed=42,
        llm_invoke=lambda p: "raw", agent_type="irrigation_farmer",
    )

    trace = writer.traces[0][1]
    attempts = trace["attempt_skills"].split("|")
    # EarlyExit must have stopped us short of the 3-retry ceiling...
    assert trace["retry_count"] < 3, "EarlyExit did not fire; test is not exercising the branch"
    # ...and the index invariant must survive the break.
    assert len(attempts) == trace["retry_count"] + 1


def test_e2e_flag_off_emits_no_new_keys():
    """Byte-identity guard at the engine level, not just the mixin."""
    writer = _StubWriter()
    engine = _e2e_engine(flag=False, writer=writer)
    engine.process_step(
        agent_id="A1", step_id=1, run_id="r", seed=42,
        llm_invoke=lambda p: "raw", agent_type="irrigation_farmer",
    )
    trace = writer.traces[0][1]
    for col in ("initial_skill", "initial_labels", "attempt_skills"):
        assert col not in trace
