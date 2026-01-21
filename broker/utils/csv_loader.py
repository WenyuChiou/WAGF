
"""
Generic CSV loader with flexible column mapping.
"""
from __future__ import annotations

from typing import Dict, List
import pandas as pd


def load_csv_with_mapping(
    csv_path: str,
    column_mapping: Dict[str, Dict],
    required_fields: List[str]
) -> pd.DataFrame:
    """Generic CSV loader with flexible column mapping.

    Args:
        csv_path: Path to CSV file
        column_mapping: Dict mapping output field -> {"col": <name>} or {"index": <int>}
        required_fields: List of required output fields

    Returns:
        DataFrame with mapped output columns only
    """
    df = pd.read_csv(csv_path)

    missing_required = [f for f in required_fields if f not in column_mapping]
    if missing_required:
        raise ValueError(f"Missing required mapping(s): {missing_required}")

    missing_columns = []
    mapped = {}
    for field, mapping in column_mapping.items():
        if "col" in mapping:
            col = mapping["col"]
            if col not in df.columns:
                missing_columns.append(col)
                continue
            mapped[field] = df[col]
        elif "index" in mapping:
            idx = mapping["index"]
            try:
                mapped[field] = df.iloc[:, idx]
            except IndexError:
                missing_columns.append(str(idx))
        else:
            raise ValueError(f"Invalid mapping for {field}: {mapping}")

    if missing_columns:
        raise ValueError(f"Missing columns: {missing_columns}")

    return pd.DataFrame(mapped)
