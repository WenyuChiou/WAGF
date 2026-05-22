"""Water-domain agent-type registry defaults."""
import copy

from broker.config.agent_types.base import (
    AgentCategory,
    AgentTypeDefinition,
    DEFAULT_PMT_CONSTRUCTS,
    PsychologicalFramework,
)
from broker.config.agent_types.registry import AgentTypeRegistry


def create_water_agent_type_registry() -> AgentTypeRegistry:
    """Create the legacy household PMT registry for the water domain."""
    # Phase 6J-C (2026-05-22): relocated from the generic
    # create_default_registry() body.
    registry = AgentTypeRegistry()

    owner_type = AgentTypeDefinition(
        type_id="household",
        category=AgentCategory.HOUSEHOLD,
        psychological_framework=PsychologicalFramework.PMT,
        constructs=copy.deepcopy(DEFAULT_PMT_CONSTRUCTS),
        eligible_skills=[
            "buy_insurance",
            "elevate_house",
            "buyout_program",
            "relocate",
            "do_nothing",
        ],
        description="Default household agent type (owner)",
    )
    registry.register(owner_type)

    owner_alias = copy.deepcopy(owner_type)
    owner_alias.type_id = "household_owner"
    owner_alias.parent = "household"
    registry.register(owner_alias)

    return registry
