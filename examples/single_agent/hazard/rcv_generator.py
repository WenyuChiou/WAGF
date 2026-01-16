"""
Replacement Cost Value (RCV) Generator.

Generates realistic RCV values for buildings and contents based on:
- Income bracket correlation
- Housing tenure (owner/renter)
- MG status adjustment
- NJ property value distributions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RCVResult:
    """Generated RCV values for a household."""

    building_rcv_usd: float  # Building replacement cost (0 for renters)
    contents_rcv_usd: float  # Contents value
    total_rcv_usd: float

    @property
    def building_rcv_kUSD(self) -> float:
        return self.building_rcv_usd / 1000.0

    @property
    def contents_rcv_kUSD(self) -> float:
        return self.contents_rcv_usd / 1000.0

    def to_dict(self) -> dict:
        return {
            "building_rcv_usd": round(self.building_rcv_usd, 2),
            "contents_rcv_usd": round(self.contents_rcv_usd, 2),
            "total_rcv_usd": round(self.total_rcv_usd, 2),
            "building_rcv_kUSD": round(self.building_rcv_kUSD, 2),
            "contents_rcv_kUSD": round(self.contents_rcv_kUSD, 2),
        }


# NJ Property Value Distribution Parameters by Income Tier
# Based on Census/ACS data for New Jersey residential properties
NJ_BUILDING_RCV_PARAMS = {
    "low_income": {
        "mu": 180_000,  # Mean building value
        "sigma": 0.35,  # Log-normal sigma
        "min": 80_000,
        "max": 350_000,
    },
    "mid_income": {
        "mu": 320_000,
        "sigma": 0.30,
        "min": 150_000,
        "max": 600_000,
    },
    "high_income": {
        "mu": 480_000,
        "sigma": 0.25,
        "min": 250_000,
        "max": 1_000_000,
    },
}

# Contents value as ratio of building RCV
CONTENTS_RATIO_RANGES = {
    "owner": (0.35, 0.55),  # 35-55% of building value
    "renter": (15_000, 50_000),  # Absolute range for renters
}

# Income bracket to tier mapping
INCOME_TO_TIER = {
    "less_than_25k": "low_income",
    "25k_to_30k": "low_income",
    "30k_to_35k": "low_income",
    "35k_to_40k": "mid_income",
    "40k_to_45k": "mid_income",
    "45k_to_50k": "mid_income",
    "50k_to_60k": "mid_income",
    "60k_to_75k": "high_income",
    "75k_or_more": "high_income",
}


class RCVGenerator:
    """
    Generate realistic RCV values based on household characteristics.

    Uses log-normal distribution correlated with income bracket.
    Applies MG adjustment (lower values for marginalized groups).
    """

    def __init__(
        self,
        seed: int = 42,
        mg_adjustment: float = 0.85,  # MG households have 15% lower values
        building_params: Optional[Dict] = None,
    ):
        """
        Initialize the RCV generator.

        Args:
            seed: Random seed for reproducibility
            mg_adjustment: Multiplier for MG households (default 0.85 = 15% lower)
            building_params: Custom building RCV distribution parameters
        """
        self.rng = np.random.default_rng(seed)
        self.mg_adjustment = mg_adjustment
        self.building_params = building_params or NJ_BUILDING_RCV_PARAMS

    def generate(
        self,
        income_bracket: str,
        is_owner: bool,
        is_mg: bool = False,
        family_size: int = 3,
    ) -> RCVResult:
        """
        Generate RCV values for a household.

        Args:
            income_bracket: Standardized income bracket key
            is_owner: True if owner-occupied
            is_mg: True if marginalized group
            family_size: Number of household members (affects contents)

        Returns:
            RCVResult with building and contents values
        """
        # Determine income tier
        tier = INCOME_TO_TIER.get(income_bracket, "mid_income")
        params = self.building_params[tier]

        if is_owner:
            # Generate building RCV
            building_rcv = self._generate_building_rcv(params, is_mg)

            # Generate contents as ratio of building
            ratio_min, ratio_max = CONTENTS_RATIO_RANGES["owner"]
            # Larger families have more contents
            family_factor = 1.0 + (family_size - 3) * 0.05
            family_factor = np.clip(family_factor, 0.8, 1.3)

            contents_ratio = self.rng.uniform(ratio_min, ratio_max) * family_factor
            contents_rcv = building_rcv * contents_ratio

        else:
            # Renters don't own building
            building_rcv = 0.0

            # Generate contents directly
            cont_min, cont_max = CONTENTS_RATIO_RANGES["renter"]

            # Scale by income tier
            if tier == "low_income":
                cont_max = 30_000
            elif tier == "high_income":
                cont_min = 25_000
                cont_max = 75_000

            # MG adjustment
            if is_mg:
                cont_max *= self.mg_adjustment

            # Family size factor
            family_factor = 1.0 + (family_size - 3) * 0.08
            family_factor = np.clip(family_factor, 0.7, 1.5)

            contents_rcv = self.rng.uniform(cont_min, cont_max) * family_factor

        return RCVResult(
            building_rcv_usd=round(building_rcv, 2),
            contents_rcv_usd=round(contents_rcv, 2),
            total_rcv_usd=round(building_rcv + contents_rcv, 2),
        )

    def _generate_building_rcv(
        self, params: Dict, is_mg: bool
    ) -> float:
        """Generate building RCV from log-normal distribution."""
        mu = params["mu"]
        sigma = params["sigma"]

        # Apply MG adjustment
        if is_mg:
            mu *= self.mg_adjustment

        # Generate from log-normal
        log_mu = np.log(mu) - (sigma**2) / 2  # Adjust for log-normal mean
        value = self.rng.lognormal(log_mu, sigma)

        # Clip to range
        return float(np.clip(value, params["min"], params["max"]))

    def generate_batch(
        self,
        records: list,  # List of dicts with income_bracket, is_owner, is_mg, family_size
    ) -> list[RCVResult]:
        """
        Generate RCV values for multiple households.

        Args:
            records: List of dicts with household characteristics

        Returns:
            List of RCVResult objects
        """
        results = []
        for rec in records:
            result = self.generate(
                income_bracket=rec.get("income_bracket", "mid_income"),
                is_owner=rec.get("is_owner", True),
                is_mg=rec.get("is_mg", False),
                family_size=rec.get("family_size", 3),
            )
            results.append(result)

        # Log statistics
        if results:
            bldg_values = [r.building_rcv_usd for r in results if r.building_rcv_usd > 0]
            cont_values = [r.contents_rcv_usd for r in results]

            logger.info(
                f"Generated RCV for {len(results)} households: "
                f"Building avg ${np.mean(bldg_values):,.0f}, "
                f"Contents avg ${np.mean(cont_values):,.0f}"
            )

        return results


def generate_rcv(
    income_bracket: str,
    is_owner: bool,
    is_mg: bool = False,
    family_size: int = 3,
    seed: int = 42,
) -> RCVResult:
    """
    Convenience function to generate RCV for a single household.

    Args:
        income_bracket: Standardized income bracket key
        is_owner: True if owner-occupied
        is_mg: True if marginalized group
        family_size: Number of household members
        seed: Random seed

    Returns:
        RCVResult
    """
    gen = RCVGenerator(seed=seed)
    return gen.generate(
        income_bracket=income_bracket,
        is_owner=is_owner,
        is_mg=is_mg,
        family_size=family_size,
    )
