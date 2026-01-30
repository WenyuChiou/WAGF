"""
Education Domain Sensors.

SensorConfig definitions for educational variables.

References:
- US Department of Education
- Bureau of Labor Statistics
- Educational psychology literature
"""

from typing import List, Dict
from cognitive_governance.v1_prototype.types import SensorConfig


# Degree level sensor
DEGREE_LEVEL_SENSOR = SensorConfig(
    domain="education",
    variable_name="degree_level",
    sensor_name="DEGREE_LEVEL",
    path="agent.degree_level",
    data_type="categorical",
    categories=[
        "none",
        "high_school",
        "associate",
        "bachelors",
        "masters",
        "doctorate",
    ],
    bin_rationale="Standard US educational attainment levels",
    literature_reference="US Census Educational Attainment",
)

# GPA sensor
GPA_SENSOR = SensorConfig(
    domain="education",
    variable_name="gpa",
    sensor_name="GPA",
    path="agent.gpa",
    data_type="numeric",
    units="points",
    quantization_type="threshold_bins",
    bins=[
        {"label": "FAILING", "max": 1.0},
        {"label": "POOR", "max": 2.0},
        {"label": "SATISFACTORY", "max": 2.5},
        {"label": "GOOD", "max": 3.0},
        {"label": "VERY_GOOD", "max": 3.5},
        {"label": "EXCELLENT", "max": 4.0},
    ],
    bin_rationale="Standard GPA classification",
    literature_reference="Academic grading conventions",
)

# Motivation sensor
MOTIVATION_SENSOR = SensorConfig(
    domain="education",
    variable_name="motivation",
    sensor_name="MOTIVATION",
    path="agent.motivation",
    data_type="numeric",
    units="score",
    quantization_type="threshold_bins",
    bins=[
        {"label": "LOW", "max": 0.33},
        {"label": "MODERATE", "max": 0.66},
        {"label": "HIGH", "max": 1.0},
    ],
    bin_rationale="Self-determination theory motivation levels",
    literature_reference="Ryan & Deci Self-Determination Theory",
)

# Family income sensor (for education context)
FAMILY_INCOME_SENSOR = SensorConfig(
    domain="education",
    variable_name="family_income",
    sensor_name="FAMILY_INCOME",
    path="agent.family_income",
    data_type="numeric",
    units="USD",
    quantization_type="threshold_bins",
    bins=[
        {"label": "LOW", "max": 40000},
        {"label": "MIDDLE", "max": 80000},
        {"label": "UPPER_MIDDLE", "max": 150000},
        {"label": "HIGH", "max": float("inf")},
    ],
    bin_rationale="Financial aid eligibility thresholds",
    literature_reference="FAFSA income thresholds",
)

# First generation student sensor
FIRST_GENERATION_SENSOR = SensorConfig(
    domain="education",
    variable_name="first_generation",
    sensor_name="FIRST_GENERATION",
    path="agent.first_generation",
    data_type="categorical",
    categories=["yes", "no"],
    bin_rationale="First-generation college student status",
    literature_reference="Higher education research",
)

# Employment status sensor
EMPLOYMENT_STATUS_SENSOR = SensorConfig(
    domain="education",
    variable_name="employment_status",
    sensor_name="EMPLOYMENT_STATUS",
    path="agent.employment_status",
    data_type="categorical",
    categories=[
        "unemployed",
        "part_time",
        "full_time",
        "self_employed",
    ],
    bin_rationale="Labor force participation categories",
    literature_reference="Bureau of Labor Statistics",
)

# Student debt sensor
STUDENT_DEBT_SENSOR = SensorConfig(
    domain="education",
    variable_name="student_debt",
    sensor_name="STUDENT_DEBT",
    path="agent.student_debt",
    data_type="numeric",
    units="USD",
    quantization_type="threshold_bins",
    bins=[
        {"label": "NONE", "max": 0},
        {"label": "LOW", "max": 20000},
        {"label": "MODERATE", "max": 50000},
        {"label": "HIGH", "max": 100000},
        {"label": "VERY_HIGH", "max": float("inf")},
    ],
    bin_rationale="Student loan debt distribution",
    literature_reference="Federal Reserve Student Loan Data",
)

# Academic field sensor
ACADEMIC_FIELD_SENSOR = SensorConfig(
    domain="education",
    variable_name="academic_field",
    sensor_name="ACADEMIC_FIELD",
    path="agent.academic_field",
    data_type="categorical",
    categories=[
        "stem",
        "business",
        "humanities",
        "social_sciences",
        "health",
        "education",
        "arts",
        "other",
    ],
    bin_rationale="Major academic field categories",
    literature_reference="CIP Classification of Instructional Programs",
)


# All sensors in a list
EDUCATION_SENSORS: List[str] = [
    "DEGREE_LEVEL",
    "GPA",
    "MOTIVATION",
    "FAMILY_INCOME",
    "FIRST_GENERATION",
    "EMPLOYMENT_STATUS",
    "STUDENT_DEBT",
    "ACADEMIC_FIELD",
]

# SensorConfig objects
EDUCATION_SENSOR_CONFIGS: Dict[str, SensorConfig] = {
    "DEGREE_LEVEL": DEGREE_LEVEL_SENSOR,
    "GPA": GPA_SENSOR,
    "MOTIVATION": MOTIVATION_SENSOR,
    "FAMILY_INCOME": FAMILY_INCOME_SENSOR,
    "FIRST_GENERATION": FIRST_GENERATION_SENSOR,
    "EMPLOYMENT_STATUS": EMPLOYMENT_STATUS_SENSOR,
    "STUDENT_DEBT": STUDENT_DEBT_SENSOR,
    "ACADEMIC_FIELD": ACADEMIC_FIELD_SENSOR,
}


def get_sensor(name: str) -> SensorConfig:
    """Get a sensor configuration by name."""
    return EDUCATION_SENSOR_CONFIGS.get(name)


def list_sensors() -> List[str]:
    """List available education sensors."""
    return EDUCATION_SENSORS.copy()
