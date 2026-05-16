"""W1 (Phase 6G #4a): fallback_activated is written at SOURCE.

The audit row-builder (broker.components.analytics.audit.trace_to_csv_row)
already prefers trace['fallback_activated'] when present. W1 makes
AuditMixin._write_audit_trace populate that top-level key directly from
the approved_skill status, instead of leaving the row-builder to infer
it from the status string. This test pins the write-side contract:

  approved_skill.approval_status == "REJECTED_FALLBACK"  -> True
  any other status (APPROVED, REJECTED, ...)             -> False
  approved_skill is None                                 -> False
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pytest

from broker.core._audit_helpers import AuditMixin


@dataclass
class _Skill:
    skill_name: str = "maintain_demand"
    approval_status: str = "APPROVED"
    execution_mapping: Any = None


@dataclass
class _Outcome:
    value: str = "ok"


class _Exec:
    def __init__(self):
        self.delivered = 1.0


class _Config:
    def get_log_fields(self, _agent_type):
        return []


class _CaptureWriter:
    """Stand-in audit_writer that records the trace dict it is handed."""
    def __init__(self):
        self.captured: Dict[str, Any] = {}

    def write_trace(self, agent_type, trace, *a, **kw):
        self.captured = trace


class _Host(AuditMixin):
    """Minimal host combining the mixin with the deps it reads off self."""
    def __init__(self):
        self.config = _Config()
        self.audit_writer = _CaptureWriter()
        self._model_name = "test-model"

    def _merge_state_after(self, state, _execution_result):
        return dict(state or {})


def _write(status_or_none):
    host = _Host()
    approved = None if status_or_none is None else _Skill(approval_status=status_or_none)
    host._write_audit_trace(
        agent_type="irrigation_farmer",
        context={"agent_type": "irrigation_farmer", "state": {}},
        run_id="run-1",
        step_id="s-1",
        timestamp="2026-05-16T00:00:00",
        env_context={"current_year": 1},
        seed=42,
        agent_id="agent_000",
        all_valid=True,
        prompt="p",
        raw_output="{}",
        context_hash="h",
        memory_pre=[],
        memory_post=[],
        skill_proposal=None,
        approved_skill=approved,
        execution_result=_Exec(),
        outcome=_Outcome(),
        retry_count=0,
        format_retry_count=0,
        total_llm_stats={},
        all_validation_history=[],
    )
    return host.audit_writer.captured


def test_fallback_activated_true_on_rejected_fallback():
    trace = _write("REJECTED_FALLBACK")
    assert trace["fallback_activated"] is True


@pytest.mark.parametrize("status", ["APPROVED", "REJECTED", "UNCERTAIN", "MODIFIED"])
def test_fallback_activated_false_on_other_statuses(status):
    trace = _write(status)
    assert trace["fallback_activated"] is False


def test_fallback_activated_false_when_approved_skill_none():
    trace = _write(None)
    assert trace["fallback_activated"] is False
