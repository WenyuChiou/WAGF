"""
Social Validator - Neighbor influence and Community norms.

IMPORTANT: Social rules are WARNING only, never blocking.
They log social context but do not reject decisions.

Validates:
- Neighbor adaptation pressure (herd behavior observation)
- Community norm deviations (outlier detection)

Domain-specific built-in checks are injected via ``builtin_checks``.
Default is empty (domain-agnostic).  Flood-domain checks live in
``examples/governed_flood/validators/flood_validators.py``.
"""
from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


class SocialValidator(BaseValidator):
    """
    Validates social context: neighbor influence and community norms.

    IMPORTANT: This validator only produces WARNINGs, never ERRORs.
    Social pressure is logged for audit but does not block decisions.

    Pass domain-specific ``builtin_checks`` for flood, irrigation, etc.
    Default is empty (YAML rules only).
    """

    def __init__(self, builtin_checks: Optional[List[BuiltinCheck]] = None):
        super().__init__(builtin_checks=builtin_checks)

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Empty — domain checks injected via validate_all(domain=...)."""
        return []

    @property
    def category(self) -> str:
        return "social"

    def validate(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate social rules (WARNING only).

        Social YAML rules are always force-downgraded to WARNING.
        Then domain-specific built-in checks run via the base class.

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules
            context: Must include 'social_context' with neighbor data

        Returns:
            List of ValidationResult objects (all valid=True for warnings)
        """
        results = []
        social_context = context.get("social_context", {})

        # --- YAML-driven social rules (always WARNING) ---
        social_rules = [r for r in rules if r.category == "social"]

        for rule in social_rules:
            if rule.evaluate(skill_name, context):
                # Social rules always produce warnings, never errors
                results.append(ValidationResult(
                    valid=True,  # Always valid - just logging
                    validator_name="SocialValidator",
                    errors=[],
                    warnings=[rule.message],
                    metadata={
                        "rule_id": rule.id,
                        "category": "social",
                        "subcategory": rule.subcategory,
                        "skill_proposed": skill_name,
                        "level": "WARNING",  # Force WARNING level
                    }
                ))

        # --- Domain-specific built-in checks ---
        for check in self._builtin_checks:
            results.extend(check(skill_name, rules, context))

        return results
