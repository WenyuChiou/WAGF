# WAGF audit trace schema

Two artefacts per run directory:

1. `household_governance_audit.csv` — flat per-decision row table.
   Written by
   `broker/components/analytics/audit.py:GenericAuditWriter._export_csv`
   (around lines 353-579).
2. `raw/<domain>_traces.jsonl` — one JSON record per agent decision
   with full skill_proposal / approved_skill / memory / cognitive
   payload. Used by deeper diagnostics.

## household_governance_audit.csv columns

### Identity / outcome (always present)

| Column | Type | Meaning |
|--------|------|---------|
| `step_id` | int | monotonic counter |
| `agent_id` | str | agent identifier |
| `year` | int | simulation year |
| `proposed_skill` | str | skill the agent proposed |
| `final_skill` | str | skill actually executed (after governance + retry) |
| `status` | str | APPROVED / REJECTED / FALLBACK |
| `fallback_activated` | bool | whether a domain-default fallback fired |
| `retry_count` | int | LLM retry attempts on this decision |
| `format_retries` | int | retries due to format-only failures |
| `validated` | bool | whether the proposal passed all validators |
| `failed_rules` | str (csv) | list of validator rules that triggered |

### Construct labels (PMT / WSA-ACA, dynamic per domain)

| Column | Meaning |
|--------|---------|
| `construct_TP_LABEL` | flood: threat-perception label (VL/L/M/H/VH) |
| `construct_CP_LABEL` | flood: coping-perception label |
| `construct_WSA_LABEL` | irrigation: water-shortage appraisal |
| `construct_ACA_LABEL` | irrigation: adaptive-capacity appraisal |
| `construct_completeness` | float (0-1) |

### Memory audit

| Column | Meaning |
|--------|---------|
| `mem_retrieved_count` | int — how many memory items entered the prompt |
| `mem_top_emotion` | str — emotion of the top-ranked item (critical / major / positive / shift / observation / routine) |
| `mem_top_source` | str — personal / community / abstract |
| `mem_surprise` | float — surprise value (0 if dormant) |
| `mem_cognitive_system` | str — SYSTEM_1 / SYSTEM_2 (only with universal engine) |

### Social audit (currently dormant in single-agent flood)

| Column | Meaning |
|--------|---------|
| `social_gossip_count` | int |
| `social_elevated_neighbors` | int |
| `social_neighbor_count` | int |
| `social_network_density` | float |

### Cognitive audit (dormant unless `--memory-engine universal`)

| Column | Meaning |
|--------|---------|
| `cog_system_mode` | str |
| `cog_surprise_value` | float |
| `cog_is_novel_state` | bool |
| `cog_margin_to_switch` | float |

### Rule audit (per-validator hits)

| Column | Meaning |
|--------|---------|
| `rules_evaluated_count` | int |
| `rules_triggered` | str (csv) |
| `rules_personal_hit` | int |
| `rules_social_hit` | int |
| `rules_thinking_hit` | int |
| `rules_physical_hit` | int |
| `rules_semantic_hit` | int |
| `hallucination_types` | str (csv) |
| `condition_0_matched`, `condition_0_rule`, … | dynamic, one pair per rule |

## raw/<domain>_traces.jsonl record shape

Top-level keys per record (set by ExperimentRunner):

```python
{
  "run_id": str,
  "step_id": int,
  "timestamp": str (ISO 8601),
  "year": int,
  "seed": int,
  "agent_id": str,
  "model": str,
  "decision_source": "llm",
  "validated": bool,
  "input": str,                    # full prompt sent to LLM
  "raw_output": str,               # LLM response verbatim
  "context_hash": str,
  "memory_pre": list[dict],        # memories retrieved BEFORE decision
  "memory_post": list[dict],       # memories AFTER decision (incl. inserts)
  "memory_audit": dict,            # retrieval bookkeeping
  "environment_context": dict,     # state passed to prompt
  "state_before": dict,
  "state_after": dict,
  "skill_proposal": {              # what the LLM proposed
    "skill_name": str,
    "agent_id": str,
    "agent_type": str,
    "reasoning": dict|str,         # parsed JSON or repr
    "confidence": float,
    "raw_output": str,
    "parsing_warnings": list,
    "parse_layer": str,
    "parse_confidence": float,
    "construct_completeness": float,
    "magnitude_pct": float,
    "magnitude_fallback": bool,
  },
  "approved_skill": {              # what governance accepted
    "skill_name": str,
    "agent_id": str,
    "agent_type": str,
  },
  "execution_result": dict,
  "outcome": dict,
  "retry_count": int,
  "format_retries": int,
  "llm_stats": dict,
  "agent_type": str,
  "validation_issues": list[dict],     # rules that triggered, per retry
  "validation_warnings_list": list,
}
```

## Construct label parsing inside `skill_proposal.reasoning`

The `reasoning` field is sometimes a string repr of a dict. Parse with
`json.loads` first, then fall back to `ast.literal_eval`. Common keys:

- `WSA_LABEL`, `WSA_REASON` (irrigation)
- `ACA_LABEL`, `ACA_REASON` (irrigation)
- `TP_LABEL`, `TP_REASON` (flood)
- `CP_LABEL`, `CP_REASON` (flood)

Use this for IBR computation when the audit CSV's `construct_*` columns
are missing or empty.

## Sentinel columns to flag

Per `broker/INVARIANTS.md` Invariant 4, the following columns are
RESERVED (constant by design until V2):

- `cog_is_novel_state` (False until `memory_engine=universal`)
- `cog_surprise_value` (0.0 until V2)
- `cog_margin_to_switch` (0.0 until V2)

Any OTHER column that appears constant across ≥80% of rows in
production data is a finding (not a feature).

`mem_top_emotion = "neutral"` constant was the 2026-04-19 memory
pipeline leak. If that pattern reappears, escalate immediately.
