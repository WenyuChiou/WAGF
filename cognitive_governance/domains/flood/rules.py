"""
Flood Domain Governance Rules.

Default PolicyRule sets for flood adaptation decisions.

These rules encode behavioral economics constraints:
- Affordability thresholds for adaptation actions
- Risk perception requirements
- Rational decision constraints

References:
- NFIP premium structures
- Elevation cost estimates (FEMA)
- Behavioral decision theory
"""

from typing import List, Dict, Any
from cognitive_governance.v1_prototype.types import PolicyRule


# =============================================================================
# Insurance Rules
# =============================================================================

INSURANCE_AFFORDABILITY_RULE = PolicyRule(
    id="insurance_affordability",
    param="savings",
    operator=">=",
    value=2000,
    message="Insufficient savings for flood insurance premium",
    level="ERROR",
    domain="flood",
    param_type="numeric",
    param_unit="USD",
    severity_score=0.8,
    literature_ref="NFIP average premium ~$700-1500/year",
    rationale="Agents need savings buffer for annual premium commitment",
)

INSURANCE_ZONE_RULE = PolicyRule(
    id="insurance_zone_requirement",
    param="flood_zone",
    operator="in",
    value=["AE", "A", "VE", "V"],
    message="NFIP insurance typically purchased in high-risk zones",
    level="WARNING",
    domain="flood",
    param_type="categorical",
    severity_score=0.5,
    literature_ref="FEMA flood zone requirements",
    rationale="Mortgage lenders require insurance in Special Flood Hazard Areas",
)

# =============================================================================
# Elevation Rules
# =============================================================================

ELEVATION_AFFORDABILITY_RULE = PolicyRule(
    id="elevation_affordability",
    param="savings",
    operator=">=",
    value=50000,
    message="Insufficient savings for home elevation ($50K-200K typical)",
    level="ERROR",
    domain="flood",
    param_type="numeric",
    param_unit="USD",
    severity_score=1.0,
    literature_ref="FEMA P-312 Homeowner's Guide",
    rationale="Home elevation requires substantial capital investment",
)

ELEVATION_INCOME_RULE = PolicyRule(
    id="elevation_income",
    param="income",
    operator=">=",
    value=50000,
    message="Elevation requires stable income for potential financing",
    level="WARNING",
    domain="flood",
    param_type="numeric",
    param_unit="USD",
    severity_score=0.6,
    literature_ref="Home improvement loan requirements",
    rationale="Banks require income verification for home improvement loans",
)

# =============================================================================
# Relocation Rules
# =============================================================================

RELOCATION_AFFORDABILITY_RULE = PolicyRule(
    id="relocation_affordability",
    param="savings",
    operator=">=",
    value=30000,
    message="Insufficient savings for relocation costs",
    level="ERROR",
    domain="flood",
    param_type="numeric",
    param_unit="USD",
    severity_score=1.0,
    literature_ref="Average moving costs and down payment requirements",
    rationale="Relocation requires moving costs + new housing down payment",
)

RELOCATION_RISK_RULE = PolicyRule(
    id="relocation_risk_threshold",
    param="risk_perception",
    operator=">=",
    value=0.6,
    message="Low risk perception unlikely to motivate relocation",
    level="WARNING",
    domain="flood",
    param_type="numeric",
    severity_score=0.4,
    literature_ref="Protection Motivation Theory",
    rationale="Major life decisions require high perceived threat",
)

# =============================================================================
# General Adaptation Rules
# =============================================================================

RATIONAL_ADAPTATION_RULE = PolicyRule(
    id="rational_adaptation",
    param="risk_perception",
    operator=">=",
    value=0.3,
    message="Very low risk perception inconsistent with protective action",
    level="WARNING",
    domain="flood",
    param_type="numeric",
    severity_score=0.3,
    literature_ref="Protection Motivation Theory",
    rationale="Some risk awareness needed to motivate protection",
)

TRUST_INFORMATION_RULE = PolicyRule(
    id="trust_information",
    param="trust",
    operator=">=",
    value=0.3,
    message="Very low trust may prevent action on flood warnings",
    level="WARNING",
    domain="flood",
    param_type="numeric",
    severity_score=0.4,
    literature_ref="Trust and risk communication literature",
    rationale="Trust in information sources affects response to warnings",
)


# =============================================================================
# Rule Collections
# =============================================================================

INSURANCE_RULES: List[PolicyRule] = [
    INSURANCE_AFFORDABILITY_RULE,
    INSURANCE_ZONE_RULE,
]

ELEVATION_RULES: List[PolicyRule] = [
    ELEVATION_AFFORDABILITY_RULE,
    ELEVATION_INCOME_RULE,
]

RELOCATION_RULES: List[PolicyRule] = [
    RELOCATION_AFFORDABILITY_RULE,
    RELOCATION_RISK_RULE,
]

GENERAL_RULES: List[PolicyRule] = [
    RATIONAL_ADAPTATION_RULE,
    TRUST_INFORMATION_RULE,
]

# All flood rules
FLOOD_RULES: List[PolicyRule] = (
    INSURANCE_RULES + ELEVATION_RULES + RELOCATION_RULES + GENERAL_RULES
)


def create_flood_policy(
    include_insurance: bool = True,
    include_elevation: bool = True,
    include_relocation: bool = True,
    include_general: bool = True,
) -> Dict[str, Any]:
    """
    Create a flood governance policy with selected rule sets.

    Args:
        include_insurance: Include insurance affordability rules
        include_elevation: Include elevation affordability rules
        include_relocation: Include relocation rules
        include_general: Include general adaptation rules

    Returns:
        Policy dict ready for PolicyEngine.verify()
    """
    rules = []

    if include_insurance:
        rules.extend(INSURANCE_RULES)
    if include_elevation:
        rules.extend(ELEVATION_RULES)
    if include_relocation:
        rules.extend(RELOCATION_RULES)
    if include_general:
        rules.extend(GENERAL_RULES)

    return {
        "domain": "flood",
        "rules": [r.__dict__ for r in rules],
    }


def get_rules_for_action(action: str) -> List[PolicyRule]:
    """
    Get relevant rules for a specific adaptation action.

    Args:
        action: Action type ("insurance", "elevation", "relocation")

    Returns:
        List of applicable PolicyRules
    """
    action_rules = {
        "insurance": INSURANCE_RULES + GENERAL_RULES,
        "elevate": ELEVATION_RULES + GENERAL_RULES,
        "elevation": ELEVATION_RULES + GENERAL_RULES,
        "relocate": RELOCATION_RULES + GENERAL_RULES,
        "relocation": RELOCATION_RULES + GENERAL_RULES,
    }
    return action_rules.get(action.lower(), GENERAL_RULES)
