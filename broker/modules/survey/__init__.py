"""
Generic survey data processing module for agent initialization.

This module provides:
- SurveyLoader: Load and validate survey data from Excel/CSV
- AgentInitializer: Create agent profiles from survey data
- AgentProfile: Complete agent profile ready for simulation

Domain-specific features (e.g., MG classification for MA flood simulation)
should be implemented in domain-specific modules (e.g., examples/multi_agent/survey/).
"""

from .survey_loader import SurveyLoader, SurveyRecord, load_survey_data, INCOME_MIDPOINTS
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
    # Agent initialization
    "AgentInitializer",
    "AgentProfile",
    "initialize_agents_from_survey",
]
