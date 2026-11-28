"""
Legacy household-survey processing module for agent initialization.

STATUS: LEGACY HOUSEHOLD SURVEY LOADER. Retained without runtime warnings
to preserve frozen flood paper runners (``examples/single_agent/run_flood.py``
and ``examples/multi_agent/flood/survey/``). New domains should use
:class:`broker.core.agent_initializer.CSVLoader` for generic profile loading.
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
