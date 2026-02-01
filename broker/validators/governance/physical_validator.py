"""
Physical Validator - State preconditions and action immutability.

Validates:
- State preconditions (already completed irreversible actions)
- Role restrictions (cannot modify property without ownership)
- Action immutability (irreversible decisions)

Domain-specific built-in checks (e.g. flood elevation/relocation state) are
injected via ``builtin_checks``.  When *None*, flood-domain defaults are
used for backward compatibility.

Design note — insurance renewal:
    ``buy_insurance`` is deliberately NOT checked for "already insured".
    Insurance is an annual renewable action (expires each year if not
    renewed).  Unlike elevation and relocation (irreversible one-time
    actions), insurance renewal is expected rational behavior.  See
    ``ResearchSimulation.execute_skill()`` for annual expiry logic.
"""
from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


# ---------------------------------------------------------------------------
# Flood-domain built-in checks
# ---------------------------------------------------------------------------

def flood_already_elevated(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block elevation if house is already elevated (flood domain)."""
    if skill_name != "elevate_house":
        return []
    state = context.get("state", {})
    if not state.get("elevated", False):
        return []
    return [ValidationResult(
        valid=False,
        validator_name="PhysicalValidator",
        errors=["House is already elevated - cannot elevate again"],
        warnings=[],
        metadata={
            "rule_id": "builtin_already_elevated",
            "category": "physical",
            "subcategory": "state",
            "hallucination_type": "physical",
            "current_state": "elevated"
        }
    )]


def flood_already_relocated(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block property actions after relocation (flood domain)."""
    state = context.get("state", {})
    if not state.get("relocated", False):
        return []
    restricted_after_relocation = {
        "relocate", "elevate_house", "buy_insurance", "buyout"
    }
    if skill_name not in restricted_after_relocation:
        return []
    return [ValidationResult(
        valid=False,
        validator_name="PhysicalValidator",
        errors=[f"Household has relocated - '{skill_name}' is no longer applicable"],
        warnings=[],
        metadata={
            "rule_id": "builtin_already_relocated",
            "category": "physical",
            "subcategory": "state",
            "hallucination_type": "physical",
            "current_state": "relocated"
        }
    )]


def flood_renter_restriction(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block property modifications for renters (flood domain)."""
    state = context.get("state", {})
    is_renter = state.get("tenure", "Owner").lower() == "renter"
    if not is_renter:
        return []
    owner_only_actions = {"elevate_house", "buyout"}
    if skill_name not in owner_only_actions:
        return []
    return [ValidationResult(
        valid=False,
        validator_name="PhysicalValidator",
        errors=[f"Renters cannot perform '{skill_name}' - property modification requires ownership"],
        warnings=[],
        metadata={
            "rule_id": "builtin_renter_restriction",
            "category": "physical",
            "subcategory": "state",
            "tenure": "renter",
            "restricted_action": skill_name
        }
    )]


# Registry of flood-domain checks for this category
FLOOD_PHYSICAL_CHECKS: List[BuiltinCheck] = [
    flood_already_elevated,
    flood_already_relocated,
    flood_renter_restriction,
]


# ---------------------------------------------------------------------------
# Validator class
# ---------------------------------------------------------------------------

class PhysicalValidator(BaseValidator):
    """
    Validates physical state: preconditions and immutable states.

    Built-in checks default to flood domain (elevation, relocation, renter).
    Pass ``builtin_checks=[]`` to disable, or supply domain-specific checks.
    """

    def __init__(self, builtin_checks: Optional[List[BuiltinCheck]] = None):
        super().__init__(builtin_checks=builtin_checks)

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Flood-domain defaults for backward compatibility."""
        return list(FLOOD_PHYSICAL_CHECKS)

    @property
    def category(self) -> str:
        return "physical"
