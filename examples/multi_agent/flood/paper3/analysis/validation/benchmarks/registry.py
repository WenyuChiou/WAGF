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
                 **kwargs) -> Optional[float]:
        """Dispatch to registered benchmark function.

        Args:
            name: Benchmark name.
            df: Agent profiles DataFrame with inferred final states.
            traces: List of decision trace dicts.
            **kwargs: Domain-specific keyword arguments forwarded to the
                registered function (e.g., ins_col, elev_col for flood).
        """
        if name not in self._registry:
            return None
        try:
            return self._registry[name](df, traces, **kwargs)
        except Exception as e:
            print(f"Warning: Could not compute {name}: {e}")
            return None

    @property
    def names(self) -> List[str]:
        return list(self._registry.keys())
