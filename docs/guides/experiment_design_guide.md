# Experiment Design Guide

This guide walks through building a new SAGE-governed experiment from scratch. Both existing experiments — flood adaptation (PMT) and Colorado River irrigation (dual-appraisal) — follow this pattern.

> **Audience**: Graduate students and researchers building hydro-social ABM experiments using the SAGE governance middleware.

---

## Architecture Overview

Every experiment has 6 components that plug into the `ExperimentBuilder` fluent API:

```
1. Configuration Files    → agent_types.yaml + skill_registry.yaml
2. Prompt Template        → LLM context construction
3. Domain Validators      → BuiltinCheck functions
4. Simulation Environment → State management + skill execution
5. Lifecycle Hooks        → Pre/post year/step callbacks
6. Experiment Runner      → ExperimentBuilder assembly
```

---

## Step 1: Define Your Domain

Choose a behavioral theory and define the agent's cognitive dimensions (appraisal constructs):

| Domain | Theory | Threat Construct | Capacity Construct |
|--------|--------|-----------------|-------------------|
| Flood adaptation | PMT (Rogers, 1983) | TP_LABEL (threat perception) | CP_LABEL (coping appraisal) |
| Irrigation demand | Dual-Appraisal (Hung & Yang, 2021) | WSA_LABEL (water scarcity) | ACA_LABEL (adaptive capacity) |
| *(Your domain)* | *(Your theory)* | *(Your threat construct)* | *(Your capacity construct)* |

The 5-level ordinal scale (VL, L, M, H, VH) is shared across all domains. Governance rules and validators reference these labels to enforce behavioral coherence.

---

## Step 2: Create Configuration Files

### 2.1 `agent_types.yaml` — The Central Configuration

This YAML file defines everything the framework needs: response format, constructs, governance rules, memory configuration, and personas.

#### Response Format

Define the fields the LLM must output. Fields are rendered in order — place `reasoning` first for the **Reasoning Before Rating** pattern:

```yaml
shared:
  response_format:
    delimiter_start: "<<<DECISION_START>>>"
    delimiter_end: "<<<DECISION_END>>>"
    fields:
      - { key: "reasoning", type: "text", required: false }
      - {
          key: "your_threat_appraisal",
          type: "appraisal",
          required: true,
          construct: "THREAT_LABEL",
          reason_hint: "One sentence on your threat assessment."
        }
      - {
          key: "your_capacity_appraisal",
          type: "appraisal",
          required: true,
          construct: "CAPACITY_LABEL",
          reason_hint: "One sentence on your adaptive capacity."
        }
      - { key: "decision", type: "choice", required: true }
      # Optional: numeric magnitude field
      - { key: "magnitude_pct", type: "numeric", min: 1, max: 30, required: false }
```

**Field types**:
- `text`: Free-form string (reasoning)
- `appraisal`: JSON object with `{LABEL: "VL"..."VH", REASON: "..."}` structure
- `choice`: Integer skill ID from the skill registry
- `numeric`: Bounded number (e.g., magnitude percentage)

#### Constructs

Register the behavioral constructs from your theory:

```yaml
shared:
  constructs:
    - id: THREAT_LABEL
      name: "Threat Assessment"
      scale: ["VL", "L", "M", "H", "VH"]
    - id: CAPACITY_LABEL
      name: "Capacity Assessment"
      scale: ["VL", "L", "M", "H", "VH"]
```

#### Governance Rules

Define thinking rules (appraisal-based) and identity rules (state-based) under a named profile:

```yaml
your_agent_type:
  governance:
    strict:
      thinking_rules:
        # Block inaction when threat is extreme
        - id: extreme_threat_block
          construct: THREAT_LABEL
          when_above: ["VH"]
          blocked_skills: ["do_nothing"]
          level: ERROR
          message: "Very High threat requires adaptive action."

        # Block expensive actions when capacity is very low
        - id: low_capacity_block
          conditions:
            - { construct: CAPACITY_LABEL, values: ["VL"] }
          blocked_skills: ["expensive_action"]
          level: ERROR
          message: "Very Low capacity cannot justify expensive action."

        # Multi-construct rule (WARNING only)
        - id: high_threat_high_cope_warning
          conditions:
            - { construct: THREAT_LABEL, values: ["H", "VH"] }
            - { construct: CAPACITY_LABEL, values: ["H", "VH"] }
          blocked_skills: ["aggressive_action"]
          level: WARNING
          message: "High threat + high capacity suggests conservation."

      identity_rules:
        # Physical impossibility
        - id: already_done_block
          precondition: action_completed    # Boolean field on agent state
          blocked_skills: ["that_action"]
          level: ERROR
          message: "Cannot repeat irreversible action."
```

**Rule evaluation order**: Identity rules first, then thinking rules in YAML order. First ERROR-level violation terminates evaluation and triggers re-prompting (up to 3 governance retries).

#### Memory Configuration

```yaml
your_agent_type:
  memory:
    engine_type: "human_centric"       # WRR-validated engine
    window_size: 5                     # Short-term buffer
    top_k_significant: 2              # Top memories by decayed importance

    emotion_keywords:
      crisis: ["drought", "shortage", "flood", "damage"]
      strategic: ["decision", "adopt", "reduce", "increase"]
      positive: ["surplus", "adequate", "safe", "protected"]
      social: ["neighbor", "community", "upstream"]

    emotional_weights:
      crisis: 1.0
      strategic: 0.8
      positive: 0.6
      social: 0.4
      baseline_observation: 0.1

    source_weights:
      personal: 1.0
      neighbor: 0.8
      community: 0.6
      general_knowledge: 0.4

    source_patterns:
      personal: ["i ", "my ", "me "]
      neighbor: ["neighbor", "adjacent"]
      community: ["basin", "community", "region"]
```

#### Reflection Configuration

```yaml
global_config:
  reflection:
    interval: 1                       # Reflect every year
    batch_size: 10                    # Agents per reflection batch
    importance_boost: 0.9             # Importance score for generated insights
    method: hybrid
    questions:                        # Domain-specific guidance
      - "Was your strategy effective given the conditions?"
      - "What patterns do you notice between your actions and outcomes?"
      - "How should you adjust your approach going forward?"
```

### 2.2 `skill_registry.yaml` — Available Actions

Define every action an agent can propose:

```yaml
skills:
  - skill_id: increase_demand
    description: "Request more resource allocation."
    eligible_agent_types: ["your_agent_type"]
    preconditions:
      - "not at_cap"                  # State field check
    institutional_constraints:
      annual: true
      max_magnitude_pct: 30
      magnitude_default: 10
    allowed_state_changes:
      - request
      - allocation
    implementation_mapping: "env.execute_skill"
    conflicts_with: [decrease_demand]

  - skill_id: adopt_technology
    description: "Invest in efficiency technology."
    eligible_agent_types: ["your_agent_type"]
    preconditions:
      - "not has_technology"          # Once-only check
    institutional_constraints:
      once_only: true
    allowed_state_changes:
      - has_technology
    implementation_mapping: "env.execute_skill"

  - skill_id: maintain_status_quo
    description: "No change to current practices."
    eligible_agent_types: ["*"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes: []
    implementation_mapping: "env.execute_skill"

default_skill: maintain_status_quo
```

---

## Step 3: Write Prompt Template

Create a template file (e.g., `config/prompts/your_agent.txt`) that the `TieredContextBuilder` populates with agent-specific context:

```text
You are {persona_narrative}.

=== CURRENT SITUATION (Year {year}) ===
{situation_context}

=== YOUR RECENT MEMORIES ===
{memory_text}

=== AVAILABLE ACTIONS ===
{skills_text}

=== YOUR TASK ===
Assess the situation using two dimensions:
1. **Threat Assessment** (THREAT_LABEL): How severe is the current threat? (VL/L/M/H/VH)
2. **Capacity Assessment** (CAPACITY_LABEL): How well can you adapt? (VL/L/M/H/VH)

Then choose ONE action from the list above.

Respond EXACTLY in this format:
<<<DECISION_START>>>
reasoning: [your analysis]
your_threat_appraisal: {"THREAT_LABEL": "...", "THREAT_REASON": "..."}
your_capacity_appraisal: {"CAPACITY_LABEL": "...", "CAPACITY_REASON": "..."}
decision: [number]
<<<DECISION_END>>>
```

---

## Step 4: Implement Domain Validators

Domain validators provide physical and social checks beyond YAML-driven rules. Each check function follows the `BuiltinCheck` callable signature: `(skill_name, rules, context) -> List[ValidationResult]`.

```python
# validators/your_validators.py
from typing import List, Dict, Any
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import ValidationResult

def physical_cap_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block resource increase when at physical cap."""
    if skill_name != "increase_demand":
        return []
    if not context.get("at_cap", False):
        return []
    return [ValidationResult(
        valid=False,
        validator_name="DomainPhysicalValidator",
        errors=["Cannot increase — already at physical capacity."],
        warnings=[],
        metadata={"rule_id": "resource_cap_check", "level": "ERROR"},
    )]

def social_norm_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Warn if agent contradicts community trend."""
    if skill_name != "increase_demand":
        return []
    if context.get("community_conservation_rate", 0) > 0.5:
        return [ValidationResult(
            valid=True,  # WARNING: allow but log
            validator_name="DomainSocialValidator",
            errors=[],
            warnings=["Most peers are conserving — consider alignment."],
            metadata={"rule_id": "community_norm_warning", "level": "WARNING"},
        )]
    return []

# Aggregate all checks
ALL_DOMAIN_CHECKS = [physical_cap_check, social_norm_check]
```

**ValidationResult fields**:
- `valid`: `False` for ERROR (blocks action), `True` for WARNING (logs only)
- `errors`: List of error messages (sent to LLM on retry)
- `warnings`: List of warning messages (logged for analysis)
- `metadata`: Dict with `rule_id`, `level`, `category` for audit tracking

### Bridge to ExperimentBuilder

`ExperimentBuilder.with_custom_validators()` expects `(proposal, context, skill_registry) -> List[ValidationResult]`. Write a bridge function that adapts the BuiltinCheck signature:

```python
def domain_governance_validator(proposal, context, skill_registry=None):
    """Bridge domain checks to SkillBrokerEngine custom_validators."""
    skill_name = getattr(proposal, "skill_name", str(proposal))
    results = []
    for check in ALL_DOMAIN_CHECKS:
        results.extend(check(skill_name, [], context))
    return results
```

---

## Step 5: Build Simulation Environment

The environment manages physical state and executes approved skills:

```python
class YourEnvironment:
    def __init__(self, agents, seed=42):
        self.agents = agents
        self.year = 0
        self.rng = random.Random(seed)

    def advance_year(self):
        """Update environment state for new year."""
        self.year += 1
        # Generate stochastic events, update conditions, etc.

    def execute_skill(self, agent_id: str, skill_name: str, parameters: dict):
        """Apply approved skill to agent state."""
        agent = self.agents[agent_id]
        magnitude = parameters.get("magnitude_pct", 10) / 100

        if skill_name == "increase_demand":
            agent.request = min(agent.request * (1 + magnitude), agent.max_allocation)
        elif skill_name == "decrease_demand":
            agent.request = max(agent.request * (1 - magnitude), agent.min_allocation)
        elif skill_name == "adopt_technology":
            agent.has_technology = True
        # maintain_status_quo: no state change

    def get_agent_context(self, agent_id: str) -> dict:
        """Build situation context for prompt template."""
        agent = self.agents[agent_id]
        return {
            "year": self.year,
            "current_allocation": agent.request,
            "conditions": self._get_conditions(),
            # ... domain-specific context
        }
```

---

## Step 6: Assemble with ExperimentBuilder

```python
from broker.core.experiment import ExperimentBuilder

# Load configuration
registry = load_skill_registry("config/skill_registry.yaml")
memory_engine = create_memory_engine(agent_config)  # HumanCentricMemoryEngine

# Build experiment
builder = (
    ExperimentBuilder()
    .with_model(args.model)                          # e.g., "gemma3:4b"
    .with_years(args.years)                          # Simulation duration
    .with_agents(agents)                             # Dict[str, BaseAgent]
    .with_simulation(env)                            # Your environment
    .with_context_builder(ctx_builder)               # TieredContextBuilder
    .with_skill_registry(registry)                   # From YAML
    .with_memory_engine(memory_engine)               # HumanCentric
    .with_governance("strict", "config/agent_types.yaml")
    .with_custom_validators([domain_governance_validator])
    .with_exact_output(str(output_dir))
    .with_workers(args.workers)
    .with_seed(args.seed)
)
runner = builder.build()

# Attach lifecycle hooks
runner.hooks = {
    "pre_year":  hooks.pre_year,       # Inject memories, update context
    "post_step": hooks.post_step,      # Record decisions
    "post_year": hooks.post_year,      # Reflection, logging
}

# Run
runner.run(llm_invoke=create_llm_invoke(args.model))
```

---

## Step 7: Implement Lifecycle Hooks

Hooks inject domain-specific behavior at key simulation points:

```python
class YourLifecycleHooks:
    def __init__(self, env, runner, reflection_engine, output_dir):
        self.env = env
        self.runner = runner
        self.reflection_engine = reflection_engine
        self.output_dir = output_dir

    def pre_year(self, year, agents):
        """Called before each simulation year."""
        self.env.advance_year()

        for agent_id, agent in agents.items():
            # Inject situation memories
            memory = self.runner.memory_engine
            memory.add_memory(agent_id, f"Year {year}: {self.env.describe_conditions()}")

            # Add action-outcome feedback from prior year
            if year > 1:
                feedback = self._build_feedback(agent_id, year - 1)
                memory.add_memory(agent_id, feedback)

            # Sync physical state flags for governance
            agent.state["at_cap"] = agent.request >= agent.max_allocation
            agent.state["has_technology"] = agent.has_technology

    def post_step(self, agent_id, result):
        """Called after each agent's decision is processed."""
        # Record to simulation log
        self.log_decision(agent_id, result)

    def post_year(self, year, agents):
        """Called after all agents have decided."""
        # Trigger batch reflection
        if self.reflection_engine:
            self.reflection_engine.reflect_batch(agents, year)

        # Write yearly output files
        self.save_yearly_log(year)
```

---

## Step 8: Configure Memory & Reflection

### Memory Engine Selection

| Engine | Mode | Use Case |
|--------|------|----------|
| `HumanCentricMemoryEngine` | Basic ranking | **WRR-validated**. Window + top-k by decayed importance. |
| `ImportanceMemoryEngine` | Weighted scoring | Experimental. Recency/importance/context weights. |
| `WindowMemoryEngine` | FIFO only | Baseline. Fixed-size sliding window. |

For WRR experiments, use `HumanCentricMemoryEngine` in basic ranking mode. Importance is computed as:

```
importance = emotional_weight * source_weight
```

Keywords in the memory text are matched against `emotion_keywords` and `source_patterns` defined in `agent_types.yaml`.

### Reflection

The `ReflectionEngine` runs at configurable intervals (default: every year). Each reflection batch:

1. Retrieves recent episodic memories for a group of agents
2. Sends them to the LLM with domain-specific guidance questions
3. Generates semantic insights (high-importance memories)
4. Consolidates insights into long-term memory

**Action-outcome feedback** connects decisions to consequences:
> "Year 5: You chose to decrease_demand by 15%. Outcome: Supply was adequate, utilisation dropped to 65%."

This enables causal learning through the reflection loop.

---

## Output Files & Analysis

Every experiment produces a standard output structure:

```
results/<run_name>/
  simulation_log.csv                 # Per-agent per-year decisions + constructs
  <agent_type>_governance_audit.csv  # Governance validation trace
  governance_summary.json            # Aggregate intervention statistics
  config_snapshot.yaml               # Full config for reproducibility
  raw/<agent_type>_traces.jsonl      # Full LLM interaction traces
  reflection_log.jsonl               # Reflection insights
```

### Key Metrics

| Metric | Source | Meaning |
|--------|--------|---------|
| `total_interventions` | `governance_summary.json` | ERROR-level blocks (governance corrected LLM) |
| `retry_success` | `governance_summary.json` | Agent corrected behavior on retry |
| `total_warnings` | `governance_summary.json` | WARNING observations (logged, not blocked) |
| Construct distributions | `simulation_log.csv` | Appraisal label frequencies per year |
| Skill distributions | `simulation_log.csv` | Action choice frequencies per year |

---

## Key Principles

1. **LLM proposes, System disposes** — The LLM only suggests skills; the system validates and executes.
2. **Configuration over code** — Governance rules, response format, and memory config are YAML-driven. New domains require minimal Python.
3. **Reasoning Before Rating** — Place the `reasoning` field first in `response_format.fields` to improve autoregressive generation quality.
4. **Two retry mechanisms** — Format retries (up to 2) for parse failures; governance retries (up to 3) for rule violations.
5. **Behavioral theory compliance** — Governance rules enforce coherence between appraisal dimensions and action choices, preventing cognitive hallucination.

---

## Reference Implementations

| Experiment | Theory | Agents | Horizon | Key Files |
|-----------|--------|--------|---------|-----------|
| `examples/governed_flood/` | PMT (Rogers, 1983) | 100 households | 10 years | [README](../../examples/governed_flood/README.md) |
| `examples/irrigation_abm/` | Dual-Appraisal (Hung & Yang, 2021) | 78 CRSS users | 42 years | [README](../../examples/irrigation_abm/README.md) |
| `examples/single_agent/` | PMT (full ablation) | 100 households | 10 years | Groups A/B/C validation |
