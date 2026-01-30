"""
Finance Domain Governance Rules.

Default PolicyRule sets for financial decisions.

References:
- CFPB Consumer Financial Protection Bureau
- Behavioral economics literature
- Financial planning best practices
"""

from typing import List, Dict, Any
from cognitive_governance.v1_prototype.types import PolicyRule


# =============================================================================
# Savings Rules
# =============================================================================

EMERGENCY_FUND_RULE = PolicyRule(
    id="emergency_fund",
    param="savings_ratio",
    operator=">=",
    value=0.3,
    message="Insufficient emergency fund for major financial decisions",
    level="WARNING",
    domain="finance",
    param_type="numeric",
    severity_score=0.7,
    literature_ref="CFPB recommends 3-6 months expenses",
    rationale="Emergency fund provides buffer against financial shocks",
)

SAVINGS_BEFORE_INVESTING_RULE = PolicyRule(
    id="savings_before_investing",
    param="savings_ratio",
    operator=">=",
    value=0.2,
    message="Build emergency savings before aggressive investing",
    level="WARNING",
    domain="finance",
    param_type="numeric",
    severity_score=0.6,
    literature_ref="Personal finance best practices",
    rationale="Emergency fund should precede market investments",
)

# =============================================================================
# Debt Rules
# =============================================================================

DEBT_RATIO_RULE = PolicyRule(
    id="debt_ratio_limit",
    param="debt_ratio",
    operator="<=",
    value=0.43,
    message="Debt-to-income ratio too high for additional borrowing",
    level="ERROR",
    domain="finance",
    param_type="numeric",
    severity_score=0.9,
    literature_ref="Qualified Mortgage rule (43% DTI limit)",
    rationale="High DTI indicates financial stress and default risk",
)

MANAGEABLE_DEBT_RULE = PolicyRule(
    id="manageable_debt",
    param="debt_ratio",
    operator="<=",
    value=0.35,
    message="Debt level concerning - consider debt reduction first",
    level="WARNING",
    domain="finance",
    param_type="numeric",
    severity_score=0.5,
    literature_ref="Financial planning guidelines",
    rationale="Lower debt allows more financial flexibility",
)

# =============================================================================
# Credit Rules
# =============================================================================

CREDIT_FOR_MAJOR_PURCHASE_RULE = PolicyRule(
    id="credit_for_major_purchase",
    param="credit_score",
    operator=">=",
    value=670,
    message="Credit score may limit financing options",
    level="WARNING",
    domain="finance",
    param_type="numeric",
    param_unit="points",
    severity_score=0.6,
    literature_ref="Prime lending thresholds",
    rationale="Higher credit scores get better interest rates",
)

CREDIT_FOR_MORTGAGE_RULE = PolicyRule(
    id="credit_for_mortgage",
    param="credit_score",
    operator=">=",
    value=620,
    message="Credit score below conventional mortgage threshold",
    level="ERROR",
    domain="finance",
    param_type="numeric",
    param_unit="points",
    severity_score=0.8,
    literature_ref="FHA and conventional mortgage requirements",
    rationale="Minimum credit score for most mortgage products",
)

# =============================================================================
# Investment Rules
# =============================================================================

RISK_ALIGNMENT_RULE = PolicyRule(
    id="risk_alignment",
    param="risk_tolerance",
    operator=">=",
    value=0.5,
    message="Conservative risk tolerance inconsistent with aggressive investment",
    level="WARNING",
    domain="finance",
    param_type="numeric",
    severity_score=0.4,
    literature_ref="Investment suitability requirements",
    rationale="Investment strategy should match risk tolerance",
)

LITERACY_FOR_COMPLEX_PRODUCTS_RULE = PolicyRule(
    id="literacy_for_complex_products",
    param="financial_literacy",
    operator=">=",
    value=0.5,
    message="Limited financial literacy for complex investment products",
    level="WARNING",
    domain="finance",
    param_type="numeric",
    severity_score=0.5,
    literature_ref="Consumer protection guidelines",
    rationale="Understanding is necessary for informed decisions",
)


# =============================================================================
# Rule Collections
# =============================================================================

SAVINGS_RULES: List[PolicyRule] = [
    EMERGENCY_FUND_RULE,
    SAVINGS_BEFORE_INVESTING_RULE,
]

DEBT_RULES: List[PolicyRule] = [
    DEBT_RATIO_RULE,
    MANAGEABLE_DEBT_RULE,
]

CREDIT_RULES: List[PolicyRule] = [
    CREDIT_FOR_MAJOR_PURCHASE_RULE,
    CREDIT_FOR_MORTGAGE_RULE,
]

INVESTMENT_RULES: List[PolicyRule] = [
    RISK_ALIGNMENT_RULE,
    LITERACY_FOR_COMPLEX_PRODUCTS_RULE,
]

# All finance rules
FINANCE_RULES: List[PolicyRule] = (
    SAVINGS_RULES + DEBT_RULES + CREDIT_RULES + INVESTMENT_RULES
)


def create_finance_policy(
    include_savings: bool = True,
    include_debt: bool = True,
    include_credit: bool = True,
    include_investment: bool = True,
) -> Dict[str, Any]:
    """
    Create a finance governance policy with selected rule sets.

    Args:
        include_savings: Include savings rules
        include_debt: Include debt rules
        include_credit: Include credit rules
        include_investment: Include investment rules

    Returns:
        Policy dict ready for PolicyEngine.verify()
    """
    rules = []

    if include_savings:
        rules.extend(SAVINGS_RULES)
    if include_debt:
        rules.extend(DEBT_RULES)
    if include_credit:
        rules.extend(CREDIT_RULES)
    if include_investment:
        rules.extend(INVESTMENT_RULES)

    return {
        "domain": "finance",
        "rules": [r.__dict__ for r in rules],
    }


def get_rules_for_action(action: str) -> List[PolicyRule]:
    """
    Get relevant rules for a specific financial action.

    Args:
        action: Action type ("invest", "borrow", "save", etc.)

    Returns:
        List of applicable PolicyRules
    """
    action_rules = {
        "invest": SAVINGS_RULES + INVESTMENT_RULES,
        "borrow": DEBT_RULES + CREDIT_RULES,
        "mortgage": DEBT_RULES + CREDIT_RULES,
        "save": SAVINGS_RULES,
        "loan": DEBT_RULES + CREDIT_RULES,
    }
    return action_rules.get(action.lower(), SAVINGS_RULES)
