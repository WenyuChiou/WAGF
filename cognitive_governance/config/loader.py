"""
Domain Config Loader - Load and parse domain YAML configurations.

Provides unified access to domain-specific settings:
- State schema
- Action catalog (skills)
- Validator configurations (names only, not instances)
- Memory rules
- Prompt templates

Task-037: Migrated from config/loader.py to SDK
Note: get_validator_instances() moved to broker for decoupling
"""
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
import yaml


@dataclass
class SkillDefinition:
    """A skill definition extracted from domain config."""
    skill_id: str
    code: str
    description: str
    constraints: List[str] = field(default_factory=list)
    effects: Dict[str, Any] = field(default_factory=dict)
    eligible_agent_types: List[str] = field(default_factory=lambda: ["default"])


@dataclass
class ValidatorConfig:
    """Validator configuration."""
    name: str
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryRule:
    """Memory update rule."""
    event_type: str
    template: str
    params: Dict[str, Any] = field(default_factory=dict)


class DomainConfigLoader:
    """
    Load and parse domain configuration from YAML.

    Provides a single entry point for all domain-specific settings,
    enabling easy extension to new domains (e.g., climate_migration).

    Usage:
        loader = DomainConfigLoader.from_file("config/domains/flood_adaptation.yaml")
        skills = loader.get_skills()
        validator_names = loader.get_validator_names()
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._skills_cache: Optional[List[SkillDefinition]] = None

    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> "DomainConfigLoader":
        """Load config from YAML file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Domain config not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return cls(config)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "DomainConfigLoader":
        """Load config from dictionary (for testing)."""
        return cls(config)

    @property
    def domain_name(self) -> str:
        """Get domain name."""
        return self.config.get("domain_name", "unknown")

    @property
    def description(self) -> str:
        """Get domain description."""
        return self.config.get("description", "")

    # =========================================================================
    # SKILLS / ACTION CATALOG
    # =========================================================================

    def get_skills(self, agent_state: str = "default") -> List[SkillDefinition]:
        """
        Get skill definitions from action_catalog for a specific state.

        Args:
            agent_state: The current state category of the agent (domain-specific).
                         If state not found, falls back to "default" or first available.

        Returns:
            List of SkillDefinition objects
        """
        action_catalog = self.config.get("action_catalog", {})

        # 1. Try exact match
        catalog = action_catalog.get(agent_state)

        # 2. Try "default" fallback
        if catalog is None:
            catalog = action_catalog.get("default")

        # 3. Last resort: first available key if catalog has states
        if catalog is None and action_catalog:
            first_key = next(iter(action_catalog.keys()))
            if isinstance(action_catalog[first_key], dict):
                catalog = action_catalog[first_key]
            else:
                # Flat catalog (no state nesting)
                catalog = action_catalog

        skills = []
        if isinstance(catalog, dict):
            for skill_id, skill_config in catalog.items():
                skills.append(SkillDefinition(
                    skill_id=skill_id,
                    code=skill_config.get("code", ""),
                    description=skill_config.get("description", ""),
                    constraints=skill_config.get("constraints", []),
                    effects=skill_config.get("effects", {})
                ))

        return skills

    def get_skill_map(self, agent_state: str = "default") -> Dict[str, str]:
        """
        Get code → skill_id mapping for a specific state.
        """
        skills = self.get_skills(agent_state)
        return {str(s.code): s.skill_id for s in skills}

    def get_all_skill_ids(self) -> List[str]:
        """Get all unique skill IDs across all agent states."""
        all_ids = set()
        action_catalog = self.config.get("action_catalog", {})
        for state_catalog in action_catalog.values():
            if isinstance(state_catalog, dict):
                all_ids.update(state_catalog.keys())
        return list(all_ids)

    # =========================================================================
    # VALIDATORS (Configuration only, no instances)
    # =========================================================================

    def get_validators(self) -> List[ValidatorConfig]:
        """Get enabled validators."""
        validators_config = self.config.get("validators", {})
        enabled = validators_config.get("enabled", [])
        domain_validators = validators_config.get("domain_validators", [])

        result = []
        for name in enabled + domain_validators:
            result.append(ValidatorConfig(name=name, enabled=True))

        return result

    def get_validator_names(self) -> List[str]:
        """Get list of enabled validator names."""
        return [v.name for v in self.get_validators()]

    # Note: get_validator_instances() has been moved to broker/utils/validator_factory.py
    # to avoid SDK → broker dependency. Use broker's create_validators_from_config() instead.

    # =========================================================================
    # MEMORY RULES
    # =========================================================================

    def get_memory_rules(self) -> Dict[str, Any]:
        """Get memory rules configuration."""
        return self.config.get("memory_rules", {})

    def get_memory_template(self, event_type: str, sub_type: str = None) -> str:
        """
        Get memory template for an event type.

        Args:
            event_type: e.g., "flood_event", "decision_made"
            sub_type: e.g., "buy_insurance" for decision_made

        Returns:
            Template string or empty string if not found
        """
        rules = self.get_memory_rules()
        rule = rules.get(event_type, {})

        if sub_type and isinstance(rule, dict):
            return rule.get(sub_type, rule.get("template", ""))

        return rule.get("template", "") if isinstance(rule, dict) else ""

    # =========================================================================
    # TRUST UPDATE RULES
    # =========================================================================

    def get_trust_rules(self) -> Dict[str, Any]:
        """Get trust update rules."""
        return self.config.get("trust_update_rules", {})

    # =========================================================================
    # PROMPT TEMPLATE
    # =========================================================================

    def get_prompt_template(self) -> str:
        """Get the prompt template if defined in config."""
        return self.config.get("prompt_template", "")

    # =========================================================================
    # STATE SCHEMA
    # =========================================================================

    def get_state_schema(self) -> Dict[str, Any]:
        """Get state schema definition."""
        return self.config.get("state_schema", {})

    def get_observable_signals(self) -> Dict[str, List[str]]:
        """Get observable signals (what LLM can see)."""
        return self.config.get("observable_signals", {})

    def get_hidden_state(self) -> List[str]:
        """Get hidden state fields (LLM cannot see)."""
        return self.config.get("hidden_state", [])

    # =========================================================================
    # RETRY POLICY
    # =========================================================================

    def get_retry_policy(self) -> Dict[str, Any]:
        """Get retry policy configuration."""
        return self.config.get("retry_policy", {
            "max_retries": 2,
            "fallback_action": "do_nothing"
        })

    # =========================================================================
    # AUDIT
    # =========================================================================

    def get_audit_config(self) -> Dict[str, Any]:
        """Get audit configuration."""
        return self.config.get("audit", {})


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def load_domain(domain_name: str, config_dir: Union[str, Path] = None) -> DomainConfigLoader:
    """
    Load a domain by name.

    Args:
        domain_name: Name of the domain (e.g., "flood_adaptation")
        config_dir: Optional config directory path

    Returns:
        DomainConfigLoader instance
    """
    if config_dir is None:
        # Default: look in cognitive_governance/domains/
        config_dir = Path(__file__).parent.parent / "domains"

    config_path = Path(config_dir) / f"{domain_name}.yaml"
    return DomainConfigLoader.from_file(config_path)
