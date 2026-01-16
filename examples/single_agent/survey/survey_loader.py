"""
Survey data loader for household flood adaptation survey.

Loads and validates survey data from Excel file, mapping columns to agent attributes.
Designed to be configurable via YAML schema for different survey formats.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

logger = logging.getLogger(__name__)


@dataclass
class SurveyRecord:
    """Single validated survey record with all relevant fields."""

    record_id: str

    # Demographics
    family_size: int
    generations: str  # "moved_here", "1", "2", "3", "more_than_3"
    income_bracket: str
    housing_status: str  # "mortgage", "rent", "own_free"
    house_type: str  # "single_family", "multi_family", etc.

    # MG Classification Factors
    housing_cost_burden: bool  # >30% of income on housing
    vehicle_ownership: bool

    # Flood Experience
    flood_experience: bool
    financial_loss: bool

    # Household Composition
    children_under_6: bool
    children_6_18: bool
    elderly_over_65: bool

    # Raw data for extensibility
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_children(self) -> bool:
        return self.children_under_6 or self.children_6_18

    @property
    def has_vulnerable_members(self) -> bool:
        return self.children_under_6 or self.elderly_over_65

    @property
    def is_owner(self) -> bool:
        return self.housing_status in ("mortgage", "own_free")

    @property
    def is_renter(self) -> bool:
        return self.housing_status == "rent"


# Default column mapping for the household flood adaptation survey
# Based on actual Excel structure with header at row 1 (0-indexed)
DEFAULT_COLUMN_MAPPING = {
    "family_size": {"index": 28, "code": "Q7"},  # How many people live in your household
    "generations": {"index": 30, "code": "Q9"},  # How many generations
    "income_bracket": {"index": 104, "code": "Q40"},  # Annual household income
    "housing_status": {"index": 22, "code": "Q2"},  # Current housing status
    "house_type": {"index": 20, "code": "Q1"},  # Which type of house
    "housing_cost_burden": {"index": 101, "code": "Q38"},  # >30% of income on housing
    "vehicle_ownership": {"index": 26, "code": "Q5"},  # Does household own a vehicle
    "flood_experience": {"index": 34, "code": "Q11"},  # Ever experienced flood
    "financial_loss": {"index": 36, "code": "Q13"},  # Flood financial loss
    "children_under_6": {"index": 31, "code": "Q10_1"},  # Children <6
    "children_6_18": {"index": 32, "code": "Q10_2"},  # Children 6-18
    "elderly_over_65": {"index": 33, "code": "Q10_3"},  # Elderly >65
}

# Income bracket standardization
INCOME_BRACKETS = {
    "Less than $25,000": "less_than_25k",
    "less than $25,000": "less_than_25k",
    "$25,000 to $29,999": "25k_to_30k",
    "25,000 to 29,999": "25k_to_30k",
    "$30,000 to $34,999": "30k_to_35k",
    "30,000 to 34,999": "30k_to_35k",
    "$35,000 to $39,999": "35k_to_40k",
    "35,000 to 39,999": "35k_to_40k",
    "$40,000 to $44,999": "40k_to_45k",
    "40,000 to 44,999": "40k_to_45k",
    "$45,000 to $49,999": "45k_to_50k",
    "45,000 to 49,999": "45k_to_50k",
    "$50,000 to $59,999": "50k_to_60k",
    "50,000 to 59,999": "50k_to_60k",
    "$60,000 to $74,999": "60k_to_75k",
    "60,000 to 74,999": "60k_to_75k",
    "$75,000 or more": "75k_or_more",
    "More than $75,000": "75k_or_more",
    "75,000 or more": "75k_or_more",
}

# Income midpoints for calculations (USD)
INCOME_MIDPOINTS = {
    "less_than_25k": 12500,
    "25k_to_30k": 27500,
    "30k_to_35k": 32500,
    "35k_to_40k": 37500,
    "40k_to_45k": 42500,
    "45k_to_50k": 47500,
    "50k_to_60k": 55000,
    "60k_to_75k": 67500,
    "75k_or_more": 100000,
}


class SurveyLoader:
    """
    Load and validate survey data from Excel files.

    Supports configurable column mapping via YAML schema.
    """

    def __init__(
        self,
        column_mapping: Optional[Dict[str, Dict[str, Any]]] = None,
        schema_path: Optional[Path] = None,
    ):
        """
        Initialize the survey loader.

        Args:
            column_mapping: Direct column mapping dict, or None to use default
            schema_path: Path to YAML schema file (overrides column_mapping)
        """
        if schema_path and Path(schema_path).exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = yaml.safe_load(f)
                self.column_mapping = schema.get("columns", DEFAULT_COLUMN_MAPPING)
        elif column_mapping:
            self.column_mapping = column_mapping
        else:
            self.column_mapping = DEFAULT_COLUMN_MAPPING

        self.validation_errors: List[Tuple[int, str]] = []

    def load(
        self,
        excel_path: Path,
        sheet_name: str = "Sheet0",
        header_row: int = 1,  # Row with column names (0-indexed)
        max_records: Optional[int] = None,
    ) -> List[SurveyRecord]:
        """
        Load survey data from Excel file.

        Args:
            excel_path: Path to Excel file
            sheet_name: Name of sheet to load
            header_row: Row index containing headers (question text)
            max_records: Maximum number of records to load (None for all)

        Returns:
            List of validated SurveyRecord objects
        """
        excel_path = Path(excel_path)
        if not excel_path.exists():
            raise FileNotFoundError(f"Survey file not found: {excel_path}")

        logger.info(f"Loading survey from {excel_path}")

        # Load Excel with headers
        df = pd.read_excel(
            excel_path,
            sheet_name=sheet_name,
            header=header_row,
        )

        logger.info(f"Loaded {len(df)} rows from survey")

        # Process each row
        records = []
        self.validation_errors = []

        for idx, row in df.iterrows():
            if max_records and len(records) >= max_records:
                break

            try:
                record = self._parse_row(idx, row)
                if record:
                    records.append(record)
            except Exception as e:
                self.validation_errors.append((idx, str(e)))
                logger.debug(f"Row {idx} validation error: {e}")

        valid_rate = len(records) / len(df) * 100 if len(df) > 0 else 0
        logger.info(
            f"Validated {len(records)}/{len(df)} records ({valid_rate:.1f}%), "
            f"{len(self.validation_errors)} errors"
        )

        return records

    def _parse_row(self, idx: int, row: pd.Series) -> Optional[SurveyRecord]:
        """Parse a single row into a SurveyRecord."""

        # Get values by column index
        def get_val(field: str) -> Any:
            col_info = self.column_mapping.get(field, {})
            col_idx = col_info.get("index")
            if col_idx is not None and col_idx < len(row):
                return row.iloc[col_idx]
            return None

        # Parse family size
        family_size_raw = get_val("family_size")
        family_size = self._parse_family_size(family_size_raw)
        if family_size is None:
            return None  # Required field

        # Parse income bracket
        income_raw = get_val("income_bracket")
        income_bracket = self._parse_income(income_raw)
        if income_bracket is None:
            return None  # Required field

        # Parse housing status
        housing_raw = get_val("housing_status")
        housing_status = self._parse_housing_status(housing_raw)
        if housing_status is None:
            return None  # Required field

        # Parse other fields (with defaults for missing)
        return SurveyRecord(
            record_id=f"S{idx:04d}",
            family_size=family_size,
            generations=self._parse_generations(get_val("generations")),
            income_bracket=income_bracket,
            housing_status=housing_status,
            house_type=self._parse_house_type(get_val("house_type")),
            housing_cost_burden=self._parse_boolean(get_val("housing_cost_burden")),
            vehicle_ownership=self._parse_boolean(get_val("vehicle_ownership")),
            flood_experience=self._parse_boolean(get_val("flood_experience")),
            financial_loss=self._parse_boolean(get_val("financial_loss")),
            children_under_6=self._parse_boolean(get_val("children_under_6")),
            children_6_18=self._parse_boolean(get_val("children_6_18")),
            elderly_over_65=self._parse_boolean(get_val("elderly_over_65")),
            raw_data=row.to_dict(),
        )

    def _parse_family_size(self, val: Any) -> Optional[int]:
        """Parse family size to integer."""
        if pd.isna(val):
            return None

        val_str = str(val).strip().lower()

        # Handle "More than 8" or "9 or more"
        if "more" in val_str or val_str == "9":
            return 9

        try:
            return int(float(val_str))
        except (ValueError, TypeError):
            return None

    def _parse_income(self, val: Any) -> Optional[str]:
        """Parse income bracket to standardized key."""
        if pd.isna(val):
            return None

        val_str = str(val).strip()

        # Try direct lookup
        if val_str in INCOME_BRACKETS:
            return INCOME_BRACKETS[val_str]

        # Try case-insensitive lookup
        val_lower = val_str.lower()
        for key, value in INCOME_BRACKETS.items():
            if key.lower() == val_lower:
                return value

        # Try partial match
        if "25,000" in val_str or "25000" in val_str:
            if "less" in val_str.lower():
                return "less_than_25k"
            return "25k_to_30k"
        if "75,000" in val_str or "75000" in val_str or "more" in val_str.lower():
            return "75k_or_more"

        return None

    def _parse_housing_status(self, val: Any) -> Optional[str]:
        """Parse housing status to standardized key."""
        if pd.isna(val):
            return None

        val_str = str(val).strip().lower()

        if "mortgage" in val_str:
            return "mortgage"
        if "rent" in val_str:
            return "rent"
        if "own" in val_str and "free" in val_str:
            return "own_free"
        if "own" in val_str:
            return "own_free"

        return None

    def _parse_generations(self, val: Any) -> str:
        """Parse generations lived at address."""
        if pd.isna(val):
            return "moved_here"

        val_str = str(val).strip().lower()

        if "moved" in val_str or "this generation" in val_str:
            return "moved_here"
        if "more than 3" in val_str or val_str == "4" or val_str == "5":
            return "more_than_3"

        try:
            gen = int(float(val_str))
            if gen <= 0:
                return "moved_here"
            if gen >= 4:
                return "more_than_3"
            return str(gen)
        except (ValueError, TypeError):
            return "moved_here"

    def _parse_house_type(self, val: Any) -> str:
        """Parse house type to standardized key."""
        if pd.isna(val):
            return "single_family"

        val_str = str(val).strip().lower()

        if "single" in val_str:
            return "single_family"
        if "multi" in val_str:
            return "multi_family"
        if "condo" in val_str:
            return "condo"
        if "mobile" in val_str:
            return "mobile_home"
        if "town" in val_str:
            return "townhouse"

        return "other"

    def _parse_boolean(self, val: Any) -> bool:
        """Parse a value as boolean."""
        if pd.isna(val):
            return False

        val_str = str(val).strip().lower()
        return val_str in ("yes", "true", "1", "y")

    def get_income_midpoint(self, income_bracket: str) -> float:
        """Get the midpoint value for an income bracket."""
        return INCOME_MIDPOINTS.get(income_bracket, 50000)


def load_survey_data(
    excel_path: Path,
    max_records: Optional[int] = None,
    schema_path: Optional[Path] = None,
) -> Tuple[List[SurveyRecord], List[Tuple[int, str]]]:
    """
    Convenience function to load survey data.

    Args:
        excel_path: Path to Excel file
        max_records: Maximum records to load
        schema_path: Optional path to YAML schema

    Returns:
        Tuple of (records, validation_errors)
    """
    loader = SurveyLoader(schema_path=schema_path)
    records = loader.load(excel_path, max_records=max_records)
    return records, loader.validation_errors
