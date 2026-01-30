# Task-057D: MA Reflection Integration (Gemini Assignment)

**Assigned To**: Gemini
**Status**: READY (after 057-A, 057-B, 057-C)
**Priority**: High
**Estimated Scope**: ~95 lines new, 1 file + 1 test file
**Depends On**: 057-A (AgentReflectionContext), 057-B (retrieve_stratified), 057-C (compute_dynamic_importance)

---

## Objective

Wire the personalized reflection system into the Multi-Agent lifecycle hooks, supporting per-agent-type batch reflection with stratified retrieval.

Currently `lifecycle_hooks.py` has no reflection integration. The SA reflection loop lives in `run_flood.py` only. Multi-agent experiments need type-aware reflection (household agents reflect differently from government or insurance agents).

---

## Context

### Current Lifecycle Hooks (`examples/multi_agent/orchestration/lifecycle_hooks.py`)

```python
class MultiAgentHooks:
    def __init__(
        self,
        environment: Dict,
        memory_engine: Optional[MemoryEngine] = None,
        hazard_module: Optional[HazardModule] = None,
        media_hub: Optional[MediaHub] = None,
        per_agent_depth: bool = False,
        year_mapping: Optional[YearMapping] = None,
        game_master: Optional[Any] = None,
        message_pool: Optional[Any] = None,
    ):
        ...

    def pre_year(self, year, env, agents): ...
    def post_step(self, agent, result): ...
    def post_year(self, year, agents, memory_engine): ...
```

No `reflection_engine` parameter, no `_run_ma_reflection()` method.

### Reflection Engine API (from 057-A, 057-C)

```python
# ReflectionEngine methods available after 057-A/C:
ReflectionEngine.extract_agent_context(agent, year) -> AgentReflectionContext
engine.generate_personalized_batch_prompt(batch_data, year) -> str
engine.generate_batch_reflection_prompt(batch_data, year) -> str  # fallback
engine.parse_batch_reflection_response(response, batch_ids, year) -> Dict[str, ReflectionInsight]
engine.compute_dynamic_importance(context) -> float
engine.store_insight(agent_id, insight) -> None
engine.should_reflect(agent_id, year) -> bool
```

### Stratified Retrieval API (from 057-B)

```python
# HumanCentricMemoryEngine new method:
engine.retrieve_stratified(agent_id, allocation=None, total_k=10) -> List[str]
```

---

## Changes Required

### File: `examples/multi_agent/orchestration/lifecycle_hooks.py`

**Change 1:** Add import (at top of file, alongside existing imports):

```python
from broker.components.reflection_engine import ReflectionEngine, AgentReflectionContext
```

**Change 2:** Add `reflection_engine` parameter to `__init__` (add to existing parameter list):

```python
def __init__(
    self,
    environment: Dict,
    memory_engine: Optional[MemoryEngine] = None,
    hazard_module: Optional[HazardModule] = None,
    media_hub: Optional[MediaHub] = None,
    per_agent_depth: bool = False,
    year_mapping: Optional[YearMapping] = None,
    game_master: Optional[Any] = None,
    message_pool: Optional[Any] = None,
    reflection_engine: Optional[ReflectionEngine] = None,  # NEW
):
    # ... existing init code ...
    self.reflection_engine = reflection_engine  # NEW: add after self._memory_bridge line
```

**Change 3:** Add `_run_ma_reflection()` method to `MultiAgentHooks`:

```python
def _run_ma_reflection(self, year: int, agents: Dict[str, Any], llm_invoke_fn=None):
    """Run personalized batch reflection for all MA agent types.

    Groups agents by type, uses personalized batch prompts,
    and applies dynamic importance scoring.
    """
    if not self.reflection_engine or not self.memory_engine:
        return
    if not self.reflection_engine.should_reflect("any", year):
        return

    from broker.components.reflection_engine import AgentReflectionContext

    # Group agents by type
    type_groups: Dict[str, List] = {}
    for agent_id, agent in agents.items():
        if getattr(agent, "relocated", False):
            continue
        agent_type = getattr(agent, "agent_type", "household")
        if agent_type not in type_groups:
            type_groups[agent_type] = []

        # Retrieve memories (stratified if available)
        if hasattr(self.memory_engine, 'retrieve_stratified'):
            memories = self.memory_engine.retrieve_stratified(agent_id, total_k=10)
        else:
            memories = self.memory_engine.retrieve(agent, top_k=10)

        if memories:
            ctx = ReflectionEngine.extract_agent_context(agent, year)
            type_groups[agent_type].append({
                "agent_id": agent_id,
                "memories": memories,
                "context": ctx,
                "agent": agent,
            })

    # Process each type separately (different LLM call per type)
    batch_size = 10
    total_stored = 0

    for agent_type, candidates in type_groups.items():
        if not candidates:
            continue

        logger.info(f"[Reflection:MA] Processing {len(candidates)} {agent_type} agents...")

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i+batch_size]
            batch_ids = [c["agent_id"] for c in batch]

            # Personalized batch prompt
            if hasattr(self.reflection_engine, 'generate_personalized_batch_prompt'):
                prompt = self.reflection_engine.generate_personalized_batch_prompt(batch, year)
            else:
                prompt = self.reflection_engine.generate_batch_reflection_prompt(batch, year)

            try:
                if llm_invoke_fn:
                    raw_res = llm_invoke_fn(prompt)
                elif self.reflection_engine.llm_client:
                    raw_res = self.reflection_engine._call_llm(prompt)
                else:
                    continue

                response_text = raw_res[0] if isinstance(raw_res, tuple) else raw_res
                insights = self.reflection_engine.parse_batch_reflection_response(
                    response_text, batch_ids, year
                )

                for agent_id, insight in insights.items():
                    if insight:
                        # Dynamic importance
                        ctx_item = next((c for c in batch if c["agent_id"] == agent_id), None)
                        if ctx_item and hasattr(self.reflection_engine, 'compute_dynamic_importance'):
                            insight.importance = self.reflection_engine.compute_dynamic_importance(
                                ctx_item["context"]
                            )

                        self.reflection_engine.store_insight(agent_id, insight)
                        self.memory_engine.add_memory(
                            agent_id,
                            f"Consolidated Reflection: {insight.summary}",
                            {"significance": insight.importance, "emotion": "major",
                             "source": "personal", "type": "reflection"}
                        )
                        total_stored += 1

            except Exception as e:
                logger.error(f"[Reflection:MA:Error] {agent_type} batch {i//batch_size+1}: {e}")

    logger.info(f"[Reflection:MA] Year {year} complete. {total_stored} insights stored.")
```

**Change 4:** Call `_run_ma_reflection()` at end of existing `post_year()` method:

```python
# At the very end of post_year(), after all existing logic, add:
self._run_ma_reflection(year, agents)
```

**Note:** The `logger` variable is already available via `from broker.utils.logging import setup_logger` — check if this import exists; if not, add `from broker.utils.logging import setup_logger` and `logger = setup_logger(__name__)` at module level.

---

## Verification

### 1. Add test file

**File**: `tests/test_ma_reflection.py`

```python
"""Tests for MA reflection integration (Task-057D)."""
import pytest
from unittest.mock import MagicMock, patch
from examples.multi_agent.orchestration.lifecycle_hooks import MultiAgentHooks


@pytest.fixture
def mock_memory_engine():
    engine = MagicMock()
    engine.retrieve_stratified = MagicMock(return_value=["Memory 1", "Memory 2"])
    engine.retrieve = MagicMock(return_value=["Memory 1", "Memory 2"])
    engine.add_memory = MagicMock()
    return engine


@pytest.fixture
def mock_reflection_engine():
    from broker.components.reflection_engine import ReflectionEngine, ReflectionInsight
    engine = MagicMock(spec=ReflectionEngine)
    engine.should_reflect = MagicMock(return_value=True)
    engine.llm_client = MagicMock(return_value="response")
    engine.generate_personalized_batch_prompt = MagicMock(return_value="prompt")
    engine.parse_batch_reflection_response = MagicMock(return_value={
        "H_001": ReflectionInsight(summary="Learned to be cautious", importance=0.8, year_created=3),
    })
    engine.store_insight = MagicMock()
    engine.extract_agent_context = ReflectionEngine.extract_agent_context
    engine.compute_dynamic_importance = MagicMock(return_value=0.85)
    engine._call_llm = MagicMock(return_value="response")
    return engine


@pytest.fixture
def hooks(mock_memory_engine, mock_reflection_engine):
    env = {"year": 3}
    return MultiAgentHooks(
        environment=env,
        memory_engine=mock_memory_engine,
        reflection_engine=mock_reflection_engine,
    )


class TestMAReflection:
    def test_reflection_groups_by_type(self, hooks, mock_reflection_engine):
        agents = {
            "H_001": MagicMock(id="H_001", agent_type="household", relocated=False,
                               elevated=True, insured=False, flood_history=[True],
                               mg_status=False, last_decision="buy_insurance", name="", custom_traits={}),
            "GOV_001": MagicMock(id="GOV_001", agent_type="government", relocated=False,
                                  elevated=False, insured=False, flood_history=[],
                                  mg_status=False, last_decision="", name="", custom_traits={}),
        }
        hooks._run_ma_reflection(3, agents)

        # Should have called parse at least once
        assert mock_reflection_engine.parse_batch_reflection_response.called

    def test_no_reflection_engine_noop(self, mock_memory_engine):
        hooks = MultiAgentHooks(environment={"year": 1}, memory_engine=mock_memory_engine)
        # Should not raise
        hooks._run_ma_reflection(1, {"H_001": MagicMock()})

    def test_skips_relocated_agents(self, hooks, mock_memory_engine):
        agents = {
            "H_001": MagicMock(id="H_001", agent_type="household", relocated=True),
        }
        hooks._run_ma_reflection(3, agents)
        mock_memory_engine.retrieve_stratified.assert_not_called()
```

### 2. Run tests

```bash
pytest tests/test_ma_reflection.py -v
pytest tests/integration/test_ma_memory_social.py -v
```

All tests must pass. No regressions.

---

## DO NOT

- Do NOT modify `pre_year()`, `post_step()`, or existing `post_year()` logic
- Do NOT modify `broker/components/reflection_engine.py` (Codex's task)
- Do NOT modify `broker/components/memory_engine.py` or `humancentric_engine.py`
- Do NOT change `MemoryBridge` integration (Task-056) — keep it separate
- Keep ALL new `__init__` parameters Optional with `None` default (backward compatible)
