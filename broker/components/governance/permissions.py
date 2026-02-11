"""
Generic role-based permission enforcement for multi-agent systems.

Provides:
- RoleEnforcer: Validates skill/state permissions per agent type
- PermissionResult: Outcome of a permission check

Roles are injected via constructor (no hardcoded defaults).
Domain-specific role configs (e.g. FLOOD_ROLES) should live in the
domain module (examples/multi_agent/flood/protocols/role_config.py).

Reference: Task-058C (Drift Detection & Social Norms)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


@dataclass
class PermissionResult:
    """Outcome of a permission check.

    Attributes:
        allowed: Whether the action is permitted
        reason: Explanation (especially if denied)
        agent_type: The agent type that was checked
        action: The skill/scope/field that was checked
    """
    allowed: bool
    reason: str
    agent_type: str
    action: str


class RoleEnforcer:
    """Validates skill and state access permissions per agent type.

    Roles dict schema:
    {
        "agent_type_name": {
            "allowed_skills": ["skill1", "skill2", ...],
            "readable_scopes": ["global", "regional", ...],
            "writable_fields": ["field1", "field2", ...],
        },
        ...
    }

    Args:
        roles: Mapping of agent_type -> permission config.
               No default — must be provided by domain module.
    """

    def __init__(self, roles: Dict[str, Dict[str, Any]]):
        self.roles = roles

    def check_skill_permission(
        self, agent_type: str, skill: str,
    ) -> PermissionResult:
        """Check if an agent type is allowed to use a specific skill."""
        role = self.roles.get(agent_type)
        if role is None:
            return PermissionResult(
                allowed=False,
                reason=f"Unknown agent type: '{agent_type}'",
                agent_type=agent_type,
                action=skill,
            )

        allowed_skills: List[str] = role.get("allowed_skills", [])
        if skill in allowed_skills:
            return PermissionResult(
                allowed=True, reason="Skill permitted",
                agent_type=agent_type, action=skill,
            )

        return PermissionResult(
            allowed=False,
            reason=f"Skill '{skill}' not in allowed list for '{agent_type}': "
                   f"{allowed_skills}",
            agent_type=agent_type,
            action=skill,
        )

    def check_state_access(
        self, agent_type: str, scope: str,
    ) -> PermissionResult:
        """Check if an agent type can read a specific state scope."""
        role = self.roles.get(agent_type)
        if role is None:
            return PermissionResult(
                allowed=False,
                reason=f"Unknown agent type: '{agent_type}'",
                agent_type=agent_type,
                action=scope,
            )

        readable: List[str] = role.get("readable_scopes", [])
        if scope in readable:
            return PermissionResult(
                allowed=True, reason="Scope readable",
                agent_type=agent_type, action=scope,
            )

        return PermissionResult(
            allowed=False,
            reason=f"Scope '{scope}' not readable for '{agent_type}': {readable}",
            agent_type=agent_type,
            action=scope,
        )

    def check_state_mutation(
        self, agent_type: str, field_name: str,
    ) -> PermissionResult:
        """Check if an agent type can write/mutate a specific state field."""
        role = self.roles.get(agent_type)
        if role is None:
            return PermissionResult(
                allowed=False,
                reason=f"Unknown agent type: '{agent_type}'",
                agent_type=agent_type,
                action=field_name,
            )

        writable: List[str] = role.get("writable_fields", [])
        if field_name in writable:
            return PermissionResult(
                allowed=True, reason="Field writable",
                agent_type=agent_type, action=field_name,
            )

        return PermissionResult(
            allowed=False,
            reason=f"Field '{field_name}' not writable for '{agent_type}': {writable}",
            agent_type=agent_type,
            action=field_name,
        )

    def get_allowed_skills(self, agent_type: str) -> List[str]:
        """Return the list of allowed skills for an agent type."""
        role = self.roles.get(agent_type, {})
        return list(role.get("allowed_skills", []))
