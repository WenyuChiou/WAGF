"""
Flood Domain Sensors.

SensorConfig definitions for flood-related variables with
domain-specific quantization based on literature.

References:
- FEMA flood zone classifications
- NFIP (National Flood Insurance Program) guidelines
- Behavioral flood adaptation literature
"""

from typing import List, Dict, Any
from cognitive_governance.v1_prototype.types import SensorConfig


# Flood level sensor
FLOOD_LEVEL_SENSOR = SensorConfig(
    domain="flood",
    variable_name="flood_level",
    sensor_name="FLOOD_LEVEL",
    path="environment.flood_level",
    data_type="numeric",
    units="feet",
    quantization_type="threshold_bins",
    bins=[
        {"label": "NONE", "max": 0.0},
        {"label": "MINOR", "max": 1.0},
        {"label": "MODERATE", "max": 3.0},
        {"label": "MAJOR", "max": 6.0},
        {"label": "CATASTROPHIC", "max": float("inf")},
    ],
    bin_rationale="Based on FEMA damage thresholds and insurance claim categories",
    literature_reference="FEMA P-312 Homeowner's Guide to Retrofitting",
)

# Flood risk perception sensor
RISK_PERCEPTION_SENSOR = SensorConfig(
    domain="flood",
    variable_name="risk_perception",
    sensor_name="RISK_PERCEPTION",
    path="agent.risk_perception",
    data_type="numeric",
    units="probability",
    quantization_type="threshold_bins",
    bins=[
        {"label": "VERY_LOW", "max": 0.1},
        {"label": "LOW", "max": 0.3},
        {"label": "MODERATE", "max": 0.5},
        {"label": "HIGH", "max": 0.7},
        {"label": "VERY_HIGH", "max": 1.0},
    ],
    bin_rationale="Subjective probability categories for flood risk",
    literature_reference="Wachinger et al. (2013) Risk Perception Review",
)

# Adaptation status sensor (categorical)
ADAPTATION_STATUS_SENSOR = SensorConfig(
    domain="flood",
    variable_name="adaptation_status",
    sensor_name="ADAPTATION_STATUS",
    path="agent.adaptation_status",
    data_type="categorical",
    categories=[
        "unprotected",
        "insured",
        "elevated",
        "insured_elevated",
        "relocated",
        "fully_adapted",
    ],
    bin_rationale="Hierarchical adaptation levels from no protection to full adaptation",
    literature_reference="Xiao et al. (2023) Household Flood Adaptation",
)

# Income sensor
INCOME_SENSOR = SensorConfig(
    domain="flood",
    variable_name="income",
    sensor_name="INCOME",
    path="agent.income",
    data_type="numeric",
    units="USD",
    quantization_type="threshold_bins",
    bins=[
        {"label": "LOW", "max": 30000},
        {"label": "LOWER_MIDDLE", "max": 50000},
        {"label": "MIDDLE", "max": 75000},
        {"label": "UPPER_MIDDLE", "max": 100000},
        {"label": "HIGH", "max": float("inf")},
    ],
    bin_rationale="US Census income quintile approximations",
    literature_reference="US Census Bureau Income Data",
)

# Savings sensor
SAVINGS_SENSOR = SensorConfig(
    domain="flood",
    variable_name="savings",
    sensor_name="SAVINGS",
    path="agent.savings",
    data_type="numeric",
    units="USD",
    quantization_type="threshold_bins",
    bins=[
        {"label": "CRITICAL", "max": 1000},
        {"label": "LOW", "max": 5000},
        {"label": "MODERATE", "max": 15000},
        {"label": "ADEQUATE", "max": 50000},
        {"label": "STRONG", "max": float("inf")},
    ],
    bin_rationale="Emergency fund recommendations (3-6 months expenses)",
    literature_reference="CFPB Emergency Savings Guidelines",
)

# Flood zone sensor
FLOOD_ZONE_SENSOR = SensorConfig(
    domain="flood",
    variable_name="flood_zone",
    sensor_name="FLOOD_ZONE",
    path="agent.flood_zone",
    data_type="categorical",
    categories=["X", "B", "C", "AE", "A", "VE", "V"],
    bin_rationale="FEMA flood zone classifications (X=minimal, AE=high, V=coastal)",
    literature_reference="FEMA Flood Map Service Center",
)

# Trust sensor
TRUST_SENSOR = SensorConfig(
    domain="flood",
    variable_name="trust",
    sensor_name="TRUST",
    path="agent.trust",
    data_type="numeric",
    units="score",
    quantization_type="threshold_bins",
    bins=[
        {"label": "VERY_LOW", "max": 0.2},
        {"label": "LOW", "max": 0.4},
        {"label": "NEUTRAL", "max": 0.6},
        {"label": "HIGH", "max": 0.8},
        {"label": "VERY_HIGH", "max": 1.0},
    ],
    bin_rationale="Trust in institutions/information sources",
    literature_reference="Social trust literature",
)

# Days since flood sensor
DAYS_SINCE_FLOOD_SENSOR = SensorConfig(
    domain="flood",
    variable_name="days_since_flood",
    sensor_name="DAYS_SINCE_FLOOD",
    path="environment.days_since_flood",
    data_type="numeric",
    units="days",
    quantization_type="threshold_bins",
    bins=[
        {"label": "IMMEDIATE", "max": 30},
        {"label": "RECENT", "max": 180},
        {"label": "PAST_YEAR", "max": 365},
        {"label": "DISTANT", "max": 1825},  # 5 years
        {"label": "FORGOTTEN", "max": float("inf")},
    ],
    bin_rationale="Memory decay and risk perception over time",
    literature_reference="Availability heuristic literature",
)


# All sensors in a list
FLOOD_SENSORS: List[str] = [
    "FLOOD_LEVEL",
    "RISK_PERCEPTION",
    "ADAPTATION_STATUS",
    "INCOME",
    "SAVINGS",
    "FLOOD_ZONE",
    "TRUST",
    "DAYS_SINCE_FLOOD",
]

# SensorConfig objects
FLOOD_SENSOR_CONFIGS: Dict[str, SensorConfig] = {
    "FLOOD_LEVEL": FLOOD_LEVEL_SENSOR,
    "RISK_PERCEPTION": RISK_PERCEPTION_SENSOR,
    "ADAPTATION_STATUS": ADAPTATION_STATUS_SENSOR,
    "INCOME": INCOME_SENSOR,
    "SAVINGS": SAVINGS_SENSOR,
    "FLOOD_ZONE": FLOOD_ZONE_SENSOR,
    "TRUST": TRUST_SENSOR,
    "DAYS_SINCE_FLOOD": DAYS_SINCE_FLOOD_SENSOR,
}


def get_sensor(name: str) -> SensorConfig:
    """Get a sensor configuration by name."""
    return FLOOD_SENSOR_CONFIGS.get(name)


def list_sensors() -> List[str]:
    """List available flood sensors."""
    return FLOOD_SENSORS.copy()
