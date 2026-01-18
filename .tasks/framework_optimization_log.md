# Framework Optimization Log (v3.1 -> v4.0)

This document records technical debt and optimization opportunities identified during the "Stress Validation" phase of v3.1. These items are deferred to preserve experimental consistency but are critical for the next major version.

## 1. dormant Feature: Reflection Engine

**Status**: Implemented but Unused.
**Location**: `broker/components/reflection_engine.py`

### The Gap

The `ReflectionEngine` class exists and implements:

- `ReflectionInsight` data structure.
- `generate_batch_reflection_prompt` for year-end summary.
- `store_insight` for persistence.

However, `run_flood.py` (the main loop) **never imports or instantiates it**. The simulation currently runs purely on "Correction" (Retry Loop) without long-term "Reflection".

### Implementation Plan (v4.0)

1.  **Instantiate**: In `Experiment.__init__`, add `self.reflection_engine = ReflectionEngine(...)`.
2.  **Trigger**: In `Experiment.run_year()`, after all agents have acted:
    ```python
    if year % reflection_interval == 0:
        insights = self.reflection_engine.generate_batch_reflection_prompt(agents, year)
        for agent_id, insight in insights.items():
            # KEY: Save the insight back to the agent's memory so they "remember" the lesson
            self.memory_engine.add_memory(agent_id, insight.content, metadata={'type': 'reflection'})
    ```
3.  **Verify**: Measure if "Intervention Rate" decreases in later years (proof of learning).

## 2. Component: Memory Engine Scalability

**Status**: Functional but O(N) complexity.
**Location**: `broker/components/memory_engine.py`

### The Gap

`HumanCentricMemory` uses a simple Python `List` for storage.

- `retrieve()` performs a full linear scan to calculate time-decay for _every_ memory item.
- Performance acceptable for N=100 agents, 10 years (~10k items total).
- Will choke at N=10,000 agents.

### Optimization Plan

1.  **Vector Store**: Integrate `chromadb` or `faiss`.
2.  **Bucketing**: Maintain separate lists for `Critical` (Always check) vs `Routine` (Check only if recent).

## 3. Component: Governance Logic

**Status**: Stateless Functions.
**Location**: `broker/core/skill_registry.py`

### The Gap

Validators are pure functions (e.g., `check_budget(action)`). They cannot track _global_ state (e.g., "Total community spending this year").

### Optimization Plan

- Convert validators to `class Validator(ABC)` with `update_state(action)` methods.
