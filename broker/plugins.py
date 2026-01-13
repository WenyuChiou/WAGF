"""
Plugin Registry Pattern for Third-Party Extensions.

Provides a centralized registry for registering and discovering:
- Custom ContextProviders
- Custom Validators
- Custom MemoryEngines
- Custom Adapters

Phase 25 PR11: Priority 3 - Plugin Registry
"""
from typing import Dict, Type, Any, Optional, List, Callable
from abc import ABC, abstractmethod


class Plugin(ABC):
    """Base class for all plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""
        ...
    
    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """Plugin description."""
        return ""


class PluginRegistry:
    """
    Central registry for framework plugins.
    
    Supports registration and discovery of:
    - context_providers: Custom ContextProvider implementations
    - validators: Custom AgentValidator implementations  
    - memory_engines: Custom MemoryEngine implementations
    - adapters: Custom ModelAdapter implementations
    - preprocessors: LLM output preprocessors (like DeepSeek)
    
    Usage:
        registry = PluginRegistry()
        registry.register("context_providers", "my_provider", MyProvider)
        provider_class = registry.get("context_providers", "my_provider")
    """
    
    _instance: Optional['PluginRegistry'] = None
    
    def __new__(cls):
        """Singleton pattern for global registry access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: Dict[str, Dict[str, Any]] = {
                "context_providers": {},
                "validators": {},
                "memory_engines": {},
                "adapters": {},
                "preprocessors": {},
                "hooks": {}
            }
        return cls._instance
    
    def register(self, category: str, name: str, plugin: Any, metadata: Dict = None):
        """
        Register a plugin in the specified category.
        
        Args:
            category: Plugin category (context_providers, validators, etc.)
            name: Unique name for the plugin
            plugin: Plugin class or callable
            metadata: Optional metadata dict
        """
        if category not in self._plugins:
            self._plugins[category] = {}
        
        self._plugins[category][name] = {
            "plugin": plugin,
            "metadata": metadata or {}
        }
    
    def get(self, category: str, name: str) -> Optional[Any]:
        """
        Get a registered plugin by category and name.
        
        Returns:
            Plugin class/callable or None if not found
        """
        if category not in self._plugins:
            return None
        entry = self._plugins[category].get(name)
        return entry["plugin"] if entry else None
    
    def list_plugins(self, category: str = None) -> Dict[str, List[str]]:
        """
        List all registered plugins.
        
        Args:
            category: Specific category to list, or None for all
            
        Returns:
            Dict mapping categories to plugin names
        """
        if category:
            return {category: list(self._plugins.get(category, {}).keys())}
        return {cat: list(plugins.keys()) for cat, plugins in self._plugins.items()}
    
    def unregister(self, category: str, name: str) -> bool:
        """Remove a plugin from the registry."""
        if category in self._plugins and name in self._plugins[category]:
            del self._plugins[category][name]
            return True
        return False
    
    def clear(self, category: str = None):
        """Clear all plugins or a specific category."""
        if category:
            self._plugins[category] = {}
        else:
            for cat in self._plugins:
                self._plugins[cat] = {}


# Convenience decorators for plugin registration
def register_provider(name: str):
    """Decorator to register a ContextProvider."""
    def decorator(cls):
        PluginRegistry().register("context_providers", name, cls)
        return cls
    return decorator


def register_validator(name: str):
    """Decorator to register a Validator."""
    def decorator(cls):
        PluginRegistry().register("validators", name, cls)
        return cls
    return decorator


def register_memory_engine(name: str):
    """Decorator to register a MemoryEngine."""
    def decorator(cls):
        PluginRegistry().register("memory_engines", name, cls)
        return cls
    return decorator


def register_preprocessor(name: str):
    """Decorator to register a preprocessor function."""
    def decorator(func):
        PluginRegistry().register("preprocessors", name, func)
        return func
    return decorator


# Global registry instance
plugins = PluginRegistry()
