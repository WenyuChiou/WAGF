# Task-026: Universal Cognitive Architecture (v3) Implementation

## Status
**Completed** (2026-01-20)

## Objective
Implement the Phase 3 "Surprise Engine" with EMA-based expectation tracking and System 1/2 switching logic for memory retrieval.

## Dependencies
- Task-021 (Context-Dependent Memory Retrieval) - completed

## Implementation Summary

### Core Components

#### 1. EMAPredictor
Exponential Moving Average predictor for tracking environmental expectations.

```python
class EMAPredictor:
    """
    Formula: E_t = (alpha * R_t) + ((1 - alpha) * E_{t-1})

    Methods:
    - update(reality) -> float: Update expectation based on observation
    - predict() -> float: Get current expectation
    - surprise(reality) -> float: Calculate prediction error
    """
```

#### 2. UniversalCognitiveEngine
System 1/2 cognitive architecture that extends HumanCentricMemoryEngine.

```python
class UniversalCognitiveEngine:
    """
    - System 1 (Routine): Low surprise, recency-biased retrieval
    - System 2 (Crisis): High surprise, importance-weighted retrieval

    Switching governed by: |Reality - Expectation| > arousal_threshold
    """
```

### Key Features

| Feature | Description |
|:--------|:------------|
| **EMA Tracking** | Tracks expectation of `flood_depth` (configurable) |
| **System Switching** | Automatic System 1/2 based on prediction error |
| **Boiling Frog** | Repeated exposure normalizes expectations |
| **v1/v2 Emulation** | Set `arousal_threshold=99.0` for v1, `0.0` for v2 |

### Files Created/Modified

| File | Change |
|:-----|:-------|
| `broker/components/universal_memory.py` | **NEW** - Main implementation |
| `tests/test_universal_memory.py` | **FIXED** - Updated patch path |
| `broker/components/memory_engine.py` | Factory already supports `"universal"` type |

### Usage

```python
from broker.components.memory_engine import create_memory_engine

# Create universal cognitive engine
engine = create_memory_engine(
    'universal',
    arousal_threshold=2.0,  # Surprise level to trigger System 2
    ema_alpha=0.3,          # Adaptation speed (0.1=slow, 0.9=fast)
    stimulus_key='flood_depth'  # Environment key to track
)

# Retrieve with world state for surprise calculation
memories = engine.retrieve(
    agent=agent,
    top_k=5,
    world_state={'flood_depth': 5.0}  # High depth = surprise
)

# Check cognitive state
state = engine.get_cognitive_state()
# {'system': 'SYSTEM_2', 'surprise': 5.0, 'expectation': 1.5, ...}
```

### Test Results

```
tests/test_universal_memory.py::TestEMAPredictor::test_ema_update_math PASSED
tests/test_universal_memory.py::TestUniversalCognitiveEngine::test_system_1_routine_low_surprise PASSED
tests/test_universal_memory.py::TestUniversalCognitiveEngine::test_system_2_crisis_high_surprise PASSED
tests/test_universal_memory.py::TestUniversalCognitiveEngine::test_normalization_adaptation_cycle PASSED
```

### Theoretical Foundation

- **Kahneman (2011)**: Thinking, Fast and Slow (System 1/2)
- **Friston (2010)**: Free Energy Principle / Predictive Processing
- **Park et al. (2023)**: Generative Agents memory architecture

## Integration Status

| Component | Status | Notes |
|:----------|:-------|:------|
| Unit Tests | Pass | 4/4 tests |
| Factory Function | Works | `create_memory_engine('universal')` |
| MA System | **NOT YET** | Requires integration into `run_unified_experiment.py` |

## Next Steps

1. **Task-027**: Integrate `UniversalCognitiveEngine` into MA system
   - Update `run_unified_experiment.py` to use `--memory-engine universal`
   - Pass `world_state` to `retrieve()` calls
   - Add CLI parameters for `arousal_threshold` and `ema_alpha`

2. **Validation**: Run experiments comparing System 1/2 behavior
   - Compare with humancentric engine
   - Measure "boiling frog" normalization effect

## Artifacts

- `broker/components/universal_memory.py`
- `tests/test_universal_memory.py`
