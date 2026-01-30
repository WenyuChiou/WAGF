"""
Health Domain Pack.

Pre-configured components for health behavior change research.

Components:
- HEALTH_SENSORS: SensorConfig definitions for health variables
- HEALTH_RULES: Default governance PolicyRules for health decisions
- HEALTH_FEASIBILITY: Categorical transition feasibility matrix
- HealthObserver: Social observation for health behaviors
- HealthEnvironmentObserver: Environment observation for health conditions

Literature:
- Transtheoretical Model (TTM) of behavior change
- Health Belief Model (HBM)
- Social Cognitive Theory
"""

from .sensors import HEALTH_SENSORS, HEALTH_SENSOR_CONFIGS
from .rules import HEALTH_RULES, create_health_policy
from .observer import HealthObserver, HealthEnvironmentObserver

# Re-export feasibility from XAI module
from cognitive_governance.v1_prototype.xai.feasibility import (
    HEALTH_FEASIBILITY,
    HEALTH_RATIONALES,
)

__all__ = [
    # Sensors
    "HEALTH_SENSORS",
    "HEALTH_SENSOR_CONFIGS",
    # Rules
    "HEALTH_RULES",
    "create_health_policy",
    # Observers
    "HealthObserver",
    "HealthEnvironmentObserver",
    # Feasibility
    "HEALTH_FEASIBILITY",
    "HEALTH_RATIONALES",
]
