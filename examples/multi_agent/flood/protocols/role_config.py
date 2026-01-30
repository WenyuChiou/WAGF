"""
Flood-domain role permission configuration.

Defines FLOOD_ROLES for use with broker.components.role_permissions.RoleEnforcer.

Usage:
    from examples.multi_agent.flood.ma_role_config import FLOOD_ROLES
    enforcer = RoleEnforcer(roles=FLOOD_ROLES)

Reference: Task-058C (Drift Detection & Social Norms)
"""

FLOOD_ROLES = {
    "government": {
        "allowed_skills": [
            "increase_subsidy",
            "decrease_subsidy",
            "set_policy",
            "allocate_budget",
            "announce_policy",
        ],
        "readable_scopes": ["global", "regional", "community"],
        "writable_fields": [
            "subsidy_rate",
            "budget_remaining",
            "policy_announcement",
            "target_adoption_rate",
        ],
    },
    "insurance": {
        "allowed_skills": [
            "raise_premium",
            "lower_premium",
            "adjust_payout",
            "assess_risk",
            "issue_policy",
        ],
        "readable_scopes": ["global", "regional", "policyholders"],
        "writable_fields": [
            "premium_rate",
            "payout_ratio",
            "solvency_ratio",
            "risk_assessment",
        ],
    },
    "household": {
        "allowed_skills": [
            "buy_insurance",
            "drop_insurance",
            "elevate_house",
            "relocate",
            "do_nothing",
            "invest_in_mitigation",
        ],
        "readable_scopes": ["personal", "neighbors"],
        "writable_fields": [
            "has_insurance",
            "elevated",
            "relocated",
        ],
    },
}
