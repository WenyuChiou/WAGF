"""
Personal Validator - Financial and Cognitive constraints.

Validates:
- Financial affordability (savings vs costs, income limits)
- Cognitive capability (extreme states blocking options)

Domain-specific built-in checks (e.g. flood elevation affordability) are
injected via ``builtin_checks``.  When *None*, flood-domain defaults are
used for backward compatibility.
"""
from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


# ---------------------------------------------------------------------------
# Flood-domain built-in checks
# ---------------------------------------------------------------------------

def flood_elevation_affordability(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Check if agent can afford house elevation (flood domain).

    Only fires for ``elevate_house`` and when no explicit YAML rule
    with id prefix ``elevation_affordability`` exists.
    """
    if skill_name != "elevate_house":
        return []

    # Skip if an explicit YAML rule already covers this
    if any(r.id.startswith("elevation_affordability") for r in rules if r.category == "personal"):
        return []

    state = context.get("state", {})
    savings = state.get("savings", 0)
    elevation_cost = state.get("elevation_cost", 50000)
    subsidy_rate = state.get("subsidy_rate", 0.0)
    effective_cost = elevation_cost * (1 - subsidy_rate)

    if savings < effective_cost:
        return [ValidationResult(
            valid=False,
            validator_name="PersonalValidator",
            errors=[f"Insufficient funds: savings ${savings:.0f} < cost ${effective_cost:.0f}"],
            warnings=[],
            metadata={
                "rule_id": "builtin_elevation_affordability",
                "category": "personal",
                "subcategory": "financial",
                "savings": savings,
                "effective_cost": effective_cost
            }
        )]

    return []


# Registry of flood-domain checks for this category
FLOOD_PERSONAL_CHECKS: List[BuiltinCheck] = [flood_elevation_affordability]


# ---------------------------------------------------------------------------
# Validator class
# ---------------------------------------------------------------------------

class PersonalValidator(BaseValidator):
    """
    Validates personal constraints: financial affordability and cognitive capability.

    Built-in checks default to flood domain (elevation affordability).
    Pass ``builtin_checks=[]`` to disable, or supply domain-specific checks.
    """

    def __init__(self, builtin_checks: Optional[List[BuiltinCheck]] = None):
        super().__init__(builtin_checks=builtin_checks)

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Flood-domain defaults for backward compatibility."""
        return list(FLOOD_PERSONAL_CHECKS)

    @property
    def category(self) -> str:
        return "personal"
