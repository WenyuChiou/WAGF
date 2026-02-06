# Cognitive Governance SDK

Universal Cognitive Governance Middleware for Agent Frameworks.

## Architecture Position

This package is a **companion SDK layer**, independent of the broker's 7-layer architecture:

```text
┌─────────────────────────────────────────────────────────────────┐
│  cognitive_governance/  (Companion SDK Layer)                   │
│  ├── memory/                 → UnifiedCognitiveEngine (v5)      │
│  │   └── strategies/         → EMA, Symbolic, Hybrid surprise   │
│  ├── agents/                 → BaseAgent, AgentProtocol         │
│  └── v1_prototype/           → Legacy (see DEPRECATED.md)       │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Used by broker L4 Memory Layer
                              │
┌─────────────────────────────────────────────────────────────────┐
│  broker/  (Core 7-Layer Architecture)                           │
│  L1 - LLM Interface    │  L5 - Reflection                       │
│  L2 - Governance       │  L6 - Social (MA only)                 │
│  L3 - Execution        │  L7 - Utilities                        │
│  L4 - Memory ◄─────────┴── Uses cognitive_governance            │
└─────────────────────────────────────────────────────────────────┘
```

**Use this package for**: Memory engines (UnifiedCognitiveEngine), surprise strategies, and base agent protocols.

**Use broker/ for**: Experiment runners, governance validators, context builders, and skill execution.

---

## Quick Start

```python
from cognitive_governance.v1_prototype.core.engine import PolicyEngine
from cognitive_governance.v1_prototype.core.policy_loader import PolicyLoader

# Create engine and policy
engine = PolicyEngine()
policy = PolicyLoader.from_dict({
    "rules": [
        {
            "id": "min_savings",
            "param": "savings",
            "operator": ">=",
            "value": 500,
            "message": "Need $500",
            "level": "ERROR",
        }
    ]
})

# Verify action
trace = engine.verify(
    action={"action": "buy_insurance"},
    state={"savings": 300},
    policy=policy,
)

if trace.valid:
    print("Action ALLOWED")
else:
    print(f"Action BLOCKED: {trace.rule_message}")
    print(f"To pass: {trace.state_delta}")
```

## Features

| Feature | Description |
|---------|-------------|
| **PolicyEngine** | Stateless rule verification |
| **XAI Counterfactual** | "What change would make this pass?" |
| **SymbolicMemory** | O(1) state signature lookup |
| **EntropyCalibrator** | Detect over/under-governance |
| **UnifiedCognitiveEngine (v5)** | Unified memory with pluggable surprise strategies |

---

## v5 Unified Memory System

The v5 `UnifiedCognitiveEngine` provides a unified memory architecture combining the best of previous versions:

- **v2 HumanCentric**: Emotion/source weighting (preserved for SA experiment reproducibility)
- **v3 Universal**: EMA-based surprise detection
- **v4 Symbolic**: Frequency-based novelty detection

### Architecture

```
UnifiedCognitiveEngine (v5)
├── SurpriseStrategy (pluggable)
│   ├── EMASurpriseStrategy      # Continuous prediction error
│   ├── SymbolicSurpriseStrategy # Frequency-based novelty
│   └── HybridSurpriseStrategy   # 60% EMA + 40% Symbolic
├── UnifiedMemoryStore
│   ├── Working Memory (capacity limited)
│   └── Long-term Memory (consolidated)
└── AdaptiveRetrievalEngine
    └── System 1/2 switching based on arousal
```

### Usage Example

```python
from cognitive_governance.memory import UnifiedCognitiveEngine
from cognitive_governance.memory.strategies import (
    EMASurpriseStrategy,
    SymbolicSurpriseStrategy,
    HybridSurpriseStrategy,
)

# Option 1: EMA-based surprise (continuous sensor data)
strategy = EMASurpriseStrategy(stimulus_key="flood_depth", alpha=0.3)
engine = UnifiedCognitiveEngine(
    surprise_strategy=strategy,
    arousal_threshold=0.5,
    decay_rate=0.1,
)

# Option 2: Symbolic surprise (discrete events)
strategy = SymbolicSurpriseStrategy(default_sensor_key="flood_depth")
engine = UnifiedCognitiveEngine(surprise_strategy=strategy)

# Option 3: Hybrid (recommended for most use cases)
strategy = HybridSurpriseStrategy(
    ema_weight=0.6,
    symbolic_weight=0.4,
    ema_stimulus_key="flood_depth",
    ema_alpha=0.3,
)
engine = UnifiedCognitiveEngine(surprise_strategy=strategy)

# Add memories
engine.add_memory(
    agent_id="agent_001",
    content="Experienced severe flooding in 2024",
    metadata={
        "emotion": "major",      # major/minor/neutral
        "source": "personal",   # personal/neighbor/community
    }
)

# Retrieve with context
memories = engine.retrieve(
    agent_id="agent_001",
    context={"flood_depth": 1.5},
    top_k=5,
)

for mem in memories:
    print(f"- {mem.content} (importance: {mem.importance:.2f})")
```

### Configuration via YAML

```yaml
# agent_types.yaml
household:
  memory:
    engine_type: "unified"
    surprise_strategy: "hybrid"    # ema, symbolic, or hybrid
    arousal_threshold: 0.5         # System 1/2 switching threshold
    ema_alpha: 0.3                 # EMA smoothing factor
    decay_rate: 0.1                # Memory decay rate
    stimulus_key: "flood_depth"    # Sensor key for surprise calculation
    emotional_weights:
      direct_impact: 1.0
      strategic_choice: 0.8
      efficacy_gain: 0.6
      social_feedback: 0.4
    source_weights:
      personal: 1.0
      neighbor: 0.8
      community: 0.6
```

### Surprise Strategies

| Strategy | Use Case | How It Works |
|----------|----------|--------------|
| **EMA** | Continuous sensors | Tracks prediction error via exponential moving average |
| **Symbolic** | Discrete events | Detects novelty via frequency-based signatures |
| **Hybrid** | General purpose | Combines EMA (60%) + Symbolic (40%) |

### System 1/2 Cognitive Switching

When `arousal > arousal_threshold`:
- **System 2 Mode**: Emphasizes importance-weighted retrieval
- Slower, more deliberate memory access

When `arousal <= arousal_threshold`:
- **System 1 Mode**: Emphasizes recency-weighted retrieval
- Faster, automatic memory access

### Memory Factory Integration

Use the unified memory factory from broker:

```python
from broker.components.memory_factory import create_memory_engine

# Create any supported engine type
engine = create_memory_engine(
    engine_type="unified",  # or window, importance, humancentric, hierarchical, universal
    config={
        "surprise_strategy": "hybrid",
        "arousal_threshold": 0.5,
        "ema_alpha": 0.3,
    }
)
```

---

## Testing

```bash
# SDK tests (moved to tests/sdk/)
python cognitive_governance/demo_sdk_usage.py
python -m pytest tests/sdk/ -v

# v5 Memory tests
python -m pytest tests/test_unified_memory.py -v

# Memory factory tests
python -m pytest tests/test_memory_factory.py -v
```

---

## Version History

| Version | Engine | Key Feature |
|---------|--------|-------------|
| v1 | WindowMemoryEngine | Sliding window baseline |
| v2 | HumanCentricMemoryEngine | Emotion/source weighting |
| v3 | UniversalCognitiveEngine | EMA surprise + System 1/2 |
| v4 | SymbolicContextMonitor | Frequency-based novelty |
| **v5** | **UnifiedCognitiveEngine** | **Unified architecture with pluggable strategies** |

For SA experiment reproducibility, v2 `HumanCentricMemoryEngine` is preserved and recommended.
