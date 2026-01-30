"""
Health Domain Sensors.

SensorConfig definitions for health behavior variables.

References:
- CDC Physical Activity Guidelines
- WHO health recommendations
- Health behavior change literature
"""

from typing import List, Dict
from cognitive_governance.v1_prototype.types import SensorConfig


# Activity level sensor
ACTIVITY_LEVEL_SENSOR = SensorConfig(
    domain="health",
    variable_name="activity_level",
    sensor_name="ACTIVITY_LEVEL",
    path="agent.activity_level",
    data_type="categorical",
    categories=[
        "sedentary",
        "light_active",
        "moderately_active",
        "very_active",
    ],
    bin_rationale="CDC physical activity guidelines categories",
    literature_reference="CDC Physical Activity Guidelines for Americans",
)

# Diet quality sensor
DIET_QUALITY_SENSOR = SensorConfig(
    domain="health",
    variable_name="diet_quality",
    sensor_name="DIET_QUALITY",
    path="agent.diet_quality",
    data_type="categorical",
    categories=[
        "unhealthy_diet",
        "mixed_diet",
        "healthy_diet",
    ],
    bin_rationale="Simplified diet quality categories",
    literature_reference="USDA Dietary Guidelines",
)

# Smoking status sensor
SMOKING_STATUS_SENSOR = SensorConfig(
    domain="health",
    variable_name="smoking_status",
    sensor_name="SMOKING_STATUS",
    path="agent.smoking_status",
    data_type="categorical",
    categories=[
        "smoker",
        "trying_to_quit",
        "former_smoker",
        "non_smoker",
    ],
    bin_rationale="Smoking cessation stages",
    literature_reference="Transtheoretical Model (Prochaska)",
)

# BMI sensor
BMI_SENSOR = SensorConfig(
    domain="health",
    variable_name="bmi",
    sensor_name="BMI",
    path="agent.bmi",
    data_type="numeric",
    units="kg/m2",
    quantization_type="threshold_bins",
    bins=[
        {"label": "UNDERWEIGHT", "max": 18.5},
        {"label": "NORMAL", "max": 25.0},
        {"label": "OVERWEIGHT", "max": 30.0},
        {"label": "OBESE", "max": float("inf")},
    ],
    bin_rationale="WHO BMI classification",
    literature_reference="World Health Organization",
)

# Sleep quality sensor
SLEEP_QUALITY_SENSOR = SensorConfig(
    domain="health",
    variable_name="sleep_quality",
    sensor_name="SLEEP_QUALITY",
    path="agent.sleep_quality",
    data_type="categorical",
    categories=[
        "poor",
        "fair",
        "good",
        "excellent",
    ],
    bin_rationale="Sleep quality self-assessment categories",
    literature_reference="Pittsburgh Sleep Quality Index",
)

# Stress level sensor
STRESS_LEVEL_SENSOR = SensorConfig(
    domain="health",
    variable_name="stress_level",
    sensor_name="STRESS_LEVEL",
    path="agent.stress_level",
    data_type="numeric",
    units="score",
    quantization_type="threshold_bins",
    bins=[
        {"label": "LOW", "max": 0.3},
        {"label": "MODERATE", "max": 0.6},
        {"label": "HIGH", "max": 0.8},
        {"label": "SEVERE", "max": 1.0},
    ],
    bin_rationale="Perceived Stress Scale categories",
    literature_reference="Cohen Perceived Stress Scale",
)

# Self-efficacy sensor
SELF_EFFICACY_SENSOR = SensorConfig(
    domain="health",
    variable_name="self_efficacy",
    sensor_name="SELF_EFFICACY",
    path="agent.self_efficacy",
    data_type="numeric",
    units="score",
    quantization_type="threshold_bins",
    bins=[
        {"label": "LOW", "max": 0.33},
        {"label": "MODERATE", "max": 0.66},
        {"label": "HIGH", "max": 1.0},
    ],
    bin_rationale="Self-efficacy belief strength",
    literature_reference="Bandura Self-Efficacy Theory",
)

# Stage of change sensor (TTM)
STAGE_OF_CHANGE_SENSOR = SensorConfig(
    domain="health",
    variable_name="stage_of_change",
    sensor_name="STAGE_OF_CHANGE",
    path="agent.stage_of_change",
    data_type="categorical",
    categories=[
        "precontemplation",
        "contemplation",
        "preparation",
        "action",
        "maintenance",
    ],
    bin_rationale="Transtheoretical Model stages",
    literature_reference="Prochaska & DiClemente TTM",
)

# Chronic condition sensor
CHRONIC_CONDITION_SENSOR = SensorConfig(
    domain="health",
    variable_name="chronic_condition",
    sensor_name="CHRONIC_CONDITION",
    path="agent.chronic_condition",
    data_type="categorical",
    categories=[
        "none",
        "diabetes",
        "hypertension",
        "heart_disease",
        "multiple",
    ],
    bin_rationale="Common chronic conditions",
    literature_reference="CDC Chronic Disease Indicators",
)


# All sensors in a list
HEALTH_SENSORS: List[str] = [
    "ACTIVITY_LEVEL",
    "DIET_QUALITY",
    "SMOKING_STATUS",
    "BMI",
    "SLEEP_QUALITY",
    "STRESS_LEVEL",
    "SELF_EFFICACY",
    "STAGE_OF_CHANGE",
    "CHRONIC_CONDITION",
]

# SensorConfig objects
HEALTH_SENSOR_CONFIGS: Dict[str, SensorConfig] = {
    "ACTIVITY_LEVEL": ACTIVITY_LEVEL_SENSOR,
    "DIET_QUALITY": DIET_QUALITY_SENSOR,
    "SMOKING_STATUS": SMOKING_STATUS_SENSOR,
    "BMI": BMI_SENSOR,
    "SLEEP_QUALITY": SLEEP_QUALITY_SENSOR,
    "STRESS_LEVEL": STRESS_LEVEL_SENSOR,
    "SELF_EFFICACY": SELF_EFFICACY_SENSOR,
    "STAGE_OF_CHANGE": STAGE_OF_CHANGE_SENSOR,
    "CHRONIC_CONDITION": CHRONIC_CONDITION_SENSOR,
}


def get_sensor(name: str) -> SensorConfig:
    """Get a sensor configuration by name."""
    return HEALTH_SENSOR_CONFIGS.get(name)


def list_sensors() -> List[str]:
    """List available health sensors."""
    return HEALTH_SENSORS.copy()
