"""Recovery fidelity tests for JSONL-as-truth audit artifacts."""
from __future__ import annotations

import csv

from broker.components.analytics.audit import AuditConfig, GenericAuditWriter
from broker.tools.recover_csv_from_jsonl import recover_csv


def _trace(step_id: int, raw_output: str) -> dict:
    return {
        "step_id": step_id,
        "year": 2035,
        "timestamp": f"2026-06-10T12:00:0{step_id}",
        "agent_id": f"agent-{step_id}",
        "retry_count": step_id - 1,
        "validated": True,
        "llm_stats": {
            "llm_retries": 0,
            "llm_success": True,
            "prompt_tokens": 10 + step_id,
            "response_tokens": 20 + step_id,
            "num_ctx": 4096,
            "context_utilization": 0.1 * step_id,
        },
        "format_retries": 0,
        "fallback_activated": False,
        "raw_output": raw_output,
        "skill_proposal": {
            "skill_name": "act",
            "parsing_warnings": [],
            "raw_output": raw_output,
            "parse_layer": "json_block",
            "parse_confidence": 0.9,
            "construct_completeness": 1.0,
            "reasoning": {
                "THREAT_LABEL": "H",
                "plain_text": f"reason {step_id}",
            },
        },
        "approved_skill": {
            "skill_name": "act",
            "status": "APPROVED",
        },
        "memory_audit": {
            "retrieved_count": 2,
            "cognitive_system": "system2",
            "surprise_value": 0.2,
            "retrieval_mode": "episodic",
            "memories": [
                {"emotion": "concern", "source": "lab"},
                {"emotion": "concern", "source": "lab"},
            ],
        },
        "social_audit": {
            "gossip_received": [],
            "neighbor_count": 1,
            "network_density": 0.5,
            "visible_actions": {"act_neighbors": step_id},
        },
        "cognitive_audit": {
            "system_mode": "deliberative",
            "surprise": 0.1,
            "is_novel_state": False,
            "margin_to_switch": 0.4,
        },
        "rule_breakdown": {},
        "validation_issues": [],
        "validation_warnings_list": [],
        "shadow_blocked": [],
        "rules_evaluated": [],
        "triggered_rules": [],
        "condition_results": [],
    }


def test_recovered_csv_is_byte_identical_to_live_csv(tmp_path):
    """Pins the F12 contract: JSONL is truth and recovery is byte-faithful.

    This failed before 2026-06-10 because top-level JSONL raw_output
    truncation could make recovered raw_output diverge from the live CSV.
    """
    long_raw_output = (
        "first line, with comma\n"
        + ("x" * 650)
        + "\nthird line, with comma, and \"quotes\""
    )
    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="recovery-fidelity")
    )
    writer.write_trace("recovery_agent", _trace(1, "short output"))
    writer.write_trace("recovery_agent", _trace(2, long_raw_output))
    writer.write_trace("recovery_agent", _trace(3, "another short output"))
    writer.finalize()

    live_csv = tmp_path / "recovery_agent_governance_audit.csv"
    archived_live_csv = tmp_path / "recovery_agent_governance_audit.live.csv"
    live_csv.replace(archived_live_csv)

    summary = recover_csv(tmp_path)

    assert summary["recovery_agent"]["rows_recovered"] == 3
    assert live_csv.read_bytes() == archived_live_csv.read_bytes()


def _trace_with_params(step_id: int, raw_output: str, params: dict) -> dict:
    """Inject top-level proposed_param_<name> keys exactly as _audit_helpers emits
    them when global_config.audit.param_columns is ON and the proposal carries
    setpoints (mirrors test_audit_schema_golden.py's _synthetic_trace injection)."""
    trace = _trace(step_id, raw_output)
    trace.update(params)
    return trace


def test_proposed_param_columns_roundtrip_through_recovery(tmp_path):
    """6W deferred: proposed_param_<name> columns must survive the JSONL->CSV
    rebuild byte-identically.

    The recovery path shares trace_to_csv_row + compute_csv_fieldnames with the
    live writer, so equality is guaranteed by construction — this test pins it so a
    future divergence (e.g. a recover-side filter that drops unknown keys) is caught.
    Beyond byte-identity it asserts the param columns are actually PRESENT with the
    right values, so the test cannot pass trivially with both CSVs lacking them.
    """
    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="recovery-params")
    )
    writer.write_trace(
        "param_agent",
        _trace_with_params(1, "out-1", {
            "proposed_param_release_cms": 12.0,
            "proposed_param_hydropower_mw": 800.0,
        }),
    )
    writer.write_trace(
        "param_agent",
        _trace_with_params(2, "out-2", {
            "proposed_param_release_cms": 5.5,
            "proposed_param_hydropower_mw": 400.0,
        }),
    )
    writer.finalize()

    live_csv = tmp_path / "param_agent_governance_audit.csv"
    archived_live_csv = tmp_path / "param_agent_governance_audit.live.csv"
    live_csv.replace(archived_live_csv)

    summary = recover_csv(tmp_path)

    assert summary["param_agent"]["rows_recovered"] == 2
    # byte-identity: recovered == live
    assert live_csv.read_bytes() == archived_live_csv.read_bytes()

    # ...and the param columns are genuinely present with preserved values.
    # NOTE: live_csv now holds the RECOVERED csv (the original was moved aside
    # above); byte-identity already proved they match, so reading either is fine.
    # DictWriter str-formats float(12.0) as "12.0"; the float() parse is exact.
    with live_csv.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert "proposed_param_release_cms" in rows[0]
    assert "proposed_param_hydropower_mw" in rows[0]
    assert float(rows[0]["proposed_param_release_cms"]) == 12.0
    assert float(rows[1]["proposed_param_release_cms"]) == 5.5
    assert float(rows[0]["proposed_param_hydropower_mw"]) == 800.0
    assert float(rows[1]["proposed_param_hydropower_mw"]) == 400.0


# ─────────────────────────────────────────────────────────────────────
# feat/v3-parallel-determinism review fix: crash-proof step_id sort key,
# and recover_csv's own out-of-order-JSONL case.
# ─────────────────────────────────────────────────────────────────────


def test_export_csv_sort_key_tolerates_mixed_step_id_types(tmp_path):
    """GenericAuditWriter._export_csv's step_id sort must never raise on a
    non-int step_id (a legacy or malformed trace): int step_ids sort
    numerically first, then every missing/None/str step_id keeps its
    original (write_trace call) order, stable, at the end."""
    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="mixed-step-id")
    )
    t_missing = _trace(99, "missing")
    del t_missing["step_id"]
    t_none = _trace(99, "none-ish")
    t_none["step_id"] = None
    t_str = _trace(99, "str-ish")
    t_str["step_id"] = "3"  # a string, not an int

    # Scrambled write order; the only int step_ids are 5 and 2, so a
    # correct sort places them [2, 5], with the three non-int rows after,
    # in their original write order.
    writer.write_trace("mixed_agent", _trace(5, "five"))
    writer.write_trace("mixed_agent", t_missing)
    writer.write_trace("mixed_agent", _trace(2, "two"))
    writer.write_trace("mixed_agent", t_none)
    writer.write_trace("mixed_agent", t_str)
    writer.finalize()  # must not raise

    csv_path = tmp_path / "mixed_agent_governance_audit.csv"
    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert [r["raw_output"] for r in rows] == [
        "two", "five", "missing", "none-ish", "str-ish",
    ]


def test_recover_csv_sort_key_tolerates_mixed_step_id_types(tmp_path):
    """Same crash-proof sort key, exercised through recover_csv's own copy
    of it in broker/tools/recover_csv_from_jsonl.py."""
    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="mixed-step-id-recover")
    )
    t_missing = _trace(99, "missing")
    del t_missing["step_id"]
    t_str = _trace(99, "str-ish")
    t_str["step_id"] = "3"

    writer.write_trace("mixed_agent", _trace(5, "five"))
    writer.write_trace("mixed_agent", t_missing)
    writer.write_trace("mixed_agent", _trace(2, "two"))
    writer.write_trace("mixed_agent", t_str)
    writer.finalize()

    summary = recover_csv(tmp_path)  # must not raise
    assert summary["mixed_agent"]["rows_recovered"] == 4

    csv_path = tmp_path / "mixed_agent_governance_audit.csv"
    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert [r["raw_output"] for r in rows] == ["two", "five", "missing", "str-ish"]


def test_recover_csv_out_of_order_jsonl_matches_live_finalize(tmp_path):
    """recover_csv must sort an out-of-order (thread-completion-order)
    JSONL back to the same row order a live finalize() would have
    produced, not just reproduce whatever order the JSONL happens to be
    in. Simulates a workers>1 JSONL (written in COMPLETION order) by
    shuffling the lines of a JSONL that was captured in submission
    (step_id) order."""
    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="recovery-shuffle")
    )
    for step_id in (1, 2, 3, 4, 5):
        writer.write_trace("shuffle_agent", _trace(step_id, f"out-{step_id}"))
    writer.finalize()

    live_csv = tmp_path / "shuffle_agent_governance_audit.csv"
    archived_live_csv = tmp_path / "shuffle_agent_governance_audit.live.csv"
    live_csv.replace(archived_live_csv)

    # Scramble the JSONL to a completion-like order (5, 1, 4, 2, 3),
    # keeping the leading _metadata header line first (recover_csv's
    # reader only ever treats the LITERAL first record as a possible
    # metadata header).
    jsonl_path = tmp_path / "raw" / "shuffle_agent_traces.jsonl"
    lines = jsonl_path.read_text(encoding="utf-8").splitlines(keepends=True)
    header, body = lines[0], lines[1:]
    assert len(body) == 5
    scrambled_order = [4, 0, 3, 1, 2]  # body indices -> step_ids 5,1,4,2,3
    jsonl_path.write_text(
        header + "".join(body[i] for i in scrambled_order), encoding="utf-8",
    )

    summary = recover_csv(tmp_path)
    assert summary["shuffle_agent"]["rows_recovered"] == 5
    assert live_csv.read_bytes() == archived_live_csv.read_bytes()
