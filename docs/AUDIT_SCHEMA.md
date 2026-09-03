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
| Rejected-row discipline | `proposed_skill`, `final_skill`, `status` | `broker/components/analytics/audit.py:trace_to_csv_row` | On `REJECTED`, `final_skill` is the BLOCKED proposal, not what executed. **What actually executed depends on the domain's `global_config.governance.on_retry_exhausted` policy**: `default` (the default) runs the registry `default_skill`, whose name is then absent from the row; `keep_proposal` runs the blocked proposal itself, in which case `final_skill` and the executed action coincide. The row alone cannot tell you which — enable `global_config.audit.executed_skill_columns` and read `executed_skill` / `executed_via_fallback`, or check `advise_spec_resolved`/policy in the run manifest. Analysts must remap by `status` and use executed-only discipline. |
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

## Known-limitation columns in pre-v0.7 corpora

These columns exist in the schema and are populated on every row, but the
value they carry is not the signal the column name implies. Unlike the
Reserved/Dead columns above (which are simply unwired), these columns look
like real per-row data and can silently mislead an analysis that does not
know the mechanism below. Treat them as unreliable in released corpora.
Fixes for the still-open rows are flag-gated (default-OFF) and land in a
later PR in this stack, not this one — this PR only documents the gap.

| Column | What it looks like | What it actually is | Mechanism (verified) | Status |
|---|---|---|---|---|
| `fallback_activated` | Per-row boolean: did the registry default skill execute? | For traces written before commit `0e3187c` (pre-Phase-6G, includes the v21 5-seed Gemma-3 4B corpus), this is `False` on every row, including the rows where a fallback genuinely executed. | Before `broker/core/_audit_helpers.py`'s `_write_audit_trace` was changed (Phase 6G #4a, commit `5f64055b7`, 2026-05-16) to write `fallback_activated` at source, the key was never present in the trace dict, so `trace_to_csv_row` (`broker/components/analytics/audit.py`) fell through to a narrower status-string inference set that did not include `REJECTED_FALLBACK`. v21 5-seed Gemma-3 4B has 105/16,380 rows (0.64%) affected. Full writeup: `broker/INVARIANTS.md` Invariant 2, "Known current state". | Fixed going forward (traces written after 2026-05-16 populate this correctly). Pre-fix corpora are permanently affected; do not repair in place — regenerating via `recover_csv_from_jsonl` on a pre-fix JSONL trace changes this column's values relative to the original on-disk CSV, by design. |
| `rules_personal_hit`, `rules_social_hit`, `rules_thinking_hit`, `rules_semantic_hit` | Per-row count of rules that fired in that governance category. | Structurally zero on every row produced by the production validator, regardless of how many rules actually fired. | `_safe_rule_breakdown` (`broker/core/_audit_helpers.py`) calls `get_rule_breakdown()` (`broker/validators/governance/__init__.py`), which reads `result.metadata.get("category", "")` off each `ValidationResult`. Every production run validates through `AgentValidator` (`broker/validators/agent/agent_validator.py`), whose `ValidationResult.metadata` dicts use keys like `level` / `rule` / `rules_hit` / `field` / `constraint` — verified by grep, `AgentValidator` never sets `metadata["category"]`. So the category lookup is always `""`, which matches none of the five breakdown buckets. | Not yet fixed. `rules_physical_hit` is excluded from this list because it CAN be populated, but only when a domain explicitly sets the opt-in, default-OFF `global_config.governance.dispatch_domain_physical` flag, which routes through `PhysicalValidator` directly (`broker/core/skill_broker_engine.py`, ~line 775) and that validator's base class does set `metadata["category"]` (`broker/validators/governance/base_validator.py`). Under the default config (no dispatch flag), `rules_physical_hit` is zero for the same reason as the other four. Do not use these columns as a rule-category breakdown; use `failed_rules` / `rules_triggered` (rule-ID level, not category level) instead. |
| `mem_top_emotion`, `mem_top_source` | Per-row summary of the retrieved memories' dominant emotion/source. | In corpora where the upstream memory dict never populates real `emotion`/`source` values, this is the constant placeholder `"neutral"` / `"personal"` on every row, not a computed summary. | `broker/core/_audit_helpers.py`'s `_write_audit_trace` builds `memory_audit["memories"]` via `memory.get("emotion", "neutral")` and `memory.get("source", "personal")`; `broker/components/analytics/audit.py`'s `trace_to_csv_row` then takes the mode of those values. If the upstream memory records never carry real `emotion`/`source` keys, the default is what gets aggregated, indistinguishable in the CSV from a genuine unanimous mode. This is the same failure class the 2026-04-19 NW flood post-mortem documented (`broker/INVARIANTS.md` Invariant 2, born from this exact incident) and the reason `_SUSPICIOUS_COLUMN_DEFAULTS` in `audit.py` flags these two columns for sentinel-constancy detection. | Partially mitigated: `detect_audit_sentinels` / `AuditWriter.finalize()` now WARN on suspicious constancy, but do not repair historical rows. Check the run's sentinel warnings (or `audit_summary.json`) before trusting these two columns for any given corpus. |
| Row-count parity between arms | Two experiment arms with the same agent/year/seed grid are expected to produce the same number of CSV rows. | Not guaranteed. A step whose LLM output fails to parse after retries returns `SkillOutcome.ABORTED` directly (`broker/core/skill_broker_engine.py`, the early return right after `_invoke_llm_with_retries`), before the function reaches its single `_write_audit_trace` call site later in the same method. An ABORTED step is therefore never written to the JSONL trace or the CSV. | Verified structurally: `_write_audit_trace` has exactly one call site in `skill_broker_engine.py`, and the ABORTED branch `return`s before reaching it. So an arm with more parse failures than the other silently has fewer audit rows, not more ABORTED rows — the asymmetry is invisible unless you cross-check row counts against the expected agent x year x seed grid. | Not yet fixed. Cross-check CSV row counts against the expected grid before comparing rejection/rate statistics between arms; do not assume equal row counts imply equal step counts. |

## Semantics Gotchas

| Gotcha | Meaning | Recommended handling |
|---|---|---|
| `validated=True` with non-empty `failed_rules` | A retry recovered. The final attempt is clean, but prior blocking issues are preserved. | Treat as "retry-recovered", not as a final contradiction. |
| `rules_triggered` vs `failed_rules` | `rules_triggered` reads `rules_hit`; `failed_rules` reads `rule_id`. Legacy validators can diverge. | Use both only after checking validator attribution semantics. |
| `failed_rules` = `Unknown` | The producing `ValidationResult` carries no `metadata.rule_id`. Known producer: `AgentValidator:format` missing-required-fields (`agent_validator.py`), which fires on EVERY frozen-mock-baseline row — its label is frozen as `Unknown` because renaming it breaks mock byte-identity re-verification. | Treat `Unknown` + `error_messages` starting "Response missing required fields" as the format check. Rename to `format_required_fields` only at the next `AUDIT_SCHEMA_VERSION` bump. |
| `output_schema_violation` / `precondition_violation` in `failed_rules` | Named 2026-06-10 (both registry-level checks in `skill_broker_engine._run_validators`). Byte-safe: zero occurrences of either in the frozen mock baselines, so naming them changed no frozen-path bytes. | Rows older than 2026-06-10 show these producers as `Unknown`. |
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
