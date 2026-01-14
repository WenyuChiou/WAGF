"""
Agent Type Configuration Loader

Loads unified agent configuration from broker/agent_types.yaml.
Provides easy access to prompts, validation rules, and coherence rules.
"""

import yaml
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


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
    id: str = "unknown"
    construct: Optional[str] = None # Single construct (legacy)
    conditions: Optional[List[Dict[str, Any]]] = None # Multi-construct: [{'construct': 'TP', 'values': ['L']}]
    state_field: Optional[str] = None
    state_fields: Optional[List[str]] = None
    aggregation: str = "single"
    threshold: float = 0.5
    expected_levels: Optional[List[str]] = None
    trigger_phrases: Optional[List[str]] = None
    blocked_skills: Optional[List[str]] = None
    level: str = "ERROR" # ERROR (retry) or WARNING (log only)
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    _config = {}
    
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
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            # Fallback to empty config if file missing (useful for testing)
            self._config = {}
        except Exception as e:
            print(f"Warning: Failed to load config from {yaml_path}: {e}")
            self._config = {}
    
    def get_base_type(self, agent_type: str) -> str:
        """Map a specific agent type/subtype to a base type defined in config."""
        if agent_type in self._config:
            return agent_type
        
        # Suffix-based mapping (mg/nmg)
        base_type = agent_type.split('_')[0]
        if base_type in self._config:
            return base_type
            
        return agent_type

    def get(self, agent_type: str) -> Dict[str, Any]:
        """Get config for agent type."""
        base_type = self.get_base_type(agent_type)
        return self._config.get(base_type, {})
    
    def items(self):
        """Allow iteration over agent types."""
        return self._config.items()
    
    def keys(self):
        """Allow checking agent types."""
        return self._config.keys()
    
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
    
    def get_identity_rules(self, agent_type: str) -> List[CoherenceRule]:
        """Get identity/status rules."""
        cfg = self.get(agent_type)
        profile = os.environ.get("GOVERNANCE_PROFILE", "default").lower()
        gov = cfg.get("governance", {})
        
        # Load profile-specific rules if they exist, otherwise fallback
        rules = gov.get(profile, {}).get("identity_rules", cfg.get("identity_rules", {}))
        
        # DEBUG
        # print(f"DEBUG_CONFIG: Loading identity_rules for {agent_type} (Profile: {profile}). Found {len(rules)} entries.")
            
        if isinstance(rules, dict):
            rules_list = [{"id": k, **v} for k, v in rules.items()]
        else:
            rules_list = rules
            
        return [
            CoherenceRule(
                construct=rule.get("construct", rule.get("id")),
                conditions=rule.get("conditions"),
                blocked_skills=rule.get("blocked_skills"),
                level=rule.get("level", "ERROR"),
                message=rule.get("message", ""),
                metadata={"precondition": rule.get("precondition")}
            )
            for rule in rules_list
        ]

    def validate_schema(self, agent_type: str) -> List[str]:
        """
        Validate that the configuration for an agent type is consistent.
        Returns a list of error/warning messages.
        """
        issues = []
        cfg = self.get(agent_type)
        if not cfg:
            return [f"Agent type '{agent_type}' not found in config."]

        # 1. Check Profile
        profile = os.environ.get("GOVERNANCE_PROFILE", "default").lower()
        gov = cfg.get("governance", {})
        if profile != "default" and profile not in gov:
            issues.append(f"WARNING: Governance profile '{profile}' not found for '{agent_type}'. Falling back to default.")

        # 2. Check Thinking Rules vs Constructs
        config_parsing = self.get_parsing_config(agent_type)
        constructs = config_parsing.get("constructs", {})
        rules = self.get_thinking_rules(agent_type)
        for rule in rules:
            target_constructs = []
            # For legacy format: id IS the construct name if no explicit construct field
            c_field = rule.construct
            if c_field and not rule.conditions:
                target_constructs.append(c_field)
            
            if rule.conditions:
                for cond in rule.conditions:
                    if "construct" in cond:
                        target_constructs.append(cond["construct"])
            
            for c in target_constructs:
                if c not in constructs:
                    issues.append(f"ERROR: Thinking rule '{rule.id}' references unknown construct '{c}'.")

        return issues

    def get_thinking_rules(self, agent_type: str) -> List[CoherenceRule]:
        """Get cognitive/thinking rules."""
        cfg = self.get(agent_type)
        profile = os.environ.get("GOVERNANCE_PROFILE", "default").lower()
        gov = cfg.get("governance", {})
        
        # Load profile-specific rules if they exist, otherwise fallback
        rules_container = gov.get(profile, {}) if profile in gov else gov.get("default", {})
        rules = rules_container.get("thinking_rules", cfg.get("thinking_rules", cfg.get("coherence_rules", {})))
        
        # DEBUG
        # print(f"DEBUG_CONFIG: Loading thinking_rules for {agent_type} (Profile: {profile}). Found {len(rules)} entries.")
            
        if isinstance(rules, list):
            rules_list = rules
        else:
            rules_list = [{"id": k, **v} for k, v in rules.items()]
            
        return [
            CoherenceRule(
                id=rule.get("id", rule.get("construct", "unknown")),
                construct=rule.get("construct", rule.get("id") if "conditions" not in rule else None),
                conditions=rule.get("conditions"),
                expected_levels=rule.get("when_above", rule.get("when_true")),
                blocked_skills=rule.get("blocked_skills"),
                level=rule.get("level", "ERROR"),
                message=rule.get("message", "")
            )
            for rule in rules_list
        ]

    def get_coherence_rules(self, agent_type: str) -> List[CoherenceRule]:
        """Legacy compatibility accessor."""
        return self.get_thinking_rules(agent_type)
    
    def get_constructs(self, agent_type: str) -> Dict[str, Dict]:
        """Get construct definitions."""
        cfg = self.get(agent_type)
        return cfg.get("constructs", {})
    
    def get_prompt_template(self, agent_type: str) -> str:
        """Get prompt template."""
        cfg = self.get(agent_type)
        return cfg.get("prompt_template", "")
    
    def get_parsing_config(self, agent_type: str) -> Dict[str, Any]:
        """Get parsing configuration for model adapter, falling back to default."""
        cfg = self.get(agent_type)
        parsing = cfg.get("parsing", {})
        
        # Merge with default if not presence
        default_parsing = self._config.get("default", {}).get("parsing", {})
        if not parsing:
            return default_parsing
            
        # Ensure constructs are inherited if missing
        if "constructs" not in parsing and "constructs" in default_parsing:
            parsing["constructs"] = default_parsing["constructs"]
            
        return parsing

    def get_memory_config(self, agent_type: str) -> Dict[str, Any]:
        """Get memory engine configuration (Phase 12), falling back to default."""
        cfg = self.get(agent_type)
        memory = cfg.get("memory", {})
        if not memory:
            return self._config.get("default", {}).get("memory", {})
        return memory

    def get_log_fields(self, agent_type: str) -> List[str]:
        """Get list of reasoning fields to highlight in logs, falling back to default."""
        cfg = self.get(agent_type)
        fields = cfg.get("log_fields", [])
        if not fields:
            return self._config.get("default", {}).get("log_fields", [])
        return fields


    def get_skill_map(self, agent_type: str, context: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Get numeric skill map for an agent, optionally resolving variants based on context.
        """
        parsing = self.get_parsing_config(agent_type)
        if not parsing:
            return {}
            
        # 1. Check for explicit skill_variant
        variant = context.get("skill_variant") if context else None
        if variant:
            v_key = f"skill_map_{variant}"
            if v_key in parsing:
                return parsing[v_key]
        
        # 2. Smart Resolution
        if context:
            for key, val in context.items():
                if isinstance(val, bool):
                    v_key = f"skill_map_{key}" if val else f"skill_map_non_{key}"
                    if v_key in parsing:
                        return parsing[v_key]
        
        # 3. Fallback
        return parsing.get("skill_map", {})

    def get_parameters(self, agent_type: str) -> Dict[str, Any]:
        """Get domain parameters for agent type."""
        cfg = self.get(agent_type)
        return cfg.get("parameters", {})

    def get_llm_params(self, agent_type: str) -> Dict[str, Any]:
        """Get LLM parameters (num_predict, num_ctx, etc.) for agent type."""
        cfg = self.get(agent_type)
        return cfg.get("llm_params", {})

    @property
    def agent_types(self) -> List[str]:
        """List all available agent types."""
        return list(self._config.keys())


class GovernanceAuditor:
    """
    Singleton for tracking and summarizing governance interventions.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GovernanceAuditor, cls).__new__(cls)
            cls._instance.rule_hits = defaultdict(int)
            cls._instance.retry_success_count = 0
            cls._instance.retry_failure_count = 0
            cls._instance.total_interventions = 0
        return cls._instance

    def log_intervention(self, rule_id: str, success: bool, is_final: bool = False):
        """Record a validator intervention."""
        self.rule_hits[rule_id] += 1
        self.total_interventions += 1
        
        if is_final:
            if success:
                self.retry_success_count += 1
            else:
                self.retry_failure_count += 1

    def save_summary(self, output_path: Path):
        """Save aggregated statistics to JSON."""
        summary = {
            "total_interventions": self.total_interventions,
            "rule_frequency": dict(self.rule_hits),
            "outcome_stats": {
                "retry_success": self.retry_success_count,
                "retry_exhausted": self.retry_failure_count
            }
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=4)
        print(f"[Governance:Auditor] Summary saved to {output_path}")


# Convenience function
def load_agent_config(yaml_path: Optional[str] = None) -> AgentTypeConfig:
    """Load agent type configuration."""
    return AgentTypeConfig.load(yaml_path)