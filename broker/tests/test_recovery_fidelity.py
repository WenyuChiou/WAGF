"""Recovery fidelity tests for JSONL-as-truth audit artifacts."""
from __future__ import annotations

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
