"""
Education Domain Governance Rules.

Default PolicyRule sets for educational decisions.

References:
- Educational attainment research
- Human capital theory
- Educational psychology
"""

from typing import List, Dict, Any
from cognitive_governance.v1_prototype.types import PolicyRule


# =============================================================================
# Academic Progress Rules
# =============================================================================

GPA_FOR_GRADUATION_RULE = PolicyRule(
    id="gpa_for_graduation",
    param="gpa",
    operator=">=",
    value=2.0,
    message="GPA below graduation requirement",
    level="ERROR",
    domain="education",
    param_type="numeric",
    severity_score=1.0,
    literature_ref="Standard graduation requirements",
    rationale="Minimum GPA required for degree completion",
)

GPA_FOR_GRADUATE_SCHOOL_RULE = PolicyRule(
    id="gpa_for_graduate_school",
    param="gpa",
    operator=">=",
    value=3.0,
    message="GPA below typical graduate school threshold",
    level="WARNING",
    domain="education",
    param_type="numeric",
    severity_score=0.7,
    literature_ref="Graduate admissions standards",
    rationale="Competitive graduate programs require strong GPA",
)

# =============================================================================
# Motivation Rules
# =============================================================================

MOTIVATION_FOR_ADVANCEMENT_RULE = PolicyRule(
    id="motivation_for_advancement",
    param="motivation",
    operator=">=",
    value=0.4,
    message="Low motivation may hinder educational advancement",
    level="WARNING",
    domain="education",
    param_type="numeric",
    severity_score=0.5,
    literature_ref="Self-Determination Theory",
    rationale="Intrinsic motivation predicts educational success",
)

# =============================================================================
# Financial Rules (Education Context)
# =============================================================================

DEBT_LIMIT_RULE = PolicyRule(
    id="student_debt_limit",
    param="student_debt",
    operator="<=",
    value=100000,
    message="Student debt approaching federal loan limits",
    level="WARNING",
    domain="education",
    param_type="numeric",
    param_unit="USD",
    severity_score=0.6,
    literature_ref="Federal student loan limits",
    rationale="High debt burden may outweigh educational returns",
)

INCOME_FOR_SELF_FUNDING_RULE = PolicyRule(
    id="income_for_self_funding",
    param="family_income",
    operator=">=",
    value=50000,
    message="May qualify for financial aid",
    level="WARNING",
    domain="education",
    param_type="numeric",
    param_unit="USD",
    severity_score=0.3,
    literature_ref="FAFSA thresholds",
    rationale="Lower income qualifies for need-based aid",
)

# =============================================================================
# Degree Progression Rules
# =============================================================================

PREREQUISITE_DEGREE_RULE = PolicyRule(
    id="prerequisite_degree",
    param="degree_level",
    operator="in",
    value=["bachelors", "masters", "doctorate"],
    message="Bachelor's degree typically required for graduate school",
    level="ERROR",
    domain="education",
    param_type="categorical",
    severity_score=0.9,
    literature_ref="Graduate admission requirements",
    rationale="Most graduate programs require undergraduate degree",
)

# =============================================================================
# Employment Rules
# =============================================================================

EMPLOYMENT_BALANCE_RULE = PolicyRule(
    id="employment_balance",
    param="employment_status",
    operator="not_in",
    value=["full_time"],
    message="Full-time work may conflict with full-time study",
    level="WARNING",
    domain="education",
    param_type="categorical",
    severity_score=0.4,
    literature_ref="Work-study balance research",
    rationale="Full-time work associated with lower completion rates",
)


# =============================================================================
# Rule Collections
# =============================================================================

ACADEMIC_RULES: List[PolicyRule] = [
    GPA_FOR_GRADUATION_RULE,
    GPA_FOR_GRADUATE_SCHOOL_RULE,
    MOTIVATION_FOR_ADVANCEMENT_RULE,
]

FINANCIAL_RULES: List[PolicyRule] = [
    DEBT_LIMIT_RULE,
    INCOME_FOR_SELF_FUNDING_RULE,
]

PROGRESSION_RULES: List[PolicyRule] = [
    PREREQUISITE_DEGREE_RULE,
]

EMPLOYMENT_RULES: List[PolicyRule] = [
    EMPLOYMENT_BALANCE_RULE,
]

# All education rules
EDUCATION_RULES: List[PolicyRule] = (
    ACADEMIC_RULES + FINANCIAL_RULES + PROGRESSION_RULES + EMPLOYMENT_RULES
)


def create_education_policy(
    include_academic: bool = True,
    include_financial: bool = True,
    include_progression: bool = True,
    include_employment: bool = True,
) -> Dict[str, Any]:
    """
    Create an education governance policy with selected rule sets.

    Args:
        include_academic: Include academic performance rules
        include_financial: Include financial rules
        include_progression: Include degree progression rules
        include_employment: Include employment rules

    Returns:
        Policy dict ready for PolicyEngine.verify()
    """
    rules = []

    if include_academic:
        rules.extend(ACADEMIC_RULES)
    if include_financial:
        rules.extend(FINANCIAL_RULES)
    if include_progression:
        rules.extend(PROGRESSION_RULES)
    if include_employment:
        rules.extend(EMPLOYMENT_RULES)

    return {
        "domain": "education",
        "rules": [r.__dict__ for r in rules],
    }


def get_rules_for_action(action: str) -> List[PolicyRule]:
    """
    Get relevant rules for a specific educational action.

    Args:
        action: Action type ("enroll", "graduate", "advance", etc.)

    Returns:
        List of applicable PolicyRules
    """
    action_rules = {
        "enroll": FINANCIAL_RULES + PROGRESSION_RULES,
        "graduate": ACADEMIC_RULES,
        "advance": ACADEMIC_RULES + PROGRESSION_RULES,
        "drop_out": [],
        "change_major": ACADEMIC_RULES,
    }
    return action_rules.get(action.lower(), ACADEMIC_RULES)
