"""
Survey Manager

This module acts as the main entry point for survey data loading, processing,
sampling, and saving. It orchestrates the workflow by importing and utilizing
functions from other survey-related modules like data structures, processing,
and sampling utilities.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import random

# Import necessary components from other modules
from .survey_data_structures import SurveyHousehold
from .survey_processing import (
    load_survey_data, filter_nj_respondents, process_survey_row
)
from .survey_sampling import stratified_sample

# Configuration constants
DATA_DIR = Path(__file__).parent / "data"
SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# =============================================================================
# SAVING FUNCTION
# =============================================================================

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
    if households: # Avoid division by zero if list is empty
        mg_count = sum(1 for h in households if h.mg)
        owner_count = sum(1 for h in households if h.tenure == 'Owner')
        flood_exp_count = sum(1 for h in households if h.flood_experience)

        print(f"MG households: {mg_count} ({mg_count/len(households):.1%})")
        print(f"Owners: {owner_count} ({owner_count/len(households):.1%})")
        print(f"Flood experience: {flood_exp_count} ({flood_exp_count/len(households):.1%})")

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
        default=SEED,
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
