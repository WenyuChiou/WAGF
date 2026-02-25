# Memory and Retrieval System

## Overview

This document explains the memory system architecture used in the Water Agent Governance Framework for agent-based simulations.

## Memory Engines

### 1. WindowMemoryEngine (Baseline)

- **Type**: Sliding window
- **Retrieval**: Last N events only
- **Use case**: Simple experiments, no emotional weighting

### 2. ImportanceMemoryEngine

- **Type**: Keyword-based scoring
- **Retrieval**: Prioritizes significant events (flood, damage)
- **Use case**: Importance-weighted recall

### 3. HumanCentricMemoryEngine (Recommended)

- **Type**: Human-inspired memory model
- **Features**:
  - Emotional encoding (fear, relief, regret)
  - Source differentiation (personal > neighbor > community)
  - Time decay: e^(-λt)
  - Stochastic consolidation (working → long-term)
- **Use case**: Realistic behavioral simulation

## Memory Flow

```
Event occurs → Working Memory (short-term)
                    ↓
            Importance scoring (emotion × source)
                    ↓
            Stochastic consolidation (70% prob)
                    ↓
            Long-term Storage (episodic)
```

## Retrieval Mechanism

**Type: Passive (Context-triggered)**

At each decision point, memories are automatically retrieved:

1. Recent N events (working memory)
2. Top-K significant events (long-term, ranked by importance)

No explicit query required - retrieval is triggered by `ContextBuilder.build()`.

## Importance Scoring

| Factor      | Weight | Description                 |
| ----------- | ------ | --------------------------- |
| **Emotion** |        |                             |
| fear        | 1.0    | Flood damage, loss          |
| regret      | 0.9    | Poor decisions              |
| relief      | 0.6    | Recovery, positive outcomes |
| neutral     | 0.3    | Routine events              |
| **Source**  |        |                             |
| personal    | 1.0    | Direct experience           |
| neighbor    | 0.7    | Social network              |
| community   | 0.4    | Public information          |

**Formula**: `importance = emotion_weight × source_weight × (1 - decay)`

## Literature References

- Park et al. (2023): Generative Agents - human-centric memory with reflection
- Atkinson & Shiffrin (1968): Short-term to long-term memory model
- Ebbinghaus (1885): Forgetting curve, exponential decay

See `docs/references/master_catalog.bib` for full citations.
