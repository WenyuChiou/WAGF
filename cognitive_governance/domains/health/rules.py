"""
Health Domain Governance Rules.

Default PolicyRule sets for health behavior decisions.

References:
- Transtheoretical Model (TTM)
- Health Belief Model
- Social Cognitive Theory
"""

from typing import List, Dict, Any
from cognitive_governance.v1_prototype.types import PolicyRule


# =============================================================================
# Self-Efficacy Rules
# =============================================================================

SELF_EFFICACY_FOR_CHANGE_RULE = PolicyRule(
    id="self_efficacy_for_change",
    param="self_efficacy",
    operator=">=",
    value=0.4,
    message="Low self-efficacy may hinder behavior change",
    level="WARNING",
    domain="health",
    param_type="numeric",
    severity_score=0.6,
    literature_ref="Bandura Self-Efficacy Theory",
    rationale="Self-efficacy predicts successful behavior change",
)

# =============================================================================
# Stage of Change Rules
# =============================================================================

READY_FOR_ACTION_RULE = PolicyRule(
    id="ready_for_action",
    param="stage_of_change",
    operator="in",
    value=["preparation", "action", "maintenance"],
    message="Not yet ready for active behavior change",
    level="WARNING",
    domain="health",
    param_type="categorical",
    severity_score=0.5,
    literature_ref="Transtheoretical Model",
    rationale="Action-oriented interventions need readiness",
)

# =============================================================================
# Stress Rules
# =============================================================================

STRESS_MANAGEMENT_RULE = PolicyRule(
    id="stress_management",
    param="stress_level",
    operator="<=",
    value=0.7,
    message="High stress may impair health behavior adherence",
    level="WARNING",
    domain="health",
    param_type="numeric",
    severity_score=0.5,
    literature_ref="Stress and health behavior literature",
    rationale="Chronic stress undermines health behaviors",
)

# =============================================================================
# BMI Rules
# =============================================================================

BMI_MEDICAL_GUIDANCE_RULE = PolicyRule(
    id="bmi_medical_guidance",
    param="bmi",
    operator="<=",
    value=30.0,
    message="BMI suggests need for medical guidance on exercise",
    level="WARNING",
    domain="health",
    param_type="numeric",
    param_unit="kg/m2",
    severity_score=0.4,
    literature_ref="ACSM Exercise Guidelines",
    rationale="Higher BMI may require modified exercise approach",
)

# =============================================================================
# Smoking Rules
# =============================================================================

SMOKING_CESSATION_SUPPORT_RULE = PolicyRule(
    id="smoking_cessation_support",
    param="smoking_status",
    operator="not_in",
    value=["smoker"],
    message="Active smokers benefit from cessation support",
    level="WARNING",
    domain="health",
    param_type="categorical",
    severity_score=0.3,
    literature_ref="CDC Smoking Cessation Guidelines",
    rationale="Smoking cessation improves all health outcomes",
)

# =============================================================================
# Activity Rules
# =============================================================================

GRADUAL_ACTIVITY_INCREASE_RULE = PolicyRule(
    id="gradual_activity_increase",
    param="activity_level",
    operator="not_in",
    value=["very_active"],
    message="Consider gradual increase to avoid injury",
    level="WARNING",
    domain="health",
    param_type="categorical",
    severity_score=0.3,
    literature_ref="CDC Physical Activity Guidelines",
    rationale="Sudden activity increases risk injury",
)

# =============================================================================
# Chronic Condition Rules
# =============================================================================

CHRONIC_CONDITION_AWARENESS_RULE = PolicyRule(
    id="chronic_condition_awareness",
    param="chronic_condition",
    operator="in",
    value=["none"],
    message="Chronic condition requires medical consultation before changes",
    level="WARNING",
    domain="health",
    param_type="categorical",
    severity_score=0.6,
    literature_ref="Chronic disease management guidelines",
    rationale="Behavior changes should account for existing conditions",
)


# =============================================================================
# Rule Collections
# =============================================================================

READINESS_RULES: List[PolicyRule] = [
    SELF_EFFICACY_FOR_CHANGE_RULE,
    READY_FOR_ACTION_RULE,
    STRESS_MANAGEMENT_RULE,
]

PHYSICAL_RULES: List[PolicyRule] = [
    BMI_MEDICAL_GUIDANCE_RULE,
    GRADUAL_ACTIVITY_INCREASE_RULE,
]

SMOKING_RULES: List[PolicyRule] = [
    SMOKING_CESSATION_SUPPORT_RULE,
]

CONDITION_RULES: List[PolicyRule] = [
    CHRONIC_CONDITION_AWARENESS_RULE,
]

# All health rules
HEALTH_RULES: List[PolicyRule] = (
    READINESS_RULES + PHYSICAL_RULES + SMOKING_RULES + CONDITION_RULES
)


def create_health_policy(
    include_readiness: bool = True,
    include_physical: bool = True,
    include_smoking: bool = True,
    include_condition: bool = True,
) -> Dict[str, Any]:
    """
    Create a health governance policy with selected rule sets.

    Args:
        include_readiness: Include behavior change readiness rules
        include_physical: Include physical activity rules
        include_smoking: Include smoking cessation rules
        include_condition: Include chronic condition rules

    Returns:
        Policy dict ready for PolicyEngine.verify()
    """
    rules = []

    if include_readiness:
        rules.extend(READINESS_RULES)
    if include_physical:
        rules.extend(PHYSICAL_RULES)
    if include_smoking:
        rules.extend(SMOKING_RULES)
    if include_condition:
        rules.extend(CONDITION_RULES)

    return {
        "domain": "health",
        "rules": [r.__dict__ for r in rules],
    }


def get_rules_for_action(action: str) -> List[PolicyRule]:
    """
    Get relevant rules for a specific health action.

    Args:
        action: Action type ("exercise", "quit_smoking", "diet", etc.)

    Returns:
        List of applicable PolicyRules
    """
    action_rules = {
        "exercise": READINESS_RULES + PHYSICAL_RULES + CONDITION_RULES,
        "quit_smoking": READINESS_RULES + SMOKING_RULES,
        "diet": READINESS_RULES + CONDITION_RULES,
        "weight_loss": READINESS_RULES + PHYSICAL_RULES + CONDITION_RULES,
    }
    return action_rules.get(action.lower(), READINESS_RULES)
