"""
Process Full Qualtrics Survey Data for Paper 3.

Reads cleaned_complete_data_977.xlsx (920 respondents) and produces
cleaned_survey_full.csv with ALL processed respondents (no sampling).
BalancedSampler then selects 100 agents from this pool.

Key differences from survey_loader.py:
- Handles NUMERIC Qualtrics codes (1/2 for Yes/No, 1-10 for income, etc.)
- Does not filter by NJ (optional flag; full Qualtrics data may already be filtered)
- Outputs ALL respondents (no stratified sampling — that's BalancedSampler's job)
- Same output format as cleaned_survey.csv for compatibility

Column mapping verified against:
- Draft V6.docx questionnaire (42 questions)
- Qualtrics export column names (Q1-Q45 with +3 offset from questionnaire)
- SM_clean_vr.docx Table 12

Qualtrics offset: Q(n) in Qualtrics = Q(n-3) in questionnaire (for Q4+)
  Q1/Q2 = consent + Prolific PID (not in questionnaire)
  Q3 = screener/state question
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple

# =============================================================================
# COLUMN MAPPINGS (Qualtrics column names)
# =============================================================================

# PMT construct → Qualtrics column names
PMT_MAPPING = {
    # Social Capital (6 items): Questionnaire Q18_1-6 → Qualtrics Q21_1-6
    "SC": ["Q21_1", "Q21_2", "Q21_3", "Q21_4", "Q21_5", "Q21_6"],
    # Place Attachment (9 items): Questionnaire Q18_7-15 → Qualtrics Q21_7-15
    "PA": ["Q21_7", "Q21_8", "Q21_9", "Q21_10", "Q21_11",
           "Q21_12", "Q21_13", "Q21_14", "Q21_15"],
    # Threat Perception (11 items): Questionnaire Q19_1-11 → Qualtrics Q22_1-11
    "TP": ["Q22_1", "Q22_2", "Q22_3", "Q22_4", "Q22_5",
           "Q22_6", "Q22_7", "Q22_8", "Q22_9", "Q22_10", "Q22_11"],
    # Coping Perception (8 items): Q21_1-2 + Q22_{1,2,4,5,7,8} → Q24_1-2 + Q25_{1,2,4,5,7,8}
    "CP": ["Q24_1", "Q24_2", "Q25_1", "Q25_2", "Q25_4",
           "Q25_5", "Q25_7", "Q25_8"],
    # Stakeholder Perception (3 items): Q22_{3,6,9} → Q25_{3,6,9}
    "SP": ["Q25_3", "Q25_6", "Q25_9"],
}

# Income bracket codes (Qualtrics Q43 numeric code → label, midpoint)
INCOME_BRACKETS = {
    1:  ("Less than $25,000", 20000),
    2:  ("$25,000 to $29,999", 27500),
    3:  ("$30,000 to $34,999", 32500),
    4:  ("$35,000 to $39,999", 37500),
    5:  ("$40,000 to $44,999", 42500),
    6:  ("$45,000 to $49,999", 47500),
    7:  ("$50,000 to $54,999", 52500),
    8:  ("$55,000 to $59,999", 57500),
    9:  ("$60,000 to $74,999", 67500),
    10: ("More than $74,999", 100000),
}

# 150% Federal Poverty Guidelines by family size (2024 HHS)
POVERTY_150_PCT = {
    1: 22110, 2: 29940, 3: 37770, 4: 45600,
    5: 53430, 6: 61260, 7: 69090, 8: 76920,
}

# Flood frequency codes (Qualtrics Q17 → count)
FLOOD_FREQ_MAP = {
    1: 0,   # Never / 0 times
    2: 2,   # 1-2 times
    3: 4,   # 3-4 times
    4: 6,   # 5-6 times
    5: 7,   # 7 or more times
}

# Recent flood text codes (Qualtrics Q15)
RECENT_FLOOD_MAP = {
    1: "Less than 1 year ago",
    2: "1 to 5 years ago",
    3: "6 to 10 years ago",
    4: "More than 10 years ago",
    7: "Not sure",
}

# Insurance type codes (Qualtrics Q26 = Questionnaire Q23)
INSURANCE_TYPE_MAP = {
    1: "Private flood insurance",
    2: "NFIP",
    3: "Both private and NFIP",
    4: "None",
}

# Post-flood action codes (Qualtrics Q19 = Questionnaire Q16)
POST_FLOOD_ACTION_MAP = {
    1: "Filed insurance claim",
    2: "Applied for government assistance",
    3: "Elevated house",
    4: "Participated in buyout",
    5: "Did nothing",
}


# =============================================================================
# DATA CLASS
# =============================================================================

@dataclass
class SurveyHousehold:
    """Processed survey household — same schema as cleaned_survey.csv."""
    survey_id: str
    tenure: str
    income_bracket: str
    income: float
    household_size: int
    generations: int
    has_vehicle: bool
    has_children: bool
    has_elderly: bool
    housing_cost_burden: bool
    flood_experience: bool
    flood_frequency: int
    sfha_awareness: bool
    mg: bool
    mg_criteria_met: int
    sc_score: float
    pa_score: float
    tp_score: float
    cp_score: float
    sp_score: float
    recent_flood_text: str
    insurance_type: str
    post_flood_action: str
    zipcode: str


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def compute_pmt_score(row: pd.Series, columns: List[str]) -> float:
    """Compute mean of Likert items (1-5 scale). Returns 3.0 if no valid data."""
    values = []
    for col in columns:
        if col in row.index and pd.notna(row[col]):
            val = row[col]
            if isinstance(val, (int, float, np.integer, np.floating)):
                values.append(max(1, min(5, float(val))))
    return round(np.mean(values), 2) if values else 3.0


def classify_mg(housing_burden: bool, no_vehicle: bool,
                income_midpoint: float, family_size: int,
                threshold: int = 2) -> Tuple[bool, int]:
    """
    MG classification: 2/3 criteria met.
    1. Housing cost burden >30%
    2. No vehicle
    3. Income below 150% poverty line (by family size)
    """
    criteria_met = 0
    if housing_burden:
        criteria_met += 1
    if no_vehicle:
        criteria_met += 1
    poverty_line = POVERTY_150_PCT.get(min(8, max(1, family_size)), 45600)
    if income_midpoint < poverty_line:
        criteria_met += 1
    return (criteria_met >= threshold, criteria_met)


def process_row(row: pd.Series, idx: int) -> SurveyHousehold:
    """Process a single Qualtrics row with NUMERIC codes."""

    # --- Survey ID ---
    survey_id = str(row.get("PROLIFIC_PID", row.get("ResponseId", f"P{idx:04d}")))

    # --- Tenure (Q5): 1=Rent, 2=Own w/ mortgage, 3=Own w/o mortgage, 4=Other ---
    tenure_code = int(row.get("Q5", 2)) if pd.notna(row.get("Q5")) else 2
    tenure = "Renter" if tenure_code == 1 else "Owner"

    # --- Income (Q43): 1-10 numeric codes ---
    income_code = int(row.get("Q43", 10)) if pd.notna(row.get("Q43")) else 10
    income_bracket, income = INCOME_BRACKETS.get(income_code, ("More than $74,999", 100000))

    # --- Family size (Q10): 1-8 ---
    family_raw = row.get("Q10", 3)
    if pd.notna(family_raw):
        household_size = max(1, min(8, int(family_raw)))
    else:
        household_size = 3

    # --- Generations (Q12): 1-5 ---
    gen_raw = row.get("Q12", 1)
    if pd.notna(gen_raw):
        generations = max(1, min(5, int(gen_raw)))
    else:
        generations = 1

    # --- Vehicle (Q8): 1=Yes, 2=No ---
    vehicle_code = int(row.get("Q8", 1)) if pd.notna(row.get("Q8")) else 1
    has_vehicle = (vehicle_code == 1)

    # --- Children / Elderly (Q13_1/2/3): 1=Yes, 2=No ---
    has_children = (
        (int(row.get("Q13_1", 2)) if pd.notna(row.get("Q13_1")) else 2) == 1 or
        (int(row.get("Q13_2", 2)) if pd.notna(row.get("Q13_2")) else 2) == 1
    )
    has_elderly = (int(row.get("Q13_3", 2)) if pd.notna(row.get("Q13_3")) else 2) == 1

    # --- Housing cost burden (Q41): 1=Yes, 2=No ---
    # Qualtrics Q41 = Questionnaire Q38 (housing cost >30%)
    burden_code = int(row.get("Q41", 2)) if pd.notna(row.get("Q41")) else 2
    housing_cost_burden = (burden_code == 1)

    # --- Flood experience (Q14_0): 1=Yes experienced, 2=No ---
    flood_code = int(row.get("Q14_0", 2)) if pd.notna(row.get("Q14_0")) else 2
    flood_experience = (flood_code == 1)

    # --- Flood frequency (Q17): numeric code 1-5 ---
    freq_code = row.get("Q17", 1)
    if pd.notna(freq_code):
        flood_frequency = FLOOD_FREQ_MAP.get(int(freq_code), 0)
    else:
        flood_frequency = 0

    # --- SFHA awareness (Q7): 1=Yes, 2=No ---
    sfha_code = int(row.get("Q7", 2)) if pd.notna(row.get("Q7")) else 2
    sfha_awareness = (sfha_code == 1)

    # --- MG classification ---
    mg, mg_criteria = classify_mg(housing_cost_burden, not has_vehicle,
                                  income, household_size)

    # --- PMT construct scores ---
    sc_score = compute_pmt_score(row, PMT_MAPPING["SC"])
    pa_score = compute_pmt_score(row, PMT_MAPPING["PA"])
    tp_score = compute_pmt_score(row, PMT_MAPPING["TP"])
    cp_score = compute_pmt_score(row, PMT_MAPPING["CP"])
    sp_score = compute_pmt_score(row, PMT_MAPPING["SP"])

    # --- Text fields for memory generation ---
    recent_code = row.get("Q15", "")
    if pd.notna(recent_code):
        recent_flood_text = RECENT_FLOOD_MAP.get(int(recent_code), str(recent_code))
    else:
        recent_flood_text = ""

    ins_code = row.get("Q26", "")
    if pd.notna(ins_code):
        insurance_type = INSURANCE_TYPE_MAP.get(int(ins_code), str(ins_code))
    else:
        insurance_type = ""

    action_code = row.get("Q19", "")
    if pd.notna(action_code):
        post_flood_action = POST_FLOOD_ACTION_MAP.get(int(action_code), str(action_code))
    else:
        post_flood_action = ""

    zipcode = str(row.get("Q44", "")) if pd.notna(row.get("Q44")) else ""

    return SurveyHousehold(
        survey_id=survey_id,
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
        sc_score=sc_score,
        pa_score=pa_score,
        tp_score=tp_score,
        cp_score=cp_score,
        sp_score=sp_score,
        recent_flood_text=recent_flood_text,
        insurance_type=insurance_type,
        post_flood_action=post_flood_action,
        zipcode=zipcode,
    )


def filter_nj(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to NJ respondents by zip code (07xxx, 08xxx)."""
    zips = df["Q44"].astype(str).str.strip()
    nj_mask = zips.str.startswith("07") | zips.str.startswith("08")
    nj_df = df[nj_mask].copy()
    print(f"[INFO] Filtered to {len(nj_df)} NJ respondents (from {len(df)} total)")
    return nj_df


def process_full_survey(
    excel_path: str,
    output_path: str,
    nj_only: bool = True,
) -> List[SurveyHousehold]:
    """
    Process full Qualtrics data and save ALL respondents (no sampling).

    Args:
        excel_path: Path to cleaned_complete_data_977.xlsx
        output_path: Path for output CSV
        nj_only: If True, filter to NJ zip codes only

    Returns:
        List of all processed SurveyHousehold objects
    """
    print(f"[INFO] Loading {excel_path}")
    df = pd.read_excel(excel_path)
    print(f"[INFO] Loaded {len(df)} rows, {len(df.columns)} columns")

    if nj_only:
        df = filter_nj(df)

    # Process all rows
    households = []
    errors = 0
    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            h = process_row(row, idx)
            households.append(h)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"[WARN] Row {idx}: {e}")

    print(f"[INFO] Processed {len(households)} households ({errors} errors)")

    # Save to CSV
    records = [asdict(h) for h in households]
    out_df = pd.DataFrame(records)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)

    # Summary statistics
    n = len(households)
    mg_count = sum(1 for h in households if h.mg)
    owner_count = sum(1 for h in households if h.tenure == "Owner")
    renter_count = n - owner_count
    flood_count = sum(1 for h in households if h.flood_experience)

    mg_owners = sum(1 for h in households if h.mg and h.tenure == "Owner")
    mg_renters = sum(1 for h in households if h.mg and h.tenure == "Renter")
    nmg_owners = sum(1 for h in households if not h.mg and h.tenure == "Owner")
    nmg_renters = sum(1 for h in households if not h.mg and h.tenure == "Renter")

    print(f"\n{'='*60}")
    print(f"  Survey Processing Summary")
    print(f"{'='*60}")
    print(f"  Total households: {n}")
    print(f"  MG: {mg_count} ({mg_count/n*100:.1f}%)")
    print(f"  Owners: {owner_count} ({owner_count/n*100:.1f}%)")
    print(f"  Flood experience: {flood_count} ({flood_count/n*100:.1f}%)")
    print(f"\n  4-Cell Composition (available pool):")
    print(f"    Cell A (MG-Owner):   {mg_owners:4d}  {'OK' if mg_owners >= 25 else 'SHORTFALL (need 25)'}")
    print(f"    Cell B (MG-Renter):  {mg_renters:4d}  {'OK' if mg_renters >= 25 else 'SHORTFALL (need 25)'}")
    print(f"    Cell C (NMG-Owner):  {nmg_owners:4d}  {'OK' if nmg_owners >= 25 else 'SHORTFALL (need 25)'}")
    print(f"    Cell D (NMG-Renter): {nmg_renters:4d}  {'OK' if nmg_renters >= 25 else 'SHORTFALL (need 25)'}")

    print(f"\n  PMT Construct Averages:")
    for name in ["sc", "pa", "tp", "cp", "sp"]:
        scores = [getattr(h, f"{name}_score") for h in households]
        print(f"    {name.upper()}: {np.mean(scores):.2f} (std={np.std(scores):.2f})")

    print(f"\n  MG Criteria Distribution:")
    for c in range(4):
        count = sum(1 for h in households if h.mg_criteria_met == c)
        print(f"    {c} criteria met: {count}")

    print(f"\n[OK] Saved to {output_path}")
    return households


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process full Qualtrics survey for Paper 3")
    parser.add_argument(
        "--input", type=str,
        default="C:/Users/wenyu/OneDrive - Lehigh University/Desktop/Lehigh/NSF-project/"
                "questionniare/Results/Formal_test/processed_data/cleaned_complete_data_977.xlsx",
        help="Path to Qualtrics Excel file",
    )
    parser.add_argument(
        "--output", type=str,
        default="examples/multi_agent/flood/data/cleaned_survey_full.csv",
        help="Path for output CSV (all respondents, no sampling)",
    )
    parser.add_argument(
        "--no-nj-filter", action="store_true",
        help="Include all respondents (not just NJ)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    output_path = script_dir / args.output

    process_full_survey(
        excel_path=args.input,
        output_path=str(output_path),
        nj_only=not args.no_nj_filter,
    )
