"""
MA (Multi-Agent Flood Simulation) Survey Module.

Provides MA-specific survey loading and agent initialization:
- FloodSurveyLoader: Load surveys with flood experience fields
- FloodSurveyRecord: Survey record with flood fields
- MGClassifier: Marginalized Group classifier
- MAAgentInitializer: MA-specific agent initialization
- initialize_ma_agents_from_survey: Convenience function for MA initialization
"""

from .flood_survey_loader import (
    FloodSurveyLoader,
    FloodSurveyRecord,
    FLOOD_COLUMN_MAPPING,
    load_flood_survey_data,
)
from .mg_classifier import (
    MGClassifier,
    MGClassificationResult,
    PovertyLineTable,
)
from .ma_initializer import (
    MAAgentProfile,
    MAAgentInitializer,
    initialize_ma_agents_from_survey,
)

__all__ = [
    # Flood survey loading
    "FloodSurveyLoader",
    "FloodSurveyRecord",
    "FLOOD_COLUMN_MAPPING",
    "load_flood_survey_data",
    # MG classification
    "MGClassifier",
    "MGClassificationResult",
    "PovertyLineTable",
    # MA agent initialization
    "MAAgentProfile",
    "MAAgentInitializer",
    "initialize_ma_agents_from_survey",
]
