# Task-057A: Personalized Reflection Prompt (Codex Assignment)

**Assigned To**: Codex
**Status**: READY
**Priority**: High
**Estimated Scope**: ~120 lines new, 1 file + 1 test file
**Depends On**: None (Phase 1 — can run in parallel with 057-B)

---

## Objective

Add agent identity context to reflection prompts so that different agent types (household, government, insurance) and individual agent states (elevated, insured, flood history) produce differentiated reflection outputs.

Currently `generate_reflection_prompt()` and `generate_batch_reflection_prompt()` produce identical prompts for all agents — no name, no type, no state. This causes all reflection insights to be homogeneous.

---

## Context

### Current Code (`broker/components/reflection_engine.py`)

Line 78-106: `generate_reflection_prompt()` — generic prompt with no agent identity:
```python
return f"""You are reflecting on your experiences from the past {self.reflection_interval} year(s).
**Your Recent Memories:**
{memories_text}
**Task:** Summarize the key lessons you have learned...
"""
```

Line 201-226: `generate_batch_reflection_prompt()` — batch mode, also no identity:
```python
lines.append(f"{agent_id} Memories: {mem_text}")
```

### Problem

All 100 agents get the same prompt template with no identity differentiation. The LLM produces nearly identical reflections.

---

## Changes Required

### File: `broker/components/reflection_engine.py`

**Change 1:** Add `AgentReflectionContext` dataclass (after `ReflectionInsight`, ~line 31):

```python
@dataclass
class AgentReflectionContext:
    """Agent identity context for personalized reflection prompts."""
    agent_id: str
    agent_type: str = "household"          # household | government | insurance
    name: str = ""                         # Display name if available
    elevated: bool = False
    insured: bool = False
    flood_count: int = 0                   # Number of floods experienced
    years_in_sim: int = 0                  # Agent age in simulation
    mg_status: bool = False                # Marginalized group
    recent_decision: str = ""              # Last skill chosen
    custom_traits: Dict[str, Any] = field(default_factory=dict)
```

**Change 2:** Add per-type reflection question bank (module-level, after the dataclass):

```python
REFLECTION_QUESTIONS: Dict[str, List[str]] = {
    "household": [
        "What risks feel most urgent to your family right now?",
        "Have your neighbors' choices influenced your thinking?",
        "What trade-offs have you faced between cost and safety?",
    ],
    "government": [
        "Which communities are most vulnerable right now?",
        "Are current subsidy and grant programs reaching those who need them?",
        "What policy adjustments would improve equity outcomes?",
    ],
    "insurance": [
        "Which risk segments are underpriced or overpriced?",
        "How has the claims pattern changed over time?",
        "What adjustments to premium models are needed?",
    ],
}
```

**Change 3:** Add `extract_agent_context()` static method to `ReflectionEngine`:

```python
@staticmethod
def extract_agent_context(agent, year: int = 0) -> AgentReflectionContext:
    """Extract reflection context from an agent object."""
    return AgentReflectionContext(
        agent_id=getattr(agent, 'id', str(agent)),
        agent_type=getattr(agent, 'agent_type', 'household'),
        name=getattr(agent, 'name', ''),
        elevated=getattr(agent, 'elevated', False),
        insured=getattr(agent, 'insured', False),
        flood_count=sum(1 for f in getattr(agent, 'flood_history', []) if f),
        years_in_sim=year,
        mg_status=getattr(agent, 'mg_status', False),
        recent_decision=getattr(agent, 'last_decision', ''),
        custom_traits=getattr(agent, 'custom_traits', {}),
    )
```

**Change 4:** Add `generate_personalized_reflection_prompt()` method to `ReflectionEngine`:

```python
def generate_personalized_reflection_prompt(
    self,
    context: AgentReflectionContext,
    memories: List[str],
    current_year: int
) -> str:
    """Generate a personalized reflection prompt with agent identity."""
    if not memories:
        return ""

    memories_text = "\n".join([f"- {m}" for m in memories])

    # Identity block
    identity_lines = [f"You are {context.agent_id}"]
    if context.name:
        identity_lines[0] += f" ({context.name})"
    identity_lines[0] += f", a {context.agent_type} agent in Year {current_year}."

    if context.agent_type == "household":
        status_parts = []
        if context.elevated:
            status_parts.append("your house is elevated")
        if context.insured:
            status_parts.append("you have flood insurance")
        if context.flood_count > 0:
            status_parts.append(f"you've been flooded {context.flood_count} time(s)")
        if context.mg_status:
            status_parts.append("you have limited resources")
        if status_parts:
            identity_lines.append(f"Current status: {', '.join(status_parts)}.")

    identity_block = "\n".join(identity_lines)

    # Questions (type-specific)
    questions = REFLECTION_QUESTIONS.get(context.agent_type, REFLECTION_QUESTIONS["household"])
    q_text = "\n".join([f"- {q}" for q in questions])

    return f"""{identity_block}

**Your Recent Memories:**
{memories_text}

**Reflection Questions:**
{q_text}

**Task:** Based on your experiences and situation, provide a 2-3 sentence personal reflection capturing what you've learned and how it will shape your future decisions. Speak in first person.
"""
```

**Change 5:** Add `generate_personalized_batch_prompt()` method to `ReflectionEngine`:

```python
def generate_personalized_batch_prompt(
    self,
    batch_data: List[Dict[str, Any]],
    current_year: int
) -> str:
    """Generate batch prompt with per-agent identity context."""
    if not batch_data:
        return ""

    lines = [f"### Background\nYou are a Reflection Assistant for {len(batch_data)} agents in Year {current_year}."]
    lines.append("Instructions: Provide a personalized 2-sentence reflection for each agent based on their unique situation and memories.\n")

    lines.append("### Agent Data")
    for item in batch_data:
        agent_id = item.get("agent_id", "Unknown")
        ctx = item.get("context")  # AgentReflectionContext or None
        memories = item.get("memories", [])
        mem_text = " ".join(memories) if memories else "(No memories)"

        # Identity line
        if ctx:
            identity = f"[{ctx.agent_type}"
            traits = []
            if getattr(ctx, 'elevated', False):
                traits.append("elevated")
            if getattr(ctx, 'insured', False):
                traits.append("insured")
            if getattr(ctx, 'flood_count', 0) > 0:
                traits.append(f"flooded {ctx.flood_count}x")
            if getattr(ctx, 'mg_status', False):
                traits.append("MG")
            if traits:
                identity += f", {', '.join(traits)}"
            identity += "]"
        else:
            identity = "[household]"

        lines.append(f"{agent_id} {identity} Memories: {mem_text}")

    lines.append("\n### Output Requirement")
    lines.append("Return ONLY a JSON object mapping Agent IDs to personalized reflection strings. Each reflection should reference the agent's specific situation. No filler.")

    return "\n".join(lines)
```

---

## Verification

### 1. Add test file

**File**: `tests/test_reflection_personalization.py`

```python
"""Tests for personalized reflection prompts (Task-057A)."""
import pytest
from unittest.mock import MagicMock
from broker.components.reflection_engine import (
    ReflectionEngine, AgentReflectionContext, REFLECTION_QUESTIONS
)


@pytest.fixture
def engine():
    return ReflectionEngine()


class TestAgentReflectionContext:
    def test_extract_from_agent(self, engine):
        agent = MagicMock()
        agent.id = "H_001"
        agent.agent_type = "household"
        agent.name = "Chen"
        agent.elevated = True
        agent.insured = False
        agent.flood_history = [True, False, True]
        agent.mg_status = False
        agent.last_decision = "buy_insurance"
        agent.custom_traits = {}

        ctx = ReflectionEngine.extract_agent_context(agent, year=5)
        assert ctx.agent_id == "H_001"
        assert ctx.agent_type == "household"
        assert ctx.elevated is True
        assert ctx.flood_count == 2
        assert ctx.years_in_sim == 5

    def test_extract_missing_attrs_defaults(self, engine):
        agent = MagicMock(spec=[])
        agent.id = "X_001"
        ctx = ReflectionEngine.extract_agent_context(agent, year=1)
        assert ctx.agent_type == "household"
        assert ctx.flood_count == 0


class TestPersonalizedPrompt:
    def test_household_prompt_contains_identity(self, engine):
        ctx = AgentReflectionContext(
            agent_id="H_005", agent_type="household",
            elevated=True, insured=True, flood_count=3, mg_status=False
        )
        prompt = engine.generate_personalized_reflection_prompt(
            ctx, ["Year 3: Got flooded", "Year 4: Bought insurance"], 5
        )
        assert "H_005" in prompt
        assert "household" in prompt
        assert "elevated" in prompt
        assert "flood insurance" in prompt
        assert "flooded 3 time" in prompt

    def test_government_prompt_has_government_questions(self, engine):
        ctx = AgentReflectionContext(agent_id="GOV_1", agent_type="government")
        prompt = engine.generate_personalized_reflection_prompt(
            ctx, ["Year 5: Distributed grants"], 5
        )
        assert "vulnerable" in prompt.lower() or "equity" in prompt.lower() or "subsidy" in prompt.lower()

    def test_empty_memories_returns_empty(self, engine):
        ctx = AgentReflectionContext(agent_id="H_001")
        prompt = engine.generate_personalized_reflection_prompt(ctx, [], 1)
        assert prompt == ""


class TestPersonalizedBatchPrompt:
    def test_batch_includes_identity_tags(self, engine):
        batch = [
            {"agent_id": "H_001", "memories": ["Flooded"], "context": AgentReflectionContext(
                agent_id="H_001", agent_type="household", elevated=True, flood_count=2)},
            {"agent_id": "H_002", "memories": ["Safe year"], "context": AgentReflectionContext(
                agent_id="H_002", agent_type="household", mg_status=True)},
        ]
        prompt = engine.generate_personalized_batch_prompt(batch, 5)
        assert "H_001 [household, elevated, flooded 2x]" in prompt
        assert "H_002 [household, MG]" in prompt

    def test_batch_no_context_fallback(self, engine):
        batch = [{"agent_id": "H_003", "memories": ["A memory"], "context": None}]
        prompt = engine.generate_personalized_batch_prompt(batch, 3)
        assert "[household]" in prompt


class TestReflectionQuestions:
    def test_all_types_have_questions(self):
        for t in ["household", "government", "insurance"]:
            assert t in REFLECTION_QUESTIONS
            assert len(REFLECTION_QUESTIONS[t]) >= 2
```

### 2. Run tests

```bash
pytest tests/test_reflection_personalization.py -v
pytest tests/test_reflection_engine_v2.py -v
```

All tests must pass.

---

## DO NOT

- Do NOT modify `generate_reflection_prompt()` or `generate_batch_reflection_prompt()` — keep as-is for backward compatibility
- Do NOT modify `_create_insight()` or `parse_batch_reflection_response()`
- Do NOT touch any file other than `broker/components/reflection_engine.py` and `tests/test_reflection_personalization.py`
- Do NOT change the `ReflectionInsight` dataclass
