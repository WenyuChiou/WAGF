import pytest
from unittest.mock import MagicMock
from broker.components.memory_engine import HierarchicalMemoryEngine
from broker.components.skill_retriever import SkillRetriever
from broker.components.skill_registry import SkillRegistry
from broker.components.context_builder import BaseAgentContextBuilder
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import SkillDefinition
from cognitive_governance.agents import BaseAgent, AgentConfig

def test_v3_2_full_integration():
    # 1. Setup Components
    memory_engine = HierarchicalMemoryEngine(window_size=1, semantic_top_k=1)
    retriever = SkillRetriever(top_n=2)
    registry = SkillRegistry()
    
    # Skills
    s1 = SkillDefinition("buy_insurance", "Focus on insurance and savings.", ["*"], [], {}, [], "")
    s2 = SkillDefinition("elevate_house", "Raise house to avoid flood.", ["*"], [], {}, [], "")
    s_dn = SkillDefinition("do_nothing", "Take no action.", ["*"], [], {}, [], "")
    
    registry.register(s1)
    registry.register(s2)
    registry.register(s_dn)
    
    # Agent
    config = AgentConfig(name="Agent1", agent_type="household", state_params=[], objectives=[], constraints=[], skills=["buy_insurance", "elevate_house", "do_nothing"])
    agent = BaseAgent(config)
    agent.fixed_attributes = {"income_level": "High", "tract_id": "T123"}
    agent._id = "Agent1"
    
    # 2. Add some episodic memory
    memory_engine.add_memory("Agent1", "I observed a small flood.")
    memory_engine.add_memory("Agent1", "My neighbor bought insurance.", metadata={"importance": 0.9})
    memory_engine.add_memory("Agent1", "Latest news shows rising sea levels.")
    
    # 3. Context Builder
    # BaseAgentContextBuilder needs agents and memory_engine
    cb = BaseAgentContextBuilder(
        agents={"Agent1": agent},
        memory_engine=memory_engine,
        prompt_templates={"household": "CORE:{memory}\nSKILLS:{skills}"}
    )
    
    # 4. Engine
    engine = SkillBrokerEngine(
        skill_registry=registry,
        model_adapter=MagicMock(),
        validators=[],
        simulation_engine=MagicMock(),
        context_builder=cb,
        skill_retriever=retriever
    )
    
    # 5. Process Step
    # We want to see if retrieval picks 'buy_insurance' because context has 'insurance' in memory
    llm = MagicMock(return_value="<decision>{'strategy': 'test', 'confidence': 0.8, 'decision': 'do_nothing'}</decision>")
    
    # Mocking context keywords for retrieval test
    # Memory has 'insurance', so 'buy_insurance' should be retrieved
    res = engine.process_step("Agent1", 1, "run1", 42, llm, agent_type="household")
    
    # 6. Verify Context Formatting
    # Get the last prompt sent to LLM
    prompt = llm.call_args[0][0]
    
    # Verify Core Memory
    assert "CORE: income_level=High tract_id=T123" in prompt
    # Verify Semantic Memory (neighbor bought insurance was importance 0.9)
    assert "HISTORIC:" in prompt
    assert "My neighbor bought insurance." in prompt
    # Verify Episodic Memory (Recent)
    assert "RECENT:" in prompt
    assert "Latest news shows rising sea levels." in prompt
    
    # Verify RAG Skill Retrieval
    # 'buy_insurance' should be there because 'neighbor bought insurance' is in memory
    assert "buy_insurance: Focus on insurance and savings." in prompt
    # 'do_nothing' should be there as fallback
    assert "do_nothing: Take no action." in prompt
    # 'elevate_house' should be missing if top_n=2
    assert "elevate_house" not in prompt

if __name__ == "__main__":
    test_v3_2_full_integration()
