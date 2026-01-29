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
]
