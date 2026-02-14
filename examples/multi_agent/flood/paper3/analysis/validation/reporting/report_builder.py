"""
Validation Report Builder — data classes and serialization.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from validation.metrics.l1_micro import L1Metrics
from validation.metrics.l2_macro import L2Metrics


@dataclass
class ValidationReport:
    """Complete validation report."""
    l1: L1Metrics
    l2: L2Metrics
    traces_path: str
    seed: Optional[int]
    model: str
    pass_all: bool


def _to_json_serializable(obj):
    """Convert numpy/pandas types to JSON-serializable Python types."""
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_json_serializable(v) for v in obj]
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    return obj
