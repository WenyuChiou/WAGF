"""
Broker Interfaces Package

Generic protocols and interfaces for dependency injection.
Allows domain-specific implementations to be provided without
coupling the broker framework to specific application domains.
"""
from .enrichment import (
    PositionData,
    PositionEnricher,
    ValueData,
    ValueEnricher,
)
from .context_types import (
    PsychologicalFrameworkType,
    MemoryContext,
    ConstructAppraisal,
    UniversalContext,
    PromptVariables,
    PriorityItem,
)
from .rating_scales import (
    FrameworkType,
    RatingScale,
    RatingScaleRegistry,
    get_scale_for_framework,
    validate_rating_value,
)
from .perception import (
    PerceptionMode,
    DescriptorMapping,
    PerceptionConfig,
    PerceptionFilterProtocol,
    PerceptionFilterRegistryProtocol,
    FLOOD_DEPTH_DESCRIPTORS,
    DAMAGE_SEVERITY_DESCRIPTORS,
    NEIGHBOR_COUNT_DESCRIPTORS,
)
from .environment_protocols import (
    EnvironmentProtocol,
    TieredEnvironmentProtocol,
    SocialEnvironmentProtocol,
)

__all__ = [
    # Enrichment interfaces
    "PositionData",
    "PositionEnricher",
    "ValueData",
    "ValueEnricher",
    # Context types
    "PsychologicalFrameworkType",
    "MemoryContext",
    "ConstructAppraisal",
    "UniversalContext",
    "PromptVariables",
    "PriorityItem",
    # Rating scales (Task-041)
    "FrameworkType",
    "RatingScale",
    "RatingScaleRegistry",
    "get_scale_for_framework",
    "validate_rating_value",
    # Perception filters (Task-043)
    "PerceptionMode",
    "DescriptorMapping",
    "PerceptionConfig",
    "PerceptionFilterProtocol",
    "PerceptionFilterRegistryProtocol",
    "FLOOD_DEPTH_DESCRIPTORS",
    "DAMAGE_SEVERITY_DESCRIPTORS",
    "NEIGHBOR_COUNT_DESCRIPTORS",
    # Environment protocols (migrated from cognitive_governance)
    "EnvironmentProtocol",
    "TieredEnvironmentProtocol",
    "SocialEnvironmentProtocol",
]
