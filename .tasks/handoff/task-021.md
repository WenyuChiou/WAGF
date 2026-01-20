# Task-021: Context-Dependent Memory Retrieval

**Status**: DONE

**Objective**: Implement a context-dependent memory retrieval mechanism for the `HumanCentricMemoryEngine` to allow agents to prioritize relevant memories based on environmental context (e.g., flood events), without compromising the engine's generality.

**Implementation Summary**:

1.  **Decoupled Design**: Separated application-specific "context analysis" from the generic "memory boosting" mechanism.
    -   `TieredContextBuilder` (application layer) is now responsible for analyzing the `env_context` (e.g., `flood_occurred`) and generating "boosting instructions" (`contextual_boosters`).
    -   `HumanCentricMemoryEngine` (generic layer) receives these `contextual_boosters` and applies a weighted score to memories that match the specified tags (e.g., `emotion:fear`).

2.  **Code Changes**:
    -   **`broker/components/context_builder.py`**:
        -   `TieredContextBuilder.build` now generates `contextual_boosters` based on `env_context.get("flood_occurred")`.
        -   `MemoryProvider.provide` now passes `contextual_boosters` to `memory_engine.retrieve`.
    -   **`broker/components/memory_engine.py`**:
        -   `HumanCentricMemoryEngine.__init__` now accepts configurable weights for recency, importance, and contextual boost (`W_recency`, `W_importance`, `W_context`).
        -   `HumanCentricMemoryEngine.retrieve` now implements the generic boosting logic based on the received `contextual_boosters`.
        -   `HumanCentricMemoryEngine._add_memory_internal` was corrected to properly handle `importance` and other metadata from the test setup.
        -   The logic for combining working and long-term memory in `retrieve` was corrected to ensure memory uniqueness and preserve metadata.
    -   **`tests/test_human_centric_memory_engine.py`**:
        -   A new unit test file was created to validate the context-dependent retrieval logic.
        -   The test was updated iteratively to reflect the bug fixes and now passes, confirming the functionality of both boosted and non-boosted retrieval.
    -   **`broker/utils/logging.py`**:
        -   Temporarily set to `DEBUG` for troubleshooting, then reverted to `INFO`.

**Validation**:
- All unit tests in `tests/test_human_centric_memory_engine.py` have passed, confirming that the new mechanism correctly prioritizes memories based on contextual boosters.

**Artifacts**:
- `.tasks/handoff/task-021-memory-retrieval-plan.md`: The detailed implementation plan for this task.
- `tests/test_human_centric_memory_engine.py`: The unit test file created to validate this feature.

**Conclusion**: The new memory retrieval mechanism has been successfully implemented and verified, enhancing the cognitive realism of the agents.
