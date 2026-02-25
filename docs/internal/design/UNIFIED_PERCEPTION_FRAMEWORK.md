# Unified Perception Framework

> **Design Goal**: Domain-agnostic agent perception for any real-world scenario
> **Not tied to**: PMT, FLOODABM, or any specific behavioral theory

---

## Design Principles

1. **Domain-Agnostic**: Works for flood, finance, health, education, urban planning, etc.
2. **Theory-Neutral**: No hardcoded constructs (TP, CP, SP are LLM's job to evaluate)
3. **Passive Observation**: Agents observe but don't actively communicate
4. **Point Events**: Events are instantaneous, not intervals
5. **Minimal Assumptions**: Only model what's universal across domains

---

## Core Taxonomy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     UNIFIED PERCEPTION TAXONOMY                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 1. AGENT STATE (Internal, Private)                                  │    │
│  │                                                                     │    │
│  │    What: Agent's own attributes and status                         │    │
│  │    Visibility: Private to agent                                    │    │
│  │    Mutability: Agent self-modify via actions                       │    │
│  │                                                                     │    │
│  │    Generic Examples:                                                │    │
│  │    • Identity: id, type, group                                     │    │
│  │    • Resources: budget, assets, inventory                          │    │
│  │    • Status flags: any boolean states                              │    │
│  │    • Numeric attributes: any measurable properties                 │    │
│  │                                                                     │    │
│  │    Domain-Specific (configured, not hardcoded):                    │    │
│  │    • Flood: elevated, has_insurance, property_value                │    │
│  │    • Finance: portfolio_value, debt, credit_score                  │    │
│  │    • Health: has_vaccination, chronic_condition                    │    │
│  │    • Education: enrolled, grade_level, test_scores                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 2. ENVIRONMENT STATE (External, Observable)                        │    │
│  │                                                                     │    │
│  │    2a. GLOBAL (All agents observe same values)                     │    │
│  │        • Simulation time: year, step                               │    │
│  │        • System-wide conditions: any shared state                  │    │
│  │                                                                     │    │
│  │    2b. SPATIAL (Location-dependent)                                │    │
│  │        • Region-specific conditions                                │    │
│  │        • Agents only see their region's state                      │    │
│  │                                                                     │    │
│  │    2c. INSTITUTIONAL (Policy/rule state)                           │    │
│  │        • Rates, limits, thresholds                                 │    │
│  │        • Published policies                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 3. EVENTS (Discrete, Point-in-Time)                                │    │
│  │                                                                     │    │
│  │    Properties:                                                      │    │
│  │    • event_type: string identifier                                 │    │
│  │    • severity: INFO | MINOR | MODERATE | SEVERE | CRITICAL         │    │
│  │    • scope: GLOBAL | REGIONAL | LOCAL | AGENT                      │    │
│  │    • data: arbitrary payload dict                                  │    │
│  │                                                                     │    │
│  │    Timing: Instantaneous (point, not interval)                     │    │
│  │                                                                     │    │
│  │    Examples by domain:                                              │    │
│  │    • Flood: "flood" event with depth_m                             │    │
│  │    • Finance: "market_crash" with loss_percent                     │    │
│  │    • Health: "outbreak" with infection_rate                        │    │
│  │    • Policy: "subsidy_change" with new_rate                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 4. SOCIAL OBSERVATION (Passive Only)                               │    │
│  │                                                                     │    │
│  │    Mode: Passive observation (NO active communication)             │    │
│  │                                                                     │    │
│  │    4a. VISIBLE ATTRIBUTES                                          │    │
│  │        What: Neighbors' externally observable states               │    │
│  │        Configured per domain (what's "visible")                    │    │
│  │        Example: elevated house (visible), has_insurance (maybe)    │    │
│  │                                                                     │    │
│  │    4b. VISIBLE ACTIONS                                             │    │
│  │        What: Recent behavioral changes in neighbors                │    │
│  │        Example: "Neighbor X elevated their house"                  │    │
│  │                                                                     │    │
│  │    4c. AGGREGATED METRICS                                          │    │
│  │        What: Computed statistics about community/neighbors         │    │
│  │        Example: "45% of neighbors have insurance"                  │    │
│  │        Scopes: COMMUNITY, NEIGHBORS, TYPE, SPATIAL                 │    │
│  │                                                                     │    │
│  │    NO gossip/rumors in core framework (domain can add if needed)   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 5. MEMORY (Historical, Per-Agent)                                  │    │
│  │                                                                     │    │
│  │    What: Agent's accumulated experiences                           │    │
│  │    Content: Text snippets of past events/decisions                 │    │
│  │    Retrieval: Configurable (window, importance, etc.)              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Observation Accuracy: Removed from Core

**Decision**: Observation accuracy is **domain-specific** and should NOT be in core.

Rationale:
- Not all domains need noisy observation
- Adds complexity without universal benefit
- Domains that need it can implement via custom Observer

If a domain needs observation noise:
```python
# Domain-specific observer can add noise
class NoisyFloodObserver(SocialObserver):
    def get_observable_attributes(self, agent):
        attrs = super().get_observable_attributes(agent)
        # Add noise if needed
        attrs["elevation_height"] = attrs["elevation_height"] * (1 + random.gauss(0, 0.1))
        return attrs
```

---

## LLM Self-Evaluation (Not System-Calculated)

The framework **provides raw data**, LLM **derives meaning**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEPARATION OF CONCERNS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FRAMEWORK PROVIDES (Raw Perception):                                        │
│  ─────────────────────────────────────                                       │
│  • "A flood occurred with depth 0.6m"                    ← Event            │
│  • "Your property value is $300,000"                     ← Agent State      │
│  • "45% of neighbors have insurance"                     ← Observable       │
│  • "Neighbor X elevated their house last year"           ← Visible Action   │
│  • "You flooded 3 times in the past 10 years"            ← Memory           │
│                                                                              │
│  LLM DERIVES (Cognitive Appraisal):                                          │
│  ──────────────────────────────────                                          │
│  • "I perceive HIGH threat from flooding"                ← Self-evaluated   │
│  • "I feel CAPABLE of taking protective action"          ← Self-evaluated   │
│  • "I TRUST the government subsidy program"              ← Self-evaluated   │
│  • Decision: "I will buy flood insurance"                ← LLM output       │
│                                                                              │
│  FRAMEWORK DOES NOT:                                                         │
│  ─────────────────────                                                       │
│  • Calculate TP, CP, SP, or any psychological constructs                    │
│  • Enforce any behavioral theory (PMT, TPB, HBM, etc.)                      │
│  • Interpret what observations "mean" to the agent                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Unified Context Structure

```python
@dataclass
class UniversalContext:
    """Domain-agnostic context structure.

    All fields are optional - domains use what they need.
    """

    # 1. Agent's own state (private)
    state: Dict[str, Any] = field(default_factory=dict)

    # 2. Environment state (observable)
    environment: EnvironmentContext = None

    # 3. Events (discrete, point-in-time)
    events: List[Dict[str, Any]] = field(default_factory=list)

    # 4. Social observation (passive)
    social: SocialContext = None

    # 5. Observable metrics (aggregated)
    observables: Dict[str, float] = field(default_factory=dict)

    # 6. Memory (historical)
    memory: List[str] = field(default_factory=list)


@dataclass
class EnvironmentContext:
    """Tiered environment state."""
    global_state: Dict[str, Any] = field(default_factory=dict)   # All see same
    spatial_state: Dict[str, Any] = field(default_factory=dict)  # Location-specific
    institutional: Dict[str, Any] = field(default_factory=dict)  # Policy/rules


@dataclass
class SocialContext:
    """Passive social observation (no active communication)."""
    visible_attributes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # neighbor_id → {attr: value}

    visible_actions: List[Dict[str, Any]] = field(default_factory=list)
    # [{neighbor_id, action, description, timestamp}]

    neighbor_count: int = 0
```

---

## Event Framework (Point Events)

Events are **instantaneous points**, not intervals.

```python
@dataclass
class EnvironmentEvent:
    """A discrete, point-in-time event."""

    event_type: str                    # Identifier (e.g., "flood", "market_crash")
    severity: EventSeverity            # Impact level
    scope: EventScope                  # Who's affected
    description: str                   # Human-readable
    data: Dict[str, Any]               # Arbitrary payload

    # Scope targeting
    location: Optional[str] = None     # For REGIONAL/LOCAL
    affected_agents: List[str] = None  # For AGENT scope

    # Metadata
    domain: str = "generic"
    timestamp: Optional[datetime] = None  # Point in time (not duration)
```

For scenarios needing duration:
```python
# Application layer handles duration, not core framework
# e.g., "flood_start" and "flood_end" as separate events
# or track state changes: env.global_state["flood_active"] = True/False
```

---

## Domain Configuration Pattern

Domains configure what's observable without modifying core:

```python
# Domain configuration (YAML or Python)
domain_config = {
    "domain": "flood_adaptation",

    # What agent attributes are externally visible
    "visible_attributes": [
        "elevated",           # Physical: can see construction
        "relocated",          # Physical: can see empty house
        # "has_insurance",    # NOT visible by default
    ],

    # What actions generate visible events
    "visible_actions": [
        "elevate_house",      # Construction visible
        "relocate",           # Moving visible
        "buy_insurance",      # May be visible (sign/sticker)
    ],

    # Observable metrics to compute
    "observables": [
        {
            "name": "adaptation_rate",
            "condition": "elevated OR has_insurance",
            "scope": "COMMUNITY",
        },
        {
            "name": "neighbor_elevation_rate",
            "condition": "elevated",
            "scope": "NEIGHBORS",
        },
    ],

    # Event generators
    "event_generators": [
        {"domain": "flood", "class": "FloodEventGenerator"},
        {"domain": "policy", "class": "PolicyEventGenerator"},
    ],
}
```

---

## Flow Diagram (Simplified)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PERCEPTION PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

PRE_YEAR:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Event       │────▶│ Event       │────▶│ Environment │
│ Generators  │     │ Manager     │     │ State Sync  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Observable  │
                    │ Manager     │
                    └─────────────┘

PER_AGENT (Context Building):
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Agent State │────▶│             │     │             │
├─────────────┤     │             │     │             │
│ Events      │────▶│  Context    │────▶│    LLM      │
├─────────────┤     │  Builder    │     │  (decides)  │
│ Observables │────▶│             │     │             │
├─────────────┤     │             │     │             │
│ Social Obs  │────▶│             │     │             │
├─────────────┤     └─────────────┘     └─────────────┘
│ Memory      │────▶       │
└─────────────┘            ▼
                    UniversalContext
                    (raw data only,
                     no interpretation)

POST_STEP:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ LLM         │────▶│ Skill       │────▶│ State       │
│ Decision    │     │ Executor    │     │ Update      │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                        Social state
                                        visible to
                                        neighbors
```

---

## Summary: What's In vs Out of Core

| In Core (Generic) | Out of Core (Domain-Specific) |
|-------------------|-------------------------------|
| State container structures | Specific state attributes |
| Event protocol & manager | Specific event generators |
| Observable computation engine | Specific metric definitions |
| Social observation framework | What's "visible" per domain |
| Context builder pipeline | Domain prompt templates |
| Memory retrieval interface | Memory ranking strategies |

| In Core (Generic) | NOT in Core |
|-------------------|-------------|
| Raw perception data | Psychological constructs (TP, CP, SP) |
| Factual observations | Interpretation of observations |
| Event delivery | Behavioral theory enforcement |
| Aggregated metrics | "Meaning" of metrics |

---

## File Structure

```
broker/
├── interfaces/
│   ├── context_types.py       # UniversalContext, SocialContext
│   ├── event_generator.py     # EventGeneratorProtocol, EnvironmentEvent
│   └── observable_state.py    # ObservableMetric, ObservableSnapshot
│
├── components/
│   ├── event_manager.py       # EnvironmentEventManager
│   ├── observable_state.py    # ObservableStateManager
│   ├── context_providers.py   # All providers
│   └── event_generators/
│       ├── __init__.py
│       ├── flood.py           # Domain: flood
│       ├── hazard.py          # Domain: hazard (PRB grid)
│       ├── impact.py          # Domain: financial impact
│       └── policy.py          # Domain: policy changes
│
└── core/
    └── unified_context_builder.py  # Assembles UniversalContext
```

---

## Next Steps

1. **Refactor**: Move any hardcoded PMT references out of core
2. **Validate**: Ensure flood domain works with this generic structure
3. **Test**: Create a second domain (e.g., simple finance) to verify generality
4. **Document**: Create domain onboarding guide

---

*This design prioritizes simplicity and domain-agnosticism over feature completeness.*
