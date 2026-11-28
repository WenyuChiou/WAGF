"""
Model Adapter - Supported backward-compatibility re-export shim.

The canonical implementations live in :mod:`broker.utils.parsing`. Retained
without deprecation warnings for existing runners and tests.
"""
from .parsing import ModelAdapter, UnifiedAdapter, get_adapter  # noqa: F401
from .adapters.deepseek import deepseek_preprocessor  # noqa: F401

__all__ = ["ModelAdapter", "UnifiedAdapter", "get_adapter", "deepseek_preprocessor"]
