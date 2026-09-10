"""
Flood-domain role permission configuration.

Defines FLOOD_ROLES config data. Org-3 note (2026-09): the
`RoleEnforcer` it was written for (`broker/components/governance/permissions.py`)
was never wired into any production pipeline and was removed as
unused dead code; FLOOD_ROLES itself is kept as config data in case a
future consumer needs it.

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
            "improve_crs",
            "reduce_crs",
            "maintain_crs",
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
