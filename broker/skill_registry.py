"""
Skill Registry - Central registry for skill definitions.

The Skill Registry is the "institutional charter" of the system.
It defines what skills exist, who can use them, and under what conditions.
This is NOT a prompt - it's a governance configuration.
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import yaml
from pathlib import Path

from .skill_types import SkillDefinition, ValidationResult


class SkillRegistry:
    """
    Central registry for all available skills.
    
    The registry serves as the single source of truth for:
    - What skills exist in the system
    - Who is eligible to use each skill
    - What preconditions must be met
    - What institutional constraints apply
    - What state changes are allowed
    - How skills map to execution commands
    """
    
    def __init__(self):
        self.skills: Dict[str, SkillDefinition] = {}
        self._default_skill: str = "do_nothing"
    
    def register(self, skill: SkillDefinition) -> None:
        """Register a skill definition."""
        self.skills[skill.skill_id] = skill
    
    def register_from_yaml(self, yaml_path: str) -> None:
        """Load skill definitions from YAML file."""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        for skill_data in data.get('skills', []):
            skill = SkillDefinition(
                skill_id=skill_data['skill_id'],
                description=skill_data.get('description', ''),
                eligible_agent_types=skill_data.get('eligible_agent_types', ['*']),
                preconditions=skill_data.get('preconditions', []),
                institutional_constraints=skill_data.get('institutional_constraints', {}),
                allowed_state_changes=skill_data.get('allowed_state_changes', []),
                implementation_mapping=skill_data.get('implementation_mapping', '')
            )
            self.register(skill)
    
    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        """Get a skill definition by ID."""
        return self.skills.get(skill_id)
    
    def exists(self, skill_id: str) -> bool:
        """Check if a skill exists in the registry."""
        return skill_id in self.skills
    
    def get_default_skill(self) -> str:
        """Get the default fallback skill."""
        return self._default_skill
    
    def set_default_skill(self, skill_id: str) -> None:
        """Set the default fallback skill."""
        if skill_id in self.skills:
            self._default_skill = skill_id
    
    @classmethod
    def from_domain_config(cls, loader: "DomainConfigLoader", agent_state: str = "non_elevated") -> "SkillRegistry":
        """
        Create a SkillRegistry from a DomainConfigLoader.
        
        This enables dynamic loading of skills from domain YAML configuration,
        improving extensibility for new domains.
        
        Args:
            loader: DomainConfigLoader instance
            agent_state: Agent state for skill selection ("non_elevated" or "elevated")
        
        Returns:
            SkillRegistry populated with skills from the domain config
        
        Example:
            loader = DomainConfigLoader.from_file("config/domains/flood_adaptation.yaml")
            registry = SkillRegistry.from_domain_config(loader)
        """
        from .skill_types import SkillDefinition
        
        registry = cls()
        
        for skill in loader.get_skills(agent_state):
            # Convert loader's SkillDefinition to registry's SkillDefinition
            registry.register(SkillDefinition(
                skill_id=skill.skill_id,
                description=skill.description,
                eligible_agent_types=skill.eligible_agent_types,
                preconditions=skill.constraints,  # Map constraints to preconditions
                institutional_constraints={"once_only": "elevated" in skill.effects or "relocated" in skill.effects},
                allowed_state_changes=list(skill.effects.keys()),
                implementation_mapping=f"sim.{skill.skill_id}"
            ))
        
        # Set default skill (usually do_nothing)
        if "do_nothing" in registry.skills:
            registry.set_default_skill("do_nothing")
        
        return registry

    def check_eligibility(self, skill_id: str, agent_type: str) -> ValidationResult:
        """Check if an agent type is eligible to use a skill."""
        skill = self.get(skill_id)
        if not skill:
            return ValidationResult(
                valid=False,
                validator_name="SkillRegistry.eligibility",
                errors=[f"Skill '{skill_id}' not found in registry"]
            )
        
        # Wildcard allows all agent types
        if '*' in skill.eligible_agent_types:
            return ValidationResult(valid=True, validator_name="SkillRegistry.eligibility")
        
        if agent_type not in skill.eligible_agent_types:
            return ValidationResult(
                valid=False,
                validator_name="SkillRegistry.eligibility",
                errors=[f"Agent type '{agent_type}' not eligible for skill '{skill_id}'"]
            )
        
        return ValidationResult(valid=True, validator_name="SkillRegistry.eligibility")
    
    def check_preconditions(self, skill_id: str, agent_state: Dict[str, Any]) -> ValidationResult:
        """Check if preconditions are met for a skill."""
        skill = self.get(skill_id)
        if not skill:
            return ValidationResult(
                valid=False,
                validator_name="SkillRegistry.preconditions",
                errors=[f"Skill '{skill_id}' not found"]
            )
        
        errors = []
        for precondition in skill.preconditions:
            # Preconditions are strings like "not has_insurance", "elevated", etc.
            if precondition.startswith("not "):
                field = precondition[4:].strip()
                if agent_state.get(field, False):
                    errors.append(f"Precondition failed: '{precondition}' (field is True)")
            else:
                if not agent_state.get(precondition, False):
                    errors.append(f"Precondition failed: '{precondition}' (field is False)")
        
        return ValidationResult(
            valid=len(errors) == 0,
            validator_name="SkillRegistry.preconditions",
            errors=errors
        )
    
    def get_execution_mapping(self, skill_id: str) -> Optional[str]:
        """Get the execution mapping for a skill."""
        skill = self.get(skill_id)
        return skill.implementation_mapping if skill else None
    
    def get_allowed_state_changes(self, skill_id: str) -> List[str]:
        """Get the allowed state changes for a skill."""
        skill = self.get(skill_id)
        return skill.allowed_state_changes if skill else []
    
    def list_skills(self) -> List[str]:
        """List all registered skill IDs."""
        return list(self.skills.keys())


# Convenience function to create flood adaptation registry
def create_flood_adaptation_registry() -> SkillRegistry:
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
