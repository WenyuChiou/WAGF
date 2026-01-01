"""
Test LLM Provider Interface

Tests for:
- OllamaProvider
- LLMProviderRegistry
- Provider Factory
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from interfaces.llm_provider import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    LLMProviderRegistry,
    RoutingLLMProvider
)


class TestLLMConfig:
    """Test LLMConfig dataclass."""
    
    def test_default_values(self):
        config = LLMConfig(model="test-model")
        assert config.model == "test-model"
        assert config.temperature == 0.7
        assert config.max_tokens == 1024
        assert config.timeout == 60.0
    
    def test_custom_values(self):
        config = LLMConfig(
            model="gpt-4",
            temperature=0.5,
            max_tokens=2048,
            timeout=120.0
        )
        assert config.temperature == 0.5
        assert config.max_tokens == 2048


class TestLLMProviderRegistry:
    """Test LLMProviderRegistry."""
    
    def test_register_provider(self):
        registry = LLMProviderRegistry()
        mock_provider = Mock(spec=LLMProvider)
        
        registry.register("test", mock_provider)
        
        assert "test" in registry
        assert registry.get("test") == mock_provider
    
    def test_default_provider(self):
        registry = LLMProviderRegistry()
        mock_provider = Mock(spec=LLMProvider)
        
        registry.register("local", mock_provider, set_default=True)
        
        assert registry.default == mock_provider
    
    def test_list_providers(self):
        registry = LLMProviderRegistry()
        registry.register("p1", Mock(spec=LLMProvider))
        registry.register("p2", Mock(spec=LLMProvider))
        
        providers = registry.list_providers()
        
        assert "p1" in providers
        assert "p2" in providers
    
    def test_get_nonexistent_raises(self):
        registry = LLMProviderRegistry()
        
        with pytest.raises(KeyError):
            registry.get("nonexistent")


class TestRoutingLLMProvider:
    """Test RoutingLLMProvider."""
    
    def test_routes_by_context(self):
        registry = LLMProviderRegistry()
        local_provider = Mock(spec=LLMProvider)
        cloud_provider = Mock(spec=LLMProvider)
        
        local_provider.invoke.return_value = LLMResponse(
            content="local response",
            model="llama",
            usage={}
        )
        cloud_provider.invoke.return_value = LLMResponse(
            content="cloud response",
            model="gpt-4",
            usage={}
        )
        
        registry.register("local", local_provider)
        registry.register("cloud", cloud_provider)
        
        router = RoutingLLMProvider(
            config=LLMConfig(model="router"),
            registry=registry,
            routing_rules={"default": "local", "high_stakes": "cloud"}
        )
        
        # Default context uses local
        response = router.invoke("test", context="default")
        assert response.content == "local response"
        
        # High stakes uses cloud
        response = router.invoke("test", context="high_stakes")
        assert response.content == "cloud response"
    
    def test_fallback_on_failure(self):
        registry = LLMProviderRegistry()
        local_provider = Mock(spec=LLMProvider)
        cloud_provider = Mock(spec=LLMProvider)
        
        local_provider.invoke.side_effect = Exception("Local failed")
        cloud_provider.invoke.return_value = LLMResponse(
            content="fallback response",
            model="gpt-4",
            usage={}
        )
        
        registry.register("local", local_provider)
        registry.register("cloud", cloud_provider)
        
        router = RoutingLLMProvider(
            config=LLMConfig(model="router"),
            registry=registry,
            routing_rules={"default": "local"},
            fallback_provider="cloud"
        )
        
        response = router.invoke("test")
        assert response.content == "fallback response"


class TestProviderFactory:
    """Test provider factory functions."""
    
    def test_create_ollama_provider(self):
        from providers.factory import create_provider
        
        provider = create_provider({
            "type": "ollama",
            "model": "llama3.2:3b"
        })
        
        assert provider.provider_name == "ollama"
        assert provider.model_name == "llama3.2:3b"
    
    def test_unknown_provider_raises(self):
        from providers.factory import create_provider
        
        with pytest.raises(ValueError):
            create_provider({"type": "unknown", "model": "test"})


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
