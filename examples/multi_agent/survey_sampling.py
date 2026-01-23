"""
Stratified sampling functions for survey data processing.

This module contains the logic for performing stratified sampling on
processed survey household data to create a representative sample for simulation,
ensuring proportional representation across key strata like Marginalized Group (MG)
status and tenure.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import random

# Import necessary structures
from .survey_data_structures import SurveyHousehold

# Configuration constants
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# =============================================================================
# STRATIFIED SAMPLING
# =============================================================================

def stratified_sample(
    households: List[SurveyHousehold],
    n_sample: int = 100,
    seed: int = SEED
) -> List[SurveyHousehold]:
    """
    Perform stratified sampling by MG status × tenure.

    Maintains original population proportions:
    - MG: ~16%, NMG: ~84%
    - Owner: ~64%, Renter: ~36%
    
    Args:
        households: List of all processed SurveyHousehold objects.
        n_sample: Target number of samples.
        seed: Random seed for reproducibility.

    Returns:
        A list of sampled SurveyHousehold objects.
    """
    random.seed(seed)
    np.random.seed(seed)

    # Group by strata
    strata = {
        ("MG", "Owner"): [],
        ("MG", "Renter"): [],
        ("NMG", "Owner"): [],
        ("NMG", "Renter"): [],
    }

    for h in households:
        mg_key = "MG" if h.mg else "NMG"
        strata[(mg_key, h.tenure)].append(h)

    # Calculate proportions
    total = len(households)
    proportions = {k: len(v) / total for k, v in strata.items()}

    print(f"\n[INFO] Population proportions:")
    for k, p in proportions.items():
        print(f"  {k}: {p:.1%} ({len(strata[k])} households)")

    # Sample from each stratum
    sampled = []
    for key, proportion in proportions.items():
        stratum_n = max(1, round(n_sample * proportion))
        available = strata[key]

        if len(available) >= stratum_n:
            sampled.extend(random.sample(available, stratum_n))
        else:
            # If not enough, take all available
            sampled.extend(available)
            print(f"[WARN] Stratum {key} has only {len(available)} (needed {stratum_n})")

    # Adjust if we have too many or too few
    if len(sampled) > n_sample:
        sampled = random.sample(sampled, n_sample)
    elif len(sampled) < n_sample:
        # Fill from largest stratum if needed (simple approach)
        remaining = n_sample - len(sampled)
        all_remaining = [h for h in households if h not in sampled]
        if all_remaining:
            sampled.extend(random.sample(all_remaining, min(remaining, len(all_remaining))))

    print(f"\n[INFO] Sampled {len(sampled)} households")

    # Verify sample proportions
    if sampled: # Avoid division by zero if sampled list is empty
        sample_mg = sum(1 for h in sampled if h.mg) / len(sampled)
        sample_owner = sum(1 for h in sampled if h.tenure == "Owner") / len(sampled)
        print(f"  MG ratio in sample: {sample_mg:.1%}")
        print(f"  Owner ratio in sample: {sample_owner:.1%}")

    return sampled
