"""Tests for personalized reflection prompts (Task-057A)."""
import pytest
from unittest.mock import MagicMock

from broker.components.reflection_engine import (
    ReflectionEngine,
    AgentReflectionContext,
    REFLECTION_QUESTIONS,
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
            agent_id="H_005",
            agent_type="household",
            elevated=True,
            insured=True,
            flood_count=3,
            mg_status=False,
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
        assert (
            "vulnerable" in prompt.lower()
            or "equity" in prompt.lower()
            or "subsidy" in prompt.lower()
        )

    def test_empty_memories_returns_empty(self, engine):
        ctx = AgentReflectionContext(agent_id="H_001")
        prompt = engine.generate_personalized_reflection_prompt(ctx, [], 1)
        assert prompt == ""


class TestPersonalizedBatchPrompt:
    def test_batch_includes_identity_tags(self, engine):
        batch = [
            {
                "agent_id": "H_001",
                "memories": ["Flooded"],
                "context": AgentReflectionContext(
                    agent_id="H_001",
                    agent_type="household",
                    elevated=True,
                    flood_count=2,
                ),
            },
            {
                "agent_id": "H_002",
                "memories": ["Safe year"],
                "context": AgentReflectionContext(
                    agent_id="H_002",
                    agent_type="household",
                    mg_status=True,
                ),
            },
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
