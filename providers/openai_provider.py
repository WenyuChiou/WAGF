"""
OpenAI LLM Provider - API support for OpenAI models.

Supports:
- gpt-4-turbo, gpt-4
- gpt-3.5-turbo
- And OpenAI-compatible APIs (Azure, local deployments)
"""
from typing import Any, Dict
import os

from providers.llm_provider import LLMProvider, LLMConfig, LLMResponse

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class OpenAIProvider(LLMProvider):
    """
    LLM Provider for OpenAI API.
    
    Usage:
        config = LLMConfig(model="gpt-4-turbo")
        provider = OpenAIProvider(config, api_key="sk-...")
        response = provider.invoke("Hello!")
    """
    
    def __init__(
        self,
        config: LLMConfig,
        api_key: str = None,
        base_url: str = None
    ):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        super().__init__(config)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        
        # Initialize client
        client_kwargs = {"api_key": self.api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self._client = openai.OpenAI(**client_kwargs)
        self._async_client = openai.AsyncOpenAI(**client_kwargs)
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    def invoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Synchronously invoke OpenAI model."""
        messages = [{"role": "user", "content": prompt}]
        
        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        
        choice = response.choices[0]
        
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            metadata={
                "finish_reason": choice.finish_reason,
                "id": response.id,
            },
            raw_response=response
        )
    
    async def ainvoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Asynchronously invoke OpenAI model."""
        messages = [{"role": "user", "content": prompt}]
        
        response = await self._async_client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        
        choice = response.choices[0]
        
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            metadata={
                "finish_reason": choice.finish_reason,
                "id": response.id,
            },
            raw_response=response
        )
    
    def validate_connection(self) -> bool:
        """Check if API key is valid."""
        try:
            self._client.models.list()
            return True
        except Exception:
            return False
