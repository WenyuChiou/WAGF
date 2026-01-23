from typing import List

import pandas as pd

def compute_construct_score(row: pd.Series, columns: List[str]) -> float:
    """
    Compute mean score for a PMT construct.

    Args:
        row: Survey response row
        columns: List of column names for this construct

    Returns:
        Mean score (1-5), defaults to 3.0 if no valid responses
    """
    values = []
    for col in columns:
        if col in row.index and pd.notna(row[col]):
            val = row[col]
            # Convert Likert text to number
            if isinstance(val, str):
                val = LIKERT_MAP.get(val.strip(), 3)
            elif isinstance(val, (int, float)):
                val = max(1, min(5, val))  # Clamp to 1-5
            else:
                continue
            values.append(val)

    return np.mean(values) if values else 3.0
