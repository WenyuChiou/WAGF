# MAS Five-Layer Architecture: Framework Mapping

> **Version**: v0.54.0
> **Last Updated**: 2026-01-29
> **Task Reference**: Task-052 (analysis), Task-054 (Communication Layer implementation)

This document maps the Water Agent Governance Framework to the standard MAS (Multi-Agent Systems) five-layer architecture based on contemporary literature (Generative Agents, Concordia, AgentTorch, MetaGPT).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MAS FIVE-LAYER ARCHITECTURE                              │
│                                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐ │
│  │    STATE     │────▶│ OBSERVATION  │────▶│   ACTION     │────▶│ TRANSITION │ │
│  │   (World)    │     │  (Perceive)  │     │  (Decide)    │     │  (Execute) │ │
│  └──────────────┘     └──────────────┘     └──────────────┘     └────────────┘ │
│         ▲                                                              │        │
│         │                    ┌──────────────┐                          │        │
│         │                    │COMMUNICATION │                          │        │
│         │                    │  (Interact)  │                          │        │
│         │                    └──────┬───────┘                          │        │
│         │                           │                                  │        │
│         └───────────────────────────┴──────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: State Layer

**Purpose**: Define "what the world is" - all entities, objects, and environment variables.

### Theoretical Foundation

| Concept | Description | Literature |
|---------|-------------|------------|
| **S_Ag (Agents)** | Agent internal states | AgentTorch (2024) |
| **S_Ob (Objects)** | Interactable objects | AgentTorch (2024) |
| **S_Env (Environment)** | Global environment state | AgentTorch (2024) |
| **Grounded Variables** | Code-maintained (non-LLM) variables | Concordia (2023) |

### Framework Implementation

#### S_Ag: Agent States

| Agent Type | State Class | Key Attributes | File |
|------------|-------------|----------------|------|
| **Household** | `HouseholdAgentState` | elevated, relocated, trust_*, TP_LABEL, CP_LABEL | `ma_agents/household.py` |
| **Government** | `GovernmentAgentState` | budget, policy_enacted, subsidy_rate | `ma_agents/government.py` |
| **Insurance** | `InsuranceAgentState` | premium_pool, claim_ratio, risk_model | `ma_agents/insurance.py` |

#### S_Ob: Objects

| Object | Class | Purpose | File |
|--------|-------|---------|------|
| **Threat Perception** | `TPState` | Track TP values per agent | `environment/tp_state.py` |
| **Social Network** | `SocialGraph` | Agent relationships | `broker/components/social_graph.py` |
| **Position Assignment** | `PositionAssignment` | Spatial locations | `environment/settlement.py` |

#### S_Env: Environment

| Entity | Class | Purpose | File |
|--------|-------|---------|------|
| **Flood Events** | `FloodEvent` | Hazard specifications | `environment/hazard.py` |
| **Damage Results** | `DamageResult` | Post-flood damage | `environment/core.py` |
| **Settlement Reports** | `SettlementReport` | Insurance settlements | `environment/settlement.py` |

#### Grounded Variables

Variables maintained by code (not LLM-generated):

| Variable | Type | Update Mechanism | Rationale |
|----------|------|------------------|-----------|
| `elevated` | bool | SimulationEngine | Physical state, deterministic |
| `relocated` | bool | SimulationEngine | Physical state, deterministic |
| `damage_amount` | float | DamageCalculator | Mathematical formula |
| `tp_new` | float | TPDecayEngine | Decay equation |
| `budget` | float | Policy logic | Accounting rules |
| `premium` | float | RiskModel | Actuarial calculation |

### Literature References

- **AgentTorch** (Chopra & Raskar, 2024): Entity separation framework. Zotero Key: `RMNEUT7F`
- **PMT** (Rogers, 1975): Protection motivation for household behavior. Zotero Key: `NV3BZ94J`
- **Bubeck et al.** (2012): Flood risk perception dynamics. Zotero Key: `ZADR7ZXE`

---

## Layer 2: Observation Layer

**Purpose**: Define "what agents perceive" - transform world state to agent observations.

### Theoretical Foundation

| Concept | Description | Literature |
|---------|-------------|------------|
| **O(S)** | Observation function | POMDP (Kaelbling et al., 1998) |
| **Partial Observability** | Agents see subset of state | POMDP |
| **Bounded Rationality** | Cognitive limitations | Simon (1955) |
| **Perception Filtering** | Type-specific transformation | Generative Agents (2023) |

### Framework Implementation

#### Observation Function: ContextBuilder

The 12-step Context Provider Pipeline transforms state → prompt:

```python
# broker/components/context_builder.py
PROVIDER_ORDER = [
    "agent_profile",       # 1. Who am I
    "initial_memory",      # 2. Seeded memories
    "memory",              # 3. Retrieved memories
    "environment_event",   # 4. Current events
    "observable_state",    # 5. Visible state
    "social",              # 6. Neighbor info
    "agent_type_context",  # 7. Type-specific rules
    "skill_eligibility",   # 8. Available actions
    "governance_rules",    # 9. Decision constraints
    "response_format",     # 10. Output structure
    "cognitive_trace",     # 11. Reasoning template
    "perception_aware",    # 12. FINAL: Filter all
]
```

#### Partial Observability: ObservableScope

```python
# broker/interfaces/observable_state.py
class ObservableScope(Enum):
    COMMUNITY = "community"   # Global metrics
    NEIGHBORS = "neighbors"   # Direct connections
    TYPE = "type"             # Same agent type
    SPATIAL = "spatial"       # Nearby in space
```

#### Perception Filtering

| Filter | Input | Output | Example |
|--------|-------|--------|---------|
| `HouseholdPerceptionFilter` | `tp=0.85` | `"high threat"` | Qualitative |
| `GovernmentPerceptionFilter` | `tp=0.85` | `tp=0.85` | Quantitative |
| `InsurancePerceptionFilter` | `claims=[]` | Statistics | Aggregated |

```python
# broker/components/perception_filter.py
class HouseholdPerceptionFilter:
    def filter(self, context: Dict, agent: Agent) -> Dict:
        # Convert numeric TP to qualitative label
        tp_value = context.get("tp_new", 0.5)
        context["threat_level"] = self._to_qualitative(tp_value)
        return context
```

### Literature References

- **Simon** (1955): Bounded rationality foundation. Zotero Key: `6MSEC2KH`
- **Kaelbling et al.** (1998): POMDP formalization. Zotero Key: `QU47TXUP`
- **Park et al.** (2023): Environment tree observation. Zotero Key: `MATE4MG3`

---

## Layer 3: Action Layer

**Purpose**: Define "how agents decide" - memory, reflection, planning, and skill use.

### Theoretical Foundation

| Concept | Description | Literature |
|---------|-------------|------------|
| **Memory Stream** | Complete experience record | Generative Agents (2023) |
| **Reflection** | Higher-level insight synthesis | Generative Agents (2023) |
| **Planning** | Goal decomposition | Generative Agents (2023) |
| **Tool Use** | External capability invocation | Toolformer (2023) |
| **Working Memory** | Cognitive capacity limits | Miller (1956), Cowan (2001) |

### Framework Implementation

#### Memory Stream: CognitiveMemory

```python
# broker/components/memory.py
@dataclass
class CognitiveMemory:
    working: List[MemoryItem]    # Recent, high-access
    episodic: List[MemoryItem]   # Long-term storage

# cognitive_governance/memory/unified_engine.py
class UnifiedCognitiveEngine:
    """v5 Memory engine with System 1/2 retrieval."""

    def retrieve(
        self,
        agent_id: str,
        query: str,
        top_k: int = 5,
        arousal: float = 0.0,  # Controls System 1/2
    ) -> List[UnifiedMemoryItem]:
        # Recency × Importance × Context scoring
        pass
```

#### Reflection: ReflectionEngine

```python
# broker/components/reflection_engine.py
class ReflectionEngine:
    def should_reflect(self, agent_id: str, year: int) -> bool:
        """Trigger yearly reflection."""
        return year > 1 and year % self.reflection_interval == 0

    def generate_reflection_prompt(self, memories: List) -> str:
        """Create LLM prompt for insight synthesis."""
        pass

    def store_insight(self, agent_id: str, insight: str):
        """Store with high importance (0.9)."""
        pass
```

#### Planning: Gap Analysis

| Feature | Status | Implementation |
|---------|--------|----------------|
| Daily Plans | ⚠️ Implicit | No dedicated module |
| Plan Revision | ⚠️ Missing | No interrupt detection |
| Goal Hierarchy | ⚠️ Partial | Skills have preconditions |

**Recommendation**: Consider adding `DailyPlanGenerator` module.

#### Skill/Tool Use: SkillRegistry

```python
# broker/components/skill_registry.py
@dataclass
class SkillDefinition:
    name: str
    description: str
    preconditions: List[Precondition]
    effects: Dict[str, Any]
    agent_types: List[str]

# broker/core/skill_broker_engine.py
class SkillBrokerEngine:
    def propose_skill(self, context: Dict) -> SkillProposal:
        """LLM proposes skill based on context."""
        pass

    def validate_skill(self, proposal: SkillProposal) -> ValidationResult:
        """Run through governance validators."""
        pass

    def execute_skill(self, approved: ApprovedSkill) -> ExecutionResult:
        """Execute validated skill."""
        pass
```

#### Cognitive Constraints

```python
# cognitive_governance/memory/config/cognitive_constraints.py
@dataclass
class CognitiveConstraints:
    system1_memory_count: int = 5   # Cowan (2001): 4±1
    system2_memory_count: int = 7   # Miller (1956): 7±2
    working_capacity: int = 10
    top_k_significant: int = 2
```

### Literature References

- **Park et al.** (2023): Memory stream, reflection, planning. Zotero Key: `MATE4MG3`
- **Packer et al.** (2023): MemGPT hierarchical memory. Zotero Key: `4K3K9MQJ`
- **Schick et al.** (2023): Toolformer tool use. Zotero Key: `4CUZ2ZTH`
- **Miller** (1956): 7±2 working memory. Zotero Key: `XNCU5J2T`
- **Cowan** (2001): 4±1 focus attention. Zotero Key: `NXZ6CFRI`

---

## Layer 4: Transition Layer

**Purpose**: Define "what happens after actions" - execute actions and update state.

### Theoretical Foundation

| Concept | Description | Literature |
|---------|-------------|------------|
| **T(S, A)** | Transition function | MDP formalism |
| **Game Master** | Action resolution mediator | Concordia (2023) |
| **Event Generation** | Environment dynamics | ABM (Gilbert, 2019) |
| **Feedback Loop** | Action → State → Observation | MAS theory |

### Framework Implementation

#### Transition Function

```
Action (LLM) → Validation → Execution → State Update → Memory → Observation
```

```python
# Simplified execution flow
result = skill_broker.validate_skill(proposal)
if result.approved:
    execution = simulation_engine.execute_skill(result.skill)
    state_manager.apply_changes(execution.state_changes)
    memory_engine.add_memory(agent_id, execution.outcome)
```

#### Game Master: Partial Implementation

The framework implements **partial GM functionality**:

| GM Function | Implementation | Module |
|-------------|----------------|--------|
| Action Validation | ✅ Full | `SkillBrokerEngine` |
| Action Execution | ✅ Full | `SimulationEngine` |
| Natural Language Resolution | ⚠️ Partial | Structured skills only |
| World State Narration | ❌ Missing | No narrator module |

```python
# broker/core/skill_broker_engine.py
class SkillBrokerEngine:
    """Partial Game Master: Validates and executes agent actions."""

    def resolve_action(self, agent: Agent, action: str) -> ExecutionResult:
        # 1. Parse action into SkillProposal
        proposal = self.parse_action(action)

        # 2. Validate against governance rules
        validation = self.validate(proposal, agent)

        # 3. Execute if approved
        if validation.approved:
            return self.execute(validation.skill)
        else:
            return ExecutionResult(status="blocked", reason=validation.errors)
```

#### Event Generation

```python
# broker/components/event_generators/
class HazardEventGenerator(EventGeneratorProtocol):
    def generate(self, year: int, step: int, context: Dict) -> List[EnvironmentEvent]:
        """Generate flood events based on hazard model."""
        pass

class PolicyEventGenerator(EventGeneratorProtocol):
    def generate(self, year: int, step: int, context: Dict) -> List[EnvironmentEvent]:
        """Generate policy change events."""
        pass

# broker/components/ma_event_manager.py
class MAEventManager:
    def register(self, domain: str, generator: EventGeneratorProtocol):
        self.generators[domain] = generator

    def generate_all(self, year: int, step: int) -> List[EnvironmentEvent]:
        events = []
        for gen in self.generators.values():
            events.extend(gen.generate(year, step, self.context))
        return events
```

#### Feedback Loop (5 Steps)

```
1. Execute  → SimulationEngine.execute_skill()
2. Apply    → StateManager.apply_state_changes()
3. Memory   → MemoryEngine.add_memory()
4. Observe  → ContextBuilder.build()
5. Perceive → PerceptionFilter.filter()
```

### Literature References

- **Vezhnevets et al.** (2023): Concordia GM concept. Zotero Key: `HITVU4HK`
- **Gilbert** (2019): ABM methodology. Zotero Key: `67PWUHTW`

---

## Layer 5: Communication Layer

**Purpose**: Define "how agents interact" - messaging, coordination, synchronization.

### Theoretical Foundation

| Concept | Description | Literature |
|---------|-------------|------------|
| **Network Topology** | Agent connection patterns | Barabási (2016) |
| **P2P Communication** | Direct agent messaging | MAS (Wooldridge, 2009) |
| **Broadcast** | One-to-many messaging | MAS |
| **Pub-Sub** | Publish-subscribe pattern | MetaGPT (2023) |
| **Social Learning** | Learning from others | Bandura (1977) |

### Framework Implementation

#### Network Topology: SocialGraph

```python
# broker/components/social_graph.py
class SocialGraph:
    topology: Literal["global", "random", "neighborhood", "spatial", "custom"]

    def get_neighbors(self, agent_id: str) -> List[str]:
        """Return connected agents."""
        pass

# broker/components/social_graph_config.py
class SocialGraphConfig:
    topology: str = "spatial"
    neighbor_radius: float = 1000.0  # meters
    max_neighbors: int = 8
```

#### P2P Communication: InteractionHub

```python
# broker/components/interaction_hub.py
class InteractionHub:
    def get_visible_neighbor_actions(
        self,
        agent_id: str,
        social_graph: SocialGraph,
    ) -> Dict[str, str]:
        """Get observable actions from neighbors."""
        neighbors = social_graph.get_neighbors(agent_id)
        return {n: self.action_log.get(n) for n in neighbors}

    def calculate_neighbor_influence(
        self,
        agent_id: str,
        action: str,
    ) -> float:
        """Calculate % of neighbors who took action."""
        neighbors = self.social_graph.get_neighbors(agent_id)
        count = sum(1 for n in neighbors if self.action_log.get(n) == action)
        return count / len(neighbors)  # 0-1 normalized
```

#### Broadcast: MAEventManager

```python
# broker/components/ma_event_manager.py
class EventScope(Enum):
    GLOBAL = "global"       # All agents
    TYPE = "type"           # Same agent type
    SPATIAL = "spatial"     # Nearby agents
    TARGETED = "targeted"   # Specific agents

class MAEventManager:
    def broadcast(self, event: EnvironmentEvent, scope: EventScope):
        """Broadcast event to agents based on scope."""
        if scope == EventScope.GLOBAL:
            targets = self.all_agents
        elif scope == EventScope.TYPE:
            targets = self.agents_by_type[event.target_type]
        # ...
```

#### Shared Message Pool (Task-054)

```python
# broker/components/message_pool.py
class MessagePool:
    """MetaGPT-style shared message pool with pub-sub + mailbox delivery."""

    def publish(self, message: AgentMessage) -> int:
        """Add message and distribute to mailboxes."""

    def broadcast(self, sender_id, sender_type, content, ...) -> AgentMessage:
        """Broadcast to all registered agents."""

    def send_to_neighbors(self, sender_id, content, ...) -> AgentMessage:
        """Send to social graph neighbors only."""

    def send_direct(self, sender_id, sender_type, recipient_id, ...) -> AgentMessage:
        """Point-to-point messaging."""

    def subscribe(self, agent_id, message_types=None, source_types=None):
        """Register interest in specific message types."""

    def get_unread(self, agent_id) -> List[AgentMessage]:
        """Read cursor-based unread tracking."""

    def advance_step(self, current_step) -> int:
        """TTL-based message expiration."""
```

| Feature | Status | Module |
|---------|--------|--------|
| Subscribe to topics | ✅ Implemented | `MessagePool.subscribe()` |
| Unsubscribe | ✅ Implicit (re-subscribe with empty list) | `MessagePool.subscribe()` |
| Message filtering | ✅ Full | `Subscription.matches()` |
| TTL expiration | ✅ Full | `MessagePool.advance_step()` |
| Priority ordering | ✅ Full | `MessagePool.get_messages()` |
| Context injection | ✅ Full | `MessagePoolProvider.provide()` |

#### Game Master / Coordinator (Task-054)

```python
# broker/components/coordinator.py
class GameMaster:
    """Concordia-style central coordinator for action resolution."""

    def submit_proposal(self, proposal: ActionProposal) -> None:
        """Collect agent proposals during execution."""

    def resolve_phase(self, shared_state=None) -> List[ActionResolution]:
        """Resolve all proposals using pluggable strategy."""

    def get_resolution(self, agent_id: str) -> Optional[ActionResolution]:
        """Look up resolution for specific agent."""

# Strategies:
class PassthroughStrategy:     # Approve all (no conflict checking)
class ConflictAwareStrategy:   # Use ConflictResolver for conflicts
class CustomStrategy:          # Delegate to user callable
```

#### Conflict Resolution (Task-054)

```python
# broker/components/conflict_resolver.py
class ConflictDetector:
    """Detect resource over-allocation from proposals."""

class ConflictResolver:
    """Orchestrate detection + resolution."""

# Resolution strategies:
class PriorityResolution:      # Institutional > MG > NMG ordering
class ProportionalResolution:  # Split proportionally
```

#### Phase Orchestration (Task-054)

```python
# broker/components/phase_orchestrator.py
class PhaseOrchestrator:
    """Configurable multi-phase execution ordering."""

    def get_execution_plan(self, agents) -> List[Tuple[ExecutionPhase, List[str]]]:
        """Topological sort of phase dependencies."""

    @classmethod
    def from_yaml(cls, path: str) -> "PhaseOrchestrator":
        """Load from YAML configuration."""

# Default phases: INSTITUTIONAL → HOUSEHOLD → RESOLUTION → OBSERVATION
```

#### Synchronization: EventPhase

```python
# broker/core/experiment.py
class EventPhase(Enum):
    PRE_YEAR = "pre_year"   # Before agent actions
    PER_STEP = "per_step"   # During agent turn
    POST_YEAR = "post_year" # After all agents acted

class ExperimentRunner:
    def run_year(self, year: int):
        # 1. Pre-year events (environment changes)
        self.process_events(EventPhase.PRE_YEAR)

        # 2. Agent actions (parallel or sequential)
        with ThreadPoolExecutor(max_workers=self.parallelism) as executor:
            futures = [executor.submit(self.run_agent, a) for a in self.agents]

        # 3. Post-year events (settlements, decay)
        self.process_events(EventPhase.POST_YEAR)
```

### Literature References

- **Hong et al.** (2023): MetaGPT shared message pool. Zotero Key: `U44MWXQC`
- **Bandura** (1977): Social learning theory. Zotero Key: `V2KWAFB8`
- **Barabási** (2016): Network science. Zotero Key: `DVZAZ8K4`
- **Wooldridge** (2009): Multi-agent systems. Zotero Key: `GNC2TMM6`

---

## Gap Analysis Summary

### Implemented vs. Missing Features

| Layer | Feature | Status | Priority |
|-------|---------|--------|----------|
| **State** | Entity separation (S_Ag, S_Ob, S_Env) | ✅ Full | - |
| **State** | Grounded variables | ✅ Full | - |
| **Observation** | Context pipeline | ✅ Full | - |
| **Observation** | Perception filtering | ✅ Full | - |
| **Observation** | Multimodal perception | ❌ Missing | LOW |
| **Action** | Memory stream | ✅ Full | - |
| **Action** | Reflection | ✅ Full | - |
| **Action** | Planning module | ⚠️ Implicit | MEDIUM |
| **Action** | Plan revision | ❌ Missing | MEDIUM |
| **Transition** | Action validation | ✅ Full | - |
| **Transition** | Game Master | ✅ Full (Task-054) | - |
| **Communication** | Network topology | ✅ Full | - |
| **Communication** | P2P messaging | ✅ Full | - |
| **Communication** | Pub-Sub messaging | ✅ Full (Task-054) | - |
| **Communication** | Conflict arbitration | ✅ Full (Task-054) | - |
| **Communication** | Phase orchestration | ✅ Full (Task-054) | - |
| **Communication** | Shared message pool | ✅ Full (Task-054) | - |

### Resolved Gaps (Task-054)

The following gaps identified in Task-052 were addressed in Task-054:

| Gap | Resolution | New Module | Tests |
|-----|-----------|------------|-------|
| ❌ Game Master | ✅ `GameMaster` + strategy pattern | `coordinator.py` | 20 |
| ❌ Conflict Resolution | ✅ `ConflictResolver` + Priority/Proportional | `conflict_resolver.py` | 15 |
| ❌ Agent Ordering | ✅ `PhaseOrchestrator` + topological sort | `phase_orchestrator.py` | 21 |
| ❌ Shared Message Pool | ✅ `MessagePool` + pub-sub + mailbox | `message_pool.py` | 23 |
| ❌ Pub-Sub | ✅ `Subscription` filtering in MessagePool | `message_pool.py` | included |
| ⚠️ Context injection | ✅ `MessagePoolProvider` | `message_provider.py` | included |

### Remaining Improvements

1. **Planning Module** (MEDIUM priority)
   - Add `DailyPlanGenerator` for explicit agent planning
   - Implement plan revision on significant events

2. **Negotiation Protocol** (LOW priority)
   - Multi-round agent negotiation / consensus building
   - Currently not implemented in any module

3. **LLM-based Institutional Agents** (LOW priority)
   - Government/Insurance currently rule-based
   - Consider LLM-based policy generation

---

## Literature Summary Table

| Layer | Key Papers | Zotero Keys |
|-------|------------|-------------|
| **State** | AgentTorch, PMT, Bubeck | RMNEUT7F, NV3BZ94J, ZADR7ZXE |
| **Observation** | Simon, POMDP | 6MSEC2KH, QU47TXUP |
| **Action** | Generative Agents, MemGPT, Toolformer, Miller, Cowan | MATE4MG3, 4K3K9MQJ, 4CUZ2ZTH, XNCU5J2T, NXZ6CFRI |
| **Transition** | Concordia, Gilbert ABM | HITVU4HK, 67PWUHTW |
| **Communication** | MetaGPT, Bandura, Barabási, Wooldridge | U44MWXQC, V2KWAFB8, DVZAZ8K4, GNC2TMM6 |

---

## Appendix: File-Module Mapping

### State Layer Files

```
examples/multi_agent/ma_agents/
├── household.py          # HouseholdAgentState
├── government.py         # GovernmentAgentState
└── insurance.py          # InsuranceAgentState

examples/multi_agent/environment/
├── tp_state.py           # TPState
├── tp_decay.py           # TPDecayEngine
├── vulnerability.py      # VulnerabilityCalculator
├── hazard.py             # FloodEvent
├── settlement.py         # SettlementReport
└── core.py               # DamageResult
```

### Observation Layer Files

```
broker/components/
├── context_builder.py        # ContextBuilder (12-step pipeline)
├── context_providers.py      # All provider implementations
├── perception_filter.py      # PerceptionFilterRegistry
└── observable_state.py       # ObservableStateManager

broker/interfaces/
├── observable_state.py       # ObservableScope enum
└── perception.py             # PerceptionFilterProtocol
```

### Action Layer Files

```
broker/components/
├── memory.py                 # CognitiveMemory
├── memory_engine.py          # MemoryEngine wrapper
├── reflection_engine.py      # ReflectionEngine
├── skill_registry.py         # SkillRegistry
└── skill_retriever.py        # SkillRetriever

cognitive_governance/memory/
├── unified_engine.py         # UnifiedCognitiveEngine v5
├── retrieval.py              # AdaptiveRetrievalEngine
├── store.py                  # UnifiedMemoryStore
└── config/
    └── cognitive_constraints.py  # CognitiveConstraints
```

### Transition Layer Files

```
broker/core/
├── skill_broker_engine.py    # SkillBrokerEngine
├── experiment.py             # ExperimentRunner
└── governed_broker.py        # GovernedBroker

broker/components/
├── event_manager.py          # EventManager
├── ma_event_manager.py       # MAEventManager
└── event_generators/
    ├── flood.py              # FloodEventGenerator
    ├── hazard.py             # HazardEventGenerator
    ├── policy.py             # PolicyEventGenerator
    └── impact.py             # ImpactEventGenerator
```

### Communication Layer Files

```
broker/interfaces/
└── coordination.py           # Shared types (Task-054):
                              #   ExecutionPhase, PhaseConfig,
                              #   ActionProposal, ActionResolution,
                              #   ResourceConflict, AgentMessage, Subscription

broker/components/
├── social_graph.py           # SocialGraph (5 topologies)
├── social_graph_config.py    # SocialGraphConfig
├── neighbor_utils.py         # Neighbor calculation utilities
├── message_pool.py           # MessagePool (Task-054): pub-sub + mailbox
├── message_provider.py       # MessagePoolProvider (Task-054): context injection
├── conflict_resolver.py      # ConflictResolver (Task-054): detection + resolution
├── coordinator.py            # GameMaster (Task-054): action resolution
└── phase_orchestrator.py     # PhaseOrchestrator (Task-054): execution ordering
```

### Communication Layer Tests

```
tests/
├── test_message_pool.py              # 23 tests
├── test_conflict_resolver.py         # 15 tests
├── test_coordinator.py               # 20 tests
├── test_phase_orchestrator.py        # 21 tests
└── integration/
    └── test_communication_layer.py   # 8 integration tests
```

**Total Communication Layer: 87 tests (all passing)**

---

*Document generated as part of Task-052 (analysis) and Task-054 (Communication Layer implementation)*
