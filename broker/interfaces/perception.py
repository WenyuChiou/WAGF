"""
Perception Filter Protocol - Agent-type specific context transformation.

Design Principles:
1. Agent-type aware: Different agents see different representations
2. Configurable: Mapping rules can be customized per domain
3. Composable: Filters can be chained

Example:
    Household sees: "waist-deep water", "significant damage"
    Government sees: 3.2 ft, $35,000
"""
from typing import Dict, Any, List, Protocol, Optional
from dataclasses import dataclass, field
from enum import Enum


class PerceptionMode(Enum):
    """How numerical data is presented to an agent."""
    QUANTITATIVE = "quantitative"  # Exact numbers: $25,000, 45%
    QUALITATIVE = "qualitative"    # Descriptors: "significant loss"
    HYBRID = "hybrid"              # Some numbers, some descriptors


@dataclass
class DescriptorMapping:
    """Maps numerical ranges to qualitative descriptors.

    Example:
        damage_ratio → "minimal" | "minor" | "moderate" | "significant" | "devastating"

    Args:
        field_name: The output field name in context
        ranges: List of (min, max, descriptor) tuples
        unit: Unit of measurement (e.g., "ft", "$", "%")
    """
    field_name: str
    ranges: List[tuple]  # [(min, max, descriptor), ...]
    unit: str = ""

    def describe(self, value: float) -> str:
        """Convert numerical value to descriptor.

        Args:
            value: Numerical value to convert

        Returns:
            Qualitative descriptor string
        """
        for min_val, max_val, descriptor in self.ranges:
            if min_val <= value < max_val:
                return descriptor
        return "unknown"


@dataclass
class PerceptionConfig:
    """Configuration for a perception filter.

    Args:
        mode: How data is presented (quantitative/qualitative/hybrid)
        visible_fields: Fields agent can see (empty = all)
        hidden_fields: Fields to remove from context
        descriptor_mappings: Numerical-to-qualitative mappings
        social_radius: For spatial neighbor computation
    """
    mode: PerceptionMode = PerceptionMode.QUALITATIVE
    visible_fields: List[str] = field(default_factory=list)
    hidden_fields: List[str] = field(default_factory=list)
    descriptor_mappings: Dict[str, DescriptorMapping] = field(default_factory=dict)
    social_radius: int = 2


class PerceptionFilterProtocol(Protocol):
    """Interface for perception filters.

    Transforms raw context into agent-appropriate representation.
    Different agent types (household, government, insurance) have
    different filters that shape what information they can "see".
    """

    @property
    def agent_type(self) -> str:
        """Agent type this filter applies to (e.g., 'household', 'government')."""
        ...

    def filter(self, context: Dict[str, Any], agent: Any) -> Dict[str, Any]:
        """Transform raw context for this agent type.

        Args:
            context: Raw context with numerical data
            agent: Agent instance (for MG/tenure checks)

        Returns:
            Filtered context appropriate for agent type
        """
        ...


class PerceptionFilterRegistryProtocol(Protocol):
    """Interface for perception filter registries."""

    def register(self, agent_type: str, filter_instance: Any) -> None:
        """Register a filter for an agent type."""
        ...

    def get(self, agent_type: str) -> Optional[Any]:
        """Get filter for agent type."""
        ...

    def filter_context(
        self,
        agent_type: str,
        context: Dict[str, Any],
        agent: Any
    ) -> Dict[str, Any]:
        """Apply appropriate filter based on agent type."""
        ...


# Pre-defined descriptor mappings for common use cases
FLOOD_DEPTH_DESCRIPTORS = DescriptorMapping(
    field_name="flood_depth",
    ranges=[
        (0.0, 0.5, "ankle-deep water"),
        (0.5, 2.0, "knee-deep water"),
        (2.0, 4.0, "waist-deep water"),
        (4.0, 8.0, "chest-deep water"),
        (8.0, float('inf'), "over-head water"),
    ],
    unit="ft",
)

DAMAGE_SEVERITY_DESCRIPTORS = DescriptorMapping(
    field_name="damage_severity",
    ranges=[
        (0.0, 0.05, "minimal damage"),
        (0.05, 0.15, "minor damage"),
        (0.15, 0.30, "moderate damage"),
        (0.30, 0.50, "significant damage"),
        (0.50, float('inf'), "devastating damage"),
    ],
)

NEIGHBOR_COUNT_DESCRIPTORS = DescriptorMapping(
    field_name="neighbors_description",
    ranges=[
        (0, 1, "none of your neighbors"),
        (1, 3, "a few of your neighbors"),
        (3, 6, "some of your neighbors"),
        (6, 11, "many of your neighbors"),
        (11, float('inf'), "most of your neighbors"),
    ],
)


__all__ = [
    "PerceptionMode",
    "DescriptorMapping",
    "PerceptionConfig",
    "PerceptionFilterProtocol",
    "PerceptionFilterRegistryProtocol",
    # Pre-defined mappings
    "FLOOD_DEPTH_DESCRIPTORS",
    "DAMAGE_SEVERITY_DESCRIPTORS",
    "NEIGHBOR_COUNT_DESCRIPTORS",
]
