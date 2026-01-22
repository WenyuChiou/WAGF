"""
MG (Marginalized Group) Classifier.

Classifies households as MG or NMG based on three criteria:
1. Housing cost burden >30% of income
2. No vehicle ownership
3. Below federal poverty line (based on family size and income)

A household is classified as MG if at least 2 of the 3 criteria are met.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from broker.modules.survey.survey_loader import SurveyRecord, INCOME_MIDPOINTS

logger = logging.getLogger(__name__)


@dataclass
class PovertyLineTable:
    """
    Federal Poverty Line thresholds by family size.

    Default values are 2024 Federal Poverty Guidelines for 48 contiguous states.
    """

    year: int = 2024
    thresholds: Dict[int, int] = None
    additional_person: int = 5380  # Amount added per person beyond 8

    def __post_init__(self):
        if self.thresholds is None:
            # 2024 Federal Poverty Guidelines
            self.thresholds = {
                1: 15060,
                2: 20440,
                3: 25820,
                4: 31200,
                5: 36580,
                6: 41960,
                7: 47340,
                8: 52720,
            }

    def get_threshold(self, family_size: int) -> int:
        """Get poverty threshold for a given family size."""
        if family_size <= 0:
            family_size = 1

        if family_size <= 8:
            return self.thresholds.get(family_size, self.thresholds[1])

        # For families > 8, add additional_person for each extra member
        base = self.thresholds[8]
        extra = (family_size - 8) * self.additional_person
        return base + extra


@dataclass
class MGClassificationResult:
    """Result of MG classification for a household."""

    is_mg: bool
    score: int  # Number of criteria met (0-3)
    criteria: Dict[str, bool]  # Individual criterion results
    details: Dict[str, str]  # Human-readable details

    @property
    def group_label(self) -> str:
        return "MG" if self.is_mg else "NMG"


class MGClassifier:
    """
    Classifier for Marginalized Group (MG) status.

    MG Definition (at least 2 of 3 criteria):
    1. Housing cost burden: >30% of income spent on housing
    2. No vehicle: Household does not own a vehicle
    3. Below poverty: Household income below federal poverty line for family size
    """

    def __init__(
        self,
        poverty_table: Optional[PovertyLineTable] = None,
        income_midpoints: Optional[Dict[str, int]] = None,
        threshold: int = 2,  # Minimum criteria to be classified as MG
    ):
        """
        Initialize the classifier.

        Args:
            poverty_table: Custom poverty line thresholds (uses 2024 defaults if None)
            income_midpoints: Custom income bracket midpoints
            threshold: Minimum number of criteria to classify as MG (default: 2)
        """
        self.poverty_table = poverty_table or PovertyLineTable()
        self.income_midpoints = income_midpoints or INCOME_MIDPOINTS
        self.threshold = threshold

    def classify(self, record: SurveyRecord) -> MGClassificationResult:
        """
        Classify a household as MG or NMG.

        Args:
            record: SurveyRecord with household data

        Returns:
            MGClassificationResult with classification and details
        """
        # Criterion 1: Housing cost burden >30%
        housing_cost_burden = record.housing_cost_burden
        housing_detail = "Yes (>30%)" if housing_cost_burden else "No (<=30%)"

        # Criterion 2: No vehicle
        no_vehicle = not record.vehicle_ownership
        vehicle_detail = "No vehicle" if no_vehicle else "Has vehicle"

        # Criterion 3: Below poverty line
        income = self.income_midpoints.get(record.income_bracket, 50000)
        poverty_threshold = self.poverty_table.get_threshold(record.family_size)
        below_poverty = income < poverty_threshold
        poverty_detail = (
            f"Income ${income:,} < Poverty ${poverty_threshold:,} (Family: {record.family_size})"
            if below_poverty
            else f"Income ${income:,} >= Poverty ${poverty_threshold:,} (Family: {record.family_size})"
        )

        # Calculate score
        criteria = {
            "housing_cost_burden": housing_cost_burden,
            "no_vehicle": no_vehicle,
            "below_poverty": below_poverty,
        }
        score = sum(criteria.values())
        is_mg = score >= self.threshold

        details = {
            "housing_cost_burden": housing_detail,
            "no_vehicle": vehicle_detail,
            "below_poverty": poverty_detail,
        }

        return MGClassificationResult(
            is_mg=is_mg,
            score=score,
            criteria=criteria,
            details=details,
        )

    def classify_batch(
        self, records: list[SurveyRecord]
    ) -> Tuple[list[MGClassificationResult], Dict[str, int]]:
        """
        Classify multiple households and return statistics.

        Args:
            records: List of SurveyRecord objects

        Returns:
            Tuple of (results_list, statistics_dict)
        """
        results = [self.classify(r) for r in records]

        # Calculate statistics
        mg_count = sum(1 for r in results if r.is_mg)
        nmg_count = len(results) - mg_count

        stats = {
            "total": len(results),
            "mg_count": mg_count,
            "nmg_count": nmg_count,
            "mg_ratio": mg_count / len(results) if results else 0,
            "criteria_met_0": sum(1 for r in results if r.score == 0),
            "criteria_met_1": sum(1 for r in results if r.score == 1),
            "criteria_met_2": sum(1 for r in results if r.score == 2),
            "criteria_met_3": sum(1 for r in results if r.score == 3),
            "housing_burden_count": sum(
                1 for r in results if r.criteria["housing_cost_burden"]
            ),
            "no_vehicle_count": sum(1 for r in results if r.criteria["no_vehicle"]),
            "below_poverty_count": sum(
                1 for r in results if r.criteria["below_poverty"]
            ),
        }

        logger.info(
            f"MG Classification: {mg_count} MG ({stats['mg_ratio']:.1%}), "
            f"{nmg_count} NMG out of {len(results)} households"
        )

        return results, stats


def classify_household(
    record: SurveyRecord,
    poverty_table: Optional[PovertyLineTable] = None,
) -> MGClassificationResult:
    """
    Convenience function to classify a single household.

    Args:
        record: SurveyRecord to classify
        poverty_table: Optional custom poverty thresholds

    Returns:
        MGClassificationResult
    """
    classifier = MGClassifier(poverty_table=poverty_table)
    return classifier.classify(record)
