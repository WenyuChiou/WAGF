"""
Benchmark Registry — decorator-based dispatch for benchmark computations.
"""

from typing import Callable, Dict, List, Optional

import pandas as pd


class BenchmarkRegistry:
    """Registry for benchmark computation functions."""

    def __init__(self):
        self._registry: Dict[str, Callable] = {}

    def register(self, name: str):
        """Decorator to register a benchmark computation function."""
        def decorator(func: Callable):
            self._registry[name] = func
            return func
        return decorator

    def dispatch(self, name: str, df: pd.DataFrame, traces: List[Dict],
                 ins_col: Optional[str], elev_col: Optional[str]) -> Optional[float]:
        """Dispatch to registered benchmark function."""
        if name not in self._registry:
            return None
        try:
            return self._registry[name](df, traces, ins_col, elev_col)
        except Exception as e:
            print(f"Warning: Could not compute {name}: {e}")
            return None

    @property
    def names(self) -> List[str]:
        return list(self._registry.keys())
