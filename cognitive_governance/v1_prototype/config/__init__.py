"""
Configuration Module.

Provides unified configuration loading and schema definitions for experiments.

Components:
- schema.py: Configuration dataclasses (ExperimentConfig, MemoryConfig, etc.)
- loader.py: UnifiedConfigLoader for YAML loading with env interpolation

Usage:
    >>> from cognitive_governance.v1_prototype.config import (
    ...     ExperimentConfig,
    ...     UnifiedConfigLoader,
    ...     load_config,
    ...     create_default_config,
    ... )
    >>>
    >>> # Load from YAML file
    >>> config = load_config("config/flood_study.yaml")
    >>>
    >>> # Or create programmatically
    >>> config = create_default_config("flood", agents=100, years=10)
    >>>
    >>> # Access nested configs
    >>> print(config.memory.engine)
    >>> print(config.llm.model)
"""

from .schema import (
    MemoryConfig,
    ReflectionConfig,
    SocialConfig,
    GovernanceConfig,
    LLMConfig,
    DomainPackConfig,
    OutputConfig,
    ExperimentConfig,
)

from .loader import (
    UnifiedConfigLoader,
    load_config,
    create_default_config,
)

__all__ = [
    # Schema dataclasses
    "MemoryConfig",
    "ReflectionConfig",
    "SocialConfig",
    "GovernanceConfig",
    "LLMConfig",
    "DomainPackConfig",
    "OutputConfig",
    "ExperimentConfig",
    # Loader
    "UnifiedConfigLoader",
    "load_config",
    "create_default_config",
]
