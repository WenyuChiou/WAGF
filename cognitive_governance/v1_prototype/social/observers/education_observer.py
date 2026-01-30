"""Education domain social observer."""
from typing import Any, Dict, List, Optional
from ..observer import SocialObserver


class EducationObserver(SocialObserver):
    """
    Social observer for educational psychology domain.

    Neighbors can observe:
    - Educational milestones (graduation, enrollment)
    - School choice
    - NOT: grades, test scores, internal motivation
    """

    @property
    def domain(self) -> str:
        return "education"

    def get_observable_attributes(self, agent: Any) -> Dict[str, Any]:
        """Return education-relevant visible attributes."""
        attrs = {}

        if hasattr(agent, "enrolled_in_school"):
            attrs["enrolled"] = agent.enrolled_in_school
        if hasattr(agent, "school_name"):
            attrs["school_name"] = agent.school_name
        if hasattr(agent, "highest_degree"):
            attrs["highest_degree"] = agent.highest_degree
        if hasattr(agent, "currently_studying"):
            attrs["currently_studying"] = agent.currently_studying

        return attrs

    def get_visible_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """Return recent education-related visible actions."""
        actions = []

        if getattr(agent, "recently_graduated", False):
            actions.append({
                "action": "graduated",
                "description": f"{getattr(agent, 'id', 'Agent')} graduated",
            })

        if getattr(agent, "changed_major", False):
            actions.append({
                "action": "changed_major",
                "description": f"{getattr(agent, 'id', 'Agent')} changed their major",
            })

        if getattr(agent, "dropped_out", False):
            actions.append({
                "action": "dropped_out",
                "description": f"{getattr(agent, 'id', 'Agent')} dropped out of school",
            })

        return actions

    def get_gossip_content(
        self,
        agent: Any,
        memory: Optional[Any] = None
    ) -> Optional[str]:
        """Return education-related shareable content."""
        if hasattr(agent, "study_tip") and agent.study_tip:
            return agent.study_tip
        return None
