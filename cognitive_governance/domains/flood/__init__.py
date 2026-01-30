"""
Flood Domain Pack.

Pre-configured components for flood risk adaptation research.

Components:
- FLOOD_SENSORS: SensorConfig definitions for flood-related variables
- FLOOD_RULES: Default governance PolicyRules for flood decisions
- FLOOD_FEASIBILITY: Categorical transition feasibility matrix
- FloodObserver: Social observation for flood adaptation
- FloodEnvironmentObserver: Environment observation for flood conditions

Literature:
- Tonn & Czajkowski (2024): Climate risk communication
- Xiao et al. (2023): Household flood adaptation
- FEMA flood zone definitions
"""

from .sensors import FLOOD_SENSORS, FLOOD_SENSOR_CONFIGS
from .rules import FLOOD_RULES, create_flood_policy
from .observer import FloodObserver, FloodEnvironmentObserver

# Re-export feasibility from XAI module
from cognitive_governance.v1_prototype.xai.feasibility import (
    FLOOD_FEASIBILITY,
    FLOOD_RATIONALES,
)

__all__ = [
    # Sensors
    "FLOOD_SENSORS",
    "FLOOD_SENSOR_CONFIGS",
    # Rules
    "FLOOD_RULES",
    "create_flood_policy",
    # Observers
    "FloodObserver",
    "FloodEnvironmentObserver",
    # Feasibility
    "FLOOD_FEASIBILITY",
    "FLOOD_RATIONALES",
]
