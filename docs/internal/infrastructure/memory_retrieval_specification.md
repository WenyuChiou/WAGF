# Memory and Retrieval Module Specification

## 1. Overview: Memory as State vs Retrieval as Tool

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MEMORY / RETRIEVAL DISTINCTION                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   MEMORY (State)                   RETRIEVAL (Tool)                         │
│   ─────────────────                ────────────────                         │
│   - Persistent storage             - Active extraction                      │
│   - Updated by events              - Invoked during reasoning               │
│   - Owned by agent                 - Returns subset to prompt               │
│   - Deterministic                  - May have scoring/ranking               │
│                                                                             │
│   Agent owns memory →              Agent calls retrieval →                  │
│   Memory accumulates               Retrieval returns relevant subset        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Principle

> **Memory is WHERE experiences are stored.**  
> **Retrieval is HOW experiences are accessed for decision-making.**

---

## 2. Memory Classification

### 2.1 Memory Types

| Type | Duration | Capacity | Decay | Use Case |
|------|----------|----------|-------|----------|
| **Working Memory** | Short-term | 5-10 items | None (evicted) | Recent decisions, current context |
| **Episodic Memory** | Long-term | 50+ items | Yes (time-based) | Significant experiences (floods, losses) |

### 2.2 Memory Item Structure

```python
@dataclass
class MemoryItem:
    content: str                 # Text description of experience
    importance: float = 0.5      # 0.0 - 1.0 (determines consolidation)
    year: int = 0                # Simulation year when created
    timestamp: datetime          # Real timestamp (for ordering)
    tags: List[str] = []         # Classification tags

# Examples:
MemoryItem(
    content="Year 3: A flood occurred causing $50,000 in damages",
    importance=0.9,      # High -> goes to episodic
    year=3,
    tags=["flood", "damage"]
)

MemoryItem(
    content="Year 4: I decided to buy_insurance",
    importance=0.5,      # Medium -> working memory
    year=4,
    tags=["decision"]
)
```

### 2.3 Memory Layers Flow

```
┌──────────────────────────────────────────────────────────────┐
│                     MEMORY LAYERS                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   Event occurs                                               │
│       ↓                                                      │
│   ┌──────────────┐                                           │
│   │ Importance   │                                           │
│   │ Assessment   │                                           │
│   └──────────────┘                                           │
│       ↓                                                      │
│   importance >= 0.7?                                         │
│       │                                                      │
│   Yes ↓           No ↓                                       │
│   ┌─────────────┐  ┌─────────────┐                           │
│   │  EPISODIC   │  │   WORKING   │                           │
│   │   Memory    │  │   Memory    │                           │
│   │ (permanent) │  │ (temp, FIFO)│                           │
│   └─────────────┘  └─────────────┘                           │
│                           │                                  │
│                    consolidate() at year end                 │
│                           │                                  │
│                    importance >= 0.7?                        │
│                           ↓                                  │
│                    Move to Episodic                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Retrieval Mechanism

### 3.1 Retrieval Scoring

```python
def retrieve(self, top_k: int = 5, current_year: int = 0) -> List[str]:
    """
    Two-phase retrieval:
    1. Working Memory (priority - most recent/important)
    2. Episodic Memory (decay-weighted importance)
    """
    
    # Phase 1: Working Memory
    # Scoring: timestamp (recent first) × importance
    working_scored = sorted(
        self._working,
        key=lambda x: (x.timestamp, x.importance),
        reverse=True
    )
    
    # Phase 2: Episodic Memory (supplement)
    # Scoring: decay(years_passed) × importance
    for item in self._episodic:
        years_passed = current_year - item.year
        decay = DECAY_RATE ** years_passed  # 0.95^years
        score = decay * importance
```

### 3.2 Retrieval Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `top_k` | 5 | Maximum memories returned |
| `current_year` | 0 | For decay calculation |
| `DECAY_RATE` | 0.95 | Per-year decay factor |

### 3.3 Retrieval as Tool (Skill Registry)

```yaml
# skill_registry.yaml
memory_tools:
  - skill_id: retrieve_memory
    description: "Retrieve relevant past experiences for decision making"
    eligible_agent_types: ["*"]  # All agents can use
    implementation_mapping: "memory.retrieve"
    parameters:
      top_k: 5
```

---

## 4. Memory Operations

### 4.1 Add Operations

| Method | Auto-Routes To | Importance Threshold |
|--------|----------------|---------------------|
| `add_experience()` | Working or Episodic | >= 0.7 → Episodic |
| `add_working()` | Working only | N/A |
| `add_episodic()` | Episodic only | N/A |
| `update_after_flood()` | Episodic | Fixed: 0.9 |
| `update_after_decision()` | Working | 0.7 (if not do_nothing) |

### 4.2 Event-Driven Memory Updates

```python
# After flood event
if damage > 0:
    agent.memory.update_after_flood(damage=50000, year=3)
    # → Episodic: "Year 3: A flood occurred causing $50,000 in damages"

# After decision
agent.memory.update_after_decision(decision="buy_insurance", year=3)
    # → Working: "Year 3: I decided to buy_insurance" (importance=0.7)

agent.memory.update_after_decision(decision="do_nothing", year=4)
    # → Working: "Year 4: I decided to do_nothing" (importance=0.3)
```

### 4.3 Consolidation (Year-End)

```python
def consolidate(self) -> int:
    """Move high-importance working memories to episodic."""
    transferred = 0
    for item in self._working:
        if item.importance >= CONSOLIDATION_THRESHOLD:
            self._episodic.append(item)
            transferred += 1
    # Working memory remains intact (will evict naturally)
    return transferred
```

---

## 5. Configuration

### 5.1 Memory Parameters

```python
class CognitiveMemory:
    # Capacity
    WORKING_CAPACITY = 10      # Max working memory items
    EPISODIC_CAPACITY = 50     # Max episodic memory items
    
    # Consolidation
    CONSOLIDATION_THRESHOLD = 0.7  # Move to episodic if >= this
    
    # Retrieval
    DECAY_RATE = 0.95          # Per-year decay for episodic
```

### 5.2 Importance Guidelines

| Event Type | Suggested Importance | Destination |
|------------|---------------------|-------------|
| Major flood (damage > $50k) | 0.9 | Episodic |
| Minor flood (damage < $10k) | 0.6 | Working |
| Elevation decision | 0.8 | Episodic |
| Insurance decision | 0.7 | Episodic |
| Do nothing | 0.3 | Working |
| Policy change observation | 0.5 | Working |
| Neighbor adaptation | 0.4 | Working |

---

## 6. Integration Points

### 6.1 With Prompt (Context)

```python
# prompts.py
def build_household_prompt(state, context, memory: CognitiveMemory):
    memories = memory.retrieve(top_k=5, current_year=context['year'])
    
    prompt = f"""
=== YOUR MEMORY ===
{chr(10).join(f'- {m}' for m in memories)}
"""
```

### 6.2 With Audit (Logging)

```python
# audit_writer.py
trace = {
    "context": {
        "memory_retrieved": memory.retrieve(top_k=5),
        "memory_working_count": len(memory._working),
        "memory_episodic_count": len(memory._episodic)
    }
}
```

### 6.3 With State (Persistence)

```python
# Memory is part of agent state
class HouseholdAgent:
    state: HouseholdAgentState
    memory: CognitiveMemory  # Persistent across years
    
    def serialize(self) -> Dict:
        return {
            "state": asdict(self.state),
            "memory": {
                "working": [asdict(m) for m in self.memory._working],
                "episodic": [asdict(m) for m in self.memory._episodic]
            }
        }
```

### 6.4 Environment → Agent Information Flow (Observable Events)

Agent 如何得知災害程度和財務損失：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              ENVIRONMENT → MEMORY INFORMATION FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   HAZARD MODULE             VULNERABILITY MODULE        FINANCE MODULE      │
│   ─────────────             ───────────────────        ──────────────       │
│   FloodEvent                DamageEstimate             FinancialOutcome     │
│   • occurred: bool          • building_damage          • claim_approved     │
│   • depth_ft: float         • contents_damage          • insurance_payout   │
│   • extent: str             • total_damage             • out_of_pocket      │
│                             • depth_above_floor        • deductible_paid    │
│       │                           │                           │             │
│       ▼                           ▼                           ▼             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    AGENT OBSERVABLE (可見)                          │   │
│   │                                                                     │   │
│   │  • "A flood occurred this year" (from Hazard)                       │   │
│   │  • "My home sustained $X in damages" (from Vulnerability)           │   │
│   │  • "Insurance paid $Y for my claim" (from Finance)                  │   │
│   │  • "I paid $Z out-of-pocket" (from Finance)                         │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    MEMORY UPDATE                                    │   │
│   │                                                                     │   │
│   │  update_memory_from_flood(flood, damage, year)                      │   │
│   │  update_memory_from_claim(outcome, year)                            │   │
│   │  → Creates MemoryItem with appropriate importance                   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Observable vs Non-Observable

| Category | Observable by Agent | Not Observable |
|----------|---------------------|----------------|
| **Hazard** | `flood_occurred`, `flood_severity` | Probability distribution, regional impacts |
| **Exposure** | `my_property_value`, `my_flood_zone` | Neighbor property values |
| **Vulnerability** | `my_damage`, `damage_ratio` | Neighbor damage, total community damage |
| **Finance** | `my_payout`, `my_out_of_pocket`, `claim_result` | Insurance reserves, loss ratio, other claims |

#### Memory Templates by Event Type

```python
EVENT_MEMORY_TEMPLATES = {
    "flood_with_damage": {
        "template": "Year {year}: A flood caused ${damage:,.0f} in damages to my home",
        "importance": lambda damage: 0.9 if damage > 50000 else 0.6,
        "destination": "episodic",
        "tags": ["flood", "damage"]
    },
    "flood_no_damage": {
        "template": "Year {year}: A flood occurred but my home was not damaged",
        "importance": 0.4,
        "destination": "working",
        "tags": ["flood", "no_damage"]
    },
    "claim_approved": {
        "template": "Year {year}: Insurance covered ${payout:,.0f} of my ${damage:,.0f} loss",
        "importance": 0.7,
        "destination": "episodic",
        "tags": ["insurance", "claim", "approved"]
    },
    "claim_denied": {
        "template": "Year {year}: My insurance claim was denied",
        "importance": 0.85,  # Denial is very memorable
        "destination": "episodic",
        "tags": ["insurance", "claim", "denied"]
    },
    "high_oop": {
        "template": "Year {year}: I paid ${oop:,.0f} out-of-pocket for flood repairs",
        "importance": lambda oop: 0.85 if oop > 20000 else 0.5,
        "destination": "episodic",
        "tags": ["expense", "out_of_pocket"]
    }
}
```

#### Information Timing

```
Year Loop:
│
├── BEGINNING: Agent makes decision (uses past memories)
│
├── MIDDLE: Environment events occur
│   ├── Hazard: Flood generated
│   ├── Exposure: Agent exposed
│   ├── Vulnerability: Damage calculated
│   └── Finance: Claims processed
│
└── END: Agent receives information (updates memory)
    ├── Agent learns: "A flood occurred"
    ├── Agent learns: "My damage was $X"
    ├── Agent learns: "Insurance paid $Y"
    └── Memory updated for NEXT year's decisions
```

---

## 7. Test Specification

### 7.1 Unit Tests

```python
def test_memory_add_working():
    """Test working memory add and eviction."""
    mem = CognitiveMemory(agent_id="H001")
    
    # Add items up to capacity
    for i in range(12):
        mem.add_working(f"Event {i}", importance=0.5)
    
    assert len(mem._working) == 10  # Capacity limit
    assert "Event 0" not in [m.content for m in mem._working]  # Evicted

def test_memory_add_episodic():
    """Test episodic memory add."""
    mem = CognitiveMemory(agent_id="H001")
    mem.add_episodic("Major flood", importance=0.9, year=3)
    
    assert len(mem._episodic) == 1
    assert mem._episodic[0].tags == []

def test_memory_consolidation():
    """Test transfer from working to episodic."""
    mem = CognitiveMemory(agent_id="H001")
    mem.add_working("Low importance", importance=0.3)
    mem.add_working("High importance", importance=0.8)
    
    transferred = mem.consolidate()
    assert transferred == 1
    assert len(mem._episodic) == 1

def test_memory_retrieval_priority():
    """Test working memory takes priority."""
    mem = CognitiveMemory(agent_id="H001")
    mem.add_episodic("Old event", importance=0.9, year=1)
    mem.add_working("Recent event", importance=0.5, year=5)
    
    retrieved = mem.retrieve(top_k=2, current_year=5)
    assert retrieved[0] == "Recent event"  # Working first

def test_memory_retrieval_decay():
    """Test episodic memory decay."""
    mem = CognitiveMemory(agent_id="H001")
    mem.add_episodic("Year 1 event", importance=0.9, year=1)
    mem.add_episodic("Year 10 event", importance=0.5, year=10)
    
    retrieved = mem.retrieve(top_k=2, current_year=10)
    # Year 10 event should rank higher despite lower importance
    # due to less decay
```

### 7.2 Integration Tests

```python
def test_memory_with_flood_decision_cycle():
    """Test full cycle: flood → memory → decision → memory."""
    agent = HouseholdAgent(state=..., memory=CognitiveMemory("H001"))
    
    # Year 1: Flood occurs
    agent.memory.update_after_flood(damage=50000, year=1)
    assert len(agent.memory._episodic) == 1
    
    # Year 2: Agent retrieves memory for decision
    memories = agent.memory.retrieve(top_k=5, current_year=2)
    assert "flood" in memories[0].lower()
    
    # Year 2: Agent decides to buy insurance
    agent.memory.update_after_decision("buy_insurance", year=2)
    assert len(agent.memory._working) == 1

def test_memory_serialization():
    """Test memory can be saved and restored."""
    mem = CognitiveMemory(agent_id="H001")
    mem.add_episodic("Event 1", importance=0.9, year=1)
    mem.add_working("Event 2", importance=0.5, year=2)
    
    # Serialize
    data = {
        "working": [{"content": m.content, "importance": m.importance} 
                    for m in mem._working],
        "episodic": [{"content": m.content, "importance": m.importance} 
                     for m in mem._episodic]
    }
    
    # Deserialize
    new_mem = CognitiveMemory(agent_id="H001")
    for item in data["working"]:
        new_mem.add_working(item["content"], item["importance"])
    for item in data["episodic"]:
        new_mem.add_episodic(item["content"], item["importance"])
    
    assert len(new_mem._working) == 1
    assert len(new_mem._episodic) == 1
```

---

## 8. Retrieval as Skill (Tool Invocation)

### 8.1 Skill Registry Entry

```yaml
# skill_registry.yaml
memory_tools:
  - skill_id: retrieve_memory
    description: "Retrieve relevant past experiences for decision making"
    eligible_agent_types: ["*"]  # All agents can use
    preconditions: []
    institutional_constraints:
      max_retrieve: 5
    allowed_state_changes: []  # Read-only
    implementation_mapping: "memory.retrieve"
```

### 8.2 Retrieval Invocation

```python
# During agent reasoning phase
def prepare_context(agent: HouseholdAgent, year: int) -> Dict:
    """Invoke retrieval as a tool call."""
    
    # Tool: retrieve_memory
    retrieved_memories = agent.memory.retrieve(top_k=5, current_year=year)
    
    return {
        "state": agent.state,
        "retrieved_memories": retrieved_memories,  # Tool output
        "year": year
    }
```

### 8.3 Retrieval Audit Trail

```json
{
  "tool_invocation": {
    "tool_id": "retrieve_memory",
    "parameters": {
      "top_k": 5,
      "current_year": 3
    },
    "result": [
      "Year 2: A flood occurred causing $50,000 in damages",
      "Year 2: I decided to buy_insurance"
    ],
    "result_count": 2
  }
}
```

---

## 9. Memory in Audit Logs

### 9.1 Audit Trace Structure

```python
# audit_writer.py
def write_household_trace(
    self,
    output: HouseholdOutput,
    state: Dict,
    context: Dict,
    memory: CognitiveMemory  # NEW: Include memory
):
    trace = {
        "timestamp": datetime.now().isoformat(),
        "year": output.year,
        "agent_id": output.agent_id,
        
        # State
        "state_before": state,
        
        # Memory (NEW)
        "memory": {
            "retrieved": memory.retrieve(top_k=5, current_year=output.year),
            "working_count": len(memory._working),
            "episodic_count": len(memory._episodic),
            "working_items": [
                {"content": m.content, "importance": m.importance, "year": m.year}
                for m in memory._working
            ],
            "episodic_items": [
                {"content": m.content, "importance": m.importance, "year": m.year}
                for m in memory._episodic[:10]  # Limit to 10 for audit
            ]
        },
        
        # Reasoning
        "reasoning": {...},
        
        # Action
        "action": {...},
        
        # Validation
        "validation": {...}
    }
```

### 9.2 Memory Update Audit

```python
# After decision, log memory updates
def log_memory_update(
    self,
    agent_id: str,
    year: int,
    update_type: str,  # "flood" or "decision"
    memory_item: MemoryItem
):
    update_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent_id": agent_id,
        "year": year,
        "update_type": update_type,
        "memory_item": {
            "content": memory_item.content,
            "importance": memory_item.importance,
            "destination": "episodic" if memory_item.importance >= 0.7 else "working",
            "tags": memory_item.tags
        }
    }
    # Append to memory_updates.jsonl
```

### 9.3 Year-End Consolidation Audit

```python
# At year end, log consolidation
def log_consolidation(
    self,
    agent_id: str,
    year: int,
    transferred_count: int,
    transferred_items: List[str]
):
    consolidation_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent_id": agent_id,
        "year": year,
        "consolidation": {
            "transferred_count": transferred_count,
            "transferred_items": transferred_items,
            "working_after": len(memory._working),
            "episodic_after": len(memory._episodic)
        }
    }
```

---

## 10. Skill-Based Memory Storage

### 10.1 Skill → Memory Mapping

| Skill ID | Memory Update | Importance | Destination |
|----------|---------------|------------|-------------|
| `buy_insurance` | "I purchased flood insurance" | 0.7 | Episodic |
| `elevate_house` | "I elevated my house" | 0.8 | Episodic |
| `relocate` | "I relocated to a new area" | 0.9 | Episodic |
| `do_nothing` | "I chose not to take action" | 0.3 | Working |

### 10.2 Implementation

```python
# After decision execution
def update_memory_from_skill(
    memory: CognitiveMemory,
    skill_id: str,
    year: int,
    context: Dict = None
) -> MemoryItem:
    """Add memory based on skill executed."""
    
    SKILL_MEMORY_MAP = {
        "buy_insurance": {
            "template": "Year {year}: I purchased flood insurance (premium: ${premium:.0f})",
            "importance": 0.7,
            "tags": ["decision", "insurance"]
        },
        "elevate_house": {
            "template": "Year {year}: I elevated my house with {subsidy_pct:.0%} subsidy",
            "importance": 0.8,
            "tags": ["decision", "elevation"]
        },
        "relocate": {
            "template": "Year {year}: I relocated to a safer area",
            "importance": 0.9,
            "tags": ["decision", "relocation"]
        },
        "do_nothing": {
            "template": "Year {year}: I chose to wait and not take protective action",
            "importance": 0.3,
            "tags": ["decision", "inaction"]
        }
    }
    
    config = SKILL_MEMORY_MAP.get(skill_id)
    if not config:
        return None
    
    content = config["template"].format(year=year, **(context or {}))
    return memory.add_experience(
        content=content,
        importance=config["importance"],
        year=year,
        tags=config["tags"]
    )
```

### 10.3 Environment Event → Memory

```python
# After flood event
def update_memory_from_flood(
    memory: CognitiveMemory,
    flood: FloodEvent,
    damage: DamageEstimate,
    year: int
) -> MemoryItem:
    """Add memory based on flood experience."""
    
    if damage.total_damage > 0:
        severity = "major" if damage.total_damage > 50000 else "minor"
        content = f"Year {year}: A {severity} flood caused ${damage.total_damage:,.0f} in damages"
        return memory.add_episodic(
            content=content,
            importance=0.9 if severity == "major" else 0.6,
            year=year,
            tags=["flood", severity]
        )
    
    elif flood.occurred:
        content = f"Year {year}: A flood occurred but caused no damage to my property"
        return memory.add_working(
            content=content,
            importance=0.4,
            year=year,
            tags=["flood", "no_damage"]
        )
    
    return None

# After insurance claim
def update_memory_from_claim(
    memory: CognitiveMemory,
    outcome: FinancialOutcome,
    year: int
) -> MemoryItem:
    """Add memory based on insurance claim experience."""
    
    if outcome.claim_filed:
        if outcome.claim_approved:
            content = f"Year {year}: Insurance paid ${outcome.insurance_payout:,.0f} for my claim"
            return memory.add_episodic(
                content=content,
                importance=0.7,
                year=year,
                tags=["insurance", "claim", "approved"]
            )
        else:
            content = f"Year {year}: My insurance claim was denied"
            return memory.add_episodic(
                content=content,
                importance=0.8,  # Denial is memorable
                year=year,
                tags=["insurance", "claim", "denied"]
            )
    return None
```

---

## 11. Complete Audit Trail Example

```json
{
  "timestamp": "2026-01-05T04:30:00.000000",
  "year": 3,
  "agent_id": "H001",
  
  "state_before": {
    "elevated": false,
    "has_insurance": true,
    "cumulative_damage": 50000
  },
  
  "memory": {
    "retrieved": [
      "Year 2: A major flood caused $50,000 in damages",
      "Year 2: I purchased flood insurance (premium: $1,200)"
    ],
    "working_count": 3,
    "episodic_count": 2,
    "retrieval_scores": [
      {"content": "Year 2: A major flood...", "score": 0.855},
      {"content": "Year 2: I purchased...", "score": 0.665}
    ]
  },
  
  "reasoning": {
    "constructs": {
      "TP": {"level": "HIGH", "explanation": "Experienced major damage last year"},
      "CP": {"level": "MODERATE", "explanation": "Insurance helped but OOP still high"}
    },
    "justification": "Given my past flood experience and available subsidy..."
  },
  
  "action": {
    "decision_skill": "elevate_house",
    "skill_parameters": {
      "subsidy_rate": 0.5
    }
  },
  
  "memory_update": {
    "type": "skill_execution",
    "content": "Year 3: I elevated my house with 50% subsidy",
    "importance": 0.8,
    "destination": "episodic"
  },
  
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": []
  },
  
  "state_after": {
    "elevated": true,
    "has_insurance": true,
    "cumulative_damage": 50000
  }
}
```

---

## 12. Implementation Checklist

### Memory Core
- [x] `MemoryItem` dataclass with metadata
- [x] `CognitiveMemory.add_working()` with FIFO eviction
- [x] `CognitiveMemory.add_episodic()` with capacity control
- [x] `CognitiveMemory.consolidate()` for year-end transfer
- [x] `CognitiveMemory.retrieve()` with decay scoring
- [x] `update_after_flood()` convenience method
- [x] `update_after_decision()` convenience method
- [x] `format_for_prompt()` for LLM integration
- [x] `to_list()` for ContextBuilder compatibility

### Retrieval as Skill
- [x] Skill Registry entry for `retrieve_memory`
- [ ] Tool invocation logging in audit
- [ ] Retrieval parameters in audit trace

### Audit Integration
- [ ] Memory snapshot in household trace
- [ ] Memory update logging
- [ ] Consolidation logging at year-end

### Skill-Based Storage
- [ ] Skill → Memory mapping configuration
- [ ] `update_memory_from_skill()` implementation
- [ ] `update_memory_from_flood()` implementation
- [ ] `update_memory_from_claim()` implementation

### Future
- [ ] Memory serialization/deserialization
- [ ] Tag-based retrieval
- [ ] Query-based retrieval
