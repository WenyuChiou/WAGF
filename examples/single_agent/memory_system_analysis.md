# Memory System Analysis

## Memory Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    HumanCentricMemoryEngine                 │
├─────────────────────────────────────────────────────────────┤
│  Working Memory (Short-term)                                │
│  ├─ Recent events (window_size=3)                           │
│  └─ Fast access, no filtering                               │
├─────────────────────────────────────────────────────────────┤
│  Long-term Storage (Episodic)                               │
│  ├─ Scored by importance (emotion × source)                 │
│  ├─ Time decay: e^(-λt)                                     │
│  └─ Stochastic consolidation (prob=0.7)                     │
├─────────────────────────────────────────────────────────────┤
│  Retrieval (Passive, Context-triggered)                     │
│  ├─ Window: Always return last N                            │
│  └─ Significance: Top-k by importance score                 │
└─────────────────────────────────────────────────────────────┘
```

## How Memory Works

### 1. Memory Addition (Short → Long)

```python
# Event occurs
memory_engine.add_memory(agent_id, "Year 3: Flood caused $50,000 damage",
                         metadata={"emotion": "fear", "source": "personal"})

# Internal processing:
1. Classify emotion: fear/relief/regret/neutral
2. Classify source: personal > neighbor > community
3. Compute importance = emotion_weight × source_weight
4. Store in working memory with timestamp
5. Stochastic consolidation (70% prob) → Long-term storage
```

### 2. Importance Scoring

| Emotion | Weight | Description                          |
| ------- | ------ | ------------------------------------ |
| fear    | 1.0    | Flood damage, loss, threat           |
| regret  | 0.9    | Poor decisions, missed opportunities |
| relief  | 0.6    | Positive outcomes, recovery          |
| neutral | 0.3    | Routine events                       |

| Source    | Weight | Description                |
| --------- | ------ | -------------------------- |
| personal  | 1.0    | Direct experience          |
| neighbor  | 0.7    | Social network information |
| community | 0.4    | Public information, news   |

**Formula**: `importance = emotion_weight × source_weight × (1 - decay)`

### 3. Retrieval Mechanism

**Type: Passive (Context-triggered)**

At decision time, memories are **automatically retrieved** by the ContextBuilder:

```python
# In MultiAgentContextBuilder.build():
memory = memory_engine.retrieve(agent, top_k=3)

# HumanCentricMemoryEngine.retrieve():
def retrieve(self, agent, query=None, top_k=3):
    # 1. Get working memory (most recent)
    recent = working_memory[-window_size:]

    # 2. Apply time decay to long-term
    decayed = apply_decay(long_term, current_time)

    # 3. Rank by importance
    ranked = sorted(decayed, key=lambda m: m['importance'], reverse=True)

    # 4. Return combined (recent + top significant)
    return recent + ranked[:top_k_significant]
```

### 4. Memory Flow in Simulation

```
Year 1: Agent makes decision
  └─ add_memory("Year 1: I purchased flood insurance")

Year 2: Flood occurs
  └─ add_memory("Year 2: Flood caused $30,000 damage", emotion="fear")

Year 3: Agent decision
  └─ retrieve() returns:
     - "Year 2: Flood caused $30,000 damage" (HIGH: fear × personal)
     - "Year 1: I purchased flood insurance" (MEDIUM: neutral × personal)
```

## Comparison: With vs Without Memory Retrieval

### Without Memory (Baseline)

- Agent only sees current state (elevated, insured, damage)
- No historical context
- Decisions are reactive, not learning

### With Memory (HumanCentric)

- Agent recalls significant past events
- Emotional weighting prioritizes traumatic experiences
- Decisions reflect accumulated experience

### Expected Behavioral Differences

| Scenario               | Without Memory | With Memory                           |
| ---------------------- | -------------- | ------------------------------------- |
| After flood            | May do_nothing | More likely to protect (recalls fear) |
| Insurance claim denied | No effect      | Reduced trust (recalls regret)        |
| Neighbor elevated      | No awareness   | May follow (recalls neighbor success) |

## Experiment Recommendation

1. **deepseek & gpt-oss**: Need rerun (API issues, not framework bugs)
2. **gemma & llama**: Results valid (97% and 70% validation)
3. **Memory comparison**: Run same agents with:
   - `--memory-engine window` (baseline)
   - `--memory-engine humancentric` (full)

## Quick Test Command

```powershell
# With memory
python examples/single_agent/run_modular_experiment.py --model llama3.2:3b --memory-engine humancentric --years 10 --agents 50

# Without memory (window only)
python examples/single_agent/run_modular_experiment.py --model llama3.2:3b --memory-engine window --years 10 --agents 50
```
