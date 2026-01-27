"""
Agent Type Configuration Loader

Loads unified agent configuration from broker/agent_types.yaml.
Provides easy access to prompts, validation rules, and coherence rules.

Task-035: Added SDK UnifiedConfigLoader integration for experiment configs.
"""

import yaml
import os
import json
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import defaultdict
from broker.utils.logging import setup_logger

if TYPE_CHECKING:
    from governed_ai_sdk.v1_prototype.config import (
        UnifiedConfigLoader,
        ExperimentConfig,
        MemoryConfig as SDKMemoryConfig,
    )

logger = setup_logger(__name__)


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
        agent_cfg = config.get("my_agent_type")  # e.g., "household", "trader", etc.
        valid_actions = agent_cfg["actions"]
        rules = agent_cfg["validation_rules"]
    """
    
    _instance = None
    _config = {}
    
    @classmethod
    def load(cls, yaml_path: str = None) -> "AgentTypeConfig":
        """Load or return cached config."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_yaml(yaml_path)
        elif yaml_path is not None:
            # Allow reloading from an explicit path to avoid stale cached config.
            cls._instance._load_yaml(yaml_path)
        return cls._instance
    
    def _load_yaml(self, yaml_path: str = None):
        """Load from YAML file."""
        if yaml_path is None:
            # 1. Try CWD
            cwd_path = Path.cwd() / "agent_types.yaml"
            if cwd_path.exists():
                yaml_path = cwd_path
            else:
                # 2. Fallback to package default
                yaml_path = Path(__file__).parent / "agent_types.yaml"
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            # logger.info(f"Loaded configuration from {yaml_path}")
        except FileNotFoundError:
            # Fallback to empty config if file missing (useful for testing)
            self._config = {}
        except Exception as e:
            logger.warning(f"Failed to load config from {yaml_path}: {e}")
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
    
    def get_shared(self, key: str, default: Any = "") -> Any:
        """Get shared config value (e.g., rating_scale)."""
        shared = self._config.get("shared", {})
        return shared.get(key, default)
    
    def get_governance_retries(self, default: int = 3) -> int:
        """Get max retries for governance loop (Global > Shared > Default)."""
        # 1. Check Global Config
        global_gov = self._config.get("global_config", {}).get("governance", {})
        return global_gov.get("max_retries", self._config.get("shared", {}).get("governance", {}).get("max_retries", default))
    
    def get_governance_max_reports(self, default: int = 3) -> int:
        """Get max reports per retry (Global > Shared > Default)."""
        # 1. Check Global Config
        global_gov = self._config.get("global_config", {}).get("governance", {})
        return global_gov.get("max_reports_per_retry", self._config.get("shared", {}).get("governance", {}).get("max_reports_per_retry", default))
    
    def get_llm_retries(self, default: int = 2) -> int:
        """Get max retries for raw LLM invocation (Global > Shared > Default)."""
        # 1. Check Global Config
        global_llm = self._config.get("global_config", {}).get("llm", {})
        return global_llm.get("max_retries", self._config.get("shared", {}).get("llm", {}).get("max_retries", default))
    
    def get_reflection_config(self) -> dict:
        """Get reflection configuration (Global > Shared > Default).
        
        Returns dict with keys: interval, batch_size, importance_boost
        """
        defaults = {"interval": 1, "batch_size": 10, "importance_boost": 0.9}
        
        # 1. Global Config
        global_refl = self._config.get("global_config", {}).get("reflection", {}) or {}
        
        # 2. Shared (Legacy Fallback)
        shared_refl = self._config.get("shared", {}).get("reflection", {}) or {}
        
        # Merge: Global > Shared > Default
        merged = defaults.copy()
        merged.update(shared_refl) # Apply legacy shared
        merged.update(global_refl) # Apply new global
        
        return merged
    
    def get_valid_actions(self, agent_type: str) -> List[str]:
        """Get all valid action IDs and aliases for agent type."""
        cfg = self.get(agent_type)
        # Check both top-level and nested parsing.actions
        actions = cfg.get("actions", cfg.get("parsing", {}).get("actions", []))
        valid = []
        for action in actions:
            valid.append(action["id"])
            valid.extend(action.get("aliases", []))
        return valid
    
    def get_action_alias_map(self, agent_type: str) -> Dict[str, str]:
        """Get a mapping from aliases (and canonical IDs) to canonical skill IDs."""
        cfg = self.get(agent_type)
        # Check both top-level and nested parsing.actions
        actions = cfg.get("actions", cfg.get("parsing", {}).get("actions", []))
        alias_map = {}
        for action in actions:
            canonical = action["id"]
            # Map canonical to itself
            alias_map[canonical.lower()] = canonical
            # Map all aliases to canonical
            for alias in action.get("aliases", []):
                alias_map[alias.lower()] = canonical
        return alias_map

    
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

        # Task 015 fix: Look in both locations for governance rules
        # 1. Top-level governance section: governance.{profile}.{agent_type}.identity_rules
        # 2. Agent-type section: {agent_type}.governance.{profile}.identity_rules (legacy)
        top_level_gov = self._config.get("governance", {})
        rules = top_level_gov.get(profile, {}).get(agent_type, {}).get("identity_rules", [])

        # Fallback to agent-type embedded governance (legacy format)
        if not rules:
            gov = cfg.get("governance", {})
            rules = gov.get(profile, {}).get("identity_rules", cfg.get("identity_rules", {}))
        
        # DEBUG
        # print(f"DEBUG_CONFIG: Loading identity_rules for {agent_type} (Profile: {profile}). Found {len(rules)} entries.")
            
        if isinstance(rules, dict):
            rules_list = [{"id": k, **v} for k, v in rules.items()]
        else:
            rules_list = rules
            
        return [
            CoherenceRule(
                id=rule.get("id", "unknown"),
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
        top_level_gov = self._config.get("governance", {})
        top_level_profile = top_level_gov.get(profile, {}) if profile != "default" else {}
        has_top_level = agent_type in top_level_profile
        if profile != "default" and profile not in gov and not has_top_level:
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

        # Task 015 fix: Look in both locations for governance rules
        # 1. Top-level governance section: governance.{profile}.{agent_type}.thinking_rules
        # 2. Agent-type section: {agent_type}.governance.{profile}.thinking_rules (legacy)
        top_level_gov = self._config.get("governance", {})
        rules = top_level_gov.get(profile, {}).get(agent_type, {}).get("thinking_rules", [])

        # Fallback to agent-type embedded governance (legacy format)
        if not rules:
            gov = cfg.get("governance", {})
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
        """Get memory engine configuration (v1/v2/v3 supported), falling back to default."""
        cfg = self.get(agent_type)
        memory = cfg.get("memory", {}) or {}
        if not memory:
            return self._config.get("default", {}).get("memory", {}) or {}
        return memory

    def get_log_fields(self, agent_type: str) -> List[str]:
        """Get list of reasoning fields to highlight in logs, falling back to default."""
        cfg = self.get(agent_type)
        fields = cfg.get("log_fields", [])
        if not fields:
            return self._config.get("default", {}).get("log_fields", [])
        return fields

    def get_global_skills(self, agent_type: str) -> List[str]:
        """Get list of world-available skills (Phase 32) that are always presented."""
        parsing = self.get_parsing_config(agent_type)
        return parsing.get("global_skills", [])

    def get_full_disclosure_agent_types(self) -> List[str]:
        """Get list of agent types that bypass skill retrieval (Phase 33)."""
        types = []
        for atype, cfg in self._config.items():
            if cfg.get("parsing", {}).get("full_disclosure"):
                types.append(atype)
        return types


    def get_skill_map(self, agent_type: str, context: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Get numeric skill map for an agent, optionally resolving variants based on context.
        
        Priority:
        1. dynamic_skill_map from context (for shuffled options)
        2. skill_variant-based map from YAML
        3. Smart resolution based on boolean context vars
        4. Default skill_map fallback
        """
        # 0. Check for dynamic_skill_map from context (highest priority - used for option shuffling)
        if context:
            # Check both top-level and nested in 'personal'
            dynamic_map = context.get("dynamic_skill_map") or context.get("personal", {}).get("dynamic_skill_map")
            if dynamic_map:
                return dynamic_map
        
        parsing = self.get_parsing_config(agent_type)
        if not parsing:
            return {}
            
        # 0. Check for dynamic_skill_map (Priority for transient mappings)
        dynamic = context.get("dynamic_skill_map") if context else None
        if dynamic:
            return dynamic

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
        shared_llm = self._config.get("shared", {}).get("llm", {}) or {}
        global_llm = self._config.get("global_config", {}).get("llm", {}) or {}
        agent_llm = cfg.get("llm_params", {}) or {}
        merged = {}
        merged.update(shared_llm)
        merged.update(global_llm)
        merged.update(agent_llm)
        return merged

    def get_global_memory_config(self) -> Dict[str, Any]:
        """Get global memory config (Global > Shared > Default)."""
        defaults = {
            "window_size": 3,
            "consolidation_threshold": 0.6,
            "consolidation_probability": 0.7,
            "top_k_significant": 2,
            "decay_rate": 0.1
        }
        shared_mem = self._config.get("shared", {}).get("memory", {})
        global_mem = self._config.get("global_config", {}).get("memory", {})
        merged = defaults.copy()
        merged.update(shared_mem)
        merged.update(global_mem)
        return merged

    def get_sensory_cortex(self, agent_type: str = None) -> Optional[List[Dict]]:
        """Return sensory_cortex config if defined in global memory config."""
        memory_cfg = self._config.get("global_config", {}).get("memory", {})
        return memory_cfg.get("sensory_cortex", None)

    def get_response_format(self, agent_type: str) -> Dict[str, Any]:
        """Get response format configuration (delimiters, fields) with shared fallback."""
        cfg = self.get(agent_type)
        agent_fmt = cfg.get("response_format", {})
        shared_fmt = self._config.get("shared", {}).get("response_format", {})
        
        # Merge: agent-specific overrides shared
        if agent_fmt:
            return {**shared_fmt, **agent_fmt}
        return shared_fmt

    @property
    def agent_types(self) -> List[str]:
        """List all available agent types."""
        return list(self._config.keys())

    # =========================================================================
    # Task-035: SDK UnifiedConfigLoader Integration
    # =========================================================================

    _sdk_loader: Optional["UnifiedConfigLoader"] = None
    _sdk_experiment_config: Optional["ExperimentConfig"] = None

    @classmethod
    def set_sdk_loader(cls, loader: "UnifiedConfigLoader"):
        """
        Set the SDK UnifiedConfigLoader for experiment config access.

        This allows using SDK-style configuration (YAML with validation)
        alongside the existing agent_types.yaml system.

        Args:
            loader: Instance of governed_ai_sdk.v1_prototype.config.UnifiedConfigLoader

        Example:
            >>> from governed_ai_sdk.v1_prototype.config import UnifiedConfigLoader
            >>> loader = UnifiedConfigLoader()
            >>> AgentTypeConfig.set_sdk_loader(loader)
        """
        cls._sdk_loader = loader

    @classmethod
    def load_sdk_experiment(cls, config_path: str) -> Optional["ExperimentConfig"]:
        """
        Load experiment configuration using SDK UnifiedConfigLoader.

        Args:
            config_path: Path to YAML experiment config file

        Returns:
            ExperimentConfig instance or None if SDK not available

        Example:
            >>> config = AgentTypeConfig.load_sdk_experiment("config/flood_study.yaml")
            >>> print(config.domain, config.agents)
        """
        if cls._sdk_loader is None:
            try:
                from governed_ai_sdk.v1_prototype.config import UnifiedConfigLoader
                cls._sdk_loader = UnifiedConfigLoader()
            except ImportError:
                logger.warning("SDK not available, cannot load experiment config")
                return None

        try:
            cls._sdk_experiment_config = cls._sdk_loader.load_experiment(config_path)
            logger.info(f"Loaded SDK experiment config: {cls._sdk_experiment_config.name}")
            return cls._sdk_experiment_config
        except Exception as e:
            logger.error(f"Failed to load SDK experiment config: {e}")
            return None

    def get_sdk_memory_config(self) -> Optional["SDKMemoryConfig"]:
        """
        Get SDK MemoryConfig from loaded experiment.

        Returns SDK-style MemoryConfig with validated fields, or None if
        no SDK experiment config is loaded.

        Returns:
            SDKMemoryConfig instance or None
        """
        if self._sdk_experiment_config is not None:
            return self._sdk_experiment_config.memory
        return None

    def get_sdk_reflection_config(self) -> Optional[Dict[str, Any]]:
        """
        Get SDK ReflectionConfig from loaded experiment.

        Returns:
            Dict with reflection settings or None
        """
        if self._sdk_experiment_config is not None:
            refl = self._sdk_experiment_config.reflection
            return {
                "enabled": refl.enabled,
                "interval": refl.interval,
                "auto_promote": refl.auto_promote,
                "promotion_threshold": refl.promotion_threshold,
                "max_memories_per_reflection": refl.max_memories_per_reflection,
            }
        return None

    def get_sdk_llm_config(self) -> Optional[Dict[str, Any]]:
        """
        Get SDK LLMConfig from loaded experiment.

        Returns:
            Dict with LLM settings or None
        """
        if self._sdk_experiment_config is not None:
            llm = self._sdk_experiment_config.llm
            return {
                "provider": llm.provider,
                "model": llm.model,
                "temperature": llm.temperature,
                "max_tokens": llm.max_tokens,
                "base_url": llm.base_url,
            }
        return None

    def get_memory_config_v2(self, agent_type: str) -> Dict[str, Any]:
        """
        Get memory config with SDK fallback.

        Priority:
        1. SDK experiment config (if loaded)
        2. Agent-type specific config from YAML
        3. Global memory config

        Args:
            agent_type: The agent type name

        Returns:
            Dict with memory configuration
        """
        # 1. Try SDK config first
        sdk_mem = self.get_sdk_memory_config()
        if sdk_mem is not None:
            return {
                "engine": sdk_mem.engine,
                "window_size": sdk_mem.window_size,
                "arousal_threshold": sdk_mem.arousal_threshold,
                "ema_alpha": sdk_mem.ema_alpha,
                "consolidation_threshold": sdk_mem.consolidation_threshold,
                "persistence": sdk_mem.persistence,
                "persistence_path": sdk_mem.persistence_path,
            }

        # 2. Fallback to existing logic
        return self.get_memory_config(agent_type)



class GovernanceAuditor:
    """
    Singleton for tracking and summarizing governance interventions.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GovernanceAuditor, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.stats_lock = threading.Lock()
        self.rule_hits = defaultdict(int)
        self.retry_success_count = 0
        self.retry_failure_count = 0
        self.total_interventions = 0
        self.parse_errors = 0
        self._initialized = True

    def log_intervention(self, rule_id: str, success: bool, is_final: bool = False):
        """Record a validator intervention."""
        with self.stats_lock:
            self.rule_hits[rule_id] += 1
            self.total_interventions += 1
            
            if is_final:
                if success:
                    self.retry_success_count += 1
                else:
                    self.retry_failure_count += 1

    def log_parse_error(self):
        """Record a parsing failure where LLM output could not be converted to SkillProposal."""
        with self.stats_lock:
            self.parse_errors += 1

    def save_summary(self, output_path: Path):
        """Save aggregated statistics to JSON."""
        summary = {
            "total_interventions": self.total_interventions,
            "rule_frequency": dict(self.rule_hits),
            "outcome_stats": {
                "retry_success": self.retry_success_count,
                "retry_exhausted": self.retry_failure_count,
                "parse_errors": self.parse_errors
            }
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=4)
        logger.info(f"[Governance:Auditor] Summary saved to {output_path}")

    def print_summary(self):
        """Print a human-readable summary to console."""
        print("\n" + "="*50)
        print("  GOVERNANCE AUDIT SUMMARY")
        print("="*50)
        print(f"  Total Interventions: {self.total_interventions}")
        print(f"  Parsing Failures:    {self.parse_errors}")
        print(f"  Successful Retries:  {self.retry_success_count}")
        print(f"  Final Fallouts:      {self.retry_failure_count}")
        print("-"*50)
        print("  Top Rule Violations:")
        # Sort by frequency
        sorted_rules = sorted(self.rule_hits.items(), key=lambda x: x[1], reverse=True)
        for rule_id, count in sorted_rules[:5]:
            print(f"  - {rule_id}: {count} hits")
        print("="*50 + "\n")


# Convenience function
def load_agent_config(yaml_path: Optional[str] = None) -> AgentTypeConfig:
    """Load agent type configuration."""
    return AgentTypeConfig.load(yaml_path)
