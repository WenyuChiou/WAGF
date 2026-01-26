"""
Domain-Specific Reflection Templates.

Provides structured prompts and parsing for agent reflection across domains.
Each template is tailored to the specific decision context of its domain.

Usage:
    >>> from governed_ai_sdk.v1_prototype.reflection import get_reflection_template
    >>> template = get_reflection_template("flood")
    >>> prompt = template.generate_prompt("agent_001", memories, context)
    >>> insight = template.parse_response(llm_response, memories, context)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .insight import ReflectionInsight


class ReflectionTemplate(ABC):
    """
    Abstract base for domain-specific reflection prompts.

    Each domain template provides:
    1. A specialized prompt structure for that domain
    2. Parsing logic to extract structured insights from LLM responses
    3. Domain-specific tags and importance scoring
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the domain name."""
        pass

    @property
    def name(self) -> str:
        """Return template name for tracing."""
        return f"{self.domain}_reflection"

    @abstractmethod
    def generate_prompt(
        self,
        agent_id: str,
        memories: List[str],
        context: Dict[str, Any]
    ) -> str:
        """
        Generate reflection prompt for LLM.

        Args:
            agent_id: Unique agent identifier
            memories: List of memory content strings to reflect on
            context: Current context (year, state, etc.)

        Returns:
            Formatted prompt string for LLM
        """
        pass

    @abstractmethod
    def parse_response(
        self,
        response: str,
        memories: List[str],
        context: Dict[str, Any]
    ) -> ReflectionInsight:
        """
        Parse LLM response into structured insight.

        Args:
            response: Raw LLM response text
            memories: Original input memories
            context: Original context

        Returns:
            ReflectionInsight instance
        """
        pass

    def get_focus_areas(self) -> List[str]:
        """Return domain-specific focus areas for reflection."""
        return ["patterns", "lessons_learned", "future_actions"]


class GenericReflectionTemplate(ReflectionTemplate):
    """Generic template for domains without specific implementation."""

    @property
    def domain(self) -> str:
        return "generic"

    def generate_prompt(self, agent_id, memories, context) -> str:
        period = context.get("period", "recent time")
        memory_list = "\n".join(f"- {m}" for m in memories[:10])

        return f"""As {agent_id}, reflect on your experiences from {period}.

Your memories:
{memory_list}

Consider:
1. What patterns do you notice in your experiences?
2. What lessons have you learned?
3. What would you do differently in the future?

Provide a concise 2-3 sentence insight that captures the most important lesson."""

    def parse_response(self, response, memories, context) -> ReflectionInsight:
        summary = response.strip()
        if len(summary) > 500:
            summary = summary[:500] + "..."

        return ReflectionInsight(
            summary=summary,
            source_memories=memories[:5],
            importance=0.75,
            domain="generic",
            tags=["reflection", "general"],
        )


class FloodReflectionTemplate(ReflectionTemplate):
    """
    Flood domain: focus on adaptation lessons, risk patterns.

    Emphasizes:
    - Flood damage experiences and emotional impact
    - Adaptation decision effectiveness (insurance, elevation)
    - Social influence from neighbors' experiences
    - Risk perception evolution over time
    """

    @property
    def domain(self) -> str:
        return "flood"

    def get_focus_areas(self) -> List[str]:
        return [
            "adaptation_effectiveness",
            "risk_pattern_recognition",
            "social_influence_assessment",
            "financial_impact",
        ]

    def generate_prompt(self, agent_id, memories, context) -> str:
        year = context.get("year", "this year")
        flood_occurred = context.get("flood_occurred", False)
        adaptation_status = context.get("adaptation_status", "unknown")

        memory_list = "\n".join(f"- {m}" for m in memories[:10])

        flood_context = ""
        if flood_occurred:
            flood_context = "\nNote: A flood occurred during this period."

        return f"""As {agent_id}, reflect on your experiences over year {year}.
Your current adaptation status: {adaptation_status}
{flood_context}

Your memories:
{memory_list}

Consider:
1. What flood-related patterns have you noticed in your area?
2. Did your adaptation decisions (insurance, elevation) help or hurt?
3. How have your neighbors' experiences influenced your thinking?
4. What would you do differently regarding flood protection?

Provide a concise 2-3 sentence insight that captures your most important lesson about flood risk and adaptation."""

    def parse_response(self, response, memories, context) -> ReflectionInsight:
        summary = response.strip()
        if len(summary) > 500:
            summary = summary[:500] + "..."

        # Determine importance based on context
        importance = 0.85
        if context.get("flood_occurred"):
            importance = 0.95  # Higher importance after actual flood

        # Extract action implications if present
        action_implications = None
        action_keywords = ["should", "will", "need to", "must", "plan to"]
        for sentence in summary.split("."):
            if any(kw in sentence.lower() for kw in action_keywords):
                action_implications = sentence.strip()
                break

        return ReflectionInsight(
            summary=summary,
            source_memories=memories[:5],
            importance=importance,
            domain="flood",
            tags=["adaptation", "risk_assessment", "flood"],
            action_implications=action_implications,
        )


class FinanceReflectionTemplate(ReflectionTemplate):
    """
    Finance domain: focus on savings, debt, investment lessons.

    Emphasizes:
    - Financial decision outcomes
    - Savings and debt management patterns
    - Emergency fund adequacy
    - Investment and spending behavior
    """

    @property
    def domain(self) -> str:
        return "finance"

    def get_focus_areas(self) -> List[str]:
        return [
            "savings_patterns",
            "debt_management",
            "emergency_preparedness",
            "spending_behavior",
        ]

    def generate_prompt(self, agent_id, memories, context) -> str:
        period = context.get("period", "this year")
        savings_ratio = context.get("savings_ratio", "unknown")
        debt_ratio = context.get("debt_ratio", "unknown")

        memory_list = "\n".join(f"- {m}" for m in memories[:10])

        return f"""As {agent_id}, reflect on your financial experiences over {period}.
Current savings ratio: {savings_ratio}
Current debt ratio: {debt_ratio}

Your memories:
{memory_list}

Consider:
1. What patterns do you notice in your spending and saving habits?
2. How well did your financial decisions serve you?
3. Were you prepared for unexpected expenses?
4. What would you do differently regarding your finances?

Provide a concise 2-3 sentence insight about your most important financial lesson."""

    def parse_response(self, response, memories, context) -> ReflectionInsight:
        summary = response.strip()
        if len(summary) > 500:
            summary = summary[:500] + "..."

        # Higher importance if in financial stress
        importance = 0.80
        if context.get("debt_ratio", 0) > 0.4:
            importance = 0.90

        return ReflectionInsight(
            summary=summary,
            source_memories=memories[:5],
            importance=importance,
            domain="finance",
            tags=["financial_planning", "savings", "debt"],
        )


class EducationReflectionTemplate(ReflectionTemplate):
    """
    Education domain: focus on learning progress, motivation, goals.

    Emphasizes:
    - Academic performance patterns
    - Learning strategy effectiveness
    - Motivation and persistence
    - Goal alignment and progress
    """

    @property
    def domain(self) -> str:
        return "education"

    def get_focus_areas(self) -> List[str]:
        return [
            "academic_progress",
            "learning_strategies",
            "motivation_patterns",
            "goal_achievement",
        ]

    def generate_prompt(self, agent_id, memories, context) -> str:
        semester = context.get("semester", "this semester")
        gpa = context.get("gpa", "unknown")
        major = context.get("major", "your field")

        memory_list = "\n".join(f"- {m}" for m in memories[:10])

        return f"""As {agent_id}, reflect on your educational journey during {semester}.
Current GPA: {gpa}
Field of study: {major}

Your memories:
{memory_list}

Consider:
1. What study strategies worked well for you?
2. What challenges affected your academic performance?
3. How has your motivation changed over time?
4. What would you do differently in your approach to learning?

Provide a concise 2-3 sentence insight about your most important educational lesson."""

    def parse_response(self, response, memories, context) -> ReflectionInsight:
        summary = response.strip()
        if len(summary) > 500:
            summary = summary[:500] + "..."

        # Higher importance for struggling students
        importance = 0.80
        gpa = context.get("gpa", 2.5)
        if isinstance(gpa, (int, float)) and gpa < 2.0:
            importance = 0.90

        return ReflectionInsight(
            summary=summary,
            source_memories=memories[:5],
            importance=importance,
            domain="education",
            tags=["learning", "academic", "motivation"],
        )


class HealthReflectionTemplate(ReflectionTemplate):
    """
    Health domain: focus on behavior change, wellness, habits.

    Emphasizes:
    - Health behavior patterns
    - Stage of change progression
    - Social support and barriers
    - Wellness goal achievement
    """

    @property
    def domain(self) -> str:
        return "health"

    def get_focus_areas(self) -> List[str]:
        return [
            "behavior_patterns",
            "change_progress",
            "social_support",
            "wellness_goals",
        ]

    def generate_prompt(self, agent_id, memories, context) -> str:
        period = context.get("period", "recently")
        stage_of_change = context.get("stage_of_change", "unknown")
        health_goal = context.get("health_goal", "improving health")

        memory_list = "\n".join(f"- {m}" for m in memories[:10])

        return f"""As {agent_id}, reflect on your health journey over {period}.
Current stage of change: {stage_of_change}
Health goal: {health_goal}

Your memories:
{memory_list}

Consider:
1. What health behaviors have you been able to maintain?
2. What challenges or triggers affected your progress?
3. How has support from others influenced your journey?
4. What would you do differently to improve your health?

Provide a concise 2-3 sentence insight about your most important health lesson."""

    def parse_response(self, response, memories, context) -> ReflectionInsight:
        summary = response.strip()
        if len(summary) > 500:
            summary = summary[:500] + "..."

        # Higher importance for active change stages
        importance = 0.80
        stage = context.get("stage_of_change", "")
        if stage in ["action", "preparation"]:
            importance = 0.90

        return ReflectionInsight(
            summary=summary,
            source_memories=memories[:5],
            importance=importance,
            domain="health",
            tags=["wellness", "behavior_change", "health"],
        )


# =============================================================================
# Registry and Factory
# =============================================================================

REFLECTION_TEMPLATES: Dict[str, type] = {
    "generic": GenericReflectionTemplate,
    "flood": FloodReflectionTemplate,
    "finance": FinanceReflectionTemplate,
    "education": EducationReflectionTemplate,
    "health": HealthReflectionTemplate,
}


def get_reflection_template(domain: str) -> ReflectionTemplate:
    """
    Get domain-specific reflection template.

    Args:
        domain: Domain name (flood, finance, education, health)

    Returns:
        Appropriate ReflectionTemplate instance

    Example:
        >>> template = get_reflection_template("flood")
        >>> prompt = template.generate_prompt("agent_001", memories, context)
    """
    template_class = REFLECTION_TEMPLATES.get(domain.lower(), GenericReflectionTemplate)
    return template_class()


def register_reflection_template(domain: str, template_class: type) -> None:
    """
    Register a custom reflection template for a domain.

    Args:
        domain: Domain name
        template_class: Class inheriting from ReflectionTemplate
    """
    if not issubclass(template_class, ReflectionTemplate):
        raise TypeError("template_class must inherit from ReflectionTemplate")
    REFLECTION_TEMPLATES[domain.lower()] = template_class
