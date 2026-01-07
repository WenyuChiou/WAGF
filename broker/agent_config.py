"""
Agent Type Configuration Loader

Loads unified agent configuration from broker/agent_types.yaml.
Provides easy access to prompts, validation rules, and coherence rules.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ActionConfig:
    """Single action configuration."""
    id: str
    aliases: List[str]
    description: str
    requires: Optional[Dict[str, Any]] = None


@dataclass
class ValidationRule:
    """Single validation rule."""
    name: str
    param: str
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    max_delta: Optional[float] = None
    level: str = "WARNING"
    message: str = ""


@dataclass  
class CoherenceRule:
    """Construct coherence rule."""
    construct: str
    state_field: Optional[str] = None
    state_fields: Optional[List[str]] = None
    aggregation: str = "single"
    threshold: float = 0.5
    expected_levels: Optional[List[str]] = None
    trigger_phrases: Optional[List[str]] = None
    blocked_skills: Optional[List[str]] = None
    message: str = ""


class AgentTypeConfig:
    """
    Loader for agent type configurations.
    
    Usage:
        config = AgentTypeConfig.load()
        household = config.get("household")
        valid_actions = household["actions"]
        rules = household["validation_rules"]
    """
    
    _instance = None
    _config = None
    
    @classmethod
    def load(cls, yaml_path: str = None) -> "AgentTypeConfig":
        """Load or return cached config."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_yaml(yaml_path)
        return cls._instance
    
    def _load_yaml(self, yaml_path: str = None):
        """Load from YAML file."""
        if yaml_path is None:
            yaml_path = Path(__file__).parent / "agent_types.yaml"
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
    
    def get_base_type(self, agent_type: str) -> str:
        """Map a specific agent type/subtype to a base type defined in config."""
        # Handle common subtypes like household_mg -> household
        # If the exact type exists, return it, otherwise try base mapping
        if agent_type in self._config:
            return agent_type
        
        # Simple suffix-based mapping as a fallback
        base_type = agent_type.replace("_mg", "").replace("_nmg", "")
        return base_type

    def get(self, agent_type: str) -> Dict[str, Any]:
        """Get config for agent type."""
        base_type = self.get_base_type(agent_type)
        return self._config.get(base_type, {})
    
    def get_valid_actions(self, agent_type: str) -> List[str]:
        """Get all valid action IDs and aliases for agent type."""
        cfg = self.get(agent_type)
        actions = cfg.get("actions", [])
        valid = []
        for action in actions:
            valid.append(action["id"])
            valid.extend(action.get("aliases", []))
        return valid
    
    def get_validation_rules(self, agent_type: str) -> Dict[str, ValidationRule]:
        """Get validation rules as dict."""
        cfg = self.get(agent_type)
        rules = cfg.get("validation_rules", {})
        return {
            name: ValidationRule(
                name=name,
                param=rule.get("param", ""),
                min_val=rule.get("min"),
                max_val=rule.get("max"),
                max_delta=rule.get("max_delta"),
                level=rule.get("level", "WARNING"),
                message=rule.get("message", "")
            )
            for name, rule in rules.items()
        }
    
    def get_coherence_rules(self, agent_type: str) -> List[CoherenceRule]:
        """Get coherence rules for construct validation."""
        cfg = self.get(agent_type)
        rules = cfg.get("coherence_rules", {})
        return [
            CoherenceRule(
                construct=name,
                state_field=rule.get("state_field"),
                state_fields=rule.get("state_fields"),
                aggregation=rule.get("aggregation", "single"),
                threshold=rule.get("threshold", 0.5),
                expected_levels=rule.get("when_above", rule.get("when_true")),
                trigger_phrases=rule.get("trigger_phrases"),
                blocked_skills=rule.get("blocked_skills"),
                message=rule.get("message", "")
            )
            for name, rule in rules.items()
        ]
    
    def get_constructs(self, agent_type: str) -> Dict[str, Dict]:
        """Get construct definitions."""
        cfg = self.get(agent_type)
        return cfg.get("constructs", {})
    
    def get_prompt_template(self, agent_type: str) -> str:
        """Get prompt template."""
        cfg = self.get(agent_type)
        return cfg.get("prompt_template", "")
    
    def get_parsing_config(self, agent_type: str) -> Dict[str, Any]:
        """Get parsing configuration for model adapter."""
        cfg = self.get(agent_type)
        return cfg.get("parsing", {})

    def get_parameters(self, agent_type: str) -> Dict[str, Any]:
        """Get domain parameters for agent type."""
        cfg = self.get(agent_type)
        return cfg.get("parameters", {})

    @property
    def agent_types(self) -> List[str]:
        """List all available agent types."""
        return list(self._config.keys())


# Convenience function
def load_agent_config(yaml_path: Optional[str] = None) -> AgentTypeConfig:
    """Load agent type configuration."""
    return AgentTypeConfig.load(yaml_path)
