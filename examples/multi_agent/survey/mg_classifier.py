"""
Marginalized Group (MG) Classifier for Multi-Agent Flood Simulation.

MG Classification based on 2/3 criteria:
1. Housing cost burden >30%: Q41 = "Yes"
2. No vehicle: Q8 = "No"
3. Below 150% poverty line: Q43 < threshold (by family size)

Reference: US Census Bureau poverty thresholds, HUD cost burden definitions
"""

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import pandas as pd


# 150% of 2024 HHS Poverty Guidelines by family size
POVERTY_150_PCT = {
    1: 22_110,
    2: 29_940,
    3: 37_770,
    4: 45_600,
    5: 53_430,
    6: 61_260,
    7: 69_090,
    8: 76_920,
}

# Income bracket midpoints (from broker survey loader)
INCOME_MIDPOINTS = {
    "less_than_15k": 10000,
    "15k_to_25k": 20000,
    "25k_to_35k": 30000,
    "35k_to_50k": 42500,
    "50k_to_60k": 55000,
    "60k_to_75k": 67500,
    "75k_to_100k": 87500,
    "100k_to_150k": 125000,
    "150k_to_200k": 175000,
    "more_than_200k": 250000,
}


@dataclass
class MGClassificationResult:
    """Result of MG classification."""
    is_mg: bool
    score: int  # Number of criteria met (0-3)
    criteria: Dict[str, bool]


class MGClassifier:
    """
    Marginalized Group classifier.

    Classifies agents as MG if they meet 2 or more of 3 criteria:
    1. Housing cost burden >30%
    2. No vehicle
    3. Below 150% poverty line
    """

    def __init__(self, threshold: int = 2):
        """
        Initialize classifier.

        Args:
            threshold: Number of criteria needed to classify as MG (default: 2)
        """
        self.threshold = threshold

    def classify(self, record: Any) -> MGClassificationResult:
        """
        Classify a survey record as MG or NMG.

        Args:
            record: Survey record (FloodSurveyRecord or similar with raw_data)

        Returns:
            MGClassificationResult with is_mg, score, and criteria dict
        """
        criteria = {
            "housing_burden": False,
            "no_vehicle": False,
            "below_poverty": False,
        }

        # Get raw data from record
        if hasattr(record, "raw_data"):
            raw = record.raw_data
        elif isinstance(record, dict):
            raw = record
        else:
            raw = {}

        # Criterion 1: Housing cost burden >30%
        if hasattr(record, "housing_cost_burden"):
            criteria["housing_burden"] = record.housing_cost_burden
        else:
            cost_burden = str(raw.get("Q41", "")).strip().lower()
            criteria["housing_burden"] = cost_burden == "yes"

        # Criterion 2: No vehicle
        if hasattr(record, "vehicle_ownership"):
            criteria["no_vehicle"] = not record.vehicle_ownership
        else:
            vehicle = str(raw.get("Q8", "")).strip().lower()
            criteria["no_vehicle"] = vehicle == "no"

        # Criterion 3: Below 150% poverty line
        income_bracket = getattr(record, "income_bracket", raw.get("Q43", "50k_to_60k"))
        if isinstance(income_bracket, str):
            income = INCOME_MIDPOINTS.get(income_bracket, 50000)
        else:
            income = 50000

        family_size = getattr(record, "family_size", raw.get("Q10", 3))
        if isinstance(family_size, str):
            if "more than" in family_size.lower():
                family_size = 8
            else:
                try:
                    family_size = int(family_size)
                except ValueError:
                    family_size = 3
        family_size = max(1, min(8, int(family_size) if pd.notna(family_size) else 3))

        poverty_threshold = POVERTY_150_PCT.get(family_size, 46800)
        criteria["below_poverty"] = income < poverty_threshold

        # Calculate score
        score = sum(criteria.values())
        is_mg = score >= self.threshold

        return MGClassificationResult(
            is_mg=is_mg,
            score=score,
            criteria=criteria,
        )


def determine_mg_status(row: pd.Series) -> Tuple[bool, int]:
    """
    Determine Marginalized Group status based on 2/3 criteria.

    Legacy function for backward compatibility.

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
        if "more than" in family_size_raw.lower():
            family_size = 8
        else:
            try:
                family_size = int(family_size_raw)
            except ValueError:
                family_size = 3
    else:
        family_size = int(family_size_raw) if pd.notna(family_size_raw) else 3

    family_size = max(1, min(8, family_size))
    poverty_threshold = POVERTY_150_PCT.get(family_size, 46800)

    if income < poverty_threshold:
        criteria_met += 1

    is_mg = criteria_met >= 2
    return is_mg, criteria_met
