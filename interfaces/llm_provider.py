from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

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
