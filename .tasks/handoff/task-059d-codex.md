# Task-059D: Reflection Triggers per Agent Type (Codex Assignment)

**Assigned To**: Codex
**Status**: COMPLETED
**Priority**: High
**Estimated Scope**: ~80 lines new in reflection_engine.py, ~20 lines in lifecycle_hooks.py, 1 test file
**Depends On**: None (Phase 1 ??can run in parallel with 059-B, 059-C)
**Branch**: `feat/memory-embedding-retrieval`

---

## Objective

Add a literature-backed trigger system to `ReflectionEngine` so that reflection is not just periodic but also event-driven. Currently, reflection only fires for household agents at year-end via `should_reflect()`. This task adds 4 trigger types and extends reflection to government and insurance agents.

**Literature Basis**:
- Park et al. (2023): Importance-threshold trigger (~2-3x per simulated day)
- Shinn et al. (2023, Reflexion): Event-triggered reflection after failures
- MAR (2024): Multi-critic debate for cross-agent reflection
- Toy & MacAdam (2024, Metacognition): System 1/2 metacognitive reflection

**SA Compatibility**: The existing `should_reflect(agent_id, current_year)` method is NOT modified. New trigger logic is additive. SA experiments calling `should_reflect()` directly will work unchanged.

---

## Context

### Current Code: `broker/components/reflection_engine.py`

Line 76-119: `ReflectionEngine.__init__()` and `should_reflect()`:
```python
def should_reflect(self, agent_id: str, current_year: int) -> bool:
    """Check if it's time for an agent to perform reflection."""
    if self.reflection_interval <= 0:
        return False
    return current_year > 0 and current_year % self.reflection_interval == 0
```

This is purely periodic ??no awareness of events, agent type, or environment.

Line 48-63: `REFLECTION_QUESTIONS` already has per-type questions for `household`, `government`, `insurance`.

Line 167-211: `generate_personalized_reflection_prompt()` already works for all agent types.

### Current Code: `examples/multi_agent/orchestration/lifecycle_hooks.py`

`_run_ma_reflection()` only triggers for household agents:
```python
for agent in agents:
    if agent.agent_type in ("household_owner", "household_renter"):
        # ... reflection logic
```

Government and insurance agents never reflect.

### Problem

1. Reflection is only periodic, not event-driven
2. Only household agents reflect ??government/insurance never do
3. No way to configure triggers per agent type in YAML

---

## Changes Required

### File: `broker/components/reflection_engine.py`

**Change 1:** Add `ReflectionTrigger` enum and `ReflectionConfig` dataclass (after `IMPORTANCE_PROFILES`, ~line 73):

```python
from enum import Enum


class ReflectionTrigger(Enum):
    """Types of events that can trigger reflection.

    Literature mapping:
    - CRISIS: Park et al. (2023) ??importance sum exceeds threshold
    - PERIODIC: Park et al. (2023) ??regular interval reflection
    - DECISION: Shinn et al. (2023, Reflexion) ??after significant actions
    - INSTITUTIONAL: MAR (2024) ??cross-agent policy reflection
    """
    CRISIS = "crisis"           # After flood event (all affected agents)
    PERIODIC = "periodic"       # Every N years (configurable)
    DECISION = "decision"       # After major irreversible action
    INSTITUTIONAL = "institutional"  # After policy change > threshold


@dataclass
class ReflectionTriggerConfig:
    """Configuration for reflection triggers.

    Loaded from YAML global_config.reflection.triggers.
    """
    crisis: bool = True                    # Reflect after flood events
    periodic_interval: int = 5             # Reflect every N years
    decision_types: List[str] = field(     # Reflect after these skills
        default_factory=lambda: ["elevate_house", "buyout_program", "relocate"]
    )
    institutional_threshold: float = 0.05  # Policy change > 5% triggers reflection
    method: str = "hybrid"                 # "llm", "template", or "hybrid"
    batch_size: int = 10
    importance_boost: float = 0.85
```

**Change 2:** Add `should_reflect_triggered()` method to `ReflectionEngine` (after existing `should_reflect()`, ~line 119):

```python
    def should_reflect_triggered(
        self,
        agent_id: str,
        agent_type: str,
        current_year: int,
        trigger: ReflectionTrigger,
        trigger_config: Optional[ReflectionTriggerConfig] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if reflection should fire based on trigger type and agent type.

        This extends should_reflect() with event-driven triggers.
        The original should_reflect() is preserved for backward compatibility.

        Args:
            agent_id: Agent identifier
            agent_type: One of "household", "government", "insurance" (or subtypes)
            current_year: Current simulation year
            trigger: The trigger event type
            trigger_config: Configuration for triggers (from YAML)
            context: Optional context with event details

        Returns:
            True if reflection should proceed
        """
        if trigger_config is None:
            trigger_config = ReflectionTriggerConfig()

        context = context or {}

        if trigger == ReflectionTrigger.CRISIS:
            if not trigger_config.crisis:
                return False
            # All agent types reflect after crisis events
            return True

        elif trigger == ReflectionTrigger.PERIODIC:
            interval = trigger_config.periodic_interval
            if interval <= 0:
                return False
            return current_year > 0 and current_year % interval == 0

        elif trigger == ReflectionTrigger.DECISION:
            # Only the acting agent reflects after their decision
            decision = context.get("decision", "")
            return decision in trigger_config.decision_types

        elif trigger == ReflectionTrigger.INSTITUTIONAL:
            # Government and insurance agents reflect on policy changes
            if agent_type not in ("government", "insurance"):
                return False
            policy_change = abs(context.get("policy_change_magnitude", 0.0))
            return policy_change > trigger_config.institutional_threshold

        return False
```

**Change 3:** Add `load_trigger_config()` class method (after `should_reflect_triggered()`):

```python
    @staticmethod
    def load_trigger_config(config_dict: Optional[Dict[str, Any]] = None) -> ReflectionTriggerConfig:
        """Load ReflectionTriggerConfig from a dict (typically from YAML).

        Args:
            config_dict: Dict with trigger settings. Keys match ReflectionTriggerConfig fields.
                         If None, returns defaults.

        Returns:
            ReflectionTriggerConfig instance
        """
        if not config_dict:
            return ReflectionTriggerConfig()

        triggers = config_dict.get("triggers", config_dict)
        return ReflectionTriggerConfig(
            crisis=triggers.get("crisis", True),
            periodic_interval=triggers.get("periodic_interval", 5),
            decision_types=triggers.get("decision_types", ["elevate_house", "buyout_program", "relocate"]),
            institutional_threshold=triggers.get("institutional_threshold", 0.05),
            method=config_dict.get("method", "hybrid"),
            batch_size=config_dict.get("batch_size", 10),
            importance_boost=config_dict.get("importance_boost", 0.85),
        )
```

---

## Domain Wiring (Phase 3)

### File: `examples/multi_agent/ma_agent_types.yaml`

**Change 4:** Add reflection trigger config under `global_config` (after existing `global_config.reflection` or create if missing):

```yaml
global_config:
  reflection:
    interval: 1
    batch_size: 10
    importance_boost: 0.85
    triggers:
      crisis: true
      periodic_interval: 5
      decision_types:
        - elevate_house
        - buyout_program
        - relocate
      institutional_threshold: 0.05
    method: hybrid
```

### File: `examples/multi_agent/orchestration/lifecycle_hooks.py`

**Change 5:** In `_run_ma_reflection()`, extend to handle government and insurance agents after household reflection. This is a MINIMAL change ??add a block after the existing household loop:

Find the section that iterates over agents for reflection (the loop that checks `agent.agent_type in ("household_owner", "household_renter")`). After that loop, add:

```python
        # Government/Insurance reflection (institutional trigger)
        from broker.components.reflection_engine import ReflectionTrigger
        for agent in agents:
            if getattr(agent, 'agent_type', '') in ("government", "insurance"):
                base_type = "government" if "government" in agent.agent_type else "insurance"
                memories = memory_engine.retrieve(agent, top_k=5) if hasattr(memory_engine, 'retrieve') else []
                if memories:
                    context = ReflectionEngine.extract_agent_context(agent, year)
                    prompt = reflection_engine.generate_personalized_reflection_prompt(
                        context, memories, year
                    )
                    # Use synthetic reflection (same as household)
                    insight = reflection_engine.parse_reflection_response(
                        f"As a {base_type} agent, I observe: " + "; ".join(memories[:2]),
                        len(memories),
                        year,
                    )
                    if insight:
                        reflection_engine.store_insight(str(agent.unique_id), insight)
                        memory_engine.add_memory(
                            str(agent.unique_id),
                            f"[Reflection Y{year}] {insight.summary}",
                            {"importance": insight.importance, "type": "reflection", "source": "reflection"},
                        )
```

---

## Verification

### 1. Add test file

**File**: `tests/test_reflection_triggers.py`

```python
"""Tests for ReflectionTrigger system (Task-059D)."""
import pytest

from broker.components.reflection_engine import (
    ReflectionEngine,
    ReflectionTrigger,
    ReflectionTriggerConfig,
)


class TestReflectionTriggerEnum:
    """Verify trigger types exist."""

    def test_crisis_trigger(self):
        assert ReflectionTrigger.CRISIS.value == "crisis"

    def test_periodic_trigger(self):
        assert ReflectionTrigger.PERIODIC.value == "periodic"

    def test_decision_trigger(self):
        assert ReflectionTrigger.DECISION.value == "decision"

    def test_institutional_trigger(self):
        assert ReflectionTrigger.INSTITUTIONAL.value == "institutional"


class TestReflectionTriggerConfig:
    """Verify config defaults and loading."""

    def test_default_config(self):
        cfg = ReflectionTriggerConfig()
        assert cfg.crisis is True
        assert cfg.periodic_interval == 5
        assert "elevate_house" in cfg.decision_types
        assert cfg.institutional_threshold == 0.05

    def test_load_from_dict(self):
        d = {
            "triggers": {
                "crisis": False,
                "periodic_interval": 3,
                "decision_types": ["relocate"],
                "institutional_threshold": 0.10,
            },
            "method": "llm",
            "batch_size": 5,
        }
        cfg = ReflectionEngine.load_trigger_config(d)
        assert cfg.crisis is False
        assert cfg.periodic_interval == 3
        assert cfg.decision_types == ["relocate"]
        assert cfg.method == "llm"

    def test_load_none_returns_defaults(self):
        cfg = ReflectionEngine.load_trigger_config(None)
        assert cfg.crisis is True
        assert cfg.periodic_interval == 5


class TestShouldReflectTriggered:
    """Verify trigger logic per agent type."""

    def setup_method(self):
        self.engine = ReflectionEngine()
        self.config = ReflectionTriggerConfig()

    def test_crisis_trigger_all_types(self):
        """Crisis trigger fires for all agent types."""
        for atype in ["household", "government", "insurance"]:
            assert self.engine.should_reflect_triggered(
                "a1", atype, 3, ReflectionTrigger.CRISIS, self.config
            )

    def test_crisis_disabled(self):
        cfg = ReflectionTriggerConfig(crisis=False)
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.CRISIS, cfg
        )

    def test_periodic_trigger(self):
        cfg = ReflectionTriggerConfig(periodic_interval=5)
        assert self.engine.should_reflect_triggered(
            "a1", "household", 5, ReflectionTrigger.PERIODIC, cfg
        )
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.PERIODIC, cfg
        )
        assert self.engine.should_reflect_triggered(
            "a1", "household", 10, ReflectionTrigger.PERIODIC, cfg
        )

    def test_periodic_year_zero(self):
        """Year 0 should not trigger periodic reflection."""
        cfg = ReflectionTriggerConfig(periodic_interval=1)
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 0, ReflectionTrigger.PERIODIC, cfg
        )

    def test_decision_trigger(self):
        ctx = {"decision": "elevate_house"}
        assert self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.DECISION, self.config, ctx
        )

    def test_decision_trigger_not_listed(self):
        ctx = {"decision": "buy_insurance"}
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.DECISION, self.config, ctx
        )

    def test_institutional_trigger_government(self):
        ctx = {"policy_change_magnitude": 0.10}
        assert self.engine.should_reflect_triggered(
            "gov1", "government", 3, ReflectionTrigger.INSTITUTIONAL, self.config, ctx
        )

    def test_institutional_trigger_household_ignored(self):
        """Household agents don't respond to institutional triggers."""
        ctx = {"policy_change_magnitude": 0.50}
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.INSTITUTIONAL, self.config, ctx
        )

    def test_institutional_below_threshold(self):
        ctx = {"policy_change_magnitude": 0.01}
        assert not self.engine.should_reflect_triggered(
            "gov1", "government", 3, ReflectionTrigger.INSTITUTIONAL, self.config, ctx
        )


class TestBackwardCompatibility:
    """Verify existing should_reflect() is unchanged."""

    def test_legacy_should_reflect(self):
        engine = ReflectionEngine(reflection_interval=3)
        assert engine.should_reflect("a1", 3) is True
        assert engine.should_reflect("a1", 4) is False
        assert engine.should_reflect("a1", 6) is True

    def test_legacy_should_reflect_zero_interval(self):
        engine = ReflectionEngine(reflection_interval=0)
        assert engine.should_reflect("a1", 5) is False
```

### 2. Run tests

```bash
pytest tests/test_reflection_triggers.py -v
pytest tests/test_ma_reflection.py -v
pytest tests/test_broker_core.py -v
```

All tests must pass.

---

## Domain Wiring ??Location 2: `examples/governed_flood/` (SA flood case)

The governed_flood case currently uses ReflectionEngine via `run_experiment.py`. Add trigger config to its YAML:

**D6**: `examples/governed_flood/config/agent_types.yaml` ??Add reflection trigger config under `global_config.reflection`:

```yaml
global_config:
  reflection:
    interval: 1
    batch_size: 10
    importance_boost: 0.9
    triggers:
      crisis: true
      periodic_interval: 5
      decision_types:
        - elevate_house
        - relocate
      institutional_threshold: 0.05
    method: hybrid
```

**Note**: The governed_flood case has NO government/insurance agents, so `INSTITUTIONAL` trigger will not fire. Only `CRISIS`, `PERIODIC`, and `DECISION` triggers apply for household agents.

---

## DO NOT

- Do NOT modify the existing `should_reflect()` method ??it must keep its current signature and behavior
- Do NOT remove or rename any existing methods on ReflectionEngine
- Do NOT make `should_reflect_triggered()` replace `should_reflect()` ??they coexist
- Do NOT change the `REFLECTION_QUESTIONS` dict or `IMPORTANCE_PROFILES` dict
- Do NOT add LLM calls in the domain wiring change (Change 5) ??use synthetic reflection matching the existing pattern
- Do NOT touch `broker/components/engines/`

---

## Completion Notes

- **Commit**: 41514be (feat(reflection): add trigger-based reflection)
- **Files**:
  - roker/components/reflection_engine.py`n  - examples/multi_agent/orchestration/lifecycle_hooks.py`n  - examples/multi_agent/ma_agent_types.yaml`n  - examples/governed_flood/config/agent_types.yaml`n  - 	ests/test_reflection_triggers.py`n- **Tests**: Not run in this session

