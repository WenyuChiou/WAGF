"""
Gemini LLM Provider - support for Google Gemini models via API.

Supports:
- gemini-1.5-flash
- gemini-1.5-pro
- gemini-2.0-flash-exp (if available)
"""
import os
import asyncio
from typing import Any, Dict, Optional
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse

from providers.llm_provider import LLMProvider, LLMConfig, LLMResponse

class GeminiProvider(LLMProvider):
    """
    LLM Provider for Google Gemini API.
    
    Usage:
        config = LLMConfig(model="gemini-1.5-flash")
        provider = GeminiProvider(config, api_key="YOUR_API_KEY")
        response = provider.invoke("Hello!")
    """
    
    def __init__(
        self,
        config: LLMConfig,
        api_key: Optional[str] = None
    ):
        super().__init__(config)
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key not found. Set GOOGLE_API_KEY env var or pass in constructor.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.config.model,
            generation_config={
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens,
            },
            safety_settings={
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            }
        )
    
    @property
    def provider_name(self) -> str:
        return "gemini"
    
    def _format_response(self, response: GenerateContentResponse) -> LLMResponse:
        """Helper to convert Gemini response to standard LLMResponse."""
        try:
            content = response.text
        except ValueError:
            # If the response was blocked, we can't access .text
            content = f"Error: Response blocked by safety filters. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'unknown'}"
            
        return LLMResponse(
            content=content,
            model=self.config.model,
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
            },
            metadata={
                "finish_reason": str(response.candidates[0].finish_reason) if response.candidates else "unknown",
            },
            raw_response=response
        )
    
    def invoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Synchronously invoke Gemini model."""
        # Optional: override generation config if kwargs provided
        generation_config = {
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        
        response = self.model.generate_content(
            prompt,
            generation_config=generation_config
        )
        return self._format_response(response)
    
    async def ainvoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Asynchronously invoke Gemini model."""
        generation_config = {
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        
        response = await self.model.generate_content_async(
            prompt,
            generation_config=generation_config
        )
        return self._format_response(response)
    
    def validate_connection(self) -> bool:
        """Simple check by listing models (requires valid key)."""
        try:
            # Try a very small generation or list models
            # listing models is safer as it doesn't consume tokens for actual gen
            for m in genai.list_models():
                if self.config.model in m.name:
                    return True
            return False
        except Exception:
            return False
