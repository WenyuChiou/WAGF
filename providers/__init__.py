"""
LLM Provider Implementations.

Concrete implementations of LLMProvider for different backends:
- OllamaProvider: Local models via Ollama
- OpenAIProvider: OpenAI API (GPT-4, etc.)
- AnthropicProvider: Anthropic API (Claude)
- GeminiProvider: Google Gemini API

Providers are imported lazily to avoid requiring all optional dependencies
(httpx, openai, anthropic, etc.) at import time.
"""
from .factory import create_provider, load_providers_from_config
from .rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitedProvider,
    RetryHandler
)


def __getattr__(name):
    """Lazy import for provider classes that require optional dependencies."""
    if name == "OllamaProvider":
        from .ollama import OllamaProvider
        return OllamaProvider
    if name == "OpenAIProvider":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "OllamaProvider",
    "OpenAIProvider",
    "create_provider",
    "load_providers_from_config",
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitedProvider",
    "RetryHandler",
]
