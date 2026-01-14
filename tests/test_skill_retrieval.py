import pytest
from broker.components.skill_retriever import SkillRetriever
from broker.interfaces.skill_types import SkillDefinition

def test_retrieval_logic():
    retriever = SkillRetriever(top_n=2)
    
    skills = [
        SkillDefinition(
            skill_id="buy_insurance",
            description="Protect against flood damage costs.",
            eligible_agent_types=["*"],
            preconditions=[],
            institutional_constraints={},
            allowed_state_changes=["has_insurance"],
            implementation_mapping=""
        ),
        SkillDefinition(
            skill_id="elevate_house",
            description="Raise your home above water level.",
            eligible_agent_types=["*"],
            preconditions=[],
            institutional_constraints={},
            allowed_state_changes=["elevated"],
            implementation_mapping=""
        ),
        SkillDefinition(
            skill_id="invest_stocks",
            description="Buy financial shares for long term growth and wealth savings.",
            eligible_agent_types=["*"],
            preconditions=[],
            institutional_constraints={},
            allowed_state_changes=["wealth"],
            implementation_mapping=""
        ),
        SkillDefinition(
            skill_id="do_nothing",
            description="Take no action this year.",
            eligible_agent_types=["*"],
            preconditions=[],
            institutional_constraints={},
            allowed_state_changes=[],
            implementation_mapping=""
        )
    ]
    
    # Context 1: Flooding threat
    context_flood = {
        "perception": {"flood_intensity": 0.8},
        "state": {"has_insurance": False}
    }
    
    retrieved = retriever.retrieve(context_flood, skills)
    ids = [s.skill_id for s in retrieved]
    
    assert "buy_insurance" in ids
    assert "do_nothing" in ids # Fallback safety
    assert "invest_stocks" not in ids # Should be lower ranked
    
    # Context 2: Financial/Wealth focus
    context_wealth = {
        "state": {"wealth": 0.9, "savings": 0.8},
        "perception": {"flood_intensity": 0.0}
    }
    
    retrieved_wealth = retriever.retrieve(context_wealth, skills)
    ids_wealth = [s.skill_id for s in retrieved_wealth]
    
    assert "invest_stocks" in ids_wealth
    assert "do_nothing" in ids_wealth

def test_skill_broker_integration():
    # Mock dependencies manually or use simple objects
    from unittest.mock import MagicMock
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.components.skill_registry import SkillRegistry
    
    registry = SkillRegistry()
    s_def = SkillDefinition("s1", "description", ["*"], [], {}, [], "")
    s_def = SkillDefinition("s1", "This is an important skill", ["*"], [], {}, [], "")
    registry.register(s_def)
    
    retriever = SkillRetriever(top_n=1)
    
    # Mock ContextBuilder
    cb = MagicMock()
    # Align context keyword 'important' with skill description
    cb.build.return_value = {
        "available_skills": ["s1", "do_nothing"],
        "state": {"important": 1.0}
    }
    
    engine = SkillBrokerEngine(
        skill_registry=registry,
        model_adapter=MagicMock(),
        validators=[],
        simulation_engine=MagicMock(),
        context_builder=cb,
        skill_retriever=retriever
    )
    
    # Mock llm_invoke
    llm = MagicMock(return_value="<decision>{'decision': 's1'}</decision>")
    
    engine.process_step("a1", 1, "r1", 42, llm)
    
    # Verify CB.format_prompt was called with retrieved skills
    cb.format_prompt.assert_called()
    call_args = cb.format_prompt.call_args[0][0]
    # 's1' should be there because 'important' matched the description
    assert "s1" in call_args["available_skills"]
    assert "retrieved_skill_definitions" in call_args
