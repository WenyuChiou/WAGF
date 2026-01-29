"""
Ollama LLM Provider - Local model support via Ollama.

Supports all models available in Ollama:
- llama3.2:3b, llama3.2:8b
- gemma3:4b
- deepseek-r1:8b
- mistral, etc.
"""
import asyncio
from typing import Any, Dict
import httpx

from providers.llm_provider import LLMProvider, LLMConfig, LLMResponse


class OllamaProvider(LLMProvider):
    """
    LLM Provider for Ollama (local models).
    
    Usage:
        config = LLMConfig(model="llama3.2:3b")
        provider = OllamaProvider(config, base_url="http://localhost:11434")
        response = provider.invoke("Hello!")
    """
    
    def __init__(self, config: LLMConfig, base_url: str = "http://localhost:11434"):
        super().__init__(config)
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=config.timeout)
        self._async_client = None  # Lazy init
    
    @property
    def provider_name(self) -> str:
        return "ollama"
    
    def invoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Synchronously invoke Ollama model."""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            }
        }
        
        # Add any extra params
        payload["options"].update(self.config.extra_params)
        
        response = self._client.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        return LLMResponse(
            content=data.get("response", ""),
            model=self.config.model,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
            metadata={
                "total_duration": data.get("total_duration", 0),
                "load_duration": data.get("load_duration", 0),
            },
            raw_response=data
        )
    
    async def ainvoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Asynchronously invoke Ollama model."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.config.timeout)
        
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            }
        }
        
        payload["options"].update(self.config.extra_params)
        
        response = await self._async_client.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        return LLMResponse(
            content=data.get("response", ""),
            model=self.config.model,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
            metadata={
                "total_duration": data.get("total_duration", 0),
            },
            raw_response=data
        )
    
    def validate_connection(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            # Check if model exists
            url = f"{self.base_url}/api/tags"
            response = self._client.get(url)
            response.raise_for_status()
            
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            
            # Check if our model is available (with or without tag)
            model_base = self.config.model.split(":")[0]
            return any(model_base in m for m in models)
        except Exception:
            return False
    
    def __del__(self):
        """Cleanup connections."""
        if hasattr(self, "_client"):
            self._client.close()
        if hasattr(self, "_async_client") and self._async_client:
            # Async cleanup should be handled properly in async context
            pass
