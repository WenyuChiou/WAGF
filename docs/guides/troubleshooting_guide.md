# WAGF Troubleshooting Guide

This guide covers common errors, their root causes, and step-by-step solutions for
the Water Agent Governance Framework (WAGF). Each section follows the structure:
**Symptom** (what you see), **Root Causes** (why it happens), **Diagnosis** (how to
investigate), and **Solution** (how to fix it).

> **Cross-reference**: For YAML configuration syntax, see the
> [YAML Configuration Reference](./yaml_configuration_reference.md).

---

## Table of Contents

1. [Governance Validation Errors](#1-governance-validation-errors)
2. [LLM Output Parsing Errors](#2-llm-output-parsing-errors)
3. [Ollama Connection Issues](#3-ollama-connection-issues)
4. [Memory System Issues](#4-memory-system-issues)
5. [Multi-Agent Specific Issues](#5-multi-agent-specific-issues)
6. [Debug Workflow](#6-debug-workflow)

---

## 1. Governance Validation Errors

The governance layer validates every LLM decision before it reaches the simulation
engine. When validation fails, the broker retries the LLM up to `max_retries` times
(default 3, configurable in `global_config.governance.max_retries`). If all retries
are exhausted, the decision is REJECTED and a fallback skill executes instead.

### 1.1 "Max retries reached" (Governance Fallout)

**Symptom**

You see these log lines in sequence:

```
[Governance:Retry] Attempt 1 failed validation for agent_42. Errors: [...]
[Governance:Retry] Attempt 2 failed validation for agent_42. Errors: [...]
[Governance:Retry] Attempt 3 failed validation for agent_42. Errors: [...]
[Governance:Fallout] CRITICAL: Max retries (3) reached for agent_42.
  - Final Choice Rejected: 'elevate_home'
  - Blocked By: ['Precondition failed: ...']
  - Ratings: TP_LABEL=H | SE_LABEL=L
  - Agent Motivation: "I want to protect my house..."
  - Action: Proceeding with 'do_nothing' (Result: REJECTED)
```

The broker logs `[Governance:Exhausted]` and the audit CSV shows `status=REJECTED`
or `status=REJECTED_FALLBACK`.

**Root Causes**

1. **Deterministic constraint violation**: The agent's static attributes (income,
   property value, flood zone) make a skill permanently ineligible. No amount of
   retrying will change the outcome because the blocking rule depends on agent state,
   not LLM output. The broker detects this via the EarlyExit mechanism and logs:
   ```
   [Governance:EarlyExit] Deterministic rules blocked retry 1 for agent_42:
   ['affordability_check']. Skipping remaining retries.
   ```

2. **Persistent construct mismatch**: The LLM consistently outputs reasoning that
   triggers a thinking/coherence rule. For example, a `low_coping` rule blocks
   `elevate_home` when the Coping Appraisal label is "L" or "VL", and the LLM keeps
   producing that same appraisal across retries.

3. **Overly restrictive governance rules**: The YAML-defined rules have conditions
   so tight that the LLM has almost no valid option space. Multiple rules may combine
   to block every non-default skill.

4. **Prompt-governance misalignment**: The prompt anchors encourage a behavior that
   governance rules block. For example, a prompt emphasizing "you are risk-averse"
   combined with rules that block `do_nothing` for high-threat agents creates a
   contradiction.

**Diagnosis**

1. Open the audit CSV (`<output_dir>/<agent_type>_governance_audit.csv`) and filter
   for `validated=False`. Check the `failed_rules` and `error_messages` columns to
   identify which rules are blocking.

2. Check if the same `failed_rules` appear across all retry attempts in the JSONL
   trace file (`<output_dir>/raw/<agent_type>_traces.jsonl`). If yes, the rule is
   likely deterministic.

3. Review the governance summary JSON (`<output_dir>/audit_summary.json` and the
   `GovernanceAuditor.print_summary()` output) for the top rule violations:
   ```
   GOVERNANCE AUDIT SUMMARY
   ================================================
     Total Interventions: 47
     Top Rule Violations (ERROR):
     - affordability_check: 23 hits
     - low_coping: 12 hits
   ```

4. Cross-reference the blocking rule ID with your `agent_types.yaml` to understand
   the rule's conditions, thresholds, and blocked skills.

**Solution**

- **For deterministic blockers** (affordability, eligibility): These are working as
  designed. Ensure your agent population is realistic. If too many agents are blocked,
  review the threshold values in governance rules:
  ```yaml
  governance:
    default:
      household:
        identity_rules:
          - id: affordability_check
            precondition: cannot_afford_elevation
            blocked_skills: [elevate_home]
            level: ERROR
            message: "Income too low for elevation"
  ```

- **For construct-based blockers**: Adjust the `thinking_rules` thresholds, or change
  the rule `level` from `ERROR` (blocking, triggers retry) to `WARNING` (logged but
  non-blocking):
  ```yaml
  thinking_rules:
    - id: low_coping
      construct: CA_LABEL
      when_above: [VL, L]
      blocked_skills: [elevate_home]
      level: WARNING  # Changed from ERROR to WARNING
  ```
  **Important**: WARNING-level rules produce 0% behavior change for small LLMs. Only
  ERROR-level rules (BLOCK + retry) reliably alter agent behavior.

- **Increase max_retries** for construct-based rules where the LLM may eventually
  produce a different appraisal:
  ```yaml
  global_config:
    governance:
      max_retries: 5  # Default is 3
  ```

- **Reduce max_reports_per_retry** if the intervention feedback overwhelms the LLM's
  context window:
  ```yaml
  global_config:
    governance:
      max_reports_per_retry: 2  # Default is 3
  ```

### 1.2 "Precondition failed"

**Symptom**

```
[Precondition] elevate_home: ["Precondition failed: 'not already_elevated' (field is True)"]
```

Or in the audit CSV: `failed_rules=precondition_violation`.

**Root Causes**

1. The skill has a `preconditions` field in the skill registry YAML that checks agent
   state booleans. For example, `elevate_home` requires `not already_elevated`, but
   the agent's state has `already_elevated=True`.

2. The agent's state was not reset correctly after a previous action (e.g., a prior
   elevation should have set `already_elevated=True`, which is correct and expected).

3. The precondition field name in the YAML does not match the field name in the agent
   state dictionary (case-sensitive mismatch).

**Diagnosis**

1. Check the skill registry YAML for the skill's preconditions:
   ```yaml
   skills:
     - skill_id: elevate_home
       preconditions:
         - "not already_elevated"
         - "is_homeowner"
   ```

2. Check the agent's `state_before` in the JSONL trace to verify the field values.

3. Ensure the simulation engine sets the correct state fields after skill execution.

**Solution**

- If the precondition is correct, this is working as designed. The LLM should choose
  a different skill.
- If the precondition field name has a typo, fix it in the skill registry YAML.
- If the state field is not being set correctly, check your simulation engine's
  `execute_skill()` implementation.

### 1.3 "Construct missing" / Missing Required Constructs

**Symptom**

```
[Broker:Retry] Missing required constructs ['TP_LABEL', 'CA_LABEL'] for agent_42
  (household), attempt 1/2
```

Or in the adapter log:

```
[Adapter:Diagnostic] Warning: Missing constructs for 'household':
  ['TP_LABEL', 'CA_LABEL', 'SE_LABEL']
```

**Root Causes**

1. **LLM did not output the expected JSON keys**: The model's response omitted
   appraisal constructs that the `parsing.constructs` block in `agent_types.yaml`
   expects. This is common with smaller models (1b-4b parameter) that struggle with
   structured output.

2. **Construct keyword mismatch**: The LLM used a different key name (e.g.,
   `"threat_perception"` instead of matching the configured `keywords` for `TP_LABEL`).

3. **Regex extraction failure**: The construct's `regex` pattern in the YAML config
   does not match the LLM's output format. For example, the regex expects `(VL|L|M|H|VH)`
   but the model outputs `"Medium"` without a normalization mapping.

4. **Prompt template mismatch**: The prompt does not instruct the LLM to output the
   required construct fields, or uses different names than what the parser expects.

**Diagnosis**

1. Check the `raw_output` column in the audit CSV to see exactly what the LLM produced.
2. Check `parsing.constructs` in `agent_types.yaml` and verify keyword lists match
   the LLM's output key names.
3. Check if a `normalization` mapping is defined for the agent type to handle common
   LLM variations:
   ```yaml
   parsing:
     normalization:
       "very low": "VL"
       "low": "L"
       "medium": "M"
       "moderate": "M"
       "high": "H"
       "very high": "VH"
   ```

**Solution**

- Add missing keyword synonyms to the construct's `keywords` list.
- Add a `normalization` mapping for common LLM output variations.
- Ensure the prompt template explicitly lists the expected JSON keys. Use the
  `response_format` configuration to generate clear output instructions:
  ```yaml
  shared:
    response_format:
      start_delimiter: "<<<DECISION_START>>>"
      end_delimiter: "<<<DECISION_END>>>"
  ```
- For persistently non-compliant models, consider using the `preprocessor` config
  to clean output before parsing:
  ```yaml
  parsing:
    preprocessor:
      type: smart_repair
  ```

### 1.4 "Key collision in validation context"

**Symptom**

```
[Governance:Diagnostic] Key collision in validation context: {'year', 'flood_zone'}.
  env_context takes precedence. Consider using distinct key names.
```

**Root Causes**

The agent's `state` dictionary and the environment `env_context` dictionary both
contain keys with the same name. When flattened into the `validation_context`, one
overwrites the other. This is a common source of subtle bugs where validators read
the wrong value.

**Diagnosis**

Check your experiment's `env_context` and agent state dictionaries for overlapping
key names.

**Solution**

Rename keys to be distinct. For example, use `env_year` or `simulation_year` in the
environment context instead of `year` if the agent state also has `year`.

The framework provides structured access via `validation_context["agent_state"]` and
`validation_context["env_state"]` for validators that need to disambiguate. Prefer
these nested accessors over flat key lookups in custom validators.

### 1.5 "Output schema violation"

**Symptom**

```
[OutputSchema] elevate_home: ["Field 'magnitude_pct': 150 > maximum 100"]
```

**Root Causes**

The LLM output a numeric value outside the bounds defined in the skill's
`output_schema` in the skill registry YAML.

**Solution**

The framework already clamps numeric values via `_parse_numeric_value()` in the
model adapter. If you see this error, check that:
1. The `output_schema` bounds in the skill registry match the `response_format`
   numeric field bounds in `agent_types.yaml`.
2. The numeric field's `min`/`max` are realistic for your domain.

### 1.6 "Composite conflict" (Multi-Skill)

**Symptom**

```
[Multi-Skill] agent_42 | Composite conflict: ["Skills 'elevate_home' and
  'relocate' are mutually exclusive"]
```

**Root Causes**

In multi-skill mode, the agent proposed two skills that are listed in each other's
`conflicts_with` field in the skill registry.

**Solution**

This is working as designed. The secondary skill is silently dropped. If you want to
allow the combination, remove the `conflicts_with` entry from the skill registry YAML.

---

## 2. LLM Output Parsing Errors

The `UnifiedAdapter` in `model_adapter.py` uses a multi-layer parsing strategy:
enclosure extraction, JSON parsing, keyword search, digit extraction, and finally
a default fallback. Errors here mean the LLM's output could not be converted into
a valid `SkillProposal`.

### 2.1 "Unparsable output" / Parse Error After Retries

**Symptom**

```
[LLM:Error] Model returned unparsable output after retries for agent_42.
```

Or:

```
[Broker:Retry] Empty/Null response received (Attempt 1/2)
```

The audit CSV shows `status=REJECTED_FALLBACK` and `parse_layer=default`.

**Root Causes**

1. **Empty LLM response**: The model returned an empty string or only `<think>`
   tokens with no actual decision content. Common with Qwen3 models that sometimes
   produce only reasoning without a final answer.

2. **No recognizable delimiter**: The response did not contain `<<<DECISION_START>>>`
   / `<<<DECISION_END>>>` or `<decision>` / `</decision>` tags, AND no parseable
   JSON block was found.

3. **Malformed JSON**: The LLM attempted JSON but produced invalid syntax (unclosed
   braces, trailing commas, double-braces). The adapter's repair logic (`{{` to `{`,
   trailing comma removal) could not fix it.

4. **Strict mode rejection**: When `strict_mode: true` (default), the adapter refuses
   to extract decisions from stray digits in reasoning text. This prevents false
   positives but means a poorly formatted response returns `None`.

**Diagnosis**

1. Check `raw_output` in the JSONL trace or audit CSV.
2. Look at the `parse_layer` column: empty means total parse failure; `"default"`
   means all layers failed and the fallback skill was used.
3. Check `format_retries` column: if > 0, the broker attempted structural retries
   before giving up.
4. Review `parsing_warnings` for specific adapter diagnostics:
   - `"STRICT_MODE: Rejected digit extraction (3). Will trigger retry."` means a
     digit was found but strict mode prevented its use.
   - `"STRICT_MODE: Failed to parse any valid decision for agent 'agent_42'"` means
     the adapter returned `None` to trigger the broker's retry mechanism.

**Solution**

- **Improve the prompt**: Ensure the prompt template explicitly shows the expected
  JSON format with delimiters. Use `response_format` configuration:
  ```yaml
  shared:
    response_format:
      start_delimiter: "<<<DECISION_START>>>"
      end_delimiter: "<<<DECISION_END>>>"
      fields:
        - key: decision
          type: integer
          required: true
        - key: magnitude_pct
          type: numeric
          min: 1
          max: 100
  ```

- **Use a preprocessor** for models that produce markdown code blocks or unusual
  formatting:
  ```yaml
  parsing:
    preprocessor:
      type: smart_repair
  ```

- **Disable strict mode** as a last resort (not recommended for production):
  ```yaml
  parsing:
    strict_mode: false  # Allows digit extraction from reasoning text
  ```

- **Increase format retries**: The broker already retries 2 times for format issues
  before entering governance validation. The LLM receives a message:
  `"Response was empty or unparsable. Please output a valid JSON decision."`

### 2.2 "Choice not in skill registry" / Hallucinated Action

**Symptom**

The LLM outputs a skill name that does not exist in the registry or the
`agent_types.yaml` action list. The adapter's alias map cannot resolve it.

In the audit CSV: `proposed_skill` shows the hallucinated name, `final_skill` shows
the fallback.

**Root Causes**

1. **LLM hallucinated an action**: The model invented an action not in the option
   list (e.g., "build_seawall" when only "elevate_home", "buy_insurance", "relocate",
   and "do_nothing" exist).

2. **Alias map incomplete**: The LLM used a reasonable abbreviation or synonym that
   is not listed in the action's `aliases` field in `agent_types.yaml`.

3. **Skill map mismatch**: The LLM output a number that is not in the current
   `skill_map` (e.g., "5" when only options 1-4 exist).

**Diagnosis**

1. Check `raw_output` for the exact text the LLM produced.
2. Check your `agent_types.yaml` for the action definitions and their aliases.
3. Check `parsing_warnings` for messages like `"Default skill 'do_nothing' used."`

**Solution**

- Add common abbreviations to the action's `aliases` list:
  ```yaml
  actions:
    - id: buy_insurance
      aliases: [insurance, insure, BI, buy_ins, "Buy Insurance"]
      description: "Purchase flood insurance"
  ```

- Ensure the prompt lists options clearly with numbered choices. The framework
  generates `options_text` and `valid_choices_text` automatically from the action
  definitions.

- For persistent hallucination issues, add the hallucinated name as an alias mapping
  to the correct skill if it makes semantic sense.

### 2.3 "Parse layer: default" / All Parsers Failed

**Symptom**

The audit CSV shows `parse_layer=default` or `parse_layer=digit_fallback`. The
`parse_confidence` is 0.20 (lowest).

**Root Causes**

All parsing layers (enclosure, JSON, keyword, digit) failed to extract a valid
decision. The adapter fell back to the `default_skill` from the parsing configuration.

This often happens when:
- The LLM produced a long narrative response with no structured output.
- The model output is in a language different from what the parser expects.
- The model echoed the entire prompt back instead of responding.

**Diagnosis**

1. Check `parse_confidence` values across your run. If most agents have confidence
   < 0.50, the model may be fundamentally incompatible with your prompt format.
2. Check `construct_completeness` -- a value of 0.0 means zero expected constructs
   were found.

**Solution**

- Switch to a more instruction-following model. Models with 4b+ parameters generally
  produce better structured output than 1b models.
- Simplify the prompt: reduce the number of required output fields.
- Use the `enclosure` pattern (delimiters) which is the most robust extraction method.

### 2.4 Invalid Label Values

**Symptom**

```
[Broker:Retry] Missing required constructs ['TP_LABEL'] for agent_42 (household),
  attempt 1/2
```

The GovernanceAuditor reports `invalid_label_retries > 0`.

**Root Causes**

A `_LABEL` construct field contains an invalid value like `"VL/L/M/H/VH"` (the
model echoed the allowed values list) instead of a single valid label.

**Solution**

- Add the `_is_list_item()` guard's list delimiters to your config if the model uses
  unusual separators:
  ```yaml
  parsing:
    list_delimiters: ['/', '|', '\\']
  ```
- Ensure your normalization map handles common edge cases.
- The adapter already handles this with `proximity_window`-based extraction, but very
  small models may still echo option lists. Increase `proximity_window` in the parsing
  config if labels are found far from their keywords:
  ```yaml
  parsing:
    proximity_window: 50  # Default is 35 characters
  ```

---

## 3. Ollama Connection Issues

WAGF uses Ollama as the default local LLM provider. The framework communicates with
Ollama via its HTTP API at `http://localhost:11434/api/generate`.

### 3.1 Connection Refused

**Symptom**

```
[LLM:Direct] Model 'gemma3:4b' connection refused. Is Ollama running at
  http://localhost:11434/api/generate?
```

Or:

```
[LLM:Error] Connection to Ollama failed for 'gemma3:4b': ConnectionRefusedError
```

**Root Causes**

1. Ollama is not running.
2. Ollama is running on a different port or host.
3. A firewall is blocking the connection.

**Solution**

1. Start Ollama: `ollama serve` (or check if it's running as a system service).
2. Verify Ollama is accessible: `curl http://localhost:11434/api/tags`
3. If using a non-default port, set the `OLLAMA_HOST` environment variable.

### 3.2 Model Not Found

**Symptom**

```
[LLM:Direct] Model 'gemma3:4b' HTTP Error 404: model not found
```

**Root Causes**

The requested model is not pulled/available in your local Ollama installation.

**Solution**

Pull the model first:
```bash
ollama pull gemma3:4b
```

List available models:
```bash
ollama list
```

### 3.3 Context Length Exceeded

**Symptom**

The model produces truncated or nonsensical output. The audit CSV shows
`context_utilization` values close to or exceeding 1.0. You may see warnings about
prompt tokens exceeding `num_ctx`.

**Root Causes**

The combined prompt (system instructions + agent context + memory + retry feedback)
exceeds the model's configured context window (`num_ctx`).

**Diagnosis**

1. Check the `prompt_tokens` and `num_ctx` columns in the audit CSV.
2. Calculate utilization: `context_utilization = prompt_tokens / num_ctx`.
3. Values above 0.85 indicate risk; values above 1.0 mean truncation occurred.

**Solution**

- Increase `num_ctx` in your LLM configuration:
  ```yaml
  global_config:
    llm:
      num_ctx: 32768  # Default is 16384
  ```
  Note: Larger context windows require more GPU memory.

- Reduce prompt length by:
  - Decreasing memory retrieval count (`top_k` in memory config).
  - Reducing `max_reports_per_retry` to limit governance feedback size.
  - Shortening the prompt template.
  - Using `max_gossip` to limit social context in multi-agent runs.

### 3.4 Timeout Issues

**Symptom**

```
[LLM:Direct] Model 'llama3.1:70b' timed out after 120s. Consider increasing timeout
  for this model.
```

**Root Causes**

Large models (27b, 30b, 32b, 70b) need more time to generate responses, especially
on CPU or with limited GPU memory.

**Solution**

- The framework auto-detects large models and applies `timeout_large_model` (default
  600s). If your model is not detected, add its size pattern:
  ```yaml
  global_config:
    llm:
      timeout: 120              # Standard models
      timeout_large_model: 900  # Large models
      large_model_patterns: ["27b", "30b", "32b", "70b", "72b"]
  ```

- For custom model names without standard size suffixes, increase the base timeout:
  ```yaml
  global_config:
    llm:
      timeout: 300
  ```

### 3.5 Empty Content from LLM

**Symptom**

```
[LLM:Retry] Model 'gemma3:4b' returned truly empty content. Retrying...
[LLM:Error] Model 'gemma3:4b' returned empty content after 2 attempts.
```

The GovernanceAuditor reports `empty_content_retries` and/or
`empty_content_failures` > 0.

**Root Causes**

1. The model ran out of tokens (`num_predict` too low).
2. GPU memory pressure caused the model to produce empty output.
3. For Qwen3 models: the response contained only `<think>` tokens with no actual
   JSON decision.

**Solution**

- Increase `num_predict`:
  ```yaml
  global_config:
    llm:
      num_predict: 2048  # Default is -1 (unlimited) for LLMConfig, but 2048 for direct API
  ```
- For Qwen3 models, the framework automatically appends `/no_think` and strips
  thinking tokens. If issues persist, increase `max_retries` in LLM config:
  ```yaml
  global_config:
    llm:
      max_retries: 4  # Default is 2
  ```

---

## 4. Memory System Issues

WAGF supports multiple memory engines: `window` (simple sliding window),
`humancentric` (working + long-term with consolidation), `hierarchical` (deprecated),
and `importance` (deprecated).

### 4.1 Memory Not Retrieving Expected Events

**Symptom**

The agent's prompt does not include a recent important event (e.g., a flood that
happened last year). The `memory_pre` field in the audit trace is empty or contains
irrelevant memories.

**Root Causes**

1. **Window engine with small window_size**: The `WindowMemoryEngine` uses a fixed
   sliding window (default 3). Events older than `window_size` steps are dropped.

2. **Memory not added**: The experiment layer did not call `memory_engine.add_memory()`
   after the event occurred.

3. **HumanCentric consolidation threshold**: Memories below the arousal/importance
   threshold are not promoted from working memory to long-term storage and may be
   evicted.

4. **Wrong agent_id**: Memory was added with a different agent_id than the one used
   for retrieval.

**Diagnosis**

1. Check the `mem_retrieved_count` column in the audit CSV. If 0, no memories were
   retrieved.
2. Check the `memory_pre` and `memory_post` fields in the JSONL trace for the
   specific agent.
3. For HumanCentric engines, check `mem_retrieval_mode` and `mem_top_source`.

**Solution**

- Increase window size for WindowMemoryEngine:
  ```yaml
  global_config:
    memory:
      window_size: 10  # Default is 3
  ```

- For HumanCentric engines, lower the consolidation threshold to retain more
  memories:
  ```yaml
  global_config:
    memory:
      consolidation_threshold: 0.4  # Default is 0.6
  ```

- Ensure your experiment code adds memories with the correct agent_id and metadata:
  ```python
  memory_engine.add_memory(
      agent_id=agent.agent_id,
      content="Experienced major flood in Year 5 (depth: 3ft)",
      metadata={"source": "flood_event", "year": 5, "importance": 0.9}
  )
  ```

### 4.2 Unknown Memory Engine Type

**Symptom**

```
ValueError: Unknown memory engine type: 'advanced'. Available engines: hierarchical,
  humancentric, importance, window. Register custom engines with
  MemoryEngineRegistry.register().
```

**Root Causes**

The `engine` field in your memory configuration specifies a type that is not
registered in the `MemoryEngineRegistry`.

**Solution**

Use one of the supported engine types:
- `window` -- Simple sliding window (default, best for baselines)
- `humancentric` -- Working + long-term with emotional consolidation (recommended
  for production)
- `importance` -- Deprecated, use humancentric
- `hierarchical` -- Deprecated, use humancentric

Or register a custom engine:
```python
from broker.components.memory_registry import MemoryEngineRegistry
MemoryEngineRegistry.register("my_engine", MyCustomEngine)
```

### 4.3 Consolidation Not Triggering

**Symptom**

In long runs, agents only have recent memories and no long-term memories. The
`mem_retrieval_mode` is always `"working"` and never `"longterm"`.

**Root Causes**

1. **Consolidation probability too low**: The `consolidation_probability` parameter
   controls how likely it is that a memory is promoted during each consolidation
   check.

2. **Reflection interval too high**: Reflection (which triggers consolidation) only
   runs every `N` steps. If `N` is larger than your run length, consolidation never
   triggers.

3. **Importance scores too low**: Memories need to exceed the `consolidation_threshold`
   to be promoted. If all events have low importance, nothing gets consolidated.

**Solution**

- Adjust consolidation parameters:
  ```yaml
  global_config:
    memory:
      consolidation_threshold: 0.5    # Lower = more memories consolidated
      consolidation_probability: 0.8  # Higher = more frequent consolidation
    reflection:
      interval: 1  # Reflect every step (default)
  ```

- Ensure high-importance events are tagged with appropriate metadata when added to
  memory.

---

## 5. Multi-Agent Specific Issues

Multi-agent simulations add social graphs, phased execution, and inter-agent
communication on top of the single-agent governance loop.

### 5.1 Phase Not Executing

**Symptom**

A simulation phase (e.g., "post_flood", "annual_decision") does not execute for
certain agents. No audit traces are written for those agents in that phase.

**Root Causes**

1. **Agent type not configured for the phase**: The experiment's lifecycle hooks may
   filter agents by type, and the agent type is not included.

2. **Lifecycle hook returns early**: A custom lifecycle hook (e.g.,
   `pre_step_hook`) returns a signal that skips the phase for certain agents.

3. **Agent was pruned from the simulation**: If an agent relocated or was removed
   (e.g., buyout), it may have been pruned from the active agent pool.

**Diagnosis**

1. Check your experiment's lifecycle hooks for filtering logic.
2. Check if the agent appears in the simulation's active agent list.
3. Check the social graph for whether the agent was pruned:
   ```python
   # In your experiment code:
   print(social_graph.get_neighbors(agent_id))  # Empty = pruned
   ```

**Solution**

- Verify agent type membership in phase dispatch logic.
- Check `_prune_agent_from_graph()` if agents are being removed after relocation.
- Ensure lifecycle hooks do not inadvertently skip agents.

### 5.2 Social Graph Edges Missing

**Symptom**

Agents report 0 neighbors in the audit CSV (`social_neighbor_count=0`). Gossip and
observation context are empty. The social audit shows no visible actions.

**Root Causes**

1. **Graph not initialized**: The `SocialGraph` was not populated with edges during
   setup.

2. **Spatial radius too small**: For spatial graphs, the `radius` parameter may be
   too small to connect any agents.

3. **Max connections exceeded**: The `max_connections` limit (if set) may be too
   restrictive.

4. **Agents pruned after relocation**: Relocated agents are removed from the graph
   via `_prune_agent_from_graph()`. If many agents relocate, the graph becomes
   sparse.

**Diagnosis**

1. Check graph initialization in your experiment setup code.
2. Log the graph's edge count after initialization:
   ```python
   print(f"Graph edges: {len(social_graph.graph.edges())}")
   ```
3. Check the `social_neighbor_count` column in the audit CSV.

**Solution**

- Increase the spatial radius:
  ```yaml
  social_graph:
    type: spatial
    radius: 5  # Default is 3 grid cells
  ```

- Remove or increase `max_connections`:
  ```yaml
  social_graph:
    max_connections: 0  # 0 = unlimited
  ```

- Verify graph construction uses the correct agent coordinates.

### 5.3 Gossip Not Propagating

**Symptom**

The `social_gossip_count` is always 0 in the audit CSV, even though agents have
neighbors.

**Root Causes**

1. **max_gossip set to 0**: The `InteractionHub.build_social_context()` call has
   `max_gossip=0`.

2. **No gossip-producing observer**: If using SDK observers, the observer may not
   produce gossip content.

3. **Agent states lack gossip-triggering attributes**: Gossip generation depends on
   observable actions (e.g., a neighbor who elevated their home). If no neighbors
   have taken observable actions, there is nothing to gossip about.

**Solution**

- Ensure `max_gossip >= 1` in your experiment's social context call.
- Verify that agents' state dictionaries contain the observable attributes that
  trigger gossip generation (e.g., `is_elevated`, `has_insurance`, `relocated`).

---

## 6. Debug Workflow

### 6.1 How to Read Audit CSV Traces

The audit CSV (`<output_dir>/<agent_type>_governance_audit.csv`) is the primary
diagnostic tool. Key columns:

| Column | Description |
|--------|-------------|
| `step_id` | Simulation step/year |
| `agent_id` | Agent identifier |
| `proposed_skill` | What the LLM chose |
| `final_skill` | What the broker approved (may differ from proposed) |
| `status` | `APPROVED`, `REJECTED`, `REJECTED_FALLBACK` |
| `validated` | `True` if governance approved |
| `retry_count` | Number of governance retries used |
| `format_retries` | Number of structural/format retries used |
| `parse_layer` | Which parsing layer succeeded (`json`, `keyword`, `digit`, `default`) |
| `parse_confidence` | Confidence of parse (0.20-0.95) |
| `construct_completeness` | Fraction of required constructs found (0.0-1.0) |
| `failed_rules` | Pipe-separated list of blocking rule IDs |
| `error_messages` | Pipe-separated validation error messages |
| `warning_rules` | Non-blocking warning rule IDs |
| `prompt_tokens` | Tokens used by the prompt |
| `context_utilization` | `prompt_tokens / num_ctx` (>0.85 is risky) |
| `construct_*` | Dynamic construct label values (e.g., `construct_TP_LABEL`) |
| `mem_retrieved_count` | Memories retrieved for this decision |
| `social_gossip_count` | Gossip snippets received |
| `social_neighbor_count` | Number of social graph neighbors |

**Common analysis patterns:**

```python
import pandas as pd

df = pd.read_csv("output/household_governance_audit.csv")

# 1. Rejection rate
print(f"Rejection rate: {(df.status == 'REJECTED').mean():.1%}")

# 2. Top blocking rules
print(df[df.validated == False]['failed_rules'].value_counts().head())

# 3. Parse quality distribution
print(df['parse_layer'].value_counts())

# 4. Context utilization warnings
high_util = df[df.context_utilization > 0.85]
print(f"High context utilization: {len(high_util)} / {len(df)} steps")

# 5. Agents that never got approved
rejected_agents = df.groupby('agent_id')['validated'].all()
always_rejected = rejected_agents[~rejected_agents].index
print(f"Always-rejected agents: {len(always_rejected)}")
```

### 6.2 JSONL Trace Files

For deeper investigation, use the JSONL traces at
`<output_dir>/raw/<agent_type>_traces.jsonl`. Each line is a complete JSON object
with the full prompt, raw LLM output, validation history, memory snapshots, and
execution results.

```python
import json

with open("output/raw/household_traces.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        trace = json.loads(line)
        if trace["agent_id"] == "agent_42" and trace.get("step_id") == 5:
            print(json.dumps(trace, indent=2))
            break
```

### 6.3 Log Level Configuration

WAGF uses the `BROKER_LOG_LEVEL` environment variable to control log verbosity.

```bash
# Windows
set BROKER_LOG_LEVEL=DEBUG
python run_experiment.py

# Unix/Mac
BROKER_LOG_LEVEL=DEBUG python run_experiment.py
```

Available levels (from most to least verbose):
- `DEBUG` -- Parser internals, RAG retrieval, construct matching details
- `INFO` -- Parse layer results, construct classifications, governance retries
  resolved (default)
- `WARNING` -- Initial validation failures, missing constructs, key collisions,
  truncated retry reports
- `ERROR` -- Max retries exhausted, parse failures after retries, LLM connection
  errors, governance fallout diagnostics

**Recommended levels by scenario:**

| Scenario | Level | Reason |
|----------|-------|--------|
| Production run | `WARNING` | Only shows problems |
| Pilot calibration | `INFO` | See parse quality and construct values |
| Debugging parsing | `DEBUG` | Full adapter trace with regex matches |
| Debugging governance | `INFO` | Retry attempts, rule hits, EarlyExit |

### 6.4 Using `--verbose` Flag and `log_prompt`

Many WAGF experiments support a `--verbose` flag that enables detailed LLM I/O
logging:

```bash
python run_experiment.py --verbose
```

This sets `log_prompt=True` in the `SkillBrokerEngine`, which enables:
- Full prompt logging before each LLM call.
- Reasoning summary with dynamic label extraction.
- LLM input/output character counts.

Additionally, the `verbose` flag on `create_llm_invoke()` enables:
- Prompt preview: first 100 characters of each prompt.
- Raw output preview: first 200 characters of each response.
- Think-token stripping diagnostics for Qwen3 models.

### 6.5 Governance Audit Summary

At the end of a run, call `GovernanceAuditor().print_summary()` to see aggregated
statistics:

```
==================================================
  GOVERNANCE AUDIT SUMMARY
==================================================
  Total Interventions: 156
  Parsing Failures:    12
  Successful Retries:  28
  Final Fallouts:      7
--------------------------------------------------
  Structural Faults (Format Issues):
  - Format Retry Attempts: 15
  - Faults Fixed:          12
  - Faults Terminal:       3
--------------------------------------------------
  LLM-Level Retries (Extra LLM Calls):
  - Empty Content Retries:   4
  - Empty Content Failures:  1
  - Invalid Label Retries:   8
  - Total Extra LLM Calls:   27
--------------------------------------------------
  Top Rule Violations (ERROR):
  - affordability_check: 45 hits
  - low_coping: 23 hits
  - flood_zone_appropriateness: 18 hits
--------------------------------------------------
  Warnings (Non-Blocking): 34
  - observation_mismatch: 15 warnings
  - income_consistency: 19 warnings
==================================================
```

This summary is also saved as JSON to `<output_dir>/governance_auditor_summary.json`
when you call `auditor.save_summary(path)`.

### 6.6 Quick Diagnostic Checklist

When something goes wrong, work through this checklist:

1. **Is Ollama running?** `curl http://localhost:11434/api/tags`
2. **Is the model pulled?** `ollama list`
3. **Is agent_types.yaml loading?** Check for `[Config] Agent type configuration not
   found` warnings at startup.
4. **Is the skill registry valid?** Check for `Skill registry configuration not found`
   or `Invalid YAML` errors.
5. **Are governance rules loading?** Set `GOVERNANCE_PROFILE` env var if using
   non-default profiles.
6. **Are agents getting parsed?** Check `parse_layer` distribution in audit CSV.
   If mostly `default`, the prompt/model combination is not working.
7. **Are agents getting approved?** Check `validated` column. If approval rate < 50%,
   governance rules may be too strict.
8. **Is memory working?** Check `mem_retrieved_count`. If always 0, memory engine
   may not be initialized or seeded.
9. **Is the social graph connected?** Check `social_neighbor_count`. If always 0,
   graph initialization may have failed.
10. **Is context overflowing?** Check `context_utilization`. If > 0.85, reduce
    prompt size or increase `num_ctx`.

---

## Appendix: Error Message Quick Reference

| Error Message | Source | Section |
|---------------|--------|---------|
| `[Governance:Fallout] CRITICAL: Max retries (N) reached` | `skill_broker_engine.py` | [1.1](#11-max-retries-reached-governance-fallout) |
| `[Governance:EarlyExit] Deterministic rules blocked` | `skill_broker_engine.py` | [1.1](#11-max-retries-reached-governance-fallout) |
| `[Governance:Exhausted] Parsing failed. Forcing fallback` | `skill_broker_engine.py` | [1.1](#11-max-retries-reached-governance-fallout) |
| `[Governance:Diagnostic] Key collision in validation context` | `skill_broker_engine.py` | [1.4](#14-key-collision-in-validation-context) |
| `[Precondition] skill: Precondition failed` | `skill_registry.py` | [1.2](#12-precondition-failed) |
| `[OutputSchema] skill: Field exceeds bounds` | `skill_registry.py` | [1.5](#15-output-schema-violation) |
| `[Multi-Skill] Composite conflict` | `skill_broker_engine.py` | [1.6](#16-composite-conflict-multi-skill) |
| `[LLM:Error] Model returned unparsable output after retries` | `skill_broker_engine.py` | [2.1](#21-unparsable-output--parse-error-after-retries) |
| `[Broker:Retry] Empty/Null response received` | `skill_broker_engine.py` | [2.1](#21-unparsable-output--parse-error-after-retries) |
| `[Broker:Retry] Missing required constructs` | `skill_broker_engine.py` | [1.3](#13-construct-missing--missing-required-constructs) |
| `[Adapter:Error] STRICT_MODE: Failed to parse` | `model_adapter.py` | [2.1](#21-unparsable-output--parse-error-after-retries) |
| `[Adapter:Diagnostic] Warning: Missing constructs` | `model_adapter.py` | [1.3](#13-construct-missing--missing-required-constructs) |
| `[LLM:Direct] connection refused` | `llm_utils.py` | [3.1](#31-connection-refused) |
| `[LLM:Direct] HTTP Error 404` | `llm_utils.py` | [3.2](#32-model-not-found) |
| `[LLM:Direct] timed out after Ns` | `llm_utils.py` | [3.4](#34-timeout-issues) |
| `[LLM:Retry] returned truly empty content` | `llm_utils.py` | [3.5](#35-empty-content-from-llm) |
| `[LLM:Error] returned empty content after N attempts` | `llm_utils.py` | [3.5](#35-empty-content-from-llm) |
| `[Config] Agent type configuration not found` | `agent_config.py` | [6.6](#66-quick-diagnostic-checklist) |
| `[Config] Invalid YAML` | `agent_config.py` | [6.6](#66-quick-diagnostic-checklist) |
| `Skill registry configuration not found` | `skill_registry.py` | [6.6](#66-quick-diagnostic-checklist) |
| `Invalid YAML in skill registry` | `skill_registry.py` | [6.6](#66-quick-diagnostic-checklist) |
| `Unknown memory engine type` | `memory_registry.py` | [4.2](#42-unknown-memory-engine-type) |
| `Default skill 'X' not in registry` | `skill_broker_engine.py` | [1.1](#11-max-retries-reached-governance-fallout) |
| `YAML default_skill='X' not found in registry` | `skill_registry.py` | [6.6](#66-quick-diagnostic-checklist) |
