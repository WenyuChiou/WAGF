"""
Depth Sampler for assigning flood zones to agents.

Assigns agents to flood depth zones based on their reported flood experience.
Uses stratified sampling from PRB flood depth distribution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Tuple

import numpy as np

# Use Protocol for duck typing to avoid circular imports
class FloodExperienceRecord(Protocol):
    """Protocol for records with flood experience data."""

    flood_experience: bool
    financial_loss: bool


logger = logging.getLogger(__name__)


class DepthCategory(Enum):
    """Flood depth categories based on PRB distribution."""

    DRY = "dry"
    SHALLOW = "shallow"  # 0-0.5m
    MODERATE = "moderate"  # 0.5-1.0m
    DEEP = "deep"  # 1.0-2.0m
    VERY_DEEP = "very_deep"  # 2.0-4.0m
    EXTREME = "extreme"  # 4.0m+


# Depth ranges for each category (min, max) in meters
DEPTH_RANGES = {
    DepthCategory.DRY: (0.0, 0.0),
    DepthCategory.SHALLOW: (0.01, 0.5),
    DepthCategory.MODERATE: (0.5, 1.0),
    DepthCategory.DEEP: (1.0, 2.0),
    DepthCategory.VERY_DEEP: (2.0, 4.0),
    DepthCategory.EXTREME: (4.0, 8.0),
}

# PRB observed distribution ratios (from analysis)
PRB_DISTRIBUTION = {
    DepthCategory.DRY: 0.7693,
    DepthCategory.SHALLOW: 0.0251,
    DepthCategory.MODERATE: 0.0293,
    DepthCategory.DEEP: 0.0895,
    DepthCategory.VERY_DEEP: 0.0741,
    DepthCategory.EXTREME: 0.0127,
}


@dataclass
class PositionAssignment:
    """Result of position assignment for an agent."""

    zone: DepthCategory
    base_depth_m: float  # Sampled depth within zone
    cell_id: Optional[Tuple[int, int]] = None  # Grid cell if available
    flood_probability: float = 0.0  # Annual flood probability based on zone

    @property
    def zone_name(self) -> str:
        return self.zone.value

    def to_dict(self) -> Dict:
        return {
            "zone": self.zone_name,
            "base_depth_m": round(self.base_depth_m, 3),
            "cell_id": self.cell_id,
            "flood_probability": round(self.flood_probability, 3),
        }


class DepthSampler:
    """
    Sample flood depths and assign positions based on flood experience.

    Assignment logic:
    - flood_experience=True + financial_loss=True -> deep/very_deep/extreme
    - flood_experience=True + no_loss -> shallow/moderate
    - flood_experience=False -> mostly dry, some shallow
    """

    # Probability weights for each experience category
    WEIGHTS_FLOOD_WITH_LOSS = {
        DepthCategory.DEEP: 0.55,
        DepthCategory.VERY_DEEP: 0.35,
        DepthCategory.EXTREME: 0.10,
    }

    WEIGHTS_FLOOD_NO_LOSS = {
        DepthCategory.SHALLOW: 0.60,
        DepthCategory.MODERATE: 0.40,
    }

    WEIGHTS_NO_FLOOD = {
        DepthCategory.DRY: 0.85,
        DepthCategory.SHALLOW: 0.15,
    }

    def __init__(
        self,
        seed: int = 42,
        cell_pools: Optional[Dict[DepthCategory, List[Tuple[int, int, float]]]] = None,
    ):
        """
        Initialize the depth sampler.

        Args:
            seed: Random seed for reproducibility
            cell_pools: Pre-computed pools of cells by category from PRB grid
        """
        self.rng = np.random.default_rng(seed)
        self.cell_pools = cell_pools

    def assign_position(self, record: FloodExperienceRecord) -> PositionAssignment:
        """
        Assign flood zone position based on survey record.

        Args:
            record: SurveyRecord with flood experience data

        Returns:
            PositionAssignment with zone and depth
        """
        # Determine category weights based on flood experience
        if record.flood_experience:
            if record.financial_loss:
                weights = self.WEIGHTS_FLOOD_WITH_LOSS
            else:
                weights = self.WEIGHTS_FLOOD_NO_LOSS
        else:
            weights = self.WEIGHTS_NO_FLOOD

        # Sample category
        categories = list(weights.keys())
        probs = list(weights.values())
        zone = self.rng.choice(categories, p=probs)

        # Sample depth within category
        depth = self._sample_depth_in_zone(zone)

        # Get cell from pool if available
        cell_id = None
        if self.cell_pools and zone in self.cell_pools:
            pool = self.cell_pools[zone]
            if pool:
                idx = self.rng.integers(0, len(pool))
                cell_id = (pool[idx][0], pool[idx][1])
                depth = pool[idx][2]  # Use actual depth from grid

        # Calculate flood probability based on zone
        flood_prob = self._get_flood_probability(zone)

        return PositionAssignment(
            zone=zone,
            base_depth_m=depth,
            cell_id=cell_id,
            flood_probability=flood_prob,
        )

    def _sample_depth_in_zone(self, zone: DepthCategory) -> float:
        """Sample a depth value within a zone's range."""
        min_d, max_d = DEPTH_RANGES[zone]

        if zone == DepthCategory.DRY:
            return 0.0

        # Use triangular distribution (mode near lower end)
        mode = min_d + (max_d - min_d) * 0.3
        return float(self.rng.triangular(min_d, mode, max_d))

    def _get_flood_probability(self, zone: DepthCategory) -> float:
        """
        Estimate annual flood probability based on zone.

        Based on PRB historical data (13 years, 2011-2023).
        """
        # Rough estimates based on zone flooding frequency
        probs = {
            DepthCategory.DRY: 0.0,
            DepthCategory.SHALLOW: 0.15,  # ~2 years in 13
            DepthCategory.MODERATE: 0.30,  # ~4 years in 13
            DepthCategory.DEEP: 0.50,  # ~6-7 years in 13
            DepthCategory.VERY_DEEP: 0.70,  # ~9 years in 13
            DepthCategory.EXTREME: 0.85,  # ~11 years in 13
        }
        return probs.get(zone, 0.0)

    def assign_batch(
        self, records: List[FloodExperienceRecord]
    ) -> Tuple[List[PositionAssignment], Dict[str, int]]:
        """
        Assign positions for multiple records.

        Args:
            records: List of SurveyRecord objects

        Returns:
            Tuple of (assignments, zone_counts)
        """
        assignments = [self.assign_position(r) for r in records]

        # Count by zone
        zone_counts = {}
        for cat in DepthCategory:
            zone_counts[cat.value] = sum(
                1 for a in assignments if a.zone == cat
            )

        logger.info(f"Position assignments: {zone_counts}")

        return assignments, zone_counts


def sample_flood_depth_for_year(
    base_depth: float,
    year_severity: float = 1.0,
    rng: Optional[np.random.Generator] = None,
) -> float:
    """
    Sample actual flood depth for a specific year.

    Adds variability to base depth based on year severity.

    Args:
        base_depth: Base depth from position assignment
        year_severity: Multiplier for flood severity (1.0 = average)
        rng: Random number generator

    Returns:
        Actual flood depth in meters for this year
    """
    if rng is None:
        rng = np.random.default_rng()

    if base_depth == 0:
        return 0.0

    # Add random variation (+/- 30%)
    variation = rng.uniform(0.7, 1.3)
    depth = base_depth * year_severity * variation

    return max(0.0, float(depth))
