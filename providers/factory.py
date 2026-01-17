"""
Provider Factory - Create LLM providers from configuration.

Enables loading providers from YAML configuration files,
supporting multi-LLM experiments with minimal code changes.
"""
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import os

from interfaces.llm_provider import LLMProvider, LLMConfig, LLMProviderRegistry


def create_provider(config: Dict[str, Any]) -> LLMProvider:
    """
    Create an LLM provider from configuration dictionary.
    
    Args:
        config: Provider configuration with 'type' and 'model' keys
        
    Returns:
        LLMProvider instance
    """
    provider_type = config.get("type", "ollama").lower()
    
    # 1. Base Configuration
    llm_config = LLMConfig(
        model=config.get("model", "llama3.2:3b"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 1024),
        timeout=config.get("timeout", 60.0),
        extra_params=config.get("extra_params", {})
    )
    
    # 2. Instantiate Concrete Provider
    provider = None
    if provider_type == "ollama":
        from .ollama import OllamaProvider
        provider = OllamaProvider(
            config=llm_config,
            base_url=config.get("base_url", "http://localhost:11434")
        )
    elif provider_type in ("openai", "azure"):
        from .openai_provider import OpenAIProvider
        
        api_key = config.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var, "")
            
        provider = OpenAIProvider(
            config=llm_config,
            api_key=api_key,
            base_url=config.get("base_url")
        )
    
    elif provider_type == "gemini":
        from .gemini import GeminiProvider
        
        api_key = config.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var, "")
            
        provider = GeminiProvider(
            config=llm_config,
            api_key=api_key
        )
    
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")

    # 3. Apply Rate Limiting / Retries if specified
    rpm_limit = config.get("rpm_limit")
    max_retries = config.get("max_retries", 3)
    
    # If using cloud providers, default to some safety if not specified
    if provider_type in ["gemini", "openai"] and rpm_limit is None:
        # Defaults for safety (adjust as needed)
        rpm_limit = 15 

    if rpm_limit or max_retries:
        from interfaces.llm_provider import RateLimitedProvider
        provider = RateLimitedProvider(
            base_provider=provider,
            max_retries=max_retries,
            rpm_limit=rpm_limit
        )
        
    return provider


def load_providers_from_config(config_path: str | Path) -> LLMProviderRegistry:
    """
    Load LLM providers from YAML configuration file.
    
    Args:
        config_path: Path to providers.yaml file
        
    Returns:
        LLMProviderRegistry with all configured providers
        
    Example YAML:
        providers:
          local-llama:
            type: ollama
            model: llama3.2:3b
          cloud-gpt4:
            type: openai
            model: gpt-4-turbo
            api_key: ${OPENAI_API_KEY}
        
        default: local-llama
        
        routing:
          high_stakes: cloud-gpt4
          simple: local-llama
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    registry = LLMProviderRegistry()
    
    # Load each provider
    providers_config = config.get("providers", {})
    for name, provider_config in providers_config.items():
        provider = create_provider(provider_config)
        registry.register(name, provider)
    
    # Set default
    default_name = config.get("default")
    if default_name and default_name in registry:
        registry.set_default(default_name)
    
    return registry


def create_routing_provider(
    config_path: str | Path,
    routing_key: str = "routing"
) -> LLMProvider:
    """
    Create a routing provider from configuration.
    
    Args:
        config_path: Path to providers.yaml
        routing_key: Key in config for routing rules
        
    Returns:
        RoutingLLMProvider configured with routing rules
    """
    from interfaces.llm_provider import RoutingLLMProvider, LLMConfig
    
    path = Path(config_path)
    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    registry = load_providers_from_config(config_path)
    routing_rules = config.get(routing_key, {"default": config.get("default")})
    
    return RoutingLLMProvider(
        config=LLMConfig(model="router"),
        registry=registry,
        routing_rules=routing_rules,
        fallback_provider=config.get("fallback")
    )
