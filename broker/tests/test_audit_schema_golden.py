"""Golden tests for governance audit CSV schema version 2."""
from __future__ import annotations

import csv
import json
from copy import deepcopy

from broker.components.analytics.audit import (
    AUDIT_SCHEMA_VERSION,
    AuditConfig,
    GenericAuditWriter,
    compute_csv_fieldnames,
    trace_to_csv_row,
)


GOLDEN_FIELDNAMES = [
    "step_id",
    "year",
    "agent_id",
    "proposed_skill",
    "final_skill",
    "status",
    "fallback_activated",
    "retry_count",
    "format_retries",
    "validated",
    "failed_rules",
    "shadow_blocked",
    "parse_layer",
    "parse_confidence",
    "construct_completeness",
    "construct_BUDGET_UTIL",
    "construct_PLAN_GAP",
    "construct_THREAT_LABEL",
    "rules_evaluated_count",
    "rules_triggered",
    "mem_retrieved_count",
    "mem_cognitive_system",
    "mem_surprise",
    "social_gossip_count",
    "social_neighbor_count",
    "cog_system_mode",
    "cog_surprise_value",
    "cog_is_novel_state",
    "rules_personal_hit",
    "rules_social_hit",
    "rules_thinking_hit",
    "rules_physical_hit",
    "rules_semantic_hit",
    "hallucination_types",
    "appraisal",
    "cog_margin_to_switch",
    "condition_0_matched",
    "condition_0_rule",
    "condition_1_matched",
    "condition_1_rule",
    "condition_2_matched",
    "condition_2_rule",
    "context_utilization",
    "demo_anchors",
    "demo_score",
    "error_messages",
    "llm_retries",
    "llm_success",
    "mem_retrieval_mode",
    "mem_top_emotion",
    "mem_top_source",
    "num_ctx",
    "parsing_warnings",
    "prompt_tokens",
    "raw_output",
    "reason_budget_util",
    "reason_plain_text",
    "reason_plan_gap",
    "reason_threat_label",
    "response_tokens",
    "social_network_density",
    "social_request_upgrade_neighbors",
    "timestamp",
    "warning_messages",
    "warning_rules",
]


def _synthetic_trace() -> dict:
    return {
        "step_id": 7,
        "year": 2035,
        "timestamp": "2026-06-10T12:00:00",
        "agent_id": "agent-1",
        "retry_count": 2,
        "validated": True,
        "llm_stats": {
            "llm_retries": 1,
            "llm_success": True,
            "prompt_tokens": 101,
            "response_tokens": 202,
            "num_ctx": 4096,
            "context_utilization": 0.25,
        },
        "format_retries": 1,
        "fallback_activated": False,
        "skill_proposal": {
            "skill_name": "request_upgrade",
            "parsing_warnings": ["trimmed", "json_repaired"],
            "raw_output": "line one, with comma\nline two",
            "parse_layer": "json_block",
            "parse_confidence": 0.91,
            "construct_completeness": 0.83,
            "reasoning": {
                "THREAT_LABEL": "H",
                "BUDGET_UTIL": 0.42,
                "PLAN_GAP": "M",
                "appraisal": "high concern",
                "plain_text": "deterministic explanation",
                "demographic_audit": {
                    "score": 0.75,
                    "cited_anchors": ["age", "income"],
                },
            },
        },
        "approved_skill": {
            "skill_name": "registry_default",
            "status": "REJECTED",
        },
        "memory_audit": {
            "retrieved_count": 2,
            "cognitive_system": "system2",
            "surprise_value": 0.33,
            "retrieval_mode": "episodic",
            "memories": [
                {"emotion": "concern", "source": "neighbor"},
                {"emotion": "concern", "source": "neighbor"},
            ],
        },
        "social_audit": {
            "gossip_received": ["a", "b"],
            "neighbor_count": 5,
            "network_density": 0.67,
            "visible_actions": {"request_upgrade_neighbors": 3},
        },
        "cognitive_audit": {
            "system_mode": "deliberative",
            "surprise": 0.44,
            "is_novel_state": True,
            "margin_to_switch": 0.12,
        },
        "rule_breakdown": {
            "personal": 1,
            "social": 2,
            "thinking": 3,
            "physical": 4,
            "semantic": 5,
        },
        "validation_issues": [
            {
                "rule_id": "rule_error",
                "errors": ["blocked, because"],
                "hallucination_type": "invalid_terminal",
            }
        ],
        "validation_warnings_list": [
            {"rule_id": "rule_warn", "warnings": ["soft issue"]}
        ],
        "shadow_blocked": [{"rule_id": "shadow_rule"}],
        "rules_evaluated": ["rule_error", "rule_warn"],
        "triggered_rules": ["rule_error", "rule_warn"],
        "condition_results": [
            {"rule_id": "condition_0", "matched": True},
            {"rule_id": "condition_1", "matched": False},
            {"rule_id": "condition_2", "matched": True},
        ],
    }


def _fieldnames(trace: dict) -> list[str]:
    return compute_csv_fieldnames([trace_to_csv_row(trace)])


def test_audit_schema_version_2_fieldnames_match_golden():
    assert AUDIT_SCHEMA_VERSION == "2", (
        "column set changed? bump AUDIT_SCHEMA_VERSION in audit.py AND "
        "update this golden in the same commit."
    )
    assert _fieldnames(_synthetic_trace()) == GOLDEN_FIELDNAMES


def test_world_delta_adds_only_key_gated_world_columns():
    trace = _synthetic_trace()
    world_trace = deepcopy(trace)
    world_trace["execution_result"] = {
        "action_context": {
            "world_delta": {
                "world_changes": {
                    "water_depth": 1.25,
                    "road_status": "closed",
                },
                "contention_rule": "last_writer_wins",
            }
        }
    }

    base_fields = _fieldnames(trace)
    world_fields = _fieldnames(world_trace)

    assert set(world_fields) - set(base_fields) == {
        "world_contention_rule",
        "world_road_status",
        "world_water_depth",
    }
    assert set(base_fields) - set(world_fields) == set()


def test_proposed_param_columns_are_key_gated_and_sorted_after_priority():
    """6W-B6: proposed_param_<name> keys (emitted only when the param_columns flag
    is ON and the proposal carries setpoints) add EXACTLY those columns and never
    reorder/drop the frozen set. A trace without them == GOLDEN_FIELDNAMES."""
    trace = _synthetic_trace()
    param_trace = deepcopy(trace)
    param_trace["proposed_param_release_cms"] = 12.0
    param_trace["proposed_param_hydropower_mw"] = 800.0

    base_fields = _fieldnames(trace)
    param_fields = _fieldnames(param_trace)

    assert base_fields == GOLDEN_FIELDNAMES  # no param keys -> frozen schema intact
    assert set(param_fields) - set(base_fields) == {
        "proposed_param_release_cms",
        "proposed_param_hydropower_mw",
    }
    assert set(base_fields) - set(param_fields) == set()  # nothing dropped/reordered out


def test_cost_columns_are_key_gated_and_sorted_after_priority():
    """2026-09-15: the token/latency columns add EXACTLY five names and reorder
    nothing. A trace whose stats dict predates them (every JSONL written before
    this change, and every trace the recovery CLI replays from one) still
    produces GOLDEN_FIELDNAMES, which is why this is additive rather than a
    schema bump."""
    trace = _synthetic_trace()
    cost_trace = deepcopy(trace)
    cost_trace["llm_stats"].update({
        "prompt_tokens_total": 303,
        "response_tokens_total": 404,
        "llm_calls_total": 3,
        "llm_latency_ms": 812.5,
        "tokens_per_second": 41.2,
        # JSONL-only: read by the context-budget tripwire, never projected.
        "context_utilization_peak": 0.44,
        "prompt_tokens_peak": 1802,
        "num_ctx_peak": 4096,
    })

    base_fields = _fieldnames(trace)
    cost_fields = _fieldnames(cost_trace)

    assert base_fields == GOLDEN_FIELDNAMES
    assert set(cost_fields) - set(base_fields) == {
        "prompt_tokens_total",
        "response_tokens_total",
        "llm_calls_total",
        "llm_latency_ms",
        "tokens_per_second",
    }
    assert set(base_fields) - set(cost_fields) == set()
    # Relative order of every frozen column is untouched; the five land in the
    # alphabetical tail, exactly as `llm_calls` and `executed_skill` did.
    assert [c for c in cost_fields if c in GOLDEN_FIELDNAMES] == GOLDEN_FIELDNAMES


def test_schema_sidecar_matches_csv_header(tmp_path):
    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="schema-golden")
    )
    writer.write_trace("schema_agent", _synthetic_trace())
    writer.finalize()

    csv_path = tmp_path / "schema_agent_governance_audit.csv"
    schema_path = tmp_path / "schema_agent_governance_audit.schema.json"

    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    assert schema["audit_schema_version"] == "2"
    assert schema["fieldnames"] == header
