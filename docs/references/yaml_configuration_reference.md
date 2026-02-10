# YAML Configuration Reference

> **Water Agent Governance Framework (WAGF) v2**
>
> This reference documents the two YAML configuration files required for every
> WAGF experiment: **`agent_types.yaml`** (agent behavior, governance, parsing)
> and **`skill_registry.yaml`** (action space, preconditions, institutional
> constraints).  For end-to-end usage patterns see
> [Experiment Design Guide](../guides/experiment_design_guide.md).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Part 1 -- agent_types.yaml](#2-part-1----agent_typesyaml)
   - [global_config](#21-global_config)
   - [shared](#22-shared)
   - [Agent Type Blocks](#23-agent-type-blocks)
   - [Governance Rules](#24-governance-rules)
3. [Part 2 -- skill_registry.yaml](#3-part-2----skill_registryyaml)
   - [Skill Definition Fields](#31-skill-definition-fields)
   - [default_skill](#32-default_skill)
   - [Institutional Constraints](#33-institutional-constraints)
   - [Conflict and Dependency Declarations](#34-conflict-and-dependency-declarations)
4. [Cross-Reference: Loading Logic](#4-cross-reference-loading-logic)
5. [Complete Minimal Example](#5-complete-minimal-example)

---

## 1. Overview

Every WAGF experiment requires two YAML files passed at initialization:

| File | Purpose | Loaded by |
|------|---------|-----------|
| `agent_types.yaml` | Agent prompts, parsing, governance rules, memory, LLM params | `AgentTypeConfig.load(path)` in `broker/utils/agent_config.py` |
| `skill_registry.yaml` | Available skills (action space), preconditions, constraints | `SkillRegistry.register_from_yaml(path)` in `broker/components/skill_registry.py` |

Both files are loaded with `yaml.safe_load()` using UTF-8 encoding. YAML parse
errors surface with line-number diagnostics.

---

## 2. Part 1 -- agent_types.yaml

The `agent_types.yaml` file is a single YAML document containing several
top-level keys:

```
global_config:   # Framework-wide defaults
shared:          # Shared definitions (rating scale, response format)
<agent_type>:    # One block per agent type (e.g., household_owner)
governance:      # Governance rule profiles (strict / relaxed / disabled)
metadata:        # Optional version metadata
```

### 2.1 global_config

Framework-wide defaults that apply to all agent types unless overridden at the
agent-type level.

#### 2.1.1 global_config.memory

Controls the sliding-window episodic memory system.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `window_size` | int | No | 5 | Number of recent time-steps retained in working memory |
| `consolidation_threshold` | float | No | 0.6 | Importance score above which a memory is consolidated to long-term store |
| `consolidation_probability` | float | No | 0.7 | Probability of consolidation when threshold is met |
| `top_k_significant` | int | No | 2 | Number of most-significant memories surfaced per retrieval |
| `decay_rate` | float | No | 0.1 | Exponential decay rate for memory importance over time |
| `arousal_threshold` | float | No | 1.0 | Stimulus intensity above which arousal-based encoding triggers |
| `ema_alpha` | float | No | 0.3 | Exponential moving average smoothing factor for arousal tracking |
| `stimulus_key` | string | No | (none) | Environment variable key that drives arousal (e.g., `flood_depth_m`) |
| `ranking_mode` | string | No | `"weighted"` | Memory ranking strategy. Valid values: `weighted`, `recency` |

**Example:**

```yaml
global_config:
  memory:
    window_size: 5
    consolidation_threshold: 0.6
    consolidation_probability: 0.7
    top_k_significant: 2
    decay_rate: 0.1
```

#### 2.1.2 global_config.cognitive_config

Per-agent-type cognitive arousal configuration. Keyed by agent type name.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `stimulus_key` | string | Yes | -- | State field that drives cognitive arousal |
| `arousal_threshold` | float | No | 1.0 | Threshold above which arousal triggers reflection |
| `ema_alpha` | float | No | 0.3 | EMA smoothing factor |
| `engine` | string | No | `"universal"` | Cognitive engine type. Valid values: `universal`, `window` |

**Example:**

```yaml
global_config:
  cognitive_config:
    household_owner:
      stimulus_key: flood_depth_m
      arousal_threshold: 1.0
      ema_alpha: 0.3
      engine: universal
```

#### 2.1.3 global_config.reflection

Controls the periodic reflection subsystem where agents synthesize lessons
from accumulated memories.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `interval` | int | No | 1 | Reflect every N time-steps |
| `batch_size` | int | No | 10 | Max memories processed per reflection |
| `importance_boost` | float | No | 0.9 | Importance score assigned to reflection-generated memories |
| `persona_instruction` | string | No | (none) | System instruction for persona-aware reflection prompts |
| `questions` | list[string] | No | [] | Guiding reflection questions injected into the prompt |
| `method` | string | No | `"hybrid"` | Reflection strategy. Valid values: `hybrid`, `periodic`, `crisis` |
| `triggers` | object | No | {} | Trigger conditions (see sub-table below) |

**Trigger sub-fields** (`global_config.reflection.triggers`):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `crisis` | bool | No | false | Enable crisis-triggered reflection |
| `periodic_interval` | int | No | 5 | Reflect every N time-steps (periodic trigger) |
| `decision_types` | list[string] | No | [] | Skill names that trigger post-decision reflection |
| `institutional_threshold` | float | No | 0.05 | Policy change magnitude that triggers reflection |

**Example:**

```yaml
global_config:
  reflection:
    interval: 1
    batch_size: 10
    importance_boost: 0.9
    method: hybrid
    triggers:
      crisis: true
      periodic_interval: 5
      decision_types: [elevate_house, buyout_program]
      institutional_threshold: 0.05
```

#### 2.1.4 global_config.llm

LLM invocation parameters applied globally (can be overridden per agent type
via `llm_params`).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | No | (CLI override) | Model identifier (typically overridden at the command line) |
| `temperature` | float | No | 0.7 | Sampling temperature |
| `top_p` | float | No | 0.9 | Nucleus sampling probability |
| `top_k` | int | No | 40 | Top-k sampling parameter |
| `num_ctx` | int | No | 4096 | Context window size in tokens |
| `num_predict` | int | No | 1024 | Maximum tokens to generate |
| `max_retries` | int | No | 2 | Maximum raw LLM invocation retries on malformed output |

**Example:**

```yaml
global_config:
  llm:
    temperature: 0.7
    num_ctx: 8192
    num_predict: 4096
    max_retries: 2
```

#### 2.1.5 global_config.governance

Controls the governance validation loop -- how many times the broker retries
after a rule blocks a decision, and how many violation reports are included
per retry prompt.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_retries` | int | No | 3 | Maximum governance loop retries after rule violations |
| `max_reports_per_retry` | int | No | 3 | Maximum `InterventionReport` objects injected per retry |
| `shuffle_options` | bool | No | false | Randomize skill option order per LLM call (mitigates positional bias) |
| `domain` | string | No | (none) | Domain selector for domain-specific validator injection (e.g., `irrigation`) |

**Example:**

```yaml
global_config:
  governance:
    max_retries: 3
    max_reports_per_retry: 3
    shuffle_options: true
```

---

### 2.2 shared

Shared definitions referenced across all agent types. These are accessed
via `AgentTypeConfig.get_shared(key)`.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `rating_scale` | string | Yes | -- | Rating scale definition injected into prompts (e.g., VL/L/M/H/VH) |
| `criteria_definitions` | string | No | "" | Prose definitions of behavioral constructs (e.g., PMT constructs) |
| `response_format` | object | Yes | -- | Structured output format the LLM must follow (see below) |
| `constructs` | object | No | {} | Shared construct extraction definitions |

#### 2.2.1 shared.response_format

Defines the structured output delimiters and fields the LLM must produce.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `delimiter_start` | string | Yes | -- | Start marker for structured response block (e.g., `<<<DECISION_START>>>`) |
| `delimiter_end` | string | Yes | -- | End marker for structured response block (e.g., `<<<DECISION_END>>>`) |
| `fields` | list[object] | Yes | -- | Ordered list of expected response fields (see below) |

**Response field sub-fields** (`shared.response_format.fields[]`):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `key` | string | Yes | -- | Field name in parsed output dictionary |
| `type` | string | Yes | -- | Field type. Valid values: `appraisal`, `choice`, `text`, `numeric`, `secondary_choice` |
| `required` | bool | Yes | -- | Whether the field must be present for a valid parse |
| `construct` | string | No | -- | Construct label key this field maps to (e.g., `TP_LABEL`). Required when `type: appraisal` |
| `reason_hint` | string | No | -- | Hint text shown to the LLM explaining what this appraisal captures |
| `description` | string | No | -- | Human-readable description of the field |
| `min` | number | No | -- | Minimum value (for `type: numeric`) |
| `max` | number | No | -- | Maximum value (for `type: numeric`) |
| `unit` | string | No | -- | Unit label (for `type: numeric`) |

**Example:**

```yaml
shared:
  rating_scale: |
    ### RATING SCALE:
    VL = Very Low | L = Low | M = Medium | H = High | VH = Very High

  response_format:
    delimiter_start: "<<<DECISION_START>>>"
    delimiter_end: "<<<DECISION_END>>>"
    fields:
      - { key: "threat_appraisal", type: "appraisal", required: true,
          construct: "TP_LABEL", reason_hint: "How threatened do you feel?" }
      - { key: "coping_appraisal", type: "appraisal", required: true,
          construct: "CP_LABEL", reason_hint: "How well can you cope?" }
      - { key: "decision", type: "choice", required: true }
```

---

### 2.3 Agent Type Blocks

Each agent type is a top-level key (e.g., `household_owner`, `irrigation_farmer`,
`nj_government`). The `AgentTypeConfig.get(agent_type)` method returns the
corresponding dictionary.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `description` | string | No | "" | Human-readable description of this agent type |
| `prompt_template` | string | No | -- | Inline Jinja2/f-string prompt template. Mutually exclusive with `prompt_template_file` |
| `prompt_template_file` | string | No | -- | Path to external prompt file (relative to config directory) |
| `llm_params` | object | No | {} | Per-type LLM overrides (same fields as `global_config.llm`) |
| `response_format` | object | No | (shared) | Per-type response format override (same schema as `shared.response_format`) |
| `multi_skill` | object | No | {enabled: false} | Multi-skill configuration (see below) |
| `parsing` | object | No | {} | LLM output parsing configuration (see below) |
| `log_fields` | list[string] | No | [] | Construct field names to log per decision |
| `memory` | object | No | {} | Per-type memory configuration overrides |
| `feedback` | object | No | {} | Feedback dashboard configuration |
| `actions` | list[object] | No | [] | Action definitions (legacy path -- may also be under `parsing.actions`) |
| `governance` | object | No | {} | Inline governance profile (for agent types that nest rules inside their block) |

#### 2.3.1 multi_skill

Enables agents to propose a primary and secondary skill in a single turn.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | No | false | Enable multi-skill proposals |
| `max_skills` | int | No | 2 | Maximum skills per turn |
| `execution_order` | string | No | `"sequential"` | Execution strategy. Valid values: `sequential`, `parallel` |
| `secondary_field` | string | No | `"secondary_decision"` | Response field key for the secondary skill |
| `secondary_magnitude_field` | string | No | -- | Response field key for secondary magnitude |
| `conflicts` | object | No | {} | Per-skill conflict map: `{skill_A: [skill_B, ...]}` |

**Example:**

```yaml
household_owner:
  multi_skill:
    enabled: true
    max_skills: 2
    execution_order: sequential
    secondary_field: secondary_decision
    conflicts:
      elevate_house: [buyout_program]
      buyout_program: [elevate_house, buy_insurance]
```

#### 2.3.2 parsing

Controls how the broker extracts structured decisions from raw LLM output.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `decision_keywords` | list[string] | No | ["decision"] | JSON keys to search for the decision value |
| `default_skill` | string | No | -- | Fallback skill when parsing fails after all retries |
| `global_skills` | list[string] | No | [] | Skills that are always available regardless of preconditions |
| `full_disclosure` | bool | No | false | Include all available skills in the prompt (not just eligible ones) |
| `strict_mode` | bool | No | false | Reject any output that does not match a known skill ID or alias |
| `preprocessor` | object | No | {} | Output preprocessor config (see below) |
| `proximity_window` | int | No | 35 | Character window for proximity-based construct extraction |
| `list_delimiters` | list[string] | No | [] | Additional delimiters for list-format parsing |
| `actions` | list[object] | No | [] | Action definitions with aliases (see below) |
| `constructs` | object | No | {} | Construct extraction rules (see below) |
| `skill_map` | object | No | {} | Maps numeric/shorthand keys to canonical skill IDs |
| `synonyms` | object | No | {} | Maps construct synonyms for fuzzy matching |
| `audit_keywords` | list[string] | No | [] | Domain keywords for hallucination audit |
| `audit_context_fields` | list[string] | No | [] | State fields to include in audit context |
| `audit_blacklist` | list[string] | No | [] | Words excluded from hallucination scoring |
| `audit_stopwords` | list[string] | No | [] | Common domain words excluded from audit term frequency |

**Preprocessor sub-fields** (`parsing.preprocessor`):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | Yes | -- | Preprocessor type. Valid values: `smart_repair` |
| `quote_values` | list[string] | No | [] | Values to auto-quote during repair (e.g., `["VL", "L", "M", "H", "VH"]`) |

#### 2.3.3 parsing.actions

Each action maps a canonical skill ID to human-readable aliases and a
description. The parser uses these to resolve LLM output to valid skill IDs.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | Yes | -- | Canonical skill ID (must match a skill in `skill_registry.yaml`) |
| `aliases` | list[string] | No | [] | Alternative names/abbreviations the LLM might produce |
| `description` | string | No | "" | Human-readable description shown in prompts |
| `requires` | object | No | {} | Per-action precondition overrides |

**Example:**

```yaml
parsing:
  actions:
    - id: do_nothing
      aliases: [DN, nothing, wait, "Do nothing"]
      description: Take no action this year
    - id: buy_insurance
      aliases: [FI, insurance, "Buy insurance"]
      description: Purchase NFIP flood insurance
```

#### 2.3.4 parsing.constructs

Defines extraction rules for behavioral constructs from LLM output. Each key
is a construct name (e.g., `TP_LABEL`, `WSA_LABEL`).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `keywords` | list[string] | Yes | -- | Context keywords that indicate proximity to this construct |
| `regex` | string | Yes | -- | Regular expression to extract the construct value |

**Example:**

```yaml
parsing:
  constructs:
    TP_LABEL:
      keywords: [threat, severity, vulnerability]
      regex: '(?i)(?:label)?[:\s\*\[]*\b(VL|L|M|H|VH)\b'
    TP_REASON:
      keywords: [threat, severity, vulnerability]
      regex: '(?i)(?:reason|why|because|explanation)[:\s\*]*(.*)'
```

---

### 2.4 Governance Rules

Governance rules enforce behavioral coherence and physical constraints on
agent decisions. Rules are organized into **profiles** (typically `strict`,
`relaxed`, `disabled`) and then by **agent type**.

The governance section can appear in two locations:

1. **Top-level `governance:` key** -- Preferred for multi-agent configurations.
   Keyed by profile, then agent type.
2. **Nested under an agent type block** as `<agent_type>.governance.profile.rules` --
   Allowed for single-agent configurations.

Each profile contains two rule lists per agent type:

- **`thinking_rules`** -- Behavioral construct checks (PMT appraisals, dual-appraisal coherence)
- **`identity_rules`** -- Physical state precondition checks (irreversible actions, caps)

#### 2.4.1 Top-Level Governance Structure

```yaml
governance:
  strict:                    # Profile name
    household_owner:         # Agent type
      identity_rules: [...]
      thinking_rules: [...]
    household_renter:
      identity_rules: [...]
      thinking_rules: [...]
  relaxed:
    household_owner:
      identity_rules: [...]
      thinking_rules: [...]
  disabled:
    household_owner:
      identity_rules: []
      thinking_rules: []
```

#### 2.4.2 thinking_rules

Thinking rules check LLM-reported behavioral construct labels (appraisals)
and block skill proposals that are incoherent with the agent's stated reasoning.

There are two syntax variants:

**Modern syntax (multi-condition):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | Yes | -- | Unique rule identifier |
| `conditions` | list[object] | Yes | -- | List of conditions that must ALL be true to trigger the rule |
| `blocked_skills` | list[string] | Yes | -- | Skill IDs blocked when the rule triggers |
| `level` | string | No | `"ERROR"` | Enforcement level. Valid values: `ERROR` (block + retry), `WARNING` (log only) |
| `message` | string | No | "" | Human-readable explanation included in `InterventionReport` |

**Condition sub-fields** (`thinking_rules[].conditions[]`):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `construct` | string | Yes | -- | Construct label key (e.g., `TP_LABEL`, `WSA_LABEL`) |
| `values` | list[string] | Yes | -- | Construct values that satisfy this condition (e.g., `["H", "VH"]`) |

All conditions are evaluated with AND logic -- every condition must match for the
rule to fire.

**Legacy syntax (single-construct):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | Yes | -- | Unique rule identifier |
| `construct` | string | Yes | -- | Single construct key to check |
| `when_above` | list[string] | Yes | -- | Construct values that trigger the rule |
| `blocked_skills` | list[string] | Yes | -- | Skill IDs blocked when the rule triggers |
| `level` | string | No | `"ERROR"` | Enforcement level |
| `message` | string | No | "" | Explanation message |

**Example (modern multi-condition):**

```yaml
thinking_rules:
  - id: high_threat_high_cope_no_increase
    conditions:
      - { construct: WSA_LABEL, values: ["H", "VH"] }
      - { construct: ACA_LABEL, values: ["H", "VH"] }
    blocked_skills: [increase_large, increase_small]
    level: ERROR
    message: "Demand increase BLOCKED: high scarcity + high adaptive capacity."
```

**Example (legacy single-construct):**

```yaml
thinking_rules:
  - id: high_threat_no_maintain
    construct: WSA_LABEL
    when_above: ["VH"]
    blocked_skills: [maintain_demand]
    level: WARNING
    message: "Water threat is Very High -- maintaining demand is suboptimal."
```

#### 2.4.3 identity_rules

Identity rules check agent state preconditions (boolean flags) and block
skills that violate physical or institutional constraints.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | Yes | -- | Unique rule identifier |
| `precondition` | string | Yes | -- | State field name to check (must be boolean `true` to trigger) |
| `blocked_skills` | list[string] | Yes | -- | Skill IDs blocked when the precondition is true |
| `level` | string | No | `"ERROR"` | Enforcement level. Valid values: `ERROR`, `WARNING` |
| `message` | string | No | "" | Explanation message |

**Example:**

```yaml
identity_rules:
  - id: elevated_already
    precondition: elevated
    blocked_skills: [elevate_house]
    level: ERROR
  - id: water_right_cap
    precondition: at_allocation_cap
    blocked_skills: [increase_large, increase_small]
    level: ERROR
    message: "Cannot increase demand -- already at maximum water right allocation."
```

#### 2.4.4 Governance Level Semantics

| Level | Behavior | Use When |
|-------|----------|----------|
| `ERROR` | Blocks the decision. Broker re-prompts the LLM with an `InterventionReport`. Counts toward `max_retries`. | Hard constraints -- physical impossibility, institutional prohibition |
| `WARNING` | Logged but decision proceeds. Appears in audit trail but does not trigger retry. | Soft guidance -- suboptimal choices, behavioral nudges |

**Important:** For small LLMs (< 8B parameters), `WARNING` rules have near-zero
behavioral impact. Use `ERROR` for any rule that must change agent behavior.

#### 2.4.5 RuleCondition Evaluation (Advanced)

The `broker/governance/rule_types.py` module implements a more expressive
`RuleCondition` dataclass that supports four condition types:

| Condition Type | Context Key | Operators | Description |
|----------------|-------------|-----------|-------------|
| `construct` | `reasoning` | `in`, `==`, `!=`, `>`, `<`, `>=`, `<=` | Behavioral construct label check |
| `precondition` | `state` | `==`, `!=` | Boolean/value state field check |
| `expression` | `state` | `>`, `<`, `>=`, `<=`, `==`, `!=` | Numeric expression on state fields |
| `social` | `social_context` | `>`, `<`, `>=`, `<=`, `in` | Social context field check (e.g., adoption rate) |

**Valid operators for all condition types:**

| Operator | Description |
|----------|-------------|
| `==` | Equal to `values[0]` |
| `!=` | Not equal to `values[0]` |
| `>` | Greater than `values[0]` |
| `<` | Less than `values[0]` |
| `>=` | Greater than or equal to `values[0]` |
| `<=` | Less than or equal to `values[0]` |
| `in` | Value is a member of `values` list (default operator) |

---

### 2.5 Additional Top-Level Sections

These sections are optional and domain-specific.

| Section | Description |
|---------|-------------|
| `floodabm_parameters` | Domain-specific parameters for the flood ABM (PMT distributions, insurance rates, etc.) |
| `personas` | Behavioral cluster persona definitions (e.g., aggressive, conservative) with magnitude parameters |
| `memory_config` | Per-agent-type memory engine configuration (engine type, sensors, scorers) |
| `retrieval_config` | Memory retrieval strategy configuration (importance weighting, recency, top-k) |
| `social_memory_config` | Social memory and gossip configuration (gossip categories, importance threshold) |
| `metadata` | Version and provenance metadata for the configuration file |

---

## 3. Part 2 -- skill_registry.yaml

The `skill_registry.yaml` file defines the **action space** -- what skills
(abstract behavioral intentions) are available, who can use them, and under
what conditions. It is loaded by `SkillRegistry.register_from_yaml()`.

### Top-Level Structure

```yaml
skills:              # List of skill definitions
  - skill_id: ...
  - skill_id: ...

default_skill: ...   # Fallback skill when all proposals are rejected
```

### 3.1 Skill Definition Fields

Each entry in the `skills` list defines one skill.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `skill_id` | string | Yes | -- | Unique identifier (must match action IDs in `agent_types.yaml`) |
| `description` | string | No | "" | Human-readable description of the skill's behavioral intent |
| `eligible_agent_types` | list[string] | No | `["*"]` | Agent types permitted to use this skill. `"*"` = all types |
| `preconditions` | list[string] | No | [] | Boolean state preconditions (e.g., `"not at_allocation_cap"`) |
| `institutional_constraints` | object | No | {} | Domain-specific institutional rules (see Section 3.3) |
| `allowed_state_changes` | list[string] | No | [] | State fields this skill is permitted to modify |
| `implementation_mapping` | string | No | "" | Simulation engine command (e.g., `"sim.protect"`, `"env.execute_skill"`) |
| `output_schema` | object | No | {} | JSON Schema for expected output structure |
| `conflicts_with` | list[string] | No | [] | Mutually exclusive skill IDs (see Section 3.4) |
| `depends_on` | list[string] | No | [] | Prerequisite skill IDs that must be completed first (see Section 3.4) |

**Example (minimal):**

```yaml
skills:
  - skill_id: take_action
    description: "Take a protective action (costs resources but reduces risk)"
    eligible_agent_types: ["*"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes:
      - protected
    implementation_mapping: "sim.protect"
```

**Example (production -- irrigation):**

```yaml
skills:
  - skill_id: increase_large
    description: "Aggressively increase water demand (8-20% change)."
    eligible_agent_types: ["irrigation_farmer"]
    preconditions:
      - "not at_allocation_cap"
    institutional_constraints:
      annual: true
      magnitude_type: "percentage"
      max_magnitude_pct: 20
      magnitude_default: 12
    allowed_state_changes:
      - request
      - diversion
    implementation_mapping: "env.execute_skill"
    output_schema:
      type: object
      required: [decision]
      properties:
        decision: { type: integer, enum: [1, 2, 3, 4, 5] }
    conflicts_with: []
```

### 3.2 default_skill

A top-level field specifying the fallback skill executed when:

- All governance retries are exhausted (proposal repeatedly rejected)
- LLM output cannot be parsed after `max_retries`
- The `REJECTED` fallback pathway is triggered

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `default_skill` | string | No | `"do_nothing"` | Skill ID to execute as fallback. Must exist in the `skills` list |

If specified but not found in the registry, a warning is logged and the
built-in default (`"do_nothing"`) is retained.

**Example:**

```yaml
default_skill: maintain_demand
```

### 3.3 Institutional Constraints

The `institutional_constraints` object within each skill definition encodes
domain-specific rules that the simulation engine enforces at execution time.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `once_only` | bool | No | false | Skill can only be executed once per agent lifetime (irreversible actions) |
| `annual` | bool | No | false | Skill can be executed at most once per simulation year |
| `magnitude_type` | string | No | -- | Type of magnitude parameter. Valid values: `percentage`, `absolute`, `ordinal` |
| `max_magnitude_pct` | number | No | -- | Maximum magnitude as a percentage (when `magnitude_type: percentage`) |
| `magnitude_default` | number | No | -- | Default magnitude if LLM does not specify one |
| `cooldown_years` | int | No | -- | Minimum years between consecutive uses of this skill |
| `requires_approval` | bool | No | false | Whether institutional approval is required (e.g., buyout programs) |

**Example:**

```yaml
institutional_constraints:
  annual: true
  magnitude_type: "percentage"
  max_magnitude_pct: 8
  magnitude_default: 4
```

### 3.4 Conflict and Dependency Declarations

Skills can declare mutual exclusivity and prerequisite relationships.

#### conflicts_with

A list of skill IDs that cannot be executed in the same turn as this skill.
When multi-skill mode is enabled, the broker validates that primary and
secondary skills do not conflict.

```yaml
conflicts_with: [buyout_program]  # Cannot elevate and buyout in same turn
```

#### depends_on

A list of skill IDs that must have been successfully executed (in a prior
turn) before this skill becomes available. Used for composite or phased
actions.

```yaml
depends_on: [apply_for_grant]  # Must have applied for grant before elevating
```

---

## 4. Cross-Reference: Loading Logic

### AgentTypeConfig (agent_types.yaml)

Implemented in `broker/utils/agent_config.py`. Key methods:

| Method | Returns | Description |
|--------|---------|-------------|
| `AgentTypeConfig.load(yaml_path)` | `AgentTypeConfig` | Singleton loader with per-path cache |
| `.get(agent_type)` | dict | Full config dict for an agent type |
| `.get_shared(key)` | Any | Value from the `shared` section |
| `.get_governance_retries()` | int | `global_config.governance.max_retries` (default: 3) |
| `.get_governance_max_reports()` | int | `global_config.governance.max_reports_per_retry` (default: 3) |
| `.get_llm_retries()` | int | `global_config.llm.max_retries` (default: 2) |
| `.get_reflection_config()` | dict | Merged reflection config (global > shared > defaults) |
| `.get_valid_actions(agent_type)` | list[str] | All valid skill IDs and aliases for the agent type |
| `.get_action_alias_map(agent_type)` | dict | Maps aliases (lowercase) to canonical skill IDs |

**Resolution priority:** `global_config` > `shared` > built-in defaults.

**Agent type resolution:** If `agent_type` is not a direct key, the loader
tries splitting on `_` and matching the first segment (e.g., `household_mg`
resolves to `household`).

### SkillRegistry (skill_registry.yaml)

Implemented in `broker/components/skill_registry.py`. Key methods:

| Method | Returns | Description |
|--------|---------|-------------|
| `SkillRegistry.register_from_yaml(path)` | None | Loads all skills and sets `default_skill` |
| `.get(skill_id)` | `SkillDefinition` or None | Retrieve a skill definition |
| `.exists(skill_id)` | bool | Check if a skill is registered |
| `.get_default_skill()` | str | Get the default fallback skill ID |
| `.check_eligibility(skill_id, agent_type)` | `ValidationResult` | Verify agent type can use the skill |

### GovernanceRule (rule_types.py)

Implemented in `broker/governance/rule_types.py`.

| Method | Returns | Description |
|--------|---------|-------------|
| `GovernanceRule.evaluate(skill_name, context)` | bool | True if rule should block the skill |
| `RuleCondition.evaluate(context)` | bool | True if single condition is satisfied |

The `context` dictionary passed to `evaluate()` has three sub-dictionaries:

```python
context = {
    "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "L", ...},  # LLM construct outputs
    "state": {"elevated": True, "relocated": False, ...},     # Agent state
    "social_context": {"adoption_rate": 0.4, ...}             # Social context
}
```

---

## 5. Complete Minimal Example

### agent_types.yaml

```yaml
# Minimal agent_types.yaml for a two-skill scenario
global_config:
  memory:
    window_size: 3
  llm:
    num_ctx: 4096
    num_predict: 1024
    max_retries: 2
  governance:
    max_retries: 2
    max_reports_per_retry: 2

shared:
  rating_scale: |
    ### RATING SCALE:
    VL = Very Low | L = Low | M = Medium | H = High | VH = Very High

  response_format:
    delimiter_start: "<<<DECISION_START>>>"
    delimiter_end: "<<<DECISION_END>>>"
    fields:
      - { key: "threat_appraisal", type: "appraisal", required: true,
          construct: "TP_LABEL",
          reason_hint: "How threatened do you feel?" }
      - { key: "coping_appraisal", type: "appraisal", required: true,
          construct: "CP_LABEL",
          reason_hint: "How well can you cope?" }
      - { key: "decision", type: "decision", required: true }

agent_types:
  simple_agent:
    prompt_template: |
      You are a resident deciding how to prepare for a potential hazard.
      Your current situation: {situation}

      Choose one action:
      1. take_action -- Spend resources to protect yourself
      2. do_nothing -- Wait and see

      {response_format}
    governance:
      profile: strict
      rules:
        - rule_id: already_protected
          description: "Cannot take_action if already protected"
          conditions:
            - construct: "protected"
              operator: "eq"
              value: true
          action: "block"
          fallback_skill: "do_nothing"
          message: "Already protected -- no need to act again."
```

### skill_registry.yaml

```yaml
# Minimal skill_registry.yaml
skills:
  - skill_id: take_action
    description: "Take a protective action (costs resources but reduces risk)"
    eligible_agent_types: ["*"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes:
      - protected
    implementation_mapping: "sim.protect"

  - skill_id: do_nothing
    description: "Do nothing this round"
    eligible_agent_types: ["*"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes: []
    implementation_mapping: "sim.noop"

default_skill: do_nothing
```

---

## Appendix: Construct Label Normalization

The governance engine normalizes free-form LLM outputs to standard labels
before rule evaluation. The following mappings are applied:

| Raw Output | Normalized |
|------------|------------|
| `"Very Low"`, `"VERYLOW"`, `"VERY_LOW"` | `VL` |
| `"Low"`, `"LOW"` | `L` |
| `"Medium"`, `"MED"`, `"MODERATE"` | `M` |
| `"High"`, `"HIGH"` | `H` |
| `"Very High"`, `"VERYHIGH"`, `"VERY_HIGH"` | `VH` |

This normalization is performed in `GovernanceRule._normalize_label()` and
ensures robust rule matching regardless of how the LLM phrases its appraisals.

---

*Document generated for WAGF v2. See `broker/governance/rule_types.py`,
`broker/components/skill_registry.py`, and `broker/utils/agent_config.py`
for authoritative implementation details.*
