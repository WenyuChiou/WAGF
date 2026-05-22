"""Tests for personalized reflection prompts (Task-057A)."""
import pytest
from unittest.mock import MagicMock

from broker.components.cognitive.reflection import (
    ReflectionEngine,
    AgentReflectionContext,
    _DEFAULT_REFLECTION_QUESTIONS,
)


@pytest.fixture
def engine():
    return ReflectionEngine()


@pytest.fixture(scope="session")
def flood_pack():
    """Ensure FloodDomainPack is registered so the reflection hooks
    resolve to flood behaviour (Phase 6H Item 9).

    No teardown: registration is a process-global import side effect.
    `import examples.governed_flood` fires `register()` once per process
    (sys.modules cache); clearing it on teardown would permanently
    unregister the pack for every later test, since the cached re-import
    cannot re-fire the registration."""
    import examples.governed_flood  # noqa: F401 — registers FloodDomainPack


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

    def test_government_prompt_uses_generic_fallback_without_yaml(self, engine):
        """Phase 6H Item 4: government reflection questions are no longer
        hardcoded per agent type. Without resolver-supplied questions the
        prompt carries the domain-neutral generic fallback — a domain
        author supplies government-specific questions via
        agent_types.yaml (government.reflection.questions)."""
        ctx = AgentReflectionContext(agent_id="GOV_1", agent_type="government")
        prompt = engine.generate_personalized_reflection_prompt(
            ctx, ["Year 5: Distributed grants"], 5
        )
        assert _DEFAULT_REFLECTION_QUESTIONS[0] in prompt

    def test_empty_memories_returns_empty(self, engine):
        ctx = AgentReflectionContext(agent_id="H_001")
        prompt = engine.generate_personalized_reflection_prompt(ctx, [], 1)
        assert prompt == ""


class TestPersonalizedBatchPrompt:
    def test_batch_includes_identity_tags(self, engine, flood_pack):
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
    """Phase 6H Item 4: the per-flood-agent-type hardcoded dict was
    replaced by a domain-neutral generic fallback; questions are now
    resolved per-domain via AgentTypeConfig.get_reflection_questions()."""

    def test_default_questions_nonempty_and_domain_neutral(self):
        assert len(_DEFAULT_REFLECTION_QUESTIONS) >= 2
        joined = " ".join(_DEFAULT_REFLECTION_QUESTIONS).lower()
        for flood_word in ("flood", "insurance", "premium", "elevat"):
            assert flood_word not in joined, (
                f"generic fallback must not carry domain wording: {flood_word!r}"
            )

    def test_individual_prompt_uses_passed_questions(self, engine):
        ctx = AgentReflectionContext(agent_id="A1", name="A1", agent_type="farmer")
        custom = ["Did your allocation match the inflow forecast?"]
        prompt = engine.generate_personalized_reflection_prompt(
            ctx, ["a memory"], 3, reflection_questions=custom
        )
        assert custom[0] in prompt

    def test_individual_prompt_falls_back_to_generic(self, engine):
        ctx = AgentReflectionContext(agent_id="A1", name="A1", agent_type="farmer")
        prompt = engine.generate_personalized_reflection_prompt(
            ctx, ["a memory"], 3
        )
        assert _DEFAULT_REFLECTION_QUESTIONS[0] in prompt
