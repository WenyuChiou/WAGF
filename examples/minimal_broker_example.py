"""
Minimal Skill-Governed Broker Example.

This script demonstrates the core "Proposal -> Validation -> Impact" loop
without any domain-specific (disaster) modeling. 
Focus: Behavioral control and institutional governance.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.components.skill_registry import SkillRegistry
from broker.interfaces.skill_types import SkillDefinition, ApprovedSkill
from validators.agent_validator import AgentValidator

# 1. Define Skills in the Registry (The Institutional Charter)
registry = SkillRegistry()

# Skill 1: Do nothing
registry.register(SkillDefinition(
    skill_id="do_nothing",
    description="Remain idle and observe.",
    eligible_agent_types=["*"],
    preconditions=[],
    institutional_constraints={},
    allowed_state_changes=[],
    implementation_mapping="pass"
))

# Skill 2: Upgrade Skill (Restricted by budget)
registry.register(SkillDefinition(
    skill_id="upgrade_system",
    description="Perform a system upgrade (Costs $500).",
    eligible_agent_types=["admin", "power_user"],
    preconditions=["not system_upgraded"],
    institutional_constraints={"cost": 500},
    allowed_state_changes=["system_upgraded", "credits"],
    implementation_mapping="apply_upgrade"
))

# 2. Setup Validator (The Governance Laws)
# In a real scenario, this would load from a YAML file.
validator = AgentValidator() 

# 3. Setup Broker Engine
broker = SkillBrokerEngine(
    registry=registry,
    validators=[validator],
    output_dir="minimal_audit"
)

# 4. Define a Mock Agent and World State
class MockAgent:
    def __init__(self, agent_id, agent_type, credits):
        self.id = agent_id
        self.agent_type = agent_type
        self.credits = credits
        self.system_upgraded = False
        
    def get_available_skills(self):
        # The agent only sees skills it is authorized for
        return ["do_nothing", "upgrade_system"]

agent = MockAgent("Agent_007", "power_user", 1000)
context = {
    "agent_id": agent.id,
    "agent_type": agent.agent_type,
    "state": {"credits": agent.credits, "system_upgraded": agent.system_upgraded}
}

print(f"--- Initial State: Credits={agent.credits}, Upgraded={agent.system_upgraded} ---")

# 5. Simulate the Loop (Mental Sandbox)
# Scenario: User wants to upgrade.
proposal_data = {
    "skill_name": "upgrade_system",
    "reasoning": {"threat": "[LOW] System is old", "coping": "[HIGH] Upgrade is affordable"}
}

print(f"\n[Step 1] Agent Proposes: {proposal_data['skill_name']}")

# 6. Broker Processing (Authorize)
result = broker.process(
    agent_id=agent.id,
    proposal_json=proposal_data,
    context=context
)

if result.outcome.value == "APPROVED":
    print(f"✅ Approval: {result.approved_skill.skill_name} authorized by Broker.")
    
    # 7. Execution (Physical Impact)
    # The simulation engine would do this based on parameters
    agent.credits -= 500
    agent.system_upgraded = True
    print(f"--- Final State: Credits={agent.credits}, Upgraded={agent.system_upgraded} ---")
else:
    print(f"❌ Rejected: {result.validation_errors}")

print(f"\nAudit logs saved to minimal_audit/household_audit.jsonl")
