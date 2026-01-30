"""
Survey Data Loader for MA System

Loads and processes survey data from Excel to create agent profiles.
Implements:
- NJ filtering (755 responses)
- Stratified sampling (100 agents by MG × tenure)
- PMT construct calculation (SC, PA, TP, CP, SP)
- MG classification (2/3 criteria)

References:
- SM_clean_vr.docx Table 12: Variable mapping
- outline_V1.docx: Traditional ABM design
"""

import pandas as pd
import numpy as np
from survey.pmt_calculator import compute_construct_score
from survey.mg_classifier import determine_mg_status
from survey.stratified_sampler import stratified_sample
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import random

# Seed for reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

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
    "Strongly Disagree": 1,
    "Strongly disagree": 1,
    "Disagree": 2,
    "disagree": 2,
    "Neutral": 3,
    "neutral": 3,
    "Agree": 4,
    "agree": 4,
    "Strongly Agree": 5,
    "Strongly agree": 5,
}

# Demographic column mapping
DEMO_COLUMNS = {
    "state": "Q3",           # NJ/NY/Others
    "housing_type": "Q4",    # Single/Multi-family
    "tenure": "Q5",          # Own/Rent
    "construction_year": "Q6",
    "sfha_awareness": "Q7",  # Yes/No
    "vehicle": "Q8",         # Yes/No (MG indicator)
    "family_size": "Q10",    # 1-8+
    "residency_length": "Q11",
    "generations": "Q12",    # 1-4+
    "children_under6": "Q13_1",
    "children_6_18": "Q13_2",
    "elderly_over65": "Q13_3",
    "flood_experience": "Q14",  # Yes/No
    "recent_flood": "Q15",      # MCQ
    "flood_frequency": "Q17",   # MCQ
    "post_flood_action": "Q19",
    "insurance_type": "Q20",    # Insurance coverage type
    "cost_burden": "Q41",       # Yes/No (MG indicator)
    "income": "Q43",            # MCQ (MG indicator)
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
    1: 22590,
    2: 30660,
    3: 38730,
    4: 46800,
    5: 54870,
    6: 62940,
    7: 71010,
    8: 79080,
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


# =============================================================================
# CORE FUNCTIONS
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


def save_to_csv(households: List[SurveyHousehold], output_path: Path) -> None:
    """Save processed households to CSV."""
    records = [asdict(h) for h in households]
    df = pd.DataFrame(records)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False)
    print(f"\n[OK] Saved {len(households)} households to {output_path}")

    # Print summary statistics
    print("\n=== Survey Data Summary ===")
    print(f"Total households: {len(households)}")
    print(f"MG households: {sum(1 for h in households if h.mg)} ({sum(1 for h in households if h.mg)/len(households):.1%})")
    print(f"Owners: {sum(1 for h in households if h.tenure == 'Owner')} ({sum(1 for h in households if h.tenure == 'Owner')/len(households):.1%})")
    print(f"Flood experience: {sum(1 for h in households if h.flood_experience)} ({sum(1 for h in households if h.flood_experience)/len(households):.1%})")

    print("\n=== PMT Construct Averages ===")
    print(f"SC (Social Capital): {np.mean([h.sc_score for h in households]):.2f}")
    print(f"PA (Place Attachment): {np.mean([h.pa_score for h in households]):.2f}")
    print(f"TP (Threat Perception): {np.mean([h.tp_score for h in households]):.2f}")
    print(f"CP (Coping Perception): {np.mean([h.cp_score for h in households]):.2f}")
    print(f"SP (Stakeholder Perception): {np.mean([h.sp_score for h in households]):.2f}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def load_and_process_survey(
    excel_path: Path,
    output_path: Path,
    n_agents: int = 100,
    seed: int = SEED
) -> List[SurveyHousehold]:
    """
    Main function to load, process, and sample survey data.

    Args:
        excel_path: Path to Excel file with survey data
        output_path: Path to save cleaned CSV
        n_agents: Number of agents to sample
        seed: Random seed for reproducibility

    Returns:
        List of processed SurveyHousehold objects
    """
    # Load data
    df = load_survey_data(excel_path)

    # Filter to NJ
    nj_df = filter_nj_respondents(df)

    # Process all NJ respondents
    print(f"\n[INFO] Processing {len(nj_df)} NJ respondents...")
    households = []
    for idx, (_, row) in enumerate(nj_df.iterrows()):
        try:
            h = process_survey_row(row, idx)
            households.append(h)
        except Exception as e:
            print(f"[WARN] Failed to process row {idx}: {e}")

    print(f"[INFO] Successfully processed {len(households)} households")

    # Stratified sampling
    sampled = stratified_sample(households, n_agents, seed)

    # Save to CSV
    save_to_csv(sampled, output_path)

    return sampled


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load and process survey data for MA system")
    parser.add_argument(
        "--input",
        type=str,
        default="input/initial_household data.xlsx",
        help="Path to input Excel file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/cleaned_survey.csv",
        help="Path to output CSV file"
    )
    parser.add_argument(
        "--n-agents",
        type=int,
        default=100,
        help="Number of agents to sample"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed"
    )
    args = parser.parse_args()

    # Resolve paths relative to this file
    script_dir = Path(__file__).parent
    excel_path = script_dir / args.input
    output_path = script_dir / args.output

    # Run
    households = load_and_process_survey(
        excel_path=excel_path,
        output_path=output_path,
        n_agents=args.n_agents,
        seed=args.seed
    )

    print(f"\n[DONE] Processed {len(households)} households")
