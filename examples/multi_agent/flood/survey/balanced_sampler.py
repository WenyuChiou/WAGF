"""
Balanced 4-Cell Sampler for Paper 3 Experiment Design.

Samples equal numbers from each stratum (MG/NMG × Owner/Renter)
to ensure statistical power per subgroup, unlike the proportional
StratifiedSampler which preserves population ratios.

Design: 25 agents per cell = 100 total
  Cell A: MG-Owner (25)
  Cell B: MG-Renter (25)
  Cell C: NMG-Owner (25)
  Cell D: NMG-Renter (25)
"""

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BalancedSampleResult:
    """Result of balanced sampling."""
    profiles: List[Any]
    cell_counts: Dict[str, int]
    shortfalls: Dict[str, int]
    oversampled: bool


class BalancedSampler:
    """
    Sample equal counts from 4 strata (MG/NMG × Owner/Renter).

    If a stratum has fewer members than needed, either:
    - oversample (with replacement) if allow_oversample=True
    - take all available and report the shortfall
    """

    CELL_LABELS = {
        ("MG", "Owner"): "A",
        ("MG", "Renter"): "B",
        ("NMG", "Owner"): "C",
        ("NMG", "Renter"): "D",
    }

    def __init__(
        self,
        n_per_cell: int = 25,
        seed: int = 42,
        allow_oversample: bool = True,
    ):
        self.n_per_cell = n_per_cell
        self.seed = seed
        self.allow_oversample = allow_oversample

    def _get_stratum_key(self, profile: Any) -> Tuple[str, str]:
        """Extract (MG/NMG, Owner/Renter) from a profile."""
        if hasattr(profile, "mg"):
            mg_key = "MG" if profile.mg else "NMG"
        elif hasattr(profile, "is_mg"):
            mg_key = "MG" if profile.is_mg else "NMG"
        elif isinstance(profile, dict):
            mg_key = "MG" if profile.get("mg", False) else "NMG"
        else:
            mg_key = "NMG"

        if hasattr(profile, "tenure"):
            tenure = profile.tenure
        elif isinstance(profile, dict):
            tenure = profile.get("tenure", "Owner")
        else:
            tenure = "Owner"

        return (mg_key, tenure)

    def sample(
        self,
        profiles: List[Any],
        seed: Optional[int] = None,
    ) -> BalancedSampleResult:
        """
        Sample n_per_cell profiles from each of the 4 strata.

        Args:
            profiles: All available profiles (HouseholdProfile, MAAgentProfile, or dict)
            seed: Optional seed override

        Returns:
            BalancedSampleResult with profiles, counts, shortfalls, oversample flag
        """
        rng = random.Random(seed or self.seed)

        # Group into 4 strata
        strata: Dict[Tuple[str, str], List] = {
            ("MG", "Owner"): [],
            ("MG", "Renter"): [],
            ("NMG", "Owner"): [],
            ("NMG", "Renter"): [],
        }

        for p in profiles:
            key = self._get_stratum_key(p)
            if key in strata:
                strata[key].append(p)

        # Report population
        print(f"\n[BalancedSampler] Population: {len(profiles)} profiles")
        for key, members in strata.items():
            label = self.CELL_LABELS[key]
            print(f"  Cell {label} ({key[0]}-{key[1]}): {len(members)} available, need {self.n_per_cell}")

        # Sample from each stratum
        sampled = []
        cell_counts = {}
        shortfalls = {}
        oversampled = False

        for key in [("MG", "Owner"), ("MG", "Renter"), ("NMG", "Owner"), ("NMG", "Renter")]:
            label = self.CELL_LABELS[key]
            available = strata[key]
            needed = self.n_per_cell

            if len(available) >= needed:
                selected = rng.sample(available, needed)
            elif self.allow_oversample and len(available) > 0:
                # Sample with replacement to reach target
                selected = rng.choices(available, k=needed)
                oversampled = True
                shortfalls[f"{key[0]}-{key[1]}"] = needed - len(available)
                print(f"  [WARN] Cell {label}: oversampled {needed - len(available)} "
                      f"(pool={len(available)}, target={needed})")
            else:
                selected = list(available)
                shortfalls[f"{key[0]}-{key[1]}"] = needed - len(available)
                print(f"  [WARN] Cell {label}: only {len(available)} available (need {needed})")

            # Assign cell label metadata
            for p in selected:
                if hasattr(p, "__dict__"):
                    p._balanced_cell = label
                elif isinstance(p, dict):
                    p["_balanced_cell"] = label

            sampled.extend(selected)
            cell_counts[f"{key[0]}-{key[1]}"] = len(selected)

        total = sum(cell_counts.values())
        mg_count = cell_counts.get("MG-Owner", 0) + cell_counts.get("MG-Renter", 0)
        print(f"\n[BalancedSampler] Sampled {total} profiles")
        print(f"  MG: {mg_count} ({mg_count/total*100:.1f}%)")
        print(f"  NMG: {total - mg_count} ({(total-mg_count)/total*100:.1f}%)")
        if oversampled:
            print(f"  [NOTE] Oversampling used for {len(shortfalls)} cell(s)")

        return BalancedSampleResult(
            profiles=sampled,
            cell_counts=cell_counts,
            shortfalls=shortfalls,
            oversampled=oversampled,
        )
