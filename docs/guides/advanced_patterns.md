# Advanced Patterns Guide

This guide covers three advanced architectural patterns that arise when building
multi-agent simulations with WAGF: **state hierarchy**, **two-way coupling**,
and **per-agent-type LLM configuration**.

---

## 1. State Hierarchy

WAGF distinguishes three tiers of state. Understanding which tier to use — and
how data flows between them — is critical for correct governance evaluation and
prompt rendering.

### 1.1 The Three Tiers

| Tier | Storage | Mutability | Example |
|------|---------|-----------|---------|
| **Environment (global)** | `env` dict returned by `sim.advance_year()` | Updated once per step by the simulation engine | `year`, `basin_level`, `flood_occurred` |
| **Agent dynamic state** | `agent.dynamic_state` | Updated by hooks, `apply_delta()`, or direct assignment | `water_usage`, `has_insurance`, `relocated` |
| **Agent fixed attributes** | `agent.fixed_attributes` or `agent.custom_attributes` | Set at initialization; never mutated at runtime | `income`, `tenure`, `flood_zone` |

### 1.2 How State Enters the LLM Context

The `TieredContextBuilder.build()` method assembles a layered context dict:

```
context = {
    "personal": { ... },          # Agent-level data (fixed + dynamic merged)
    "local":    { "spatial": {}, "social": [], "visible_actions": [] },
    "global":   [ ... ],          # Global news / media
    "institutional": { ... },     # Government / insurance feedback
    "state":    { ... },          # Boolean subset for identity rules
    "environment_context": { ... } # Raw env dict for CognitiveCache hash
}
```

**Merge order** (later overwrites earlier):

1. `custom_attributes` (CSV / profile data)
2. Bare scalar attributes on the agent object
3. `dynamic_state` dict

This means `dynamic_state["has_insurance"] = False` will override an initial
`custom_attributes["has_insurance"] = True` in the prompt template.

### 1.3 The `state` Sub-Dict

The `state` sub-dict is automatically extracted:

```python
context["state"] = {k: v for k, v in personal.items() if isinstance(v, bool)}
```

Only **boolean** values enter `state`. This is the dict that **identity rules**
check via their `precondition` field. For example:

```yaml
identity_rules:
  - id: no_increase_when_warning
    precondition: warning_active       # checks state["warning_active"] is True
    blocked_skills: [increase_usage]
    level: ERROR
```

If you need a non-boolean value in an identity rule, convert it to a boolean
flag in a `pre_year` hook:

```python
def pre_year(year, env, agents):
    for a in agents.values():
        a.dynamic_state["is_low_income"] = a.fixed_attributes["income"] < 25000
```

### 1.4 Environment Context in Validation

During governance validation, the `SkillBrokerEngine` merges agent state and
environment into a flat `validation_context`:

```python
validation_context = {
    "agent_state": context,         # Full nested context
    "agent_type": agent_type,
    "env_state": env_context,       # Full env dict
    **context.get("state", {}),     # Flattened booleans
    **env_context                   # Flattened env keys
}
```

**Warning**: If `state` and `env_context` share a key name, `env_context`
wins silently. In debug mode (`python` without `-O`), a diagnostic warning
is logged. Use distinct key names to avoid collisions.

### 1.5 Practical Guidelines

| Scenario | Where to store | How to access in prompt |
|----------|---------------|----------------------|
| Shared world state (year, weather) | `sim.advance_year()` return dict | `{year}`, `{basin_level}` |
| Agent attribute that changes (insurance, elevation) | `agent.dynamic_state` | `{has_insurance}`, `{elevated}` |
| Agent attribute that never changes (income, tenure) | `agent.fixed_attributes` | `{income}`, `{tenure}` |
| Boolean flag for governance rules | `agent.dynamic_state` (must be `bool`) | Identity rule `precondition` |
| Derived field for prompt readability | `agent.dynamic_state` | `{income_range}`, `{flood_experience_summary}` |

---

## 2. Two-Way Coupling

In WAGF, agents affect the environment and the environment affects agents. This
is implemented through **explicit hooks**, not automatic feedback.

### 2.1 The Coupling Loop

```
┌─────────────────────────────────────────────────────┐
│                  Simulation Loop                     │
│                                                      │
│  1. sim.advance_year()          → env dict           │
│  2. pre_year(year, env, agents) → sync env→agents    │
│  3. LLM decides                 → SkillProposal      │
│  4. Governance validates         → ApprovedSkill      │
│  5. sim.execute_skill(skill)    → agents→env          │
│  6. post_step(agent, result)    → logging             │
│  7. post_year(year, agents)     → end-of-year logic   │
│                                                      │
│  Loop back to step 1                                 │
└─────────────────────────────────────────────────────┘
```

### 2.2 Agent → Environment (Steps 3–5)

When the LLM chooses a skill and governance approves it, the `ExperimentRunner`
calls `sim.execute_skill(approved_skill)`. The simulation engine updates its
internal state:

```python
class BasinSimulation:
    def execute_skill(self, approved_skill):
        if approved_skill.skill_name == "increase_usage":
            agent = self.agents[approved_skill.agent_id]
            usage = agent.dynamic_state.get("water_usage", 50)
            agent.dynamic_state["water_usage"] = min(100, usage + 10)
            return ExecutionResult(success=True, state_changes={"water_usage": +10})
```

The `state_changes` dict in `ExecutionResult` is applied to the agent via
`agent.apply_delta()` by the experiment runner.

### 2.3 Environment → Agent (Steps 1–2)

The environment feeds back into agents through the `pre_year` hook. This is
where you synchronize global state into individual agent state:

```python
def pre_year(year, env, agents):
    # Sync regulator's warning into each farmer's dynamic_state
    for agent in agents.values():
        if agent.agent_type == "farmer":
            agent.dynamic_state["warning_active"] = sim.warning_active

    # Update flood exposure based on environment
    if env.get("flood_occurred"):
        for agent in agents.values():
            agent.dynamic_state["flood_count"] += 1
            agent.dynamic_state["years_since_flood"] = 0
```

### 2.4 Cross-Agent Coupling (Phase Ordering)

When one agent type's decisions affect another's context, use **phase ordering**:

```python
builder.with_phase_order([
    ["regulator"],    # Phase 1: decides first
    ["farmer"],       # Phase 2: sees regulator's decision
])
```

Within each phase, agents execute sequentially (or in parallel if
`workers > 1`). Between phases, you can use `post_step` hooks to propagate
decisions.

### 2.5 What WAGF Does NOT Auto-Couple

WAGF does not automatically:

- Push `execute_skill` results into other agents' state
- Update `dynamic_state` from `env` without a hook
- Trigger cascading re-evaluation when one agent's decision changes

All inter-agent and environment-agent feedback must be **explicitly coded**
in lifecycle hooks. This is by design — it keeps the coupling transparent and
auditable.

### 2.6 Common Coupling Patterns

**Pattern A: Institutional feedback** — Government agent sets subsidy rate,
households see it next year:

```python
def pre_year(year, env, agents):
    gov = agents.get("NJ_STATE")
    if gov:
        rate = gov.dynamic_state.get("subsidy_rate", 0.5)
        for a in agents.values():
            if a.agent_type.startswith("household"):
                a.dynamic_state["current_subsidy_rate"] = rate
```

**Pattern B: Shared resource depletion** — Farmers drain a basin, basin level
affects next year's prompt:

```python
class BasinSim:
    def advance_year(self):
        total_usage = sum(a.dynamic_state.get("water_usage", 50) for a in self.farmers)
        self.basin_level = max(0, min(100, self.basin_level - drain + 5))
        return {"basin_level": self.basin_level, ...}
```

**Pattern C: Social observation** — Agent A sees Agent B's last action via the
social graph (handled by `SocialProvider` in context builder, no custom hook
needed).

---

## 3. Per-Agent-Type LLM Configuration

WAGF supports configuring different LLM parameters for each agent type. This is
useful when:

- Institutional agents need larger context windows than household agents
- Different agent types benefit from different temperature settings
- You want to use a cheaper model for simple agent types

### 3.1 Parameter Override Hierarchy

LLM parameters are resolved with a three-level merge (later wins):

```
shared.llm  →  global_config.llm  →  <agent_type>.llm_params
```

This is implemented in `AgentTypeConfig.get_llm_params()`:

```python
def get_llm_params(self, agent_type: str) -> Dict[str, Any]:
    shared_llm = self._config.get("shared", {}).get("llm", {})
    global_llm = self._config.get("global_config", {}).get("llm", {})
    agent_llm  = cfg.get("llm_params", {})
    merged = {}
    merged.update(shared_llm)
    merged.update(global_llm)
    merged.update(agent_llm)
    return merged
```

### 3.2 YAML Configuration

```yaml
global_config:
  llm:
    num_ctx: 8192
    num_predict: 1024
    temperature: 0.7

household_owner:
  llm_params:
    num_ctx: 16384      # Owners get larger context (complex decisions)
    temperature: 0.8    # Slightly more creative

household_renter:
  llm_params:
    num_ctx: 4096       # Renters have simpler decisions
    temperature: 0.6    # More deterministic

government:
  llm_params:
    num_ctx: 32768      # Institutional agents see aggregate data
    num_predict: 2048   # May need longer reasoning
```

### 3.3 How It Works at Runtime

The `ExperimentRunner` caches one `llm_invoke` function per agent type:

```python
def get_llm_invoke(self, agent_type: str) -> Callable:
    if agent_type not in self._llm_cache:
        overrides = self.broker.config.get_llm_params(agent_type)
        model_name = overrides.pop("model", None) or self.config.model
        self._llm_cache[agent_type] = create_llm_invoke(
            model_name,               # Per-type model if specified, else CLI default
            verbose=self.config.verbose,
            overrides=overrides       # Per-type parameter overrides
        )
    return self._llm_cache[agent_type]
```

When processing each agent, the runner selects the type-specific invoke:

```python
result = self.broker.process_step(
    agent_id=agent.id,
    llm_invoke=self.get_llm_invoke(agent.agent_type),
    ...
)
```

### 3.4 Available Override Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | str | Ollama model name (overrides CLI `--model` for this type) |
| `num_ctx` | int | Context window size (tokens) |
| `num_predict` | int | Max tokens to generate (-1 = unlimited) |
| `temperature` | float | Sampling temperature (0.0–2.0) |
| `top_p` | float | Nucleus sampling threshold (0.0–1.0) |
| `top_k` | int | Top-k sampling |

### 3.5 Injecting a Custom LLM Function

For testing or when you need entirely different model backends per type, you can
directly inject into the runner's LLM cache:

```python
runner = builder.build()

# Use a mock for regulators, real Ollama for farmers
runner._llm_cache["regulator"] = mock_llm
runner._llm_cache["farmer"] = create_llm_invoke("gemma3:4b")
```

This pattern is used in the `multi_agent_simple` example for testing without
Ollama.

### 3.6 Per-Type Model Names (YAML-Native)

You can specify a different Ollama model for each agent type directly in YAML
via the `model` key inside `llm_params`:

```yaml
household_owner:
  llm_params:
    model: gemma3:4b        # Uses gemma3:4b for owners
    num_ctx: 16384

household_renter:
  llm_params:
    model: gemma3:1b        # Uses smaller model for renters
    num_ctx: 4096

government:
  llm_params:
    model: llama3.3:70b     # Uses large model for policy agent
    num_ctx: 32768
```

If `model` is not specified in `llm_params`, the CLI/builder model
(`ExperimentBuilder.with_model(...)`) is used as fallback.

---

## Quick Reference: Hook Signatures

| Hook | Signature | When Called |
|------|-----------|------------|
| `pre_year` / `pre_step` | `(year: int, env: dict, agents: dict)` | Before any agent acts |
| `post_step` | `(agent: BaseAgent, result: SkillBrokerResult)` | After each agent's decision |
| `post_year` / `post_step_end` | `(year: int, agents: dict)` | After all agents have acted |

**Note**: `post_year` does NOT receive the `env` dict. If you need environment
data in `post_year`, capture it via closure:

```python
def make_hooks(sim):
    def post_year(year, agents):
        print(f"Basin level: {sim.basin_level}")
    return {"post_year": post_year}
```

---

## See Also

- [Multi-Agent Setup Guide](multi_agent_setup_guide.md) — Full MA configuration walkthrough
- [YAML Configuration Reference](../references/yaml_configuration_reference.md) — Field-by-field reference
- [Troubleshooting Guide](troubleshooting_guide.md) — Common errors and fixes
