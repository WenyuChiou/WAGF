from typing import List

import numpy as np

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
        # Fill from largest stratum
        remaining = n_sample - len(sampled)
        all_remaining = [h for h in households if h not in sampled]
        if all_remaining:
            sampled.extend(random.sample(all_remaining, min(remaining, len(all_remaining))))

    print(f"\n[INFO] Sampled {len(sampled)} households")

    # Verify sample proportions
    sample_mg = sum(1 for h in sampled if h.mg) / len(sampled)
    sample_owner = sum(1 for h in sampled if h.tenure == "Owner") / len(sampled)
    print(f"  MG ratio: {sample_mg:.1%}")
    print(f"  Owner ratio: {sample_owner:.1%}")

    return sampled
