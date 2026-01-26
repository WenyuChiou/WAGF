"""
Domain-Aware Memory Scoring System.

Provides explainable, domain-specific scoring for memory relevance.
Each domain scorer prioritizes different aspects of memories based on
the research context (flood, finance, education, health).

Usage:
    >>> from governed_ai_sdk.v1_prototype.memory.scoring import get_memory_scorer
    >>> scorer = get_memory_scorer("flood")
    >>> score = scorer.score(memory, context, agent_state)
    >>> print(score.total, score.explanation)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryScore:
    """Explainable memory relevance score.

    Attributes:
        total: Overall relevance score (0-1)
        components: Breakdown of scoring components
        explanation: Human-readable explanation
        rank: Optional rank among scored memories
    """
    total: float
    components: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    rank: Optional[int] = None

    def __post_init__(self):
        # Clamp total to [0, 1]
        self.total = max(0.0, min(1.0, self.total))


class MemoryScorer(ABC):
    """Abstract base for domain-specific memory scoring.

    Each domain scorer implements custom logic to prioritize
    memories relevant to that domain's decision-making context.
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the domain name (flood, finance, education, health)."""
        pass

    @abstractmethod
    def score(
        self,
        memory: Dict[str, Any],
        context: Dict[str, Any],
        agent_state: Dict[str, Any]
    ) -> MemoryScore:
        """Score memory relevance for current context.

        Args:
            memory: Memory item (dict with 'content', 'importance', etc.)
            context: Current decision context (environment state, etc.)
            agent_state: Agent's current state attributes

        Returns:
            MemoryScore with total score and component breakdown
        """
        pass

    def score_batch(
        self,
        memories: List[Dict[str, Any]],
        context: Dict[str, Any],
        agent_state: Dict[str, Any]
    ) -> List[MemoryScore]:
        """Score multiple memories and rank them.

        Args:
            memories: List of memory items
            context: Current decision context
            agent_state: Agent's current state

        Returns:
            List of MemoryScores, sorted by total (descending)
        """
        scores = [
            self.score(memory, context, agent_state)
            for memory in memories
        ]
        # Sort and assign ranks
        scores_sorted = sorted(scores, key=lambda s: s.total, reverse=True)
        for i, score in enumerate(scores_sorted):
            score.rank = i + 1
        return scores_sorted


class GenericMemoryScorer(MemoryScorer):
    """Generic scorer for domains without specific implementation."""

    @property
    def domain(self) -> str:
        return "generic"

    def score(self, memory, context, agent_state) -> MemoryScore:
        # Simple scoring based on recency and importance
        recency = memory.get("recency_score", 0.5)
        importance = memory.get("importance", 0.5)

        components = {
            "recency": recency,
            "importance": importance,
        }
        total = (recency + importance) / 2

        return MemoryScore(
            total=total,
            components=components,
            explanation=f"Generic: recency={recency:.2f}, importance={importance:.2f}"
        )


class FloodMemoryScorer(MemoryScorer):
    """Flood domain: prioritize damage, risk, adaptation memories.

    Scoring factors:
    - Flood-related keywords boost relevance
    - Personal trauma from past floods increases priority
    - Recent adaptation decisions (insurance, elevation) are highlighted
    - Crisis context amplifies flood-related memories
    """

    FLOOD_KEYWORDS = {
        "critical": ["flood", "damage", "loss", "destroyed", "evacuate", "emergency"],
        "high": ["insurance", "elevate", "elevation", "protection", "warning", "risk"],
        "moderate": ["neighbor", "community", "news", "weather", "storm"],
    }

    @property
    def domain(self) -> str:
        return "flood"

    def score(self, memory, context, agent_state) -> MemoryScore:
        content = str(memory.get("content", "")).lower()

        # Base scores
        recency = memory.get("recency_score", 0.5)
        importance = memory.get("importance", 0.5)

        # Keyword relevance scoring
        keyword_score = 0.0
        keyword_matches = []
        for level, keywords in self.FLOOD_KEYWORDS.items():
            weight = {"critical": 0.15, "high": 0.10, "moderate": 0.05}[level]
            for kw in keywords:
                if kw in content:
                    keyword_score += weight
                    keyword_matches.append(kw)
        keyword_score = min(keyword_score, 0.5)  # Cap at 0.5

        # Trauma boost if agent experienced flood
        trauma_boost = 0.0
        if agent_state.get("flood_experience") or agent_state.get("has_flood_damage"):
            trauma_boost = 0.2

        # Crisis context boost
        crisis_boost = 0.0
        if context.get("flood_active") or context.get("crisis_event"):
            crisis_boost = 0.15

        components = {
            "recency": recency * 0.25,
            "importance": importance * 0.25,
            "keyword_relevance": keyword_score,
            "trauma_boost": trauma_boost,
            "crisis_boost": crisis_boost,
        }

        total = sum(components.values())

        # Build explanation
        explanation_parts = [f"Flood context"]
        if keyword_matches:
            explanation_parts.append(f"keywords={keyword_matches[:3]}")
        if trauma_boost > 0:
            explanation_parts.append("trauma_amplified")
        if crisis_boost > 0:
            explanation_parts.append("crisis_active")
        explanation = ", ".join(explanation_parts)

        return MemoryScore(
            total=total,
            components=components,
            explanation=explanation
        )


class FinanceMemoryScorer(MemoryScorer):
    """Finance domain: prioritize savings, debt, investment memories.

    Scoring factors:
    - Financial decision keywords boost relevance
    - Recent debt/savings changes are prioritized
    - Major purchases and financial stress increase priority
    """

    FINANCE_KEYWORDS = {
        "critical": ["bankruptcy", "debt", "loss", "emergency", "crisis"],
        "high": ["savings", "investment", "loan", "credit", "income", "expense"],
        "moderate": ["budget", "purchase", "payment", "financial", "money"],
    }

    @property
    def domain(self) -> str:
        return "finance"

    def score(self, memory, context, agent_state) -> MemoryScore:
        content = str(memory.get("content", "")).lower()

        recency = memory.get("recency_score", 0.5)
        importance = memory.get("importance", 0.5)

        # Keyword scoring
        keyword_score = 0.0
        keyword_matches = []
        for level, keywords in self.FINANCE_KEYWORDS.items():
            weight = {"critical": 0.15, "high": 0.10, "moderate": 0.05}[level]
            for kw in keywords:
                if kw in content:
                    keyword_score += weight
                    keyword_matches.append(kw)
        keyword_score = min(keyword_score, 0.5)

        # Financial stress boost
        stress_boost = 0.0
        debt_ratio = agent_state.get("debt_ratio", 0)
        savings_ratio = agent_state.get("savings_ratio", 1)
        if debt_ratio > 0.4 or savings_ratio < 0.2:
            stress_boost = 0.15

        # Major decision boost
        decision_boost = 0.0
        if context.get("major_purchase") or context.get("loan_decision"):
            decision_boost = 0.1

        components = {
            "recency": recency * 0.25,
            "importance": importance * 0.25,
            "keyword_relevance": keyword_score,
            "stress_boost": stress_boost,
            "decision_boost": decision_boost,
        }

        total = sum(components.values())

        explanation_parts = ["Finance context"]
        if keyword_matches:
            explanation_parts.append(f"keywords={keyword_matches[:3]}")
        if stress_boost > 0:
            explanation_parts.append("financial_stress")

        return MemoryScore(
            total=total,
            components=components,
            explanation=", ".join(explanation_parts)
        )


class EducationMemoryScorer(MemoryScorer):
    """Education domain: prioritize learning, achievement, motivation memories.

    Scoring factors:
    - Academic keywords boost relevance
    - Recent grade/performance changes prioritized
    - Goal-related memories highlighted during decision points
    """

    EDUCATION_KEYWORDS = {
        "critical": ["graduate", "fail", "drop", "scholarship", "expel"],
        "high": ["degree", "course", "grade", "major", "study", "exam"],
        "moderate": ["class", "professor", "student", "learn", "school"],
    }

    @property
    def domain(self) -> str:
        return "education"

    def score(self, memory, context, agent_state) -> MemoryScore:
        content = str(memory.get("content", "")).lower()

        recency = memory.get("recency_score", 0.5)
        importance = memory.get("importance", 0.5)

        # Keyword scoring
        keyword_score = 0.0
        keyword_matches = []
        for level, keywords in self.EDUCATION_KEYWORDS.items():
            weight = {"critical": 0.15, "high": 0.10, "moderate": 0.05}[level]
            for kw in keywords:
                if kw in content:
                    keyword_score += weight
                    keyword_matches.append(kw)
        keyword_score = min(keyword_score, 0.5)

        # Motivation boost based on GPA
        motivation_boost = 0.0
        gpa = agent_state.get("gpa", 2.5)
        if gpa < 2.0:  # Struggling student prioritizes academic memories
            motivation_boost = 0.15
        elif gpa > 3.5:  # High achiever also values academic context
            motivation_boost = 0.1

        # Decision point boost
        decision_boost = 0.0
        if context.get("enrollment_decision") or context.get("major_selection"):
            decision_boost = 0.1

        components = {
            "recency": recency * 0.25,
            "importance": importance * 0.25,
            "keyword_relevance": keyword_score,
            "motivation_boost": motivation_boost,
            "decision_boost": decision_boost,
        }

        total = sum(components.values())

        explanation_parts = ["Education context"]
        if keyword_matches:
            explanation_parts.append(f"keywords={keyword_matches[:3]}")
        if motivation_boost > 0:
            explanation_parts.append("motivation_context")

        return MemoryScore(
            total=total,
            components=components,
            explanation=", ".join(explanation_parts)
        )


class HealthMemoryScorer(MemoryScorer):
    """Health domain: prioritize wellness, behavior change, medical memories.

    Scoring factors:
    - Health behavior keywords boost relevance
    - Stage of change affects priority
    - Recent health events (smoking, exercise changes) highlighted
    """

    HEALTH_KEYWORDS = {
        "critical": ["hospital", "diagnosis", "emergency", "surgery", "chronic"],
        "high": ["exercise", "diet", "smoking", "weight", "health", "doctor"],
        "moderate": ["wellness", "fitness", "habit", "lifestyle", "stress"],
    }

    @property
    def domain(self) -> str:
        return "health"

    def score(self, memory, context, agent_state) -> MemoryScore:
        content = str(memory.get("content", "")).lower()

        recency = memory.get("recency_score", 0.5)
        importance = memory.get("importance", 0.5)

        # Keyword scoring
        keyword_score = 0.0
        keyword_matches = []
        for level, keywords in self.HEALTH_KEYWORDS.items():
            weight = {"critical": 0.15, "high": 0.10, "moderate": 0.05}[level]
            for kw in keywords:
                if kw in content:
                    keyword_score += weight
                    keyword_matches.append(kw)
        keyword_score = min(keyword_score, 0.5)

        # Change readiness boost
        readiness_boost = 0.0
        stage = agent_state.get("stage_of_change", "")
        if stage in ["preparation", "action"]:
            readiness_boost = 0.15
        elif stage == "contemplation":
            readiness_boost = 0.1

        # Health event boost
        event_boost = 0.0
        if agent_state.get("recent_health_event") or context.get("health_crisis"):
            event_boost = 0.15

        components = {
            "recency": recency * 0.25,
            "importance": importance * 0.25,
            "keyword_relevance": keyword_score,
            "readiness_boost": readiness_boost,
            "event_boost": event_boost,
        }

        total = sum(components.values())

        explanation_parts = ["Health context"]
        if keyword_matches:
            explanation_parts.append(f"keywords={keyword_matches[:3]}")
        if readiness_boost > 0:
            explanation_parts.append(f"stage={stage}")

        return MemoryScore(
            total=total,
            components=components,
            explanation=", ".join(explanation_parts)
        )


# =============================================================================
# Registry and Factory
# =============================================================================

MEMORY_SCORERS: Dict[str, type] = {
    "generic": GenericMemoryScorer,
    "flood": FloodMemoryScorer,
    "finance": FinanceMemoryScorer,
    "education": EducationMemoryScorer,
    "health": HealthMemoryScorer,
}


def get_memory_scorer(domain: str) -> MemoryScorer:
    """Get domain-specific memory scorer.

    Args:
        domain: Domain name (flood, finance, education, health)

    Returns:
        Appropriate MemoryScorer instance

    Example:
        >>> scorer = get_memory_scorer("flood")
        >>> score = scorer.score(memory, context, agent_state)
    """
    scorer_class = MEMORY_SCORERS.get(domain.lower(), GenericMemoryScorer)
    return scorer_class()


def register_memory_scorer(domain: str, scorer_class: type) -> None:
    """Register a custom memory scorer for a domain.

    Args:
        domain: Domain name
        scorer_class: Class inheriting from MemoryScorer
    """
    if not issubclass(scorer_class, MemoryScorer):
        raise TypeError("scorer_class must inherit from MemoryScorer")
    MEMORY_SCORERS[domain.lower()] = scorer_class
