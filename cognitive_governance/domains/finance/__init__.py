"""
Finance Domain Pack.

Pre-configured components for financial decision-making research.

Components:
- FINANCE_SENSORS: SensorConfig definitions for financial variables
- FINANCE_RULES: Default governance PolicyRules for financial decisions
- FINANCE_FEASIBILITY: Categorical transition feasibility matrix
- FinanceObserver: Social observation for financial behaviors
- FinanceEnvironmentObserver: Environment observation for economic conditions

Literature:
- CFPB Consumer Financial Protection Bureau guidelines
- Behavioral economics (Thaler, Kahneman)
- Financial literacy research
"""

from .sensors import FINANCE_SENSORS, FINANCE_SENSOR_CONFIGS
from .rules import FINANCE_RULES, create_finance_policy
from .observer import FinanceObserver, FinanceEnvironmentObserver

# Re-export feasibility from XAI module
from cognitive_governance.v1_prototype.xai.feasibility import (
    FINANCE_FEASIBILITY,
    FINANCE_RATIONALES,
)

__all__ = [
    # Sensors
    "FINANCE_SENSORS",
    "FINANCE_SENSOR_CONFIGS",
    # Rules
    "FINANCE_RULES",
    "create_finance_policy",
    # Observers
    "FinanceObserver",
    "FinanceEnvironmentObserver",
    # Feasibility
    "FINANCE_FEASIBILITY",
    "FINANCE_RATIONALES",
]
