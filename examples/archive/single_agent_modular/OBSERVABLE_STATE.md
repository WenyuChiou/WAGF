# Observable State Module

## Overview

The Observable State Module enables cross-agent observation: agents can see metrics
computed from other agents' states (e.g., "45% of neighbors have insurance").

This is a general-purpose mechanism that allows agent behavior to affect what
other agents observe, enabling emergent social dynamics in multi-agent simulations.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ pre_year Hook                                            │
│  obs_manager.compute(agents, year)                       │
│    → Computes all registered metrics                     │
│    → Stores in ObservableSnapshot                        │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ Context Building (per agent)                             │
│  ObservableStateProvider.provide()                       │
│    → Injects observables dict into context               │
│    → Community metrics: same for all agents              │
│    → Neighborhood metrics: agent-specific                │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ LLM Prompt                                               │
│  "Community insurance rate: 45%"                         │
│  "Your neighbors' elevation rate: 60%"                   │
└──────────────────────────────────────────────────────────┘
```

## Scopes

| Scope | Description | Context Prefix | Example |
|-------|-------------|----------------|---------|
| COMMUNITY | All agents | (none) | `insurance_penetration_rate` |
| NEIGHBORS | Agent's neighbors | `my_` | `my_neighbor_insurance_rate` |
| TYPE | Per agent type | `type_` | `type_adaptation_rate` |
| SPATIAL | Per region/tract | `region_` | `region_damage_rate` |

## Pre-built Flood Metrics

The module includes pre-built metrics for flood adaptation experiments:

| Metric | Scope | Description |
|--------|-------|-------------|
| `insurance_penetration_rate` | COMMUNITY | % of active agents with insurance |
| `elevation_penetration_rate` | COMMUNITY | % of active agents with elevation |
| `adaptation_rate` | COMMUNITY | % of active agents with any protection |
| `relocation_rate` | COMMUNITY | % of all agents relocated |
| `neighbor_insurance_rate` | NEIGHBORS | % of neighbors with insurance |
| `neighbor_elevation_rate` | NEIGHBORS | % of neighbors with elevation |

## Usage in single_agent_modular

The module is already integrated. Agents receive observable metrics in their
context during decision-making.

### Accessing Observables in Agent Context

```python
# In context during agent decision:
context = {
    "observables": {
        "insurance_penetration_rate": 0.45,      # 45% community rate
        "elevation_penetration_rate": 0.30,      # 30% community rate
        "adaptation_rate": 0.55,                 # 55% with any protection
        "relocation_rate": 0.05,                 # 5% relocated
        "my_neighbor_insurance_rate": 0.60,      # 60% of MY neighbors
        "my_neighbor_elevation_rate": 0.40,      # 40% of MY neighbors
    },
    # ... other context fields
}
```

## Creating Custom Metrics

### Simple Rate Metric

```python
from broker.components.observable_state import (
    ObservableStateManager,
    create_rate_metric,
    ObservableScope,
)

manager = ObservableStateManager()

# Simple rate metric
manager.register(create_rate_metric(
    name="has_solar_panels",
    condition=lambda a: getattr(a, 'solar_installed', False),
    description="% of homes with solar",
))
```

### Rate Metric with Filter

```python
# Rate metric with filter (exclude certain agents)
manager.register(create_rate_metric(
    name="owner_insurance_rate",
    condition=lambda a: getattr(a, 'has_insurance', False),
    filter_fn=lambda a: getattr(a, 'tenure', '') == 'Owner',
    description="% of owners with insurance",
))
```

### Neighborhood Metric

```python
# Neighborhood-scope metric (per-agent)
manager.register(create_rate_metric(
    name="neighbor_solar_rate",
    condition=lambda a: getattr(a, 'solar_installed', False),
    scope=ObservableScope.NEIGHBORS,
    description="% of neighbors with solar",
))

# Don't forget to set the neighbor graph!
manager.set_neighbor_graph(graph)
```

### Custom Compute Function

```python
from broker.interfaces.observable_state import ObservableMetric

# Custom metric with arbitrary compute function
def compute_avg_income(agents):
    incomes = [getattr(a, 'income', 0) for a in agents.values()]
    return sum(incomes) / len(incomes) if incomes else 0.0

manager.register(ObservableMetric(
    name="avg_community_income",
    compute_fn=compute_avg_income,
    scope=ObservableScope.COMMUNITY,
    description="Average income in community",
))
```

## Integration Checklist

When integrating into a new experiment:

- [ ] Create `ObservableStateManager`
- [ ] Register metrics (use factories or custom)
- [ ] Set neighbor graph (if using NEIGHBORS scope)
- [ ] Add `ObservableStateProvider` to context builder
- [ ] Call `compute()` in `pre_year` hook

### Example Integration

```python
from broker.components.observable_state import (
    ObservableStateManager,
    create_flood_observables,  # or create your own
)
from broker.components.context_providers import ObservableStateProvider

# In main():

# 1. Create manager and register metrics
obs_manager = ObservableStateManager()
obs_manager.register_many(create_flood_observables())

# 2. Set neighbor graph (for NEIGHBORS scope)
obs_manager.set_neighbor_graph(graph)

# 3. Add provider to context builder
ctx_builder.providers.append(ObservableStateProvider(obs_manager))

# 4. Pass to hooks for yearly computation
hooks = FloodHooks(..., obs_manager=obs_manager)

# In hooks.pre_year():
def pre_year(self, year, env, agents):
    if self.obs_manager:
        self.obs_manager.compute(agents, year)
    # ... rest of pre_year logic
```

## Design Principles

1. **Domain-agnostic**: Core module knows nothing about flood/insurance/etc
2. **Pluggable metrics**: Register any compute function
3. **Multi-scope**: community, neighbors, type-based, spatial
4. **Update modes**: per_year, per_step, on_demand (default: per_year)

## Performance Considerations

- Metrics are computed once per year (or per step if configured)
- Neighborhood metrics scale with O(agents × neighbors)
- Cached in ObservableSnapshot until next compute()
- Context provider reads from cache (no recomputation)

## Extending for New Domains

Create a factory function for your domain:

```python
def create_my_domain_observables() -> List[ObservableMetric]:
    """Factory for my domain's observable metrics."""
    return [
        create_rate_metric(
            "my_metric_1",
            condition=lambda a: getattr(a, 'my_attr', False),
            description="Description of metric 1",
        ),
        # ... more metrics
    ]
```

Then use it like `create_flood_observables()`.
