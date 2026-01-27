# Single-Agent Flood Adaptation Case Design

> **Domain**: Flood Risk Management
> **Agent Type**: Household
> **Framework**: Protection Motivation Theory (PMT)

---

## Overview

The Single-Agent (SA) flood adaptation case simulates a household making protective decisions in response to flood events over multiple years. The agent uses Protection Motivation Theory (PMT) constructs to appraise threats and coping options.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SA Pipeline Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│   │  Context │───→│   LLM    │───→│  Parse   │───→│ Validate │ │
│   │  Builder │    │ Invoke   │    │ Response │    │ Decision │ │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│        │                                               │        │
│        │                                               ↓        │
│   ┌──────────┐                                  ┌──────────┐   │
│   │   Env    │←─────────────────────────────────│ Execute  │   │
│   │  Update  │                                  │  Skill   │   │
│   └──────────┘                                  └──────────┘   │
│        │                                               │        │
│        └──────────────────┬────────────────────────────┘        │
│                           ↓                                     │
│                    ┌──────────┐                                 │
│                    │  Audit   │                                 │
│                    │  Trace   │                                 │
│                    └──────────┘                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## PMT-Based Decision Framework

### The 5 PMT Constructs

| Construct | Abbr | Description | Scale |
|-----------|------|-------------|-------|
| **Threat Appraisal** | TP | Perceived severity and probability of flood | VL/L/M/H/VH |
| **Coping Appraisal** | CP | Perceived ability to cope with flood | VL/L/M/H/VH |
| **Self-Efficacy** | SE | Belief in ability to execute protective action | VL/L/M/H/VH |
| **Response Efficacy** | RE | Belief that action will reduce threat | VL/L/M/H/VH |
| **Protection Motivation** | PM | Overall motivation to protect | VL/L/M/H/VH |

### VL/L/M/H/VH Scoring Format

The agent outputs appraisals using a 5-level scale:

| Label | Meaning | Numeric Range |
|-------|---------|---------------|
| **VL** | Very Low | 0.0 - 0.2 |
| **L** | Low | 0.2 - 0.4 |
| **M** | Medium | 0.4 - 0.6 |
| **H** | High | 0.6 - 0.8 |
| **VH** | Very High | 0.8 - 1.0 |

### Example LLM Response

```json
{
  "decision": 1,
  "threat_appraisal": {
    "label": "VH",
    "reason": "Major flood last year caused $50,000 damage"
  },
  "coping_appraisal": {
    "label": "M",
    "reason": "Insurance would help but savings are limited"
  },
  "reasoning": {
    "threat": "The flood probability is increasing based on recent events",
    "coping": "Buying insurance provides financial protection at reasonable cost"
  }
}
```

---

## Available Skills

### Skill Registry

| ID | Skill Name | Description | Precondition |
|----|------------|-------------|--------------|
| 1 | `buy_insurance` | Purchase flood insurance (annual, provides financial protection) | Can renew annually |
| 2 | `elevate_house` | Raise house foundation (one-time, prevents physical damage) | `elevated == False` |
| 3 | `relocate` | Leave neighborhood permanently (eliminates flood risk) | `relocated == False` |
| 4 | `do_nothing` | Take no protective action this year | Always available |

> **Source**: `examples/single_agent/skill_registry.yaml`

### Dynamic Skill Mapping

The skill numbering changes based on agent state:

**Non-Elevated Agent (4 options)**:
```
1. buy_insurance
2. elevate_house
3. relocate
4. do_nothing
```

**Elevated Agent (3 options)**:
```
1. buy_insurance
2. relocate
3. do_nothing
```

### Skill Eligibility

Skills are filtered based on agent state in `FinalContextBuilder`:

```python
# Agent cannot elevate twice
if agent.elevated:
    available_skills.remove("elevate_house")

# Dynamic skill map adjusts numbering
if elevated:
    dynamic_skill_map = {"1": "buy_insurance", "2": "relocate", "3": "do_nothing"}
else:
    dynamic_skill_map = {"1": "buy_insurance", "2": "elevate_house", "3": "relocate", "4": "do_nothing"}
```

---

## Governance Rules

> **Source**: `examples/single_agent/agent_types.yaml` (lines 341-401)

### Governance Profiles

Three profiles are available: `strict`, `relaxed`, and `disabled`.

### Strict Mode - Thinking Rules

| Rule ID | Construct | Condition | Blocked Skills | Level |
|---------|-----------|-----------|----------------|-------|
| `extreme_threat_block` | TP_LABEL | TP = VH | `do_nothing` | ERROR |
| `low_coping_block` | CP_LABEL | CP = VL | `elevate_house`, `relocate` | ERROR |
| `relocation_threat_low` | TP_LABEL | TP = VL or L | `relocate` | ERROR |
| `elevation_threat_low` | TP_LABEL | TP = VL or L | `elevate_house` | ERROR |

### Strict Mode - Identity Rules

| Rule ID | Precondition | Blocked Skills | Level |
|---------|--------------|----------------|-------|
| `elevation_block` | `elevated == True` | `elevate_house` | ERROR |

### Relaxed Mode

| Rule Type | Construct | Condition | Blocked Skills | Level |
|-----------|-----------|-----------|----------------|-------|
| Thinking | TP_LABEL | TP = H+ | `do_nothing` | WARNING |
| Identity | `elevated == True` | - | `elevate_house` | WARNING |

### Disabled Mode

All rules are disabled - no governance enforcement.

### CLI Usage

```bash
# Run with strict governance (default)
python run_flood.py --governance-mode strict

# Run with relaxed governance
python run_flood.py --governance-mode relaxed

# Run without governance
python run_flood.py --governance-mode disabled
```

---

## Memory System

### Available Memory Engines

SA supports multiple memory engine types via `--memory-engine` flag:

| Engine | Description | Use Case |
|--------|-------------|----------|
| `window` | Sliding window (default) | Simple, last N memories |
| `importance` | Active retrieval with keywords | Domain-specific filtering |
| `humancentric` | Emotional encoding + consolidation | Research on memory bias |
| `hierarchical` | Tiered (Core, Episodic, Semantic) | Complex memory structure |

### CLI Usage

```bash
# Use default window memory
python run_flood.py --memory-engine window --window-size 5

# Use importance-based retrieval
python run_flood.py --memory-engine importance

# Use human-centric with emotional encoding
python run_flood.py --memory-engine humancentric
```

### Window Memory Engine (Default)

```python
class WindowMemoryEngine:
    """Sliding window memory - keeps last N experiences."""

    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.memories = {}  # agent_id -> list[str]

    def add_memory(self, agent_id: str, content: str):
        self.memories.setdefault(agent_id, []).append(content)
        # Trim to window size
        self.memories[agent_id] = self.memories[agent_id][-self.window_size:]

    def retrieve(self, agent, top_k: int = 3) -> list[str]:
        return self.memories.get(agent.id, [])[-top_k:]
```

### Memory in Context

Past experiences are included in the LLM prompt:

```
=== YOUR MEMORY ===
Year 1: Got flooded with $10,000 damage on my house.
Year 2: No flood occurred this year. | Elevation grants are available.
Year 3: A flood occurred, but my house was protected by its elevation.
```

### Memory Content Format

Each year generates consolidated memory entries:

```python
# Example memory entry
"Year 3: Got flooded with $10,000 damage. | Elevation grants are available. | I observe 20% of neighbors elevated and 5% relocated."
```

---

## Environment

### Flood Event Modes

| Mode | Description | CLI Flag |
|------|-------------|----------|
| `fixed` | Use predefined flood years from `flood_years.csv` | `--flood-mode fixed` |
| `prob` | Probabilistic (20% per year by default) | `--flood-mode prob` |

### Flood Event Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FLOOD_PROBABILITY` | 0.2 | Base probability per year (prob mode) |
| `GRANT_PROBABILITY` | 0.5 | Probability grants are available |
| `flood_threshold` | 0.1-0.5 | Agent-specific flood susceptibility |

### State Variables

| Variable | Type | Description |
|----------|------|-------------|
| `elevated` | bool | House has been elevated |
| `has_insurance` | bool | Active insurance policy (expires annually) |
| `relocated` | bool | Agent has left the neighborhood |
| `trust_in_insurance` | float | Trust level (0.0-1.0) |
| `trust_in_neighbors` | float | Trust in community (0.0-1.0) |
| `flood_threshold` | float | Agent's flood susceptibility |

### Lifecycle Hooks

```python
def pre_year(year: int, env: dict, agents: dict):
    """Called before each simulation year."""
    # Generate flood event based on mode
    if flood_mode == "prob":
        flood_event = random.random() < FLOOD_PROBABILITY
    else:  # fixed mode
        flood_event = year in flood_years

    # Generate grant availability
    grant_available = random.random() < GRANT_PROBABILITY

    # Add memories for each agent
    for agent in agents.values():
        if flood_event and not agent.elevated:
            if random.random() < agent.flood_threshold:
                mem = f"Year {year}: Got flooded with $10,000 damage."

def post_year(year: int, agents: dict):
    """Called after each simulation year."""
    # Update trust values based on outcomes
    for agent in agents.values():
        if agent.has_insurance:
            agent.trust_in_insurance += (-0.10 if flooded else 0.02)
        # Community action rate affects neighbor trust
        if community_action_rate > 0.30:
            agent.trust_in_neighbors += 0.04
```

### Insurance Expiry

Insurance expires annually - agents must re-purchase each year:

```python
# In execute_skill()
if skill != "buy_insurance":
    state_changes["has_insurance"] = False  # Expires if not renewed
```

---

## Audit Trace

### Complete Trace Structure

Every decision produces an audit trace:

```json
{
  "run_id": "sa_run_20260127_001",
  "step_id": 1,
  "timestamp": "2026-01-27T10:30:00Z",
  "year": 1,
  "agent_id": "household_001",
  "agent_type": "household",

  "input": "You are a household in a flood-prone area...",
  "raw_output": "<<<DECISION_START>>>{\"decision\": 1}<<<DECISION_END>>>",

  "skill_proposal": {
    "skill_name": "buy_insurance",
    "reasoning": {
      "threat_appraisal": {"label": "VH", "reason": "Recent floods"},
      "coping_appraisal": {"label": "M", "reason": "Limited budget"}
    },
    "parse_layer": "json"
  },

  "validation_result": {
    "outcome": "APPROVED",
    "issues": []
  },

  "approved_skill": {
    "skill_name": "buy_insurance",
    "execution_mapping": "sim.buy_insurance"
  },

  "state_before": {"elevated": false, "has_insurance": false},
  "state_after": {"elevated": false, "has_insurance": true},

  "retry_count": 0,
  "validated": true
}
```

---

## Response Parsing

### Parse Layers

The parser attempts multiple strategies:

| Layer | Method | Example |
|-------|--------|---------|
| 1 | JSON with delimiters | `<<<DECISION_START>>>{"decision": 1}<<<DECISION_END>>>` |
| 2 | Raw JSON | `{"decision": 1}` |
| 3 | Keyword extraction | `I will buy insurance` → skill=buy_insurance |
| 4 | Naked digit | `1` → skill=buy_insurance |

### Think Tag Stripping

For models like Qwen3 that include think tags:

```
<think>Let me consider the options carefully...</think>
{"decision": 1, "threat_appraisal": {"label": "H"}}
```

The parser strips `<think>...</think>` before JSON extraction.

---

## Running the Experiment

### Basic Run

```bash
python examples/single_agent/run_flood.py \
  --model llama3.2:3b \
  --years 10 \
  --output results/sa_run_001
```

### Configuration

```yaml
# config.yaml
experiment:
  years: 10
  flood_probability: 0.3

agent:
  type: household
  initial_state:
    elevated: false
    has_insurance: false
    savings: 50000
    property_value: 200000

governance:
  enabled: true
  strictness: relaxed
```

### Output Files

| File | Description |
|------|-------------|
| `traces.jsonl` | Complete audit traces (one per line) |
| `summary.json` | Run summary statistics |
| `state_history.csv` | State changes over time |

---

## Key Metrics

### Adaptation Metrics

| Metric | Description |
|--------|-------------|
| **Adaptation Rate** | % of years with protective action |
| **Insurance Coverage** | % of years with active insurance |
| **Elevation Rate** | % of agents that elevated |

### Cognitive Metrics

| Metric | Description |
|--------|-------------|
| **TP Distribution** | Distribution of threat appraisal labels |
| **CP Distribution** | Distribution of coping appraisal labels |
| **Consistency Score** | TP/CP alignment with chosen action |

---

## Integration with SDK

### Using SDK Components

```python
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader

# Create policy engine
engine = PolicyEngine()

# Load rules from YAML
policy = PolicyLoader.from_yaml("governance_rules.yaml")

# Verify decision
trace = engine.verify(
    action={"skill": "buy_insurance"},
    state=agent.state,
    policy=policy
)

if not trace.valid:
    print(f"BLOCKED: {trace.rule_message}")
    print(f"Suggestion: {trace.state_delta}")  # XAI counterfactual
```

---

## Related Documentation

- [SDK README](../../governed_ai_sdk/README.md) - SDK architecture
- [Integration Tests](../../tests/integration/README.md) - Test coverage
- [MA Case Design](../multi_agent/CASE_DESIGN.md) - Multi-agent variant
