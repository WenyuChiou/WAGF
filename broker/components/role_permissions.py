from dataclasses import dataclass
from typing import Dict, Optional

FLOOD_ROLES: Dict[str, Dict] = {
    "government": {
        "allowed_skills": ["increase_subsidy", "decrease_subsidy", "maintain_subsidy", "outreach"],
        "can_read_state": ["community", "type", "spatial"],
        "can_modify": ["subsidy_rate", "mg_priority", "budget"],
        "artifact_type": "PolicyArtifact",
    },
    "insurance": {
        "allowed_skills": ["raise_premium", "lower_premium", "maintain_premium"],
        "can_read_state": ["community", "type"],
        "can_modify": ["premium_rate", "payout_ratio", "risk_pool"],
        "artifact_type": "MarketArtifact",
    },
    "household": {
        "allowed_skills": [
            "buy_insurance", "buy_contents_insurance", "elevate_house",
            "relocate", "do_nothing", "buyout_program",
        ],
        "can_read_state": ["neighbors", "community"],
        "can_modify": ["elevated", "has_insurance", "relocated"],
        "artifact_type": "HouseholdIntention",
    },
}


@dataclass
class PermissionResult:
    allowed: bool
    reason: str = ""


class RoleEnforcer:
    def __init__(self, roles: Optional[Dict[str, Dict]] = None):
        self.roles = roles or FLOOD_ROLES

    def _get_role(self, agent_type: str) -> Optional[Dict]:
        return self.roles.get(agent_type)

    def check_skill_permission(self, agent_type: str, skill: str) -> PermissionResult:
        role = self._get_role(agent_type)
        if not role:
            return PermissionResult(False, f"Unknown agent_type: {agent_type}")
        if skill in role.get("allowed_skills", []):
            return PermissionResult(True, "")
        return PermissionResult(False, f"Skill not allowed: {skill}")

    def check_state_access(self, agent_type: str, scope: str) -> PermissionResult:
        role = self._get_role(agent_type)
        if not role:
            return PermissionResult(False, f"Unknown agent_type: {agent_type}")
        if scope in role.get("can_read_state", []):
            return PermissionResult(True, "")
        return PermissionResult(False, f"Scope not allowed: {scope}")

    def check_state_mutation(self, agent_type: str, field: str) -> PermissionResult:
        role = self._get_role(agent_type)
        if not role:
            return PermissionResult(False, f"Unknown agent_type: {agent_type}")
        if field in role.get("can_modify", []):
            return PermissionResult(True, "")
        return PermissionResult(False, f"Field not allowed: {field}")
