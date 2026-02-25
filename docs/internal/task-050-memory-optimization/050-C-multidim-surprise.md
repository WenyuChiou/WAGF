# Task 050-C: Multi-dimensional Surprise Tracking

> **Status**: Complete
> **Priority**: MEDIUM
> **Complexity**: Low

---

## Overview

Extend the surprise tracking system to monitor multiple environmental variables simultaneously, providing richer anomaly detection for System 1/2 switching.

## Problem Statement

Current EMA surprise strategy limitations:
1. Only tracks a single variable (e.g., `flood_depth`)
2. Cannot detect multi-factor anomalies (e.g., low flood + high panic)
3. No weighted combination of multiple surprise sources
4. Misses cross-variable correlations

## Literature Reference

| Paper | Key Insight |
|-------|-------------|
| **A-MEM** (2025) | Multi-factor surprise triggers memory consolidation |
| **Generative Agents** (Park et al., 2023) | Importance from multiple relevance dimensions |
| **Dual-Process Theory** (Kahneman) | System 2 activation from any unexpected stimulus |

### From Zotero (Task-050 Collection)
- L1: A-MEM uses composite surprise for memory linking
- L3: Generative Agents aggregate multiple importance factors

## Technical Design

### 1. New Class: `MultiDimensionalSurpriseStrategy`

```python
class MultiDimensionalSurpriseStrategy(SurpriseStrategy):
    """
    Track multiple variables with weighted aggregation.

    Args:
        variables: Dict mapping variable_name -> weight
        alpha: EMA smoothing factor
        aggregation: "max", "mean", "weighted_sum"
    """

    def __init__(
        self,
        variables: Dict[str, float],  # {"flood_depth": 0.5, "panic_level": 0.3}
        alpha: float = 0.3,
        aggregation: str = "max"
    ):
        self._predictors: Dict[str, EMAPredictor] = {}
        self._weights = variables
        self._aggregation = aggregation
```

### 2. Aggregation Strategies

| Strategy | Formula | Use Case |
|----------|---------|----------|
| `max` | `max(s_i)` | Any anomaly triggers System 2 |
| `mean` | `mean(s_i)` | Balanced multi-factor |
| `weighted_sum` | `sum(w_i * s_i)` | Domain-weighted importance |

### 3. Integration with UnifiedCognitiveEngine

```python
# Enhanced configuration
surprise_config = {
    "strategy": "multidimensional",
    "variables": {
        "flood_depth": 0.4,
        "neighbor_panic": 0.3,
        "policy_change": 0.3
    },
    "aggregation": "max"
}
```

## Implementation Steps

1. [x] Create documentation
2. [x] Implement `MultiDimensionalSurpriseStrategy`
3. [x] Add unit tests (20 tests passing)
4. [x] Export from strategies/__init__.py
5. [ ] Update UnifiedCognitiveEngine integration (optional)

---

## Files Created/Modified

| File | Status | Description |
|------|--------|-------------|
| `cognitive_governance/memory/strategies/multidimensional.py` | Created | Multi-dimensional surprise |
| `cognitive_governance/memory/strategies/__init__.py` | Modified | Export new class |
| `cognitive_governance/memory/__init__.py` | Modified | Export new class |
| `tests/test_multidim_surprise.py` | Created | 20 unit tests |

## Usage Example

```python
from cognitive_governance.memory import (
    MultiDimensionalSurpriseStrategy,
    create_flood_surprise_strategy,
)

# Custom configuration
strategy = MultiDimensionalSurpriseStrategy(
    variables={
        "flood_depth": 0.4,
        "neighbor_panic": 0.3,
        "policy_change": 0.3
    },
    aggregation="max"  # Any spike triggers System 2
)

# Pre-configured for flood domain
strategy = create_flood_surprise_strategy(
    include_social=True,
    include_policy=True
)

# Update and get surprise
surprise = strategy.update({"flood_depth": 2.5, "neighbor_panic": 0.8})
dominant = strategy.get_dominant_variable()  # "neighbor_panic"
trace = strategy.get_trace()  # Detailed per-variable info
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-29 | Initial design document created |
| 2026-01-29 | Implementation complete, 20 tests passing |
