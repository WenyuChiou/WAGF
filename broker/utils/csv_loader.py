
"""
Generic CSV loader with flexible column mapping.

.. deprecated:: 0.7.0
    Use :class:`broker.core.agent_initializer.CSVLoader` for schema-mapped
    profile loading in new domains.
"""
from __future__ import annotations

import warnings
from typing import Dict, List
import pandas as pd


def load_csv_with_mapping(
    csv_path: str,
    column_mapping: Dict[str, Dict],
    required_fields: List[str]
) -> pd.DataFrame:
    """Generic CSV loader with flexible column mapping.

    .. deprecated:: 0.7.0
        Use :class:`broker.core.agent_initializer.CSVLoader` instead.
    """
    warnings.warn(
        "broker.utils.csv_loader.load_csv_with_mapping is deprecated since v0.7.0; "
        "use broker.core.agent_initializer.CSVLoader instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
