"""
Flood Survey Loader for MA (Multi-Agent Flood Simulation).

This module extends the generic SurveyRecord with flood-specific fields
and provides flood-specific column mappings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from broker.modules.survey.survey_loader import SurveyRecord, SurveyLoader, INCOME_MIDPOINTS


@dataclass
class FloodSurveyRecord(SurveyRecord):
    """Survey record extended with flood-specific fields."""

    # Flood Experience
    flood_experience: bool = False
    financial_loss: bool = False


# Flood-specific column mapping (extends DEFAULT_COLUMN_MAPPING)
FLOOD_COLUMN_MAPPING = {
    "family_size": {"index": 28, "code": "Q7"},
    "generations": {"index": 30, "code": "Q9"},
    "income_bracket": {"index": 104, "code": "Q40"},
    "housing_status": {"index": 22, "code": "Q2"},
    "house_type": {"index": 20, "code": "Q1"},
    "housing_cost_burden": {"index": 101, "code": "Q38"},
    "vehicle_ownership": {"index": 26, "code": "Q5"},
    "flood_experience": {"index": 34, "code": "Q11"},  # Flood-specific
    "financial_loss": {"index": 36, "code": "Q13"},  # Flood-specific
    "children_under_6": {"index": 31, "code": "Q10_1"},
    "children_6_18": {"index": 32, "code": "Q10_2"},
    "elderly_over_65": {"index": 33, "code": "Q10_3"},
}


class FloodSurveyLoader(SurveyLoader):
    """Survey loader for flood adaptation surveys."""

    def __init__(
        self,
        schema_path: Optional[Path] = None,
        required_fields: Optional[List[str]] = None,
        narrative_fields: Optional[List[str]] = None,
        narrative_labels: Optional[Dict[str, str]] = None,
        value_maps: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """Initialize flood survey loader with flood-specific mappings."""
        super().__init__(
            column_mapping=FLOOD_COLUMN_MAPPING,
            schema_path=schema_path,
            required_fields=required_fields,
            narrative_fields=narrative_fields,
            narrative_labels=narrative_labels,
            value_maps=value_maps,
        )

    def _parse_row(self, idx: int, row) -> Optional[FloodSurveyRecord]:
        """Parse a row into a FloodSurveyRecord (extends parent with flood fields)."""

        # Use parent parsing for common fields
        base_record = super()._parse_row(idx, row)
        if base_record is None:
            return None

        # Get flood-specific values
        def get_val(field: str) -> Any:
            col_info = self.column_mapping.get(field, {})
            col_idx = self._resolved_columns.get(field)
            if col_idx is not None and col_idx < len(row):
                value = row.iloc[col_idx]
                return self._apply_value_map(field, value, col_info)
            return None

        # Create FloodSurveyRecord with all fields from base plus flood-specific
        return FloodSurveyRecord(
            record_id=base_record.record_id,
            family_size=base_record.family_size,
            generations=base_record.generations,
            income_bracket=base_record.income_bracket,
            housing_status=base_record.housing_status,
            house_type=base_record.house_type,
            housing_cost_burden=base_record.housing_cost_burden,
            vehicle_ownership=base_record.vehicle_ownership,
            children_under_6=base_record.children_under_6,
            children_6_18=base_record.children_6_18,
            elderly_over_65=base_record.elderly_over_65,
            raw_data=base_record.raw_data,
            flood_experience=self._parse_boolean(get_val("flood_experience")),
            financial_loss=self._parse_boolean(get_val("financial_loss")),
        )


def load_flood_survey_data(
    excel_path: Path,
    max_records: Optional[int] = None,
    schema_path: Optional[Path] = None,
) -> Tuple[List[FloodSurveyRecord], List[Tuple[int, str]]]:
    """
    Convenience function to load flood survey data.

    Args:
        excel_path: Path to Excel file
        max_records: Maximum records to load
        schema_path: Optional path to YAML schema

    Returns:
        Tuple of (records, validation_errors)
    """
    loader = FloodSurveyLoader(schema_path=schema_path)
    records = loader.load(excel_path, max_records=max_records)
    return records, loader.validation_errors
