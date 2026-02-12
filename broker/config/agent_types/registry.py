"""
Agent Type Registry - Central registry for agent type definitions.

Provides a unified interface for managing agent types across SA and MA scenarios.
Supports YAML-based configuration loading with inheritance.

Part of Task-040: SA/MA Unified Architecture (Part 14.5)
"""
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import copy
import yaml

from broker.config.agent_types.base import (
    AgentTypeDefinition,
    AgentCategory,
    PsychologicalFramework,
    DEFAULT_PMT_CONSTRUCTS,
    DEFAULT_UTILITY_CONSTRUCTS,
)


class AgentTypeRegistry:
    """
    Central registry for agent type definitions.

    This registry manages all agent type configurations and provides:
    - Type registration and lookup
    - YAML-based configuration loading
    - Inheritance resolution (parent types)
    - Per-type context template and skill eligibility queries

    Usage:
        registry = AgentTypeRegistry()
        registry.load_from_yaml(Path("config/agent_types.yaml"))

        # Query agent type info
        defn = registry.get("household_owner")
        skills = registry.get_eligible_skills("household_renter")
    """

    def __init__(self):
        self._types: Dict[str, AgentTypeDefinition] = {}
        self._inheritance_resolved: Set[str] = set()

    def register(self, defn: AgentTypeDefinition) -> None:
        """
        Register an agent type definition.

        Args:
            defn: AgentTypeDefinition to register

        Raises:
            ValueError: If type_id is empty or already registered
        """
        if not defn.type_id:
            raise ValueError("AgentTypeDefinition must have a non-empty type_id")

        if defn.type_id in self._types:
            raise ValueError(f"Agent type '{defn.type_id}' is already registered")

        self._types[defn.type_id] = defn

    def get(self, type_id: str) -> Optional[AgentTypeDefinition]:
        """
        Get an agent type definition by ID.

        Args:
            type_id: The agent type identifier

        Returns:
            AgentTypeDefinition if found, None otherwise
        """
        defn = self._types.get(type_id)
        if defn and defn.type_id not in self._inheritance_resolved:
            self._resolve_inheritance(type_id)
        return self._types.get(type_id)

    def get_all(self) -> Dict[str, AgentTypeDefinition]:
        """Get all registered agent types."""
        # Resolve inheritance for all types
        for type_id in self._types:
            if type_id not in self._inheritance_resolved:
                self._resolve_inheritance(type_id)
        return dict(self._types)

    def get_by_category(self, category: AgentCategory) -> List[AgentTypeDefinition]:
        """
        Get all agent types in a category.

        Args:
            category: AgentCategory to filter by

        Returns:
            List of matching AgentTypeDefinitions
        """
        return [
            defn for defn in self.get_all().values()
            if defn.category == category
        ]

    def get_by_framework(self, framework: PsychologicalFramework) -> List[AgentTypeDefinition]:
        """
        Get all agent types using a specific psychological framework.

        Args:
            framework: PsychologicalFramework to filter by

        Returns:
            List of matching AgentTypeDefinitions
        """
        return [
            defn for defn in self.get_all().values()
            if defn.psychological_framework == framework
        ]

    def get_context_template(self, type_id: str) -> str:
        """
        Get the context template path for an agent type.

        Args:
            type_id: The agent type identifier

        Returns:
            Template path string, empty if not found
        """
        defn = self.get(type_id)
        return defn.context_template if defn else ""

    def get_eligible_skills(self, type_id: str) -> List[str]:
        """
        Get eligible skills for an agent type.

        Args:
            type_id: The agent type identifier

        Returns:
            List of eligible skill names, empty if not found
        """
        defn = self.get(type_id)
        return defn.eligible_skills if defn else []

    def get_psychological_framework(self, type_id: str) -> Optional[PsychologicalFramework]:
        """
        Get the psychological framework for an agent type.

        Args:
            type_id: The agent type identifier

        Returns:
            PsychologicalFramework if found, None otherwise
        """
        defn = self.get(type_id)
        return defn.psychological_framework if defn else None

    def get_constructs(self, type_id: str) -> Dict[str, Any]:
        """
        Get psychological constructs for an agent type.

        Args:
            type_id: The agent type identifier

        Returns:
            Dictionary of construct definitions
        """
        defn = self.get(type_id)
        return dict(defn.constructs) if defn else {}

    def is_skill_eligible(self, type_id: str, skill_name: str) -> bool:
        """
        Check if a skill is eligible for an agent type.

        Args:
            type_id: The agent type identifier
            skill_name: The skill to check

        Returns:
            True if eligible, False otherwise
        """
        defn = self.get(type_id)
        return defn.is_skill_eligible(skill_name) if defn else False

    def list_types(self) -> List[str]:
        """Get list of all registered type IDs."""
        return list(self._types.keys())

    def has_type(self, type_id: str) -> bool:
        """Check if a type is registered."""
        return type_id in self._types

    def _resolve_inheritance(self, type_id: str) -> None:
        """
        Resolve inheritance for an agent type.

        Merges parent type fields into child type (child overrides parent).
        """
        if type_id in self._inheritance_resolved:
            return

        defn = self._types.get(type_id)
        if not defn or not defn.parent:
            self._inheritance_resolved.add(type_id)
            return

        # Resolve parent first (recursive)
        parent_id = defn.parent
        if parent_id not in self._types:
            self._inheritance_resolved.add(type_id)
            return

        self._resolve_inheritance(parent_id)
        parent = self._types[parent_id]

        # Merge parent into child (child takes precedence)
        merged = self._merge_definitions(parent, defn)
        self._types[type_id] = merged
        self._inheritance_resolved.add(type_id)

    def _merge_definitions(
        self,
        parent: AgentTypeDefinition,
        child: AgentTypeDefinition
    ) -> AgentTypeDefinition:
        """
        Merge parent definition into child (child overrides).

        Args:
            parent: Parent type definition
            child: Child type definition

        Returns:
            Merged AgentTypeDefinition
        """
        # Start with a copy of child
        merged_constructs = dict(parent.constructs)
        merged_constructs.update(child.constructs)

        merged_skills = child.eligible_skills or parent.eligible_skills

        merged_validation = child.validation or parent.validation

        merged_memory = child.memory_config or parent.memory_config

        merged_response = child.response_format or parent.response_format

        return AgentTypeDefinition(
            type_id=child.type_id,
            category=child.category,
            psychological_framework=child.psychological_framework,
            constructs=merged_constructs,
            context_template=child.context_template or parent.context_template,
            system_prompt=child.system_prompt or parent.system_prompt,
            response_format=merged_response,
            eligible_skills=merged_skills,
            validation=merged_validation,
            memory_config=merged_memory,
            parent=None,  # Inheritance resolved
            description=child.description or parent.description,
            metadata={**parent.metadata, **child.metadata},
        )

    def load_from_yaml(self, yaml_path: Path) -> int:
        """
        Load agent type definitions from a YAML file.

        Expected YAML structure:
            agent_types:
              household_owner:
                type_id: household_owner
                category: household
                psychological_framework: pmt
                eligible_skills: [...]
              household_renter:
                type_id: household_renter
                parent: household_owner
                eligible_skills: [...]

        Args:
            yaml_path: Path to YAML configuration file

        Returns:
            Number of types loaded

        Raises:
            FileNotFoundError: If YAML file doesn't exist
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"Agent types config not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return self.load_from_dict(data)

    def load_from_dict(self, data: Dict[str, Any]) -> int:
        """
        Load agent type definitions from a dictionary.

        Supports two formats:
        1. Direct: {"agent_types": {type_id: {...}, ...}}
        2. Legacy: {type_id: {...}, ...} (backward compatible)

        Args:
            data: Dictionary containing agent type definitions

        Returns:
            Number of types loaded
        """
        count = 0

        # Support both formats
        types_data = data.get("agent_types", data)

        # Filter out non-type keys (like "global_config", "shared")
        non_type_keys = {"global_config", "shared", "governance", "response_format"}

        for type_id, type_data in types_data.items():
            if type_id in non_type_keys:
                continue

            if not isinstance(type_data, dict):
                continue

            # Ensure type_id is set
            type_data["type_id"] = type_data.get("type_id", type_id)

            try:
                defn = AgentTypeDefinition.from_dict(type_data)
                self.register(defn)
                count += 1
            except Exception as e:
                # Log but continue loading other types
                print(f"Warning: Failed to load agent type '{type_id}': {e}")

        return count

    def clear(self) -> None:
        """Clear all registered types."""
        self._types.clear()
        self._inheritance_resolved.clear()

    def __len__(self) -> int:
        return len(self._types)

    def __contains__(self, type_id: str) -> bool:
        return type_id in self._types


def create_default_registry() -> AgentTypeRegistry:
    """
    Create a registry with default household types (water domain).

    .. deprecated::
        This function provides water-domain defaults for backward compatibility.
        New domains should use ``AgentTypeRegistry()`` with YAML config via
        ``ExperimentBuilder.with_governance()``.

    Returns:
        AgentTypeRegistry with default household types
    """
    registry = AgentTypeRegistry()

    # Default household owner type
    owner_type = AgentTypeDefinition(
        type_id="household",
        category=AgentCategory.HOUSEHOLD,
        psychological_framework=PsychologicalFramework.PMT,
        constructs=copy.deepcopy(DEFAULT_PMT_CONSTRUCTS),
        eligible_skills=["buy_insurance", "elevate_house", "buyout_program", "relocate", "do_nothing"],
        description="Default household agent type (owner)",
    )
    registry.register(owner_type)

    # Alias for backward compatibility
    owner_alias = copy.deepcopy(owner_type)
    owner_alias.type_id = "household_owner"
    owner_alias.parent = "household"
    registry.register(owner_alias)

    return registry


# Global default registry instance
_default_registry: Optional[AgentTypeRegistry] = None


def get_default_registry() -> AgentTypeRegistry:
    """
    Get the global default registry instance.

    Creates a default registry on first call.

    Returns:
        The global AgentTypeRegistry instance
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = create_default_registry()
    return _default_registry


def reset_default_registry() -> None:
    """Reset the global default registry (for testing)."""
    global _default_registry
    _default_registry = None
