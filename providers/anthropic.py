"""
Anthropic LLM Provider - API support for Claude models.

Works with any Claude model ID, e.g. claude-haiku-5-5, claude-sonnet-5-5,
claude-opus-5-5. Temperature is sent only when the config sets one: current
Claude models reject it (Opus 5.5) or accept only the default (Sonnet 5.5,
Haiku 5.5).

Usage:
    --model anthropic:claude-haiku-5-5
    --model claude:claude-sonnet-5-5
"""
from typing import Any, Dict
import os

from providers.llm_provider import LLMProvider, LLMConfig, LLMResponse

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Used when the config sets no max_tokens (the API requires one).
DEFAULT_MAX_TOKENS = 16000


class AnthropicProvider(LLMProvider):
    """
    LLM Provider for Anthropic Claude API.

    Usage:
        config = LLMConfig(model="claude-sonnet-4-5-20250929")
        provider = AnthropicProvider(config, api_key="sk-ant-...")
        response = provider.invoke("Hello!")
    """

    def __init__(
        self,
        config: LLMConfig,
        api_key: str = None,
    ):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        super().__init__(config)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY environment "
                "variable or pass api_key parameter."
            )

        self._client = anthropic.Anthropic(api_key=self.api_key)
        self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _request_kwargs(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Build the Messages API request; omit temperature when it is unset.

        ``max_tokens`` is required by the API. When unset it defaults to
        DEFAULT_MAX_TOKENS, which leaves room for the thinking that current
        Claude models do before answering.
        """
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        request: Dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        temperature = kwargs.get("temperature", self.config.temperature)
        if temperature is not None:
            request["temperature"] = temperature
        return request

    def invoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Synchronously invoke Claude model."""
        response = self._client.messages.create(
            **self._request_kwargs(prompt, **kwargs)
        )

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": (
                    response.usage.input_tokens + response.usage.output_tokens
                ),
            },
            metadata={
                "stop_reason": response.stop_reason,
                "id": response.id,
            },
            raw_response=response,
        )

    async def ainvoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Asynchronously invoke Claude model."""
        response = await self._async_client.messages.create(
            **self._request_kwargs(prompt, **kwargs)
        )

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": (
                    response.usage.input_tokens + response.usage.output_tokens
                ),
            },
            metadata={
                "stop_reason": response.stop_reason,
                "id": response.id,
            },
            raw_response=response,
        )

    def validate_connection(self) -> bool:
        """Check if API key is valid by sending a minimal request."""
        try:
            self._client.messages.create(
                model=self.config.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception:
            return False
