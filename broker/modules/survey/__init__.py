"""
Survey data processing module for real-world agent initialization.

This module provides:
- SurveyLoader: Load and validate survey data from Excel
- MGClassifier: Classify households as MG (Marginalized Group) or NMG
- AgentInitializer: Create agent profiles from survey data
- AgentProfile: Complete agent profile ready for simulation
"""

from .survey_loader import SurveyLoader, SurveyRecord, load_survey_data, INCOME_MIDPOINTS
from .mg_classifier import MGClassifier, PovertyLineTable, MGClassificationResult
from .agent_initializer import (
    AgentInitializer,
    AgentProfile,
    initialize_agents_from_survey,
)

__all__ = [
    # Survey loading
    "SurveyLoader",
    "SurveyRecord",
    "load_survey_data",
    "INCOME_MIDPOINTS",
    # MG classification
    "MGClassifier",
    "PovertyLineTable",
    "MGClassificationResult",
    # Agent initialization
    "AgentInitializer",
    "AgentProfile",
    "initialize_agents_from_survey",
]
