"""
Reflection Insight Data Structure.

Provides structured representation of insights generated from reflection processes.
Insights can be promoted to memories for long-term retention.

Usage:
    >>> from cognitive_governance.v1_prototype.reflection import ReflectionInsight
    >>> insight = ReflectionInsight(
    ...     summary="Flood insurance saved me $50,000 in repairs",
    ...     source_memories=["memory_1", "memory_2"],
    ...     importance=0.9,
    ...     domain="flood"
    ... )
    >>> memory_dict = insight.to_memory_format()
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ReflectionInsight:
    """
    Structured insight from agent reflection.

    Represents a consolidated understanding derived from reviewing memories.
    Can be converted to memory format for long-term storage.

    Attributes:
        summary: The main insight text
        source_memories: List of memory IDs/contents that informed this insight
        importance: Importance score for memory promotion (0-1)
        domain: Domain context (flood, finance, education, health)
        created_at: When the insight was generated
        tags: Semantic tags for retrieval
        confidence: Confidence level in the insight (0-1)
        action_implications: Suggested actions based on insight
    """

    summary: str
    source_memories: List[str] = field(default_factory=list)
    importance: float = 0.8
    domain: str = "generic"
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.7
    action_implications: Optional[str] = None

    def __post_init__(self):
        # Clamp importance and confidence to [0, 1]
        self.importance = max(0.0, min(1.0, self.importance))
        self.confidence = max(0.0, min(1.0, self.confidence))

    def to_memory_format(self) -> Dict[str, Any]:
        """
        Convert insight to memory item for promotion.

        Returns:
            Dict suitable for storing in memory engine
        """
        return {
            "content": f"[REFLECTION] {self.summary}",
            "importance": self.importance,
            "source": "reflection",
            "domain": self.domain,
            "tags": self.tags + ["reflection", "insight"],
            "created_at": self.created_at.isoformat(),
            "confidence": self.confidence,
            "source_memories": self.source_memories[:5],  # Limit for storage
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert insight to full dictionary representation.

        Returns:
            Dict with all insight attributes
        """
        return {
            "summary": self.summary,
            "source_memories": self.source_memories,
            "importance": self.importance,
            "domain": self.domain,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "confidence": self.confidence,
            "action_implications": self.action_implications,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReflectionInsight":
        """
        Create insight from dictionary.

        Args:
            data: Dictionary with insight attributes

        Returns:
            ReflectionInsight instance
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            summary=data.get("summary", ""),
            source_memories=data.get("source_memories", []),
            importance=data.get("importance", 0.8),
            domain=data.get("domain", "generic"),
            created_at=created_at,
            tags=data.get("tags", []),
            confidence=data.get("confidence", 0.7),
            action_implications=data.get("action_implications"),
        )

    def __str__(self) -> str:
        return f"ReflectionInsight({self.domain}): {self.summary[:50]}..."


@dataclass
class ReflectionTrace:
    """
    Trace of a reflection process for explainability.

    Records the full context of how a reflection was generated,
    including input memories, template used, and output insight.

    Attributes:
        agent_id: The agent who reflected
        timestamp: When reflection occurred
        input_memories: Memories used as input
        template_name: Name of the template used
        prompt: The actual prompt sent to LLM
        raw_response: LLM's raw response
        insight: Parsed insight result
        processing_time_ms: Time taken for reflection
    """

    agent_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    input_memories: List[str] = field(default_factory=list)
    template_name: str = "generic"
    prompt: str = ""
    raw_response: str = ""
    insight: Optional[ReflectionInsight] = None
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for logging/export."""
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "input_memories_count": len(self.input_memories),
            "template_name": self.template_name,
            "prompt_length": len(self.prompt),
            "response_length": len(self.raw_response),
            "insight_summary": self.insight.summary if self.insight else None,
            "insight_importance": self.insight.importance if self.insight else None,
            "processing_time_ms": self.processing_time_ms,
        }
