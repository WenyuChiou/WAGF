"""F3 (2026-06-10 audit review): opt-in EXECUTED-stage audit columns.

The REJECTED-row gap: on REJECTED the engine executes the registry default
skill as fallback, but the CSV records the BLOCKED proposal as ``final_skill``
and plain-REJECTED rows keep ``fallback_activated=False`` (only
REJECTED_FALLBACK sets it). The fix is two ADDITIVE columns —
``executed_skill`` + ``executed_via_fallback`` — gated by
``global_config.audit.executed_skill_columns`` (default OFF).

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
from broker.core._audit_helpers import AuditMixin
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
    assert _cfg().get_audit_executed_columns() is False
    assert _cfg({"audit": {}}).get_audit_executed_columns() is False


def test_getter_explicit_on():
    assert _cfg(
        {"audit": {"executed_skill_columns": True}}
    ).get_audit_executed_columns() is True


def test_getter_non_dict_audit_block_is_off():
    # A malformed scalar block must read as OFF, never raise.
    assert _cfg({"audit": "yes"}).get_audit_executed_columns() is False


# ---------------------------------------------------------------------------
# Flattener key-gating (the byte-identity mechanism)
# ---------------------------------------------------------------------------

_BASE_TRACE = {
    "step_id": "Y1",
    "agent_id": "A1",
    "approved_skill": {"skill_name": "do_nothing", "status": "REJECTED"},
    "skill_proposal": {"skill_name": "elevate"},
}


def test_row_without_keys_has_no_executed_columns():
    row = trace_to_csv_row(dict(_BASE_TRACE))
    assert "executed_skill" not in row
    assert "executed_via_fallback" not in row
    # and therefore the derived fieldnames cannot contain them
    assert "executed_skill" not in compute_csv_fieldnames([row])


def test_row_with_keys_carries_executed_truth():
    t = dict(_BASE_TRACE)
    t["executed_skill"] = "do_nothing"
    t["executed_via_fallback"] = True
    row = trace_to_csv_row(t)
    assert row["executed_skill"] == "do_nothing"
    assert row["executed_via_fallback"] is True
    fieldnames = compute_csv_fieldnames([row])
    assert "executed_skill" in fieldnames
    assert "executed_via_fallback" in fieldnames


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
            get_audit_executed_columns=lambda: flag,
        )


def _write(host: _Host) -> dict:
    approved = SimpleNamespace(
        skill_name="elevate",
        approval_status="REJECTED",
        execution_mapping={},
    )
    host._write_audit_trace(
        agent_type="household", context={}, run_id="r", step_id="Y1",
        timestamp="t", env_context={}, seed=42, agent_id="A1",
        all_valid=False, prompt="p", raw_output="o", context_hash="h",
        memory_pre=[], memory_post=[], skill_proposal=None,
        approved_skill=approved, execution_result=None,
        outcome=SkillOutcome.REJECTED, retry_count=2,
        format_retry_count=0, total_llm_stats={},
        all_validation_history=[],
        executed_skill="do_nothing", executed_via_fallback=True,
    )
    assert len(host.audit_writer.traces) == 1
    return host.audit_writer.traces[0][1]


def test_mixin_flag_off_keys_absent_from_trace():
    trace = _write(_Host(flag=False))
    assert "executed_skill" not in trace
    assert "executed_via_fallback" not in trace


def test_mixin_flag_on_keys_present_in_trace():
    trace = _write(_Host(flag=True))
    assert trace["executed_skill"] == "do_nothing"
    assert trace["executed_via_fallback"] is True
    # the lie the columns correct: final_skill still records the BLOCKED
    # proposal — both facts must coexist on the same trace.
    assert trace["approved_skill"]["skill_name"] == "elevate"
    assert trace["fallback_activated"] is False  # plain REJECTED, by design


def test_mixin_uncertain_parse_failure_path_is_consistent():
    """UNCERTAIN (parse-failure -> REJECTED_FALLBACK status): BOTH flags are
    True together — fallback_activated from the approval status, and
    executed_via_fallback from the execution branch. Internally consistent,
    unlike the plain-REJECTED case where they deliberately diverge."""
    host = _Host(flag=True)
    approved = SimpleNamespace(
        skill_name="do_nothing",
        approval_status="REJECTED_FALLBACK",
        execution_mapping={},
    )
    host._write_audit_trace(
        agent_type="household", context={}, run_id="r", step_id="Y1",
        timestamp="t", env_context={}, seed=42, agent_id="A1",
        all_valid=False, prompt="p", raw_output="garbage", context_hash="h",
        memory_pre=[], memory_post=[], skill_proposal=None,
        approved_skill=approved, execution_result=None,
        outcome=SkillOutcome.UNCERTAIN, retry_count=2,
        format_retry_count=0, total_llm_stats={},
        all_validation_history=[],
        executed_skill="do_nothing", executed_via_fallback=True,
    )
    trace = host.audit_writer.traces[0][1]
    assert trace["executed_via_fallback"] is True
    assert trace["fallback_activated"] is True


def test_mixin_config_without_getter_is_off():
    # Engines wired with a config object predating the getter must behave
    # exactly like flag-OFF (getattr guard, never AttributeError).
    host = _Host(flag=False)
    host.config = SimpleNamespace(get_log_fields=lambda agent_type: [])
    trace = _write(host)
    assert "executed_skill" not in trace
