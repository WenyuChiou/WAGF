# WAGF Audit Schema

## Contract

The raw JSONL trace is the source of truth.

| Artifact | Path | Producer | Contract |
|---|---|---|---|
| Raw trace log | `raw/<agent_type>_traces.jsonl` | `broker/components/analytics/audit.py:GenericAuditWriter.write_trace` | Append-only JSONL. The first line is a `_metadata` header for schema-aware runs. |
| Flat CSV | `<agent_type>_governance_audit.csv` | `broker/components/analytics/audit.py:GenericAuditWriter._export_csv` | Projection of each JSONL trace through `trace_to_csv_row`. |
| Recovery CSV | `<agent_type>_governance_audit.csv` | `broker/tools/recover_csv_from_jsonl.py:recover_csv` | Reuses `trace_to_csv_row` and `compute_csv_fieldnames` verbatim. |
| Schema sidecar | `<agent_type>_governance_audit.schema.json` | `broker/components/analytics/audit.py:GenericAuditWriter._export_csv` | Records `audit_schema_version`, git short hash, row count, and CSV fieldnames. |
| Run summary | `audit_summary.json` | `broker/components/analytics/audit.py:GenericAuditWriter.finalize` | Written last so schema version, sentinel warnings, and CSV export failures are captured. |

Schema version `"2"` begins on 2026-06-10. The version stamp appears in the
JSONL `_metadata` header, `audit_summary.json`, and each per-CSV sidecar.

Analyst rule: recover or compare CSVs through the framework tools. Do not treat
raw CSV byte hashes as the data contract when nondeterministic cells are known.

## Column Groups

| Group | Columns | Producer file:symbol | Notes |
|---|---|---|---|
| Identity and timing | `step_id`, `year`, `timestamp`, `agent_id` | `broker/components/analytics/audit.py:trace_to_csv_row` | Basic row identity. `timestamp` is wall-clock trace time. |
| Final status | `status`, `retry_count`, `validated` | `broker/components/analytics/audit.py:trace_to_csv_row` | `status` comes from `approved_skill.status`; `validated` is final-attempt state. |
| LLM stats | `llm_retries`, `llm_success`, `prompt_tokens`, `response_tokens`, `num_ctx`, `context_utilization` | `broker/components/analytics/audit.py:trace_to_csv_row` | Reads `trace.llm_stats` first, then legacy top-level retry fields. |
| Parse quality | `format_retries`, `parsing_warnings`, `parse_layer`, `parse_confidence`, `construct_completeness`, `raw_output` | `broker/components/analytics/audit.py:trace_to_csv_row` | `raw_output` prefers `skill_proposal.raw_output`, then top-level `raw_output`. Newlines are sanitized for CSV. |
| Skill logic | `proposed_skill`, `final_skill`, `status` | `broker/components/analytics/audit.py:trace_to_csv_row` | `proposed_skill` is the model proposal. `final_skill` is `approved_skill.skill_name`. |
| Rejected-row discipline | `proposed_skill`, `final_skill`, `status` | `broker/components/analytics/audit.py:trace_to_csv_row` | On `REJECTED`, the executed registry-default skill name is not in the row. Analysts must remap by `status` and use executed-only discipline. |
| Fallback | `fallback_activated` | `broker/components/analytics/audit.py:trace_to_csv_row` | Reads top-level `fallback_activated` when present; otherwise infers from legacy status strings. |
| Reasoning | `reason_*`, `appraisal`, `demo_score`, `demo_anchors` | `broker/components/analytics/audit.py:trace_to_csv_row` | Dynamic flattening of `skill_proposal.reasoning`. Demographic audit gets explicit columns. |
| Constructs | `construct_*` | `broker/components/analytics/audit.py:trace_to_csv_row` | Dynamic subset of reasoning keys ending in `_LABEL`, `_UTIL`, `_GAP`, `_IMPACT`, or `_APPETITE`. |
| Memory | `mem_retrieved_count`, `mem_cognitive_system`, `mem_surprise`, `mem_retrieval_mode`, `mem_top_emotion`, `mem_top_source` | `broker/components/analytics/audit.py:trace_to_csv_row` | Reads `memory_audit`; defaults are placeholders when the dict is absent. |
| Social | `social_gossip_count`, `social_neighbor_count`, `social_network_density`, `social_*` | `broker/components/analytics/audit.py:trace_to_csv_row` | Broker columns plus dynamic `visible_actions` keys prefixed as `social_<key>`. |
| Cognitive | `cog_system_mode`, `cog_surprise_value`, `cog_is_novel_state`, `cog_margin_to_switch` | `broker/components/analytics/audit.py:trace_to_csv_row` | Reserved in current runs. See reserved/dead table before analysis. |
| Rule breakdown | `rules_personal_hit`, `rules_social_hit`, `rules_thinking_hit`, `rules_physical_hit`, `rules_semantic_hit` | `broker/components/analytics/audit.py:trace_to_csv_row` | Reads category counts from `rule_breakdown`. |
| Triggered rules | `rules_evaluated_count`, `rules_triggered` | `broker/components/analytics/audit.py:trace_to_csv_row` | `rules_triggered` joins top-level `triggered_rules`; count reads `rules_evaluated`. |
| Validation failures | `failed_rules`, `error_messages`, `hallucination_types` | `broker/components/analytics/audit.py:trace_to_csv_row`; `broker/components/analytics/audit.py:GenericAuditWriter.write_trace` | `write_trace` builds `validation_issues`; projection flattens rule ids and errors. |
| Validation warnings | `warning_rules`, `warning_messages` | `broker/components/analytics/audit.py:trace_to_csv_row`; `broker/components/analytics/audit.py:GenericAuditWriter.write_trace` | Non-blocking governance observations from `validation_warnings_list`. |
| Shadow mode | `shadow_blocked` | `broker/components/analytics/audit.py:trace_to_csv_row`; `broker/validators/governance/base_validator.py:BaseValidator._to_shadow` | Rules that would block in active mode but were recorded non-blocking in shadow mode. |
| Condition details | `condition_0_rule`, `condition_0_matched`, `condition_1_rule`, `condition_1_matched`, `condition_2_rule`, `condition_2_matched` | `broker/components/analytics/audit.py:trace_to_csv_row` | Reserved first-three condition projection. See reserved/dead table. |
| World coupling | `world_*`, `world_contention_rule` | `broker/components/analytics/audit.py:trace_to_csv_row` | Key-gated. Columns appear only when `execution_result.action_context.world_delta` is present. |
| Field ordering | all CSV columns | `broker/components/analytics/audit.py:compute_csv_fieldnames` | Priority columns first, construct columns sorted, remaining columns alphabetical. |
| Schema sidecar | `fieldnames`, `audit_schema_version`, `git_commit_short`, `row_count` | `broker/components/analytics/audit.py:GenericAuditWriter._export_csv` | Sidecar fieldnames must match the CSV header exactly. |

## Stable Column Inventory

Schema `"2"` pins the column set with `broker/tests/test_audit_schema_golden.py`.
Dynamic columns can still appear when trace keys appear, but the stable test
trace covers the standard audit projection.

| Column | Group | Producer file:symbol |
|---|---|---|
| `step_id` | identity | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `year` | identity | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `agent_id` | identity | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `proposed_skill` | skill logic | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `final_skill` | skill logic | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `status` | final status | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `fallback_activated` | fallback | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `retry_count` | final status | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `format_retries` | parse quality | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `validated` | final status | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `failed_rules` | validation failures | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `shadow_blocked` | shadow mode | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `parse_layer` | parse quality | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `parse_confidence` | parse quality | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `construct_completeness` | parse quality | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `construct_BUDGET_UTIL` | constructs | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `construct_PLAN_GAP` | constructs | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `construct_THREAT_LABEL` | constructs | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `rules_evaluated_count` | triggered rules | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `rules_triggered` | triggered rules | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `mem_retrieved_count` | memory | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `mem_cognitive_system` | memory | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `mem_surprise` | memory | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `social_gossip_count` | social | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `social_neighbor_count` | social | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `cog_system_mode` | cognitive | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `cog_surprise_value` | cognitive | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `cog_is_novel_state` | cognitive | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `rules_personal_hit` | rule breakdown | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `rules_social_hit` | rule breakdown | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `rules_thinking_hit` | rule breakdown | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `rules_physical_hit` | rule breakdown | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `rules_semantic_hit` | rule breakdown | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `hallucination_types` | validation failures | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `appraisal` | reasoning | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `cog_margin_to_switch` | cognitive | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `condition_0_matched` | condition details | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `condition_0_rule` | condition details | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `condition_1_matched` | condition details | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `condition_1_rule` | condition details | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `condition_2_matched` | condition details | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `condition_2_rule` | condition details | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `context_utilization` | LLM stats | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `demo_anchors` | reasoning | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `demo_score` | reasoning | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `error_messages` | validation failures | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `llm_retries` | LLM stats | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `llm_success` | LLM stats | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `mem_retrieval_mode` | memory | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `mem_top_emotion` | memory | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `mem_top_source` | memory | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `num_ctx` | LLM stats | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `parsing_warnings` | parse quality | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `prompt_tokens` | LLM stats | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `raw_output` | parse quality | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `reason_budget_util` | reasoning | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `reason_plain_text` | reasoning | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `reason_plan_gap` | reasoning | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `reason_threat_label` | reasoning | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `response_tokens` | LLM stats | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `social_network_density` | social | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `social_request_upgrade_neighbors` | social | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `timestamp` | identity | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `warning_messages` | validation warnings | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `warning_rules` | validation warnings | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `world_<key>` | world coupling | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `world_contention_rule` | world coupling | `broker/components/analytics/audit.py:trace_to_csv_row` |

## Reserved Or Dead Columns

These columns are wired into consumers or the CSV projection, but current
framework producers do not emit meaningful upstream values. Treat each as
reserved. Do not analyze them as empirical signals.

| Column | CSV producer | Upstream producer | Status |
|---|---|---|---|
| `cog_system_mode` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `cog_surprise_value` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `cog_is_novel_state` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `cog_margin_to_switch` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `condition_0_rule` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `condition_0_matched` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `condition_1_rule` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `condition_1_matched` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `condition_2_rule` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `condition_2_matched` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |
| `rules_evaluated_count` | `broker/components/analytics/audit.py:trace_to_csv_row` | none in current runs | reserved - do not analyze |

## Semantics Gotchas

| Gotcha | Meaning | Recommended handling |
|---|---|---|
| `validated=True` with non-empty `failed_rules` | A retry recovered. The final attempt is clean, but prior blocking issues are preserved. | Treat as "retry-recovered", not as a final contradiction. |
| `rules_triggered` vs `failed_rules` | `rules_triggered` reads `rules_hit`; `failed_rules` reads `rule_id`. Legacy validators can diverge. | Use both only after checking validator attribution semantics. |
| `mem_top_source` | Derived through set iteration over observed memory sources. Ties can vary with `PYTHONHASHSEED`. | Use `broker.tools.compare_audit_csv`, not raw SHA256, for audit comparisons. |
| `fire_rate` in `validator_health.csv` | Computed per emitted validation result, not per proposal. ERROR rules tend toward `1.0`; WARNING rules tend toward `0.0`. | Do not interpret it as proposal-level prevalence. |
| Lowercase rule levels | Enforcement comparisons are exact-string checks for `"ERROR"`. Unknown levels are treated like non-blocking warnings. | Write `ERROR` or `WARNING`, uppercase. Schema 2 loaders warn but preserve behavior. |
| CSV text cells | `trace_to_csv_row` strips newlines and carriage returns from strings. | Use JSONL for exact raw text. |
| Dynamic columns | `construct_*`, `social_*`, and `world_*` depend on keys present in traces. | Compare against the schema sidecar for the run under analysis. |

## Historical Note

| Era | Schema | Notes |
|---|---|---|
| Before 2026-06-10 | `"1"` era or no sidecar | Frozen CSVs may carry old column sets without an honest schema bump. |
| Before 2026-06-10 | `"1"` era | Some CSVs contain a duplicate `construct_completeness` header. `pandas` reads a `.1` suffix; `csv.DictReader` keeps one value. |
| Before 2026-06-10 | `"1"` era | Top-level JSONL `raw_output` may be truncated. `skill_proposal.raw_output` may still carry the fuller text. |
| 2026-06-10 onward | `"2"` | JSONL top-level `raw_output` truncation is removed, CSV sidecars exist, and fieldnames are pinned by tests. |

Do not repair frozen files in place. Treat historical artifacts as immutable
evidence and document the schema era in any paper or replication package.

## Which Plane Answers What

| Question | CSV | JSONL | Nowhere |
|---|---:|---:|---:|
| Final action label | yes | yes | no |
| Final status | yes | yes | no |
| Retry count | yes | yes | no |
| Format retry count | yes | yes | no |
| Deduplicated blocking-rule union | yes | yes | no |
| Deduplicated warning-rule union | yes | yes | no |
| Construct labels and utilities | yes, for suffix-matching reasoning keys | yes | no |
| Parse layer and confidence | yes | yes | no |
| Token counts | yes | yes | no |
| Memory top emotion/source summary | yes | yes | no |
| Full memory internals | no | yes, if written by the producer | no |
| Social visible-action summaries | yes | yes | no |
| Full social internals | no | yes, if written by the producer | no |
| Validator names | no | yes | no |
| Per-issue metadata such as `expected_terminal` | no | yes | no |
| Full prompts | no | yes, if the trace writer includes them | no |
| World commit deltas | yes, only when key-gated columns appear | yes | no |
| Per-attempt retry sequence | no | no | accepted gap |
| Executed registry-default name on `REJECTED` | no | no | accepted gap |

## Analyst Checklist

| Step | Check |
|---|---|
| 1 | Read `<agent_type>_governance_audit.schema.json` before reading the CSV. |
| 2 | Confirm `audit_schema_version` and the CSV header match the sidecar. |
| 3 | Treat JSONL as canonical for raw text, validator metadata, and internals. |
| 4 | Use CSV for flat final-action, final-status, retry, rule-union, and construct analyses. |
| 5 | Exclude reserved/dead columns from statistical analysis. |
| 6 | For recovered artifacts, cite that `recover_csv_from_jsonl` shares `trace_to_csv_row` with the live writer. |
