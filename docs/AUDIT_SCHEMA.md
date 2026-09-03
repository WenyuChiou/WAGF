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
| Rejected-row discipline | `proposed_skill`, `final_skill`, `status` | `broker/components/analytics/audit.py:trace_to_csv_row` | On `REJECTED`, `final_skill` is the BLOCKED proposal, not what executed. **What actually executed depends on the domain's `global_config.governance.on_retry_exhausted` policy**: `default` (the default) runs the registry `default_skill`, whose name is then absent from the row; `keep_proposal` runs the blocked proposal itself, in which case `final_skill` and the executed action coincide. The row alone cannot tell you which — enable `global_config.audit.corrected_status_columns` and read `execution_path` (which names the branch outright) plus `executed_skill`, or `global_config.audit.executed_skill_columns` for `executed_skill` / `executed_via_fallback` alone, or check `advise_spec_resolved`/policy in the run manifest. Analysts must remap by `status` and use executed-only discipline. |
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
| Executed truth | `executed_skill`, `executed_via_fallback`, `execution_path` | `broker/core/skill_broker_engine.py:process_step`; `broker/core/_audit_helpers.py:_write_audit_trace` | Key-gated. `executed_skill` / `executed_via_fallback` appear under `global_config.audit.executed_skill_columns` **or** `global_config.audit.corrected_status_columns`; `execution_path` under the latter only. See "Corrected status columns" below. |
| Field ordering | all CSV columns | `broker/components/analytics/audit.py:compute_csv_fieldnames` | Priority columns first, construct columns sorted, remaining columns alphabetical. |
| Schema sidecar | `fieldnames`, `audit_schema_version`, `git_commit_short`, `row_count`, `corrected_status_columns` | `broker/components/analytics/audit.py:GenericAuditWriter._export_csv` | Sidecar fieldnames must match the CSV header exactly. `audit_schema_version` is `"2"` for the flag-OFF column set and `"3"` for the corrected one. `corrected_status_columns: true` appears only when the flag was ON; its ABSENCE means OFF (a flag-OFF sidecar is byte-identical to a pre-v0.7 one). |

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
| `executed_skill` | executed truth (key-gated) | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `executed_via_fallback` | executed truth (key-gated) | `broker/components/analytics/audit.py:trace_to_csv_row` |
| `execution_path` | executed truth (key-gated) | `broker/components/analytics/audit.py:trace_to_csv_row` |

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

Every row below is **fixed under `global_config.audit.corrected_status_columns:
true` from v0.7** (see "Corrected status columns" following this table). The
flag defaults to OFF and must stay OFF for any rerun that has to reproduce a
published corpus: it adds a column, adds rows, and changes the values of four
existing columns, so a flag-ON rerun of a frozen experiment is a DIFFERENT
artifact by design. Nothing repairs an existing corpus in place.

| Column | What it looks like | What it actually is | Mechanism (verified) | Status |
|---|---|---|---|---|
| `fallback_activated` | Per-row boolean: did the registry default skill execute? | For traces written before commit `0e3187c` (pre-Phase-6G, includes the v21 5-seed Gemma-3 4B corpus), this is `False` on every row, including the rows where a fallback genuinely executed. | Before `broker/core/_audit_helpers.py`'s `_write_audit_trace` was changed (Phase 6G #4a, commit `5f64055b7`, 2026-05-16) to write `fallback_activated` at source, the key was never present in the trace dict, so `trace_to_csv_row` (`broker/components/analytics/audit.py`) fell through to a narrower status-string inference set that did not include `REJECTED_FALLBACK`. v21 5-seed Gemma-3 4B has 105/16,380 rows (0.64%) affected. Full writeup: `broker/INVARIANTS.md` Invariant 2, "Known current state". | Fixed under `audit.corrected_status_columns=true` from v0.7: the flag derives the column from the EXECUTED skill, so a plain-`REJECTED` row on which the registry default ran now reads True. Partially fixed for traces after 2026-05-16 (`REJECTED_FALLBACK` rows only). Pre-fix corpora are permanently affected; do not repair in place — regenerating via `recover_csv_from_jsonl` on a pre-fix JSONL trace changes this column's values relative to the original on-disk CSV, by design. |
| `rules_personal_hit`, `rules_social_hit`, `rules_thinking_hit`, `rules_semantic_hit` | Per-row count of rules that fired in that governance category. | Structurally zero on every row produced by the production validator, regardless of how many rules actually fired. | `_safe_rule_breakdown` (`broker/core/_audit_helpers.py`) calls `get_rule_breakdown()` (`broker/validators/governance/__init__.py`), which reads `result.metadata.get("category", "")` off each `ValidationResult`. Every production run validates through `AgentValidator` (`broker/validators/agent/agent_validator.py`), whose `ValidationResult.metadata` dicts use keys like `level` / `rule` / `rules_hit` / `field` / `constraint` — verified by grep, `AgentValidator` never sets `metadata["category"]`. So the category lookup is always `""`, which matches none of the five breakdown buckets. | PARTLY fixed under `audit.corrected_status_columns=true` from v0.7: `get_rule_breakdown` then INFERS the category from `metadata["tier"]` / validator name / rule id when `category` is absent, so `AgentValidator`'s affordability results count as `personal` and its Tier-2 results as `thinking`. It is an inference, not a declaration — only categories the producer's tier labels can express populate, so a zero can still mean "no tier named this category". Rules whose category cannot be named go to `rules_uncategorised_total` / `rules_uncategorised_ids` in `run_integrity.json` (logged once per run), NOT into a plausible bucket: the flood `identity_rules` (`elevated_already` / `relocated_already`) are physical preconditions, and `AgentValidator:format` is a schema breach, and neither is one of the five governance categories. An explicit `category` still wins, so validators that set it are unaffected. `rules_physical_hit` is excluded from this list because it CAN be populated, but only when a domain explicitly sets the opt-in, default-OFF `global_config.governance.dispatch_domain_physical` flag, which routes through `PhysicalValidator` directly (`broker/core/skill_broker_engine.py`, ~line 775) and that validator's base class does set `metadata["category"]` (`broker/validators/governance/base_validator.py`). Under the default config (no dispatch flag), `rules_physical_hit` is zero for the same reason as the other four. Do not use these columns as a rule-category breakdown; use `failed_rules` / `rules_triggered` (rule-ID level, not category level) instead. |
| `mem_top_emotion`, `mem_top_source` | Per-row summary of the retrieved memories' dominant emotion/source. | In corpora where the upstream memory dict never populates real `emotion`/`source` values, this is the constant placeholder `"neutral"` / `"personal"` on every row, not a computed summary. | `broker/core/_audit_helpers.py`'s `_write_audit_trace` builds `memory_audit["memories"]` via `memory.get("emotion", "neutral")` and `memory.get("source", "personal")`; `broker/components/analytics/audit.py`'s `trace_to_csv_row` then takes the mode of those values. If the upstream memory records never carry real `emotion`/`source` keys, the default is what gets aggregated, indistinguishable in the CSV from a genuine unanimous mode. This is the same failure class the 2026-04-19 NW flood post-mortem documented (`broker/INVARIANTS.md` Invariant 2, born from this exact incident) and the reason `_SUSPICIOUS_COLUMN_DEFAULTS` in `audit.py` flags these two columns for sentinel-constancy detection. | Fixed under `audit.corrected_status_columns=true` from v0.7: an absent `emotion`/`source` key is written as `"unobserved"`, which no analysis can mistake for a unanimous observation. Observed values are untouched, so a run whose memory records carry real values reads identically under both settings. Otherwise mitigated only: `detect_audit_sentinels` / `AuditWriter.finalize()` WARN on suspicious constancy, but do not repair historical rows. Check the run's sentinel warnings (or `audit_summary.json`) before trusting these two columns for any given corpus. |
| Row-count parity between arms | Two experiment arms with the same agent/year/seed grid are expected to produce the same number of CSV rows. | Not guaranteed. A step whose LLM output fails to parse after retries returns `SkillOutcome.ABORTED` directly (`broker/core/skill_broker_engine.py`, the early return right after `_invoke_llm_with_retries`), before the function reaches its single `_write_audit_trace` call site later in the same method. An ABORTED step is therefore never written to the JSONL trace or the CSV. | Verified structurally: `_write_audit_trace` has exactly one call site in `skill_broker_engine.py`, and the ABORTED branch `return`s before reaching it. So an arm with more parse failures than the other silently has fewer audit rows, not more ABORTED rows — the asymmetry is invisible unless you cross-check row counts against the expected agent x year x seed grid. | Fixed under `audit.corrected_status_columns=true` from v0.7: the ABORTED branch emits a sentinel row (`status=ABORTED`, `executed_skill` empty, `execution_path=aborted`) before returning, so the count is conserved and the failure is visible rather than absent. `run_integrity.json` additionally records `audit_rows` / `audit_aborted_rows` / `audit_grid_rows` on every run, flag or no flag. For corpora without the flag, cross-check CSV row counts against the expected grid before comparing rejection/rate statistics between arms; do not assume equal row counts imply equal step counts. |

## Corrected status columns (`audit.corrected_status_columns`, v0.7)

Setting `global_config.audit.corrected_status_columns: true` makes the audit
plane report what the broker DID rather than what it approved. Default OFF;
YAML placement and precedence are in
`docs/references/yaml_configuration_reference.md`.

### The deterministic remap rule

`status` alone does not say what ran, because the REJECTED branch of
`broker/core/skill_broker_engine.py:process_step` has three exits. With the
flag ON, `execution_path` states which one the row took:

| `execution_path` | When | `executed_skill` | Relationship to `final_skill` |
|---|---|---|---|
| `approved` | `status` is `APPROVED` (first pass or after retries) and a simulation engine executed it | the approved skill | identical |
| `approved_no_engine` | `status` is `APPROVED` but the run wired NO simulation engine, so nothing executed — the broker records a pseudo-execution | the approved skill | identical |
| `rejected_default` | `status` is `REJECTED` and the domain's `governance.on_retry_exhausted` is `default` (the default) | the registry `default_skill` | **differs** — `final_skill` is the BLOCKED proposal |
| `rejected_proposal` | `status` is `REJECTED` and `on_retry_exhausted` is `keep_proposal` | the blocked proposal itself | identical |
| `fallback` | `status` is `REJECTED_FALLBACK` — the parser never produced a usable choice | the registry `default_skill` | **may differ** — `final_skill` usually already holds the registry default, but a domain whose per-agent-type parsing supplies its own `default_skill` (the `ma_agent_types.yaml` case) can leave a different name there. `executed_skill` is authoritative |
| `aborted` | the step's output never parsed at all; sentinel row, nothing executed | `""` | both empty |
| `not_executed` | a blocked proposal whose configured default skill is not in the registry, so nothing ran | `None` | n/a |
| `unknown` | a caller reached the audit writer without stating which branch ran | as written | undetermined — exclude these rows from executed-only analysis rather than guessing |

`rejected_default` is the only path where `final_skill` names an action that
never happened. Executed-only analysis should read `executed_skill`, not
`final_skill`, and can select the affected rows with
`execution_path == "rejected_default"`.

`approved_no_engine` is not a defect and does not need excluding — it is what a
run without a simulation engine looks like, and the multi-agent flood runner
(`examples/multi_agent/flood/run_unified_experiment.py`) is exactly such a run:
its agent state is advanced by lifecycle hooks, not by
`SkillBrokerEngine.simulation_engine`. The label exists so an analyst pooling
several domains can see which rows had an engine confirm the action and which
did not, instead of reading one `approved` and assuming both.

### Sentinel rows write `""` into numeric columns

An `ABORTED` sentinel row (and the flag-ON `ABORTED_EXCEPTION` row) writes an
empty string, never a zero, into every field it did not measure. Which
fields those are depends on what the retry loop had accumulated before the
abort: `llm_success`, `llm_retries`, `prompt_tokens`, `response_tokens` and
`num_ctx` carry REAL values whenever the stats dict holds them (the retry
loop seeds the first two and accumulates the token counts), and are `""`
only for keys the stats dict lacks; `context_utilization` and `mem_surprise`
are always `""` on a sentinel row. So a `True` in `llm_success` does not
prove a row is not a sentinel — use `status` / `execution_path` for that. A
zero in any of these would be a fabricated measurement of a call that did
happen, and it would silently drag any mean computed over the column.

The cost is that those columns are no longer uniformly numeric on a flag-ON
corpus. **Coerce before aggregating**: `pd.to_numeric(df["prompt_tokens"],
errors="coerce")` turns the sentinel cells into `NaN`, which `mean()` /
`sum()` skip. Reading the column without coercing gives pandas an `object`
dtype, and `.mean()` on it either raises or silently returns nothing usable
depending on the version.

### The four existing columns whose VALUES change

| Column | Flag OFF | Flag ON |
|---|---|---|
| `fallback_activated` | `approved_skill.approval_status == "REJECTED_FALLBACK"` — False on a plain-`REJECTED` row even though the registry default ran | derived from the executed skill: True on every path where a default stood in for the agent's choice |
| `rules_personal_hit`, `rules_social_hit`, `rules_thinking_hit`, `rules_semantic_hit` | read `metadata["category"]`, which the production `AgentValidator` never sets, so structurally zero | **INFERRED** from `metadata["tier"]` / validator name / rule id; an explicit `category` still wins. See the caveat below — these are inferences, not declarations |
| `mem_top_emotion`, `mem_top_source` | absent keys default to `"neutral"` / `"personal"`, indistinguishable from a unanimous observation | absent keys become `"unobserved"`; observed values are unchanged |
| row count | a step whose output never parsed leaves no row | that step gets an `ABORTED` sentinel row, so per-agent-year counts are conserved |

#### The `rules_*_hit` caveat: inferred, not declared

Under the flag these four counts are INFERRED from the tier label, the
validator name and the rule id — the emission site is deliberately not changed,
because giving `AgentValidator` an explicit `metadata["category"]` would alter
`rules_*_hit` with the flag OFF and break byte identity for every frozen
corpus. Two consequences the reader has to carry:

- **Only categories the producer's tiers can express will ever populate.** A
  bucket reading zero can mean "no rule of that category fired" OR "no tier
  label in this domain names that category". `social` / `physical` / `semantic`
  are commonly the second case.
- **Identity and precondition rules are reported as uncategorised, not
  personal.** The flood `identity_rules` (`elevated_already`,
  `relocated_already`) test whether the house is already elevated or the
  household already gone — physical preconditions, not statements about who the
  agent is. They are counted in `run_integrity.json` as
  `rules_uncategorised_total` / `rules_uncategorised_ids` (and logged once per
  run), never folded into `rules_personal_hit`. `AgentValidator:format` lands
  there too: a schema breach is not one of the five governance categories.

Read `rules_uncategorised_total` alongside the columns. An all-zero
`rules_*_hit` row with a non-zero uncategorised total means the rules fired and
their category could not be named — not that governance was quiet.

### Schema version under the flag

`AUDIT_SCHEMA_VERSION` stays `"2"` and pins the FLAG-OFF column set, which this
change leaves untouched — `broker/tests/test_audit_schema_golden.py` passes
unchanged, and the flag-OFF sidecar gains no key. The corrected set is a
strict superset written only on request, so it carries its own number:
`AUDIT_SCHEMA_VERSION_CORRECTED = "3"`. Reading `"2"` on a corrected CSV would
apply the wrong contract — `fallback_activated` keeps its name and answers a
different question there.

Four artifacts carry the stamp. Three are resolved from the same signal
(`execution_path` present in the written fieldnames), so they cannot disagree:

| Artifact | Flag OFF | Flag ON | Resolved from |
|---|---|---|---|
| `<agent_type>_governance_audit.schema.json` (sidecar) | `"2"` | `"3"` + `corrected_status_columns: true` | the fieldnames just written |
| `audit_summary.json` | `"2"` | `"3"` | the same detection, restamped in `GenericAuditWriter.finalize` |
| `run_integrity.json` → `framework_provenance.audit_schema_version` | `"2"` | `"3"` | `audit_coverage`'s header read of the CSV |
| `raw/<agent_type>_traces.jsonl` → `_metadata.audit_schema_version` | `"2"` | `"2"` | the base constant, always |

**The JSONL stamp is the documented exception.** That record is written when
the first trace for an agent type arrives, and the CSV column set does not
exist until every trace is in (`compute_csv_fieldnames` unions keys across all
rows) — so it cannot be resolved there without guessing from one row. Treat the
sidecar, `audit_summary.json` and `run_integrity.json` as authoritative for
which column contract a CSV follows; a `"2"` in the JSONL `_metadata` is the
base constant, not a claim about the CSV beside it.

Every corrected column is key-gated exactly as `executed_skill_columns` (F3),
`initial_proposal_columns` (P0-1a), `advise_columns` (P0-1c) and
`param_columns` (6W-B6) are, so a rerun of a published corpus with the flag
absent reproduces byte-for-byte. Turning the flag ON produces a different
artifact on purpose.

### Reporting side (no flag needed)

`run_integrity.json` gains, on every run, `framework_provenance`
(framework version, audit schema version, git short hash) and audit coverage:
`audit_rows`, `audit_aborted_rows`, `audit_agents`, `audit_years`,
`audit_grid_rows`, `audit_rows_missing_vs_grid`, `configured_grid_rows`,
`audit_rows_missing_vs_configured_grid`, `parse_layer_distribution`,
`parse_layer_digit_share`, `parse_layer_default_share`,
`audit_coverage_by_file`, `audit_aborted_rows_source`,
`audit_expectation_unmatched_keys` (present only when an expectation key named
no audit CSV — without it, a misspelled agent type reads as "not measured"),
plus `audit_corrected_status_columns_resolved`
(the flag the engine actually read), `audit_sentinel_write_failures` and the
`rules_uncategorised_*` pair. These read the audit CSV and write only to
`run_integrity.json`, so no CSV byte changes.
`broker.tools.readiness_report` surfaces the same values under
`audit_coverage` / `framework_provenance` / `governance_profile`.

`rules_uncategorised_total` / `rules_uncategorised_ids` are populated only on a
run with the flag ON. With the flag OFF the total is `0` — not because nothing
was uncategorised, but because with no inference running EVERYTHING is, which
the known-limitation table above already states once for all such runs. A
per-run tally repeating it would be a number that is always 100%.

`audit_aborted_rows` is counted from the CSV `status` column and nothing else
(`audit_aborted_rows_source` records that). One consequence to carry: with the
flag OFF, the F1 exception sentinel written by
`ExperimentRunner._write_aborted_trace` has its `ABORTED_EXCEPTION` at the top
level of the trace while the CSV's `status` cell is read off `approved_skill`,
so that cell says `UNKNOWN` and the row is **not** counted here. Those rows are
countable only from `raw/*_traces.jsonl`, where `decision_source == "exception"`
survives. With the flag ON the sentinel writes a real `ABORTED_EXCEPTION`
status and the CSV count is complete.

Two grids, and the difference matters:

- `audit_grid_rows` is the OBSERVED `agents x years` cross-product. It can only
  find holes inside what was observed — a run cut short at year 9 of 13
  observes a 9-year grid and reports nothing missing.
- `configured_grid_rows` is what the RUNNER was configured to produce
  (`expected_agents x expected_years`, threaded from `ExperimentRunner` and
  `run_flood.py`). `audit_rows_missing_vs_configured_grid` is that minus the
  rows, and it is the number that catches truncation. Both are `null` when no
  caller supplied an expectation — a guessed expectation would false-alarm on
  exactly the runs this exists to certify.

Neither missing count is a verdict. **It is a number to explain**: a domain
where agents leave the active set (a relocated flood household) legitimately
produces fewer rows than `agents x years`, and nothing here subtracts exits on
the domain's behalf — doing so would hide the truncation case. There is
deliberately no `row_count_conserved` boolean: it would restate
`audit_rows_missing_vs_configured_grid == 0` while dropping that caveat, so a
legitimate agent exit read as a bare `False` that looks like a verdict.

Coverage is computed PER audit CSV (keyed by file stem in
`audit_coverage_by_file`) as well as pooled, because a two-agent-type run
pooled into one grid multiplies one type's agents by the other type's years and
reports a fictional expectation. `parse_layer_default_share` counts PARSE
layers whose name contains `default`; a governance `REJECTED` -> registry-default
substitution is not a parse layer and never appears there — select those rows
with `execution_path == "rejected_default"` instead.

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
| Per-attempt retry sequence | yes, under `audit.initial_proposal_columns` (`attempt_skills`) | yes | no |
| Executed registry-default name on `REJECTED` | yes, under `audit.executed_skill_columns` or `audit.corrected_status_columns` (`executed_skill`) | yes | no |
| Which remap rule produced the executed action | yes, under `audit.corrected_status_columns` (`execution_path`) | yes | no |
| Steps whose output never parsed | yes, under `audit.corrected_status_columns` (an `ABORTED` sentinel row) | yes | no |

## Analyst Checklist

| Step | Check |
|---|---|
| 1 | Read `<agent_type>_governance_audit.schema.json` before reading the CSV. |
| 2 | Confirm `audit_schema_version` and the CSV header match the sidecar. |
| 3 | Treat JSONL as canonical for raw text, validator metadata, and internals. |
| 4 | Use CSV for flat final-action, final-status, retry, rule-union, and construct analyses. |
| 5 | Exclude reserved/dead columns from statistical analysis. |
| 5b | Check the sidecar for `corrected_status_columns`. When absent, apply the known-limitation table above before reading `fallback_activated`, `rules_*_hit`, `mem_top_*`, or any row count. When present, read `executed_skill` (not `final_skill`) for executed-only analysis. |
| 6 | For recovered artifacts, cite that `recover_csv_from_jsonl` shares `trace_to_csv_row` with the live writer. |
