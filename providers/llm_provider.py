from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Callable
import time
import asyncio
import random
import threading

@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""
    model: str
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout: float = 60.0
    extra_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LLMResponse:
    """Standardized response from an LLM provider."""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_response: Any = None

class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique name of the provider."""
        ...
        
    @abstractmethod
    def invoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Synchronously invoke the LLM."""
        ...
        
    @abstractmethod
    async def ainvoke(self, prompt: str, **kwargs) -> LLMResponse:
        """Asynchronously invoke the LLM."""
        ...
        
    def validate_connection(self) -> bool:
        """Check if provider is available and properly configured."""
        return True

class LLMProviderRegistry:
    """Registry to manage multiple LLM providers."""
    
    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._default: Optional[str] = None
        
    def register(self, name: str, provider: LLMProvider):
        self._providers[name] = provider
        if not self._default:
            self._default = name
            
    def set_default(self, name: str):
        if name in self._providers:
            self._default = name
            
    def get(self, name: str = None) -> LLMProvider:
        key = name or self._default
        if not key or key not in self._providers:
            raise ValueError(f"Provider not found: {key}")
        return self._providers[key]
    
    def __contains__(self, name: str) -> bool:
        return name in self._providers
    
    def items(self):
        return self._providers.items()

class RoutingLLMProvider(LLMProvider):
    """Provider that routes requests to different underlying providers based on rules."""
    
    def __init__(
        self, 
        config: LLMConfig, 
        registry: LLMProviderRegistry,
        routing_rules: Dict[str, str],
        fallback_provider: Optional[str] = None
    ):
        super().__init__(config)
        self.registry = registry
        self.routing_rules = routing_rules
        self.fallback_provider = fallback_provider
        
    @property
    def provider_name(self) -> str:
        return "router"
        
    def _get_provider_for_rule(self, rule: str) -> LLMProvider:
        name = self.routing_rules.get(rule) or self.fallback_provider
        return self.registry.get(name)
        
    def invoke(self, prompt: str, **kwargs) -> LLMResponse:
        rule = kwargs.get("routing_rule", "default")
        provider = self._get_provider_for_rule(rule)
        return provider.invoke(prompt, **kwargs)
        
    async def ainvoke(self, prompt: str, **kwargs) -> LLMResponse:
        rule = kwargs.get("routing_rule", "default")
        provider = self._get_provider_for_rule(rule)
        return await provider.ainvoke(prompt, **kwargs)

class RateLimitedProvider(LLMProvider):
    """
    Wrapper for LLMProvider that adds rate limiting and retry logic.
    
    Args:
        base_provider: The provider to wrap
        max_retries: Maximum number of retries per call
        delay_seconds: Fixed delay between retry attempts
        rpm_limit: Optional requests-per-minute target (adds sleep if needed)
    """
    def __init__(
        self, 
        base_provider: LLMProvider,
        max_retries: int = 3,
        delay_seconds: float = 2.0,
        rpm_limit: Optional[int] = None
    ):
        super().__init__(base_provider.config)
        self.base_provider = base_provider
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        self.rpm_delay = 60.0 / rpm_limit if rpm_limit else 0.0
        self._last_call_time = 0.0
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return f"rate_limited_{self.base_provider.provider_name}"

    def _wait_for_rpm(self):
        if self.rpm_delay > 0:
            with self._lock:
                elapsed = time.time() - self._last_call_time
                if elapsed < self.rpm_delay:
                    time.sleep(self.rpm_delay - elapsed)
                self._last_call_time = time.time()

    async def _await_for_rpm(self):
        if self.rpm_delay > 0:
            # Note: For async, we should ideally use asyncio.Lock, 
            # but if we are in a mixed thread environment (like ExperimentRunner), 
            # threading.Lock is safer for the shared variable.
            # However, await must not be inside threading.Lock.
            
            # Simple spin-lock with sleep for async
            while True:
                with self._lock:
                    elapsed = time.time() - self._last_call_time
                    if elapsed >= self.rpm_delay:
                        self._last_call_time = time.time()
                        return
                    wait = self.rpm_delay - elapsed
                await asyncio.sleep(wait)

    def invoke(self, prompt: str, **kwargs) -> LLMResponse:
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                self._wait_for_rpm()
                return self.base_provider.invoke(prompt, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Exponential backoff: delay * (2^attempt) + jitter
                    wait = self.delay_seconds * (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait)
        raise last_exception

    async def ainvoke(self, prompt: str, **kwargs) -> LLMResponse:
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                await self._await_for_rpm()
                return await self.base_provider.ainvoke(prompt, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait = self.delay_seconds * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait)
        raise last_exception

    def validate_connection(self) -> bool:
        return self.base_provider.validate_connection()
