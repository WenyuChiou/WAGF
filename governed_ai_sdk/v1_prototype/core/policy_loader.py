"""
PolicyLoader - Load policies from Dict or YAML.

Simplified from: broker/utils/agent_config.py
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from governed_ai_sdk.v1_prototype.types import PolicyRule


class PolicyLoader:
    """
    Load and parse policy definitions.

    Supports:
        - Direct Dict input
        - YAML file loading
        - Inline rule definition
    """

    @staticmethod
    def from_dict(policy_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load policy from a dictionary.

        Expected format:
            {
                "id": "financial_prudence",
                "rules": [
                    {"id": "min_savings", "param": "savings", "operator": ">=", ...}
                ]
            }
        """
        # Validate structure
        if "rules" not in policy_dict:
            policy_dict["rules"] = []

        # Convert rule dicts to PolicyRule objects for validation
        validated_rules = []
        for r in policy_dict["rules"]:
            if isinstance(r, dict):
                # This will raise ValueError if invalid
                rule = PolicyRule(**r)
                validated_rules.append(rule)
            elif isinstance(r, PolicyRule):
                validated_rules.append(r)

        policy_dict["_validated_rules"] = validated_rules
        return policy_dict

    @staticmethod
    def from_yaml(yaml_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load policy from YAML file.

        Expected YAML format:
            id: financial_prudence
            rules:
              - id: min_savings
                param: savings
                operator: ">="
                value: 500
                message: "Insufficient savings"
                level: ERROR
        """
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            policy_dict = yaml.safe_load(f)

        return PolicyLoader.from_dict(policy_dict)

    @staticmethod
    def from_rules(rules: List[PolicyRule], policy_id: str = "inline") -> Dict[str, Any]:
        """
        Create policy from a list of PolicyRule objects.

        Useful for programmatic rule definition.
        """
        return {
            "id": policy_id,
            "rules": [
                {
                    "id": r.id,
                    "param": r.param,
                    "operator": r.operator,
                    "value": r.value,
                    "message": r.message,
                    "level": r.level,
                    "xai_hint": r.xai_hint,
                }
                for r in rules
            ],
            "_validated_rules": rules,
        }


def load_policy(source: Union[str, Path, Dict]) -> Dict[str, Any]:
    """
    Convenience function to load policy from any source.

    Args:
        source: YAML path, or policy dict

    Returns:
        Validated policy dictionary
    """
    if isinstance(source, dict):
        return PolicyLoader.from_dict(source)
    elif isinstance(source, (str, Path)):
        path = Path(source)
        if path.suffix in (".yaml", ".yml"):
            return PolicyLoader.from_yaml(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")
