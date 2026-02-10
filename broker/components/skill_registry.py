"""
Skill Registry - Central registry for skill definitions.

The Skill Registry is the "institutional charter" of the system.
It defines what skills exist, who can use them, and under what conditions.
This is NOT a prompt - it's a governance configuration.
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import logging
import yaml
from pathlib import Path

from ..interfaces.skill_types import SkillDefinition, ValidationResult

logger = logging.getLogger(__name__)


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
        """Load skill definitions from YAML file.

        Also reads the top-level ``default_skill`` key (if present) and
        sets the registry's default fallback skill accordingly.
        """
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
                implementation_mapping=skill_data.get('implementation_mapping', ''),
                output_schema=skill_data.get('output_schema', {}),
                conflicts_with=skill_data.get('conflicts_with', []),
                depends_on=skill_data.get('depends_on', []),
            )
            self.register(skill)

        # Set default fallback skill from YAML if specified
        default_id = data.get("default_skill")
        if default_id:
            if default_id in self.skills:
                self._default_skill = default_id
            else:
                logger.warning(
                    f"YAML default_skill='{default_id}' not found in registry. "
                    f"Using fallback '{self._default_skill}'"
                )
    
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
            # Preconditions are strings like "not has_item", "is_active", etc.
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

    def get_magnitude_bounds(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get magnitude constraints from institutional_constraints."""
        skill = self.get(skill_id)
        if not skill:
            return None
        ic = skill.institutional_constraints
        if "magnitude_type" not in ic:
            return None
        return {
            "magnitude_type": ic["magnitude_type"],
            "max_magnitude_pct": ic.get("max_magnitude_pct"),
        }

    def get_magnitude_default(self, skill_id: str) -> Optional[float]:
        """Get fallback magnitude from institutional_constraints."""
        skill = self.get(skill_id)
        if not skill:
            return None
        return skill.institutional_constraints.get("magnitude_default")

    def validate_output_schema(self, skill_id: str, output: Dict[str, Any]) -> ValidationResult:
        """Validate LLM output against JSON Schema-style output_schema.

        Supports type checking (number, string, integer), range validation
        (minimum/maximum), and enum constraints per the JSON Schema standard.
        """
        skill = self.get(skill_id)
        if not skill or not skill.output_schema:
            return ValidationResult(valid=True, validator_name="SkillRegistry.output_schema")

        errors: List[str] = []
        properties = skill.output_schema.get("properties", skill.output_schema)
        required_fields = skill.output_schema.get("required", [])

        for field_name in required_fields:
            if field_name not in output:
                errors.append(f"Required field '{field_name}' missing for skill '{skill_id}'")

        for field_name, field_spec in properties.items():
            if field_name not in output or not isinstance(field_spec, dict):
                continue
            value = output[field_name]
            expected_type = field_spec.get("type")

            if expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"Field '{field_name}': expected number, got {type(value).__name__}")
                continue
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Field '{field_name}': expected string, got {type(value).__name__}")
                continue
            if expected_type == "integer" and not isinstance(value, int):
                errors.append(f"Field '{field_name}': expected integer, got {type(value).__name__}")
                continue

            if isinstance(value, (int, float)):
                if "minimum" in field_spec and value < field_spec["minimum"]:
                    errors.append(f"Field '{field_name}': {value} < minimum {field_spec['minimum']}")
                if "maximum" in field_spec and value > field_spec["maximum"]:
                    errors.append(f"Field '{field_name}': {value} > maximum {field_spec['maximum']}")

            if "enum" in field_spec and value not in field_spec["enum"]:
                errors.append(f"Field '{field_name}': '{value}' not in allowed values {field_spec['enum']}")

        return ValidationResult(
            valid=len(errors) == 0,
            validator_name="SkillRegistry.output_schema",
            errors=errors,
        )

    def check_composite_conflicts(self, skill_ids: List[str]) -> ValidationResult:
        """Check for mutual exclusivity conflicts between proposed skills."""
        errors: List[str] = []
        # Validate all skill IDs exist in registry first
        for sid in skill_ids:
            if not self.get(sid):
                errors.append(f"Skill '{sid}' not found in registry")
        if errors:
            return ValidationResult(
                valid=False,
                validator_name="SkillRegistry.composite_conflicts",
                errors=errors,
            )
        # Check pairwise conflicts
        for i, sid in enumerate(skill_ids):
            skill = self.get(sid)
            for other_sid in skill_ids[i + 1:]:
                other_skill = self.get(other_sid)
                if other_sid in skill.conflicts_with or sid in other_skill.conflicts_with:
                    errors.append(f"Skills '{sid}' and '{other_sid}' are mutually exclusive")
        return ValidationResult(
            valid=len(errors) == 0,
            validator_name="SkillRegistry.composite_conflicts",
            errors=errors,
        )

