# Customization Guide — Water Agent Governance Framework

## Overview

This guide explains how to customize each WAGF component for a new domain. All examples illustrate patterns from both flood adaptation (PMT) and irrigation demand (dual-appraisal) domains.

---

## 1. Custom Validators

Each check function follows the `BuiltinCheck` callable signature: `(skill_name, rules, context) -> List[ValidationResult]`:

```python
from typing import List, Dict, Any
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import ValidationResult

def my_physical_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Physical constraint check — block increase when at capacity."""
    if skill_name != "increase_demand":
        return []
    if not context.get("at_cap", False):
        return []
    return [ValidationResult(
        valid=False,                  # ERROR = block and retry
        validator_name="DomainPhysicalValidator",
        errors=["At maximum capacity — cannot increase demand."],
        warnings=[],
        metadata={"rule_id": "capacity_cap_check", "level": "ERROR"},
    )]
```

Validators fall into five categories:

| Category | Purpose | Example |
|----------|---------|---------|
| **Physical** | Physical state constraints | Cannot re-elevate a house; cannot exceed water right cap |
| **Personal** | Individual resource constraints | Savings insufficient for elevation cost |
| **Social** | Community norm checks | Most neighbors adapted but agent has not |
| **Semantic** | Reasoning consistency | Cites a nonexistent neighbor; references an event that didn't happen |
| **Thinking** | Appraisal-action coherence | YAML rule-driven (see agent_types.yaml) |

### Registering Validators

Aggregate all check functions and connect them to `ExperimentBuilder` via a bridge function:

```python
ALL_CHECKS = [my_physical_check, my_social_check, my_semantic_check]

def my_domain_validator(proposal, context, skill_registry=None):
    """Bridge domain checks to SkillBrokerEngine custom_validators."""
    skill_name = getattr(proposal, "skill_name", str(proposal))
    results = []
    for check in ALL_CHECKS:
        results.extend(check(skill_name, [], context))
    return results
```

Inject into `ExperimentBuilder`:

```python
builder.with_custom_validators([my_domain_validator])
```

---

## 2. Custom Response Format

Define LLM output fields in `agent_types.yaml` under `shared.response_format.fields`:

```yaml
shared:
  response_format:
    delimiter_start: "<<<DECISION_START>>>"
    delimiter_end: "<<<DECISION_END>>>"
    fields:
      - { key: "reasoning", type: "text", required: false }
      - {
          key: "threat_assessment",
          type: "appraisal",
          required: true,
          construct: "THREAT_LABEL",
          reason_hint: "One sentence explaining the threat level."
        }
      - { key: "decision", type: "choice", required: true }
      # Optional: numeric field
      - { key: "magnitude_pct", type: "numeric", min: 1, max: 30, required: false }
```

**Field types**:

| Type | Description | Output Format |
|------|-------------|---------------|
| `text` | Free-text reasoning | String |
| `appraisal` | JSON object with label + reason | `{"LABEL": "VL"..."VH", "REASON": "..."}` |
| `choice` | Integer skill ID (maps to skill_registry order) | Integer |
| `numeric` | Bounded numeric value (e.g., magnitude percentage) | Number |

---

## 3. Custom Memory Engine

### Production Configuration (HumanCentric basic ranking mode)

```yaml
your_agent_type:
  memory:
    engine_type: "human_centric"
    window_size: 5                    # Short-term memory buffer
    top_k_significant: 2             # Top memories by decayed importance

    emotion_keywords:
      crisis: ["drought", "shortage", "flood", "damage"]
      strategic: ["decision", "adopt", "reduce", "conservation"]
      positive: ["surplus", "adequate", "safe", "improved"]
      social: ["neighbor", "community", "upstream"]

    emotional_weights:
      crisis: 1.0
      strategic: 0.8
      positive: 0.6
      social: 0.4
      baseline_observation: 0.1

    source_patterns:
      personal: ["i ", "my ", "me "]
      neighbor: ["neighbor", "adjacent", "upstream"]
      community: ["basin", "community", "region"]
```

**Importance calculation**: `importance = emotional_weight × source_weight`

**Retrieval mode**: Basic ranking combines the recent window (5 newest memories) with top-k (2 highest decayed-importance memories).

### Available Engines

| Engine | Mode | Use Case |
|--------|------|----------|
| `HumanCentricMemoryEngine` | Basic ranking | **Recommended** for all formal experiments |
| `ImportanceMemoryEngine` | Weighted scoring | Experimental. Uses recency/importance/context weights |
| `WindowMemoryEngine` | FIFO | Baseline. Fixed-size sliding window |

### Registering a Custom Memory Engine

With the `MemoryEngineRegistry`, you can add custom engines without modifying framework source code:

```python
from broker.components.memory_engine import MemoryEngine
from broker.components.memory_registry import MemoryEngineRegistry

class MyCustomMemoryEngine(MemoryEngine):
    def __init__(self, window_size: int = 5, custom_param: float = 0.5, **kwargs):
        self.window_size = window_size
        self.custom_param = custom_param
        self._memories = {}

    def add_memory(self, agent_id: str, content: str, **kwargs):
        if agent_id not in self._memories:
            self._memories[agent_id] = []
        self._memories[agent_id].append(content)

    def get_memories(self, agent_id: str, **kwargs):
        return self._memories.get(agent_id, [])[-self.window_size:]

# Register before building experiment
MemoryEngineRegistry.register("my_custom", MyCustomMemoryEngine)

# Use in experiment
from broker.components.memory_factory import create_memory_engine
engine = create_memory_engine("my_custom", {"window_size": 10, "custom_param": 0.8})
```

---

## 4. Custom Reflection Engine

### Configuring Reflection Guiding Questions

Define domain-specific reflection questions in `agent_types.yaml`:

```yaml
global_config:
  reflection:
    interval: 1                      # Reflect every year
    batch_size: 10                   # Agents per batch
    importance_boost: 0.9            # Importance score for reflection insights
    method: hybrid
    questions:
      - "Is your strategy effective under current conditions?"
      - "What patterns exist between your action magnitude and outcomes?"
      - "How should you adjust your approach going forward?"
```

### Action-Outcome Feedback

Each year, agents receive consolidated memories linking decisions to outcomes:

> "Year 5: You chose decrease_demand 15%. Result: Water supply adequate, utilization dropped to 65%."

This enables causal learning through the reflection loop.

---

## 5. Custom Skills

Define new skills in `skill_registry.yaml`:

```yaml
skills:
  - skill_id: your_new_skill
    description: "Skill description (shown in LLM prompt)."
    eligible_agent_types: ["your_agent_type"]
    preconditions:
      - "not already_done"            # Boolean state check
    institutional_constraints:
      once_only: true                 # Can only execute once
      cost_type: "one_time"
    allowed_state_changes:
      - has_done_it                   # Agent attributes this skill modifies
    implementation_mapping: "env.execute_skill"
    conflicts_with: [conflicting_skill]
```

**Key fields**:
- `preconditions`: Control skill availability (e.g., `"not elevated"` = not yet elevated)
- `institutional_constraints`: Institutional rules (e.g., `once_only`, `annual`, `max_magnitude_pct`)
- `conflicts_with`: Mutually exclusive skills (e.g., increase_demand vs decrease_demand)

### Magnitude Parameterization (magnitude_pct)

For skills requiring quantitative decisions (e.g., irrigation demand change percentage), add a `numeric` field to the response format:

```yaml
# agent_types.yaml
fields:
  - { key: "magnitude_pct", type: "numeric", min: 1, max: 30, required: false }

# skill_registry.yaml
institutional_constraints:
  magnitude_type: "percentage"
  max_magnitude_pct: 30
  magnitude_default: 10              # Default when LLM omits the value
```

---

## 6. Custom Governance Rules

### Thinking Rules (Appraisal Coherence)

Block inconsistent actions based on LLM-generated construct labels:

```yaml
thinking_rules:
  - id: my_rule_id
    construct: THREAT_LABEL           # Single construct
    when_above: ["VH"]                # Trigger conditions
    blocked_skills: ["do_nothing"]    # Skills to block
    level: ERROR                      # ERROR = block; WARNING = log only
    message: "Must take action when threat is very high."

  # Multi-construct rule
  - id: multi_construct_rule
    conditions:
      - { construct: THREAT_LABEL, values: ["H", "VH"] }
      - { construct: CAPACITY_LABEL, values: ["H", "VH"] }
    blocked_skills: ["aggressive_action"]
    level: WARNING
```

### Identity Rules (State Constraints)

Block impossible actions based on agent physical state:

```yaml
identity_rules:
  - id: physical_block
    precondition: already_done        # Boolean state field
    blocked_skills: ["that_action"]
    level: ERROR
    message: "Physically impossible to repeat this action."
```

### Rule Evaluation Order

```text
1. Identity Rules    → Physical state constraints (always evaluated first)
2. Thinking Rules    → Appraisal coherence (in YAML order)
3. Domain Validators → Custom checks (physical, social, semantic)
```

The first ERROR-level violation stops evaluation and triggers a re-prompt (up to 3 governance retries).

---

## 7. Custom Prompt Templates

Create template files in the `config/prompts/` directory:

```text
You are {persona_narrative}.

=== Current Situation (Year {year}) ===
{situation_context}

=== Your Recent Memories ===
{memory_text}

=== Available Actions ===
{skills_text}

=== Your Task ===
Respond in the following format:
<<<DECISION_START>>>
reasoning: [your analysis]
threat_assessment: {"THREAT_LABEL": "...", "THREAT_REASON": "..."}
decision: [number]
<<<DECISION_END>>>
```

`TieredContextBuilder` fills placeholders at runtime.

---

## 8. Custom Environment (Simulation Engine)

The environment manages physical state and executes approved skills:

```python
class YourEnvironment:
    def __init__(self, agents, seed=42):
        self.agents = agents
        self.year = 0

    def advance_year(self):
        """Update environment state."""
        self.year += 1
        # Generate random events, update conditions, etc.

    def execute_skill(self, agent_id: str, skill_name: str, parameters: dict):
        """Execute an approved skill."""
        agent = self.agents[agent_id]
        if skill_name == "increase_demand":
            magnitude = parameters.get("magnitude_pct", 10) / 100
            agent.request *= (1 + magnitude)
        elif skill_name == "adopt_technology":
            agent.has_technology = True
```

---

## 9. Lifecycle Hooks

| Hook | Timing | Use Cases |
|------|--------|-----------|
| `pre_year` | Before each year | Inject memories, update context, synchronize state flags |
| `post_step` | After each agent decision | Log decisions to simulation records |
| `post_year` | After each year ends | Trigger reflection, save output files |

```python
runner.hooks = {
    "pre_year":  hooks.pre_year,
    "post_step": hooks.post_step,
    "post_year": hooks.post_year,
}
```

---

## 10. Common Customization Recipes

### Recipe 1: Add a New Skill (5 steps)

1. Define the skill in `skill_registry.yaml` (see Section 5)
2. Add the skill's state field to your agent's `state_params`
3. Update the prompt template to list the new action
4. Implement `execute_skill()` handling in your environment
5. Test: run 1 agent, 1 year → verify skill appears in audit trace

### Recipe 2: Add a Governance Rule (3 steps)

1. Add the rule to `agent_types.yaml` under `governance.strict.thinking_rules`
2. Choose severity: `ERROR` (blocks action) or `WARNING` (logs only)
3. Test: create a scenario where the rule should trigger → verify in audit trace

### Recipe 3: Switch Memory Engines (2 steps)

1. Change `engine_type` in your agent type's `memory` config
2. Adjust engine-specific parameters (window_size, emotion_keywords, etc.)

### Recipe 4: Add a Domain Validator (4 steps)

1. Write a check function following the `BuiltinCheck` signature (see Section 1)
2. Create a bridge function that aggregates your checks
3. Register via `builder.with_custom_validators([bridge_fn])`
4. Test: create a scenario where validation should fail → verify ERROR in audit trace

---

## 11. Testing Your Customization

### Smoke Test (1 agent, 1 year, mock LLM)

```bash
python examples/quickstart/01_barebone.py
```

Verify: experiment completes, audit CSV generated.

### Validation Test (5 agents, 3 years, real LLM)

```bash
python your_experiment/run.py --model gemma3:4b --years 3 --agents 5 --verbose
```

Verify: governance rules trigger, retries work, final decisions are plausible.

### Profile Test (governance coverage)

Check the `governance_summary.json` output for:
- `approved_rate` > 0 (governance is not blocking everything)
- `retry_rate` < 50% (rules are not too restrictive)
- All agent types appear in the audit trace

---

## 12. Reference Implementations

| Experiment | Theory | Config Directory |
|-----------|--------|-----------------|
| Flood Adaptation | PMT (Rogers, 1983) | `examples/governed_flood/config/` |
| Irrigation ABM | Dual-Appraisal (Hung & Yang, 2021) | `examples/irrigation_abm/config/` |

See the [Experiment Design Guide](experiment_design_guide.md) for the full build process and the [YAML Configuration Reference](../references/yaml_configuration_reference.md) for field-by-field documentation.
