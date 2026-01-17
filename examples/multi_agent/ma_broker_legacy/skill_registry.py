"""
Exp3 Skill Registry - Domain specific skills for flood adaptation.
"""
from broker.skill_types import SkillDefinition
from broker.skill_registry import SkillRegistry

def create_exp3_skill_registry() -> SkillRegistry:
    """Create a pre-configured registry for flood adaptation scenario."""
    registry = SkillRegistry()
    
    registry.register(SkillDefinition(
        skill_id="buy_insurance",
        description="Purchase flood insurance for financial protection",
        eligible_agent_types=["*"],
        preconditions=[],  # Can buy even if already has (renewal)
        institutional_constraints={"annual": True},
        allowed_state_changes=["has_insurance"],
        implementation_mapping="sim.buy_insurance"
    ))
    
    registry.register(SkillDefinition(
        skill_id="elevate_house",
        description="Elevate house to prevent flood damage",
        eligible_agent_types=["*"],
        preconditions=["not elevated"],
        institutional_constraints={"once_only": True, "requires_grant": False},
        allowed_state_changes=["elevated"],
        implementation_mapping="sim.elevate"
    ))
    
    registry.register(SkillDefinition(
        skill_id="relocate",
        description="Relocate away from flood-prone area",
        eligible_agent_types=["*"],
        preconditions=["not relocated"],
        institutional_constraints={"once_only": True, "permanent": True},
        allowed_state_changes=["relocated"],
        implementation_mapping="sim.relocate"
    ))
    
    registry.register(SkillDefinition(
        skill_id="do_nothing",
        description="Take no action this year",
        eligible_agent_types=["*"],
        preconditions=[],
        institutional_constraints={},
        allowed_state_changes=[],
        implementation_mapping="sim.noop"
    ))
    
    registry.set_default_skill("do_nothing")
    
    return registry
