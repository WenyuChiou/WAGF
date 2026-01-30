"""
Education Domain Pack.

Pre-configured components for educational decision-making research.

Components:
- EDUCATION_SENSORS: SensorConfig definitions for education variables
- EDUCATION_RULES: Default governance PolicyRules for education decisions
- EDUCATION_FEASIBILITY: Categorical transition feasibility matrix
- EducationObserver: Social observation for educational behaviors
- EducationEnvironmentObserver: Environment observation for education conditions

Literature:
- US Department of Education statistics
- Educational psychology research
- Human capital theory
"""

from .sensors import EDUCATION_SENSORS, EDUCATION_SENSOR_CONFIGS
from .rules import EDUCATION_RULES, create_education_policy
from .observer import EducationObserver, EducationEnvironmentObserver

# Re-export feasibility from XAI module
from cognitive_governance.v1_prototype.xai.feasibility import (
    EDUCATION_FEASIBILITY,
    EDUCATION_RATIONALES,
)

__all__ = [
    # Sensors
    "EDUCATION_SENSORS",
    "EDUCATION_SENSOR_CONFIGS",
    # Rules
    "EDUCATION_RULES",
    "create_education_policy",
    # Observers
    "EducationObserver",
    "EducationEnvironmentObserver",
    # Feasibility
    "EDUCATION_FEASIBILITY",
    "EDUCATION_RATIONALES",
]
