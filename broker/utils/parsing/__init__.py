"""
Parsing sub-package — LLM output parsing and model adapters.

Extracted from model_adapter.py (Phase 2.2 split).
"""
from .base import ModelAdapter  # noqa: F401
from .unified_adapter import UnifiedAdapter  # noqa: F401


def get_adapter(model_name: str, config_path: str = None) -> ModelAdapter:
    """
    Get the appropriate adapter for a model.

    Uses UnifiedAdapter with model-specific preprocessor if needed.
    """
    from ..adapters.deepseek import deepseek_preprocessor

    model_lower = model_name.lower()

    # DeepSeek models use <think> tags
    if 'deepseek' in model_lower:
        return UnifiedAdapter(preprocessor=deepseek_preprocessor, config_path=config_path)

    # All other models use standard adapter
    # (Llama, Gemma, GPT-OSS, OpenAI, Anthropic, etc.)
    return UnifiedAdapter(config_path=config_path)
