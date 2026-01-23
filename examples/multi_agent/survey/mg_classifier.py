from typing import Tuple

import pandas as pd

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
