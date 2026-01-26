"""
Config package - DEPRECATED

This module is deprecated. Please import from governed_ai_sdk.config instead:

    # Old (deprecated)
    from config import DomainConfigLoader

    # New
    from governed_ai_sdk.config import DomainConfigLoader

Task-037: SDK-Broker Architecture Separation
"""
import warnings

warnings.warn(
    "The 'config' module is deprecated. "
    "Please import from 'governed_ai_sdk.config' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from SDK for backward compatibility
from governed_ai_sdk.config import (
    DomainConfigLoader,
    load_domain,
    SkillDefinition,
    ValidatorConfig,
)

__all__ = [
    "DomainConfigLoader",
    "load_domain",
    "SkillDefinition",
    "ValidatorConfig",
]
