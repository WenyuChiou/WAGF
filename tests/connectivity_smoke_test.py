
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add workspace to path
sys.path.append(str(Path(__file__).parent.parent))

from cognitive_governance.agents import BaseAgent, AgentConfig, StateParam
from broker.components.context_builder import TieredContextBuilder, AttributeProvider, SocialProvider
from broker.components.interaction_hub import InteractionHub
from broker.core.governed_broker import SkillBrokerEngine
from broker.utils.model_adapter import UnifiedAdapter
from broker.components.audit_writer import GenericAuditWriter, AuditConfig
from broker.validators.agent.agent_validator import AgentValidator
from broker.components.social_graph import GlobalGraph

def main():
    print("=== Module Connectivity Smoke Test ===")
    
    # 1. Setup Mock Data
    yaml_path = "examples/single_agent/agent_types.yaml"
    agent_id = "agent_01"
    config = AgentConfig(
        name=agent_id,
        agent_type="household",
        state_params=[
            StateParam(name="elevated", raw_range=(0, 1), initial_raw=0.0),
            StateParam(name="has_insurance", raw_range=(0, 1), initial_raw=0.0)
        ],
        objectives=[],
        constraints=[],
        skills=[]
    )
    agents = {
        agent_id: BaseAgent(config=config)
    }
    
    # 2. Setup Hub & Context Builder
    graph = GlobalGraph(agent_ids=[agent_id])
    hub = InteractionHub(graph=graph)
    ctx_builder = TieredContextBuilder(
        agents=agents,
        hub=hub,
        prompt_templates={"household": "State: {p_elevated} Perception: {flood_depth} Decide: {options_text}"}
    )
    
    # Verify Provider Pipeline
    ctx = ctx_builder.build("agent_01")
    print("\n[Context Builder] Connectivity Check:")
    print(f" - Agent Name: {ctx.get('personal', {}).get('name')}")
    print(f" - State Keys: {list(ctx.get('personal', {}).keys())}")
    assert "elevated" in ctx.get("personal", {}), "AttributeProvider failed to inject state"
    
    # 3. Setup Adapter & Broker
    from broker.components.skill_registry import SkillRegistry
    
    # Mock Simulation Engine
    from broker.interfaces.skill_types import ExecutionResult
    class MockSim:
        def execute_skill(self, approved_skill): 
            return ExecutionResult(success=True, state_changes={})
        
    adapter = UnifiedAdapter(agent_type="household", config_path=yaml_path)
    validator = AgentValidator(config_path=yaml_path)
    
    audit_cfg = AuditConfig(output_dir="tests/smoke_results", experiment_name="smoke_test")
    audit_writer = GenericAuditWriter(audit_cfg)
    
    broker = SkillBrokerEngine(
        skill_registry=SkillRegistry(), 
        model_adapter=adapter,
        validators=[validator],
        simulation_engine=MockSim(),
        context_builder=ctx_builder,
        audit_writer=audit_writer
    )
    
    # 4. Mock LLM Process
    def mock_llm(prompt: str) -> str:
        print("\n[LLM] Received Prompt (snippet):", prompt[:100])
        return "DECISION: do_nothing REASON: I am testing."
    
    print("\n[Broker] Processing Step...")
    result = broker.process_step(
        agent_id="agent_01",
        step_id=1,
        run_id="smoke_01",
        seed=42,
        llm_invoke=mock_llm,
        agent_type="household"
    )
    
    # 5. Verify Connectivity Results
    print("\n[Results] Verification:")
    print(f" - Skill Proposal: {result.skill_proposal.skill_name}")
    print(f" - Approved: {result.approved_skill.skill_name}")
    print(f" - Audit Path: {audit_writer._get_file_path('household')}")
    
    assert result.skill_proposal.skill_name == "do_nothing", "Adapter parsing failed"
    assert result.approved_skill.skill_name == "do_nothing", "Broker validation flow failed"
    
    print("\n=== Connectivity Test PASSED ===")

if __name__ == "__main__":
    main()
