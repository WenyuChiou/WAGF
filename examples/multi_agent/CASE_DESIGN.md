# Multi-Agent Flood Adaptation Case Design

> **Domain**: Flood Risk Management
> **Agent Types**: Household, Government, Insurance
> **Framework**: Protection Motivation Theory (PMT) + Social Influence

---

## Overview

The Multi-Agent (MA) flood adaptation case extends the single-agent scenario with:

1. **Multiple households** making independent decisions
2. **Institutional agents** (government, insurance) setting policies
3. **Social network** enabling information flow between neighbors
4. **Symbolic memory** with novelty-first surprise detection

```
┌─────────────────────────────────────────────────────────────────┐
│                    MA Architecture Overview                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                  Tiered Environment                      │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │   │
│   │  │  Global  │  │  Local   │  │      Social          │   │   │
│   │  │  State   │  │  States  │  │      Network         │   │   │
│   │  └──────────┘  └──────────┘  └──────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│           ┌──────────────────┼──────────────────┐               │
│           ↓                  ↓                  ↓               │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│   │  Government  │   │  Insurance   │   │  Households  │       │
│   │   (Tier 1)   │   │   (Tier 1)   │   │   (Tier 2)   │       │
│   └──────────────┘   └──────────────┘   └──────────────┘       │
│           │                  │                  │               │
│           └──────────────────┼──────────────────┘               │
│                              ↓                                   │
│                    ┌──────────────────┐                         │
│                    │   Audit Traces   │                         │
│                    └──────────────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Types

### Tier 1: Institutional Agents

#### Government Agent

| Attribute | Description |
|-----------|-------------|
| **Role** | Sets subsidy rates for flood protection |
| **Decisions** | Increase/decrease/maintain subsidy |
| **Inputs** | Aggregate flood damage, budget constraints |

**Example Decision**:
```json
{
  "decision": "increase_subsidy",
  "reasoning": "High aggregate damage last year warrants increased support"
}
```

#### Insurance Agent

| Attribute | Description |
|-----------|-------------|
| **Role** | Sets premium rates based on risk pool |
| **Decisions** | Adjust premium rates |
| **Inputs** | Claims history, risk exposure |

**Example Decision**:
```json
{
  "decision": "maintain_premium",
  "reasoning": "Current premium adequately covers projected claims"
}
```

### Tier 2: Household Agents

Same as SA case, but with additional social context:

| Attribute | Description |
|-----------|-------------|
| **Role** | Individual protective decisions |
| **Decisions** | buy_insurance, elevate_house, apply_for_grant, do_nothing |
| **Inputs** | Personal state + social context + institutional policies |

---

## Tier Ordering

Institutional agents act **before** household agents each year:

```
Year N:
  1. Government decides subsidy rate
  2. Insurance decides premium rate
  3. Households see new rates
  4. Households make decisions
  5. Flood event occurs (or not)
  6. Damage calculated
  7. Memories updated
```

This ensures households have access to current policy information when deciding.

---

## Social Network

### Graph Types

| Type | Description | Use Case |
|------|-------------|----------|
| **Spatial** | Connections based on geographic proximity | Realistic neighborhoods |
| **Ring** | Each node connected to k nearest neighbors | Controlled experiments |
| **Random** | Erdos-Renyi random graph | Baseline comparison |

### Spatial Graph

```python
from examples.multi_agent.environment.social_network import create_spatial_graph

# Create graph where agents within 3.0 units are neighbors
graph = create_spatial_graph(
    agents=households,
    positions=agent_positions,
    radius=3.0
)
```

### Ring Graph

```python
from examples.multi_agent.environment.social_network import create_ring_graph

# Create ring where each agent has 4 neighbors
graph = create_ring_graph(agents=households, k=4)
```

---

## Social Context

### Gossip Propagation

Neighbors share information about their flood experiences:

```python
def get_gossip(agent_id: str, graph: Graph) -> list[str]:
    """Get gossip from neighbors."""
    neighbors = graph.neighbors(agent_id)
    gossip = []
    for n in neighbors:
        if n.state.get("flood_damage", 0) > 0:
            gossip.append(f"Neighbor {n.id} suffered ${n.state['flood_damage']} damage")
        if n.state.get("has_insurance"):
            gossip.append(f"Neighbor {n.id} has flood insurance")
    return gossip
```

### Visible Neighbor Actions

Households can observe their neighbors' protective actions:

```python
def get_visible_actions(agent_id: str, graph: Graph) -> dict:
    """Get observable neighbor actions."""
    neighbors = graph.neighbors(agent_id)
    return {
        "elevated_pct": sum(1 for n in neighbors if n.state["elevated"]) / len(neighbors),
        "insured_pct": sum(1 for n in neighbors if n.state["has_insurance"]) / len(neighbors)
    }
```

### Social Context in Prompt

```
=== SOCIAL CONTEXT ===
Your neighbors' situations:
- 3 of 5 neighbors have flood insurance (60%)
- 1 of 5 neighbors has elevated their house (20%)
- Neighbor H3 suffered $25,000 flood damage last year
- Neighbor H5 says: "I wish I had bought insurance earlier"
```

---

## Memory V4 (SymbolicMemory)

### Overview

The MA case uses the SDK's `SymbolicMemory` for efficient state tracking:

```python
from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory

# Initialize memory with flood sensors
memory = SymbolicMemory(
    sensors=[
        {
            "path": "flood_depth_m",
            "name": "FLOOD",
            "bins": [
                {"label": "SAFE", "max": 0.3},
                {"label": "MINOR", "max": 1.0},
                {"label": "MODERATE", "max": 2.0},
                {"label": "SEVERE", "max": 99.0}
            ]
        },
        {
            "path": "panic_level",
            "name": "PANIC",
            "bins": [
                {"label": "CALM", "max": 0.3},
                {"label": "CONCERNED", "max": 0.6},
                {"label": "PANICKED", "max": 1.0}
            ]
        }
    ],
    arousal_threshold=0.5
)
```

### Sensor Quantization

Continuous values are mapped to discrete labels:

| Sensor | Value | Quantized Label |
|--------|-------|-----------------|
| flood_depth_m | 0.2 | FLOOD:SAFE |
| flood_depth_m | 0.8 | FLOOD:MINOR |
| flood_depth_m | 1.5 | FLOOD:MODERATE |
| flood_depth_m | 3.0 | FLOOD:SEVERE |

### Novelty-First Surprise

First observation of a state signature = 100% surprise:

```python
# First observation of this state
sig1, surprise1 = memory.observe({"flood_depth_m": 2.0, "panic_level": 0.7})
print(surprise1)  # 1.0 (completely novel)

# Repeated observation
sig2, surprise2 = memory.observe({"flood_depth_m": 2.0, "panic_level": 0.7})
print(surprise2)  # < 1.0 (familiar)
```

### System 1/2 Switching

Surprise level determines cognitive processing:

| Surprise | System | Processing |
|----------|--------|------------|
| < 0.5 | System 1 | Fast, heuristic-based |
| >= 0.5 | System 2 | Slow, deliberative |

```python
system = memory.determine_system(surprise)
if system == "SYSTEM_2":
    # More deliberative processing
    prompt += "\nThis is an unusual situation. Think carefully."
```

---

## Environment

### Tiered Environment Structure

```python
class TieredEnvironment:
    def __init__(self):
        self.global_state = {
            "year": 0,
            "flood_probability": 0.3,
            "subsidy_rate": 0.2,
            "premium_rate": 500
        }
        self.local_states = {}  # agent_id -> local state
        self.institutions = {}  # institution_id -> decision

    def update_global(self, key: str, value: any):
        """Update global state visible to all agents."""
        self.global_state[key] = value

    def update_local(self, agent_id: str, key: str, value: any):
        """Update local state for specific agent."""
        self.local_states.setdefault(agent_id, {})[key] = value
```

### State Layers

| Layer | Visibility | Examples |
|-------|------------|----------|
| **Global** | All agents | flood_probability, subsidy_rate, premium_rate |
| **Local** | Single agent | savings, flood_damage, personal_risk |
| **Social** | Neighbors | gossip, visible_actions |
| **Institutional** | From Tier 1 | government decisions, insurance rates |

---

## Policy Propagation

### Government → Households

When government changes subsidy rate:

```python
# Government decision
govt_decision = {"action": "increase_subsidy", "new_rate": 0.3}

# Propagate to environment
env.update_global("subsidy_rate", govt_decision["new_rate"])

# Households see new rate in their context
context = {
    "global": env.global_state,  # includes new subsidy_rate
    "local": env.local_states[agent_id],
    "social": get_social_context(agent_id)
}
```

### Insurance → Households

Similarly for premium changes:

```python
# Insurance decision
ins_decision = {"action": "increase_premium", "new_rate": 600}

# Propagate
env.update_global("premium_rate", ins_decision["new_rate"])
```

---

## Household Memory Integration

### HouseholdAgent._init_memory_v4()

```python
class HouseholdAgent:
    def _init_memory_v4(self, config: dict):
        """Initialize V4 symbolic memory from SDK."""
        if config.get("engine") == "symbolic":
            from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory
            return SymbolicMemory(
                config["sensors"],
                arousal_threshold=config.get("arousal_threshold", 0.5)
            )
        return None
```

### Memory Configuration

```yaml
# memory_config.yaml
engine: symbolic
sensors:
  - path: flood_depth_m
    name: FLOOD
    bins:
      - label: SAFE
        max: 0.3
      - label: MINOR
        max: 1.0
      - label: MODERATE
        max: 2.0
      - label: SEVERE
        max: 99.0
  - path: damage_ratio
    name: DAMAGE
    bins:
      - label: NONE
        max: 0.0
      - label: LIGHT
        max: 0.1
      - label: HEAVY
        max: 1.0
arousal_threshold: 0.5
```

---

## Running the Experiment

### Basic Run

```bash
python examples/multi_agent/run_ma_flood.py \
  --model llama3.2:3b \
  --households 10 \
  --years 10 \
  --output results/ma_run_001
```

### Configuration

```yaml
# config.yaml
experiment:
  years: 10
  flood_probability: 0.3

agents:
  households:
    count: 10
    initial_state:
      elevated: false
      has_insurance: false
      savings: 50000
  government:
    count: 1
  insurance:
    count: 1

social:
  graph_type: ring
  k: 4

memory:
  engine: symbolic
  arousal_threshold: 0.5
```

---

## Audit Trace (MA-Specific Fields)

```json
{
  "run_id": "ma_run_20260127_001",
  "step_id": 1,
  "year": 1,
  "agent_id": "household_003",
  "agent_type": "household",
  "tier": 2,

  "context": {
    "global": {
      "subsidy_rate": 0.2,
      "premium_rate": 500
    },
    "local": {
      "savings": 45000
    },
    "social": {
      "elevated_pct": 0.25,
      "insured_pct": 0.5,
      "gossip": ["Neighbor H5 suffered damage"]
    }
  },

  "memory_trace": {
    "signature": "a3f2b8c1d4e5f6g7",
    "surprise": 0.85,
    "system": "SYSTEM_2",
    "quantized_sensors": ["FLOOD:MODERATE", "PANIC:CONCERNED"]
  },

  "skill_proposal": {
    "skill_name": "buy_insurance",
    "reasoning": {
      "threat_appraisal": {"label": "VH"},
      "coping_appraisal": {"label": "M"}
    }
  },

  "validation_result": {"outcome": "APPROVED"},
  "approved_skill": {"skill_name": "buy_insurance"}
}
```

---

## Key Metrics

### Aggregate Metrics

| Metric | Description |
|--------|-------------|
| **Coverage Rate** | % of households with insurance |
| **Elevation Rate** | % of households elevated |
| **Total Damage** | Aggregate flood damage |
| **Policy Effectiveness** | Damage reduction per subsidy dollar |

### Social Metrics

| Metric | Description |
|--------|-------------|
| **Diffusion Rate** | Speed of protective action adoption |
| **Clustering** | Whether similar agents cluster |
| **Influence Score** | Impact of neighbor actions |

### Memory Metrics

| Metric | Description |
|--------|-------------|
| **Unique Signatures** | Number of distinct states observed |
| **System 2 Rate** | % of decisions in deliberative mode |
| **Surprise Distribution** | Distribution of surprise values |

---

## Comparison: SA vs MA

| Aspect | SA | MA |
|--------|----|----|
| **Agents** | 1 household | N households + institutions |
| **Context** | Personal only | Personal + social + institutional |
| **Memory** | Experience list | SymbolicMemory (SDK) |
| **Policy** | Fixed | Dynamic (govt/insurance decisions) |
| **Social** | None | Gossip + visible actions |
| **Complexity** | Simple | Complex interactions |

---

## SDK Integration

### Memory V4 from SDK

```python
from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory
from governed_ai_sdk.v1_prototype.memory.symbolic_core import Sensor

# Direct SDK usage
memory = SymbolicMemory(sensors, arousal_threshold=0.5)
sig, surprise = memory.observe(world_state)
system = memory.determine_system(surprise)
```

### Agent Protocol

```python
from governed_ai_sdk.agents import AgentProtocol

class HouseholdAgent:
    @property
    def agent_id(self) -> str:
        return self._id

    @property
    def agent_type(self) -> str:
        return "household"

    def get_state(self) -> dict:
        return self._state

# Verify protocol compliance
assert isinstance(agent, AgentProtocol)
```

---

## Related Documentation

- [SDK README](../../governed_ai_sdk/README.md) - SDK architecture
- [Integration Tests](../../tests/integration/README.md) - Test coverage
- [SA Case Design](../single_agent/CASE_DESIGN.md) - Single-agent variant
