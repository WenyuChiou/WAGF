# Multi-Agent Setup Guide — Water Agent Governance Framework

This guide walks you through building a multi-agent experiment in WAGF. It covers
agent type configuration, phase ordering, shared environments, lifecycle hooks,
social graphs, interaction hubs, cross-type governance, and scaling patterns.

**Target audience**: ABM researchers who have completed the
[Quickstart Guide](quickstart_guide.md) (Tiers 1 and 2) and want to build
simulations with heterogeneous agent populations.

**Reference example**: `examples/multi_agent_simple/` — a self-contained 7-agent
experiment (1 regulator + 6 farmers) that demonstrates every concept in this guide.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Step 1: Define Agent Types](#3-step-1-define-agent-types)
4. [Step 2: Define Skills per Type](#4-step-2-define-skills-per-type)
5. [Step 3: Phase Ordering](#5-step-3-phase-ordering)
6. [Step 4: Environment Design](#6-step-4-environment-design)
7. [Step 5: Lifecycle Hooks](#7-step-5-lifecycle-hooks)
8. [Step 6: Social Graph (optional)](#8-step-6-social-graph-optional)
9. [Step 7: InteractionHub (optional)](#9-step-7-interactionhub-optional)
10. [Step 8: Governance Across Types](#10-step-8-governance-across-types)
11. [Scaling Up](#11-scaling-up)
12. [Common Patterns](#12-common-patterns)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Overview

### What "Multi-Agent" Means in WAGF

In a single-agent WAGF experiment (Quickstart Tiers 1-2), every agent shares the
same type, the same skills, and the same governance rules. The simulation loop is
straightforward: advance the environment, then process each agent sequentially.

A **multi-agent** experiment introduces:

- **Heterogeneous agent types** — different roles with distinct skills, prompts,
  and governance rules (e.g., a `regulator` type and a `farmer` type).
- **Phase ordering** — some types must decide before others. A regulator issues
  warnings *before* farmers make usage decisions.
- **Cross-type governance** — a rule triggered by one type's action constrains
  another type's choices (e.g., a conservation warning blocks farmer increases).
- **Social interaction** — agents observe neighbors, exchange gossip, and
  influence each other through a social graph.

### When to Use Multi-Agent vs. Single-Agent

| Scenario | Recommended Approach |
|----------|---------------------|
| All agents have the same role and skills | Single-agent (Tier 1-2) |
| Agents differ only in initial attributes (e.g., income) | Single-agent with CSV loading |
| Agents have fundamentally different roles and skills | **Multi-agent** |
| Decisions of one group depend on another group's actions | **Multi-agent with phase ordering** |
| Agents influence each other through observation or gossip | **Multi-agent with social graph** |

---

## 2. Prerequisites

Before starting this guide, ensure you have:

1. **Completed Quickstart Tier 1** (`01_barebone.py`) — you understand the
   Agent-Broker-Simulation loop.
2. **Completed Quickstart Tier 2** (`02_governance.py`) — you understand how
   governance rules block and retry agent decisions.
3. **A working Python environment** with the WAGF package importable.
4. **Familiarity with YAML** — agent types, skills, and governance rules are
   configured in YAML files.

The progression path is:

```
01_barebone.py        -> 1 agent, 2 skills, no governance
02_governance.py      -> 1 agent, 2 skills, identity rule + retry
multi_agent_simple/   -> 7 agents, 5 skills, 2 types, phase ordering  <-- THIS GUIDE
```

---

## 3. Step 1: Define Agent Types

### The agent_types.yaml File

Each agent type is a top-level key in `agent_types.yaml`. The file also contains
`shared` (cross-type configuration) and `global_config` (experiment-wide settings).

Here is the complete structure from the multi-agent example:

```yaml
# agent_types.yaml

shared:
  rating_scale: |
    ### RATING SCALE:
    VL = Very Low | L = Low | M = Medium | H = High | VH = Very High

  response_format:
    delimiter_start: "<<<DECISION_START>>>"
    delimiter_end: "<<<DECISION_END>>>"
    fields:
      - { key: "reasoning", type: "text", required: false }
      - { key: "decision", type: "decision", required: true }

global_config:
  memory:
    window_size: 5
  llm:
    num_ctx: 4096
    num_predict: 1024
    max_retries: 2
  governance:
    max_retries: 2
    max_reports_per_retry: 2

# --- Agent Type 1: Regulator ---
regulator:
  prompt_template: |
    You are a water basin regulator.
    Current basin level: {basin_level}% of capacity.
    Number of farmers: {num_farmers}.

    Choose one action:
    1. issue_warning - Issue conservation warning to farmers
    2. no_action - Take no regulatory action

    {response_format}
  parsing:
    strict_mode: true
    decision_keywords: ["decision"]
    skill_map:
      "1": issue_warning
      "2": no_action
    actions:
      - id: issue_warning
        aliases: ["1", "issue warning", "warn"]
      - id: no_action
        aliases: ["2", "no action", "none"]
  governance:
    strict:
      thinking_rules:
        - id: warn_when_low
          description: "Must warn when basin is critically low"
          conditions:
            - construct: "basin_level"
              operator: "<"
              value: 30
          blocked_skills: [no_action]
          level: ERROR
          message: "Basin critically low - must issue warning."

# --- Agent Type 2: Farmer ---
farmer:
  prompt_template: |
    You are a farmer managing water usage.
    Current water level: {basin_level}% of capacity.
    Your current usage: {water_usage} units.
    {warning_text}

    Choose one action:
    1. increase_usage - Use more water for crops
    2. decrease_usage - Conserve water
    3. maintain_usage - Keep current level

    {response_format}
  parsing:
    strict_mode: true
    decision_keywords: ["decision"]
    skill_map:
      "1": increase_usage
      "2": decrease_usage
      "3": maintain_usage
    actions:
      - id: increase_usage
        aliases: ["1", "increase"]
      - id: decrease_usage
        aliases: ["2", "decrease", "conserve"]
      - id: maintain_usage
        aliases: ["3", "maintain", "keep"]
  governance:
    strict:
      thinking_rules:
        - id: no_increase_when_warning
          description: "Cannot increase usage when conservation warning is active"
          conditions:
            - construct: "warning_active"
              operator: "=="
              value: 1
          blocked_skills: [increase_usage]
          level: ERROR
          message: "Conservation warning active - cannot increase usage."
```

### Key Sections Explained

| Section | Purpose |
|---------|---------|
| `shared` | Response format and rating scales shared by all agent types |
| `global_config` | Experiment-wide LLM parameters, memory window, governance retries |
| `regulator` / `farmer` | Per-type prompt template, parsing rules, and governance rules |

### Prompt Template Variables

Template variables like `{basin_level}` and `{warning_text}` are filled at runtime
from the environment dict returned by `advance_year()`. The `TieredContextBuilder`
merges environment state, agent state, and memory into the template. Any key present
in the environment dict or the agent's `dynamic_state` can be referenced in a template.

### Creating Agents in Python

Each agent is created with an `AgentConfig` that specifies `agent_type`, which must
match one of the top-level keys in `agent_types.yaml`:

```python
from cognitive_governance.agents import BaseAgent, AgentConfig
from cognitive_governance.agents.base import StateParam, Skill

def make_regulator():
    cfg = AgentConfig(
        name="Regulator",
        agent_type="regulator",           # Must match YAML key
        state_params=[
            StateParam("warning_active", (0, 1), 0.0, "Whether a warning is issued"),
        ],
        objectives=[],
        constraints=[],
        skills=[
            Skill("issue_warning", "Issue conservation warning", "warning_active", "increase"),
            Skill("no_action", "No regulatory action", None, "none"),
        ],
    )
    return BaseAgent(cfg)

def make_farmer(farmer_id: int):
    cfg = AgentConfig(
        name=f"Farmer_{farmer_id}",
        agent_type="farmer",              # Must match YAML key
        state_params=[
            StateParam("water_usage", (0, 100), 50.0, "Water usage units"),
        ],
        objectives=[],
        constraints=[],
        skills=[
            Skill("increase_usage", "Increase water usage", "water_usage", "increase"),
            Skill("decrease_usage", "Decrease water usage", "water_usage", "decrease"),
            Skill("maintain_usage", "Keep current usage", None, "none"),
        ],
    )
    return BaseAgent(cfg)

# Build the agent dictionary
agents = {"Regulator": make_regulator()}
for i in range(1, 7):
    agents[f"Farmer_{i}"] = make_farmer(i)
```

**Important**: The `agent_type` string on `AgentConfig` must exactly match the
YAML key. If you define a `regulator` section in YAML but set
`agent_type="reg"`, the framework will not find the prompt template or
governance rules for that agent.

---

## 4. Step 2: Define Skills per Type

### The skill_registry.yaml File

The skill registry maps skill IDs to agent types, preconditions, and execution
targets. The `eligible_agent_types` field controls which agent types can use
each skill:

```yaml
# skill_registry.yaml

skills:
  # --- Farmer skills ---
  - skill_id: increase_usage
    description: "Increase water usage by a moderate amount"
    eligible_agent_types: ["farmer"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes:
      - water_usage
    implementation_mapping: "sim.increase_usage"

  - skill_id: decrease_usage
    description: "Decrease water usage to conserve"
    eligible_agent_types: ["farmer"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes:
      - water_usage
    implementation_mapping: "sim.decrease_usage"
    conflicts_with: [increase_usage]

  - skill_id: maintain_usage
    description: "Keep current water usage level"
    eligible_agent_types: ["farmer"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes: []
    implementation_mapping: "sim.noop"

  # --- Regulator skills ---
  - skill_id: issue_warning
    description: "Issue a conservation warning to all farmers"
    eligible_agent_types: ["regulator"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes:
      - warning_active
    implementation_mapping: "sim.issue_warning"

  - skill_id: no_action
    description: "Take no regulatory action"
    eligible_agent_types: ["regulator"]
    preconditions: []
    institutional_constraints: {}
    allowed_state_changes: []
    implementation_mapping: "sim.noop"

default_skill: maintain_usage
```

### Key Fields

| Field | Description |
|-------|-------------|
| `skill_id` | Unique identifier; must match the skill names in agent code and YAML parsing |
| `eligible_agent_types` | List of agent types that can propose this skill |
| `preconditions` | Boolean state checks (e.g., `"not elevated"` blocks re-elevation) |
| `institutional_constraints` | Policy rules like `once_only`, `cost_type`, `max_magnitude_pct` |
| `conflicts_with` | Mutually exclusive skills (e.g., increase vs. decrease) |
| `default_skill` | Fallback when all governance retries are exhausted (REJECTED) |

### Why eligible_agent_types Matters

When the broker receives a skill proposal from an agent, it checks
`eligible_agent_types` before governance evaluation. If a farmer somehow proposes
`issue_warning`, the broker rejects it immediately because `farmer` is not in
that skill's `eligible_agent_types`. This acts as a first-pass type-safety check.

For more details on skill configuration, see the
[Customization Guide](customization_guide_en.md), Section 5.

---

## 5. Step 3: Phase Ordering

### Why Order Matters

In many multi-agent systems, decisions are interdependent across types. Consider
a water basin scenario:

1. The **regulator** observes the basin level and decides whether to issue a
   conservation warning.
2. **Farmers** then react to the warning (or its absence) when choosing their
   water usage.

If farmers decide *before* the regulator, they cannot react to the warning. Phase
ordering solves this by grouping agent types into sequential execution phases.

### Configuring Phase Order

Use `.with_phase_order()` on the `ExperimentBuilder`:

```python
runner = (
    ExperimentBuilder()
    .with_model("mock")
    .with_years(5)
    .with_agents(agents)
    .with_simulation(sim)
    .with_skill_registry(str(script_dir / "skill_registry.yaml"))
    .with_memory_engine(WindowMemoryEngine(window_size=5))
    .with_governance("strict", str(script_dir / "agent_types.yaml"))
    .with_phase_order([["regulator"], ["farmer"]])   # Phase 1 then Phase 2
    .with_exact_output(str(script_dir / "results"))
    .with_workers(1)
    .with_seed(42)
).build()
```

The argument is a list of lists, where each inner list is a group of agent type
strings that execute together in that phase:

```python
# Two-phase example: regulator first, then all farmers
.with_phase_order([["regulator"], ["farmer"]])

# Three-phase example: government, then insurance, then households
.with_phase_order([["government"], ["insurance"], ["household_owner", "household_renter"]])
```

### Execution Semantics

Within each phase:
- If `workers=1`, agents execute **sequentially** (deterministic order).
- If `workers>1`, agents execute **in parallel** using `ThreadPoolExecutor`.

Phases themselves always execute **sequentially**. Phase 1 completes entirely
before Phase 2 begins.

### What Happens Without Phase Order

If you do not call `.with_phase_order()`, all agents execute in a single phase
(backward compatible with single-agent experiments). The internal implementation
wraps all active agents into one phase:

```python
# Internal: no phase_order configured
agent_phases = [active_agents]  # Single phase
```

### Unmatched Agent Types

If an agent's type does not appear in any phase group, it is appended to an
extra phase at the end. This prevents silent omission of agents.

---

## 6. Step 4: Environment Design

### The Simulation Engine Contract

Your simulation engine must implement two methods:

```python
class YourSimulation:
    def advance_year(self) -> dict:
        """Called once per year. Returns environment state dict."""
        ...

    def execute_skill(self, approved_skill) -> ExecutionResult:
        """Called once per agent after governance approval."""
        ...
```

The `advance_year()` return dict is merged into the prompt context. Every key
in this dict becomes available as a template variable (e.g., `{basin_level}`).

### Multi-Agent Environment Example

In a multi-agent simulation, the environment typically manages shared state
that multiple agent types read and write:

```python
from broker.interfaces.skill_types import ExecutionResult

class BasinSimulation:
    """Tracks a shared basin level that farmers draw from."""

    def __init__(self, agents, initial_level=80):
        self.agents = agents
        self.year = 0
        self.basin_level = initial_level
        self.warning_active = False

    def advance_year(self):
        self.year += 1
        # Basin replenishes 5% per year, drained by farmer usage
        total_usage = sum(
            a.dynamic_state.get("water_usage", 50)
            for a in self.agents.values()
            if a.agent_type == "farmer"
        )
        drain = (total_usage - 300) * 0.05
        self.basin_level = max(0, min(100, self.basin_level - drain + 5))

        return {
            "current_year": self.year,
            "basin_level": round(self.basin_level, 1),
            "num_farmers": 6,
            "warning_active": self.warning_active,
            "warning_text": (
                "CONSERVATION WARNING: The regulator has issued a warning. "
                "You must not increase usage."
                if self.warning_active
                else "No conservation warnings are active."
            ),
        }

    def execute_skill(self, approved_skill):
        agent = self.agents.get(approved_skill.agent_id)
        if not agent:
            return ExecutionResult(success=False, error="Agent not found")

        name = approved_skill.skill_name

        if name == "issue_warning":
            self.warning_active = True
            agent.dynamic_state["warning_active"] = 1.0
            return ExecutionResult(success=True, state_changes={"warning_active": True})

        elif name == "no_action":
            self.warning_active = False
            agent.dynamic_state["warning_active"] = 0.0
            return ExecutionResult(success=True, state_changes={})

        elif name == "increase_usage":
            usage = agent.dynamic_state.get("water_usage", 50)
            agent.dynamic_state["water_usage"] = min(100, usage + 10)
            return ExecutionResult(success=True, state_changes={"water_usage": +10})

        elif name == "decrease_usage":
            usage = agent.dynamic_state.get("water_usage", 50)
            agent.dynamic_state["water_usage"] = max(0, usage - 10)
            return ExecutionResult(success=True, state_changes={"water_usage": -10})

        return ExecutionResult(success=True, state_changes={})
```

### Design Principles for Multi-Agent Environments

1. **Shared state** (like `basin_level`) must be computed from all agents,
   not just one type.
2. **Cross-type effects** (like `warning_active`) are set by one type's skill
   execution and read by another type's governance rules.
3. **ExecutionResult** must always return `state_changes` so the broker can
   update the agent's state and memory.

---

## 7. Step 5: Lifecycle Hooks

Lifecycle hooks inject domain logic into the simulation loop without modifying
the core framework. Three hooks are available:

| Hook | Signature | Timing |
|------|-----------|--------|
| `pre_year` | `(year, env, agents_dict)` | Before agent decisions each year |
| `post_step` | `(agent, result)` | After each individual agent's decision |
| `post_year` | `(year, env, agents_dict)` | After all agents have decided |

### pre_year: State Synchronization

The most critical hook for multi-agent experiments. Use it to sync cross-type
state into each agent's `dynamic_state` so that governance rules can read it:

```python
def pre_year(year, env, agents_dict):
    """Inject environment state into agent context for governance rules."""
    print(f"\n{'='*50}")
    print(f"  Year {year}  |  Basin: {env['basin_level']}%  |  Warning: {env['warning_active']}")
    print(f"{'='*50}")

    # Sync warning_active into each farmer's dynamic state
    # so the governance construct 'warning_active' can check it
    for agent in agents_dict.values():
        if agent.agent_type == "farmer":
            sim = ...  # reference to your simulation
            agent.dynamic_state["warning_active"] = 1.0 if sim.warning_active else 0.0
```

**Why this matters**: Governance rules evaluate constructs from the agent's
`dynamic_state`. If the regulator issues a warning but you never sync
`warning_active` into farmer agents, the `no_increase_when_warning` rule
will never trigger.

### post_step: Decision Logging

Log each agent's decision for debugging and audit:

```python
def post_step(agent, result):
    """Log each agent's decision."""
    skill = getattr(result, "approved_skill", None)
    name = skill.skill_name if skill else "unknown"
    status = skill.approval_status if skill else "N/A"
    retries = getattr(result, "retry_count", 0)
    marker = f" [retried {retries}x]" if retries > 0 else ""

    if agent.agent_type == "regulator":
        print(f"  [REG] {agent.name}: {name} ({status}){marker}")
    else:
        usage = agent.dynamic_state.get("water_usage", "?")
        print(f"  [FRM] {agent.name}: {name} ({status}) -> usage={usage}{marker}")
```

### post_year: End-of-Year Summaries

Compute aggregate statistics after all agents have decided:

```python
def post_year(year, env, agents_dict):
    """End-of-year summary."""
    usages = [
        a.dynamic_state.get("water_usage", 50)
        for a in agents_dict.values()
        if a.agent_type == "farmer"
    ]
    avg = sum(usages) / len(usages) if usages else 0
    print(f"  --- Summary: avg usage={avg:.0f}, basin={env['basin_level']}% ---")
```

### Registering Hooks

Hooks are registered as a dictionary on the runner:

```python
runner.hooks = {
    "pre_year": pre_year,
    "post_step": post_step,
    "post_year": post_year,
}
```

You can also use the builder's fluent API:

```python
runner = (
    ExperimentBuilder()
    # ... other configuration ...
    .with_lifecycle_hooks(
        pre_year=pre_year,
        post_step=post_step,
        post_year=post_year,
    )
).build()
```

### Hook Protocol Signatures

The framework validates hook signatures at initialization. If your hook does not
match the expected protocol, a diagnostic warning is logged. The protocols are
defined in `broker/interfaces/lifecycle_protocols.py`:

```python
class PreYearHook(Protocol):
    def __call__(self, year: int, env: Dict[str, Any], agents: Dict[str, Any]) -> None: ...

class PostStepHook(Protocol):
    def __call__(self, agent: Any, result: SkillBrokerResult) -> None: ...

class PostYearHook(Protocol):
    def __call__(self, year: int, agents: Dict[str, Any]) -> None: ...
```

### Generic Aliases

The framework supports both `pre_year`/`post_year` (time-based) and
`pre_step`/`post_step_end` (generic) aliases. Both are invoked if registered.
For multi-agent experiments that use year-based time steps, prefer `pre_year`
and `post_year` for clarity.

---

## 8. Step 6: Social Graph (optional)

A social graph defines who can observe whom. If your agents need to see
neighbors' actions, exchange gossip, or be influenced by local norms, you
need a social graph.

### Available Graph Types

| Type | Class | Description |
|------|-------|-------------|
| `"global"` | `GlobalGraph` | Fully connected; every agent sees every other agent |
| `"random"` | `RandomGraph` | Erdos-Renyi random graph with edge probability `p` |
| `"neighborhood"` | `NeighborhoodGraph` | K-nearest-neighbor ring topology |
| `"spatial"` | `SpatialNeighborhoodGraph` | Grid-based spatial proximity with Euclidean/Manhattan distance |
| `"custom"` | `CustomGraph` | User-defined edges via a builder function |

### Creating a Social Graph

Use the `create_social_graph` factory function:

```python
from broker.components.social_graph import create_social_graph

agent_ids = list(agents.keys())

# Option 1: Neighborhood ring (k=4 neighbors each)
graph = create_social_graph("neighborhood", agent_ids, k=4)

# Option 2: Random graph (10% edge probability)
graph = create_social_graph("random", agent_ids, p=0.10, seed=42)

# Option 3: Spatial graph with grid positions
positions = {
    "H0001": (100, 200),
    "H0002": (101, 201),
    "H0003": (150, 250),
}
graph = create_social_graph(
    "spatial",
    list(positions.keys()),
    positions=positions,
    radius=3.0,          # 3 grid cells = ~90m at 30m resolution
    metric="euclidean",
    fallback_k=2,        # Minimum 2 neighbors even if outside radius
)

# Option 4: Custom edge builder
def org_hierarchy(agent_ids):
    return [("Manager_1", "Employee_1"), ("Manager_1", "Employee_2")]

graph = create_social_graph("custom", agent_ids, edge_builder=org_hierarchy)
```

### Graph API

Once created, the graph provides these methods:

```python
graph.get_neighbors("Farmer_1")        # -> ["Farmer_2", "Farmer_6"]
graph.get_neighbor_count("Farmer_1")   # -> 2
graph.add_edge("Farmer_1", "Farmer_5") # Bidirectional
graph.remove_edge("Farmer_1", "Farmer_5")
graph.summary()                        # -> {"num_agents": 7, "num_edges": 12, ...}
graph.to_dict()                        # -> {"Farmer_1": ["Farmer_2", ...], ...}
```

### Subclassing SocialGraph

For advanced topologies (e.g., scale-free networks), subclass `SocialGraph`:

```python
from broker.components.social_graph import SocialGraph

class ScaleFreeGraph(SocialGraph):
    def __init__(self, agent_ids, m=2, seed=None):
        super().__init__(agent_ids)
        # Implement Barabasi-Albert preferential attachment
        # ...
        for a, b in computed_edges:
            self.add_edge(a, b)
```

---

## 9. Step 7: InteractionHub (optional)

The `InteractionHub` sits on top of the social graph and manages information
diffusion. It aggregates spatial observations, social gossip, and environment
state into a unified "worldview" for each agent.

### Creating an InteractionHub

```python
from broker.components.social_graph import create_social_graph
from broker.components.interaction_hub import InteractionHub
from broker.components.memory_engine import WindowMemoryEngine

graph = create_social_graph("neighborhood", list(agents.keys()), k=4)
memory = WindowMemoryEngine(window_size=5)

hub = InteractionHub(
    graph=graph,
    memory_engine=memory,
    spatial_observables=["has_flood_insurance", "elevated"],  # Observable attributes
)
```

### Spatial Context

Aggregates observable attributes across an agent's neighbors:

```python
spatial = hub.get_spatial_context("Farmer_1", agents)
# -> {"neighbor_count": 4, "has_flood_insurance_pct": 0.5, "elevated_pct": 0.25}
```

The `spatial_observables` list defines which agent attributes are aggregated.
For each attribute, the hub computes the percentage of neighbors for whom that
attribute is truthy.

### Social Context (Gossip)

Retrieves gossip from neighbors' memories:

```python
social = hub.get_social_context("Farmer_1", agents, max_gossip=2)
# -> {
#     "gossip": ["Neighbor Farmer_2 mentioned: 'Year 3: Decided to: Decrease usage'"],
#     "visible_actions": [...],
#     "neighbor_count": 4
# }
```

Gossip is sampled from neighbors who have content in their memory engine.
The `max_gossip` parameter controls how many gossip snippets are included.

### Tiered Context Building

For full integration, the hub can build a complete tiered context dict:

```python
context = hub.build_tiered_context(
    agent_id="Farmer_1",
    agents=agents,
    global_news=["Basin authority announces new conservation targets."],
)
# -> {
#     "personal": {"id": "Farmer_1", "memory": [...], "water_usage": 50, ...},
#     "local": {"spatial": {...}, "social": [...], "visible_actions": [...]},
#     "global": ["Basin authority announces new conservation targets."],
#     "institutional": {},
#     "state": {...}  # Alias for "personal" (validator compatibility)
# }
```

### SDK Observer Integration (v2)

For domain-agnostic observation, the hub supports SDK observers:

```python
hub = InteractionHub(
    graph=graph,
    memory_engine=memory,
    social_observer=my_social_observer,       # SDK SocialObserver
    environment_observer=my_env_observer,     # SDK EnvironmentObserver
)

# v2 methods use observer pattern instead of hardcoded attribute checks
social = hub.get_social_context_v2("Farmer_1", agents)
env_obs = hub.get_environment_observation("Farmer_1", agents)
```

---

## 10. Step 8: Governance Across Types

### Cross-Type Rule Design

The most powerful multi-agent pattern is **cross-type governance**: rules where
one agent type's actions constrain another type's decisions.

In the basin example:

1. **Regulator** executes `issue_warning` in Phase 1.
2. The `pre_year` hook syncs `warning_active = 1.0` into every farmer's
   `dynamic_state`.
3. **Farmer** governance rule `no_increase_when_warning` checks
   `warning_active == 1` and blocks `increase_usage`.

The governance rule in `agent_types.yaml`:

```yaml
farmer:
  governance:
    strict:
      thinking_rules:
        - id: no_increase_when_warning
          description: "Cannot increase usage when conservation warning is active"
          conditions:
            - construct: "warning_active"
              operator: "=="
              value: 1
          blocked_skills: [increase_usage]
          level: ERROR
          message: "Conservation warning active - cannot increase usage."
```

### The Three-Step Pattern

Cross-type governance always follows this pattern:

```
1. Producer Agent (Phase N)  -->  Modifies shared state or own state
2. pre_year Hook             -->  Syncs state into Consumer Agent's dynamic_state
3. Consumer Agent (Phase N+1) --> Governance rule reads the synced state
```

### Rule Levels

| Level | Behavior |
|-------|----------|
| `ERROR` | Block the skill and trigger a governance retry (re-prompt the LLM) |
| `WARNING` | Log a warning but allow the skill to proceed |

For multi-agent experiments, **always use ERROR** for cross-type constraints.
WARNING-level rules have minimal behavioral impact, especially with smaller LLMs.
This is a hard-won lesson from production experiments.

### Identity Rules vs. Thinking Rules

- **Identity rules** check physical state constraints (e.g., "cannot re-elevate
  an already elevated house"). These use `precondition` with a boolean state field.
- **Thinking rules** check appraisal-action coherence or cross-type conditions.
  These use `conditions` with construct/operator/value triples.

Both rule types can reference any key in the agent's `dynamic_state`, which is
why the `pre_year` sync hook is essential.

---

## 11. Scaling Up

### From 7 Agents to 100+

The multi-agent example uses 7 agents for clarity. Here is how to scale:

#### 1. Use CSV Agent Loading

Instead of creating agents in code, load them from a CSV file:

```python
runner = (
    ExperimentBuilder()
    .with_model("gemma3:4b")
    .with_csv_agents(
        path="data/farmers.csv",
        mapping={
            "HH_ID": "id",
            "Income_Level": "income",
            "Farm_Size": "farm_size",
            "Water_Right": "water_right",
        },
        agent_type="farmer",
    )
    # ... rest of configuration
).build()
```

The `load_agents_from_csv` function reads each row and creates a `BaseAgent` with
mapped attributes stored in `agent.custom_attributes`. The `agent_type` parameter
must match a key in your `agent_types.yaml`.

#### 2. Increase Workers

For experiments with 50+ agents, parallel LLM execution significantly reduces
wall-clock time:

```python
.with_workers(4)    # 4 parallel LLM calls within each phase
```

**Important**: Parallelism operates *within* a phase. Phase ordering is still
respected: all Phase 1 agents finish before Phase 2 begins. Within a phase,
up to `workers` agents are processed simultaneously.

#### 3. Use CognitiveCache

The `CognitiveCache` (in `broker/core/efficiency.py`) automatically skips
redundant LLM calls when an agent's context hash matches a previous decision.
It is enabled by default and stored at `{output_dir}/cognitive_cache.json`.

The cache computes a hash from:
- Agent state (`dynamic_state`)
- Environment state (current year, conditions)
- Memory content

If two agents have identical state and context, the second agent reuses the
first agent's decision without calling the LLM. This is especially effective
for agents with similar initial conditions.

**Cache invalidation**: If a cached decision fails governance re-validation
(because state has changed since caching), the cache entry is automatically
invalidated and the LLM is called normally.

#### 4. Choose the Right Memory Engine

| Engine | Best For | Scaling Behavior |
|--------|----------|-----------------|
| `WindowMemoryEngine` | Prototyping, baselines | O(1) per retrieval, fixed window |
| `HumanCentricMemoryEngine` | Production experiments | O(n) per retrieval with decay scoring |
| `ImportanceMemoryEngine` | Experimental research | O(n) with weighted multi-factor scoring |

For 100+ agent experiments, `WindowMemoryEngine` is fastest but may miss important
long-term memories. `HumanCentricMemoryEngine` with `window_size=5` and
`top_k_significant=2` provides a good balance.

#### 5. Auto-Tune (Experimental)

For automatic performance tuning based on model size and available VRAM:

```python
.with_auto_tune()   # Detects model size, queries GPU, sets optimal workers/context
```

---

## 12. Common Patterns

### Pattern 1: Institutional Agents

Institutional agents (government, insurance companies) typically:
- Have a small number of instances (1-3)
- Execute in early phases
- Produce state that constrains later agents
- Do not need social graphs (they observe aggregate statistics)

```python
# Institutional agent: 1 government, executes in Phase 1
agents["Government"] = make_government_agent()

# Household agents: 100 households, execute in Phase 2
for i in range(100):
    agents[f"Household_{i}"] = make_household(i)

builder.with_phase_order([["government"], ["household"]])
```

### Pattern 2: Tiered Context Per Agent Type

Different agent types often need different context. The `TieredContextBuilder`
resolves this automatically via per-type prompt templates in `agent_types.yaml`.
Each type's template references only the variables it needs:

```yaml
# Government sees aggregate statistics
government:
  prompt_template: |
    Total agents: {num_agents}
    Average adoption rate: {avg_adoption_rate}%

# Household sees personal state and neighbor actions
household:
  prompt_template: |
    Your income: ${income}
    Flood zone: {flood_zone}
    Neighbors who adapted: {adapted_neighbors_pct}%
```

### Pattern 3: Memory Seeding from Agent Profiles

When agents are loaded from CSV or created with initial attributes, the framework
seeds their memory automatically during `ExperimentBuilder.build()`:

```python
# Internal: called by ExperimentBuilder.build()
from broker.components.memory_engine import seed_memory_from_agents
seed_memory_from_agents(mem_engine, agents)
```

If an agent has a `memory` attribute (e.g., from CSV loading with pipe-delimited
strings), those entries are added to the memory engine at initialization.

### Pattern 4: Mixed Type Populations

For experiments where agents of the same type have different sub-roles
(e.g., homeowners vs. renters), define separate types in YAML:

```yaml
household_owner:
  prompt_template: ...
  governance:
    strict:
      thinking_rules:
        - id: cannot_elevate_if_done
          precondition: elevated
          blocked_skills: [elevate_house]
          level: ERROR

household_renter:
  prompt_template: ...
  governance:
    strict:
      thinking_rules:
        - id: renter_affordability
          conditions:
            - construct: "income"
              operator: "<"
              value: 15000
          blocked_skills: [relocate]
          level: ERROR
```

Then in phase ordering, group them in the same phase since they are peers:

```python
.with_phase_order([["government"], ["insurance"], ["household_owner", "household_renter"]])
```

### Pattern 5: Deactivating Agents Mid-Simulation

Agents with `is_active = False` are skipped during the simulation loop. Use
this for agents that have relocated, been bought out, or otherwise exited:

```python
def execute_skill(self, approved_skill):
    if approved_skill.skill_name == "accept_buyout":
        agent = self.agents[approved_skill.agent_id]
        agent.is_active = False  # Agent will be skipped in future years
        return ExecutionResult(success=True, state_changes={"bought_out": True})
```

The `ExperimentRunner.run()` method filters active agents each year:

```python
active_agents = [a for a in self.agents.values() if getattr(a, 'is_active', True)]
```

### Pattern 6: Custom Validators for Cross-Type Constraints

For complex validation logic that cannot be expressed in YAML rules, use custom
validators:

```python
def basin_physical_validator(proposal, context, skill_registry=None):
    """Block all increase skills when basin is below 20%."""
    skill_name = getattr(proposal, "skill_name", str(proposal))
    basin = context.get("basin_level", 100)
    if "increase" in skill_name and basin < 20:
        from broker.validators.governance.base_validator import ValidationResult
        return [ValidationResult(
            valid=False,
            validator_name="BasinPhysicalValidator",
            errors=["Basin critically low - all increases blocked."],
            warnings=[],
            metadata={"rule_id": "basin_critical", "level": "ERROR"},
        )]
    return []

builder.with_custom_validators([basin_physical_validator])
```

See the [Customization Guide](customization_guide_en.md), Section 1 for the
full validator signature and registration pattern.

---

## 13. Troubleshooting

### Common Multi-Agent Pitfalls

#### "Governance rule never triggers"

**Symptom**: A thinking rule like `no_increase_when_warning` is defined but the
farmer still chooses `increase_usage` without being blocked.

**Root cause**: The construct referenced in the rule (e.g., `warning_active`) is
not present in the farmer agent's `dynamic_state` at the time governance evaluates.

**Solution**: Ensure your `pre_year` hook syncs the relevant state into each
target agent's `dynamic_state` *before* the agent's phase executes. Remember
that governance rules can only read from the agent's own state, not from other
agents or the environment directly.

#### "Agent type not found in config"

**Symptom**: The broker logs `[Governance:Diagnostic]` warnings about missing
agent type configuration.

**Root cause**: The `agent_type` string on `AgentConfig` does not match any
top-level key in `agent_types.yaml`.

**Solution**: Ensure exact string match. Check for typos, case sensitivity, and
trailing whitespace. The YAML key `farmer` will not match `agent_type="Farmer"`.

#### "Skill not in eligible_agent_types"

**Symptom**: An agent's proposal is immediately rejected with no governance
evaluation.

**Root cause**: The skill's `eligible_agent_types` in `skill_registry.yaml`
does not include the agent's type.

**Solution**: Add the agent type to the skill's `eligible_agent_types` list. If
a skill should be available to all types, list all types explicitly.

#### "Phase ordering has no effect"

**Symptom**: All agents still seem to execute in arbitrary order.

**Root cause**: `.with_phase_order()` was not called, or was called with an
empty list, or the agent type strings in the phase list do not match the actual
`agent_type` values.

**Solution**: Verify that the strings in `.with_phase_order([["regulator"], ["farmer"]])`
exactly match the `agent_type` field on each agent's `AgentConfig`.

#### "CognitiveCache keeps returning stale decisions"

**Symptom**: Agents make the same decision every year despite changing conditions.

**Root cause**: The cache hash includes agent state, environment, and memory. If
these inputs are identical between years (e.g., the environment dict does not
change), the cache returns the same result.

**Solution**: Ensure `advance_year()` returns year-varying data (at minimum,
include `current_year` in the return dict). The framework automatically includes
`current_year` if you omit it, but year-specific context like basin levels
should change to invalidate the cache naturally.

#### "Parallel execution produces non-deterministic results"

**Symptom**: Running the same experiment twice with the same seed produces
different agent decision sequences.

**Root cause**: `ThreadPoolExecutor` does not guarantee execution order.
Within a phase, agents may complete in different orders across runs.

**Solution**: Set `workers=1` for deterministic reproducibility. Use parallel
execution only for production runs where you need throughput over exact
reproducibility. Alternatively, sort results by agent ID before processing.

#### "Memory engine grows unbounded for large agent populations"

**Symptom**: Memory usage increases linearly with agents and years.

**Root cause**: `WindowMemoryEngine` stores memories per agent. With 400 agents
over 13 years, memory can accumulate.

**Solution**: Set an appropriate `window_size` to bound memory per agent. For
production experiments, `window_size=5` is recommended. The
`HumanCentricMemoryEngine` with decay scoring also naturally prioritizes
recent memories.

### Diagnostic Checklist

When debugging a multi-agent experiment, check these items in order:

1. Does each agent's `agent_type` match a YAML key? (`agent_types.yaml`)
2. Does each skill's `eligible_agent_types` include the correct types? (`skill_registry.yaml`)
3. Does `.with_phase_order()` use the correct type strings?
4. Does `advance_year()` return all template variables referenced in prompts?
5. Does `pre_year` sync cross-type state into target agents' `dynamic_state`?
6. Are governance rules at `ERROR` level (not `WARNING`) for behavioral constraints?
7. Does `execute_skill()` return `ExecutionResult` with `state_changes`?

### Further Reading

- [Advanced Patterns Guide](advanced_patterns.md) — State hierarchy, two-way coupling, per-type LLM config
- [Quickstart Guide](quickstart_guide.md) — Tiers 1-2 fundamentals
- [Customization Guide](customization_guide_en.md) — Custom validators, memory engines, prompts
- [Troubleshooting Guide](troubleshooting_guide.md) — Full error catalog with solutions
- [Experiment Design Guide](experiment_design_guide.md) — End-to-end design process

---

## Appendix: Complete Multi-Agent Example

The full working example is at `examples/multi_agent_simple/`. The directory
structure is:

```
examples/multi_agent_simple/
    run.py                  # Main experiment script
    agent_types.yaml        # Agent type definitions + governance rules
    skill_registry.yaml     # Skill definitions per type
    results/                # Output directory (created on run)
```

To run the example:

```bash
python examples/multi_agent_simple/run.py
```

Expected output:

```
WAGF Quickstart - Multi-Agent with Phase Ordering
==================================================
Regulator decides first; farmers react to warnings.
Agents: 1 regulator + 6 farmers = 7 total

==================================================
  Year 1  |  Basin: 80%  |  Warning: False
==================================================
  [REG] Regulator: no_action (APPROVED)
  [FRM] Farmer_1: maintain_usage (APPROVED) -> usage=50
  [FRM] Farmer_2: maintain_usage (APPROVED) -> usage=50
  ...
```

The regulator observes the basin level and decides whether to warn. Farmers then
react to the warning (or its absence). When the basin drops below thresholds,
the governance system enforces conservation rules automatically.

---

*This guide is part of the WAGF documentation suite. For questions or contributions,
see the project repository.*
