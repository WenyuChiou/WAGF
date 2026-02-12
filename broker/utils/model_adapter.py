"""
Model Adapter - Thin layer for multi-LLM support.

Re-export shim: the actual classes live in broker/utils/parsing/.
All existing imports continue to work.
"""
from .parsing import ModelAdapter, UnifiedAdapter, get_adapter  # noqa: F401
from .adapters.deepseek import deepseek_preprocessor  # noqa: F401

__all__ = ["ModelAdapter", "UnifiedAdapter", "get_adapter", "deepseek_preprocessor"]
