# Governance Core Architecture

**🌐 Language: [English](governance_core.md) | [中文](governance_core_zh.md)**

The Governance Core is the "Rational Engine" of the framework, ensuring that LLM outputs are not just text, but **valid, safe, and logical actions**.

---

## 1. Skill Lifecycle

The complete flow of a skill from definition to execution is as follows:

### Step 1: Definition

All skills must be registered in `agent_types.yaml`. This is the single source of truth.

```yaml
household:
  # Allowed actions list
  actions: ["do_nothing", "buy_insurance", "elevate_house"]

  # Aliases (Allow LLM to use natural language)
  alias:
    "wait": "do_nothing"
    "purchase": "buy_insurance"
```

### Step 2: Parsing

After the LLM outputs a response, the `UnifiedAdapter` attempts to map it to a registered skill:

1.  **Normalization**: Removes whitespace, converts to lowercase (e.g., "Buy Insurance" -> "buy_insurance").
2.  **Alias Lookup**: Checks if it matches an alias (e.g., "wait" -> "do_nothing").
3.  **Unknown Filter**: If not in the `actions` list, it is treated as an Invalid Skill.

### Step 3: Validation

This is the core governance step. The `AgentValidator` checks the skill proposal against two tiers of rules:

#### Tier 1: Identity & Status

Checks if the Agent has the **right** to perform this action.

- _Example_: You can only `buy_insurance` if `savings > 5000`.
- _Config_: Defined in the `identity_rules` block of `agent_types.yaml`.

#### Tier 2: Cognitive Consistentcy (Thinking)

Checks if the Agent's **reasoning is sound**.

- _Example_: If `threat_appraisal` is "High", you should not `do_nothing`.
- _Config_: Defined in the `thinking_rules` block of `agent_types.yaml`.

---

## 2. Validator Definition

Validators are not hardcoded; they are fully driven by YAML configuration.

### Validation Rule Example (`agent_types.yaml`)

```yaml
thinking_rules:
  - id: "R_LOGIC_01"
    level: "WARNING"
    message: "High threat perception implies action."
    # When Threat is High AND Coping is High
    conditions:
      - { construct: "threat_appraisal", values: ["H", "VH"] }
      - { construct: "coping_appraisal", values: ["H", "VH"] }
    # What is prohibited?
    blocked_skills: ["do_nothing"]
```

- **id**: Unique identifier for the rule (used in audit logs).
- **level**: `ERROR` (Reject execution) or `WARNING` (Log but allow).
- **conditions**: Prerequisites that trigger the rule.
- **blocked_skills**: Actions prohibited under these conditions.

---

## 3. Auditing

All validation results are logged in `simulation.log` and `audit_summary.json`. This allows us to track:

- How many times did Agents attempt to violate rules?
- Which rule was triggered the most?
- The "Rationality Score" (Alignment Score) of the LLM.
