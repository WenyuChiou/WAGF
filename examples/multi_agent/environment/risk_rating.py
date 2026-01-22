"""
Risk Rating 2.0 Premium Calculator.

Implements NFIP-compliant premium calculation per FLOODABM Supplementary Materials.

References:
- FEMA (2021) Risk Rating 2.0: Equity in Action
- FLOODABM Supplementary Tables S1-S2
- USACE (2006) Depth-Damage Relationships
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


# =============================================================================
# FLOODABM CONSTANTS (Table S2)
# =============================================================================

# Base Premium Rates (per $1,000 of coverage)
# r1k,s = $3.56 per $1K structure RCV
# r1k,c = $4.90 per $1K contents value
R1K_STRUCTURE = 3.56  # $/1K
R1K_CONTENTS = 4.90   # $/1K

# Coverage Limits
LIMIT_STRUCTURE = 250_000  # Ls: Max structure coverage
LIMIT_CONTENTS = 100_000   # Lc: Max contents coverage

# Deductibles
DEDUCTIBLE_STRUCTURE = 1_000  # DDs
DEDUCTIBLE_CONTENTS = 1_000   # DDc

# Reserve and Fees
RESERVE_FUND_FACTOR = 1.15  # R = 1.15
SMALL_FEE = 100  # F = $100 (federal policy fee, ICC, etc.)


# =============================================================================
# INITIAL INSURANCE UPTAKE RATES (Table S1)
# =============================================================================
# Based on: Bradt et al. (2020), Dixon (2006), Kousky et al. (2018)

INITIAL_UPTAKE = {
    "flood_prone": {
        "owner": 0.25,   # 25% - Homeowners in flood-prone areas
        "renter": 0.08,  # 8% - Renters in flood-prone areas
    },
    "non_flood_prone": {
        "owner": 0.03,   # 3% - Homeowners outside flood-prone areas
        "renter": 0.01,  # 1% - Renters outside flood-prone areas
    }
}


# =============================================================================
# FLOOD ZONE RISK MULTIPLIERS
# =============================================================================
# Based on FEMA Risk Rating 2.0 methodology

ZONE_MULTIPLIERS = {
    "VE": 2.5,    # Coastal high hazard (velocity)
    "AE": 1.5,    # High risk with Base Flood Elevation (BFE)
    "A": 1.4,     # High risk without BFE
    "AO": 1.3,    # Shallow flooding (sheet flow)
    "AH": 1.3,    # Shallow flooding with ponding
    "AR": 1.2,    # Areas with reduced risk (levee system)
    "X500": 0.8,  # Moderate risk (500-year floodplain)
    "X": 0.5,     # Minimal risk (outside floodplain)
    "B": 0.6,     # Legacy zone (moderate risk)
    "C": 0.4,     # Legacy zone (minimal risk)
    # PRB zone mapping
    "HIGH": 1.5,
    "MEDIUM": 1.0,
    "LOW": 0.5,
}


@dataclass
class PremiumResult:
    """Premium calculation result with detailed breakdown."""

    annual_premium: float  # Final annual premium
    structure_premium: float  # Structure component
    contents_premium: float  # Contents component
    base_rate_structure: float  # r1k,s applied
    base_rate_contents: float  # r1k,c applied
    zone_multiplier: float  # Risk zone adjustment
    discounts_applied: Dict[str, float]  # Individual discounts
    effective_rate: float  # Premium / total coverage

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "annual_premium": round(self.annual_premium, 2),
            "structure_premium": round(self.structure_premium, 2),
            "contents_premium": round(self.contents_premium, 2),
            "base_rate_structure": self.base_rate_structure,
            "base_rate_contents": self.base_rate_contents,
            "zone_multiplier": round(self.zone_multiplier, 2),
            "discounts_applied": {k: round(v, 4) for k, v in self.discounts_applied.items()},
            "effective_rate": round(self.effective_rate, 6),
        }


class RiskRating2Calculator:
    """
    Calculate NFIP premiums using Risk Rating 2.0 methodology.

    Key factors considered:
    - Property-specific flood risk (zone)
    - Distance to water source
    - Building characteristics (elevation)
    - Replacement cost value (RCV)
    - Community Rating System (CRS) discount

    Reference: FLOODABM Supplementary Materials
    """

    def __init__(
        self,
        r1k_structure: float = R1K_STRUCTURE,
        r1k_contents: float = R1K_CONTENTS,
        crs_discount: float = 0.0,  # Community Rating System discount (0-0.45)
    ):
        """
        Initialize the calculator.

        Args:
            r1k_structure: Premium rate per $1K of structure coverage
            r1k_contents: Premium rate per $1K of contents coverage
            crs_discount: CRS discount rate (0.0-0.45, depends on community class)
        """
        self.r1k_structure = r1k_structure
        self.r1k_contents = r1k_contents
        self.crs_discount = min(0.45, max(0.0, crs_discount))

    def calculate_premium(
        self,
        rcv_structure: float,
        rcv_contents: float,
        flood_zone: str,
        is_elevated: bool = False,
        is_owner: bool = True,
        distance_to_water_ft: Optional[float] = None,
        prior_claims: int = 0,
    ) -> PremiumResult:
        """
        Calculate annual NFIP premium.

        Formula (FLOODABM-aligned):
            structure_premium = (rcv_structure / 1000) * r1k_structure
            contents_premium = (rcv_contents / 1000) * r1k_contents
            gross_premium = (structure + contents) * zone_multiplier
            annual_premium = gross_premium * (1 - discounts) + fees

        Args:
            rcv_structure: Structure replacement cost value (0 for renters)
            rcv_contents: Contents value
            flood_zone: FEMA flood zone (AE, VE, X, etc.) or PRB zone (HIGH, MEDIUM, LOW)
            is_elevated: Whether property is elevated above BFE
            is_owner: True for owners, False for renters
            distance_to_water_ft: Distance to nearest flood source (optional)
            prior_claims: Number of prior flood insurance claims

        Returns:
            PremiumResult with detailed breakdown
        """
        # Cap coverage at NFIP limits
        covered_structure = min(rcv_structure, LIMIT_STRUCTURE) if is_owner else 0
        covered_contents = min(rcv_contents, LIMIT_CONTENTS)

        # Base premiums (per $1K of coverage)
        structure_premium = (covered_structure / 1000) * self.r1k_structure
        contents_premium = (covered_contents / 1000) * self.r1k_contents

        # Zone risk multiplier
        zone_multiplier = self._get_zone_multiplier(flood_zone)

        # Calculate discounts
        discounts = self._calculate_discounts(
            is_elevated=is_elevated,
            distance_to_water_ft=distance_to_water_ft,
            prior_claims=prior_claims,
        )

        # Total discount (capped at 70%)
        total_discount = min(0.70, sum(discounts.values()))

        # Apply zone multiplier and discounts
        gross_premium = (structure_premium + contents_premium) * zone_multiplier
        net_premium = gross_premium * (1 - total_discount)

        # Add fixed fees
        annual_premium = net_premium + SMALL_FEE

        # Calculate effective rate
        total_coverage = covered_structure + covered_contents
        effective_rate = annual_premium / total_coverage if total_coverage > 0 else 0

        return PremiumResult(
            annual_premium=round(annual_premium, 2),
            structure_premium=round(structure_premium, 2),
            contents_premium=round(contents_premium, 2),
            base_rate_structure=self.r1k_structure,
            base_rate_contents=self.r1k_contents,
            zone_multiplier=zone_multiplier,
            discounts_applied=discounts,
            effective_rate=round(effective_rate, 6),
        )

    def _get_zone_multiplier(self, flood_zone: str) -> float:
        """Get risk multiplier based on FEMA flood zone."""
        return ZONE_MULTIPLIERS.get(flood_zone.upper(), 1.0)

    def _calculate_discounts(
        self,
        is_elevated: bool,
        distance_to_water_ft: Optional[float],
        prior_claims: int,
    ) -> Dict[str, float]:
        """
        Calculate applicable discounts.

        Returns:
            Dict mapping discount type to discount rate
        """
        discounts = {}

        # Elevation discount (up to 50% for elevated structures)
        # Reference: FEMA states elevation can reduce premiums by 40-60%
        if is_elevated:
            discounts["elevation"] = 0.50

        # Distance discount (simplified - properties farther from water)
        if distance_to_water_ft and distance_to_water_ft > 500:
            # Max 20% discount for properties > 500ft from water
            discounts["distance"] = min(0.20, (distance_to_water_ft - 500) / 5000)

        # CRS discount (community-level)
        if self.crs_discount > 0:
            discounts["crs"] = self.crs_discount

        # Prior claims surcharge (negative discount)
        if prior_claims > 0:
            # Each claim increases premium by 10%, up to 30%
            discounts["claims_surcharge"] = -min(0.30, prior_claims * 0.10)

        return discounts


def get_initial_uptake_probability(
    is_flood_prone: bool,
    is_owner: bool,
) -> float:
    """
    Get initial insurance uptake probability.

    Based on FLOODABM Table S1:
    - Flood-prone homeowner: 25%
    - Flood-prone renter: 8%
    - Non-flood-prone homeowner: 3%
    - Non-flood-prone renter: 1%

    Args:
        is_flood_prone: Whether property is in flood-prone area
        is_owner: True for owners, False for renters

    Returns:
        Uptake probability (0.0-1.0)
    """
    zone_key = "flood_prone" if is_flood_prone else "non_flood_prone"
    tenure_key = "owner" if is_owner else "renter"
    return INITIAL_UPTAKE[zone_key][tenure_key]


def calculate_simple_premium(
    rcv_building: float,
    rcv_contents: float,
    flood_zone: str = "AE",
    is_elevated: bool = False,
) -> float:
    """
    Simplified premium calculation for quick estimates.

    Args:
        rcv_building: Building RCV
        rcv_contents: Contents RCV
        flood_zone: Flood zone code
        is_elevated: Whether elevated

    Returns:
        Estimated annual premium
    """
    calc = RiskRating2Calculator()
    result = calc.calculate_premium(
        rcv_structure=rcv_building,
        rcv_contents=rcv_contents,
        flood_zone=flood_zone,
        is_elevated=is_elevated,
    )
    return result.annual_premium
