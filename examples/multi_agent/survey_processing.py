"""
Core functions for processing survey data.

This module contains the primary logic for cleaning, transforming, and
calculating scores from raw survey responses. It includes functions for
data loading, filtering, parsing individual responses, and determining
demographic statuses like Marginalized Group (MG) status.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import random

# Import necessary constants and structures
from .survey_data_structures import (
    SurveyHousehold, PMT_MAPPING, LIKERT_MAP, DEMO_COLUMNS,
    INCOME_MIDPOINTS, POVERTY_150_PCT
)

# Configuration constants
DATA_DIR = Path(__file__).parent / "data"
SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# =============================================================================
# DATA LOADING AND FILTERING
# =============================================================================

def load_survey_data(excel_path: Path) -> pd.DataFrame:
    """Load survey data from Excel file."""
    print(f"[INFO] Loading survey data from {excel_path}")
    df = pd.read_excel(excel_path, sheet_name="Sheet0")
    print(f"[INFO] Loaded {len(df)} rows, {len(df.columns)} columns")
    return df


def filter_nj_respondents(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to New Jersey respondents only."""
    nj_df = df[df["Q3"] == "New Jersey"].copy()
    print(f"[INFO] Filtered to {len(nj_df)} NJ respondents (from {len(df)})")
    return nj_df


# =============================================================================
# DATA PROCESSING AND SCORING
# =============================================================================

def compute_construct_score(row: pd.Series, columns: List[str]) -> float:
    """
    Compute mean score for a PMT construct.

    Args:
        row: Survey response row
        columns: List of column names for this construct

    Returns:
        Mean score (1-5), defaults to 3.0 if no valid responses
    """
    values = []
    for col in columns:
        if col in row.index and pd.notna(row[col]):
            val = row[col]
            # Convert Likert text to number
            if isinstance(val, str):
                val = LIKERT_MAP.get(val.strip(), 3)
            elif isinstance(val, (int, float)):
                val = max(1, min(5, val))  # Clamp to 1-5
            else:
                continue
            values.append(val)

    return np.mean(values) if values else 3.0


def determine_mg_status(row: pd.Series) -> Tuple[bool, int]:
    """
    Determine Marginalized Group status based on 2/3 criteria.

    Criteria:
    1. Housing cost burden >30%: Q41 = "Yes"
    2. No vehicle: Q8 = "No"
    3. Below 150% poverty line: Q43 < threshold (by family size)

    Returns:
        (is_mg, criteria_met_count)
    """
    criteria_met = 0

    # Criterion 1: Housing cost burden
    cost_burden = str(row.get("Q41", "")).strip().lower()
    if cost_burden == "yes":
        criteria_met += 1

    # Criterion 2: No vehicle
    vehicle = str(row.get("Q8", "")).strip().lower()
    if vehicle == "no":
        criteria_met += 1

    # Criterion 3: Below 150% poverty line
    income_bracket = str(row.get("Q43", ""))
    income = INCOME_MIDPOINTS.get(income_bracket, 50000)

    # Get family size (default to 3)
    family_size_raw = row.get("Q10", 3)
    if isinstance(family_size_raw, str):
        # Extract number from string like "3" or "more than 8"
        if "more than" in family_size_raw.lower():
            family_size = 8
        else:
            try:
                family_size = int(family_size_raw)
            except:
                family_size = 3
    else:
        family_size = int(family_size_raw) if pd.notna(family_size_raw) else 3

    family_size = max(1, min(8, family_size))
    poverty_threshold = POVERTY_150_PCT.get(family_size, 46800)

    if income < poverty_threshold:
        criteria_met += 1

    is_mg = criteria_met >= 2
    return is_mg, criteria_met


def parse_tenure(row: pd.Series) -> str:
    """Parse tenure status from survey response."""
    tenure_raw = str(row.get("Q5", "")).strip().lower()
    if "rent" in tenure_raw:
        return "Renter"
    elif "own" in tenure_raw:
        return "Owner"
    else:
        return "Owner"  # Default to Owner if unclear


def parse_generations(row: pd.Series) -> int:
    """Parse generations from survey response."""
    gen_raw = str(row.get("Q12", "1")).strip().lower()
    if "moved here" in gen_raw or gen_raw == "0":
        return 1
    elif "more than" in gen_raw:
        return 4
    else:
        try:
            return int(gen_raw)
        except:
            return 1


def parse_flood_frequency(row: pd.Series) -> int:
    """Parse flood frequency from survey response."""
    freq_raw = str(row.get("Q17", "0")).strip()
    if freq_raw.startswith("0"):
        return 0
    elif "1-2" in freq_raw or freq_raw == "1" or freq_raw == "2":
        return 2
    elif "3-4" in freq_raw:
        return 4
    elif "5-6" in freq_raw:
        return 6
    elif "7" in freq_raw or "more" in freq_raw.lower():
        return 7
    else:
        try:
            return int(freq_raw)
        except:
            return 0


def process_survey_row(row: pd.Series, idx: int) -> SurveyHousehold:
    """Process a single survey row into SurveyHousehold."""

    # Parse demographics
    tenure = parse_tenure(row)
    income_bracket = str(row.get("Q43", "More than $74,999"))
    income = INCOME_MIDPOINTS.get(income_bracket, 75000)

    # Family size
    family_size_raw = row.get("Q10", 3)
    if isinstance(family_size_raw, str):
        if "more than" in family_size_raw.lower():
            household_size = 8
        else:
            try:
                household_size = int(family_size_raw)
            except:
                household_size = 3
    else:
        household_size = int(family_size_raw) if pd.notna(family_size_raw) else 3

    generations = parse_generations(row)

    # Vehicle, children, elderly
    has_vehicle = str(row.get("Q8", "Yes")).strip().lower() == "yes"
    has_children = (
        str(row.get("Q13_1", "No")).strip().lower() == "yes" or
        str(row.get("Q13_2", "No")).strip().lower() == "yes"
    )
    has_elderly = str(row.get("Q13_3", "No")).strip().lower() == "yes"
    housing_cost_burden = str(row.get("Q41", "No")).strip().lower() == "yes"

    # Flood experience
    flood_experience = str(row.get("Q14", "No")).strip().lower() == "yes"
    flood_frequency = parse_flood_frequency(row)
    sfha_awareness = str(row.get("Q7", "No")).strip().lower() == "yes"

    # MG status
    mg, mg_criteria = determine_mg_status(row)

    # PMT constructs
    sc_score = compute_construct_score(row, PMT_MAPPING["SC"])
    pa_score = compute_construct_score(row, PMT_MAPPING["PA"])
    tp_score = compute_construct_score(row, PMT_MAPPING["TP"])
    cp_score = compute_construct_score(row, PMT_MAPPING["CP"])
    sp_score = compute_construct_score(row, PMT_MAPPING["SP"])

    # Raw text for memory generation
    recent_flood_text = str(row.get("Q15", ""))
    insurance_type = str(row.get("Q20", ""))
    post_flood_action = str(row.get("Q19", ""))
    zipcode = str(row.get("Q44", ""))

    return SurveyHousehold(
        survey_id=str(row.get("ResponseId", f"R{idx:04d}")),
        tenure=tenure,
        income_bracket=income_bracket,
        income=income,
        household_size=household_size,
        generations=generations,
        has_vehicle=has_vehicle,
        has_children=has_children,
        has_elderly=has_elderly,
        housing_cost_burden=housing_cost_burden,
        flood_experience=flood_experience,
        flood_frequency=flood_frequency,
        sfha_awareness=sfha_awareness,
        mg=mg,
        mg_criteria_met=mg_criteria,
        sc_score=round(sc_score, 2),
        pa_score=round(pa_score, 2),
        tp_score=round(tp_score, 2),
        cp_score=round(cp_score, 2),
        sp_score=round(sp_score, 2),
        recent_flood_text=recent_flood_text,
        insurance_type=insurance_type,
        post_flood_action=post_flood_action,
        zipcode=zipcode,
    )
