"""Registry for environment observers."""
from typing import Dict, List, Optional
from .environment import EnvironmentObserver


class EnvironmentObserverRegistry:
    """
    Registry for domain-specific environment observers.

    Usage:
        >>> EnvironmentObserverRegistry.register(FloodEnvObserver())
        >>> observer = EnvironmentObserverRegistry.get("flood")
        >>> observation = observer.observe(agent, environment)
    """

    _observers: Dict[str, EnvironmentObserver] = {}

    @classmethod
    def register(cls, observer: EnvironmentObserver) -> None:
        """Register an environment observer."""
        cls._observers[observer.domain] = observer

    @classmethod
    def get(cls, domain: str) -> Optional[EnvironmentObserver]:
        """Get observer for a domain."""
        return cls._observers.get(domain)

    @classmethod
    def has(cls, domain: str) -> bool:
        """Check if domain has a registered observer."""
        return domain in cls._observers

    @classmethod
    def list_domains(cls) -> List[str]:
        """List all registered domains."""
        return list(cls._observers.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered observers."""
        cls._observers.clear()


__all__ = ["EnvironmentObserverRegistry"]
