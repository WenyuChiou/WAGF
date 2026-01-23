"""
Data structures and constants for survey data processing.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Configuration constants moved here
DATA_DIR = Path(__file__).parent / "data"
SEED = 42

# =============================================================================
# COLUMN MAPPINGS (SM_clean_vr.docx Table 12)
# =============================================================================

# Questionnaire Q → Excel column mapping
# Q18-X → Q21_X, Q19-X → Q22_X, Q21-X → Q24_X, Q22-X → Q25_X

PMT_MAPPING = {
    # Social Capital (SC1-SC6): Q18-1 to Q18-6 → Q21_1 to Q21_6
    "SC": ["Q21_1", "Q21_2", "Q21_3", "Q21_4", "Q21_5", "Q21_6"],

    # Place Attachment (PA1-PA9): Q18-7 to Q18-15 → Q21_7 to Q21_15
    "PA": ["Q21_7", "Q21_8", "Q21_9", "Q21_10", "Q21_11",
           "Q21_12", "Q21_13", "Q21_14", "Q21_15"],

    # Threat Perception (TP1-TP11): Q19-1 to Q19-11 → Q22_1 to Q22_11
    "TP": ["Q22_1", "Q22_2", "Q22_3", "Q22_4", "Q22_5",
           "Q22_6", "Q22_7", "Q22_8", "Q22_9", "Q22_10", "Q22_11"],

    # Coping Perception (CP1-CP8): Q21-1,2 + Q22-1,2,4,5,7,8
    # Note: Q21 → Q24, Q22 → Q25
    "CP": ["Q24_1", "Q24_2", "Q25_1", "Q25_2", "Q25_4",
           "Q25_5", "Q25_7", "Q25_8"],

    # Stakeholder Perception (SP1-SP3): Q22-3,6,9 → Q25_3, Q25_6, Q25_9
    "SP": ["Q25_3", "Q25_6", "Q25_9"],
}

# Likert scale mapping
LIKERT_MAP = {
    "Strongly Disagree": 1, "Strongly disagree": 1,
    "Disagree": 2, "disagree": 2,
    "Neutral": 3, "neutral": 3,
    "Agree": 4, "agree": 4,
    "Strongly Agree": 5, "Strongly agree": 5,
}

# Demographic column mapping
DEMO_COLUMNS = {
    "state": "Q3",
    "housing_type": "Q4",
    "tenure": "Q5",
    "construction_year": "Q6",
    "sfha_awareness": "Q7",
    "vehicle": "Q8",
    "family_size": "Q10",
    "residency_length": "Q11",
    "generations": "Q12",
    "children_under6": "Q13_1",
    "children_6_18": "Q13_2",
    "elderly_over65": "Q13_3",
    "flood_experience": "Q14",
    "recent_flood": "Q15",
    "flood_frequency": "Q17",
    "post_flood_action": "Q19",
    "insurance_type": "Q20",
    "cost_burden": "Q41",
    "income": "Q43",
    "zipcode": "Q44",
}

# Income bracket midpoints (USD)
INCOME_MIDPOINTS = {
    "Less than $25,000": 20000,
    "$25,000 to $29,999": 27500,
    "$30,000 to $34,999": 32500,
    "$35,000 to $39,999": 37500,
    "$40,000 to $44,999": 42500,
    "$45,000 to $49,999": 47500,
    "$50,000 to $54,999": 52500,
    "$55,000 to $59,999": 57500,
    "$60,000 to $74,999": 67500,
    "More than $74,999": 100000,
}

# 2024 Federal Poverty Guidelines (150% level for MG classification)
POVERTY_150_PCT = {
    1: 22590, 2: 30660, 3: 38730, 4: 46800, 5: 54870,
    6: 62940, 7: 71010, 8: 79080,
}

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SurveyHousehold:
    """Processed survey household data."""
    survey_id: str

    # Demographics
    tenure: str  # "Owner" or "Renter"
    income_bracket: str
    income: float
    household_size: int
    generations: int
    has_vehicle: bool
    has_children: bool
    has_elderly: bool
    housing_cost_burden: bool

    # Flood Experience
    flood_experience: bool
    flood_frequency: int
    sfha_awareness: bool

    # MG Status
    mg: bool
    mg_criteria_met: int  # 0-3

    # PMT Constructs (1-5 scale)
    sc_score: float
    pa_score: float
    tp_score: float
    cp_score: float
    sp_score: float

    # Raw survey data for memory generation
    recent_flood_text: str
    insurance_type: str
    post_flood_action: str
    zipcode: str
