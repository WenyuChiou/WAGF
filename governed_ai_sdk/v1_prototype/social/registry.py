"""
Registry for domain-specific social observers.
"""
from typing import Dict, Optional, List
from .observer import SocialObserver


class ObserverRegistry:
    """Global registry for social observers by domain."""

    _observers: Dict[str, SocialObserver] = {}

    @classmethod
    def register(cls, observer: SocialObserver) -> None:
        """Register an observer for its domain."""
        cls._observers[observer.domain] = observer

    @classmethod
    def get(cls, domain: str) -> Optional[SocialObserver]:
        """Get observer for domain."""
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
        """Clear all observers (useful for testing)."""
        cls._observers.clear()


__all__ = ["ObserverRegistry"]
